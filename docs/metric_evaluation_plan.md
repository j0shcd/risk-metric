# Indicator benchmark and evaluation plan

Status: design proposal, not implemented. Updated 2026-11-06.

This is the canonical plan for the next benchmark. Current implemented results
remain in [DCA evidence](dca_evidence.md). This replaces the older Phase 1/2
planning narrative; Git preserves its implementation history. Production scoring,
acceptance policy, canonical metrics and publication behavior are unchanged.

## Accepted requirements

Josh confirmed separate accumulation/opportunity and de-risking assessments,
with accumulation the primary use case. He then clarified the more important
constraint: the metric must be broadly useful as an information indicator.
Optimizing wealth under one arbitrary contribution/trading strategy is not the
right primary objective. Equal contributions alone do not control invested
capital or exposure. Strategy simulations are supporting evidence.

The benchmark must support many model ideas, limit adaptive overfitting, remain
representative of long-horizon use, and test situations outside the development
sample. No combined wealth/drawdown utility is accepted. Exact scoring and the
proposed 12/24/48-month outcome contract remain proposals pending review.

## Decision served and scope

- Decision: whether a candidate indicator adds useful information beyond the
  incumbent and simple public price information, and deserves further shadow
  evaluation. This is predictive research, not causal attribution or investment
  advice.
- Unit: one asset, one executable monthly entry timestamp and one fixed horizon.
  Every indicator faces the same opportunities, not its preferred trading dates.
- Availability: only information actually available at decision time may be used.
- Outcomes: future return/opportunity and intervening downside, assessed separately.
- Audience: Josh and future maintainers designing and implementing the benchmark.
- Deliverable now: reviewed research and an implementation specification. No new
  model, training campaign, data vendor or production-gate change in this task.
- Constraints: local/offline development, reproducible snapshots, bounded compute,
  existing free infrastructure; no incidental paid services.
- Expected useful negative result: a candidate has no incremental information, is
  fragile across eras, or cannot be evaluated with the available mature outcomes.
  Each is a valid result, not a reason to loosen the benchmark after a run.

## 1. Separate four kinds of test

| Layer | Question | Role |
| --- | --- | --- |
| Integrity and causality | Are inputs, timing, accounting and identities valid? | Deterministic requirements; failures invalidate a run |
| Indicator information | Does the score distinguish future outcomes on identical opportunities? | Primary development leaderboard |
| Economic usefulness | Does that information help across predeclared decision rules and capital controls? | Supporting evidence and trade-offs |
| External and prospective evaluation | Does it survive new market contexts and predictions frozen before outcomes? | Generalization evidence, separately reported |

A strategy winner is not automatically a better indicator. A synthetic winner is
not independent market evidence. A better historical information score is not a
guarantee of better future outcomes. Keep those distinctions in artifact schemas.

## 2. Make the primary comparison apples-to-apples

At every eligible monthly decision time, define an identical hypothetical $100
BTC purchase for every indicator, executed at the next declared executable
price and held for exactly H months. Apply the same execution convention and
costs. This is an outcome-measurement ticket, not a strategy that allocates money.
Indicators predict every ticket; they cannot choose its size, dates or inclusion.

Measure at least:

- Terminal log return, optionally relative to the identical $100 cash ticket.
  The benchmark version must freeze the cash-return convention. Use investable,
  date-available cash returns where available; retain the existing flat 3% only
  as an explicitly artificial sensitivity, not assumed historical financing.
- Maximum adverse excursion from entry: the largest loss relative to entry price.
- True peak-to-trough drawdown over the subsequent path, including entry.
- Maximum favorable excursion from entry, as an opportunity diagnostic.

All are per dollar invested. $100 is merely a readable normalization. Each
indicator sees the same prices, holding periods and exposure for these tickets.
Tickets overlap and must not be presented as simultaneously fundable independent
portfolios. Cross-market comparisons require total returns where relevant,
common currency/financing definitions and explicit market calendars.

