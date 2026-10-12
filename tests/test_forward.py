"""Synthetic fixtures verify recorder mechanics, never strategy performance."""
import copy
import gzip
import json
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
import pytest
from pm_alpha.schema import DataInvalid, utc
from pm_alpha.storage import Store, digest
from pm_alpha.data.forward_http import RateLimiter, ForwardHTTP, Response
from pm_alpha.data.http import AccessBlocked
from pm_alpha.forward_schema import parse_forward_book, Eligibility, kalshi_metadata, polymarket_metadata, category
from pm_alpha.cohort import freeze_cohort, Cohort, save_snapshot, cohort_summary, COHORT_ID
from pm_alpha.forward_reports import forward_report, health
from pm_alpha.recorder import Recorder, RecorderLock

T=utc("2026-10-01T12:00:00Z")

def meta():
    return {"platform":"kalshi","market_id":"M","event_id":"E","question":"Daily high temperature",
            "category":"weather","resolution_criteria":"Objective official final report", "resolution_source":[{"name":"NWS","url":"https://weather.gov"}],
            "expected_resolution_time":(T+timedelta(hours=12)).isoformat(),"close_time":(T+timedelta(hours=2)).isoformat(),
            "open_time":(T-timedelta(hours=12)).isoformat(),"available_time":T.isoformat(),"status":"active"}

def snap(when=None):
    return {"platform":"kalshi","market_id":"M","event_id":"E","capture_time":(when or T+timedelta(hours=1)).isoformat(),
            "yes_bid":0.45,"yes_ask":0.5,"midpoint":0.475,"spread":0.05,"volume":1000,"liquidity":None,
            "depth":{"yes_asks":[[0.5,20]],"yes_bids":[[0.45,10]],"no_asks":[[0.55,10]],"no_bids":[[0.5,20]]},"category":"weather"}


def test_rate_limiter_no_burst_and_host_budget():
    ticks=[0.0];sleeps=[]
    def sleep(n):sleeps.append(n);ticks[0]+=n
    r=RateLimiter(clock=lambda:ticks[0],sleep=sleep)
    r.acquire("weather",10);r.acquire("market");r.acquire("weather",10)
    assert sleeps==[1,9] and r.next_host["weather"]==20

def test_rate_limiter_hard_ceiling():
    with pytest.raises(ValueError):RateLimiter(0.5)

@pytest.mark.parametrize("book",[
    {},{"orderbook_fp":{"yes_dollars":[],"no_dollars":[[.5,2]]}},
    {"orderbook_fp":{"yes_dollars":[[1.1,2]],"no_dollars":[[.5,2]]}},
    {"orderbook_fp":{"yes_dollars":[[.5,0]],"no_dollars":[[.5,2]]}},
    {"orderbook_fp":{"yes_dollars":[[.5,float('nan')]],"no_dollars":[[.5,2]]}},
    {"orderbook_fp":{"yes_dollars":[[.7,2]],"no_dollars":[[.5,2]]}},
    {"orderbook_fp":{"yes_dollars":[[.4,2],[.4,3]],"no_dollars":[[.5,2]]}},
    {"orderbook_fp":{"yes_dollars":[[.4,2,0]],"no_dollars":[[.5,2]]}},
])
def test_malformed_books_rejected(book):
    with pytest.raises((DataInvalid,ValueError)):parse_forward_book("kalshi",book)

def test_kalshi_complement_and_multi_level_depth():
    b=parse_forward_book("kalshi",{"orderbook_fp":{"yes_dollars":[[.3,3],[.4,10]],"no_dollars":[[.4,5],[.5,20]]}})
    assert b["yes_ask"]==.5 and b["no_ask"]==.6 and b["no_bid"]==.5
    assert b["depth"]["yes_asks"]==[(.5,20),(.6,5)]

def test_polymarket_yes_no_books_are_independent():
    y={"bids":[{"price":".4","size":"10"}],"asks":[{"price":".5","size":"20"}]}
    n={"bids":[{"price":".45","size":"30"}],"asks":[{"price":".55","size":"40"}]}
    b=parse_forward_book("polymarket",y,n)
    assert b["no_ask"]==.55 and b["yes_ask"]==.5
    with pytest.raises(DataInvalid):parse_forward_book("polymarket",y)

@pytest.mark.parametrize("change,reason",[
    ({"category":"subjective/ambiguous"},"CATEGORY_EXCLUDED"),
    ({"status":"finalized"},"MARKET_NOT_OPEN"),
    ({"resolution_source":[]},"RESOLUTION_SOURCE_MISSING"),
    ({"expected_resolution_time":T.isoformat()},"INSUFFICIENT_TIME_REMAINING"),
    ({"expected_resolution_time":(T+timedelta(days=31)).isoformat()},"RESOLUTION_TOO_DISTANT"),
    ({"open_time":(T+timedelta(days=1)).isoformat()},"MARKET_NOT_YET_OPEN"),
])
def test_eligibility_metadata(change,reason):
    m=meta();m.update(change);assert reason in Eligibility().reasons(m,snap())

