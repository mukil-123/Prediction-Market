# Forward data protocol — collector v0.3.1

This continues Milestone 1. Historical DATA_INVALID samples and their reports remain unchanged. Collection is prospective, append-only and paper-only. No live adapter is enabled, irrespective of environment variables.

## Records and availability

`data/forward.sqlite` is a separate append-only hash-chain ledger. `forward_metadata` holds deduplicated immutable versions of question, event, category, rules, source, open/close/expected-resolution times, size constraints and current status. Every `market_snapshot` references its exact metadata key. A join retrieves these fields without repeating long rules in every snapshot. Changed rules create a new version, never an UPDATE.

Snapshots contain UTC capture time, YES and NO best bid/ask, midpoint, spread, five levels on each side, last reported trade and separately reported quote where supplied, volume, liquidity or explicit null, size constraints, current fee parameters and quality, raw hashes, endpoint, receipt provenance, source times if supplied, and execution limitations. Full requested depth (up to 100 Kalshi levels) remains in raw responses. Kalshi asks are derived from complementary bids. Polymarket YES/NO assets are mapped explicitly and fetched separately; response skew is recorded.

Capture time is the latest receipt of all inputs. Nothing received later is backdated. Kalshi REST books lack a source event clock: receipt establishes the collector's conservative availability, not exchange publication latency. Polymarket future or >90-second-old source timestamps are rejected. Capture must complete before market close. Availability is a local receipt bound; original public publication is unknown unless explicitly supplied. Clock synchronization remains a deployment requirement.

`forward_resolution` requires a final explicit binary result/payout and timestamp. Closed status, a displayed terminal price, passage of time and a preliminary weather reading never become labels. `first_observed_at` records when this recorder learned settlement. Current polling uses at most 24 oldest pending markets per reconciliation; large/unresolved backlogs need a future archive walker and monitoring. Cancelled/fractional/void outcomes are excluded visibly.

## Fixed bounded universe

Initial Kalshi series: KXHIGHMIA, KXHIGHNY, KXLOWNYC, KXBTC15M. Polymarket uses one bounded 40-market Gamma keyset page, not a complete exchange census. The universe is a feasibility sample, not a representative population. Cursor/page caps produce coverage warnings. Metadata and listing filters require binary non-composite contracts, observable dates, volume >=100 in venue units, a positive displayed bid, ask below 1 and spread <=$0.10. Weather, macro/economics, crypto, politics, sports, other objective and subjective/ambiguous are tagged; subjective/ambiguous is excluded. Categorization is lexical and can need review; a category name alone never proves objective settlement. Unknown sources or missing rules fail eligibility.

Selection is deterministic lexical round-robin across events, capped at 12 concurrent markets. Snapshot eligibility also requires at least five YES-ask shares within one cent, <=10-cent spread, >=120 seconds to expected settlement, <=30 days horizon and an open market. Venue volume units differ: Kalshi contract shares and Polymarket reported dollar volume must not be combined as economic liquidity. Missing Kalshi dollar liquidity stays null. No outcome or P&L participates in selection.

## Rate calculation and actual frequency

The single recorder permits at most **one GET start/second with no burst**, including retries. Forecast GETs also have a ten-second host spacing; each location is revisited no more frequently than every 900 seconds. Discovery and resolution target 300 seconds. Quotes target start-to-start 30-second cycles. No catch-up burst follows an overrun.

For 12 Kalshi books, steady polling consumes 12/30 = 0.40 GET/s, plus discovery/settlement overhead. A Polymarket capture uses YES book + NO book + current fee info, so 12 such captures require >=36 seconds even with negligible transport time. The configured cycle is a target, not a promise. This serial implementation deliberately allows a longer cycle and reports actual per-market gaps/HTTP RTT. The pilot's several-second transport RTT substantially reduces achievable frequency. A small future watchlist could be polled faster only in a separately versioned collector after latency/rate evidence; this release's minimum is 30 seconds.

Official Polymarket `/book` limit: 1,500/10s =150/s; Gamma market limit 300/10s =30/s. At the entire collector ceiling, usage is <=0.67% and <=3.34% respectively. Kalshi authenticated Basic has 200 read tokens/s at the usual ten-token cost, nominally 20 GET/s; **that does not establish an unauthenticated IP quota**. NWS explicitly does not disclose its numeric limit. We cannot claim a precise quota margin for these two public services. Conservative spacing, bounded work, backoff and visible 429 records are used. Coinbase's documented public limit is 10/s. These are official limits checked 2026-10-01, not permanent constants.

401/403 pauses the host in that process. There is no proxy, alternate-host retry, spoofed browser, credential, trading or geographic bypass. Transient 429/5xx gets at most two retries with backoff; long requested waits pause visibly. Non-JSON/schema changes retain raw bytes and are rejected.

## Execution and costs

Midpoint is a forecasting baseline only. YES purchases use ask and sells would use bid. Depth is displayed capacity, not a guaranteed fill. Slippage is null while unvalidated, never silently zero. Kalshi captured quadratic series fee parameters permit a conservative whole-cent ceiling using 0.07 × multiplier × shares × p × (1-p), not an exact replica of combined centicent charging. Fee quality/exactness is recorded. Unsupported fee curves are unknown and block trading economics. Polymarket's captured supported curve is checked explicitly; unknown is not interpreted as fee-free.

There are no new hypothetical orders or fills from this collector. All unvalidated markets share the existing 1% risk cluster. Normal/hard position caps remain 0.25%/0.50%; no risk authority is delegated to a model.

Kalshi's one-whole-contract size is a conservative local research floor, not a verified current venue minimum. Exact venue minimum stays null pending documentation/endpoint validation. Polymarket book minimum size is captured when provided. Reports explicitly distinguish these constraints; no small-capital advantage is assumed from fractional book volume alone.

## Storage and health

Raw bytes are SHA-256 addressed, gzip-compressed deterministically and created exclusively; identical bodies deduplicate across retrievals. Metadata is content-versioned. Every retrieval time remains in the ledger. Older uncompressed feasibility probes are preserved. All code files used by a v0.3.1 recorder are archived compressed with a source hash and Git commit. Earlier provisional pilots lack a complete archived engine version and are marked limited; their raw observation evidence remains intact.

Daily reports estimate full-occupancy disk growth from actual compressed bytes and ledger growth. Startup registry payloads and short samples inflate estimates: no precise long-run monthly claim is made. Default budget is 2 GiB plus minimum 512 MiB free space. Reaching it stops visibly, never deletes evidence. Review storage after a full day; change disk budget only to available existing local storage. A collector cannot run indefinitely without finite-storage review.

`collector-health` checks process/heartbeat, writable database, data age, access/rate failures, schema/book rejections, clock anomalies and audit chain. PID checking applies to the same local OS runtime; a remote isolated command namespace cannot prove another runtime's process identity. A fresh lease, lock and session output supplement this check. Lock files are not automatically deleted after a crash: verify the old process is gone before manually removing a stale lock. `verify-forward` checks raw hashes, source archives and snapshot timing offline. Append-only SQL/hash chains are not tamper-proof against the filesystem owner.

The loop regenerates `reports/forward/YYYY-MM-DD.md` and JSON after cycles; these are derived views, not immutable observations. Ctrl-C or `data/STOP_COLLECTOR` stops cleanly. Database/process failures produce FAILED state and a nonzero command result. Per-source failures/degraded collection appear in reports instead of being swallowed.

This session workspace is transient. A bounded session pilot demonstrates ingestion; continuing after this chat requires the supplied local loop on an awake computer with internet. No durable cloud collector or paid server has been deployed.
