# PM-C1 prospective calibration — v0.3.1

Active definition: `data/cohorts/PM-C1-FORWARD-003.json`, also frozen in the audit ledger. It must exist before any eligible cohort observation/outcome. Inclusion thresholds are prospective engineering choices, not discovered edges. No final TEST has opened.

The initial 001 definition used one hour before expected settlement. Some contracts settle many hours after closing; that definition could target a nontradable time and was retired without scored cohort outcomes. Provisional 002 corrected the close anchor but reused metadata availability for nomination time, which could predate its freeze; it was retired without entries. Both original definitions, hashes and retirement reasons remain append-only. Version 003 fixes nomination timestamps and archives source. Spread, volume, probability and risk rules were not optimized against winners/losers.

## Frozen selection

- Enroll new prospective events for 30 days from the freeze. Future cohorts need separate freezes; do not extend this one retrospectively.
- Binary, objective contracts with explicit rules/source and observable close/expected settlement. Exclude composites, subjective/ambiguous, unknown dates/sources, inactive markets and weak books.
- Fixed listing prefilter: volume >=100 in each venue's units; positive displayed bid; ask <1; spread <=0.10.
- Choose the lexically first prefiltered contract per platform/event before requesting its book. Siblings remain one event. Nomination occurs before the target; discovering an event after the target cannot create a retrospective entry.
- Fixed observation: first completed capture at/after **one hour before the nominated close time**, within 180 seconds. Actual receipt is the entry time; never backdate it to the target. Expected resolution remains a separate field. A date/rule change can exclude an entry; it never moves the target to a better price.
- Snapshot filters: at least five ask shares within one cent, maximum ten-cent spread, minimum volume, allowed category, open status, reasonable horizon and valid timestamps. The first observation locks an exclusion as well as a success. Failed book/window entries are explicitly expired; no repeated search for a more favorable price.
- Twenty fixed buckets: [0%,5%), [5%,10%), …, [95%,100%]. 100% belongs in the last bucket.

Near-close weather probabilities are nowcast observations, not necessarily useful full-day weather forecasts. Disclose this horizon; do not infer independent forecast skill or arbitrage from almost-known events. The 15-minute crypto series cannot enter a one-hour-before-close cohort because it opens too late; its captured books are feasibility data only.

## Learning and scoring

Chronological event enrollment allocates first 200 eligible events to TRAIN, next 100 to VALIDATION and next 200 to TEST. Event counts are requirements, not evidence that 500 independent events will be available within this bounded first month. The watchlist may be too small; record insufficiency instead of lowering sample requirements. Exclusions do not become replacement winners selected retrospectively.

TRAIN-only daily diagnostics report empirical frequency by bucket, Brier, log loss, ECE, sharpness and the reliability curve once labels exist. Market midpoint is the forecast baseline; ask is separately recorded for executable comparisons. TEST outcomes remain withheld from metric reports even though immutable raw settlements are owned by the user. Directly inspecting TEST records contaminates them; do not relabel exposed data untouched.

The registered baseline is the existing 20-bin calibration with prior strength 20 toward quoted probability. Its training freeze requires 200 resolved TRAIN labels actually received before freezing, with settlement after entry. Only later prospective VALIDATION observations can receive that frozen model. Early validation observations lacking a timely model cannot be backfilled with a future model. Market and model probabilities must be logged before outcomes. This release does not automatically unlock a final TEST policy; it remains closed until a separately reviewed hash-bound model/cost/threshold freeze is implemented with adequate prospective validation.

Compare forecasting improvement separately from actual hypothetical after-cost expectancy. Ask, fee vintage/bound, depth, later independent fill evidence, latency/slippage and reserved capital are required for trading evaluation. Unknown costs block it. A better Brier score alone does not establish tradable edge.

The registered threshold grid is 0, 1, 2 and 4 cents of **net expected value per payout**, for future TRAIN/VALIDATION research only. No threshold is chosen, no 8% viral rule is adopted, and no income, bankroll-return, Monte Carlo survival or drawdown estimate is justified now. Any model/filter/grid change requires a new registry/trial version before future TEST use. Existing Milestone 1 OOS and exposure controls remain unchanged.
