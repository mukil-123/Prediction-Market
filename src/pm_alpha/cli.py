"""PowerShell-friendly commands; baseline uses only the Python standard library."""
import argparse
import json
import logging
import tomllib
from pathlib import Path
from datetime import datetime,timezone,timedelta
from .storage import Store,canonical,digest
from .schema import DataInvalid,ResearchRow,utc,stamp_dict,Quote,Stamp
from .dataset import write_dataset,encode,read_dataset
from .data.http import PublicHTTP,AccessBlocked
from .data.kalshi import Kalshi,parse_market as kalshi_market,parse_label,parse_candle,BASE
from .data.polymarket import Polymarket,parse_market as poly_market,array,parse_resolution
from .research import experiment,freeze,eligible,representatives,risk_config
from .models import BinCalibration
from .execution import PaperOMS
from .monitoring import daily_report


def download(root:Path,platform:str,limit:int,pages:int,base:str,since:str|None=None)->dict:
    settings=tomllib.loads((root/"config/markets.toml").read_text())
    store=Store(root/"data/local.sqlite");http=PublicHTTP(root/"data/raw",store,settings["timeout_seconds"],settings["requests_per_second"])
    rows=[];issues=[];total=0
    try:
        if platform=="kalshi":
            if base not in (BASE,"https://api.elections.kalshi.com/trade-api/v2"):raise ValueError("Only documented official Kalshi API hosts supported")
            api=Kalshi(http,base);raw_markets=api.markets(limit=limit,pages=pages);total=len(raw_markets)
            # Snapshot is fixed ten minutes after open, at latest preceding 1-minute candle.
            # The downloaded listing is a recent feasibility sample, not an unbiased cohort.
            event_cache={}
            for raw,sha,t in raw_markets:
                store.append("market_metadata",f"market:{raw['ticker']}:{t.isoformat()}",{"raw":raw,"source_hash":sha,"available_time":t.isoformat()})
            groups={}
            for raw,sha,t in sorted(raw_markets,key=lambda x:x[0]["ticker"]):groups.setdefault(raw["event_ticker"],(raw,sha,t))
            for raw,sha,t in groups.values():
                try:
                    market=kalshi_market(raw,t);label=parse_label(raw,sha)
                    target=utc(raw["open_time"])+timedelta(minutes=10)
                    if label.available_time<=target:raise DataInvalid("Resolved before fixed snapshot")
                    if raw["event_ticker"] not in event_cache:event_cache[raw["event_ticker"]]=api.event(raw["event_ticker"])[0]
                    series=event_cache[raw["event_ticker"]].get("series_ticker")
                    if not series:raise DataInvalid("Event omitted series ticker")
                    result,candle_sha,ingested=api.candles(series,market.market_id,int(target.timestamp())-600,int(target.timestamp()))
                    candidates=[c for c in result.get("candlesticks",[]) if c.get("end_period_ts",float('inf'))<=target.timestamp()]
                    quote=None
                    for c in sorted(candidates,key=lambda c:c["end_period_ts"],reverse=True):
                        try:quote=parse_candle(c,market.market_id,ingested);break
                        except DataInvalid:continue
                    if quote is None:raise DataInvalid("No usable candle at fixed snapshot")
                    if (target-quote.stamp.event_time).total_seconds()>120:raise DataInvalid("Snapshot older than two minutes")
                    row=ResearchRow(market,quote,label,target)
                    rows.append(row);store.append("normalized_row",f"row:{market.market_id}:{ingested.isoformat()}",encode(row))
                    print(canonical({"event":"downloaded","market_id":market.market_id,"rows":len(rows)}),flush=True)
                except AccessBlocked as e:issues.append({"market_id":raw.get("ticker"),"reason":str(e)});break
                except (DataInvalid,KeyError,ValueError) as e:issues.append({"market_id":raw.get("ticker"),"reason":str(e)})
                except Exception as e:issues.append({"market_id":raw.get("ticker"),"reason":f"REQUEST_FAILED:{type(e).__name__}:{e}"})
        else:
            api=Polymarket(http);raw_markets=api.markets(True,limit,pages,since);total=len(raw_markets)
            for raw,sha,t in raw_markets:
                try:
                    market=poly_market(raw,t);state,state_sha,_=api.resolution(raw["conditionId"])
                    idx=[str(x).lower() for x in array(raw["outcomes"])].index("yes")
                    label=parse_resolution(state,market,idx,state_sha)
                    history=api.history(market.yes_token)
                    # Historical rules/publication remain unknown; this is a diagnostic only.
                    store.append("polymarket_history",f"history:{market.market_id}:{t.isoformat()}",{"market_id":market.market_id,"points":[x for x,_,_ in history],"source_hashes":sorted({h for _,h,_ in history}),"label":vars(label)|{"available_time":label.available_time.isoformat()},"limitation":"Settlement points (resolution_seconds=0) never serve as predictive inputs; publication time unverified."})
                    if not raw.get("startDate"):raise DataInvalid("Missing startDate; no creation-date proxy substituted")
                    target=utc(raw["startDate"])+timedelta(hours=24)
                    if label.available_time<=target:raise DataInvalid("Resolved before fixed 24-hour diagnostic snapshot")
                    points=[(x,h,it) for x,h,it in history if x.get("resolution_seconds",0)>0 and utc(x["timestamp"])<=target]
                    if not points:raise DataInvalid("No non-settlement price history at fixed snapshot")
                    x,h,it=max(points,key=lambda z:z[0]["timestamp"])
                    if (target-utc(x["timestamp"])).total_seconds()>10800:raise DataInvalid("History snapshot older than three hours")
                    quote=Quote(market.market_id,Stamp(utc(x["timestamp"]),None,it,"UNVERIFIED_AVAILABILITY"),float(x["price"]))
                    row=ResearchRow(market,quote,label,target)
                    rows.append(row);store.append("normalized_row",f"row:{market.market_id}:{it.isoformat()}",encode(row))
                    print(canonical({"event":"downloaded","source":"polymarket","market_id":market.market_id,"rows":len(rows)}),flush=True)
                except AccessBlocked as e:issues.append({"reason":str(e)});break
                except (DataInvalid,KeyError,ValueError) as e:issues.append({"market_id":raw.get("id"),"reason":str(e)})
    except Exception as e:issues.append({"reason":f"{type(e).__name__}:{e}"})
    metadata={"source":platform,"dataset_version":"validation-sample-v0.1","raw_markets_downloaded":total,
              "snapshot_rule":"10 minutes after opening; latest preceding minute close within 2 minutes" if platform=="kalshi" else "24 hours after startDate; preceding nonzero-resolution observation within 3 hours",
              "since":since,"retrieved_at":datetime.now(timezone.utc).isoformat(),"issues":issues,"historical_availability":"UNVERIFIED",
              "sampling":"Public listing; binary final settlements; convenience feasibility sample; no representativeness claim"}
    path=root/f"data/processed/{platform}_validation.json";write_dataset(path,rows,metadata)
    store.close();return {"dataset":str(path),"raw_markets":total,"normalized_snapshots":len(rows),"issues":len(issues),"status":"DATA_INVALID" if not rows or any(r.quote.stamp.available_time is None for r in rows) else "DATA_CHECK"}


