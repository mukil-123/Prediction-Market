# PM-M1 free microstructure feasibility

**DEFERRED_DATA_LIMITATION. No arbitrage claim.**

| Public source | HTTP response | RTT (ms) | Usable samples |
|---|---|---:|---:|
| coinbase | 200 text/html; Site Unavailable HTML | 11983.8 | 0 |
| kraken | 200 text/html; Site Unavailable HTML | 8951.0 | 0 |

Kalshi crypto book snapshots: 8. Median Kalshi book GET RTT: 8590.0 ms. Timestamp precision is local receipt; no Kalshi venue book event clock is supplied.

The unavailable responses describe this environment, not a verified global exchange outage. Raw hashes, status and timestamps are preserved. Each source stopped after one failed structured-data probe; no proxy, alias retry, credential, paid feed or circumvention was used.

Official docs describe public Coinbase L2 with snapshot sequence/time where present and Kraken L2 with per-level update seconds. Coinbase public allowance is 10 requests/s; the research client caps starts at 1/s without bursts. The observed several-second transport RTT and serial fleet polling limit practical frequency. This did not measure market-publication latency or clock offset. No synchronized spot/contract sample was obtained.

The Kalshi contract resolves using a sixty-second CF Benchmarks BRTI average, not a single Coinbase/Kraken quote. Exact benchmark data/permission and clock synchronization are unverified. Free REST data here does not support a defensible subsecond lead/lag, executable arbitrage or adverse-selection claim. Further WebSocket/benchmark work is deferred behind PM-W1.
