> Updated 2026-10-12: start with [START_HERE.md](START_HERE.md). The existing project now includes the audited research loop and simulated monthly funding workflow. Earlier release metadata below remains historical.

# Prediction-Market Alpha System

Milestone 1 plus the forward/weather milestone: a zero-subscription-cost local Python research repository. **No verified trading edge or income is established. LIVE_TRADING=false; live execution is unavailable.**

## Open the local research product

On Windows, double-click **START_RESEARCH.cmd**, then press **Start collector** in the local console. See [QUICKSTART.md](QUICKSTART.md) for setup, controls, verification and safe lock recovery. The console preserves the current database and PM-C1-FORWARD-003, shows fresh/stale collection and TRAIN maturity, and runs read-only audit/raw replay. It has no trade endpoint or automatic TEST opening.

Start with [reports/MILESTONE_1.md](reports/MILESTONE_1.md) and [reports/PM_C1_v001.md](reports/PM_C1_v001.md). All real downloaded data stays distinct from synthetic unit-test fixtures.

New collection protocol: [docs/FORWARD_DATA_PROTOCOL.md](docs/FORWARD_DATA_PROTOCOL.md), [docs/PM_C1_FORWARD_PROTOCOL.md](docs/PM_C1_FORWARD_PROTOCOL.md), [docs/PM_W1_SPEC.md](docs/PM_W1_SPEC.md). The original historical reports are preserved; do not rerun download/research commands over them to manufacture trades.

## Start continuous forward collection locally

After the setup below, check timezone data, then run:

```powershell
.\.venv\Scripts\python.exe -c "from zoneinfo import ZoneInfo; print(ZoneInfo('America/New_York'))"
# If IANA data is absent on Windows, install the free CPython data package:
.\.venv\Scripts\python.exe -m pip install tzdata
.\.venv\Scripts\python.exe -m pm_alpha freeze-forward
.\.venv\Scripts\python.exe -u -m pm_alpha collect-forward
```

The loop stays in that terminal; keep the computer awake. Ctrl-C stops cleanly. In a second terminal:

```powershell
.\.venv\Scripts\python.exe -m pm_alpha collector-health
.\.venv\Scripts\python.exe -m pm_alpha forward-report
.\.venv\Scripts\python.exe -m pm_alpha verify-forward
# Request a clean stop (remove this file before the next run):
New-Item data\STOP_COLLECTOR -ItemType File -Force
```

`scripts/start_forward.ps1` and `scripts/stop_forward.ps1` wrap these actions. Bounded smoke run: `collect-forward --cycles 1`; longer pilot: `collect-forward --seconds 900`. Configuration: `config/forward.toml`. The archive includes the original UTC-frozen cohort; do not alter/delete its ledger to create an apparently fresh test. If starting after its observation/enrollment dates, preserve it and register a new prospective version. A session pilot does not provide ongoing collection on your computer or cloud after the chat ends.

Daily derived views are in `reports/forward/YYYY-MM-DD.md`/JSON. Quotes and weather vintages are collected, final results are reconciled, unknown costs stay unknown. Weather contract matching/training is blocked pending exact final-source rules and enough valid independent pairs. No forecast/error distribution, trade rate, income or bankroll-return estimate is invented.

## Windows setup

Install Python 3.11 or newer. Extract the supplied archive, open PowerShell inside `prediction-market-alpha`, then run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pm_alpha research
.\.venv\Scripts\python.exe -m pm_alpha audit
```

Activation is unnecessary. No PowerShell execution-policy change is required for these commands. Setup needs internet to obtain free packaging/test tools; scoring the bundled sample needs no network. On Linux/macOS replace the Python path with `.venv/bin/python`.

The forward release includes `prediction-market-alpha-forward.bundle` with committed history/data. To retain Git history, use `git clone .\prediction-market-alpha-forward.bundle ..\pm-alpha-checkout` from the extracted project folder, then work inside that checkout. The pinned development versions are in `requirements-dev.lock`; runtime collection can also run directly with `PYTHONPATH=src` without package installation.

## Collect new public data

```powershell
.\.venv\Scripts\python.exe -m pm_alpha download --platform polymarket --limit 10
.\.venv\Scripts\python.exe -m pm_alpha download --platform polymarket --limit 10 --since 2026-01-01T00:00:00Z
.\.venv\Scripts\python.exe -m pm_alpha download --platform kalshi --limit 100
.\.venv\Scripts\python.exe -m pm_alpha research --dataset data/processed/kalshi_validation.json
.\.venv\Scripts\python.exe -m pm_alpha shadow-once --limit 10
.\.venv\Scripts\python.exe -m pm_alpha daily-report
```

Initial Polymarket probes returned HTTP 403/Cloudflare 1010 on October 1, 2026. Later ordinary public-client calls succeeded; access is intermittent, not a continuing universal block. The client stops on access restrictions. There is no browser automation, VPN, proxy, credential flow or restriction bypass. A blocked request creates a blocker entry; it does not create fake observations.

Kalshi is an explicit validation fallback, not interchangeable evidence about Polymarket. Its candle history lacks verified original publication times and depth. Downloaded rows retain those missing fields. **Strict PM-C1 rejects them before simulated trading.** A separate calibration diagnostic is descriptive only and cannot prove an edge. Outcomes inspected in it are logged so they cannot later be called untouched OOS.

`shadow-once` obtains public live book snapshots and records decisions before resolution. The first research model is unvalidated, and fees are deliberately not guessed; therefore the shipped command records skips. The reusable paper OMS supports later-book, visible-depth FOK simulations and settlements, tested offline. Connecting a validated model, verified time-specific fees, and automatic settlement reconciliation is remaining work; no pretend filled shadow track record is shipped.

## Frozen test sets

Only after valid data, a completed pre-registration, and training/validation:

```powershell
.\.venv\Scripts\python.exe -m pm_alpha freeze --dataset data/processed/valid_cohort.json --output reports/PM_C1_v001_freeze.json
.\.venv\Scripts\python.exe -m pm_alpha research --dataset data/processed/valid_cohort.json --freeze reports/PM_C1_v001_freeze.json
```

The freeze binds dataset, config and trained-model hashes. A second open is refused. Editing strategy thresholds requires a new registered version and fresh future holdout. Inspecting or deleting the ledger manually does not restore untouched status.

## Scope and next milestones

- PM-C1 baseline: bin calibration, raw-market baseline, forecast metrics, event-grouped purged splits, cost-aware YES-only settlement backtest, immutable OOS exposure ledger.
- Risk/execution: 0.25% normal loss cap; 0.50% immutable ceiling; 1% combined correlated cap; sizing always floors and can return zero.
- Audit: content-addressed raw downloads, UTC timestamps, SQLite append-only triggers, hash chain, decision/fill/settlement records, daily reports.
- Statistics: event-cluster bootstrap, Benjamini–Hochberg adjustment helper, conditional 10,000-path block Monte Carlo.
- PM-W1: strict detector/parser, NWS received-vintage archive, TRAIN-only empirical-error probability/EV baseline, still blocked for live contract matching/validated training. PM-M1: limited free-data probe; DEFERRED_DATA_LIMITATION. PM-S1 remains an idea; PM-A1 stays deferred with no AI dependency.

Read `docs/ARCHITECTURE.md`, `docs/DATA_SOURCES.md`, `docs/RESEARCH_RULES.md`, `docs/RISK_POLICY.md`, `docs/COST_LEDGER.md`, and `docs/BLOCKERS.md`. Existing THEER and XAUUSD/FundingPips projects were not modified. No correlation or combined-income benefit with XAUUSD has been demonstrated.
