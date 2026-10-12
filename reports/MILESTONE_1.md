# Milestone 1 — Prediction-Market Alpha System

**Built and tested; no verified trading edge. Verdict: RETEST_WITH_BETTER_DATA.**

## Work completed

Created a local, Git-versioned Python repository with zero runtime package dependencies. Implemented public Polymarket/Kalshi downloaders, normalized schema, content-addressed raw storage, UTC/as-of guards, SQLite append-only audit, probability and fee math, deterministic capped sizing, conservative portfolio grouping, PM-C1 calibration/scoring/backtesting, chronological purged splits, immutable OOS freeze/exposure ledger, paper OMS and daily reporting. No live-money adapter, wallet or paid API was connected.

## Files created/changed

- `README.md`, compact `AGENTS.md`, package/setup and Windows commands.
- `src/pm_alpha/`: modular data, schemas, models, costs, risk, portfolio, execution, validation, storage, reports and CLI.
- `tests/`: automated software, leakage, cash/exposure, OOS, real-sample parsing and persistence checks.
- `config/`: research, risk and public endpoint inventory.
- `docs/`: architecture, research/risk rules, sources/provenance, cost ledger, registry/trial ledger, viral claims, blockers and future live requirements.
- `data/`: actual API payloads, normalized datasets, original audit databases.
- `reports/PM_C1_v001.md` and JSON/SVG: Kalshi feasibility experiment.
- `reports/PM_C1_POLYMARKET_v001.md`: separate Polymarket feasibility result.
- `reports/SHADOW_2026-10-01.md`: forward sample and rejection report.

## Test results

**88 passed**, Python 3.12.14 on Linux. Native Windows execution was not available; PowerShell setup/commands are supplied. Runtime CLI needs no third-party package. `python -m pytest` is the single test command. Synthetic fixtures test software only and are never presented as market profit. Unit tests exercise 10,000-path Monte Carlo mechanics; no strategy Monte Carlo survival claim exists because there are no eligible real trades.

## First research results

| Check | Actual result |
|---|---|
| Kalshi settled market records downloaded | 100 |
| Distinct event representatives in this convenience cohort | 19 |
| Usable preceding historical candle snapshots | 7 |
| Strict timestamp-valid records | 0 |
| Valid simulated trades | 0 |
| Polymarket closed contracts inspected | 3 early + 10 recent-start |
| Usable Polymarket diagnostic snapshots | 0 |
| Final OOS opened | No |
| Recorded forward shadow decisions | 1, skipped for unverified fees |
| Live generic books rejected | 5, missing two-sided depth |
| Real-money orders / spend | 0 / $0 |

The seven Kalshi midpoint/outcome observations yield descriptive Brier score 0.183029. **This is not valid OOS forecasting evidence or a calibration edge.** Only seven events, a recent convenience sample, original publication times missing, and current metadata are insufficient.

Five of seven candle snapshots had bid–ask spreads at least $0.90 per $1 payout. Such midpoints are poor evidence of an executable opportunity. A forecast compared only with displayed/midpoint probability can appear attractive while the ask eliminates it.

No trained calibration model has passed validation. The strict runner refuses unknown release times, historical fee assumptions and missing depth. It returns DATA_INVALID rather than treating the seven rows as tradable history. Inspected diagnostic events are permanently contaminated for later untouched OOS in the included ledger.

## Blockers

Initial direct Polymarket probes returned HTTP 403/Cloudflare 1010; later ordinary public client calls succeeded. No proxy, spoofed browser, VPN or geoblock bypass was used. Early 2020 contracts returned empty history. In the recent-start sample nine did not provide the required final-resolution timestamp and one resolved before the fixed 24-hour snapshot. Raw responses and exclusions are retained.

For executable research, original publication/metadata/fee vintages and synchronized depth remain missing. The shipped forward command records snapshots/skips; a validated forecast, verified dynamic fees and automatic settlement reconciliation still need work. India/Tamil Nadu live eligibility, income bankroll and measured independence from XAUUSD remain unresolved. PM-W1/S1/M1/A1 remain registered research branches; none is promoted.

## Zero-cost status

$0 paid service/subscription spend; baseline service bill $0/month. Python/SQLite runtime, public GETs and local files only. Existing hardware, internet and electricity are assumed. Eventual live trading would require capital and fees. Full dependency limitations/replacements are in `docs/COST_LEDGER.md`.

## Next action

Replay the supplied sample locally and start permitted prospective book/metadata/fee collection before outcomes. Freeze a new cohort once those inputs are timestamp-valid. Complete shadow settlement reconciliation, then train and validate PM-C1; reserve new future events for OOS. Begin PM-W1 only after original free forecast vintages and matching station/resolution criteria pass feasibility. No paid evaluation or trading deposit is justified by this milestone.

No external GitHub repository or background cloud job was created. THEER and the XAUUSD/FundingPips code were not modified.
