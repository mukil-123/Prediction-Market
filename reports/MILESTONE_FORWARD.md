# Forward collection and weather research milestone

**NO VERIFIED EDGE. LIVE_TRADING=false. Paid service spend $0; baseline $0/month.**

## WORK COMPLETED

Continued the existing repository and preserved its original research. Added a public prospective market recorder, immutable compressed raw capture, deduplicated metadata, final settlement reconciliation, frozen close-anchored calibration cohort, strict weather detector/parser, received-vintage NWS adapter, TRAIN-only empirical weather-error model/EV helpers, daily reports, health/disk guards and local PowerShell start/stop scripts.

## CURRENT DATA COLLECTION STATUS

Checkpoint UTC: 2026-10-01T18:09:42.638385+00:00. The continuous loop was resumed in the current session after bounded pilots. This workspace does not guarantee uptime after session/inactivity cleanup; use the supplied local loop on an awake computer for ongoing capture. The released data is an immutable checkpoint, not a live synchronization channel.

| Actual checkpoint evidence | Count/value |
|---|---:|
| Snapshots | 138 |
| Distinct captured markets | 14 |
| Active watchlist cap | 12 |
| Weather forecast periods / operational observation records | 42 / 4 |
| Explicit final settlements reconciled | 2 |
| Markets with captured book before final settlement | 1 |
| API transport failures / malformed or missing-book rejections | 1 / 4 |
| Median spread | $0.0100 per $1 payout |
| Median HTTP RTT | 8589.7 ms |
| Median repeated-market capture gap (includes restarts/pauses) | 159.9 s |
| Hypothetical fills / live orders | 0 / 0 |

The one transport failure was an NWS Miami forecast timeout. Other forecast vintages were retained; no missing forecast was synthesized. Available captured books in this checkpoint are Kalshi; bounded Polymarket discovery did not yield a selected book. Volume, depth and price are observations, not proof of fills or edge.

## PM-C1 STATUS

Active cohort: PM-C1-FORWARD-003, frozen 2026-10-01T17:46:55.502904+00:00, definition hash `6368389a4891b59b0aadf0d39a483d288269b0ee9c483ec4942b04f5d6718a66`. 4 event representatives were nominated prospectively; 0 eligible observation-window entries and 0 resolved TRAIN entries exist. Scores/model comparison/after-cost expectancy are not estimable. Final TEST remains closed.

The frozen rule captures the first completed book within 180 seconds beginning one hour before close. Minimum volume100, >=5 ask shares within1cent, spread<=10c and objective binary sources are fixed. Splits require200TRAIN/100VALIDATION/200TEST events. A small 30-day watchlist may not reach these counts; do not lower requirements to obtain results. Provisional001 settlement-anchor and002 nomination-time defects were retired before any cohort scoring; all versions/reasons remain recorded.

## PM-W1 STATUS

Detected 24 distinct weather markets (42 immutable criterion versions); 0 versions passed every strict contract-rule requirement. NWS forecasts/observations are archived, but no real contract-matched error distribution is trained. Unit tests verify the empirical probability baseline and exact > versus >= semantics. Current daily high contracts inspected use The Weather Company; hourly Miami uses Synoptic Data. NWS reference observations are not their settlement labels. No candidate signal, validated threshold or weather trade exists.

The baseline needs>=30 independent TRAIN dates matched by station/source/resolution provider/variable/units/horizon, with forecasts available before target start and observations before training cutoff. Unknown slippage/fees block EV, and ask already includes the entry spread. Conditional minimum-size fee/risk floors appear in the daily report; venue minimum is explicitly unknown when only a local research floor is used.

## PM-M1 FEASIBILITY

DEFERRED_DATA_LIMITATION. Coinbase/Kraken public endpoints returned HTTP200 HTML Site Unavailable in this environment, so no spot quotes/synchronized pairs were obtained. Kalshi crypto depth is available, but no venue book event clock or exact CF BRTI match was established. Several-second HTTP RTT and asynchronous polling do not support a subsecond arbitrage claim.

## TEST RESULTS

169 passed (88 original +81 added). Source code committed as `4de0446ab3f7febbf144a7ec9961a15ce1d86ba5`. Checks cover append-only audit/raw files, throttle/backoff/access denial, duplicate and crossed books, eligibility/cohort first-observation locking, source archives, DST, exact contract thresholds, weather TRAIN/availability leakage, empirical probability/EV and capped small-bankroll/correlated sizing. Synthetic tests are software evidence only. Native Windows was not available.

Offline checkpoint verification: 186 unique raw responses, 138 snapshots, 2 referenced source archives; all hashes/chains/timing checks passed. Two archive references may share the identical code file. Earlier provisional pilots lack complete engine archives and remain feasibility data.

## FILES CREATED/CHANGED

Code: forward HTTP/rate limiter, forward schema, recorder, cohort, weather baseline/adapter, integrity, reports and limited microstructure probe. Configuration/local scripts: forward.toml and start/stop PowerShell. Documentation: FORWARD_DATA_PROTOCOL, PM_C1_FORWARD_PROTOCOL, PM_W1_SPEC, FREE_DATA_SOURCES, DATA_LIMITATIONS, cost ledger, strategy registry/trials. New forward audit/raw/source/cohort data and daily Markdown/JSON, JUnit and environment/checkpoint verification reports are included. Original historical samples, reports, risk caps and disabled live execution are preserved. THEER/XAUUSD projects were not touched.

## CURRENT RESEARCH EVIDENCE

The system captures prospective book/fee/rule receipts and meteorological forecast vintages. One observed market in this checkpoint has a book before its explicit final settlement; it is a crypto feasibility event outside the one-hour cohort, not an untouched PM-C1 test. There is no verified forecasting transformation, net trading expectancy, income estimate or capital recommendation.

## BLOCKERS

Future cohort windows/independent resolutions; exact weather station/window/rounding/provider labels; sufficient TRAIN forecast errors; validated cost/slippage/fill policy; actual venue minimum size; complete universe/backlog coverage; final forward TEST policy; clock/benchmark synchronization; finite storage and durable local uptime. Live eligibility remains unverified. Public read access is not live trading permission.

## COST STATUS

$0 paid; $0/month services. Python/SQLite/gzip/public GET/local files only. Actual raw+SQLite checkpoint size 19.62 MiB. Early full12-market/30s recurring-write projection: 262.5 MiB/day and 7.69 GiB/30days; actual serial polling is slower. Default2GiB guard prevents uncontrolled growth; remeasure after a full day and use only existing free local disk. Hardware/internet/electricity are assumed, not a new zero-price purchase.

## NEXT AUTONOMOUS ACTION

Continue the already started loop while this runtime remains available. For durable capture, extract the release and run `python -m pm_alpha collect-forward` in the documented local environment. Observe frozen windows, reconcile final labels and report exclusions. Establish exact weather resolution source/rules and collect valid error pairs before training; choose/freeze a threshold only on TRAIN/VALIDATION. Keep TEST/live money disabled and PM-A1 deferred.
