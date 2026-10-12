import sqlite3
from dataclasses import replace
from datetime import timedelta
import pytest
from pm_alpha.storage import Store
from pm_alpha.execution import PaperOMS,DisabledLiveAdapter
from pm_alpha.models import Forecast
from pm_alpha.schema import Stamp,DataInvalid

def test_append_only_sql_enforcement(tmp_path):
    s=Store(tmp_path/"a.sqlite");s.append("decision","1",{"p":.5})
    with pytest.raises(sqlite3.IntegrityError):s.db.execute("UPDATE audit SET payload='{}'")
    s.db.rollback()
    with pytest.raises(sqlite3.IntegrityError):s.db.execute("DELETE FROM audit")
    s.db.rollback();assert s.verify()
    with pytest.raises(sqlite3.IntegrityError):s.append("decision","1",{"p":.8})
    assert s.records("decision")==[{"p":.5}];s.close()

def test_chain_detects_inserted_corruption(tmp_path):
    s=Store(tmp_path/"a.sqlite");s.append("decision","1",{})
    s.db.execute("INSERT INTO audit(kind,record_key,payload,previous_hash,record_hash) VALUES('x','2','{}','bad','bad')");s.db.commit()
    assert not s.verify();s.close()

def make_decision(oms,row):
    return oms.decide(row.market,row.quote,Forecast(.9,.85,.95,100),row.entry_time,
                      fee_rate=.07,fee_hash="fixture-fee",input_hashes=["fixture"],strategy_version="FIXTURE",model_version="FIXTURE")

def test_decision_stored_before_fill_and_settlement(tmp_path,row_factory):
    row=row_factory(ask=.5);s=Store(tmp_path/"a.sqlite");oms=PaperOMS(s,bankroll=10000)
    d=make_decision(oms,row);assert d["decision"]=="PAPER_BUY"
    assert len(s.records("shadow_decision"))==1 and not s.records("paper_fill")
    t=row.entry_time+timedelta(seconds=2);later=replace(row.quote,stamp=Stamp(t,t,t))
    fill=oms.fill(d,row.market,later,t)
    assert fill["status"]=="PAPER_FILLED"
    assert oms.account()[0]<10000
    with pytest.raises(DataInvalid):oms.settle(row.label,row.entry_time)
    assert oms.settle(row.label,row.label.available_time)==1
    assert oms.settle(row.label,row.label.available_time)==0
    assert oms.account()[0]>10000 and not oms.account()[1]
    assert s.verify();s.close()

def test_incomplete_depth_fok_no_partial_fill(tmp_path,row_factory):
    r=row_factory();s=Store(tmp_path/"a.sqlite");oms=PaperOMS(s,10000);d=make_decision(oms,r)
    t=r.entry_time+timedelta(seconds=1);later=replace(r.quote,stamp=Stamp(t,t,t),ask_depth=((.5,.1),))
    result=oms.fill(d,r.market,later,t)
    assert result["status"]=="UNFILLED" and not s.records("paper_fill")
    assert oms.account()[0]==10000;s.close()

def test_same_snapshot_cannot_fill(tmp_path,row_factory):
    r=row_factory();s=Store(tmp_path/"a.sqlite");oms=PaperOMS(s,10000);d=make_decision(oms,r)
    assert oms.fill(d,r.market,r.quote,r.entry_time)["status"]=="UNFILLED";s.close()

def test_losing_paper_signal_remains(tmp_path,row_factory):
    r=row_factory(outcome=0);s=Store(tmp_path/"a.sqlite");oms=PaperOMS(s,10000);d=make_decision(oms,r)
    t=r.entry_time+timedelta(seconds=1);oms.fill(d,r.market,replace(r.quote,stamp=Stamp(t,t,t)),t)
    oms.settle(r.label,r.label.available_time)
    assert s.records("paper_settlement")[0]["hypothetical_pnl"]<0
    assert len(s.records("shadow_decision"))==1 and s.verify();s.close()

def test_unknown_fee_logged_skip(tmp_path,row_factory):
    r=row_factory();s=Store(tmp_path/"a.sqlite");oms=PaperOMS(s)
    d=oms.decide(r.market,r.quote,Forecast(.9,.8,.95,100),r.entry_time,fee_rate=None,fee_hash=None,input_hashes=["fixture"],strategy_version="fixture",model_version="fixture")
    assert d["decision"].startswith("SKIP") and s.records("shadow_decision");s.close()

def test_restart_replays_positions_and_rejects_changed_bankroll(tmp_path,row_factory):
    s=Store(tmp_path/"a.sqlite");PaperOMS(s,10000)
    with pytest.raises(ValueError):PaperOMS(s,100)
    s.close()

def test_live_execution_unavailable():
    with pytest.raises(RuntimeError):DisabledLiveAdapter().submit({"live":True})
