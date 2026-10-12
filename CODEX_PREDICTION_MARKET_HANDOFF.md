# Prediction Market Alpha — Codex continuation handoff

Prepared 2026-10-11. Scope: prediction markets only.

## Start here

Open your existing prediction-market-alpha folder in Codex. If the project is not on your PC, extract PREDICTION_MARKET_ALPHA_RESEARCH_DESKTOP_20261008.zip first and open its prediction-market-alpha folder.

Do not extract the archived database over a newer local dataset. A newer PC checkpoint takes precedence; verify it rather than replacing it. Place this handoff in the selected project folder and give Codex the prompt below. It supplements the existing AGENTS.md; it does not replace it.

## Prompt to give Codex

Continue this existing Prediction Market Alpha repository. Work on prediction markets only. Do not scaffold another project, rewrite working components, or touch YouTube, FundingPips, ORB or HFT.

Read AGENTS.md, README.md, QUICKSTART.md, PRODUCT_RELEASE.json, config/forward.toml, docs/STRATEGY_REGISTRY.md, docs/TRIAL_LEDGER.json, docs/COST_LEDGER.md and the frozen PM-C1-FORWARD-003 protocol before editing. Determine the actual local state rather than treating archived counts or timestamps as current.

The immediate objective is a reliably operating research product on this PC and an accurate explanation of what prevents valid strategy evaluation. Deliver runnable changes and verification where needed. Do not stop with a plan.

### Non-negotiable boundaries

- LIVE_TRADING=false; real orders=0. Preserve the unavailable live execution boundary. Do not add wallet/signing/order-placement code.
- Incremental spend=$0. No paid APIs, data, hosting, proxies, subscriptions or additional usage purchases.
- Preserve PM-C1-FORWARD-003, its frozen hash, thresholds, risk limits, eligibility, enrollment window and split rules. TEST remains unopened.
- Preserve existing audit rows, raw data, source archives, locked exclusions and outcome ledgers. Collection is append-only. Never backfill missed snapshots.
- Do not infer alpha from data counts. No independently verified positive expectancy exists.
- Do not weaken prerequisites to manufacture eligible samples or a backtest.
- Public-data access only. Stop on blocked access; no geographic or anti-bot circumvention.
- Preserve all unrelated files and uncommitted changes. Inspect Git status if Git exists; do not assume this archive contains Git history. Do not reset, force-push or overwrite user data.

### Execute in this order

1. Establish a safe baseline.
   Identify the project root, Python environment, source version, current UTC time, frozen file hash, database state and existing collector process. Make a consistent SQLite backup and source/config hash inventory without copying a live database unsafely. If another collector is running, preserve it and do not start a duplicate writer. A PID or stale lock alone is not evidence of an active collector.

2. Verify the real Windows runtime.
   Run the existing START_RESEARCH.cmd path on Windows. Confirm the local console, status API and verification workflow. Exercise actual start/clean-stop semantics on an isolated copy if a real collector is already running. Fix demonstrated launch/runtime defects with bounded changes; do not replace the collector or strategy logic. Keep the loopback service local. Do not change OS security settings or require administrator privileges.

3. Keep original collection running on this PC.
   Use the existing desktop/collector controls after verifying writer ownership and all guards. Confirm fresh records from actual successful requests. Report collection gaps, rejected inputs and source errors explicitly. Do not silently remove recorder.lock; establish that its owner is gone and no other writer exists first. Do not promise continuous collection if the PC sleeps, the app closes or the process is absent. Leave an already healthy collector running.

4. Verify integrity.
   Run audit, raw-message/source hash checks and deterministic book/forecast replay against a consistent read-only snapshot. Report the exact as-of timestamp and issues. Preserve frozen-file and database/cohort agreement. Use existing commands and tests before inventing parallel tooling.

5. Diagnose PM-C1 readiness without observing protected performance.
   Determine, from permitted metadata and the original recorded eligibility decisions, why nominations have not produced eligible/resolved TRAIN entries. Report each reason and relevant prospective timing/coverage requirement. Distinguish unripe markets from missing snapshots, invalid inputs and locked exclusions. Do not inspect TEST outcomes/performance or change rules to repair research gaps. If a genuine software defect is found, document its affected records and contamination; never retroactively relabel them admissible or rewrite decisions.

6. Make only useful product improvements.
   Fix concrete operational or data-integrity defects found above. Add focused regression tests where justified. Avoid another dashboard redesign, new strategy family or lengthy report as a substitute for functioning collection. Maintain the existing adapter/model/risk/OMS/research boundaries. Preserve minimum-cost, executable-price and point-in-time safeguards.

