# Run Prediction Market Alpha

This update continues the transferred project. LIVE_TRADING=false, real orders=0, added paid services=$0. No independently verified edge exists. The default research account has zero cash and no monthly budget.

## Open the console

Windows: install Python 3.11+, extract the ZIP, open `prediction-market-alpha`, and double-click **START_RESEARCH.cmd**. Linux/macOS: run **./START_RESEARCH.sh**. Keep the terminal open. The launcher opens the local console on your computer at http://127.0.0.1:8765 and starts the automated research loop plus the original collector. This is local software; it is not an online deployment or permanent cloud collection service.

On Windows hosts without IANA timezone data:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install tzdata
```

The launcher prefers the project virtual environment when present. Linux verification passed; Windows commands are provided but have not been run on a Windows host.

For offline use with collection stopped, run `START_RESEARCH.cmd --no-collect` on Windows or `./START_RESEARCH.sh --no-collect` on Linux/macOS. Add `--port 8766` if the default port is occupied. Do not terminate an unidentified listener.

## Use the product

The research worker records each stage, its evidence and its rejection reason. Qualified opportunities require supported TRAIN calibration, an independently reviewed hash-bound acceptance policy, exact settlement-source/access review, fresh executable depth, known timestamped fees and verified venue minimums. An empty result displays **NO QUALIFIED OPPORTUNITIES**. It does not invent a forecast or trade. TEST outcomes and performance remain withheld.

Enter your own **monthly amount**, **currency/unit** and **start date**. Save the simulated plan. A due contribution appears for **Confirm simulated deposit**; until confirmed it contributes no spendable cash. No bank/wallet transfer occurs. Repeated saves and confirmations are idempotent. Amount amendments begin next month; unit and original start date remain fixed for an account. Month-end dates clamp to the last day of shorter months and return to the original day afterward. Dates/schedules use UTC.

USD payout markets require USD funds; no currency conversion is assumed. Small balances may be below venue minimums under the unchanged 0.25% normal-position and 1% common-correlation caps. Sizes are floored; no extra risk or borrowing is added. The console separates deposits, other income, withdrawals, available cash, pending/open commitments, realized net P&L, executable unrealized P&L and fees. Fees are already included in realized P&L.

Paper decisions precede execution and reserve cash/exposure. A later independently received, fresh book must satisfy fill-or-kill depth, fees, edge and risk checks. Missing execution books release reservations through an audited cancellation. Settlement requires an explicit binary payout, source hash and valid later timestamps; unknown results remain unresolved. Every financial event is append-only.

**Start collector** refuses another writer or an existing recorder lock. **Clean stop** stops only the collector owned by this console; the research worker can continue offline. **Verify + replay** checks a consistent read-only database snapshot, raw/source hashes and deterministic reconstruction. Close the terminal with Ctrl-C to stop the research worker and its owned collector cleanly. SIGTERM is also handled on Linux.

In this cloud workspace requests to public market/NWS endpoints were denied by the HTTPS proxy. No fresh records were captured. Do not confuse a saved network draft with applied access, a PID with healthy collection, or a ZIP with a running process. The saved environment settings need review/save and Publish before a fresh access check. Requests denied with 401/403/451 stop that host; no restriction bypass is included.

## Commands

From the project folder on Linux/macOS:

```bash
export PYTHONPATH="$PWD/src"
export LIVE_TRADING=false
python3 -m pm_alpha research-loop --once
python3 -m pm_alpha research-status
python3 -m pm_alpha capital status
python3 -m pm_alpha replay-shadow
python3 scripts/check_runtime.py
```

Use `.venv/bin/python` if available. On Windows set `$env:PYTHONPATH = (Join-Path (Get-Location) "src")`, `$env:LIVE_TRADING = "false"`, and substitute `py -3` or `.\.venv\Scripts\python.exe` for `python3`.

CLI funding uses explicit values supplied by you:

```text
python3 -m pm_alpha capital plan --amount YOUR_AMOUNT --unit YOUR_UNIT --start-date YYYY-MM-DD
python3 -m pm_alpha capital confirm --period YYYY-MM --reference YOUR_SIMULATED_REFERENCE
python3 -m pm_alpha capital event --kind withdrawal --amount YOUR_AMOUNT --reference YOUR_REFERENCE
python3 -m pm_alpha capital event --kind other_income --amount YOUR_AMOUNT --reference YOUR_REFERENCE
```

Placeholders must be replaced; no amount shown here is a recommended budget. All actions are simulated. Withdrawals cannot reuse pending commitments. Operational locks serialize funding and research writes.

## Verification and technical demonstration

Install the existing pinned free development dependencies, then run:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pytest
PYTHONPATH=src .venv/bin/python scripts/check_runtime.py
PYTHONPATH=src .venv/bin/python -m pm_alpha technical-demo --output /tmp/alpha-demo-new
```

The demonstration output must be a new directory. It copies config/source into an isolated, explicitly labeled fixture and exercises contributions → research/selection → later-book fill → explicit settlement → raw and financial replay. Its invented training records, approval evidence and P&L prove software behavior only. Production research refuses fixture projects. Do not combine fixture ledgers with `data/forward.sqlite` or `data/shadow.sqlite`.

The historical real validation sample is absent; its regression test remains an honest skip. The original offline `research` command cannot run successfully without an admissible historical dataset. No substitute is fabricated.

## Preserve data and recover safely

Never replace a newer destination database with this ZIP. Keep both current and historical-release SQLite databases, raw files, source archives, frozen files and ledgers. Use SQLite online backup from a read-only transaction; do not copy an active database without its committed state. Archive/export code must exclude transient locks and WAL/SHM files only after taking consistent snapshots.

Inspect `data/recorder.lock`, `data/automation.lock` and `data/research.lock` ownership before starting another controller or removing a lock. A research lock is normally brief; automation lock belongs to the continuous worker. On Windows, inspect a PID with `Get-CimInstance Win32_Process -Filter "ProcessId = PID"`; on Linux inspect `ps` command, executable and project directory. A reused PID is not ownership. Remove only a demonstrably stale control lock; never delete SQLite data, raw evidence or frozen files. Do not kill an unrelated process.

The frozen PM-C1 collection/evaluation schedule and exclusions remain unchanged. The existing collector freezes the original TRAIN model only after its 200 admissible resolved observations. The bridge replays that model from original TRAIN pairs and hashes before using it. Independent acceptance evidence must be immutable and match policy references; boolean flags alone cannot qualify. Exact source reviews require matching archived document/source files and hashes. No automatic threshold tuning, TEST opening or live promotion occurs.

Current PM-W1 settlement-source alignment remains blocked; PM-M1 data feasibility remains deferred without a Binance retry. The Instagram lead remains awaiting source content. No credentials, paid hosting, signing or real execution are implemented; the original live adapter still refuses orders.