def shadow(root:Path,limit:int,dataset:Path,series:str|None=None)->dict:
    settings=tomllib.loads((root/"config/markets.toml").read_text())
    store=Store(root/"data/local.sqlite");http=PublicHTTP(root/"data/raw",store,settings["timeout_seconds"],settings["requests_per_second"]);api=Kalshi(http)
    rows,_=read_dataset(dataset);valid,_=eligible(representatives(rows))
    model=BinCalibration().fit([(r.quote.market_probability,r.label.outcome) for r in valid if r.label.available_time<datetime.now(timezone.utc)])
    policy,initial=risk_config(root);oms=PaperOMS(store,initial,policy);count=0
    for raw,sha,t in api.markets("open",limit,series=series):
        try:
            market=kalshi_market(raw,t);quote,qsha=api.book(market.market_id)
            now=datetime.now(timezone.utc)
            snapshot={"source":market.source,"market_id":market.market_id,"event_cluster":market.cluster_id,
                      "question":market.question,"rules":market.rules,"scheduled_close":market.scheduled_close.isoformat(),
                      "metadata_stamp":stamp_dict(market.stamp),"quote_stamp":stamp_dict(quote.stamp),
                      "bid":quote.bid,"ask":quote.ask,"market_probability":quote.market_probability,
                      "ask_depth":quote.ask_depth,"minimum_shares":quote.minimum_shares,"share_step":quote.share_step,
                      "input_data_hashes":[sha,qsha],"historical_fee_status":"UNKNOWN"}
            store.append("forward_snapshot",f"snapshot:{digest(snapshot)}",snapshot)
            # No fee schedule or validated model is fabricated to force a trade.
            d=oms.decide(market,quote,model.predict(quote.market_probability),now,fee_rate=None,fee_hash=None,input_hashes=[sha,qsha,digest(model.payload())],strategy_version="PM-C1-v0.1",model_version="beta-bin-market-prior-v0.1")
            count+=1
            if d["decision"]=="PAPER_BUY":
                later,_=api.book(market.market_id);oms.fill(d,market,later,datetime.now(timezone.utc))
        except DataInvalid as e:store.append("shadow_data_rejection",f"reject:{raw.get('ticker')}:{t.isoformat()}",{"market_id":raw.get("ticker"),"reason":str(e),"timestamp":datetime.now(timezone.utc).isoformat()})
    date=datetime.now(timezone.utc).date().isoformat();daily_report(store,root/f"reports/SHADOW_{date}.md",date)
    ok=store.verify();store.close();return {"decisions":count,"audit_valid":ok,"live_trading":False}


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--root",type=Path,default=Path.cwd())
    sub=parser.add_subparsers(dest="command",required=True)
    d=sub.add_parser("download");d.add_argument("--platform",choices=["polymarket","kalshi"],default="polymarket");d.add_argument("--limit",type=int,default=100);d.add_argument("--pages",type=int,default=1);d.add_argument("--base",default=BASE);d.add_argument("--since",help="Polymarket start_date_min, ISO-8601 UTC; explicit cohort restriction")
    r=sub.add_parser("research");r.add_argument("--dataset",type=Path,default=Path("data/processed/kalshi_validation.json"));r.add_argument("--config",type=Path,default=Path("config/research.toml"));r.add_argument("--report",type=Path,default=Path("reports/PM_C1_v001.md"));r.add_argument("--freeze",type=Path)
    f=sub.add_parser("freeze");f.add_argument("--dataset",type=Path,required=True);f.add_argument("--config",type=Path,default=Path("config/research.toml"));f.add_argument("--output",type=Path,required=True)
    s=sub.add_parser("shadow-once");s.add_argument("--limit",type=int,default=10);s.add_argument("--dataset",type=Path,default=Path("data/processed/kalshi_validation.json"));s.add_argument("--series",help="Explicit Kalshi series filter for book feasibility, not evidence of strategy selection")
    sub.add_parser("audit");p=sub.add_parser("daily-report");p.add_argument("--date",default=datetime.now(timezone.utc).date().isoformat())
    collect=sub.add_parser("collect-forward");collect.add_argument("--cycles",type=int);collect.add_argument("--seconds",type=int)
    sub.add_parser("freeze-forward");sub.add_parser("collector-health")
    fr=sub.add_parser("forward-report");fr.add_argument("--date",default=datetime.now(timezone.utc).date().isoformat())
    micro=sub.add_parser("micro-feasibility");micro.add_argument("--samples",type=int,default=3)
    sub.add_parser("verify-forward")
    desktop=sub.add_parser("desktop");desktop.add_argument("--port",type=int,default=8765);desktop.add_argument("--collect",action="store_true",help="Start the existing collector as this local app's child");desktop.add_argument("--open-browser",action="store_true",help="Open the loopback research console locally")
    loop=sub.add_parser('research-loop');loop.add_argument('--once',action='store_true',help='Offline audited cycle; do not start network collection');loop.add_argument('--no-collect',action='store_true');loop.add_argument('--port',type=int,default=8765);loop.add_argument('--open-browser',action='store_true')
    sub.add_parser('research-status');sub.add_parser('replay-shadow')
    demo=sub.add_parser('technical-demo');demo.add_argument('--output',type=Path,required=True,help='New isolated fixture directory; never the real dataset')
    cap=sub.add_parser('capital');actions=cap.add_subparsers(dest='capital_action',required=True)
    plan=actions.add_parser('plan');plan.add_argument('--amount',required=True);plan.add_argument('--unit',required=True);plan.add_argument('--start-date',required=True)
    confirm=actions.add_parser('confirm');confirm.add_argument('--period',required=True);confirm.add_argument('--reference',required=True)
    event=actions.add_parser('event');event.add_argument('--kind',choices=['withdrawal','other_income'],required=True);event.add_argument('--amount',required=True);event.add_argument('--reference',required=True)
    actions.add_parser('status')
    args=parser.parse_args();root=args.root.resolve()
    def resolve(p):return p if p.is_absolute() else root/p
    if args.command=='research-loop':
        if args.once:
            from .automation import ResearchLoop
            r=ResearchLoop(root).tick()
            print(canonical({k:r[k] for k in ('verdict','account','cohort','probability_support','audit_valid','live_trading','real_orders')}));return
        from .desktop import serve
        serve(root,args.port,not args.no_collect,args.open_browser,research=True);return
    if args.command=='research-status':
        from .automation import research_status
        print(canonical(research_status(root)));return
    if args.command=='capital':
        from .capital import ShadowCapital
        from .recorder import RecorderLock
        now=datetime.now(timezone.utc)
        with RecorderLock(root/'data/research.lock'):
            store=Store(root/'data/shadow.sqlite')
            try:
                capital=ShadowCapital(store)
                if args.capital_action=='plan':capital.configure(args.amount,args.unit,args.start_date,now)
                capital.schedule(now)
                if args.capital_action=='confirm':capital.confirm(args.period,args.reference,now)
                if args.capital_action=='event':capital.event(args.kind,args.amount,args.reference,now)
                result=capital.summary(now)
            finally:store.close()
        print(canonical(result));return
    if args.command=='technical-demo':
        from .technical_demo import demonstrate
        print(canonical(demonstrate(root,resolve(args.output))));return
    if args.command=='replay-shadow':
        from .shadow_replay import replay_shadow
        print(canonical(replay_shadow(root)));return
    if args.command=="desktop":
        from .desktop import serve
        serve(root,args.port,args.collect,args.open_browser);return
    if args.command=="verify-forward":
        from .forward_integrity import verify_forward
        result=verify_forward(root)
    elif args.command=="micro-feasibility":
        from .microstructure import probe
        result=probe(root,args.samples)
    elif args.command=="collect-forward":
        import signal
        from .recorder import Recorder,RecorderLock
        # Ownership precedes constructor writes/manifests, not just the polling loop.
        with RecorderLock(root/'data/recorder.lock'):
            recorder=Recorder(root)
            try:
                prior=recorder.store.last('collector_heartbeat')
                if prior and (datetime.now(timezone.utc)-datetime.fromisoformat(prior['timestamp'])).total_seconds()>180:
                    recorder.issue('collector_runtime_gap','Collection resumed after '+prior['timestamp']+'; no missed observations backfilled')
                def terminate(signum, frame):
                    raise KeyboardInterrupt
                previous=signal.signal(signal.SIGTERM,terminate)
                try:result=recorder.run(args.cycles,args.seconds,_lock_held=True)
                finally:signal.signal(signal.SIGTERM,previous)
            finally:recorder.store.close()
    elif args.command in ("freeze-forward","collector-health","forward-report"):
        from .cohort import freeze_cohort
        from .forward_reports import health,forward_report
        store=Store(root/"data/forward.sqlite")
        try:
            if args.command=="freeze-forward":result=freeze_cohort(store,root)
            elif args.command=="collector-health":result=health(store,root)
            else:
                report=forward_report(store,root,args.date);result={k:report[k] for k in ("snapshots_total","resolved_markets_total","cost_usd","live_trading")}
        finally:store.close()
    elif args.command=="download":result=download(root,args.platform,args.limit,args.pages,args.base,args.since)
    elif args.command=="research":
        all_result=experiment(root,resolve(args.dataset),resolve(args.config),resolve(args.report),resolve(args.freeze) if args.freeze else None)
        result={k:all_result[k] for k in ["status","verdict","raw_markets","timestamp_valid_rows","oos"]}
    elif args.command=="freeze":result=freeze(resolve(args.dataset),resolve(args.config),resolve(args.output),root)
    elif args.command=="shadow-once":result=shadow(root,args.limit,resolve(args.dataset),args.series)
    else:
        store=Store(root/"data/local.sqlite")
        if args.command=="daily-report":daily_report(store,root/f"reports/SHADOW_{args.date}.md",args.date)
        result={"audit_valid":store.verify(),"records":len(store.records())};store.close()
    print(canonical(result))


if __name__=="__main__":main()