Freeze the timestamp universe from source availability and common warm-up rules
before candidates run. A candidate cannot improve by dropping hard dates,
returning missing values or changing its own evaluation start. Publish coverage
and fallback behavior; distinguish unavailable from a neutral indicator value.

### Capital controls in supporting simulations

Report separately: contributions, initially invested capital, average exposure,
capital-time in market, turnover, costs and cash yield. Equal funding is one
accounting control, not evidence that invested exposure was equal.

Use fixed-notional/fixed-horizon tickets for clean information comparisons. For
actual timing-policy tests, compare with predeclared constant allocations and
controls matched on declared exposure budgets/trade counts where feasible.
Average-exposure matching is a diagnostic, not identical pathwise risk. Matching
BTC exposure at every timestamp would remove the timing difference itself.
Do not claim all these constraints can be satisfied simultaneously by arbitrary
adaptive strategies. State exactly which comparison is controlled.

## 3. What 'higher is better' can mean

### First implement an ordinal development benchmark

The current indicator is an ordered index, not a forecast probability. Evaluate
its declared meaning directly before fitting a decoder that might conceal it.
For opportunity, compute fixed-direction Kendall rank concordance between
negative risk and forward terminal return. For downside, compute concordance
between positive risk and the magnitude of future loss. Ties, minimum coverage,
aggregation weights and missing-outcome handling must be specified in the
benchmark configuration. A constant indicator has no discrimination.

Properties required of this score:

- A strictly increasing rescaling cannot improve ordering. Rounding, clipping
  and binning can introduce ties and count as candidate changes.
- Reversing its economically declared direction cannot be repaired by selecting
  the opposite sign after seeing outcomes.
- Identical dates and outcomes are used for incumbent, candidate and price-only
  references. Compare paired differences, not separate convenient samples.
- Scores are reported per horizon and era, with outcome magnitudes beside them.
  Good ordering of tiny differences is not automatically economically material.

Proposed horizons: 12, 24 and 48 months, with separate opportunity and downside
leaderboards. A headline within a family may use equal frozen horizon weights,
but must show every constituent and cannot promote a candidate by hiding a
material four-year regression. Do not pool return and downside into one utility.
Until the horizon decision is accepted, keep this as a proposal.

This is a retrospective discovery score, not a confirmatory p-value or a
probability of profit. Nonlinear conditional information that contradicts the
advertised ordering is an exploratory finding, not a passing ordinal indicator.

### Add proper forecast scoring when calibration is supportable

