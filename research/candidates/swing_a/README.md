# Slow price-history anchor and occupancy memory

Research-only candidate; no production default or financial suitability claim.

## Question and alternatives

What useful state might the current indicator be missing? Existing market inputs
already contain instantaneous moving-average extension, annual return, an expanding
power-law deviation, drawdown and volatility. This candidate asks whether duration
of displacement from a slow price-history anchor adds information for multi-year
opportunity decisions. The anchor is not actual holder cost basis.

Three independent proposals were considered before looking at scores:

1. Slow price-history anchor plus persistent occupancy (selected): sustained cheap
   or expensive conditions may identify opportunity better than a momentary rank.
2. Expanding log-age trend residual: declining structural growth may distort
   expanding ranks. Rejected for first trial because origin/extrapolation assumptions
   dominate and production already includes an expanding power-law deviation.
3. Recovery hysteresis after drawdown: sustained recovery may reduce near-term
   downside conditional on cheapness. Deferred; mixes opportunity with tactical trend.

The falsifiable selected hypothesis is that occupancy improves 24/48-month return
ordering and conditional distributions relative to instantaneous displacement and
strong price references. Downside/entry loss are separate endpoints; deterioration
must be reported and cannot be offset by averaging horizons or outcomes.

## Frozen rules before scoring

Compute log price, an elapsed-time exponentially weighted anchor with 365-day
half-life, and `tanh(log_price-anchor)` displacement. Smooth displacement with a
180-day half-life. Risk = `0.5 + 0.5*((1-w)*displacement + w*memory)`.
Initial anchor is first observed log price; initial memory is zero. Before any
observation risk is neutral 0.5. First trial fixes half-lives/scale and compares
only `w=0`, `w=0.5`, `w=1` (three variants, including the no-memory ablation).
These are interpretable smoothing choices, not estimated economic constants.
No supervised labels, calendar turning-point dates or global normalizers are used.
Parameters were designed in November 2026; causal replay does not imply the model
was actually available historically.

Each observation becomes available one calendar day after its input date. All
transforms use past observations only; requested dates use last available score.
Invalid/duplicate dates and nonpositive/nonfinite prices fail explicitly. Missing
calendar dates advance smoothing using elapsed days; no invented daily observations.

## Data and provenance

Only `btc_daily.csv` in the parent's frozen development input bundle is used.
Its supplied end date is 2022-12-31; original vintage, close and publication timezone
are unverified. The one-day lag is conservative but does not prove historical
availability or protect against later revisions. No reconstructed incumbent feature
is consumed. Parent owns shared evaluation: separate 12/24/48-month return,
entry-loss and true-drawdown cells, latest 24 mature labels, comparable baselines,
2022 development cutoff and later mechanical pseudo-OOS replay. Overlapping Bitcoin
cycles provide weak independent replication; no pristine holdout is claimed.

## Verification and status

Six unit tests cover every monthly prefix, future perturbation including the query
date, scale invariance/bounds, invalid inputs/parameters and empty-history neutrality. Removing
the observation lag makes the perturbation test fail; the mutation was restored.
Run from repository root:

```
PYTHONDONTWRITEBYTECODE=1 /private/tmp/risk-pr-review-wcp0ax41/python/bin/python -m unittest discover -s tests -p 'test_swing_a*.py' -v
```

The local Python runtime has numpy 2.4.6 and pandas 2.3.3. Frontend dependencies and
.env are absent in this isolated checkout; neither is needed or installed. No
services, secrets or network sources were accessed. The three frozen variants have now been scored. See `RESULT.md` for the negative
family result and `finalist.json` for the no-memory diagnostic finalist. Parent
owns the next bounded step: frozen outer replay or archive; no promotion is recommended.

Brief vs delivered: predictive monthly Bitcoin indicator as briefed; development outcomes/comparisons are recorded in `RESULT.md`; market uncertainty
and financial suitability remain unestablished.
No shared/product documentation changes are needed for this isolated prototype.
Skill harvest/self-review: no global skill change justified by this bounded run.

Frozen-input smoke run: 4,018 daily observations (2012-01-01 to 2022-12-31)
yield 132 finite monthly outputs. Nonfinite-parameter guard mutation also fails
its regression test; restored before commit.