@pytest.mark.parametrize("change,reason",[
    ({"volume":None},"VOLUME_LOW_OR_UNKNOWN"),({"volume":1},"VOLUME_LOW_OR_UNKNOWN"),
    ({"spread":.5},"SPREAD_TOO_WIDE"),({"depth":{"yes_asks":[[.5,1]]}},"DEPTH_TOO_LOW")])
def test_eligibility_snapshot(change,reason):
    s=snap();s.update(change);assert reason in Eligibility().reasons(meta(),s)

def test_cohort_freeze_idempotent_and_immutable(tmp_path):
    s=Store(tmp_path/"forward.sqlite");a=freeze_cohort(s,tmp_path,T)
    b=freeze_cohort(s,tmp_path,T+timedelta(days=1));assert a==b and a["observation_anchor"]=="close_time"
    with pytest.raises(sqlite3.IntegrityError):s.db.execute("UPDATE audit SET payload='{}'")
    with pytest.raises(sqlite3.IntegrityError):s.db.execute("DELETE FROM audit")
    assert s.verify();s.close()

def test_cohort_first_capture_exclusion_cannot_be_replaced(tmp_path):
    st=Store(tmp_path/"db.sqlite");c=Cohort(st,freeze_cohort(st,tmp_path,T));m=meta();c.nominate([m],T)
    bad=snap();bad["spread"]=.5;key=save_snapshot(st,bad)
    e=c.observe(m,bad,key);assert not e["eligible"]
    good=snap(T+timedelta(hours=1,seconds=30));key=save_snapshot(st,good)
    assert c.observe(m,good,key) is None and not st.records("cohort_entry")
    assert len(st.records("cohort_exclusion"))==1;st.close()

def test_snapshot_uniqueness_and_event_one_representative(tmp_path):
    st=Store(tmp_path/"db.sqlite");c=Cohort(st,freeze_cohort(st,tmp_path,T));m=meta();other=meta();other["market_id"]="Z"
    c.nominate([other,m],T);s=snap();key=save_snapshot(st,s)
    with pytest.raises(DataInvalid):save_snapshot(st,s)
    assert c.observe(m,s,key)["stage"]=="TRAIN"
    assert c.observe(other,{**s,"market_id":"Z"},key) is None
    assert st.verify();st.close()

def test_nomination_cannot_backdate_old_metadata(tmp_path):
    st=Store(tmp_path/"db.sqlite");c=Cohort(st,freeze_cohort(st,tmp_path,T));c.nominate([meta()],T+timedelta(hours=1,seconds=1))
    assert not st.records("cohort_representative");st.close()

def test_missed_book_window_recorded(tmp_path):
    st=Store(tmp_path/"db.sqlite");c=Cohort(st,freeze_cohort(st,tmp_path,T));c.nominate([meta()],T)
    assert c.expire_missed(T+timedelta(hours=1,minutes=4))==1
    assert c.expire_missed(T+timedelta(hours=1,minutes=5))==0
    assert not st.records("cohort_entry");st.close()

def test_schedule_changed_no_retarget(tmp_path):
    st=Store(tmp_path/"db.sqlite");c=Cohort(st,freeze_cohort(st,tmp_path,T));m=meta();c.nominate([m],T)
    m["expected_resolution_time"]=(T+timedelta(days=1)).isoformat()
    e=c.observe(m,snap(),save_snapshot(st,snap()));assert "SCHEDULE_CHANGED" in e["reasons"];st.close()

def test_cohort_test_outcomes_masked(tmp_path):
    st=Store(tmp_path/"db.sqlite")
    st.append("cohort_entry","t",{"cohort_id":COHORT_ID,"platform":"kalshi","market_id":"M","stage":"TEST","capture_time":T.isoformat(),"market_probability":.1})
    st.append("forward_resolution","r",{"platform":"kalshi","market_id":"M","resolved_at":(T+timedelta(days=1)).isoformat(),"outcome":1})
    report=cohort_summary(st);assert report["market_baseline"] is None and report["resolved_train"]==0 and not report["test_opened"];st.close()

def test_daily_report_unknown_values_and_stopped_health(tmp_path):
    st=Store(tmp_path/"data/forward.sqlite");st.append("collector_heartbeat","h",{"timestamp":T.isoformat(),"pid":999999,"state":"STOPPED"})
    save_snapshot(st,snap());r=forward_report(st,tmp_path,"2026-10-01")
    assert r["snapshots_today"]==1 and r["median_liquidity"] is None and r["hypothetical_trades"]==0
    assert not r["health"]["process_alive"] and r["live_trading"] is False
    assert (tmp_path/"reports/forward/2026-10-01.md").exists();st.close()

