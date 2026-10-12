"""Forecast scoring independent of trading; deterministic local SVG plots."""
from math import log
from statistics import mean
from pathlib import Path
from .models import bucket, wilson
from .schema import probability


def calibration(pairs: list[tuple[float, int]], bins: int = 20) -> list[dict]:
    groups: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for p, y in pairs:
        probability(p)
        if y not in (0, 1):
            raise ValueError("Binary label required")
        groups[bucket(p, bins)].append((p, y))
    rows = []
    for i, g in enumerate(groups):
        if g:
            actual = mean(y for _, y in g); lo, hi = wilson(sum(y for _, y in g), len(g))
            rows.append({"bucket": i, "n": len(g), "predicted": mean(p for p, _ in g), "actual": actual, "lower": lo, "upper": hi})
    return rows


def scores(pairs: list[tuple[float, int]], bins: int = 20) -> dict:
    if not pairs:
        return {"n": 0, "brier": None, "log_loss": None, "ece": None, "sharpness": None, "auc": None}
    curve = calibration(pairs, bins)
    eps = 1e-12
    clipped = [(min(1-eps, max(eps, p)), y) for p, y in pairs]
    pos = [p for p, y in pairs if y == 1]; neg = [p for p, y in pairs if y == 0]
    auc = mean(1 if a>b else 0.5 if a==b else 0 for a in pos for b in neg) if pos and neg else None
    return {"n": len(pairs), "brier": mean((p-y)**2 for p, y in pairs),
            "log_loss": -mean(y*log(p)+(1-y)*log(1-p) for p,y in clipped),
            "ece": sum(r["n"]*abs(r["actual"]-r["predicted"]) for r in curve)/len(pairs),
            "sharpness": mean((p-0.5)**2 for p, _ in pairs), "auc": auc}


def reliability_svg(pairs: list[tuple[float, int]], target: Path, title: str) -> None:
    from html import escape
    target.parent.mkdir(parents=True, exist_ok=True)
    def x(v: float) -> float: return 60+360*v
    def y(v: float) -> float: return 420-360*v
    pieces = [f'<svg xmlns="http://www.w3.org/2000/svg" width="520" height="510" viewBox="0 0 520 510"><rect width="520" height="510" fill="white"/><g font-family="sans-serif" fill="#172b4d"><text x="30" y="30" font-size="17">{escape(title)}</text><path d="M60 60V420H420" fill="none" stroke="#172b4d"/><path d="M60 420L420 60" stroke="#adb5bd" stroke-dasharray="6 6"/>']
    for v in [0,0.2,0.4,0.6,0.8,1]:
        pieces.append(f'<text x="{x(v)-10}" y="443">{v:.1f}</text><text x="20" y="{y(v)+4}">{v:.1f}</text>')
    for r in calibration(pairs):
        pieces.append(f'<line x1="{x(r["predicted"])}" x2="{x(r["predicted"])}" y1="{y(r["lower"])}" y2="{y(r["upper"])}" stroke="#2f6fed"/><circle cx="{x(r["predicted"])}" cy="{y(r["actual"])}" r="5" fill="#2f6fed"><title>n={r["n"]}</title></circle>')
    pieces.append('<text x="140" y="475">Forecast probability</text><text x="30" y="495" font-size="12">Observed outcome rate; bars: 95% Wilson intervals</text></g></svg>')
    target.write_text("".join(pieces), encoding="utf-8")
