# Path asymmetry research candidate

This isolated candidate record serves benchmark reviewers: it owns the hypothesis,
input caveats, and reproduction contract for this experiment. Shared methodology
and promotion decisions remain with the common benchmark owner. Update this file
when scoring completes; retain it with the source if the experiment is integrated.

## Preregistered finalist

`upside_energy_24m` uses monthly close log returns. Risk is 100 times the rolling
24-month sum of squared positive returns divided by the rolling sum of all squared
returns. Two returns are required; shorter or constant histories receive neutral
50. Higher scores mean hypothesized lower opportunity / greater risk. This direction
is a hypothesis, not established by an unsigned forecast-information statistic.
There is no supervised training or parameter fit. The 24-month parameter and
formulation were selected before scoring, using development information through
2022-12-31. Historical outputs are reconstructed, not evidence of a contemporary
2015 model choice. Online updates append a completed month and drop returns older
than 24 observations.

The falsifiable hypothesis is that upside-dominated large moves identify speculative
crowding and downside-dominated large moves identify better subsequent multi-year
opportunities. This could fail because squared returns discard order within the
window, crashes can persist, and upside bursts can represent durable adoption.
Ordinary momentum/RSI and strong price/time/cycle baselines may subsume the feature.
No investment policy or production setting changes here.

## Independent alternatives and input audit

Initial proposals ranked: price/volume growth divergence; path-asymmetry; lagged
Wikipedia attention surprise. The first was rejected before scoring: cached BTC
volume has unverified venue/unit continuity, median 523,615 in 2020 versus 84,840
in 2021, and maximum 4.47 billion in 2022. The attention alternative has coverage
only from July 2015 and creates time/coverage confounding. It was not implemented.
Existing onchain cache fields are derived proxies, not raw audited fundamentals:
`risk_engine/sources/onchain.py` constructs an expanding MVRV z-score and trailing
issuance-USD Puell ratio. Neither is used here.

Only `btc_daily.csv` Date and Price are read from the cropped development bundle.
Source hash: d6e0e23e4d84e32690cea42cc0bf69f44ddfe9d954939b54ba499635431ed04c.
Daily vintage, publication timing and UTC-close conventions remain unverified.
Month-end outputs use observations dated through that month end; incomplete final
calendar months are excluded. Appending future data cannot change prior outputs.
No post-2022 outcomes were inspected for model choice. Any later public-history
replay is pseudo-out-of-sample, not a pristine holdout.

## Reproduction and status

From the checkout, with the project's NumPy/pandas Python environment:

```sh
python -m unittest tests.test_swing_c
python research/candidates/swing_c/generate.py --input-dir INPUT_BUNDLE --output OUTPUT.csv
```

Four causal/domain tests pass. First candidate is implemented, not yet scored.
Next bounded step: run the locked common evaluator exactly once, record the result
(including failure), and compare per-horizon/per-outcome vectors without aggregating
away regressions. No production-suitability or financial-performance claim is made.
Skill-harvest review found no new reusable skill or existing-skill change warranted.
