"""Bounded, restartable prospective market/weather recorder. Never submits orders."""
import json
import os
import shutil
import time
import tomllib
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from .storage import Store, digest, canonical
from .schema import DataInvalid, utc
from .data.forward_http import ForwardHTTP
from .data.http import AccessBlocked
from .data.kalshi import BASE, parse_label
from .data.polymarket import GAMMA, CLOB, DATA
from .forward_schema import kalshi_metadata, polymarket_metadata, parse_forward_book, number, Eligibility
from .cohort import Cohort, freeze_cohort, save_snapshot
from .weather import NWS, detect_weather, parse_weather_contract


def now_utc():return datetime.now(timezone.utc)


class RecorderLock:
    def __init__(self,path):self.path=path
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        try:
            self.file=self.path.open("x")
        except FileExistsError as e:
            raise RuntimeError("Recorder lock exists. Check health/process before manually removing a stale lock.") from e
        self.file.write(str(os.getpid()));self.file.flush()
        return self
    def __exit__(self,*args):self.file.close();self.path.unlink(missing_ok=True)


class Recorder:
    def __init__(self,root,http=None,store=None):
        self.root=Path(root);self.config=tomllib.loads((self.root/"config/forward.toml").read_text())
        cfg=self.config["collector"]
        if cfg["poll_seconds"]<30 or cfg["max_markets"]>12 or cfg["max_markets"]<1:
            raise ValueError("Recorder v0.2 cap: 12 markets, minimum 30-second cycles")
        self.store=store or Store(self.root/"data/forward.sqlite")
        self.http=http or ForwardHTTP(self.root/"data/forward_raw",self.store,timeout=cfg["timeout_seconds"])
        self.spec=freeze_cohort(self.store,self.root);self.cohort=Cohort(self.store,self.spec)
        self.tracked={};self.last_discovery=0;self.last_weather=0;self.last_resolution=0
        self.versions={};self.series={};self.stopped=False
        for r in self.store.iter_records("forward_metadata"):
            self.versions[(r["platform"],r["market_id"])]=r
        self.nws=NWS(self.http,self.store)
        import gzip,hashlib,subprocess
        sources={str(p.relative_to(self.root)):p.read_text(encoding='utf-8') for p in sorted((self.root/'src/pm_alpha').rglob('*.py'))}
        source_files={k:hashlib.sha256(v.encode()).hexdigest() for k,v in sources.items()}
        source_hash=digest(source_files)
        code_dir=self.root/'data/code';code_dir.mkdir(parents=True,exist_ok=True)
        code_file=code_dir/f'{source_hash}.json.gz'
        if not code_file.exists():
            with code_file.open('xb') as f:f.write(gzip.compress(canonical(sources).encode(),mtime=0))
        try:commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=self.root,text=True,stderr=subprocess.DEVNULL).strip()
        except (OSError,subprocess.CalledProcessError):commit=None
        self.manifest_key=f"recorder-manifest:{time.time_ns()}"
        self.store.append("recorder_manifest",self.manifest_key,
                          {"started_at":now_utc().isoformat(),"collector_version":"v0.3.1","config_hash":digest(self.config),
                           "source_hash":source_hash,"source_files":source_files,"source_archive":str(code_file.relative_to(self.root)),"git_commit":commit,
                           "cohort_definition_hash":self.spec["definition_hash"],"live_trading":False})

    def issue(self,kind,reason,market_id=None):
        self.store.append(kind,f"{kind}:{time.time_ns()}",{"timestamp":now_utc().isoformat(),"market_id":market_id,"reason":str(reason)})

    def persist_meta(self,m):
        identity={k:v for k,v in m.items() if k not in ("available_time","source_hash")}
        key="metadata:"+digest(identity)
        old=self.store.get(key)
        if old:m=old
        else:self.store.append("forward_metadata",key,m)
        self.versions[(m["platform"],m["market_id"])]=m
        if detect_weather(m):
            wkey="weather-contract:"+digest(identity)
            if not self.store.has(wkey):
                parsed=parse_weather_contract(m)|{"platform":m["platform"],"detected_at":now_utc().isoformat()}
                self.store.append("weather_contract",wkey,parsed)
        return m,key

    def discovery(self):
        candidates=[];cfg=self.config["collector"]
        for sid in self.config["universe"]["kalshi_series"]:
            try:
                sr=self.http.get(BASE,f"/series/{sid}");series=sr.data.get("series")
                if not isinstance(series,dict) or series.get("ticker")!=sid:raise DataInvalid("Unexpected series schema")
                self.series[sid]=(series,sr)
                mr=self.http.get(BASE,"/markets",{"series_ticker":sid,"status":"open","limit":cfg["listing_limit"],"mve_filter":"exclude"})
                rows=mr.data.get("markets")
                if not isinstance(rows,list):raise DataInvalid("Unexpected market listing schema")
                if mr.data.get("cursor"):self.issue("forward_coverage_gap",f"Series {sid}: page cap reached; bounded sample, not full universe")
                for raw in rows:
                    try:
                        m=kalshi_metadata(raw,series,max(sr.received_at,mr.received_at),mr.sha256)
                        volume=number(raw,"volume_fp")
                        bid=number(raw,"yes_bid_dollars");ask=number(raw,"yes_ask_dollars")
                        # Discovery filter is fixed and outcome-free. Record exclusions for observability.
                        if volume is None or volume<100 or bid is None or ask is None or bid<=0 or ask>=1 or bid>ask or ask-bid>0.10:
                            self.issue("forward_discovery_exclusion","LISTING_VOLUME_OR_SPREAD",raw.get("ticker"));continue
                        if utc(m["close_time"])<=now_utc():continue
                        m,key=self.persist_meta(m)
                        candidates.append((m,raw,mr,key,sr))
                    except (DataInvalid,KeyError,ValueError) as e:self.issue("forward_integrity",e,raw.get("ticker"))
            except Exception as e:self.issue("forward_source_failure",f"kalshi:{sid}:{type(e).__name__}:{e}")
            self.heartbeat("DISCOVERING")
        if self.config["universe"]["polymarket_enabled"]:
            try:
                r=self.http.get(GAMMA,"/markets/keyset",{"closed":"false","active":"true","limit":cfg["listing_limit"],
                                                      "end_date_min":now_utc().isoformat()})
                rows=r.data.get("markets")
                if not isinstance(rows,list):raise DataInvalid("Unexpected Gamma keyset schema")
                if r.data.get("next_cursor"):self.issue("forward_coverage_gap","Gamma page cap reached; bounded sample, not full universe")
                for raw in rows:
                    try:
                        m=polymarket_metadata(raw,r.received_at,r.sha256)
                        volume=number(raw,"volumeNum");bid=number(raw,"bestBid");ask=number(raw,"bestAsk")
                        if volume is None or volume<100 or bid is None or ask is None or bid<=0 or ask>=1 or bid>ask or ask-bid>0.1 or m["status"]!="open":
                            self.issue("forward_discovery_exclusion","LISTING_VOLUME_OR_SPREAD_OR_STATUS",raw.get("id"));continue
                        if (utc(m["expected_resolution_time"])-now_utc()).total_seconds()>30*86400:continue
                        m,key=self.persist_meta(m);candidates.append((m,raw,r,key,None))
                    except (DataInvalid,KeyError,ValueError) as e:self.issue("forward_integrity",e,raw.get("id"))
            except Exception as e:self.issue("forward_source_failure",f"polymarket:{type(e).__name__}:{e}")
        # Nominate before selecting a book; preserve the nomination if future metadata changes.
        self.cohort.nominate([x[0] for x in candidates])
        # Round-robin series/event prevents a single weather bracket swallowing the cap.
        groups={}
        for c in sorted(candidates,key=lambda x:(x[0]["platform"],x[0]["market_id"])):
            groups.setdefault((c[0]["platform"],c[0]["event_id"]),[]).append(c)
        selected=[]
        while groups and len(selected)<cfg["max_markets"]:
            for g in list(groups):
                selected.append(groups[g].pop(0))
                if not groups[g]:del groups[g]
                if len(selected)>=cfg["max_markets"]:break
        self.tracked={(m["platform"],m["market_id"]):(m,raw,r,key,sr) for m,raw,r,key,sr in selected}
        self.last_discovery=time.monotonic()
        self.store.append("forward_universe",f"universe:{time.time_ns()}",{"timestamp":now_utc().isoformat(),
                          "tracked":[{"platform":p,"market_id":i} for p,i in self.tracked],"candidates":len(candidates),
                          "sampling":"Fixed series + bounded Gamma first page; lexical event round-robin, no outcome information",
                          "config_hash":digest(self.config)})

    def capture_market(self,c):
        m,raw,mr,mkey,sr=c
        if utc(m["close_time"])<=now_utc():return None
        responses=[mr];source_times=[]
        if m["platform"]=="kalshi":
            r=self.http.get(BASE,f"/markets/{m['market_id']}/orderbook",{"depth":100})
            book=parse_forward_book("kalshi",r.data);responses.append(r)
            series=sr.data["series"];fee_type=series.get("fee_type");multiplier=series.get("fee_multiplier")
            fee={"type":fee_type,"multiplier":multiplier,"rate":None,"exact":False,"status":"UNKNOWN",
                 "source_hash":sr.sha256,"available_time":sr.received_at.isoformat()}
            if fee_type in ("quadratic","quadratic_with_maker_fees") and multiplier is not None and 0<=float(multiplier)*0.07<=1:
                fee.update({"rate":float(multiplier)*0.07,"status":"CURRENT_PARAMETERS_CONSERVATIVE_BOUND",
                            "rounding":"ceil to whole cent; current combined centicent charging not replicated"})
            volume=number(raw,"volume_fp");liquidity=None;last=number(raw,"last_price_dollars")
            quoted_bid=number(raw,"yes_bid_dollars");quoted_ask=number(raw,"yes_ask_dollars")
            quoted=(quoted_bid+quoted_ask)/2 if quoted_bid is not None and quoted_ask is not None else None
            source_time_kind="RECEIPT_ONLY_NO_VENUE_EVENT_TIME"
        else:
            yr=self.http.get(CLOB,"/book",{"token_id":m["yes_token"]})
            nr=self.http.get(CLOB,"/book",{"token_id":m["no_token"]})
            for response,token in ((yr,m["yes_token"]),(nr,m["no_token"])):
                if str(response.data.get("asset_id"))!=token:raise DataInvalid("Book token mapping mismatch")
                if not response.data.get("timestamp"):raise DataInvalid("Polymarket book missing source timestamp")
                event=utc(float(response.data["timestamp"])/1000)
                if event>response.received_at or (response.received_at-event).total_seconds()>90:raise DataInvalid("Future/stale Polymarket book timestamp")
                source_times.append(event.isoformat())
            book=parse_forward_book("polymarket",yr.data,nr.data);responses.extend((yr,nr))
            fr=self.http.get(CLOB,f"/clob-markets/{m['condition_id']}");responses.append(fr)
            fd=fr.data.get("fd") or {}
            fee={"rate":None,"exact":False,"status":"UNKNOWN","raw_parameters":fd,"source_hash":fr.sha256,
                 "available_time":fr.received_at.isoformat()}
            if fd.get("r") is not None and fd.get("e",1)==1 and 0<=float(fd["r"])<=1:
                fee.update({"rate":float(fd["r"]),"status":"CURRENT_PARAMETERS_CAPTURED","exact":True,"rounding":"5 decimals"})
            volume=number(raw,"volumeNum");liquidity=number(raw,"liquidityNum");last=number(raw,"lastTradePrice")
            quoted=None
            source_time_kind="VENUE_MS_TIMESTAMP_PLUS_RECEIPT"
        if sr:responses.append(sr)
        capture=max(x.received_at for x in responses)
        if capture>=utc(m["close_time"]):raise DataInvalid("Capture completed after close; not a pre-outcome book")
        snapshot={"platform":m["platform"],"market_id":m["market_id"],"event_id":m["event_id"],"metadata_key":mkey,
                  "collector_manifest_key":self.manifest_key,
                  "capture_time":capture.isoformat(),"metadata_available_time":m["available_time"],"category":m["category"],
                  "expected_resolution_time":m["expected_resolution_time"],"close_time":m["close_time"],
                  "status":m["status"],"last_trade":last,"quoted_probability":quoted,"volume":volume,"liquidity":liquidity,
                  "fee":fee,"source_endpoints":[x.endpoint for x in responses],"raw_response_hashes":[x.sha256 for x in responses],
                  "input_provenance":[x.provenance() for x in responses],"source_event_times":source_times,
                  "source_time_kind":source_time_kind,"minimum_shares":m["minimum_shares"],"share_step":m["share_step"],
                  "minimum_shares_basis":m['minimum_shares_basis'],"venue_minimum_shares":m['venue_minimum_shares'],
                  "volume_unit":"contracts" if m['platform']=='kalshi' else "USD_reported",
                  "cost_exact":fee["exact"],"fill_capacity_is_guaranteed":False,"slippage_assumption":None,
                  "hypothetical_fill":None,"live_trading":False,**book}
        snapshot["depth"]={k:v[:5] for k,v in book["depth"].items()}
        snapshot["depth_levels_retained"]=5
        snapshot["full_book_in_raw"]=True
        if m['platform']=='polymarket':
            limits=[number(x.data,'min_order_size') for x in (yr,nr)]
            if all(v is not None and v>0 for v in limits):
                snapshot['venue_minimum_shares']=max(limits)
                snapshot['minimum_shares']=max(m['minimum_shares'],max(limits))
                snapshot['minimum_shares_basis']='CLOB_PAIRED_BOOKS_WITH_CONSERVATIVE_LOCAL_FLOOR'
        book_received=[x.received_at for x in responses if "/book" in x.endpoint or "/orderbook" in x.endpoint]
        snapshot["book_receipt_skew_ms"]=(max(book_received)-min(book_received)).total_seconds()*1000
        snapshot["eligibility_reasons"]=Eligibility().reasons(m,snapshot)
        snapshot["forecast_validity"]="FORWARD_RECEIPT_VALID"
        snapshot["execution_validity"]="VISIBLE_DEPTH_ONLY_COST_BOUND" if fee["rate"] is not None else "UNKNOWN_FEE"
        key=save_snapshot(self.store,snapshot);self.cohort.observe(m,snapshot,key)
        return snapshot

    def reconcile(self):
        done={(r["platform"],r["market_id"]) for r in self.store.iter_records("forward_resolution")}
        pending=[m for k,m in self.versions.items() if k not in done and utc(m["close_time"])<=now_utc()]
        # Oldest pending first. No status inferred from elapsed time/displayed prices.
        for m in sorted(pending,key=lambda m:m["close_time"])[:24]:
            try:
                if m["platform"]=="kalshi":
                    r=self.http.get(BASE,f"/markets/{m['market_id']}");raw=r.data.get("market") or {}
                    if raw.get("status") not in ("finalized","settled"):continue
                    label=parse_label(raw,r.sha256)
                    if label.market_id!=m["market_id"]:raise DataInvalid("Settlement ID mismatch")
                    outcome,resolved=label.outcome,label.available_time
                else:
                    r=self.http.get(DATA,"/v2/resolutions",{"condition":m["condition_id"]});rows=r.data.get("data") or []
                    if not rows:continue
                    if len(rows)!=1:raise DataInvalid("Ambiguous final resolution")
                    raw=rows[0]
                    if raw.get("status")!="resolved":continue
                    if sorted(raw.get("payouts") or [])!=[0,1000000] or not raw.get("resolved_at"):raise DataInvalid("Nonbinary/unverified resolution")
                    outcome=int(raw["payouts"][m["yes_index"]]/1000000);resolved=utc(raw["resolved_at"])
                if resolved>r.received_at:raise DataInvalid("Resolution has future timestamp")
                self.store.append("forward_resolution",f"resolution:{m['platform']}:{m['market_id']}",
                                  {"platform":m["platform"],"market_id":m["market_id"],"event_id":m["event_id"],
                                   "outcome":outcome,"resolved_at":resolved.isoformat(),"first_observed_at":r.received_at.isoformat(),
                                   "raw_response_hash":r.sha256,"endpoint":r.endpoint})
            except Exception as e:self.issue("forward_resolution_failure",f"{type(e).__name__}:{e}",m["market_id"])
        self.last_resolution=time.monotonic();self.cohort.freeze_training_model(now_utc())

    def disk_guard(self):
        total=sum(p.stat().st_size for p in (self.root/"data/forward_raw").glob("*"))
        db=self.root/"data/forward.sqlite"
        total+=sum(p.stat().st_size for p in db.parent.glob(db.name+"*"))
        if total>self.config["collector"]["max_disk_mb"]*1024**2 or shutil.disk_usage(self.root).free<512*1024**2:
            raise RuntimeError("DISK_BUDGET_EXCEEDED: collection paused; no raw/snapshot deletion")
        return total

    def heartbeat(self,state,**extra):
        record={"timestamp":now_utc().isoformat(),"pid":os.getpid(),"state":state,"tracked":len(self.tracked),
                "poll_seconds":self.config["collector"]["poll_seconds"],"live_trading":False,**extra}
        self.store.append("collector_heartbeat",f"heartbeat:{time.time_ns()}",record)
        path=self.root/"data/collector_health.json";tmp=path.with_suffix(".tmp")
        tmp.write_text(canonical(record)+"\n");tmp.replace(path)

    def cycle(self):
        self.disk_guard();self.heartbeat("COLLECTING")
        if not self.last_discovery or time.monotonic()-self.last_discovery>=self.config["collector"]["discovery_seconds"]:self.discovery()
        count=0
        for c in list(self.tracked.values()):
            try:
                if self.capture_market(c):count+=1
            except Exception as e:self.issue("forward_integrity" if isinstance(e,DataInvalid) else "forward_source_failure",f"{type(e).__name__}:{e}",c[0]["market_id"])
            self.heartbeat("COLLECTING",snapshots_this_cycle=count)
        if not self.last_resolution or time.monotonic()-self.last_resolution>=self.config["collector"]["resolution_seconds"]:self.reconcile()
        if self.config["weather"]["enabled"] and (not self.last_weather or time.monotonic()-self.last_weather>=self.config["weather"]["poll_seconds"]):
            for loc in self.config["weather"]["locations"]:
                try:self.nws.capture(loc)
                except Exception as e:self.issue("weather_source_failure",f"{loc['name']}:{type(e).__name__}:{e}")
            self.last_weather=time.monotonic()
        self.cohort.expire_missed(now_utc())
        self.heartbeat("RUNNING" if count else "DEGRADED_NO_SNAPSHOTS",snapshots_this_cycle=count,disk_bytes=self.disk_guard())
        return {"captured":count,"tracked":len(self.tracked),"audit_valid":self.store.verify(),"live_trading":False}

    def run(self,cycles=None,seconds=None,*,_lock_held=False):
        cfg=self.config["collector"];start=time.monotonic();n=0
        with nullcontext() if _lock_held else RecorderLock(self.root/"data/recorder.lock"):
            try:
                while (cycles is None or n<cycles) and (seconds is None or time.monotonic()-start<seconds):
                    if (self.root/"data/STOP_COLLECTOR").exists():break
                    tick=time.monotonic();result=self.cycle();n+=1
                    elapsed=time.monotonic()-tick
                    if elapsed>cfg['poll_seconds']*1.5:self.issue('forward_cadence_warning',f'Cycle required {elapsed:.2f}s versus {cfg["poll_seconds"]}s target; no catch-up burst')
                    print(canonical({"cycle":n,"timestamp":now_utc().isoformat(),**result}),flush=True)
                    from .forward_reports import forward_report
                    forward_report(self.store,self.root,now_utc().date().isoformat())
                    if cycles is not None and n>=cycles:break
                    # Short sleeps make Ctrl-C/stop-file responsive. Cadence is start-to-start, no catch-up bursts.
                    deadline=max(time.monotonic(),tick+cfg["poll_seconds"])
                    while time.monotonic()<deadline:
                        if (self.root/"data/STOP_COLLECTOR").exists():self.stopped=True;break
                        if seconds is not None and time.monotonic()-start>=seconds:self.stopped=True;break
                        time.sleep(min(1,deadline-time.monotonic()))
                    if self.stopped:break
            except KeyboardInterrupt:
                self.heartbeat('STOPPED',cycles=n,reason='INTERRUPTED_BY_USER')
            except BaseException as e:
                self.heartbeat("FAILED",reason=f"{type(e).__name__}:{e}");raise
            finally:
                if (self.store.last("collector_heartbeat") or {}).get("state")!="FAILED":self.heartbeat("STOPPED",cycles=n)
        return {"cycles":n,"live_trading":False,"state":"STOPPED"}
