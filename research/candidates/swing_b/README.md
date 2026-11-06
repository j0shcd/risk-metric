# Adaptive trend innovation research

Question: Which assumption about time, learning, or market dynamics might be limiting the current indicator?

Hypothesis: fixed lookback/expanding price ranks can confuse changing secular growth with cyclical overvaluation. A causal local-linear trend estimate can remove secular drift while retaining deviations that order multi-year opportunity. This is falsified by inferior directional ordering or no conditional predictive improvement against strong price/time/cycle baselines on the locked common evaluator. Undirected predictive information is distinct from higher-score/higher-risk ordering.

Ranked ideas before implementation: (1) adaptive local-linear log-price innovation; (2) multiscale historical investor acquisition-cost distribution; (3) mature-label online ordinal learning with regularization. Only (1) is implemented. Three parameter variants are declared before scoring; no outcome-trained parameters, hardcoded cycle dates, or reconstructed incumbent features enter the generator.

## Fixed specification

At each completed calendar month, predict log price as previous level plus .98 times previous slope. Emit `50 + 50*tanh((log_price-prediction)/(4*previous_scale))`. Then clip the innovation to four previous scales and update the level and slope. Adaptive alpha/beta=.08/.004, slow=.04/.002, fast=.16/.008. Initial level is first log price, initial slope zero, initial absolute-return scale .25. After emitting and correcting, update scale with EW alpha=1/24 of the absolute monthly log return and floor .05. Scale and state update only from current/past observations. Clipping protects the state from a single observation but prolonged structural shifts may leave the filter stale; output saturates near 0/100 during extreme moves. Slope is not independently capped. The scale floor/initialization and all other parameters are heuristics selected in November 2026, not historically deployed settings.

The generator rejects duplicate dates, nonpositive/nonfinite prices and missing entire months. It drops a trailing incomplete month. It uses the last supplied daily observation in a completed calendar month. Missing individual daily rows can therefore make the observation stale. Daily close timestamp/vendor conventions are unverified. No calendar gap filling or backward filling occurs. Higher innovation is declared higher risk, an empirical hypothesis rather than a financial guarantee.

## Provenance and scope

Input: read-only development bundle `/private/tmp/risk-hillclimb-inputs-gj866s2j/btc_daily.csv`, SHA256 `d6e0e23e4d84e32690cea42cc0bf69f44ddfe9d954939b54ba499635431ed04c`, 4018 daily rows, 2012-01-01 through 2022-12-31. Input hash checked against supplied manifest. The source-vintage and UTC close conventions are unverified; prefix invariance proves computational causality only. Full-history data and post-2022 outcomes were not read. No new data fetched, dependencies installed, credentials read, or production defaults changed.

Decision served: exploratory evidence for a broadly informative Bitcoin entry/exit risk indicator. Unit: completed monthly observation. Predictive association only, no causal claim. Root owns fixed-support comparisons for separate 12/24/48-month terminal-return, entry-loss and true-drawdown cells, direct conditional empirical CDF from the latest 24 mature labels at each origin, and subsequent pseudo-OOS replay. Four-year outer outcomes are not mature. No arbitrary horizon or wealth aggregate is used here. No hypothesis of a stable market cycle is imposed.

## Validation and restart

From this checkout, use `/private/tmp/risk-pr-review-wcp0ax41/python/bin/python -m unittest tests/test_swing_b_generator.py -v` (4 tests passed). Tests cover future-suffix perturbation/truncation, units invariance, finite outputs, current shock direction, malformed inputs, and incomplete-month exclusion. Three development-data prefix cutoffs also passed exact equality; generated support has 132 months, January 2012–December 2022.

Generate with `/private/tmp/risk-pr-review-wcp0ax41/python/bin/python research/candidates/swing_b/generator.py --inputs /private/tmp/risk-hillclimb-inputs-gj866s2j --output /private/tmp/swing_b_development.csv`.

Status: implemented and causality-tested; scoring pending root's locked evaluator. Next bounded step: evaluate only the three declared variants on development, log every result, preregister one finalist before outer replay. Open decision: none requiring user input; choice depends on the locked multi-cell Pareto comparisons. Root handles integration and push authorization.

Brief vs delivered: predictive scope, restricted inputs, deterministic generator, fixed parameters and causal tests delivered. Relative performance and uncertainty not yet answered. Primary alternative explanation for any apparent improvement is historical-cycle coincidence with few overlapping multi-year labels. Research changes are confined to this subtree and its tests; shared documentation needs no change until root integrates results. Skill-harvest/self-improvement review found no new general skill rule beyond existing causality, provenance and attempt-logging instructions.