A stronger information test evaluates distributions of those outcomes. Use a
proper loss such as CRPS for continuous forecasts, and Brier loss for a small
registered set of interpretable binary events. Avoid optimizing one convenient
return/drawdown cutoff. Proper losses reward honest forecasts in expectation;
they do not guarantee generalization after adaptive selection. See
[proper scoring rules](https://scoringrules.readthedocs.io/en/latest/theory.html).

For each outcome/horizon, define the development skill display as:

`skill = 100 * (1 - sum(weight * candidate_loss) / sum(weight * reference_loss))`

The reference and weights are common and frozen for all candidates. Zero means
matching that reference; positive means lower forecast loss. Fail visibly if the
reference loss is zero or required forecasts are missing. Optimize raw proper
loss; the realized skill ratio is a reporting normalization, not an additional
strict-propriety guarantee. Report CRPS on log returns explicitly as log-return
forecast quality, not wealth growth.

An ordinal indicator needs the same tiny causal readout for every candidate.
Start by testing a fixed regularized location model, with the indicator's slope
constrained to its declared direction and a common residual-distribution method.
Freeze capacity, regularization and update schedule before candidate selection.
Use a common training-only empirical-percentile input transform, with frozen tie
and out-of-range rules, so a 0–100 rescaling cannot change effective shrinkage.
Test positive affine and strictly increasing rescaling invariance of the readout.
Fit only on mature training labels. Do not search a decoder separately for each
indicator, invert a failed indicator, or use a full-history empirical mapping.
This evaluates the indicator plus that registered readout; raw ordinal results
remain visible so readout limitations are not mistaken for all possible information.

Two required comparisons:

1. Indicator-only readout versus a training-history unconditional distribution.
2. Fixed price-only context plus the indicator versus the same context without
   the indicator, with the same fitting rules and regularization policy.

The second measures incremental information beyond price context. Report
context-only and indicator-only ablations so an elaborate context model cannot
receive credit as indicator improvement. All readout/feature choices count as
experiments. If mature data cannot support the readout, return
`insufficient_evidence`; do not silently replace a failed forecast score with a
more flattering rank score. Rank and forecast protocols have distinct versions.

### Test broad usefulness beyond one scoring preference

For registered probability/quantile forecasts, add Murphy diagrams: compare
expected losses across a range of decision thresholds within a defined scoring
class. If curves cross, report the trade-off rather than declaring universal
superiority. Dominance within that class is stronger evidence of broad usefulness
than success at one threshold, but is not dominance for every financial strategy.
See [Ehm et al.](https://arxiv.org/abs/1503.08195).

Keep policy-independent region distributions, reliability, calibration and tail
misses visible. Proper scores, rank ordering and economic effect sizes answer
related but different questions; none should erase the others.

## 4. Chronological fitting, selection and evaluation

Do not randomly split days or use a generic 60/20/20 percentage split. Maintain
actual intervals for observation, availability, fitting, decision, execution,
outcome completion and label availability.

For a prediction at cutoff T:

1. Fit features, imputers, normalizers, embeddings and calibrators only using
   information available by T. Past feature look-back may provide causal context;
   it is not automatically another label-length embargo.
2. Train on a label only after its complete outcome and publication lag have
   resolved. Define `outcome_end = execution_time + H`, not decision time plus H;
   require `label_available_at <= fit_cutoff`. Execution lag is part of maturity.
3. Run inner chronological validation for parameter/feature/policy selection;
   every outcome used to select the winner must also have resolved before T.
4. Freeze the selected procedure and issue the next outer block's predictions.
   For an online model, freeze its update rule and replay the event order exactly.
5. Stitch outer predictions into a causal stream. Freeze each ticket's forecast
   at its entry decision; score that forecast only against its own later outcome.
   Subsequent retrains affect new tickets, never an older ticket's prediction.
   Supporting adaptive policies may update during a portfolio holding period,
   but that is a separate test.

Purge intersecting target/selection-outcome intervals. In a purely expanding
past-to-future fit, maturity rules already exclude unresolved labels; avoid
blindly applying a second 48-month gap. Any two-sided diagnostic requires its own
purge/embargo and is not a deployable walk-forward estimate. Generic
[TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
is a building block, not a substitute for this interval audit.

### Feasibility, not fictional fold counts

The inspected stored score spans December 2014 through July 2026: 140 monthly
values and 92 nominal completed 48-month entry outcomes. These are overlapping,
not 92 independent four-year histories. At January 2019/2020/2021/2022 only
1/13/25/37 monthly 48-month training labels, respectively, have matured from that
score history. A calibrated stream starting January 2021 has only about 19
nominal completed four-year entry predictions in that stored table. These are
illustrations from the old timestamp convention, not v2 eligibility counts.
Recompute them using actual execution and label-availability times, and after
rejecting incomplete month-end bins: the stored daily artifact ends July 30 but
the current resampler stamps its last value July 31.

Therefore do not promise a well-powered deeply nested four-year ML benchmark.
The implementation must generate a feasibility table per outcome, candidate
warm-up and fit date before launching a search. It must show raw starts,
nonoverlapping episode coverage and sensitivity to start offsets. These counts
are not an estimated effective sample size. Refuse unsupported fits rather than
quietly shortening the target or fitting through future labels.

Shorter training targets or self-supervised state estimation may be useful;
the model's learning target need not equal the investor evaluation horizon.
Their success does not validate a four-year claim. Longer external histories
can extend a separately labeled transfer track, not backfill unavailable BTC
on-chain inputs or pretend the present indicator existed earlier.

### Separate development feedback from promotion

- Development: chronological folds and historical robustness, fully visible and
  reusable, explicitly exploratory. Record every adaptive attempt.
- Restricted audit: evaluate a frozen finalist bundle occasionally, through a
  separate runner with limited feedback and independent artifact permissions
  where feasible. Repository-local hiding is not a security boundary. History
  already examined remains retrospective even if now named 'test'.
- Prospective shadow: archive inputs, score, forecasts, model/update state and
  identities before the outcome begins. This supplies genuinely fresh outcomes.

A future test period may be used for training only after its labels mature and
its scheduled predictions were frozen. Keep each prediction's evidence lineage.
Continuous online fitting is allowed by a frozen protocol; retrospective
rewriting of its earlier predictions is not.

## 5. Search governance and uncertainty

No finite, dependent BTC history supports an unlimited trustworthy hill climb.
More seeds, synthetic draws and fold permutations do not replenish independent
market evidence. [Adaptive holdout research](https://arxiv.org/abs/1506.02629)
and [the Ladder](https://proceedings.mlr.press/v37/blum15.html) address feedback
leakage under specific assumptions; score rounding or a pass/fail response alone
does not confer their guarantees on this time series.

Proposed first campaign: at most 24 predeclared configurations, including manual
variants, with a fixed small seed set where needed. Freeze one finalist and a
simple comparator before the audit. This is a practical research budget, not a
statistical confidence guarantee. Log abandoned/failed runs and benchmark changes
as well as winners. Resetting the run directory does not reset the trial count.

Record candidate code/config, dataset and benchmark versions, parent candidate,
hypothesis, features, fitting recipe, seeds, complete timestamped predictions,
all component losses, eligibility, cost/runtime and failure reason. Hash the
benchmark separately from the model; a candidate cannot edit its own scorer,
weights, population or audit runner. A changed benchmark requires re-evaluating
all reference models on the same snapshot, not moving the winning threshold.

Use paired calendar blocks/eras for dependence sensitivity, with several
predeclared block lengths. Four-year outcomes can remain dependent over four
years or longer. If there are too few blocks for reliable intervals, report that
rather than narrow intervals from monthly row bootstrap. Do not replace uncertainty
with `floor(n / horizon)` or present circular-shift ranks as formal significance
without exchangeability/stationarity justification.

Keep all-trial selection diagnostics separate from predictive loss. PBO/CSCV can
show ranking instability but is not a chronological deployment simulation;
Deflated Sharpe applies to a different return objective. SPA/Reality Check may
help compare a registered family of loss streams if their dependence assumptions
are defensible. None repairs unrecorded adaptive human choices or a tiny sample.
See [PBO](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) and
[bootstrap multiple comparisons](https://arch.readthedocs.io/en/latest/multiple-comparison/multiple-comparison_examples.html).

Stop a campaign when improvements disappear across eras, reflect missing-date
selection, depend on narrow settings, or do not add information beyond price.
Require absolute usefulness versus simple references as well as an incumbent
improvement for promotion; 'less bad' remains a research improvement. Statistical
readiness rules and practical margins must be frozen before outcomes are scored.
No development-score-only automatic production promotion.

## 6. Synthetic and cross-market suites

Synthetic data is a robustness laboratory and harness test, not additional
independent evidence about Bitcoin. Keep synthetic and real-data scores separate.
Use fixed development scenarios plus fresh audit seeds drawn from a frozen
parameter distribution; fresh seeds prevent memorization of paths, not misspecification
of the generator itself. Fit generators on training data only.

| Scenario family | What it tests |
| --- | --- |
| Geometric Brownian/random-walk null, with declared drift | No spurious conditional skill beyond drift/base rate |
| Planted observable signal, plus inverted/noisy/constant variants | The evaluator can recognize information and reject false confidence |
| Persistent bull and prolonged decline | Exposure drag and indicator behavior under one-way conditions |
| Crash/fast recovery, slow recovery, permanent loss | Timing asymmetry and failure of automatic mean-reversion assumptions |
| Heavy tails, volatility clusters, regime breaks | Robustness beyond Gaussian constant-volatility assumptions |
| Flat volatile market | Churn and false alarms in supporting policies |
| Delays, stale/missing inputs, source outage, 0% cash yield, higher costs | Availability, fallback and accounting robustness |

Plain Brownian motion is one null model, not a realistic replacement for market
history. Block/stationary resampling can preserve some dependence; examine
multiple block lengths and seams, and state stationarity assumptions.
[Politis–Romano](https://statistics.stanford.edu/technical-reports/stationary-bootstrap)
provides the resampling foundation, not a guarantee for nonstationary BTC cycles.

Recompute price features on each synthetic path. Never attach original on-chain
or macro histories to unrelated simulated prices. Start with price-only
simulations and separate input-failure tests. Joint simulations must preserve
specified cross-variable relationships; bootstrapping blocks is not automatically
valid for cumulative stocks, accounting identities or revised macro series.
Do not classify a higher synthetic score as a historical-market improvement.

Use S&P/Nasdaq, gold and other broad market families as a separate price-only
transfer/generalization track. Split all assets by the same calendar boundary;
otherwise correlated crises can leak across assets. Weight asset families rather
than counting overlapping indices as independent universes. Hold out both eras
and entire market families for transfer audits. Report cold-start and warm-start
procedures separately. Include total-return conventions, tradability, revisions,
survivorship, licensing and calendar differences in the data manifest.

Long public return histories such as the
[French research portfolios](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
can support this track. They do not validate BTC-specific features, and current
historical files can be revised. Shared global shocks limit independent replication.

## 7. Candidate research queue

These ideas change models or inputs, not the benchmark contract. Use the same
protocol for every family; add complexity only after failure analysis justifies it.

| Idea | Recommended role and order | Main safeguard |
| --- | --- | --- |
| Existing four components and their ablations | First reference family; test redundancy and incremental information | Same coverage and causal recomputation |
| Log returns, trailing trend/drawdown/volatility, EWMA and causal robust normalization | First small feature family, with fixed windows | No full-history fitting or centered smoothing |
| Regularized linear/additive models; shallow RF/boosted trees | First learned candidates | Capacity limits and chronological feature selection |
| Seasonal/Fourier time features | Small, hypothesis-led ablation | No absolute-date memorization; do not assume a sinusoidal four-year BTC cycle |
| Macro regime, rates, inflation, employment, credit/liquidity | Small economic groups after vintage support | Observation date is not publication date; use as-of vintages |
| Online/decay-weighted learning and change detection | Compare with fixed/expanding-window updates | Predict, freeze, wait for labels, then update; adaptation is part of the candidate |
| Anomaly scores, PCA/autoencoders and embeddings | State/uncertainty features; possible abstention inputs | Unusual does not mean buy/sell; causal fitting and coverage penalties |
| Ensembles | Start equal-weight or heavily shrunk combinations of diverse out-of-fold signals | Meta-learner trains only on causal out-of-fold predictions; shared errors remain shared |
| Transformers/foundation models | Later capped experiment, not the default | Training-cutoff/contamination audit; compare with simple models at equal data/compute |

Macro expansion should start with a few economic groups rather than hundreds of
correlated transforms. Existing sources already include DXY, real yields, Fed
balance sheet and reverse repos. ALFRED supports historical knowledge dates;
[the official documentation](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html)
explains why today's revised history is different. [FRED-MD](https://www.stlouisfed.org/research/economists/mccracken/fred-databases)
is a useful discovery/transform reference, not automatically a point-in-time panel.

Online learning can adapt unsupervised state promptly, but cannot observe an
unresolved four-year label. Drift alerts are not hindsight regime labels or
permission to retune against outer outcomes. Delayed progressive validation is
the relevant pattern; [River's implementation](https://github.com/online-ml/river/blob/main/river/evaluate/progressive_validation.py)
is a reference, not an adopted dependency. Ensembles need complementary useful
signals; averaging many correlated or directionless models creates no information.

## 8. What existing benchmarks contribute

| Reference | Reuse conceptually | Does not establish |
| --- | --- | --- |
| [Qlib](https://github.com/microsoft/qlib/blob/main/examples/benchmarks/README.md) | Reproducible model workflows, signal and portfolio reporting | Four-year BTC indicator validity |
| [FinRL](https://finrl.readthedocs.io/en/latest/finrl_meta/Environment_layer.html) | Controlled market environments and transaction-cost accounting | A universal investment reward or need for RL |
| [GIFT-Eval](https://arxiv.org/abs/2410.10393) | Common forecasting protocols, baseline diversity and contamination discipline | Profitability or Bitcoin-specific information |
| [TSB-AD](https://proceedings.neurips.cc/paper_files/paper/2024/hash/c3f3c690b7a99fba16d0efd35cb83b2c-Abstract-Datasets_and_Benchmarks_Track.html) | Anomaly-data integrity and careful detector metrics | That anomalies predict investment direction |
| Proper forecast scores and Murphy diagrams | Truthful forecast objectives and comparisons across defined decision preferences | Unlimited adaptive reuse or every user's utility |

Recommendation: keep a small repository-owned evaluator and use these as research
references. No framework migration or new runtime dependency is selected here.

## 9. Current implementation, defects and next bounded work

Inspected at local HEAD `37fbd99` on 2026-11-06. The existing compact evaluator
reran in 2.72 seconds on stored inputs in the preceding assessment; this excludes
model generation. Its current three-test results are faithfully recorded in
[DCA evidence](dca_evidence.md). That does not validate the proposed protocol.

| Capability | Current state | Required delta / acceptance |
| --- | --- | --- |
| Unit/regression infrastructure | Implemented; focused tests available | Preserve and add boundary tests that fail under reintroduced defects |
| Fixed-notional multi-horizon outcome table | Not implemented as the primary benchmark | Common timestamps, executable dates, complete outcomes and named loss conventions |
| Ordinal information score | Existing region diagnostics only | Continuous fixed-direction ranks, ties, invariance tests and paired baselines |
| Forecast readout and skill | Not implemented | Mature-label fit audit; tiny common decoder; insufficient-evidence state |
| Chronological benchmark | Partial walk-forward label/threshold sidecar | Audit complete model fitting, candidate selection and online updates |
| Baseline identity | File hashes and canonical summary exist | Immutable retained dataset; incumbent rerun on identical bytes |
| Experiment registry | SQLite run index/artifacts exist | Candidate lineage, all attempts, predictions, benchmark identity and audit access |
| Prospective archive | Release records and inputs exist | Candidate/readout/update-state lineage and outcome-resolution evaluator |
| Synthetic / external suite | Not implemented as specified | Separate evidence tiers, coherent generators and synchronized cross-asset splits |
| Supporting policy accounting | Implemented but multiple variants remain | One explicit contract per test; capital/exposure controls and reporting |

Verified issues to resolve before policy/outcome optimization:

- `_relative_window_rows` uses varying-length suffixes ending at one date. Use
  exact horizons for the new outcome table; keep suffix reports diagnostic only.
- `_accumulation_ledger` starts buying one contribution per month after position
  48, not clearing old cash. A 60-month flat-price/high-risk reproduction bought
  only 12 units of contribution and retained about 52.42 in cash including yield.
  Decide maximum contribution age versus a cash limit before implementing any
  'deployment deadline'; a maximum-age rule must own a FIFO cash-lot invariant.
- `_forward_outcomes` names entry-relative minimum return 'forward_max_drawdown'.
  A price path 100 -> 200 -> 80 yields -20% there, versus true drawdown -60%.
  Distinct names and a boundary regression must prevent semantic conflation.
- `effective_observations = floor(n / horizon)` is a rough coverage heuristic,
  not estimated effective sample size. Rename/report actual coverage explicitly.
- The acceptance availability boolean only rejects the literal `missing_rule`;
  it does not establish real-time vintage eligibility. Unknown/estimated
  availability must remain explicit and cannot support point-in-time claims.
- Current cached input fingerprint differs from the canonical summary. Recover
  and verify the canonical snapshot, or version and rerun every reference on a
  new snapshot. Never copy a new hash onto old metrics to make comparison pass.
- The month-end resampler can stamp an incomplete month as its future month end.
  Freeze as-of dates and require complete outcome horizons before scoring.

### Implementation sequence

1. **First bounded slice:** versioned immutable dataset/benchmark manifests and
   fixed-notional outcome table, with interval/split feasibility report. Test
   cash/price scale invariance, identical sample support, execution-based label
   maturity, forecast immutability after retraining, future-suffix stability,
   incomplete periods and adverse-excursion/drawdown semantics.
   Do not launch candidate searches or replace CI acceptance yet.
2. Add ordinal paired leaderboard, fixed references, candidate registry and
   historical era sensitivity. Mutation-test direction, missing-date selection,
   monotone rescaling and future leakage. Freeze development/audit roles.
3. Assess whether a tiny causal readout is supportable; add forecast scoring and
   incremental-information comparisons with explicit unavailable states. Test
   constant, inverted, random, planted-signal and overconfident sentinels.
4. Add separate synthetic/transfer tests and supporting economic panels. Audit
   generator seams, reference financing, exposure controls and policy invariants.
5. Run the predeclared small campaign. Freeze its finalist, audit, then record
   prospective predictions. Revisit richer models only on a concrete diagnosis.
6. Replace the production acceptance contract only after the indicator benchmark
   is reviewed and verified. ADR 0008 and existing canonical metrics describe the
   current policy gate until then; do not silently rewrite them as implemented.

### Genuinely open decisions

- Confirm the proposed return/downside outcome contract at 12/24/48 months.
  The glossary currently says approximately six months; the gate uses 48 months.
  Reconcile the glossary and ADRs when the new contract is accepted.
- Freeze exact family/horizon weights and materiality/non-regression margins
  before the first campaign. No cross-family scalar utility is proposed.
- For supporting accumulation policies, define permitted cash deferral precisely.
  This does not block the indicator-only fixed-notional outcome slice.
- A sealed historical audit remains limited by prior researcher exposure. Record
  its actual access boundary; only future frozen predictions can be prospective.

## Verification and handoff

This task inspects and specifies the benchmark; it does not demonstrate that a
new model is better. No new dataset was downloaded, generator fitted, or model
trained. The Astra medium collaborator supplied an independent design and then
revised it following the indicator-first correction; its claims were checked
against owning code and primary sources before inclusion.

The implementation plan now serves the requested information-indicator goal;
strategy-specific wealth optimization is explicitly outside the primary score.
Historical data quality, vintage eligibility, calibrated-readout feasibility,
benchmark false-positive rates and external-market transfer remain unverified.
The strongest alternative explanation for an apparent future leaderboard gain
will be adaptive fitting to a few shared market eras. Keep that risk visible.

Changes here are a specification, not new accepted model behavior. Record the
focused verification result and commit/publication status with the handoff.