def test_health_detects_future_clock(tmp_path):
    st=Store(tmp_path/"d.sqlite");save_snapshot(st,snap(T+timedelta(days=1)))
    h=health(st,tmp_path,T,False);assert h["stale_data"] and h["future_timestamps"]==1;st.close()

def test_single_process_lock(tmp_path):
    with RecorderLock(tmp_path/"lock"):
        with pytest.raises(RuntimeError):
            with RecorderLock(tmp_path/"lock"):pass
    assert not (tmp_path/"lock").exists()

class DummyReply:
    status=200
    headers={"Content-Type":"application/json","Date":"Thu, 01 Oct 2026 12:00:00 GMT"}
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def read(self):return b'{"ok":true}'

def test_raw_compressed_hash_and_dedup(tmp_path,monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",lambda *a,**k:DummyReply())
    st=Store(tmp_path/"d.sqlite");h=ForwardHTTP(tmp_path/"raw",st,limiter=RateLimiter(clock=lambda:100,sleep=lambda n:None))
    a=h.get("https://public.example","/data");b=h.get("https://public.example","/data")
    assert a.sha256==b.sha256 and len(list((tmp_path/"raw").glob("*")))==1
    assert gzip.decompress(next((tmp_path/"raw").glob("*")).read_bytes())==b'{"ok":true}'
    assert len(st.records("forward_retrieval"))==2 and st.verify();st.close()

def test_access_denial_stops_host(tmp_path,monkeypatch):
    calls=[]
    def deny(*a,**k):calls.append(a);raise HTTPError(a[0].full_url,403,"denied",{},None)
    monkeypatch.setattr("urllib.request.urlopen",deny)
    st=Store(tmp_path/"d.sqlite");h=ForwardHTTP(tmp_path/"raw",st)
    with pytest.raises(AccessBlocked):h.get("https://denied.example","/a")
    with pytest.raises(AccessBlocked):h.get("https://denied.example","/b")
    assert len(calls)==1;st.close()

def test_retry_429_recorded_and_budgeted(tmp_path,monkeypatch):
    calls=[];sleeps=[]
    def reply(*a,**k):
        calls.append(a)
        if len(calls)==1:raise HTTPError(a[0].full_url,429,"rate limit",{"Retry-After":"2"},None)
        return DummyReply()
    monkeypatch.setattr("urllib.request.urlopen",reply);monkeypatch.setattr("pm_alpha.data.forward_http.time.sleep",lambda n:sleeps.append(n))
    st=Store(tmp_path/"d.sqlite");h=ForwardHTTP(tmp_path/"raw",st,limiter=RateLimiter(clock=lambda:100,sleep=lambda n:None));h.get("https://public.example","/a")
    assert sleeps==[2] and st.records("forward_api_failure")[0]["status"]==429;st.close()

def test_recorder_offline_cycle_and_stop(tmp_path):
    (tmp_path/"config").mkdir();(tmp_path/"data/forward_raw").mkdir(parents=True)
    (tmp_path/"config/forward.toml").write_text('[collector]\npoll_seconds=30\ndiscovery_seconds=300\nresolution_seconds=300\ntimeout_seconds=1\nmax_markets=1\nlisting_limit=40\nmax_disk_mb=10\n[universe]\nkalshi_series=["S"]\npolymarket_enabled=false\n[weather]\nenabled=false\npoll_seconds=900\n')
    now=datetime.now(timezone.utc)
    raw={"ticker":"M","market_type":"binary","event_ticker":"E","rules_primary":"Maximum temperature at explicit station", "title":"Temperature", "open_time":(now-timedelta(hours=1)).isoformat(),"close_time":(now+timedelta(hours=4)).isoformat(),"expected_expiration_time":(now+timedelta(hours=6)).isoformat(),"status":"active","volume_fp":"1000","yes_bid_dollars":"0.4","yes_ask_dollars":"0.5"}
    series={"ticker":"S","category":"weather","fee_type":"quadratic","fee_multiplier":1,"settlement_sources":[{"name":"NWS","url":"https://weather.gov"}]}
    class FakeHTTP:
        def get(self,base,path,params=None):
            data={"series":series} if path=="/series/S" else {"markets":[raw]} if path=="/markets" else {"orderbook_fp":{"yes_dollars":[[.4,20]],"no_dollars":[[.5,20]]}}
            return Response(data,"a"*64,now,now,1,base+path,{})
    recorder=Recorder(tmp_path,http=FakeHTTP());r=recorder.run(cycles=1)
    assert r["state"]=="STOPPED" and len(recorder.store.records("market_snapshot"))==1
    assert recorder.store.records("market_snapshot")[0]["fee"]["rate"]==.07
    assert recorder.store.verify();recorder.store.close()