7. Resume research only when its gate is satisfied.
   PM-C1: wait for the preregistered eligible resolved TRAIN sample, then execute the frozen evaluation exactly as specified. Do not lower the 200-TRAIN requirement.
   PM-W1: inspect exact official settlement-source alignment only through lawful free access. Never substitute NWS or another provider for a different contractual source. If no reproducible source exists, retain SOURCE_BLOCKED.
   PM-M1: retain DEFERRED_DATA_LIMITATION. Do not retry the blocked Binance HTTP-451 route, reopen completed HFTENGINE research, optimize retail market making or build HFT execution.
   Instagram: DdTwFSqp3mS and other inaccessible leads remain AWAITING_SOURCE_CONTENT. Do not infer their mechanisms or repeatedly poll inaccessible posts. Triage only when actual legitimate source content arrives.
   Any genuinely new model/threshold/filter requires strategy versioning, a trial-ledger entry and a preregistered test before examining profitability. No live promotion in this task.

8. Validate and leave a concrete checkpoint.
   Run python -m pytest from the project root with its source environment configured. Run relevant integrity/replay/runtime checks after changes. Report failures and skips honestly. Do not fabricate the absent real historical validation dataset or replace it with synthetic data to make a regression pass.
   Update the cost ledger for additions. Record changed files, checks, current as-of counts, cohort maturity, gaps, process state and the next actual research gate in one concise report. Keep prior reports as history.

Your first response should establish the inspected local state and proceed with execution. Ask only for indispensable missing access or information. Do not request permission for ordinary reversible fixes already authorized above. Do not claim the system is profitable or finished as a live income engine. A running research product and a validated trading edge are separate milestones.

## Last verified packaged checkpoint — historical reference

This is the release state verified at 2026-10-08T11:19:05Z, not a claim about collection on 2026-10-11.

| Item | Packaged state |
|---|---|
| Product version | 0.1.1, local research desktop |
| Market books | 841 |
| Forecasts | 232 |
| Station observations | 26 |
| Settlement records | 62 |
| Raw hashes / source archives | 1,141 / 14; checks passed |
| Replay | 841 books and 232 forecasts reproduced |
| PM-C1 nominations | 10 |
| Eligible / resolved TRAIN | 0 / 0 |
| Locked exclusions | 8 |
| TEST | Unopened |
| PM-W1 | SOURCE_BLOCKED |
| PM-M1 | DEFERRED_DATA_LIMITATION |
| Tests | 207 passed, 1 skipped |
| Windows-host startup test | Not yet performed |
| Build collector at packaging | STOPPED_CLEANLY |
| Live trading / real orders | false / 0 |
| Verified edge | NONE |
| Incremental spend | $0 |

Frozen file: data/cohorts/PM-C1-FORWARD-003.json

SHA256: cc9f69d812d99b80d120c1e63a54287d85dc776bb0645c57f2e5899a5830e3d0

Release ZIP SHA256: 66fdb66ce11fbf7296626a637768ccf1fea007b42fa55b4e5835349dcf9d2351

The documented test skip needs data/processed/kalshi_validation.json, a real historical validation sample absent from this checkpoint. Do not blindly run the offline research command assuming that file exists.

## Existing launch and checks

Windows: open START_RESEARCH.cmd, then use Start collector and Verify + replay. Keep the terminal open and PC awake.

Terminal alternative, from the project root in PowerShell:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
py -3 -m pm_alpha desktop --open-browser
```

Use the existing virtual environment instead of py if appropriate. Python 3.11+ and America/New_York timezone data are required; QUICKSTART.md documents the free tzdata fallback.

Existing independent commands:

```text
python -m pm_alpha verify-forward
python -m pm_alpha collector-health
python -m pytest
```

Read the legacy health output together with record freshness and verified process ownership. No archived health report proves a process is currently running.



## 2026-10-12 continuation update

The provided transfer was continued. See PROGRESS_20261012.md, START_HERE.md, CONTINUATION_RELEASE.json and reports/CONTINUATION_20261012.md for the implemented research/shadow/contribution/settlement workflow and current verification. Earlier statements about unimplemented integration are historical. Frozen research and all original audit rows remain preserved; TEST is unopened. Real result remains NO QUALIFIED OPPORTUNITIES. Public collection is proxy-blocked; a single offline research worker runs in this temporary cloud session. No claimed edge or deployment, no paid service and no real orders. New labeled fixtures establish software behavior only.
