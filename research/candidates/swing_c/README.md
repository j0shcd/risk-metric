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

Eighteen candidate and locked-evaluator tests pass. Exactly one preregistered trial
completed. The finalist is frozen unchanged for the root-owned outer replay; no
additional variants were tried. `development_trial.zip` preserves the complete
report, trial, request, receipt and candidate CSV; `attempts.jsonl` binds hashes.
Next bounded step: root reviews and replays the frozen producer, then determines
whether the narrow downside-information result survives. No production-suitability
or financial-performance claim is made.
Skill-harvest review found no new reusable skill or existing-skill change warranted.

## Locked development result

Lower CRPS is better. The candidate beats all fixed references for 12-month
entry loss and peak drawdown, but loses all other supported cells to at least one
reference. This is a narrow downside-information lead, not broad or Pareto
superiority. In particular, 24-month return forecasts lose substantially to the
unconditional CDF. Positive ordering alignment does not establish forecast skill.
There are zero mature 48-month development forecast queries.

| Months | Outcome | Forecast n | Candidate CRPS | Context CRPS | Unconditional CRPS | Best fixed reference | Alignment |
|---:|---|---:|---:|---:|---:|---|---:|
| 12 | terminal_log_return | 48 | 0.858303 | 0.854808 | 0.858520 | calendar_cycle_cos_4y (0.810894) | 0.476582 |
| 12 | entry_adverse_log_loss | 48 | 0.343475 | 0.353230 | 0.361899 | calendar_cycle_sin_4y (0.351166) | 0.275567 |
| 12 | peak_drawdown_log_loss | 48 | 0.243514 | 0.263792 | 0.282293 | calendar_cycle_sin_4y (0.260172) | 0.420999 |
| 24 | terminal_log_return | 24 | 0.461353 | 0.453800 | 0.331074 | time_years_since_2012 (0.411880) | 0.575728 |
| 24 | entry_adverse_log_loss | 24 | 0.242418 | 0.238338 | 0.249353 | price_drawdown_12m (0.227048) | 0.361170 |
| 24 | peak_drawdown_log_loss | 24 | 0.300288 | 0.297130 | 0.300568 | price_ath_drawdown (0.274003) | 0.262633 |
| 48 | terminal_log_return | 0 | — | — | — | — | 0.232848 |
| 48 | entry_adverse_log_loss | 0 | — | — | — | — | 0.463560 |
| 48 | peak_drawdown_log_loss | 0 | — | — | — | — | -0.131089 |
