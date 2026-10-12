"""Daily collection evidence and visible health, with no fabricated performance."""
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median, mean
from urllib.parse import urlsplit
from .storage import canonical
from .schema import utc
from .cohort import cohort_summary, COHORT_ID
from .costs import taker_fee


def small_rows(store,kind,fields,date=None,time_field="capture_time"):
    # Bound memory: read scalar summaries, not full orderbooks/raw/metadata.
    expr=",".join("json_extract(payload,'$."+f+"')" for f in fields)
    sql=f"SELECT {expr} FROM audit WHERE kind=?"
    args=[kind]
    if date:
        sql+=" AND json_extract(payload,?) LIKE ?";args.extend(["$."+time_field,date+"%"])
    for row in store.db.execute(sql,args):yield dict(zip(fields,row))


def health(store,root,now=None,check_process=True):
    now=utc(now or datetime.now(timezone.utc));last=store.last("collector_heartbeat")
    result={"process_alive":False,"heartbeat_age_seconds":None,"state":"NOT_STARTED", "database_writable":False,
            "stale_data":True,"future_timestamps":0,"duplicate_snapshots":0,"api_reachable":{},"audit_valid":store.verify()}
    if last:
        age=(now-utc(last["timestamp"])).total_seconds();result.update({"state":last["state"],"heartbeat_age_seconds":age})
        if check_process and last["state"] not in ("STOPPED","FAILED"):
            try:os.kill(last["pid"],0);result["process_alive"]=True
            except (ProcessLookupError,PermissionError,OSError):pass
        if age<0:result["future_timestamps"]+=1
    try:
        store.db.execute("BEGIN IMMEDIATE");store.db.rollback();result["database_writable"]=True
    except Exception:store.db.rollback()
    snap=store.last("market_snapshot")
    if snap:
        age=(now-utc(snap["capture_time"])).total_seconds()
        result["last_snapshot_age_seconds"]=age;result["stale_data"]=age>180 or age<0
        if age<0:result["future_timestamps"]+=1
    retrievals=small_rows(store,"forward_retrieval",["url","retrieved_at"])
    for r in retrievals:result["api_reachable"][urlsplit(r["url"]).hostname]=(now-utc(r["retrieved_at"])).total_seconds()<1200
    for r in small_rows(store,"forward_api_failure",["url","timestamp","status"]):
        if r["status"] in (401,403) and (now-utc(r["timestamp"])).total_seconds()<1200:
            result["api_reachable"][urlsplit(r["url"]).hostname]=False
    for r in small_rows(store,'forward_schema_failure',['url']):result['api_reachable'][urlsplit(r['url']).hostname]=False
    for r in small_rows(store,'microstructure_failure',['source']):
        host={'coinbase':'api.exchange.coinbase.com','kraken':'api.kraken.com'}.get(r['source'])
        if host:result['api_reachable'][host]=False
    result['stale_markets']=[]
    active=store.last('forward_universe') or {}
    for item in active.get('tracked',[]):
        latest=store.db.execute("SELECT json_extract(payload,'$.capture_time'),json_extract(payload,'$.close_time') FROM audit WHERE kind='market_snapshot' AND json_extract(payload,'$.platform')=? AND json_extract(payload,'$.market_id')=? ORDER BY seq DESC LIMIT 1",(item['platform'],item['market_id'])).fetchone()
        if latest and utc(latest[1])>now and (now-utc(latest[0])).total_seconds()>180:result['stale_markets'].append(item)
    result["rate_limit_errors"]=store.db.execute("SELECT COUNT(*) FROM audit WHERE kind='forward_api_failure' AND json_extract(payload,'$.status')=429").fetchone()[0]
    result["malformed_schema_or_books"]=store.db.execute("SELECT COUNT(*) FROM audit WHERE kind='forward_integrity'").fetchone()[0]
    result["live_trading"]=False
    result["healthy"]=bool(result["process_alive"] and result["database_writable"] and not result["stale_data"] and not result['stale_markets'] and result["audit_valid"] and not result["future_timestamps"])
    return result


