# Strategy registry

| ID | Family | Hypothesis | Version | Status | Trades | Net EV | OOS | Reason |
|---|---|---|---|---|---:|---|---|---|
| PM-C1 | Calibration | Past resolution frequencies improve market probability calibration enough to survive costs | v0.1 | DATA_CHECK; DATA_INVALID input | 0 valid | Not estimable | UNTOUCHED; no valid TEST cohort | Historical publication/rules/fees/depth unavailable |
| PM-W1 | Weather | Original meteorological forecast vintages imply market mispricing | v0.1 | DATA_CHECK | 0 | Not tested | Not allocated | Station/resolution source and vintage archive feasibility pending |
| PM-S1 | Structured event | Objective timestamped predictors improve explicit event forecasts | v0.1 | IDEA | 0 | Not tested | Not allocated | Select event universe and available historical predictors |
| PM-M1 | Microstructure | Delayed/inconsistent contracts provide executable positive EV | v0.1 | IDEA | 0 | Not tested | Not allocated | Requires synchronized depth, latency and adverse-selection evidence |
| PM-A1 | AI add-on | AI has incremental scoring and trading value beyond statistical baselines | v0.1 | IDEA; optional | 0 | Not tested | Not allocated | No AI subscription/API in baseline |

These are independent interfaces/research branches, not five implemented strategies. `DATA_INVALID` is a data-quality result alongside lifecycle `DATA_CHECK`; it is not an extra successful lifecycle stage.

Allowed lifecycle: IDEA → DATA_CHECK → BACKTEST → VALIDATION → OOS → SHADOW → LIVE_SMALL → PROMOTED; any version can be RETIRED. Code forbids gate skips and live progression in milestone 1.

No version is promoted. Descriptive data-quality observations are recorded in the experiment report and do not become strategy P&L.

## Forward milestone additions (2026-10-01)

| Version | Implemented work | Research status | Evidence / release gates |
|---|---|---|---|
| PM-C1 v0.3.1 / FORWARD-003 | Append-only quotes/fees/depth, deterministic prospective nominations and one-hour-before-close cohort | FROZEN_FORWARD_COLLECTION | No resolved cohort metrics, model validation or OOS trading result; final TEST closed |
| PM-C1 provisional v0.2/001 | First prospective freeze | BLOCKED_PROTOCOL_ERROR | Settlement-time anchor could be after close; retained, no scored outcomes |
| PM-C1 provisional v0.3/002 | Close-time anchor | BLOCKED_INGESTION_TIME_FIELD | Nomination field could predate freeze from cached metadata; retained, zero entries |
| PM-W1 v0.2 | Weather detector/parser, NWS received-vintage/observation archive, empirical TRAIN-error probability and ask-based EV helpers | DATA_CHECK; CONTRACT_ALIGNMENT_BLOCKED | No real fitted error distribution, validated threshold or candidate trade |
| PM-M1 FREE-001 | Public BTC-book/clock/source feasibility probe | DEFERRED_DATA_LIMITATION | Spot endpoints returned unavailable HTML here; Kalshi books accessible, timing/CF benchmark match insufficient |
| PM-A1 | No implementation added | DEFERRED | No AI agent clone/API/subscription |

The recorder is infrastructure, not a promoted trading strategy. Provisional versions were corrected before any cohort scoring; no winning/losing result selected a filter. All old historical and OOS records remain intact. Minimum bankroll, expected monthly trades/return/drawdown/loss probability are not established. No live stage is enabled.

## Lead intake (2026-10-02)

`docs/leads/INSTAGRAM_Dd7M_sLjunh.md`: AWAITING_SOURCE_CONTENT / INSUFFICIENT_INFORMATION. Only an indexed caption mentioning Claude/YouTube income was recovered; full mechanism, economics and independent evidence are missing. No A–E classification, strategy ID, parameter variant, bot or performance trial is assigned. This is a source-intake record, not an additional tested hypothesis.

PM-W1 source-authority review: `reports/PM_W1_SOURCE_ALIGNMENT_2026-10-02.md`. Current generic contract PDF and captured market-specific provider rules conflict. No automatic NWS label substitution, parser/model modification or promotion follows; v0.2 remains blocked.

## 2026-10-03 microstructure data review

PM-M1-DATA-BINANCE-001 reopened data feasibility only. Official public time endpoint returned HTTP451 restricted-location denial; no alternate route attempted. Zero underlying events; clock offset/feed latency unmeasured. Kalshi BTC15M books resolve to CF BRTI, not Binance Futures. PM-M1 remains DEFERRED_DATA_LIMITATION; trading hypothesis and P&L remain unopened. HFTENGINE is an infrastructure research lead, excluded from FundingPips and not evidence of alpha.

## Lead intake (2026-10-08)

| Lead | Source status | Claim status | Candidate / trial | Record |
|---|---|---|---|---|
| Instagram DdTwFSqp3mS | AWAITING_SOURCE_CONTENT | UNVERIFIED; exact claim unknown | None; mechanism and duplication classification pending | [Lead record](leads/INSTAGRAM_DdTwFSqp3mS.md) |

Source-content receipt triggers exact claim extraction, evidence/duplication review and data, point-in-time, execution and small-bankroll feasibility gates before any candidate specification or P&L test. This intake changes no existing strategy, cohort, threshold, collector or dataset. LIVE_TRADING=false; real orders=0. No separate bot or performance trial has been created.

## Shadow orchestration preregistration — 2026-10-12

PM-C1-SHADOW-ORCHESTRATION-001 registers stricter admission, lower-bound after-cost ranking (lexical tie-breaks, at most three positions), unchanged risk ceilings, idempotent OMS integration and confirmed-contribution funding before implementation. See docs/SHADOW_ORCHESTRATION_001.md and the corresponding trial-ledger entry. Software-only verification is excluded from strategy performance. PM-C1-FORWARD-003 and all existing thresholds/models remain frozen; no strategy is promoted and TEST stays closed.
