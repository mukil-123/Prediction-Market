# Prediction Market Alpha — research desktop release 001

Version **0.1.1**, 2026-10-08. **LOCAL_RESEARCH_PRODUCT_READY**. Continued the current repository. This release includes runnable software, its source, collected data and independent verification artifacts. No YouTube code or work is included.

## Product delivered

A local research console with original responsive HTML/CSS/JavaScript, served by Python's standard-library HTTP server. Open **START_RESEARCH.cmd** on Windows, then press **Start collector**. It starts the existing public-data collector with its original rules. Keep the app terminal and PC awake. [QUICKSTART.md](../QUICKSTART.md) contains exact startup, timezone setup and safe lock instructions.

The app shows book/forecast/observation/settlement counts, latest YES/NO bid/ask and age, frozen cohort maturity, exclusions, data rejections, source blockers and the awaiting-source Instagram lead. Start/clean-stop controls manage only the app's own child process. It refuses duplicate writers, an existing lock, a changed frozen file, missing/mismatched cohort/database, invalid audit or live-trading configuration. Closing with Ctrl-C requests a safe stop; it does not force-kill an in-flight capture.

Verification checks audit/raw/source archives and reconstructs books/forecasts against a single consistent read-only SQLite transaction. GET/status never opens TRAIN/VALIDATION/TEST performance. TEST outcomes are withheld, and no endpoint opens TEST, changes risk/thresholds, modifies cohort rules, executes arbitrary commands or places orders. Operational actions/results are appended to the app log.

The service binds only 127.0.0.1. Collector controls require the local Host, Origin and a per-session nonce. No CORS grant, credentials, wallet, paid API, cloud hosting or trading endpoint was added. Installed-package testing confirms all UI assets ship in the wheel.

## Current real-data checkpoint

At the final check, **841 books, 232 forecasts, 26 station observations and 62 settlement records**. **1141 raw hashes and 14 source archives** pass integrity verification. All 841 books and 232 forecasts replay exactly. Source files/archive hashes are preserved. The build collector stopped cleanly before packaging, and the shipped SQLite data is a consistent backup.

Every one of the earlier checkpoint's **4,028 audit rows** was compared and preserved byte-for-byte. Collection appended new records prospectively; no missed snapshot was backfilled. The previous chat process was absent with a stale control lock; its PID absence and lock recovery were documented. Gaps between chat sessions remain real. Permanent collection requires running the delivered app on the user's always-on PC.

## Frozen research preserved

PM-C1-FORWARD-003 file SHA256: `cc9f69d812d99b80d120c1e63a54287d85dc776bb0645c57f2e5899a5830e3d0`. **10 nominations; 0 eligible TRAIN; 0 resolved TRAIN; 8 locked exclusions. TEST unopened.** No calibration model or after-cost result is available. The collector, cohort rules, thresholds, risk, cost engine, paper OMS, weather logic and all configurations were checked unchanged against the prior checkpoint. The desktop release is a product/version update, not a new optimized strategy or performance trial.

PM-W1 remains SOURCE_BLOCKED: station observations/NWS forecasts are not substitute settlement labels. PM-M1 remains DEFERRED_DATA_LIMITATION; HFT/Binance restriction work was not reopened. DdTwFSqp3mS remains AWAITING_SOURCE_CONTENT / UNVERIFIED. No source-content inference or new strategy family.

## Validation

**207 tests passed, 1 skipped**. The skipped regression needs the historical real validation sample absent from the saved source checkpoint; no replacement dataset or fabricated result was created. New cases cover read-only access, missing/tampered frozen data, live-configuration refusal, stale/reused-PID health, unconfirmed external processes, duplicate writers, owned stop controls, Host/Origin/nonce enforcement, absent trade/arbitrary-file routes and verification jobs.

Real-data HTTP smoke: dashboard and status API returned HTTP200, verification/replay passed, frozen cohort intact and no TEST data/real orders exposed. JavaScript syntax checked. A source wheel built successfully and its UI assets were verified from an isolated package extraction. The app's actual Windows launcher/browser path still needs execution on the user's PC; this environment's tests ran on Linux. Software checks do not establish alpha.

## Cost and boundaries

**$0 incremental spend; $0/month added services. LIVE_TRADING=false; REAL ORDERS=0; verified edge=NONE.** Existing hardware, network, electricity and human research time are assumptions, not proof of zero economic cost. No income, return, win rate, drawdown distribution or strategy capacity is forecast.

## Next action

Extract the release, open `prediction-market-alpha`, double-click **START_RESEARCH.cmd**, then press **Start collector** and **Verify + replay**. Leave the existing frozen experiment collecting on the always-on PC. Eligible resolved TRAIN must mature under the original rules before its preregistered evaluation can run. The research product is runnable now; a profitable/live strategy has not been established.
