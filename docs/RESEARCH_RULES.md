# Research rules and initial pre-registration

The initial experiment is a data-feasibility run. No successful trading test has been selected. Rule/config defaults were fixed before the historical snapshot diagnostics were computed.

## PM-C1-v0.1

Question: does independently estimated calibration improve quoted probabilities and leave positive after-cost EV?

Fixed first implementation: 20 equal probability bins; prior weight 20 at the input market probability; no imported viral coefficients; YES-only purchase/hold to final binary settlement; empirical 95% Wilson bin bounds; at least 20 training observations in a traded bin; lower-bound net excess >$0.02 per $1 payout share; $0.005/share proposed slippage stress; immutable risk caps; verified fees, publication times and executable depth mandatory for strict P&L.

The Wilson interval describes aggregate bin frequency under a simple sampling model; it is not a true-probability interval for each event. The prior is a shrinkage baseline, not a posterior certainty guarantee. Cluster bootstraps and future modelling of category/horizon heterogeneity must test its practical adequacy.

Kalshi feasibility extraction: latest nonempty minute candle at or before exactly 10 minutes after open, maximum age 2 minutes; one lexical market per event; current settled listing with MVE composites excluded. If unavailable, skip and record why. This recent convenience sample is not the pre-registered historical universe. Original metadata publication/revisions and candle release times are unknown, so strict eligibility fails. No current settlement price becomes an input.

## Splits and exposure

Chronological TRAIN/VALIDATION/TEST proportions 60/20/20 by entire event group. Purge earlier rows whose labels become available at or after the next split's first entry. Label-aware purging prevents training on unresolved events. It does not solve an invalid market universe or retrospective metadata.

TEST scoring and outcomes never enter model/report diagnostics before a hash-bound freeze. Frozen data/config/model/source code/risk settings must match exactly and may be opened once. Reports append event-exposure records to `data/research_audit.sqlite`; diagnostics contaminate inspected events for later OOS. Preserve that ledger across machines. New file names do not restore untouched status.

Raw resolved-data downloads necessarily contain labels for ingestion and integrity checks. This cannot make the holdout inaccessible to a person opening raw files; integrity depends on respecting the holdout and keeping an independent future cohort when outcomes were viewed. Automated report isolation is tested.

## Proposed acceptance protocol, not passed gates

1. No missing/ambiguous release times, metadata vintages, labels, fee vintages or time-of-entry executable state.
2. Event-cluster bootstrap 95% lower CI for net EV >0, using a predeclared family of tests; raw positivity alone is insufficient.
3. Out-of-sample Brier/log-loss versus market baseline and historical calibration baseline; paired cluster-bootstrap improvement must be credible. Complex models must improve both forecasting and cost-aware decision usefulness. AUC, ECE and sharpness are diagnostics, not substitutes for proper scores.
4. Chronological stability, category/horizon concentration, and parameter sensitivity assessed on TRAIN/VALIDATION before final TEST.
5. At least 10,000 event/time-block survival paths, plus adverse fees, liquidity gaps, correlated outcomes and structural-change scenarios. Calendar horizon, tolerated drawdown and required survival probability must be pre-registered after the intended capital/use case is defined; no pass threshold has been manufactured from this invalid sample.
6. New forward snapshots/decisions saved before resolution; measured fill/slippage and shadow forecast errors must agree reasonably with historical uncertainty. Shadow days and sufficient independent events are determined by precision/power, not an attractive arbitrary small sample.
7. Account/jurisdiction/terms/operational readiness before any later live milestone. LIVE_SMALL is disabled in code today.

The minimum 20/bin, 2-point EV margin and half-cent reserve are transparent initial research controls, not statistically justified promotion thresholds. They cannot be tuned after TEST and must be stress-tested. Predeclared candidate sensitivity grid for future validation: prior 10/20/40, net margin 0.01/0.02/0.03, slippage 0.0025/0.005/0.01; each attempted combination and rejected variation counts in the trial ledger.

## Multiple testing and reproducibility

Record every hypothesis, parameter combination, filter, category and universe restriction in `docs/TRIAL_LEDGER.json`. Benjamini–Hochberg FDR helper is implemented; target 5% is a proposed reporting convention, not a universal safeguard under arbitrary dependence. Record raw and adjusted p-values together. Cluster bootstrap is implemented. Deflated Sharpe and probability of backtest overfitting are deferred until there is a suitable strategy/return matrix, not faked from zero trades.

Every experiment saves source commit, dataset/config/model versions and hashes, sample dates, assumptions, costs, seed, splits, rejection counts and verdict. No reported profitability uses synthetic fixtures. Failed versions remain visible and retired versions cannot silently resume.

Scientific basis for scoring: [Gneiting & Raftery (2007), Strictly Proper Scoring Rules, Prediction, and Estimation](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf). Separate calibration/reliability and probability sharpness from trading performance; a good probability forecast need not generate profit at offered prices.
