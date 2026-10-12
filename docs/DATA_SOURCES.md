# Sources and dataset provenance

Documentation reviewed **2026-10-01 UTC**. Public access requires no trading secrets; trading access is separate. Endpoint facts may change. `docs/SOURCE_MANIFEST.json` records consulted URLs/retrievals/hashes; full third-party documentation is not redistributed.

## Polymarket

| Endpoint | Purpose | Public/auth | History/limitations |
|---|---|---|---|
| Gamma `GET /markets/keyset` | Discovery/metadata, `closed`, `limit`, `after_cursor` | Public | Follow `next_cursor`; `closed` does not prove a final payout |
| Gamma `GET /markets`, `/events` | Legacy listing/event lookup | Public | Current metadata can be revised; do not backdate it |
| CLOB `GET /book?token_id=` | Current bid/ask/depth and server milliseconds | Public | No free complete depth archive identified |
| CLOB `GET /clob-markets/{condition_id}` | Tokens/minimum size/tick/fee curve | Public | `fd` parameters verified; incompatible exponent rejected |
| CLOB `GET /fee-rate?token_id=` | Base fee | Public | A base value alone is not full historical fee evidence |
| Data `GET /v2/prices-history` | Token price observations | Public | Cursor pagination; interval/max or explicit window or as_of |
| Data `GET /v2/resolutions?condition=` | Final resolution/payouts/provenance | Public | Require resolved status, binary payouts and resolved_at |
| CLOB `GET /prices-history` | Legacy historical price path | Public | Retained in API research; not silently substituted |
| `GET polymarket.com/api/geoblock` | IP-based trading eligibility | Public | Needed before future live mode; do not circumvent |

Current documented price history: full-life 3/12-hour tiers, with finer resolutions retained for shorter windows; explicitly incompatible resolutions can produce empty results. Settlement observations with zero `resolution_seconds` are labels, not pre-outcome price forecasts. Publication/revision assurance still requires validation.

Reviewed limits include Gamma markets 300/10s, CLOB books 1,500/10s, legacy history 1,000/10s, Data v2 history 200/10s. This collector uses 1 request/s and bounded retries for transient failures, never access denials. Authenticated order signing/API credentials are needed for live orders, which are absent here. Documented order choices include GTC/GTD limit orders and FAK/FOK marketable orders. Category-specific taker fees must be verified per market; see RISK_POLICY.

Initial October 1 Polymarket probes returned HTTP 403 with Cloudflare error 1010. Later public-client requests to Gamma and Data API v2 succeeded without any anti-bot or geographic workaround. The initial 2020 cohort had empty price history; a separate recent-start cohort was then requested. Access remains intermittent; do not infer that the user's residence is its cause. Official geographic lists are consulted separately. India is not on the displayed platform block list at review time, but that is **not** a local-law or account-eligibility determination. Paper study remains possible from legitimately obtained data.

