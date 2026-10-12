# Codex task — automated prediction-market research and selection
User objective: an income system funded by a configurable recurring monthly contribution. Build the research and shadow product first; profitability is unproven.

## Execution instruction
Continue this extracted repository now. Read AGENTS.md, CODEX_PREDICTION_MARKET_HANDOFF.md, PROGRESS_20261011.md, QUICKSTART.md, existing registries and configuration.

Locate files relative to this extracted project. The old chat's absolute filesystem paths do not apply. Do not work on the earlier demo. Do not restart or rewrite working components. No YouTube, FundingPips, ORB or HFT work.

Inspect, implement useful missing functions, run checks and deliver runnable changes. Do not stop at a research plan. Preserve newer local state if present.

## Hard boundaries
LIVE_TRADING=false. REAL ORDERS=0. Incremental spend=$0.
Preserve frozen PM-C1-FORWARD-003, thresholds, risk ceilings, enrollment, splits, historical decisions and raw evidence. TEST stays unopened. No backfills, outcome-based tuning, retroactive eligibility, paid APIs or blocked-access circumvention.
Public adapters stay GET-only. No wallet, credentials, live execution or automatic transfer of real money.

## First milestone: operate the actual existing project
- Identify runtime, database, frozen hash, current collector ownership and record freshness.
- Back up SQLite consistently and inventory source/config hashes.
- Do not start a duplicate writer or remove an unverified lock.
- Exercise the existing launcher and local HTTP/API path in the actual environment; distinguish Linux checks from Windows-host checks.
- Run verify-forward, deterministic replay and pytest with src importable.
- Fix observed operational defects, with focused tests. Preserve original collection rules.
- Keep successful original collection running where a persistent local process is available. Report failures/gaps rather than claiming permanent collection in a temporary session.

## Second milestone: close the automated research-loop gaps
Map existing implementations before adding anything:
market discovery → eligibility → evidence → probability → costs/executable prices → selection/risk → shadow execution → settlement → evaluation/reporting.

For each missing link implement a small compatible component, with recorded reasons and auditable provenance. Demonstrate the complete flow. Preserve adapter/model/risk/OMS/research separation.

### Eligibility and data
Require clear contractual settlement rules, authoritative reproducible source, lawful access, point-in-time inputs, executable depth, known fees/minimum order sizes and acceptable capital lock-up.
Record EVENT_TIME, AVAILABLE_TIME and INGESTED_TIME for external features.
Missing availability or ambiguous settlement means invalid/blocked, not guessed.
Do not use final probabilities, future information or revised historical data as available-at-entry evidence.

### Probability and selection
Use reproducible, supported estimates with strategy version, inputs, timestamps and uncertainty.
A high win probability is not the selection criterion. A likely winner may be overpriced.
Require independently validated positive after-cost expectancy under executable bid/ask, depth, fees and slippage; uncertainty must be considered.
No trade when no strategy/market qualifies. Do not invent a forecast or lower gates to fill an empty screen.
Preregister any new selection/model/filter rule and track every trial before inspecting its P&L.

### Monthly contribution shadow ledger
Implement configurable amount, currency/unit and start date without assuming a budget.
Simulate recurring contributions; do not transfer money.
Distinguish scheduled contributions from confirmed deposited funds.
Only confirmed funds are available for allocation.
Separate deposits, withdrawals, realized trading P&L, unrealized P&L, fees, available cash, committed capital and other income.
Never count deposits as profit.
Ensure repeated runs/recovery cannot post the same contribution or shadow decision twice.
Respect existing risk ceilings, correlated exposures and floor sizing. No leverage, borrowing, martingale or increased risk for a small bankroll.

### Shadow and settlement
Reuse existing paper OMS and risk engine.
Audit decisions before outcomes. Never rewrite historic signals.
Use executable prices/depth rather than midpoint fills.
Do not treat synthetic fixture P&L as strategy evidence.
Reconcile explicit binary settlement results and timestamps; unclear results remain unresolved.
Show cash/capital lock-up and cost accounting coherently.

### Research gates
Diagnose PM-C1 nomination/eligibility/maturity from allowed metadata and recorded decisions; no protected outcome/performance inspection.
Do not redesign the cohort because its valid TRAIN has not matured. Execute frozen evaluation only when prerequisites hold.
PM-W1 remains blocked unless legitimate exact-source alignment succeeds.
PM-M1 remains deferred; no Binance restriction retry or completed HFT reopening.
Inaccessible Instagram leads consume no research time until source content is supplied.
Genuinely new mechanisms need duplication/economics/data gates, registry/version/trial entries, preregistration, chronological TRAIN/VALIDATION/untouched TEST, robustness and prospective shadow evidence.
Do not optimize endless candidates or automatically promote the least-bad loser.
All hard acceptance gates must pass independently.

### Reliability and reporting
Single writer, bounded retry/rate limits, clean shutdown, duplicate prevention, freshness checks, recorded gaps, replay and consistent backups.
No paid hosting or LLM API dependency.
Show collector health, data blockers, qualified opportunities or NO QUALIFIED OPPORTUNITIES, supported probabilities/uncertainty, costs, shadow cash/exposure, settled P&L and research gate status.
Reuse the existing UI; avoid cosmetic rewrites.

## Completion evidence
Deliver working code plus one clear launcher, tests, an end-to-end technical demonstration, operating instructions and exact unresolved data/research gates.
Use labeled fixtures only for technical tests and admissible real data for strategy claims.
Report changed files, as-of counts, actual process state, integrity/replay, tests/skips, costs and next action.
The missing real historical validation dataset remains an honest skip/blocker.

Do not call this a profitable income engine unless real independent research supports that conclusion.
No qualified edge is a valid result. Finish the research product and leave shadow trading allocation at zero in that case.

