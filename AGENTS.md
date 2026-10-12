# Agent instructions

- This is research to discover after-cost prediction-market edge; no successful strategy is established.
- Baseline runtime must remain Python standard library + SQLite; no paid services or silently added costs. Update `docs/COST_LEDGER.md` for every addition.
- Never turn final displayed prices into forecasts or resolution labels. Require explicit final binary payouts/results and timestamps.
- Every input has event/availability/ingestion times. Unknown historical availability is `DATA_INVALID`, never guessed. Current rules/fees must not be backdated.
- Public adapters use GET only. Stop on 401/403. Do not add anti-bot/geographic circumvention.
- Live-money execution is deliberately unavailable even if an environment variable says true; preserve this milestone boundary.
- Risk caps are code ceilings: normal 0.25%, hard 0.50%, correlated 1%. Until independence is validated, all markets share one risk group. Never round a position up.
- Audit decisions precede resolution. Append new fills/settlements; never update/delete signals. Preserve both SQLite ledgers and raw hashes.
- Event siblings stay together in chronological splits. Purge labels unavailable at the next split boundary.
- TEST is inaccessible to report metrics before hash-bound freeze. Diagnostic-inspected events are contaminated for OOS. Never reset ledgers to relabel them untouched.
- Any changed threshold/model/filter creates a version in `docs/STRATEGY_REGISTRY.md` and a trial entry in `docs/TRIAL_LEDGER.json`.
- Human reports belong in `reports/`; idealized simulations and synthetic fixtures must be explicit. No screenshot/viral profits enter performance history.
- Adapters normalize data; models forecast; risk sizes; OMS audits/fills; research scores and reports. Keep those boundaries.
- Run `python -m pytest` from the repo root; `python -m pm_alpha research` replays the bundled real validation sample offline.
