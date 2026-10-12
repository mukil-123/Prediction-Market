# PM-W1 objective weather baseline — v0.2

Highest-priority new family. No LLM, paid forecast, neural network or live trading. Status: FORWARD_FORECAST_COLLECTION; CONTRACT_ALIGNMENT_BLOCKED; no validated weather edge.

## Detector and contract parser

The detector tags maximum/minimum temperature, instantaneous temperature, precipitation, snowfall and tropical storms. The first probability baseline concerns a temperature threshold; other variables and range contracts remain detected but deferred.

The parser preserves exact wording, source and criteria hash, and attempts location, explicit station, date, variable, units, inequality, local timezone/calendar window, rounding and final/preliminary status. `above 100` means >100; `at least 100` means >=100. It never fills omitted rules from convention. A climate product code such as CLIMIA is not an ICAO station. EDT alone is not an IANA timezone. Missing station/window/rounding/source/finality yields REJECTED_AMBIGUOUS. Contract PDFs/additional methodology require a future verified parser/review; their URLs are stored, not silently treated as parsed rules. Unsupported range/minimum-window mappings are blocked.

Inspected current daily Miami/New York high markets explicitly resolve through **The Weather Company**. The hourly Miami series names **Synoptic Data/Kalshi methodology**. Legacy NWS-based series exist in discovery, but their current liquidity/contract alignment has not been established. NWS operational readings cannot be substituted for either provider's settlement. Weather.com public pages were not scraped; no documented free final-resolution API was established in this work.

## Free predictor archive

NWS adapter discovers the point endpoint for configured Miami airport and Central Park reference coordinates, checks returned timezone, then captures forecasts and latest operational station observations. References KMIA/KNYC are configured for feasibility, not inferred authoritative stations for the inspected contracts.

Each forecast period preserves source/model, target date/window, location/reference station, issue/update time, first local availability/ingestion, horizon, deterministic value/units, ensemble=null, endpoint and raw hash. Original forecast vintages are archived on receipt; current values are never inserted as historical forecasts. Revisions append. Daily NWS point periods are grid predictors: daytime-high and overnight-low proxies are not final calendar-day station extrema. Forecast intervals crossing the target contract's local date are rejected by the baseline. DST windows use local calendar boundaries, including 23/25-hour days.

NWS observations preserve measurement time and first receipt independently. They are operational and can be delayed; hourly samples do not reconstruct exact daily extrema. No synthetic final labels or forecast-error sample was created.

## First statistical model

`WeatherBaseline` fits an empirical distribution of observed minus forecast residuals, with at least 30 unique TRAIN target dates from the same station, forecast source, resolution source, variable, units and a fixed 12–36-hour horizon band. Training forecasts must precede target start; observations must follow target end and have been available before the training cutoff. Provenance hashes and unique days are required. Validation/TEST data, future revisions, mismatched units/stations and duplicate dates fail.

For a forecast mean μ, compute the proportion of training residuals for which μ+error satisfies the **exact contract inequality and explicit rounding**. The initial smoothed probability is (hits+0.5)/(n+1). Report an empirical interval and sample count; it does not quantify all station/model/nonstationary uncertainty. No default normal sigma, guessed weather error, season overfitting or invented ensemble is used. Pool simply first; station/season/model refinements require prospective versioning and validation.

Prediction requires a model frozen before the decision, a forecast received before it, a future matching contract window/date, source/station/unit/horizon/variable alignment and eligible parsed rules. The actual archive currently lacks enough accepted contract-matched forecast/final-observation pairs, so **no real error distribution is fitted**. Unit-test residuals verify mathematics only.

## Economics and validation

`weather_edge` decomposes midpoint-relative expectation, ask entry cost, spread burden, conservative venue fee, explicit slippage and uncertainty buffer. Since ask already includes crossing the entry spread, do not subtract it twice. Unknown fee or slippage returns BLOCKED_UNKNOWN_COST. Visible depth limits capacity; it does not prove fills. A positive arithmetic research candidate never authorizes an order.

`choose_threshold` accepts prospective VALIDATION records only, requires >=30 after-cost observations, and chooses among the preregistered net-EV grid. No final TEST or future settlement label can select a threshold. A nonpositive result is a failed hypothesis. Slippage/buffer/model/cost policies must be frozen before future TEST. Current data cannot select a threshold.

The existing risk engine sizes at <=0.25% normal worst-case loss, <=0.50% absolute and <=1% common cluster. Minimum-order cost/fee as a percentage of small trades and the minimum cost/0.25% bankroll floor are reported. A risk floor is not a practical profitable bankroll: Kelly, uncertainty, correlated exposures and lack of edge can forbid every trade. Capacity/turnover/trades per month/expected bankroll return/drawdown/loss probability remain unknown until a validated forward execution sample exists.

Where exact venue minimum is unknown, the report uses a labeled conservative local size (one whole Kalshi contract) and keeps the venue value null. It is not an assertion about the smallest permitted real order.