def forward_report(store,root,date):
    root=Path(root);out=root/"reports/forward";out.mkdir(parents=True,exist_ok=True)
    rows=list(small_rows(store,"market_snapshot",["platform","market_id","category","spread","volume","liquidity","capture_time","fee.status","fee.rate","yes_ask","minimum_shares","minimum_shares_basis","venue_minimum_shares"],date))
    all_count=store.db.execute("SELECT COUNT(*) FROM audit WHERE kind='market_snapshot'").fetchone()[0]
    def count(kind):return store.db.execute("SELECT COUNT(*) FROM audit WHERE kind=?",(kind,)).fetchone()[0]
    h=health(store,root);c=cohort_summary(store,out)
    spreads=[r["spread"] for r in rows];vol=[r["volume"] for r in rows if r["volume"] is not None];liq=[r["liquidity"] for r in rows if r["liquidity"] is not None]
    requests=list(small_rows(store,"forward_retrieval",["stored_bytes","elapsed_ms","retrieved_at"],date,time_field="retrieved_at"))
    db=root/"data/forward.sqlite";raw=root/"data/forward_raw"
    raw_bytes=sum(p.stat().st_size for p in raw.glob("*"));db_bytes=sum(p.stat().st_size for p in db.parent.glob(db.name+"*"))
    first=store.db.execute("SELECT json_extract(payload,'$.capture_time') FROM audit WHERE kind='market_snapshot' ORDER BY seq LIMIT 1").fetchone()
    expected_snapshots_day=12*86400/30
    # Estimate recurring writes separately from one-time registry/source startup data.
    sample_bytes=store.db.execute("SELECT AVG(length(CAST(payload AS BLOB))) FROM audit WHERE kind='market_snapshot'").fetchone()[0]
    book_sizes=[r['stored_bytes'] for r in small_rows(store,'forward_retrieval',['url','stored_bytes']) if '/orderbook' in r['url'] or '/book?' in r['url']]
    retrieval_bytes=store.db.execute("SELECT AVG(length(CAST(payload AS BLOB))) FROM audit WHERE kind='forward_retrieval'").fetchone()[0] or 0
    # 1.5x SQLite allocation overhead, one book GET per Kalshi snapshot, heartbeat and discovery/weather allowance.
    per_snapshot=1.5*((sample_bytes or 0)+retrieval_bytes+700)+(mean(book_sizes) if book_sizes else 0)
    daily=per_snapshot*expected_snapshots_day+10*1024**2 if all_count else None
    gaps=[];prior={};latest={}
    for r in rows:
        k=(r['platform'],r['market_id']);latest[k]=r
        if k in prior:gaps.append((utc(r['capture_time'])-utc(prior[k])).total_seconds())
        prior[k]=r['capture_time']
    small_capital=[]
    for (platform,market_id),r in latest.items():
        if r['fee.rate'] is None or r['minimum_shares'] is None:continue
        shares=r['minimum_shares'];cash=shares*r['yes_ask'];fee=taker_fee(shares,r['yes_ask'],r['fee.rate'],platform)
        small_capital.append({'platform':platform,'market_id':market_id,'minimum_shares':shares,'ask':r['yes_ask'],
                              'minimum_shares_basis':r['minimum_shares_basis'] or 'PROVISIONAL_LOCAL_DEFAULT','venue_minimum_shares':r['venue_minimum_shares'],
                              'minimum_cash_with_fee_bound':cash+fee,'fee_percent_of_cash':100*fee/cash if cash else None,
                              'bankroll_risk_floor':(cash+fee)/.0025,'spread':r['spread'],
                              'note':'Risk-cap lower bound only; Kelly, uncertainty, slippage and validation can require more or disallow the trade'})
    summary={"date_utc":date,"generated_at":datetime.now(timezone.utc).isoformat(),"markets_tracked":len({(r["platform"],r["market_id"]) for r in rows}),
             "snapshots_today":len(rows),"snapshots_total":all_count,"api_failures_total":count("forward_api_failure"),
             "source_failures_total":count("forward_source_failure")+count("weather_source_failure"),
             "missing_liquidity_today":sum(r["liquidity"] is None for r in rows),"median_spread":median(spreads) if spreads else None,
             "median_volume":median(vol) if vol else None,"median_liquidity":median(liq) if liq else None,
             "category_snapshots":dict(Counter(r["category"] for r in rows)),"resolved_markets_total":count("forward_resolution"),
             "newly_resolved_today":len(list(small_rows(store,"forward_resolution",["market_id"],date,time_field="first_observed_at"))),
             "weather_contract_versions_detected":count("weather_contract"),"weather_forecast_records":count("weather_forecast"),
             "weather_observation_records":count("weather_observation"),"candidate_weather_signals":count("weather_signal"),
             "hypothetical_trades":0,"real_orders":0,"integrity_violations_total":count("forward_integrity"),
             "discovery_exclusions_total":count("forward_discovery_exclusion"),"coverage_warnings_total":count("forward_coverage_gap"),
             "cohort":c,"health":h,"cost_usd":0,"service_bill_per_month_usd":0,"live_trading":False,
             "storage":{"raw_compressed_bytes":raw_bytes,"sqlite_and_wal_bytes":db_bytes,"early_projected_bytes_day":daily,
                        "early_projected_bytes_30_days":daily*30 if daily else None,"projection_note":"Kalshi-mix estimate at full 12-market/30s occupancy: observed record sizes +1.5x SQLite overhead +10MiB/day overhead; excludes one-time startup registry. Short-run estimate."},
             "http":{"requests_today":len(requests),"median_elapsed_ms":median([r["elapsed_ms"] for r in requests]) if requests else None},
             "achieved_median_market_poll_seconds":median(gaps) if gaps else None,
             "cadence_warnings_total":count('forward_cadence_warning'),"small_capital_constraints":small_capital,
             "evidence":"Forward collection/data feasibility only. No validated forecast transformation, OOS trading result or income estimate."}
    metrics=c["market_baseline"]
    fmt=lambda v:"unknown" if v is None else f"{v:.6g}" if isinstance(v,float) else str(v)
    lines=[f"# Forward research — {date} UTC", "", "**NO VERIFIED EDGE. LIVE_TRADING=false. $0 paid service spend.**", "",
           "| Collection item | Value |","|---|---:|",
           *[f"| {k.replace('_',' ')} | {fmt(summary[k])} |" for k in ("markets_tracked","snapshots_today","snapshots_total","api_failures_total","source_failures_total","missing_liquidity_today","median_spread","median_volume","median_liquidity","newly_resolved_today","resolved_markets_total","weather_contract_versions_detected","weather_forecast_records","weather_observation_records","candidate_weather_signals","hypothetical_trades","integrity_violations_total","discovery_exclusions_total","coverage_warnings_total")],
           "","Market count means distinct markets captured today; current active watchlist is in the latest immutable universe record. Volume is cumulative contract shares; Kalshi liquidity dollars are not supplied and remain unknown.",
           "","## Category snapshots","",*([f"- {k}: {v}" for k,v in summary["category_snapshots"].items()] or ["No snapshots yet."]),
           "","## PM-C1 cohort","",f"Frozen cohort: {COHORT_ID}. Eligible entries: {c['entries']}; locked exclusions: {c['exclusions']}; resolved TRAIN events: {c['resolved_train']}.",
           "Daily calibration diagnostics expose TRAIN only. VALIDATION/TEST are withheld. A model and after-cost policy are unavailable until enough independent prospective events resolve.",
           "","Market baseline scores: "+(canonical(metrics) if metrics else "not estimable; no resolved TRAIN entries."),
           "Calibration model result: not estimable. After-cost expectancy: not estimable. Final TEST opened: false.",
           "","| Probability bucket | Resolved TRAIN n | Outcome frequency |","|---|---:|---:|",
           *[f"| {b['bucket']} | {b['n']} | {fmt(b['empirical_frequency'])} |" for b in c["probability_buckets"]],
           "","## PM-W1","","NWS original received vintages are archived as predictor data. Operational station readings are not final contract labels. Ambiguous station/window/rounding/finality blocks signals; no fitted error distribution or trading threshold is claimed.",
           "","## Achieved polling and small capital","",f"Median interval between repeated same-market captures: {fmt(summary['achieved_median_market_poll_seconds'])} seconds; median public GET RTT: {fmt(summary['http']['median_elapsed_ms'])} ms. Target cadence is not an achieved-frequency claim.",
           "","| Platform/market | Minimum shares | Ask | Minimum cost + fee bound | Fee % of entry cash | Bankroll risk floor |","|---|---:|---:|---:|---:|---:|",
           *[f"| {r['platform']}/{r['market_id']} | {fmt(r['minimum_shares'])} | {fmt(r['ask'])} | {fmt(r['minimum_cash_with_fee_bound'])} | {fmt(r['fee_percent_of_cash'])} | {fmt(r['bankroll_risk_floor'])} |" for r in small_capital],
           "","The displayed size is the recorder's conservative research floor (Kalshi: one whole contract), not a verified exchange minimum when venue_minimum_shares is null. Bankroll floor is its cost divided by 0.25%, before Kelly, slippage, uncertainty or cluster restrictions. It is not a profitable/practical income bankroll estimate. All markets still share the conservative risk cluster.",
           "","## Health","",canonical(h),"","An intentional STOPPED state means collection is not running. A current process and fresh heartbeat are required; this workspace does not guarantee collection after the session.",
           "","## Storage and zero cost","",f"Compressed raw: {raw_bytes/1024**2:.2f} MiB; database plus WAL: {db_bytes/1024**2:.2f} MiB.",
           f"Early full-occupancy projection: {daily/1024**2:.1f} MiB/day, {daily*30/1024**3:.2f} GiB/30 days." if daily else "Disk projection pending snapshots.",
           "Projection uses average normalized snapshot/retrieval bytes, compressed book size, 1.5x SQLite overhead, heartbeat allocation and a 10 MiB/day discovery/weather allowance at 12 markets every 30s. One-time registry downloads are shown in actual storage, not multiplied into recurring growth. A broader Polymarket mix uses more GETs; remeasure before expansion. Budget guard stops visibly at the configured local limit; it never deletes evidence. Existing hardware, internet and electricity are assumed.",
           "","## Research evidence","",summary["evidence"],"Unknown costs are never set to zero. Visible depth is capacity evidence, not a guaranteed fill; no hypothetical fills are being reported.","",
           "Expected trades/month, return on bankroll, drawdown and probability of meaningful loss remain unknown until a validated execution policy and prospective after-cost sample exist.",""]
    target=out/f"{date}.md";target.write_text("\n".join(lines),encoding="utf-8")
    (out/f"{date}.json").write_text(canonical(summary)+"\n",encoding="utf-8")
    return summary
