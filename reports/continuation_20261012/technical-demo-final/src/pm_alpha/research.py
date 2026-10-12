"""Strict PM-C1 experiment; validation diagnostics never masquerade as valid OOS."""
import hashlib
import json
import subprocess
import tomllib
from pathlib import Path
from datetime import datetime,timezone
from .dataset import read_dataset
from .schema import DataInvalid
from .storage import Store,digest,canonical
from .models import BinCalibration
from .metrics import scores,calibration,reliability_svg
from .validation import split_rows,cluster_bootstrap,monte_carlo
from .backtest import run_backtest
from .risk import RiskPolicy


def risk_config(root:Path)->tuple[RiskPolicy,float]:
    path=root/"config/risk.toml"
    cfg=tomllib.loads(path.read_text()) if path.exists() else {}
    initial=float(cfg.pop("initial_bankroll",100.0))
    if initial<=0:raise ValueError("Positive initial bankroll required")
    return RiskPolicy(**cfg),initial


def commit_id(root:Path)->str:
    r=subprocess.run(["git","rev-parse","HEAD"],cwd=root,capture_output=True,text=True)
    return r.stdout.strip() if r.returncode==0 else "UNCOMMITTED"


def source_hash(root:Path)->str:
    return digest({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted((root/"src").rglob("*.py"))})


def eligible(rows):
    valid=[];rejected=[]
    for row in rows:
        try:row.require_valid();valid.append(row)
        except DataInvalid as e:rejected.append({"market_id":row.market.market_id,"reason":str(e)})
    return valid,rejected


def representatives(rows):
    groups={}
    for r in sorted(rows,key=lambda r:r.market.market_id):groups.setdefault(r.market.cluster_id,r)
    return sorted(groups.values(),key=lambda r:(r.entry_time,r.market.market_id))


def freeze(dataset:Path,config_path:Path,target:Path,root:Path|None=None)->dict:
    project_root=root or dataset.parent
    rows,_=read_dataset(dataset);valid,_=eligible(representatives(rows))
    cfg=tomllib.loads(config_path.read_text());splits=split_rows(valid,cfg["train_fraction"],cfg["validation_fraction"])
    if not splits["TRAIN"] or not splits["TEST"]:raise DataInvalid("Cannot freeze without valid purged TRAIN and untouched TEST")
    audit=Store((root or dataset.parent)/"data/research_audit.sqlite")
    exposed={group for r in audit.records("research_exposure") for group in r["event_clusters"]}
    audit.close()
    if exposed & {r.market.cluster_id for r in splits["TEST"]}:
        raise DataInvalid("TEST includes events already inspected in earlier diagnostics or experiments")
    model=BinCalibration(cfg["bins"],cfg["prior_strength"]).fit([(r.quote.market_probability,r.label.outcome) for r in splits["TRAIN"]])
    record={"strategy_version":cfg["strategy_version"],"config_hash":digest(cfg),"dataset_sha256":hashlib.sha256(dataset.read_bytes()).hexdigest(),
            "model_hash":digest(model.payload()),"source_hash":source_hash(project_root),
            "risk_config_hash":digest([vars(risk_config(project_root)[0]),risk_config(project_root)[1]]),
            "frozen_at":datetime.now(timezone.utc).isoformat(),"test_ids":[r.market.market_id for r in splits["TEST"]]}
    # A freeze is a new immutable file. It does not authorize trading.
    with target.open("x",encoding="utf-8") as f:f.write(canonical(record)+"\n")
    return record


