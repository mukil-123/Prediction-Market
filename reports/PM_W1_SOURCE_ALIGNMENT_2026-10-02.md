# PM-W1 source alignment follow-up — 2026-10-02

**DATA_CHECK; SOURCE_AUTHORITY_CONFLICT; no verified weather edge.** No parser, model, cohort, threshold or execution rule changed.

## Evidence and limitation

The current linked general [GLOBALTEMPERATURE contract PDF](https://assets.kalshi.com/contract_terms/GLOBALTEMPERATURE.pdf), retrieved through public document access today, describes an NWS-led source hierarchy, official station selection and non-preliminary reports. It defines strict versus inclusive comparisons, inclusive ranges, full source precision and possible fair-price fallback when data is absent. Some definitions contain placeholders and conditional precision language. This is a current document observation, not proof of its content or authority at an earlier capture time.

Previously captured KXHIGHMIA/KXHIGHNY market-specific criteria instead explicitly identify The Weather Company. They discuss preliminary/final differences, material-error review and a discretionary fair-price fallback. These exact criteria and their receipt/hash provenance are retained in immutable metadata. The linked generic document and market-specific payload are not sufficiently aligned to authorize a settlement-source substitution. Which version and hierarchy governs these contracts remains unresolved.

The [Weather Company Kalshi page](https://weather.com/kalshi) could not be retrieved by the public research tool. No scraping or paid final-data endpoint was added. Web-accessible document text is useful for review; it has not become an adapter input or a backdated rule vintage.

## Operational decision

| Alignment question | Current decision |
|---|---|
| Can NWS reference observations become Weather Company settlement labels? | No; exact provider and governing-rule authority remain unverified |
| Is CLIMIA/CLINYC an explicit weather-station mapping? | No; product/location codes alone do not establish a station |
| Does a calendar date establish timezone, exact daily interval and rounding? | No; verified market-specific definitions still required |
| Do between-range contracts fit the implemented threshold baseline? | No; range probability remains unsupported and is explicitly rejected |
| Does a final display guarantee an unrevisable authoritative value? | No; current market criteria describe review/revision contingencies |
| Is every possible settlement necessarily $0 or $1? | Not established; discretionary fair-price contingencies must be handled as nonbinary exclusions, not coerced labels |
| Can today's generic PDF clarify yesterday's rules retroactively? | No; preserve availability/version boundaries |

No eligible contract was created by this review. The existing forecast archive remains predictor data, not matching final labels; no real forecast-error distribution is fitted.

## Next data check

Establish the exact authoritative rule version/provider/station/window/precision/finality for a future contract before entry, retain that source with first receipt and hash, and then collect matching forecast/final-observation pairs. A range extension would require a new registered model/parser version, independent tests and prospective data; it is not silently enabled here. Keep PM-W1 blocked rather than infer authority from a familiar weather source.

Original PM-C1-FORWARD-003 definition and risk limits remain unchanged. $0 paid; no live or hypothetical fill was generated.
