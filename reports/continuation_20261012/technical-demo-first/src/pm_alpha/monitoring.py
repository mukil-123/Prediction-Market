"""Human-readable daily shadow and data-quality reporting."""
from pathlib import Path
from .storage import Store


def daily_report(store:Store,target:Path,date:str)->None:
    decisions=[d for d in store.records("shadow_decision") if d["timestamp"].startswith(date)]
    settlements=[d for d in store.records("paper_settlement") if d["timestamp"].startswith(date)]
    rejections=[d for d in store.records("shadow_data_rejection") if d["timestamp"].startswith(date)]
    reasons={}
    for d in decisions:reasons[d["decision"]]=reasons.get(d["decision"],0)+1
    lines=[f"# Shadow daily report — {date} UTC",f"\nAudit hash chain valid: {store.verify()}",f"Decisions recorded: {len(decisions)}",f"Book/data rejections recorded: {len(rejections)}",f"Settlements recorded: {len(settlements)}",f"Realized hypothetical P&L: ${sum(s['hypothetical_pnl'] for s in settlements):.6f}","\n| Decision | Count |","|---|---:|"]
    lines.extend(f"| {reason} | {n} |" for reason,n in sorted(reasons.items()))
    lines.extend(["\n| Market | Data rejection |","|---|---|"]+[f"| {r['market_id']} | {r['reason']} |" for r in rejections])
    lines.append("\nNo wallet, live orders, paid API or deletion of losing decisions. Unresolved outcomes remain pending; zero settlements are not zero final losses.")
    target.parent.mkdir(parents=True,exist_ok=True);target.write_text("\n".join(lines)+"\n",encoding="utf-8")