def experiment(root:Path,dataset:Path,config_path:Path,report:Path,freeze_path:Path|None=None)->dict:
    cfg=tomllib.loads(config_path.read_text());rows,metadata=read_dataset(dataset)
    if cfg.get("live_trading",False):raise ValueError("Live execution unavailable")
    policy,initial_bankroll=risk_config(root)
    reps=representatives(rows);valid,rejections=eligible(reps)
    splits=split_rows(valid,cfg["train_fraction"],cfg["validation_fraction"])
    model=BinCalibration(cfg["bins"],cfg["prior_strength"]).fit([(r.quote.market_probability,r.label.outcome) for r in splits["TRAIN"]])
    data_hash=hashlib.sha256(dataset.read_bytes()).hexdigest()
    if freeze_path:
        record=json.loads(freeze_path.read_text())
        if record["dataset_sha256"]!=data_hash or record["config_hash"]!=digest(cfg) or record["model_hash"]!=digest(model.payload()) or record["source_hash"]!=source_hash(root) or record["risk_config_hash"]!=digest([vars(policy),initial_bankroll]):
            raise DataInvalid("OOS freeze mismatch; create a new registered version")
        # Refuse repeated automated OOS opens for the same freeze.
        consumed=freeze_path.with_suffix(".consumed.json")
        with consumed.open("x",encoding="utf-8") as f:f.write(canonical({"opened_at":datetime.now(timezone.utc).isoformat(),"freeze_hash":digest(record)}))
    result={"strategy_version":cfg["strategy_version"],"model_version":cfg["model_version"],"git_commit":commit_id(root),
            "dataset_sha256":data_hash,"dataset_metadata":metadata,"config":cfg,"seed":cfg["seed"],"raw_markets":len(rows),
            "event_representatives":len(reps),"timestamp_valid_rows":len(valid),"rejections":rejections,
            "start":min((r.entry_time.isoformat() for r in rows),default=None),"end":max((r.entry_time.isoformat() for r in rows),default=None),
            "assumptions":["YES-only; hold to final binary settlement", "One deterministic representative per event cluster",
                           "No current fee schedule applied retrospectively", "No missing availability times inferred"],
            "splits":{},"oos":"OPENED_ONCE" if freeze_path else "UNTOUCHED"}
    result["risk_policy"]=vars(policy);result["initial_bankroll"]=initial_bankroll
    result["source_sha256"]=source_hash(root);result["cost_model"]="binary-settlement; conservative Kalshi cent-rounding; Polymarket linear symmetric taker fee"
    for name,group in splits.items():
        if name=="TEST" and not freeze_path:
            result["splits"][name]={"n":len(group),"status":"UNTOUCHED"};continue
        market=[(r.quote.market_probability,r.label.outcome) for r in group]
        transformed=[(model.predict(p).probability,y) for p,y in market]
        bt=run_backtest(group,model,bankroll=initial_bankroll,minimum_net_edge=cfg["minimum_net_edge"],slippage=cfg["slippage_per_share"],minimum_bin_samples=cfg["minimum_bin_samples"],policy=policy)
        improvement=[(r.market.cluster_id,(r.quote.market_probability-r.label.outcome)**2-(model.predict(r.quote.market_probability).probability-r.label.outcome)**2) for r in group]
        result["splits"][name]={"market":scores(market),"calibrated":scores(transformed),"brier_improvement_ci":cluster_bootstrap(improvement,seed=cfg["seed"]),"backtest":bt}
    # Historical-data inspection only. Does not feed models, trading or acceptance gates.
    diagnostic_rows=splits["TRAIN"] if valid else reps
    descriptive=[(r.quote.market_probability,r.label.outcome) for r in diagnostic_rows if r.quote.stamp.event_time<r.label.available_time]
    audit=Store(root/"data/research_audit.sqlite")
    inspected=diagnostic_rows+splits["TRAIN"]+splits["VALIDATION"]+(splits["TEST"] if freeze_path else [])
    audit.append("research_exposure",f"exposure:{datetime.now(timezone.utc).isoformat()}",{"dataset_sha256":data_hash,"event_clusters":sorted({r.market.cluster_id for r in inspected}),"reason":"Diagnostic/forecast/trading report inspected; these events may not be reused as untouched TEST"})
    audit.close()
    result["descriptive_only"]={"status":"NOT_A_BACKTEST_NOT_OOS","scores":scores(descriptive),"curve":calibration(descriptive),
                                 "limitations":"Current metadata, unverified historical availability and recent nonrepresentative sample; descriptive association only."}
    trade_returns=[t["return_on_bankroll"] for s in result["splits"].values() for t in s.get("backtest",{}).get("trades",[])]
    result["monte_carlo"]=monte_carlo(trade_returns,paths=cfg["monte_carlo_paths"],seed=cfg["seed"])
    result["status"]="DATA_INVALID" if not valid else "CONTINUE_RESEARCH"
    result["verdict"]="RETEST_WITH_BETTER_DATA" if not valid else "CONTINUE_RESEARCH"
    report.parent.mkdir(parents=True,exist_ok=True)
    report.with_suffix(".json").write_text(canonical(result)+"\n",encoding="utf-8")
    reliability_svg(descriptive,report.with_name(report.stem+"_reliability.svg"),"Data-quality diagnostic only")
    lines=[f"# {cfg['strategy_version']} — first experiment",f"\n**Verdict: {result['verdict']}**. Strict data status: **{result['status']}**.",
           "\n## Hypothesis\nA calibration transformation estimated only from past settled events improves probability scoring and produces positive expectancy after executable prices, costs and uncertainty.",
           f"\n## Data\nDataset SHA-256: `{data_hash}`. {len(rows)} market rows; {len(reps)} distinct event representatives (independence unproven); {len(valid)} pass timestamp integrity. Source: {metadata.get('source','unknown')}. Dates: {result['start']} to {result['end']}.",
           "\n## Exact strategy rules\n20 equal probability bins. Prior weight 20 centred on the input probability. Train only on labels available before the next chronological split. One lexicographically first market per event. Unknown event relationships share a conservative cluster. No thresholds tuned on this sample.",
           f"\n## Entry rules\nBuy YES only when the lower empirical bin bound minus executable ask, actual per-position fees and slippage exceeds {cfg['minimum_net_edge']:.2%}; at least {cfg['minimum_bin_samples']} observations in the training bin. Require verified metadata/quote availability, historical fees and depth. Hold to binary settlement.",
           "\n## Position sizing\nNormal position maximum loss 0.25%, absolute code ceiling 0.50%, correlated event cluster 1.00%, portfolio 2.00%. Fractional Kelly 0.10 can only reduce size. Default simulated bankroll $100. Venue minimum size, share step, cash and depth may cause a zero-size rejection.",
           "\n## Costs\nFees must be verified for the historical trade time. Current schedules are not assumed historical. Slippage reserve $0.005/share is a proposed research stress input, not a measured fill estimate. No maker rebates, funding bonuses or assumed free fills.",
           f"\n## Sample size\nStrict valid records: {len(valid)}. Candle-only records cannot substantiate executable performance.",
           "\n## Calibration\nDescriptive inspection of raw pre-settlement observations follows. It is neither a valid backtest nor OOS forecasting evidence."]
    for key,val in result["descriptive_only"]["scores"].items():lines.append(f"- {key}: {val}")
    lines.extend([f"\n![Reliability diagnostic]({report.stem}_reliability.svg)","\n| Probability bucket | n | Mean quote | Outcome rate | 95% Wilson interval |","|---|---:|---:|---:|---|"])
    for r in calibration(descriptive):lines.append(f"| {r['bucket']*5}–{(r['bucket']+1)*5}% | {r['n']} | {r['predicted']:.4f} | {r['actual']:.4f} | {r['lower']:.4f}–{r['upper']:.4f} |")
    for name in ["Gross results","Net results","Drawdown"]:lines.append(f"\n## {name}\nNo tradability claim. See the strict split results below; rejected data never produces trades. Drawdown requires a full marked quote stream for intratrade accuracy.")
    lines.append(f"\n## Monte Carlo\n{canonical(result['monte_carlo'])}. No survival evidence can be inferred when no valid trades exist.")
    for name in ["TRAIN","VALIDATION","TEST"]:lines.append(f"\n## {'OOS' if name=='TEST' else name.title()} results\n```json\n{json.dumps(result['splits'][name],indent=2)}\n```")
    lines.extend(["\n## Failure analysis\nUnknown historical publication time and retrospective metadata fail the as-of gate. A closed market's final displayed price is never treated as a forecast or a resolution label.",
                  "\n## Robustness tests\nNot evaluated until valid data exists. Planned: event-block bootstraps, chronological walk-forward, category/time stability, fixed parameter perturbations, and 10,000-path bankroll simulations. These are required work, not completed evidence.",
                  "\n## Known limitations\nRecent validation sample is not a complete market universe. Candle bid/ask may be asynchronous and has no depth. Actual publication/revision times are absent. A Wilson bin interval is not an individual event posterior. Correlation with the XAUUSD system cannot be measured without matched timestamped returns.",
                  f"\n## Verdict\n**{result['verdict']}**. Profitability and an income-capable bankroll remain unestablished.",
                  f"\n## Reproducibility\nCommit `{result['git_commit']}`; model `{cfg['model_version']}`; seed {cfg['seed']}. Exact config, source metadata, rejection list and machine results are in `{report.with_suffix('.json').name}`. TEST remains {result['oos']}."])
    report.write_text("\n".join(lines)+"\n",encoding="utf-8")
    return result