Primary references: [API overview](https://docs.polymarket.com/api-reference/predictions/overview), [keyset](https://docs.polymarket.com/api-reference/markets/list-markets-keyset-pagination), [history](https://docs.polymarket.com/api-reference/markets/get-a-tokens-price-history), [resolution](https://docs.polymarket.com/api-reference/markets/get-resolution-state), [limits](https://docs.polymarket.com/api-reference/rate-limits), [fees](https://docs.polymarket.com/trading/fees), [order controls](https://docs.polymarket.com/trading/place-orders), [eligibility](https://docs.polymarket.com/api-reference/geoblock).

## Kalshi: explicit fallback validation venue

Base `https://external-api.kalshi.com/trade-api/v2`. The older `api.elections.kalshi.com` public endpoint also responded during the initial probe; default implementation uses the currently documented external-api base. It is not an automated host/proxy fallback on denial.

| Endpoint | Purpose | Timestamp/data behaviour |
|---|---|---|
| `GET /markets?status=settled&mve_filter=exclude` | Recent finalized binary markets | Filter `settled` maps to response `finalized`; use explicit result/settlement timestamp |
| `GET /events/{event_ticker}` | Verified event → series mapping | Avoid guessing series names from ticker format |
| `GET /series/{series}/markets/{ticker}/candlesticks` | Recent 1/60/1440-minute history | Separate price and bid/ask candle fields; no original release times or depth |
| `GET /historical/cutoff`, `/historical/markets` | Older archive partitions | Older settled markets leave live listing; completeness needs both tiers |
| `GET /historical/markets/{ticker}/candlesticks` | Archived candles | Adapter path supported; full-universe archive walk not yet implemented |
| `GET /markets/{ticker}/orderbook` | Current fixed-point two-outcome bids | YES ask is `1-NO bid` with same depth; receipt establishes conservative availability |

Public reads require no API keys. Authenticated account/trading requests use access key/signature/timestamp and tier budgets. Current Basic authenticated read budget 200 tokens/s, usual cost 10 tokens/request; public unauthenticated quotas are not presumed identical. Client remains 1 request/s and respects 429. Current prediction order-entry APIs distinguish limit execution and time-in-force choices; an exact current private adapter is out of scope, and no private requests were made. Fee schedule and per-event/series overrides require time-specific verification; conservative cost function is not a claim to reproduce current protocol rounding.

Kalshi's international help page requires country/residence/identity eligibility under its Member Agreement. User-specific India/Tamil Nadu live eligibility remains unresolved. Public download success does not prove eligibility. No account, deposit, trade or identity action occurred.

Primary references: [public market quick start](https://docs.kalshi.com/getting_started/quick_start_market_data), [markets](https://docs.kalshi.com/api-reference/market/get-markets), [candles](https://docs.kalshi.com/api-reference/market/get-market-candlesticks), [archive](https://docs.kalshi.com/getting_started/historical_data), [order book](https://docs.kalshi.com/getting_started/orderbook_responses), [lifecycle](https://docs.kalshi.com/getting_started/market_lifecycle), [rate limits](https://docs.kalshi.com/getting_started/rate_limits), [fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf), [international eligibility](https://help.kalshi.com/en/articles/14026044-can-i-trade-on-kalshi-from-outside-the-united-states).

## Dataset timestamp semantics

| Dataset | event_time | available_time | ingested_time | Missing/revision policy |
|---|---|---|---|---|
| Current market metadata | Receipt snapshot time | Actual receipt | Actual receipt | Never set it to a historical creation date; rules may have changed |
| Kalshi historical candle | `end_period_ts` seconds UTC | **Unknown** | Actual GET receipt | Keep unavailable; strict DATA_INVALID; no forward fill of unknown quotes |
| Polymarket historical observations | Supplied timestamp/window | Not independently verified | Actual GET receipt | Retain raw; settlement row never a predictive feature |
| Polymarket live book | Server milliseconds UTC | Actual GET receipt | Actual GET receipt | Reject missing/two-sided/crossed book; detect receipt staleness |
| Kalshi live REST book | Receipt (source event time unavailable) | Actual receipt | Actual receipt | No claim to measure exchange latency; one response is a snapshot |
| Final binary labels | Final settlement/resolution timestamp | Source final settlement time, with provenance | Raw retrieval logged separately | Use final endpoint/result, not prices; current retrospective labels do not validate pre-entry rules |

All timestamps convert to UTC. Collector updates only when explicitly run (or locally scheduled); no cloud collector is running after this session. Retrieval logs include endpoint, receipt UTC, body SHA-256 and immutable raw filename. Normalized datasets include selection rules, rejected records, source/version and quality state. Content hashes protect exact reproduction, not historical availability.

Original weather forecast vintages, complete historical books and fees have not been obtained. Raw terminal quotes are visibly different from forecast inputs and are never a shortcut to calibration accuracy.
