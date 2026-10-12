# PM-M1-DATA-BINANCE-001 — data feasibility only

Scope: a bounded 30-second public BTCUSDT/ETHUSDT Futures feed sample, clock probes and synchronization audit against existing prediction-market crypto books. No exchange account, order endpoint, P&L or trading-hypothesis change. This record documents the data protocol and the observed preflight denial; it is not retrospectively presented as a pre-P&L strategy registration.

Records: raw messages/hash chain, venue event and transaction timestamps, local receipt time, estimated corrected receipt and uncertainty, BBO, depth/trades, update identifiers and interruption events. Original minimal stdlib collector is independent of PM-C1 cadence. Retain both clocks; never silently substitute receipt time for missing venue time.

Timing: server-time HTTP midpoint and RTT/2 plus timestamp quantization, rejected wall-clock jumps and disagreement allowance. This estimates offset against the server and assumes its clock accuracy; it is not independent NTP proof. A viable future sample additionally needs before/after clock checks, clock-source accuracy, propagation/polling uncertainty and a venue event-clock feed on both sides. Never quote lag smaller than total uncertainty.

Depth: official snapshot/first-update overlap and subsequent pu continuity are implemented/tested in a standalone Book component. A full live buffered snapshot/depth integration, resnapshot/reconnection policy and exchange observation validation remain unfinished. Current transport code is a data prototype; a stream receiving data would still be CAPTURED_UNVALIDATED. The raw queue writes received messages before disconnect; it is not a strategy or proof of execution quality.

Acceptance: lawful accessible source; adequate two-sided event timing; known missingness/sequence handling; independently justified underlying-to-contract benchmark translation; timing uncertainty materially below the lag scale being studied. Failure of any gate keeps PM-M1 DEFERRED_DATA_LIMITATION. No strategy profitability until these gates pass.

Observed: official fapi server-time GET returned HTTP451 for restricted location. Provider access stopped. No WebSocket, alternate host/location, proxy, paid access, deposit or account was attempted. Underlying messages=0; clock/latency/lag are unmeasured. Denial bytes and request timings are retained with verified hashes. Existing Kalshi crypto books lack venue event timestamps and use CF Benchmarks BRTI spot-index averages, not Binance perpetual prices. PM-M1 remains deferred.
