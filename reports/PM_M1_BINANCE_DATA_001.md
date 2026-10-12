# PM_M1_BINANCE_DATA_001

Experiment: **PM-M1-DATA-BINANCE-001**. Data only, $0, no orders. Verdict: **DEFERRED_DATA_LIMITATION**. Not DATA_FEASIBLE and not a reopened trading hypothesis.

## QUESTION / PROTOCOL

Can public Binance Futures BTCUSDT/ETHUSDT event data synchronize accurately enough against matching prediction-market books? Planned bounded sample: 30 seconds. Log raw hashes, event/transaction clocks, local receipt, BBO, trades, depth/update IDs and interruptions. A common event schema keeps provider time and corrected receipt distinct. No exchange account/authentication/order endpoint is needed or implemented.

## BINANCE DATA COLLECTION RESULT

The legitimate unauthenticated fapi.binance.com/fapi/v1/time preflight returned HTTP451 with restricted-location eligibility text. Access stopped for the provider; no WebSocket, alternate host, proxy/location workaround, fake account or testnet substitute followed. The collector archived the existing probe without sending another request. Its near-zero archive processing time is not a successful 30-second live sample.

| Measurement | Actual result |
|---|---|
| BTC / ETH underlying messages | 0 /0 |
| Successful connections / reconnects | 0 /0 |
| Raw denial archive | 1 record; SHA and chain verified |
| Failed HTTP request elapsed | 7,695.136174ms |
| Median/p90/p95/p99/max feed latency | all null / unmeasured |
| Local clock offset / uncertainty | null / null |
| Order latency | null; no orders |
| Underlying sequence gaps | unknown; no established stream |

Zero disconnect counts do not demonstrate reliability when no stream was established. No fabricated quote, trade or latency was inserted.

## TIMESTAMP QUALITY / CLOCK SYNCHRONIZATION

The implemented server-time probe uses the request/receipt midpoint, RTT/2 plus 1 ms quantization and observed offset disagreement; wall-clock jumps are rejected. This estimates clock offset against the exchange server and does not independently certify its accuracy. Pre/post clock drift checks and independent clock-source accuracy remain required for a successful future trial. Current offset, timestamp precision in observed underlying data, feed-latency distribution and total synchronization uncertainty are unknown.

Venue event timestamp and local receipt have separate fields. Missing venue time never becomes a guessed receipt-time event. Tests verify this and the requirement that timing uncertainty be below an observed lag. A 50 ms lag with100 ms uncertainty fails. No measured lag exists in this experiment.

## PREDICTION-MARKET DATA / SYNCHRONIZATION RESULT

The experiment audits 29 existing crypto snapshots available at the 12:09 UTC capture review; this fixed subset is not the later entire PM checkpoint. Their Kalshi source has **RECEIPT_ONLY_NO_VENUE_EVENT_TIME**. Existing REST cadence is coarse, not a continuous venue-event feed.

| Existing book HTTP elapsed metric | ms |
|---|---:|
| median | 9,229.418 |
| p90 | 9,975.7434 |
| p95 | 10,642.332 |
| p99 | 11,329.33304 |
| maximum | 11,429.638 |

These are request elapsed durations from archived provenance, **not** PM event-to-receipt latencies, exchange clock offsets or executable reaction delays.

A corresponding KXBTC15M contract uses 60 CF Benchmarks BRTI observations averaged before each comparison boundary. Binance BTCUSDT is a USDT perpetual derivative, not that spot-index settlement benchmark. Futures basis, averaging/window semantics and translation remain unverified. No Binance price is substituted for the contract's resolution source.

Underlying/PM pairs=0. Reaction lag, stale-quote duration, price adjustment, spread-response effect and fill opportunity are all unmeasured. Even successful Binance receipt alone would not establish any of them.

## MINIMUM IMPLEMENTATION / LIMITATIONS

Original stdlib-only module: src/pm_alpha/data/binance_feasibility.py. It is isolated from the PM-C1 recorder. Append-only content-addressed raw capture/hash chain; corrected-clock fields; bounded public stream prototype; standalone depth reconstruction with first-snapshot overlap, pu continuity and fail-closed resnapshot requirement. Immediate queued writes retain messages preceding disconnects.

No HFTENGINE code, UI or strategy was imported. Its public timestamp/replay ideas informed the engineering approach. Tests use offline synthetic events, not observed exchange samples. Live transport has not been validated. Automatic reconnect/resnapshot and complete buffered live-depth initialization are not yet integrated. Consequently even a future receiving run remains CAPTURED_UNVALIDATED until reconstruction, drift, gap and timing gates are demonstrated.

## PM-M1 DATA VERDICT

Hard failures: no underlying events; no PM venue event clock; unmeasured timing uncertainty; unresolved benchmark translation. Status remains **DEFERRED_DATA_LIMITATION**. No P&L, strategy filter, optimized threshold or live execution. Good feed latency, if eventually measured, would not prove good order latency.

## OTHER STREAMS / COST / TESTS

At consistent checkpoint 2026-10-03T18:08:03.969172+00:00: 492 market-book snapshots, 137 forecasts, 16 station observations and 36 settlement records. The audit chain and deterministic raw replay pass (492 books / 137 forecasts). Frozen PM-C1-FORWARD-003 file SHA-256 remains cc9f69d812d99b80d120c1e63a54287d85dc776bb0645c57f2e5899a5830e3d0. It has eight nominations under the unchanged definition, zero eligible TRAIN entries and zero resolved TRAIN entries; new nominations arose from normal forward discovery, not revised rules. TEST remains unopened.

Collector health is fresh at the checkpoint. Runtime expiry caused documented gaps, including 20,231 seconds before the current resume; missed data was not backfilled. PM-W1 remains settlement-source blocked. NWS records are predictors/observations, not substituted settlement labels. PM-M1 remains DEFERRED_DATA_LIMITATION. LIVE_TRADING=false; real orders=0; no verified profitable edge.

ORB-I0 remains frozen and data-blocked ; 43 tests pass. YouTube V1 rejected/retained; V2 AWAITING_HUMAN_NARRATION and no public upload. New PM tests:19; full PM suite:188. Raw denial integrity and the consistent forward checkpoint pass. $0 incremental spend, no capital/account/trades.

## NEXT ACTION

Seek only legitimately available free access in an eligible environment or a different legally accessible feed with proven benchmark semantics; do not bypass this venue's denial. Separately assess an authorized precise PM event feed and independent clock quality. Repeat a newly identified data experiment if those gates become possible; defer the trading hypothesis until they pass.

Official method sources: [Binance book ticker](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Individual-Symbol-Book-Ticker-Streams), [depth reconstruction](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly). Archived contract metadata/probe/synchronization files are in data/experiments/PM-M1-DATA-BINANCE-001; no live result is inferred from documentation.
