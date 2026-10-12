# Blocker log

## B1 — Intermittent Polymarket access / incomplete early history

**BLOCKER:** Initial probes returned HTTP 403/Cloudflare 1010. Later ordinary Gamma/Data API client calls succeeded; this is an intermittent access issue. The initial three 2020 markets had empty history. A recent-start cohort was separately requested, recorded as a data-feasibility variation.

**WHY IT MATTERS:** Collector completeness and free historical coverage cannot be assumed from one successful request. Early markets predate documented price-history coverage; publication/depth problems remain even where history is returned.

**MISSING:** Reliable endpoint access and sufficiently complete usable history, plus B2/B3 prerequisites.

**FREE ALTERNATIVES CHECKED:** Official documentation accessible; later ordinary Gamma/Data API reads succeeded. Three early contracts returned no history. The recent-start sample yielded nine records without a required final-resolution timestamp and one settled before the fixed diagnostic snapshot. Kalshi supplied 100 settled records and seven historical candle snapshots as a separately labeled validation sample. No proxy/browser/anti-bot bypass attempted.

**NEXT:** Run the documented public downloader on the user's ordinary permitted Windows connection. If still denied, stop and seek legitimate platform guidance; continue venue-independent offline work.

## B2 — Original historical information availability

**BLOCKER:** Candle end time does not establish publication time. Downloaded current contract rules/metadata do not establish their historical contents.

**WHY IT MATTERS:** Backdating either would permit leakage. Strict PM-C1 eligibility must report DATA_INVALID.

**MISSING:** Original released market metadata/fee vintages and quote history with defensible release/receipt semantics.

**FREE ALTERNATIVES CHECKED:** Official Polymarket history/resolution documentation; real Kalshi minute candles; current public REST books; archived-market API pathway documented. Current snapshots can be saved prospectively, but are not substituted as historical vintages.

**NEXT:** Begin allowed local prospective snapshot collection; freeze complete cohorts before outcomes. Previously inspected diagnostic events cannot be reused as untouched OOS.

## B3 — Historical executable capacity and fee vintages

**BLOCKER:** Candle quote fields have no depth and can be asynchronous; no historical market-specific fee snapshot was obtained.

**WHY IT MATTERS:** An attractive midpoint calibration curve does not establish fillable after-cost expectancy.

**MISSING:** Synchronized depth/receipt times, original fees/minimum/tick parameters, measured latency/fill/adverse-selection behaviour.

**FREE ALTERNATIVES CHECKED:** Public live books and documented fee routes; explicit conservative fee model; FOK paper simulator. No free complete depth archive verified.

**NEXT:** Store live snapshots and time-specific fee information, implement shadow reconciliation, then test costs/capacity. Label all candle-based hypothetical P&L idealized if ever enabled.

## B4 — Eligibility and income/independence evidence

**BLOCKER:** India/Tamil Nadu live eligibility, meaningful-income capital, and correlation with the XAUUSD system remain unestablished.

**WHY IT MATTERS:** Public API access is not legal/account approval; theoretical probability gains are not income; unrelated platform names do not prove independent returns.

**MISSING:** Account/residence eligibility and applicable local-law review for a later live milestone; validated returns; matched timestamps from the XAUUSD system.

**FREE ALTERNATIVES CHECKED:** Official platform restrictions and Kalshi Member Agreement/help references; capital-minimum example only; no capital deployed.

**NEXT:** Resolve eligibility before live work. Estimate income/capacity/correlation only after genuine out-of-sample and shadow results exist. None blocks local read-only research.

## B5 — Remaining strategy and production research

**BLOCKER:** Weather vintages, structured models, microstructure models, complete historical universe ingestion, automatic shadow label reconciliation, calendar-time survival stress and promotion statistics are not complete.

**WHY IT MATTERS:** A working milestone cannot be represented as a fully validated income bot.

**FREE ALTERNATIVES CHECKED:** Standard-library architecture, public API documentation and local pipeline. No paid workaround introduced.

**NEXT:** Finish a timestamp-valid PM-C1 cohort first; PM-W1 proceeds only if original free forecast vintages and matching resolution sources pass feasibility. Keep AI optional.
