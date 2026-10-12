# Capture continuity: observed runtime limitation

The collector can run in the active execution session, but this workspace has repeatedly ended its processes between sessions. A saved PID is not proof of continued collection: the sandbox can reuse that PID. Confirm a matching capture command **and** fresh, increasing append-only records.

On 2026-10-04, observed heartbeat-to-resume gaps were 46,137.788 seconds (12h 48m 58s) and 6,023.678 seconds (1h 40m 24s). Both were appended as `collector_runtime_gap`; no books were backfilled. The first gap covered two frozen 04:00 UTC observation windows. Those markets were correctly excluded under `NO_VALID_BOOK_IN_FROZEN_OBSERVATION_WINDOW`. Do not retarget or invent observations.

Continuous overnight capture needs the **existing unchanged collector** on an already available computer/process host that stays awake with internet access. No paid VPS or new service is authorized. This is an operational requirement, not a new strategy. Keep a single writer for each database; preserve the repository, source archives, SQLite ledger and raw-data directory together.

From the existing repository root, with its current configuration and Python:

```bash
PYTHONPATH=src python -m pm_alpha collector-health
PYTHONPATH=src python -m pm_alpha collect-forward
```

PowerShell uses the same program:

```powershell
$env:PYTHONPATH = "src"
python -m pm_alpha collect-forward
```

Do not start a second writer on the same database. Do not remove a lock belonging to an actual running recorder. After a stopped host, verify no matching process, preserve the stale lock, record the gap, and resume this database; do not initialize a replacement dataset. The resumed program continues the existing cohorts.

Verify periodically from a separate shell:

```bash
PYTHONPATH=src python -m pm_alpha collector-health
PYTHONPATH=src python -m pm_alpha verify-forward
```

Check fresh heartbeat, increasing snapshot records, per-market staleness, audit integrity, raw hashes, source failures and cadence warnings. A nominal 30-second configuration is not an achieved-cadence claim. Collection gaps and serial public-request delays remain evidence limitations.

As of the audited 2026-10-04 checkpoint, the two remaining current nominations have observation targets at **2026-10-05 04:00 UTC / 09:30 India time**. This is a captured schedule, not permission to change the frozen window or eligibility. Keep the host awake through the complete existing window. PM-C1-FORWARD-003, TEST lock, eligibility and LIVE_TRADING=false remain unchanged. No order execution is available.
