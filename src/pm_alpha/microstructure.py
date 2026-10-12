"""Limited free-data feasibility probe; no arbitrage/strategy implementation."""
import time
from math import isfinite
from statistics import median
from datetime import datetime, timezone
from .data.forward_http import ForwardHTTP
from .storage import Store,canonical
from .schema import DataInvalid,utc


def spot_book(raw,source):
    if source=="coinbase":
        asks,bids=raw.get("asks") or [],raw.get("bids") or []
        source_time=raw.get("time");kind="snapshot_source_time" if source_time else "receipt_only"
    elif source=="kraken":
        if raw.get("error"):raise DataInvalid("Kraken API error: "+str(raw["error"]))
        result=raw.get("result") or {}
        if len(result)!=1:raise DataInvalid("Unexpected spot pair envelope")
        b=next(iter(result.values()));asks,bids=b.get("asks") or [],b.get("bids") or []
        source_time=None;kind="per_level_update_seconds_not_snapshot_time"
    else:raise DataInvalid("Unknown underlying source")
    if not bids or not asks:raise DataInvalid("Empty spot depth")
    for row in bids+asks:
        if len(row)<2 or not all(isfinite(float(v)) and float(v)>0 for v in row[:2]):raise DataInvalid("Malformed spot depth")
    bid=max(float(r[0]) for r in bids);ask=min(float(r[0]) for r in asks)
    if bid>ask:raise DataInvalid("Crossed spot book")
    return {"bid":bid,"ask":ask,"bid_levels":len(bids),"ask_levels":len(asks),"source_time":source_time,"timestamp_kind":kind}


def probe(root,samples=3):
    if not 1<=samples<=5:raise ValueError("Feasibility probe capped at five samples per source")
    store=Store(root/"data/forward.sqlite");http=ForwardHTTP(root/"data/forward_raw",store)
    results=[];issues=[]
    sources=[("coinbase","https://api.exchange.coinbase.com","/products/BTC-USD/book",{"level":2}),
             ("kraken","https://api.kraken.com","/0/public/Depth",{"pair":"XBTUSD","count":10})]
    try:
        for source,base,path,params in sources:
            for _ in range(samples):
                try:
                    r=http.get(base,path,params);b=spot_book(r.data,source)
                    snap=store.db.execute("SELECT payload FROM audit WHERE kind='market_snapshot' AND json_extract(payload,'$.category')='crypto' ORDER BY seq DESC LIMIT 1").fetchone()
                    import json
                    market=json.loads(snap[0]) if snap else None
                    skew=abs((r.received_at-utc(market["capture_time"])).total_seconds()) if market else None
                    row={"source":source,"pair":"BTC/USD","received_at":r.received_at.isoformat(),"request_start":r.started_at.isoformat(),
                         "round_trip_ms":r.elapsed_ms,"raw_response_hash":r.sha256,"endpoint":r.endpoint,**b,
                         "prediction_market_id":market["market_id"] if market else None,"prediction_receipt_skew_seconds":skew,
                         "prediction_event_timestamp_available":bool(market and market.get("source_event_times")),
                         "prediction_market_still_open":bool(market and utc(market["close_time"])>r.received_at),
                         "benchmark_match_verified":False,"limitation":"Kraken/Coinbase spot is not the contract's sixty-second CF BRTI average"}
                    store.append("microstructure_probe",f"micro:{time.time_ns()}",row);results.append(row)
                except Exception as e:
                    row={"source":source,"timestamp":datetime.now(timezone.utc).isoformat(),"reason":f"{type(e).__name__}:{e}"}
                    latest=store.db.execute("SELECT payload FROM audit WHERE kind='forward_retrieval' AND json_extract(payload,'$.url') LIKE ? ORDER BY seq DESC LIMIT 1",(base+path+"%",)).fetchone()
                    if latest:
                        import json
                        info=json.loads(latest[0]);row.update({"http_status":info["status"],"elapsed_ms":info["elapsed_ms"],"content_type":info["headers"].get("Content-Type"),"raw_response_hash":info["sha256"]})
                    store.append("microstructure_failure",f"micro-fail:{time.time_ns()}",row);issues.append(row)
                    break # no repeated denial/schema probing or automatic alias fallback
        summary={"status":"DEFERRED_DATA_LIMITATION","samples":len(results),"issues":issues,
                 "spot_orderbook_available":bool(results),"prediction_book_available":bool(store.db.execute("SELECT 1 FROM audit WHERE kind='market_snapshot' AND json_extract(payload,'$.category')='crypto' LIMIT 1").fetchone()),
                 "median_round_trip_ms":median(r["round_trip_ms"] for r in results) if results else None,
                 "median_receipt_skew_seconds":median(r["prediction_receipt_skew_seconds"] for r in results if r["prediction_receipt_skew_seconds"] is not None) if any(r["prediction_receipt_skew_seconds"] is not None for r in results) else None,
                 "reason":"REST receipt pairs lack a synchronized prediction venue event clock and verified identical settlement underlying. No latency/arbitrage inference.",
                 "cost_usd":0,"live_trading":False}
        out=root/"reports/PM_M1_FEASIBILITY.json";out.parent.mkdir(parents=True,exist_ok=True);out.write_text(canonical(summary)+"\n")
        lines=["# PM-M1 free microstructure feasibility","","**DEFERRED_DATA_LIMITATION. No arbitrage claim.**","",canonical(summary),"",
               "| Source | Spot samples | Median HTTP RTT (ms) | Timestamp content |","|---|---:|---:|---|",*[
                   f"| {source} | {len([r for r in results if r['source']==source])} | {median([r['round_trip_ms'] for r in results if r['source']==source]):.1f} | {next(r['timestamp_kind'] for r in results if r['source']==source)} |" for source in sorted({r["source"] for r in results})],"",
               "One recorder uses a global one-GET/second ceiling and no burst. Coinbase's documented public limit is 10/s; this probe is far below it. Observed network RTT and multi-market serialization limit achievable polling. Kraken per-level times cannot be interpreted as a global book publication time. Kalshi public REST books provide receipt-time evidence without a venue event clock. Local/source clock offset, transport latency, asynchronous responses and the CF benchmark mismatch prevent a defensible subsecond lead/lag or arbitrage claim. WebSocket feasibility/authentication and exact BRTI permission remain future work.",""]
        (root/"reports/PM_M1_FEASIBILITY.md").write_text("\n".join(lines))
        return summary
    finally:store.close()
