# Architecture

Runtime: Python ≥3.11, standard library, local SQLite. TOML replaces YAML to avoid another runtime dependency. This is a Python package under `src/pm_alpha` rather than many empty directories.

| Component | Implementation | Boundary |
|---|---|---|
| Public market data | `data/http.py`, `data/polymarket.py`, `data/kalshi.py` | GET, throttling, cursors, schema checks, provenance; never order signing |
| External data | W1/S1 registered feasibility tasks | No weather vintages or structured predictor history fabricated |
| Normalized event store | `schema.py`, `dataset.py`, `storage.py` | Contract metadata, quotes and labels separate; UTC; unknown availability explicit |
| Features/as-of | `Stamp.require_asof`, `ResearchRow.require_valid` | Metadata and prices both pass release-time checks; online mode additionally checks receipt |
| Probability model | `models.py` | Independently estimated bin calibration, no LLM |
| Strategy versions/gates | `strategies.py`, config, registry | No state skips; failed gates reject advancement; LIVE_SMALL unavailable |
| Uncertainty | Wilson empirical bin intervals, cluster bootstrap | Not an individual-contract posterior; bucket heterogeneity remains a limitation |
| Costs/risk | `costs.py`, `risk.py` | USD payout math, conservative fees, position minimums, deterministic capped sizing |
| Portfolio | `portfolio.py`, cash reservations in OMS/backtest | All markets correlated until proved otherwise; no reuse of unsettled stake |
| Paper OMS | `execution.py` | Decision first; later book required for hypothetical FOK fill; append separate settlement |
| Future live adapter | `ExecutionAdapter`, `DisabledLiveAdapter` | Interface only; throws if invoked |
| Validation | `validation.py`, `research.py` | Chronological event groups, label purging, OOS freeze, contamination tracking |
| Reports/monitoring | `metrics.py`, `monitoring.py`, `cli.py` | Markdown, JSON, exact SVG reliability plots, daily audit checks |

Use `python -m pm_alpha --help` for entry points. Code-level function interfaces support verified imported datasets even while real-data publication history is blocked. The first strict experiment is expected to report missing evidence rather than force trades.

An audit hash chain detects inconsistent records under normal local operation; SQLite triggers disallow ordinary UPDATE/DELETE. It is not a tamper-proof remote notarization service: a filesystem owner can replace a database or alter code. Keep backups, source commits, hashes and original ledgers together.

Monetary calculations convert decimal quote prices to `Decimal` for fee rounding. Quote prices normalize to 12 decimal places to remove binary-float artifacts; the public feeds quote much coarser ticks. Complete tick/fee-rule replication and intratrade equity marking are future requirements.
