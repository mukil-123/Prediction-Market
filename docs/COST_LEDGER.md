# Cost ledger

**Baseline subscription/service operating cost: $0/month. Paid spend incurred: $0.** Existing computer, internet and electricity are assumed; their marginal costs are not guaranteed zero. Trading capital and transaction fees would be real costs in a later live milestone.

| Dependency/service | Purpose | Current cost | Limits | Optional? | Free replacement if unavailable |
|---|---|---:|---|---|---|
| Python ≥3.11 + standard library | CLI, HTTP, math, reports, JSON/TOML | $0 | Local CPU/RAM; no managed uptime | No | Another supported local Python distribution |
| SQLite, via `sqlite3` | Append-only audit/database | $0 | Local disk; serialized writes; no hosted backup | No | Local PostgreSQL/DuckDB after explicit migration |
| Git | Version/commit provenance | $0 | Local storage; no remote automatically provisioned | No for full provenance | Export exact source SHA manifest if Git absent; reports mark UNCOMMITTED |
| pip + setuptools | Local package installation | $0 | Package download access during setup | Setup only | Run from source using `PYTHONPATH=src`; no service required |
| pytest | Automated checks | $0 | Development installation only | No for release verification | Standard-library unittest port if package distribution disappears |
| iniconfig, pluggy, packaging, Pygments | pytest transitive tools | $0 | Versions captured in environment manifest | Testing only | Same unittest fallback |
| colorama | pytest Windows conditional dependency | $0 | Windows terminal colour support | Testing only | Run tests without colour / unittest fallback |
| Polymarket Gamma API | Discovery/rules metadata | $0 | Public API; rate limits; intermittent 403; later public reads succeeded | No for Polymarket branch | Local previously collected data; explicit separate venue research |
| Polymarket CLOB public reads | Current books/fee parameters | $0 | No free complete historical depth identified; initial 403; no depth claim | No for Polymarket execution study | Record allowed public live reads elsewhere; never bypass restrictions |
| Polymarket Data API v2 | History/final resolution | $0 | Retention/resolution tiers; no original publication guarantee; initial 403; no depth claim | No for Polymarket branch | Freeze local copies; public on-chain data is a separately reviewed pathway |
| Kalshi public REST | Explicit validation fallback | $0 | Public data only; throttled at 1 request/s; incomplete historical execution data | Yes to initial venue choice | Bundled offline sample; no synthetic substitution as performance |
| NOAA/NWS public data | Forward forecast/operational observation archive | $0 | Public identified GET; unpublished numeric quota; final settlement source alignment still blocked | No for current PM-W1 predictor branch | Previously recorded vintages; defer signals if unavailable |
| Local continuous Python loop / Windows launch script | Market/weather polling and daily reports | $0 | Existing awake computer/internet/disk; no durable session/cloud uptime | No for ongoing forward data | Run bounded `collect-forward --cycles 1`; preserve gaps |
| IANA timezone dataset / optional CPython tzdata | Correct local weather dates/DST | $0 | Uses OS data; Windows without IANA data needs the free dataset/package | Data prerequisite for weather | Supply TZif data through PYTHONTZPATH; fail rather than guess offsets |
| gzip / local source archives | Raw deduplication and exact ingestion-code provenance | $0 | Finite local disk; default 2GiB guard | No | Existing larger local disk after measured capacity review |
| Coinbase/Kraken public book probes | Limited PM-M1 feasibility | $0 | Environment returned HTML unavailable pages; no underlying quote obtained | Deferred | Defer PM-M1; no proxy or paid data replacement |
| Local Markdown/JSON/SVG renderer | Readable reports/plots | $0 | Static files; no chart service | No | Any free text/SVG viewer |

No Grok, Jev, OpenAI, Anthropic, paid datasets, VPS, proxies, paid scraping, cloud database or monitoring subscription is required or connected. AI subscriptions are not installed and are not presumed to create edge.

Future optional upgrades: licensed depth archives, managed hosting, paid forecast providers, or an AI API may be evaluated only with a new explicit cost/benefit review. Their prices are not assumed, and none appears in baseline setup.

Forward milestone additions change the paid service bill by **$0**. NWS/market public reads, local forecasting math, SQLite, gzip and report generation remain free. No AI API or managed hosting was invoked. Forecast arrays, raw responses, Git history and reports use existing storage. A free timezone dataset is a Windows data prerequisite where system IANA data is absent; it is not a paid forecasting/model service. Runtime algorithms remain Python standard library + SQLite.

2026-10-02: Instagram source triage, public official-rule review and local collector resumption add $0 paid spend and $0/month services. The expired session gap is recorded without backfill. The free pinned development test tools may be reinstalled after runtime cleanup; no paid infrastructure or AI service was added. No full social-media workflow has yet been established as reproducible for free.

2026-10-03: bounded Binance data-feasibility probe and original stdlib raw/event helpers add $0; denied HTTP451 stops further access. No broker account, order, paid data, proxy or API. Free pytest reinstalled solely to run existing/new tests. Frozen cohorts and collector rules unchanged.

2026-10-08: DdTwFSqp3mS lead intake and registry documentation add $0 paid spend and $0/month services. No source-content inference, external data purchase, strategy implementation or order placement. Existing research and live-trading restrictions are unchanged.

2026-10-08 continuation: original public forward collector resumed in bounded local runs with unchanged configuration/code. Existing free pytest restored for verification. Read-only replay/checkpoint and append-only capture add $0 paid spend; no new strategy, paid service, order or live execution. The intervening runtime gap is not backfilled.

2026-10-08 research desktop release: local Python stdlib HTTP console, read-only SQLite summaries/replay, collector process controls, original HTML/CSS/JavaScript and Windows source launcher add $0 paid spend and $0/month services. No AI API, hosting, wallet, paid data or trading endpoint. Free tzdata is needed only on Windows hosts lacking IANA data. Existing hardware/internet/electricity remain assumptions. No YouTube work was performed in this release.

2026-10-12 continuation: contribution accounting, append-only research orchestration, shadow replay, REST funding controls, and launcher integration use existing Python standard library + SQLite + local HTML/JavaScript. Added recurring service cost $0; paid spend $0; no credentials, transfers, AI API, hosting or paid data. Existing pinned free pytest dependencies were installed for development. Existing free Playwright/Chromium were reused solely for browser verification in this cloud workspace; neither is a product runtime requirement. Local fixture and consistent backup storage uses existing disk. Network allow-list draft changes incur no paid service and do not establish access or a compliance review.
