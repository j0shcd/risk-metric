# Indicator benchmark and evaluation plan

Status: finite known-law panel qualification passes; earlier single-path searches
remain failed. Seven indicator variants and two readout studies show no broad
improvement. One generative baseline adds stronger partial benchmarks but fails
the primary two-year return comparison and long-horizon calibration. No promotion.
Updated 2026-11-07.

This is the canonical plan for the next benchmark. Current implemented results
remain in [DCA evidence](dca_evidence.md). This replaces the older Phase 1/2
planning narrative; Git preserves its implementation history. Published scoring,
acceptance policy and canonical metrics are unchanged. Local producer causality
corrections below are unaccepted source revisions and have not been published.

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
outcome contract remain unaccepted. In review, Josh challenged whether fixed
notional returns and a 12/24/48-month grid constitute a robust target. They do
not by themselves. Withdraw the horizon average and ordinal rank score as the
proposed primary leaderboard; retain them as candidate diagnostics. Capital
normalization is necessary for comparison but does not validate an objective.

The research pilots demonstrate why the IID threshold and one location-only
readout cannot serve as a long-horizon market gate. A retrospective scorecard now
provides useful measurements without adopting a product utility or a total ranking.
Settle the indicator's specific informational claim before promotion. Qualification
must test the entire selection procedure against no-signal and planted-signal
worlds; simulation results remain conditional on their generators, not evidence
of real-market generalization.

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
- Deliverable: reviewed design, bounded synthetic experiments and an operational
  retrospective market scorecard with portable data and an exposure ledger.
  Research readouts are fitted; production market models are unchanged. No
  adopted investor objective, data vendor or production-gate change.
- Constraints: local/offline development, reproducible snapshots, bounded compute,
  existing free infrastructure; no incidental paid services.
- Expected useful negative result: a candidate has no incremental information, is
  fragile across eras, or cannot be evaluated with the available mature outcomes.
  Each is a valid result, not a reason to loosen the benchmark after a run.

## Implemented retrospective scorecard

This is a trustworthy **measurement instrument within a narrow scope**, not a
qualified automatic financial optimizer. It compares the incumbent, its four
components and price-only references on identical historical opportunities.
New candidates use the same frozen data, dates, outcomes and readout. There is
no aggregate winner, significance declaration or promotion command.

To reproduce the retained baseline using the committed, already-exposed snapshot:

```bash
mkdir -p output
python -m research.market_scorecard create \
  --snapshot docs/artifacts/market-scorecard-2026-11-06-snapshot.json \
  --campaign output/market-scorecard-replay \
  --diagnostic-horizons 12 24 48
python -m research.market_scorecard verify --campaign output/market-scorecard-replay
```

The destination must be new, below an existing parent without symlink components.
For a new reconstructed source, replace `--snapshot ...` with
`--source output/risk_scores_full.csv`; this changes the dataset identity when
the bytes change. Neither command updates production, contacts APIs or opens a
browser. The diagnostic horizon grid remains an implementation coordinate, not
an accepted primary investor objective. Copying a campaign or snapshot does not
restore unseen evidence.

`research/market_dataset.py` freezes complete month ends, a next-daily-close entry
and an endpoint exactly H calendar months from entry. It requires every daily
price in that path to be finite and positive; no forward-fill, last-finite-value
carry or partial-month stamping is allowed. Outcomes are terminal log return,
entry adverse **log loss** and true peak-to-trough **log loss**, with both losses
nonnegative. A 100 → 200 → 80 path has different entry loss and peak drawdown.
These daily-close losses miss intraday troughs. Log ratios are invariant to price
currency scaling and hypothetical ticket size; no contribution schedule, cash
deferral, varying exposure, interest or trading policy enters the score. This
solves common-outcome accounting; it does not establish equal risk for adaptive
investment policies.

Historical input vintages and the source's UTC/executable close convention remain
**unverified**. The snapshot preserves that status. The one-day observation-to-entry
lag is a hypothetical research convention, not proof that historical macro inputs
or reconstructed scores were available then. These results cannot be relabeled
point-in-time or prospective. This BTC snapshot includes no newly acquired macro
inputs; the separate monthly equity falsification fixture is described below.

The scorecard has two separate panels within each target/horizon:

- Fixed-direction ordinal alignment: higher risk should accompany lower return
  or greater downside loss. Constant features/outcomes have no defined alignment.
  No favorable sign is chosen after observing outcomes. Price references are
  undirected and receive no advertised risk-ordering score.
- Distribution forecast loss: exact weighted empirical CRPS for a fixed finite-bin
  decoder. Lower paired loss, or higher skill relative to the same reference, is
  better **for that defined forecasting task and decoder**. It is not conditional
  mutual information, every user's utility, profitability or proof of novel signal.

The context is trailing 12-month log return and 90-day daily-return volatility.
At every scored origin the last 24 mature calibration rows are chosen first;
the 24 fitting rows must have labels strictly mature before the first calibration
decision. No fitting/calibration overlap is permitted. Feature median thresholds
use fitting features only. Calibration labels supply the probability atoms.
Reference and augmented forecasts both mix 50% pooled calibration mass with
50% their respective context or context-plus-indicator cell. Empty augmented
cells fall back exactly to the reference, without deleting an outcome. A duplicate
context feature cannot gain merely by changing shrinkage. Each forecast retains
its dates, thresholds, atoms, weights, quantiles and fallback counts.

This decoder can use distributional differences, including scale, and can learn
either direction. The separate alignment panel checks the advertised direction.
The 50:50 shrinkage and median bins are explicit modeling choices. Finite/coarse
context can make redundant features useful to this decoder; coarse bins can also
hide real information. A gain compares context-plus-candidate with context; the
side-by-side incumbent result is **not** a test of incremental information given
the incumbent. There is no IID confidence interval over overlapping origins.

The retained [scorecard summary](artifacts/market-scorecard-2026-11-06.json) binds
the full local report through its receipt. The [portable snapshot](artifacts/market-scorecard-2026-11-06-snapshot.json)
reproduces the exact benchmark identity under the recorded runtime. Baseline dates
are December 2014–June 2026; July 30 is excluded as incomplete.

| Diagnostic horizon | Mature ordering origins | Forecast origins | Forecast dates |
| --- | ---: | ---: | --- |
| 12 months | 127 | 55 | December 2020–June 2025 |
| 24 months | 115 | 19 | December 2022–June 2024 |
| 48 months | 91 | 0 | Insufficient evidence |

These are dependent origin counts, not effective independent sample sizes. The
incumbent's 12-month forecast skill is negative for all three endpoints; at 24
months its return skill is +1.51%, entry-loss skill +3.10%, and drawdown skill
approximately zero, across only 19 overlapping origins. Four-year opportunity
ordering has the wrong sign. Those are exploratory measurements, not significance
or a recommendation to optimize toward whichever row currently looks best.

Custom submissions are JSON objects with a name, fixed `direction` of
`higher_risk` or `undirected`, a nonempty `provenance` description, and `values`
containing exactly the snapshot's ordered monthly dates and finite scalar values:

```json
{"name":"candidate-v1","direction":"higher_risk","provenance":"describe inputs and reconstruction limits","values":[{"date":"2014-12-31","value":0.5}]}
```

The example shows one row; a real submission needs every frozen date, including
all fitting/calibration dates. Extra, missing or duplicate dates are rejected.
Submit with:

```bash
python -m research.market_scorecard submit \
  --campaign output/market-scorecard-replay --candidate output/candidate.json
```

The immutable baseline never changes. Before scoring, the tool atomically reserves
one of 24 custom attempt directories and records the exact payload. Failed and
interrupted attempts consume slots; identical reruns also count. Exclusive receipts
bind input/output bytes, campaign/dataset/slot ownership, code and runtime. A
changed runtime/code, corrupt prior result or moved receipt rejects replay. An
interrupted attempt has no valid `COMPLETE`; it remains consumed. The ledger is
a local governance aid, not tamper-proof access control or a correction for all
prior research. It cannot justify unlimited adaptive reuse or create a holdout.

## Registered whole-path search: qualification failed

`research/search_qualification.py` tests a **different, explicitly fixed four-phase
synthetic selection procedure**, sharing the scorecard's finite-bin decoder. It
does not qualify the market scorecard's rolling procedure or supply its promotion
threshold. Run with a new destination:

```bash
python -m research.search_qualification --output-dir output/search-qualification-new
```

Before generating worlds, the runner writes its source hashes, runtime, seed and
criteria. Each independent 720-step world searches 24 noisy indicators across
three horizons and three outcomes: 216 development comparisons. It selects once
on development, then evaluates only that choice on audit. All horizons share phase
boundaries governed by the longest label: no short-horizon audit starts before
long-horizon selection information resolves. Every development attempt is retained.
Twenty-four fitting/calibration/development/audit rows remain overlapping and are
not treated as independent. The underlying monthly paths and feature availability
are synthetic, not market-vintage reconstructions.

There are 500 calibration worlds for each of three predeclared null families:
Gaussian prices with score persistence .5 or .95, and clustered heavy-tailed t(3)
returns with score persistence .95. Null scores are independent of all price and
context paths. The 476th ordered score calibrates each 5% threshold; their maximum,
**20.3529%**, is used for strict audit exceedance. Fresh evaluation has 200 worlds
per null and per planted location/scale family. The registered criteria require
each null's one-sided 98.333% binomial upper bound ≤10%, and each plant's one-sided
95% detection lower bound ≥80%. Rate bounds condition on this threshold realization;
threshold calibration variability was not evaluated.

The [retained result](artifacts/search-qualification-2026-11-06.json) fails:

| Family | Flags / 200 | Rate | Registered bound | Pass |
| --- | ---: | ---: | ---: | --- |
| Gaussian, score persistence .5 | 1 | 0.5% | upper 2.99% | yes |
| Gaussian, score persistence .95 | 8 | 4.0% | upper 8.08% | yes |
| Clustered t(3), score persistence .95 | 16 | 8.0% | upper 13.09% | no |
| Planted location | 5 | 2.5% | lower 0.99% | no |
| Planted scale | 8 | 4.0% | lower 2.01% | no |

The clustered result fails to establish the prespecified ≤10% bound; it does not
prove that the true rate exceeds 10%. Low detection does not establish an absence
of information, a uniquely defective decoder or a strong available four-year
signal. The per-step plant, its incremental value beyond context, noisy indicator,
overlap, limited calibration, 216-way selection and threshold interact. An exact
known-law oracle is a possible explanatory follow-up, not a way to retune these
criteria after seeing results. A 140-step path cannot supply the 48-month phases.

The first full run stopped before publishing results because zero-loss reference
cells used a nonfinite internal sentinel that JSON correctly rejected. The fixed
rule assigns zero improvement when both forecasts already have exactly zero loss.
That correction has a regression test; seeds, worlds and acceptance criteria were
unchanged, and no published results were used to choose a new threshold. The
interrupted registration remains locally at
`output/search-qualification-2026-11-06-registered`; the completed run is
`output/search-qualification-2026-11-06-finite-receipts`. Neither is a new market gate.

**Trust boundary:** use the scorecard for reproducible, common-outcome research and
error detection. Preserve the failed search result. Do not claim an indefinitely
reusable discovery score, automatic financial promotion or unseen historical BTC
evidence. Future acceptance requires a specified informational claim and evidence
separate from the research loop; no amount of reshuffling recreates new market eras.

## Known-law observed-score diagnostic

The failed search is not the end of the qualification goal. A separate
`research/gaussian_information_oracle.py` now establishes how much terminal-return
information is available in the location positive when the generating law is
known. It conditions on **observed data only**: all causal price history, versus
all causal prices plus the history of candidate zero. It never receives the
hidden state. Candidate zero is predesignated as the generator's smallest-noise
score, not the candidate selected by the failed search.

The state is stationary Gaussian AR(.95). Returns from step 2 onward equal
`.08 * state[t-2] + .04 * innovation[t]`. The score is `-state[t]` plus `.1` times
independent AR(.5) measurement error. A four-dimensional filter carries current
and two lagged states plus measurement error. It updates using the current close
and score before issuing a forecast. Future scores, prices and mature outcomes
cannot change earlier posteriors. The reference uses the complete price history,
which is stronger/different than the finite-bin readout's two-feature context.

For terminal return from entry `t+1` to `t+H+1`, let
`g_H = sum(phi**k for k in range(H))`. Its conditional mean is
`b * g_H * E[state_t | history]`; variance is:

```
H * return_noise**2
+ b**2 * (1-phi**2) * sum(g_j**2 for j in range(1, H))
+ (b * g_H)**2 * Var[state_t | history]
```

Both conditional forecasts are exact Gaussians under this known law. Their
expected CRPS is predictive standard deviation divided by `sqrt(pi)`. This
permits an analytic ratio of expected losses without fitting long-horizon labels.
It does not remove the structural-law assumption or make a market model valid.

The [retained diagnostic](artifacts/gaussian-oracle-diagnostic-2026-11-06.json)
reuses the **already exposed** 200 location worlds and all 24 common audit origins
at each horizon. All overlapping origins stay together in each of 2,000 paired
whole-world bootstrap resamples. This is post-hoc explanation, not fresh
confirmation or revised qualification criteria:

| Horizon | Exact expected CRPS skill | Replayed skill | Whole-world bootstrap 95% interval |
| --- | ---: | ---: | --- |
| 12 months | 20.72% | 20.25% | 18.25–22.22% |
| 24 months | 10.89% | 10.52% | 8.77–12.19% |
| 48 months | 4.81% | 4.44% | 2.96–5.89% |

The generator does contain incremental observed-score information beyond full
price history, including at 48 months. A correctly specified causal filter can
extract it; the registered finite-data search did not reliably do so. The gap
combines memory, reference, estimation, decoder capacity and selection, and cannot
be assigned entirely to median bins. The four-year expected gain is also much
smaller than the earlier 20.35% transferred threshold. No downside/scale oracle,
learned-model qualification, market accuracy or horizon utility is established.

Reproduce this explanatory diagnostic with:

```bash
python -m research.gaussian_oracle_diagnostic \
  --output-dir output/gaussian-oracle-diagnostic-new
```

Independent review matched the filter to the frozen generator. Boundary tests
compare recursive filtering to direct multivariate-Gaussian conditioning, terminal
variance to an independent covariance sum, and normal CRPS to numerical CDF
integration. They also check future-prefix immutability, a noiseless score, the
uninformative-score limit, paired uncertainty and retention of the failed parent
qualification status.

## Whole-path conditional randomization

`research/conditional_search.py` replaces transferred cutoff calibration with a
model-X randomization test for a **declared, known synthetic score-path law**. The
[original model-X paper](https://arxiv.org/abs/1610.02351) gives the conditional
exchangeability argument. Here one observation is an entire joint matrix of all
720 times and 24 candidates, not an independently shuffled ticket.

Conditional on the complete realized price/context path, the null score matrix is:

```
score[t,j] = .5 * context0[t] - shared_AR95[t] + sigma[j] * independent_AR50[t,j]
sigma = linearly spaced .1 ... 2
```

Both AR processes start in their stationary unit-variance distributions; candidate
correlation and temporal persistence are retained. The context component is a
known causal transform of the fixed price path. Under this null, observed and
redrawn whole score matrices are exchangeable conditional on that path. The test
reruns the complete 216-cell development search for each matrix, with common
longest-horizon phase boundaries, and reports the selected audit statistic. Its
one-campaign p-value is:

```
(1 + count(randomized_statistic >= observed_statistic)) / (randomizations + 1)
```

Ties use `>=`; 99 redraws give minimum p=.01. Exact conditional rank validity does
not require independent returns, independent outcomes or a model of the price
path. It **does require the correct entire conditional score law**. It is a strong
synthetic null, not a generic null of no useful Bitcoin information. Estimating a
score law from short market history does not inherit this guarantee.

The vectorized implementation is checked against every development attempt,
selected candidate/target/horizon and audit result from the frozen scalar search.
It computes audit losses in a batch but selection depends only on development.
Missing paths fail rather than disappear. All observed development attempts and
randomized statistics/selections are retained; source and seeds reproduce redraws.

The new registered run uses fresh seed 20261211, 500 independent null campaigns
per each of three price families, and 200 per location/scale positive. Null prices
are IID Gaussian, clustered heavy-tailed, or autocorrelated Gaussian location paths;
the observed score residual is independent of price in all nulls. Positives have
the same score-residual marginal law after subtracting the known context shift,
with a common state driving future price increments. Their raw score marginals
may differ because price context is correlated with the state.

The acceptance criteria remain explicit: each null's one-sided 98.333% upper bound
must be at most 10%; each planted sensitivity's one-sided 95% lower bound must be
at least 80%. Passing null control alone does not qualify useful-signal detection.
The full [registered result](artifacts/conditional-search-2026-11-06.json) is retained
at `output/conditional-search-2026-11-06-registered`. Its 1,900 independent campaigns
each used 99 whole-path redraws; all 190,000 score-matrix searches completed in
305 seconds with four bounded workers. No campaign was dropped. Every retained
p-value and aggregate flag count was independently recalculated from the stored
statistics, and all receipts/source hashes verified.

| Family | Flags / worlds | Rate | Registered bound | Pass |
| --- | ---: | ---: | ---: | --- |
| IID Gaussian prices | 31 / 500 | 6.2% | upper 8.91% | yes |
| Clustered t(3) prices | 18 / 500 | 3.6% | upper 5.82% | yes |
| Autocorrelated location prices | 25 / 500 | 5.0% | upper 7.50% | yes |
| Planted location | 21 / 200 | 10.5% | lower 7.14% | no |
| Planted scale | 6 / 200 | 3.0% | lower 1.31% | no |

The registered **overall qualification still fails**. Null control and sensitivity
are separate requirements. Under exact Q the exchangeable-rank argument controls
one campaign at 5%; these simulation bounds also meet the declared 10% tolerance.
They are not an empirical proof of a market 5% error rate. Low sensitivity remains
despite known observed-score information in the location world. No threshold or
readout retuning was performed using these evaluation counts.

```bash
python -m research.conditional_search \
  --output-dir output/conditional-search-new --workers 4
```

One test covers one complete registered search. Further campaigns require an
explicit shared alpha budget or another valid joint test. Human adaptation that
is not reproduced for every redraw is outside the conditional-rank argument.
The 24-slot local ledger is exposure accounting, not that statistical correction.
This restriction preserves the original long-running research goal: do not
substitute a passing synthetic null check for sensitivity or claim a restored
historical holdout. The goal remains active until its qualification requirements
are actually supported.

## Implemented qualification pilot

Run the offline research tool with locked NumPy/pandas dependencies installed:

```bash
mkdir -p output
python -m research.forecast_pilot --output-dir output/forecast-pilot-new-run
```

The output path must be new, under an existing parent, with no symlinked path
components. Runs are immutable: a completed run has a `COMPLETE` marker and a
SHA-256 manifest binding its outputs. Interrupted runs have no completion marker;
keep them for diagnosis and choose a fresh path. The tool does not repair,
overwrite, delete, open browsers or contact APIs.

`research/forecast_readout.py` owns exact empirical-distribution CRPS, a
training-only mid-percentile transform and a fixed direction-constrained ridge
location model. Residual distributions use a separate later calibration phase,
not location-fit residuals. The context coefficient is reoptimized if the
indicator's constrained slope lands at zero. These plug-in forecasts still omit
parameter uncertainty and are not asserted to be calibrated.

`research/forecast_pilot.py` generates four independent chronological regression
blocks per campaign: fit, residual calibration, development and audit. The
context is genuinely predictive; the null says that the indicator contributes
no information beyond it. All phases have explicit decision and label-resolution
steps. Each campaign tries 24 fixed noisy-indicator variants, selects once on
development, and then evaluates only that winner on audit. A distinct 200 null
campaigns calibrate a 5%-level declaration threshold for this synthetic procedure.
Fresh campaigns evaluate the full search, including its selection step.

The [portable result](artifacts/forecast-pilot-2026-11-06.json) records the frozen
configuration, source-code hashes, runtime, all reported summaries and monthly
market-data usability ledger. Full local attempts/predictions are in
`output/forecast-pilot-2026-11-06-qualified/`, approximately 15 MB, ignored by Git.
Synthetic records can be regenerated from the seed and code; the usability ledger
retains the inputs needed to reproduce coverage counts without retaining the full
ignored market artifact. It is not a retained feature dataset for training.

| Fresh campaign family | Declarations / 200 | Rate, 95% Wilson interval | Median audit CRPS skill vs context |
| --- | --- | --- | --- |
| No incremental information | 11 | 5.5%, 3.1–9.6% | approximately 0 |
| Planted signal, strength 0.5 | 197 | 98.5%, 95.7–99.5% | +5.14 |
| Planted signal, strength 1.0 | 200 | 100%, 98.1–100% | +15.04 |
| Same strong signal, inverted indicator direction | 0 | 0%, 0–1.9% | 0 |

These are Monte Carlo campaign intervals conditional on the calibrated threshold.
The threshold was 0.535 CRPS skill points; it is not a proposed market materiality
margin. The null median development gain was +0.220 points, illustrating how
selection can create an apparent improvement even without incremental information.
These independent Gaussian regression blocks do not qualify persistent, heavy-
tailed or overlapping market outcomes. The audit worlds are now exposed; do not
retune to them and describe them as unseen.

Optional coverage-only diagnostics require explicit horizons:

```bash
python -m research.forecast_pilot --output-dir output/forecast-pilot-with-coverage \
  --artifact-series output/risk_scores_full.csv --diagnostic-horizons 12 24 48
```

This invocation does not approve those horizons or score market forecasts. Under
illustrative one-month execution lag, one-day outcome publication lag and 24 raw
mature labels, the current artifact supports 89/65/17 completed entry observations
after the first fitting cutoff for 12/24/48 months. These are overlapping coverage
counts, not independent samples or sufficient calibration data. Exact month-close
rows are required; July 30 is not relabeled July 31 and missing closes are not
filled from earlier prices. As-of source/input vintages remain unverified.

At the v1 verification junction, 18 focused pilot/readout tests and the then-
complete 165-test backend suite passed. Current verification is recorded below. Eight deliberate defects were caught in isolated copies: removing
the CRPS pair term, clipping a constrained slope without refitting context,
allowing unresolved labels, accepting the wrong direction, carrying a missing
month-close price, selecting the winner using audit outcomes, using development
outcomes for residual calibration and replacing the null threshold order statistic
with the maximum. Astra's
implementation review reported no substantive correctness/leakage finding for
this synthetic-only scope. Python 3.12.16 ran the local checks; project CI pins
Python 3.11.18, so hosted execution has not been demonstrated for this slice.

A smaller harness smoke run (8 candidates, 40 threshold campaigns, 30 evaluation
campaigns per family, 96 fit/48 later-phase rows) preceded the registered-size run.
Repeated full-size runs used identical seeds and trial recipes while report
metadata was hardened; they are duplicate simulations, not new evidence.

These v1 results motivated the falsification experiments below. Their results
now determine the next bounded work; the IID pilot is not the production gate.
The indicator's informational claim remains unsettled before market scoring.

## Implemented falsification experiments

```bash
python -m research.forecast_falsification --output-dir output/forecast-falsification-new-run
```

The [retained result](artifacts/forecast-falsification-2026-11-06.json) records
configuration, source/reference hashes and uncertainty. Full local records are
in `output/forecast-falsification-2026-11-06/` (about 17 MB, ignored by Git).
Both pilots use the same exclusive, manifest-bound output writer. The v1 source
files and 0.53481558-point threshold remain unchanged; it is tested, not refitted.

The registered seed was 20261106 with 200 independent worlds per family. The
long overlap null uses one continuous 720-step log-price path with IID Gaussian
increments (standard deviation 0.04), 48-step outcomes starting after execution,
24 correlated irrelevant indicators with stationary AR(1) persistence 0.95, and
past-price context. Fit/calibration/development/audit sizes remain 192/96/96/96;
phase gaps derive from actual label-resolution times. Repeating the minimal
24-row phases on one 140-step path is a separate deterministic feasibility check.

| Test | Observed result | Interpretation |
| --- | --- | --- |
| Dependent no-edge histories | 75/200 flags at the frozen IID threshold: 37.5%, 95% Wilson interval 31.1–44.4% | The old threshold fails joint transfer to these conditions |
| Short 140-step history, 24-row phase minimums | Calibration has only 4 eligible rows; insufficient evidence | This sequential protocol is infeasible there; not a theorem about every method |
| Leading versus lagging state | Median audit skill +29.05 (95% world-bootstrap interval 28.81–29.19) versus 0 | The control distinguishes information about returns after entry from an irrelevant lagging state |
| Retrospectively revised state | All 200 worlds ineligible before scoring | Supplied late-publication metadata is rejected; undocumented real revisions are not thereby detected |
| Equal-mean tail state | Location decoder median skill 0; registered state bins +19.49 (19.29–19.75); population oracle 20 | A location-readout failure is not absence of useful distributional information |
| Deterministic price-context transform | Augmented decoder median gain +21.49 (21.11–22.21) against weak context; context-oracle loss delta exactly 0 with/without the indicator | Learnability over a restricted reference is not new information conditional on the underlying context |

Intervals resample independent complete worlds, not overlapping ticket rows; the
flag interval conditions on one fixed threshold. Overlap, persistence, context
and interphase gaps change jointly, so this falsifies transfer without isolating
a single causal mechanism. It is not an estimate of BTC false-positive rates.

Timing controls share one price path. State at t predicts r_(t+2), after entry at
t+1; a move included in the entry price cannot earn predictive skill for that
holding-period outcome. Observation, publication, decision, execution, outcome
end and label availability are all retained. Feature publication exactly at the
decision cutoff is usable; model-fitting phases begin strictly after prior
labels resolve.

The tail law is known: state0 gives ±1 and state1 gives ±3, equally likely, both
with mean zero. Population CRPS is 1.25 pooled versus 1.0 conditional. State bins
use calibration labels only, with 12 observations per state required and a pooled
fallback retaining all audit rows. The bins know the registered binary partition;
the oracle knows the population law. Neither is an adopted market model.

The redundancy law is `Y=-2*C²+epsilon`, with `epsilon~N(0,0.5²)` and `S=C²`.
An exact Gaussian context oracle already knows everything in S. The restricted
location decoder gains from S as a basis function; reporting this as novel
information beyond all price inputs would be wrong. Do not endlessly strengthen
the reference after observing results to erase legitimate representation gains.

These are qualification counterexamples, not new acceptance criteria. The next
bounded experiment is whole-path error calibration with independent generator
families and repeated threshold-calibration uncertainty. Preserve these failures
as frozen controls. Market target/horizon preferences remain unaccepted.

Verification: all 178 backend tests pass, including 13 new scenario/runner tests
(31 research tests in total). Six deliberate defects were caught in isolated
copies: including the pre-entry return, accepting late publication, partitioning
on decision time instead of label maturity, fitting state bins to audit outcomes,
using an incorrect Gaussian CRPS formula and modifying the frozen threshold.
The Gaussian oracle was independently checked against numerical integration of
its CDF loss. Terra reviewed the implementation and saved evidence without a
substantive correctness finding. Source/reference/output hashes and local links
were verified. Checks ran locally on Python 3.12.16, not hosted CI.


## Scientific interpretation and competing designs

Independent objective, validation and adversarial lenses (Sol, Terra and Astra)
were used after the first pilot. Their methodological arguments, checked against
primary sources, change the recommendation as follows. Model agreement is not
validation; the arguments and falsification tests determine the next work.

Three distinct meanings of an indicator must not share an unqualified score:

| Meaning | Evidence needed | What a passing result cannot imply |
| --- | --- | --- |
| Descriptive state: unusual, stretched or expensive against a defined quantity | Correct measurement, provenance and causal stability | That future exposure is unattractive |
| Predictive representation: helps forecast future outcomes | Incremental out-of-sample proper-loss reduction under a registered readout/context | That higher/lower states are economically preferable |
| Favourable ordering: distinguishes better exposure opportunities | Correct directional ordering across a declared outcome/preference domain | Universal dominance when upside and downside trade off |

For example, a signal that predicts variance but not expected return may be useful
risk information while failing an accumulation-opportunity claim. A registered
location-only decoder can miss that information; a flexible distribution decoder
can reward it without establishing favourable ordering. A failed decoder is not
proof that the indicator contains no information. Neither decoder is neutral.

**Recommended research architecture:** a representation benchmark for experiments,
separate directional tests for the product's stated ordering, and a decision-value
surface as the breadth check. Do not average these into one scientific certificate.
A candidate can improve one and remain ineligible for another claim.

Call the representation result *incremental usable predictive content under the
registered context/readout/update procedure*. A deterministic transform of full
price history adds no Shannon information conditional on that full history. It
can still help a restricted learner extract a useful pattern. Our small price
reference tests this practical learnability comparison, not the impossible claim
of information absent from all the underlying price data.
[Holzmann–Eulert](https://arxiv.org/abs/1404.7653) analyzes forecasting with differing
information sets; finite fitted procedures and their estimation uncertainty still
need evaluation, as emphasized by
[Giacomini–White](https://economia.uc3m.es/jgonzalo/teaching/PhdTimeSeries/GiacominiWhite.pdf).

Cash-relative log-wealth paths provide a coherent outcome representation without
arbitrary dollars: `X_t(u) = log(P_(t+u)/P_t) - log(C_(t+u)/C_t)`. This is a proposed
representation, not an accepted utility or horizon. Terminal return distributions
can cross: high upside with crash risk and modest upside with little risk can be
incomparable. Terminal stochastic dominance does not imply pathwise dominance;
separate marginal forecasts can miss ordering, recovery duration and dependence.
Even multivariate proper scores may have weak sensitivity to incorrect dependence
([Scheuerer–Hamill](https://repository.library.noaa.gov/view/noaa/22327/)). Full
48-dimensional path forecasting is not justified by this small sample.

Decision-value surfaces should use a small prespecified family of exposure/cash
choices, holding periods and loss tolerances, with decision rules fitted only on
past data and common funding constraints. Murphy diagrams are a precedent for
comparisons across defined loss classes, not a shortcut to every investor's
preferences. Persistent crossings challenge the one-dimensional indicator claim;
they are not automatically repaired by another fitted weight.

### Prioritized falsification experiments

Experiments 1–4 are implemented in the falsification runner and summarized
below. Experiments 5–6 remain proposals. The descriptions define the scientific
questions, not claims that their outcomes qualify a market benchmark.

1. **Dependence without edge.** Generate short chronological price paths with
   persistent irrelevant indicators and overlapping long-horizon outcomes. Preserve
   candidate/context dependence under the conditional null. Replay all fit,
   calibration and selection cutoffs on matured labels; hold the IID-calibrated
   threshold fixed as a falsification check. Measure whole-campaign false flags
   across independent paths. Inflation means the pilot threshold does not transfer.
   BTC-sized histories that cannot support the phases must return insufficient
   evidence; longer simulated controls do not solve their feasibility problem.
2. **Information timing with matching marginals.** Compare an observable state
   influencing future returns with an identically distributed lagging indicator
   describing past returns, and a retrospectively revised version unavailable at
   the decision time. The leading signal may score, the lagging signal must not
   inherit its edge, and unavailable revisions must be ineligible regardless of
   score. Require observation, publication, decision and execution records.
3. **Useful tail information with no mean signal.** Plant observable volatility
   or downside-tail state with equal conditional mean, plus a location-shift
   control and exact oracle distributions. Test whether the location decoder
   misses genuine information and a registered distribution readout detects it.
   Forecast skill may pass while favourable-entry ordering must remain unproven.
4. **A redundant transform repairing an underfit reference.** Generate nonlinear
   outcome dependence on price context C and an indicator S=g(C). Compare a weak
   context model, a suitable context-only oracle, the transform-augmented model
   and a genuinely additional signal. A representation gain must not be labeled
   information absent from price. Register stronger references before using their
   results, rather than increasing capacity opportunistically until a win vanishes.
5. **A relationship that vanishes or flips after selection.** Freeze the update
   algorithm and score the audit regime without retuning. Preserve marginals
   while changing the relationship; include gradual and sudden transitions.
   Report transition losses and recovery, and forbid updates from unresolved
   labels. No method can instantly identify an unobserved regime reversal.
6. **Crossed outcomes, path order and financing.** Construct upside/downside
   trade-offs and paths with similar terminal/marginal distributions but different
   crash order or recovery. Vary cash returns separately from BTC returns. The
   benchmark must show preference/dependence sensitivity rather than label one
   universally better. This can falsify the one-dimensional opportunity claim.

The first qualification tranche implements experiments 1–4, with oracle
references and explicit ineligible/insufficient-evidence states. Next, compare a
new whole-path-calibrated error rule against the frozen IID rule using separate
calibration/evaluation generator families. Predeclare parameters and hold out
families, not only seeds; do not tune the old threshold to the observed failures.
Repeat complete threshold calibration plus search/audit on independent worlds;
report both conditional and across-calibration uncertainty, modest-effect power
and chance of at least one false declaration over the planned campaign schedule.
The current Wilson intervals condition on one threshold and do not establish
indefinite 5% error control. Development diagnostics can compare return tails,
volatility/label autocorrelation, drawdown duration and cross-variable dependence;
matching them does not prove a simulator contains future BTC regimes. Unknown
source vintages remain quarantined rather than simulated into certainty.

White/Hansen family tests, block bootstrap, PBO and sequential tests answer
specific questions under explicit assumptions. They are not interchangeable
protections to stack until the score looks rigorous. Long-block inference is
weak with only a few complete market eras. Anytime-valid methods require a valid
conditional null and delayed-outcome filtration; ordinary repeated p-values are
not an e-process. See
[Casgrain–Larsson–Ziegel](https://arxiv.org/abs/2204.05680). More synthetic replications
can reduce Monte Carlo error, but not uncertainty about which generator describes
the market.

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

### Keep ordinal ordering as a diagnostic

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

Candidate diagnostic horizons are 12, 24 and 48 months, with opportunity and
downside reported separately. An equal-weight horizon average has no accepted
economic interpretation and is withdrawn as the proposed primary score. A rank
score also discards the size of outcome differences and may reflect calendar
trends across overlapping outcomes. It is not sufficient evidence of incremental
information beyond price. Select targets from the indicator's intended claim;
do not pool return and downside into one utility or treat this grid as approved.

This is a retrospective discovery score, not a confirmatory p-value or a
probability of profit. Nonlinear conditional information that contradicts the
advertised ordering is an exploratory finding, not a passing ordinal indicator.

### Evaluate conditional forecast quality when the target and data support it

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

The [independent support audit](artifacts/btc-frozen-outcome-support-2026-11-07.json)
uses the actual frozen benchmark's 139 complete month-end origins, December 2014–
June 2026, with daily history through July 30. It independently reconstructs all
417 horizon paths and checks endpoint-plus-one-day label availability. These are
**all mature outcome rows**, not the smaller matched forecast samples:

| Horizon | Mature monthly origins | Negative / nonnegative return | Entry loss >log(2) | Peak drawdown >log(2) | Maximum disjoint return intervals, negative / nonnegative |
| --- | ---: | --- | ---: | ---: | --- |
| 12 months | 127 | 32 / 95 | 23 | 56 | 5 / 9 |
| 24 months | 115 | 21 / 94 | 30 | 77 | 3 / 5 |
| 48 months | 91 | 0 / 91 | 30 | 90 | 0 / 2 |

There are no mature outer four-year labels. The four-year return event has only
one class, while the four-year peak-drawdown event has 90 positive examples and
one negative. A low Brier loss can therefore reflect class prevalence; these
samples cannot establish discrimination between four-year loss and gain regimes.
Continuous return magnitudes remain scoreable as a separate claim. The audit
retains per-role class counts and selected non-overlapping intervals.

Disjoint means closed price intervals `[entry,end]` with the next entry strictly
after the prior end. Earliest-finish greedy counts were checked independently by
dynamic programming. Counts are maxima **within each class**; their sum is not a
jointly disjoint sample. Even disjoint price paths can share market regimes and
are not asserted statistically independent. Earlier nominal row counts using
partial-month stamping are superseded by this exact-interval audit.

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

The accepted first external experiment is **monthly portability falsification**,
not pooled pretraining. The official [French monthly factors ZIP](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip)
was captured once on 2026-11-07. The parser reconstructs broad-US research-market
**total return** as `(Mkt-RF + RF)/100` and compounds it. This is neither the S&P 500
nor an executable security. The [provider methodology](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
uses current CIZ-format revised historical values; observation dates and retrieval
metadata do not establish historical publication availability.

[Acquisition metadata](../research/fixtures/french_monthly_2026-11-07.json) pins the
13,078-byte ZIP (`b03d39e4bb253dda0f14893db3b78e64b40b8d6549a0fc0fd4111dae84c98618`),
provider database 202609, 1,203 monthly observations and excluded annual section.
The cropped fixture contains 1,158 consecutive months, July 1926–December 2022;
45 later months are excluded. Its CSV SHA-256 is
`54b4aeb41fc12fb4d77034d946bb13be6036742e0a61fa63551d6ceb7d2b5374`.
Raw and derived numeric provider data remain in ignored
`data/external_private/french_monthly_2026-11-07/`; redistribution permission has
not been cleared. Only parser, invented test fixtures and metadata are committed.
A separate decimal calculation verified every cropped return and compounded index.

This monthly track replaces the proposed daily-first acquisition. It needs no
invented daily interpolation or exchange-session adapter. Daily equity drawdowns
and execution simulations remain unimplemented. Nasdaq Composite is still only a
proposed price-index stress series; gold's World Bank monthly average spot price
is not a month-end close. Neither was acquired or adopted.

**Frozen monthly contract, before scoring:**

- Feed consecutive monthly observations from January 1970, rebasing that first
  index value to 100. Generate training origins from January 1980 after fixed
  initialization. No BTC components or French factors become predictors.
- Evaluate January 1990–December 2003 as the older-family falsification and
  January 2004–December 2017 as the shared-era challenge. The candidates were
  chosen after BTC development exposure; neither era is an unseen historical
  holdout, and no claim of a pre-1990 freeze is made. Later equity outcomes share
  macro shocks with exposed BTC outcomes. These are paired observations from one
  equity family, not extra independent BTC cycles.
- Preserve the three frozen generators and parameters: A `memory_weight=0`,
  B `swing_b_adaptive`, C `window=24`. A's existing one-day observation lag uses
  the previous monthly observation; B/C use the current completed month. Sparse
  monthly sampling changes A's elapsed-time filter. Removing that lag or
  rescaling a candidate would create another trial and is not allowed here.
- At origin month-end, virtual entry is **next month-end**; exit is month-end
  H months after entry for H=12/24/48. Label availability is exit plus one calendar
  day and must be strictly before the query date. These are computational anchors,
  not verified French publication or execution timestamps.
- Score terminal log return, nonnegative entry adverse log loss, and true
  peak-to-trough log loss on the **monthly-sampled** entry-to-exit path including
  entry. Intramonth troughs/recoveries are invisible. Keep asset/frequency/protocol
  identifiers distinct from BTC daily outcomes; no cross-frequency score pooling.
- Use the existing direct empirical-CDF median decoder, latest 24 strictly mature
  outcome rows, training-only median thresholds, `>` tie rule, 50:50 pooled/local
  weights and exact fallback. No decoder or parameter selection. Primary diagnostic
  coordinate is 24-month terminal return; every other coordinate remains visible.
- Monthly context is trailing 12-month log return and sample standard deviation
  (`ddof=1`) of the latest 12 monthly log returns, without annualization. This is
  a new declared monthly context, not 90-day daily-volatility equivalence.
- Eight fixed references are those two context coordinates; current signed log
  distance below the trailing 12-month peak (13 month-end closes, distinct from
  maximum historical peak-to-trough loss); expanding ATH drawdown since
  initialization; log index/arithmetic
  12-month moving-average ratio; elapsed months since January 1970; and sine/cosine
  of a fixed 48-month phase anchored January 1970. Calendar terms are nuisance
  controls, not asserted equity cycles. Also report context-only and unconditional
  forecasts. All candidate/reference comparisons use identical mature atoms/dates.
- Report negative/nonnegative terminal-return counts, both loss-event prevalences,
  training-pool class counts and non-overlapping outcome-window counts within each
  class, per era/horizon. Events remain return `<0` and log loss `>log(2)`.
  A single-class four-year sample cannot establish event discrimination; zero
  reference-loss skill is undefined. Continuous CRPS/ordering remains descriptive.
- Descriptive portability rejection patterns per candidate: negative 24-month
  return alignment in **both** eras; or one fixed comparator with no worse CRPS
  across all three 24-month outcomes in both eras and strict improvement somewhere.
  Report every regression even without these patterns. Their absence establishes
  neither significance nor portability. A retrospective best-reference envelope
  is informative but is not an origin-time forecasting strategy.

No external candidate scoring has run at this registration point. Success would
not validate BTC-specific features, daily risk, four-year Bitcoin predictions or
professional-use reliability. Failure cannot be repaired by tuning on these eras.

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

The legacy assessment at `37fbd99` ran its compact evaluator in 2.72 seconds,
excluding model generation. [DCA evidence](dca_evidence.md) owns those historical
results. Current research implementation and qualification are recorded below;
the legacy acceptance gate remains unchanged.

| Capability | Current state | Required delta / acceptance |
| --- | --- | --- |
| Unit/regression infrastructure | Implemented; focused tests available | Preserve and add boundary tests that fail under reintroduced defects |
| Common-outcome table | Retrospective daily-close log return, entry loss and true drawdown implemented | Verified source close/availability convention and accepted primary claim remain open |
| Ordinal information diagnostics | Fixed-direction continuous ranks, ties and common origins implemented | Descriptive only; no primary rank leaderboard |
| Forecast readout and skill | Frozen residual-CDF and direct empirical-CDF protocols; separate median/rank ablations | No 48-month direct-CDF development/outer forecasts; no calibrated market model or automatic promotion |
| Chronological benchmark | Strict fitting/calibration label maturity, exact complete outcomes and independent replay implemented | Real input-vintage reconstruction and prospective update audit remain open |
| Baseline identity | Committed minimal snapshot, immutable manifests/receipts and byte-identical baseline replay | Snapshot is exposed and reconstructed, not new holdout evidence |
| Experiment registry | Shared direct-CDF budgets, immutable finalists, one release and reasoned interrupted-attempt closure implemented | Declared producer artifacts are not executed/causally certified; public exposure cannot be erased |
| Prospective archive | Bounded hash-chained observation/resolution API, synthetic CLI and independent review implemented | No live archive or verified input-publication adapter; hashes are not source authentication |
| Synthetic / external suite | Independent-world conditional panel passes; private monthly equity fixture acquired and falsification contract frozen | External candidate scoring pending; no market error-control transfer |
| Supporting policy accounting | Equal initial capital, no contributions, explicit costs, common dates and ex-post exposure matches | Candidate C's three-trade lead is exploratory; no policy winner or pathwise risk equivalence |

Legacy acceptance/policy issues remain separate from the research protocol:

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

1. **Implemented:** immutable dataset/benchmark manifests, exact outcome paths,
   paired ordering/forecast diagnostics, fixed references, candidate ledger and
   strict readout feasibility. Boundary, invariance, independent E2E and deliberate
   defect tests verify the measurement mechanics.
2. **Implemented; failed:** continuous location/scale search with seed 20270119,
   strict 192/96/96/96 phases and full selection repeated in each redraw. Its
   null controls pass, but location/scale sensitivity is 40%/11.5%. The next
   registered experiment changes the inferential unit to independent synthetic
   world panels and conditions on fitted score prefixes, as specified below.
   This is a new experiment, not a repaired result or a market significance test.
3. **Implemented:** append-only shadow observations and unique mature-label
   resolutions, actual runtime UTC timestamps, producer/configuration/readout
   identities and immutable forecast atoms. Calendar-derived entry/end/publication
   prevents shortening a declared multi-year horizon. Concurrent writes, tampering,
   premature labels and prefix immutability have regression/mutation tests and an
   independent synthetic CLI replay. Unknown vintages remain explicit; no live
   market archive is initialized. Retain trusted heads separately: a local chain
   cannot defeat adversarial tail removal/full rewriting. Appends scan bounded
   history (2,048 events, 128 KiB/event, 16 MiB total); measured 7.4ms after 100
   events and 93.1ms after 1,000. Midnight UTC dates are calendar anchors, not
   independently verified exchange execution timestamps.
   Schema v2 separates evidence timing from input freshness: known older inputs
   can support a forecast recorded today, with age/quality flags disclosed.
   Unknown vintages, historical decisions and elapsed endpoints remain ineligible.
   It does not endorse stale data quality or authenticate publication assertions.
   The CLI is `python -m research.shadow_archive --help`; request fixtures are in
   `tests/test_shadow_archive.py`. Earlier synthetic v1 archives are explicitly
   rejected, never silently reclassified.
4. Before a bounded candidate campaign, state one informational hypothesis and
   diagnostic comparisons; distinguish decoder improvement from novelty and
   directional usefulness. All explored historical results remain development
   evidence. Do not promote a model from its best exposed scorecard row.
5. External markets, real-time macro vintages and further oracle comparisons
   may address specific diagnosed gaps. They are accepted research directions,
   not implemented transfers or excuses to tune exposed qualification worlds.
6. Replace the production acceptance contract only after the indicator benchmark
   is reviewed and verified. ADR 0008 and existing canonical metrics describe the
   current policy gate until then; do not silently rewrite them as implemented.

### Genuinely open decisions

- Establish the precise information the indicator claims to convey before
  selecting primary targets/horizons. The 12/24/48-month mixture and rank-based
  primary score were challenged and withdrawn as the recommendation. The glossary
  currently says approximately six months; the gate uses 48 months. Reconcile
  glossary and ADRs only when a replacement contract is actually accepted.
- Freeze exact family/horizon weights and materiality/non-regression margins
  before the first campaign. No cross-family scalar utility is proposed.
- For supporting accumulation policies, define permitted cash deferral precisely.
  This does not block the indicator-only fixed-notional outcome slice.
- A sealed historical audit remains limited by prior researcher exposure. Record
  its actual access boundary; only future frozen predictions can be prospective.

## 10. Continuous readout, panel qualification and market campaign

### Completed continuous experiment and diagnosis

The immutable [continuous search receipt](artifacts/location-scale-search-2026-11-06.json)
binds 1,900 campaigns and source/runtime hashes. Declarations in each of three
500-campaign null families were 28, 25 and 15; their simultaneous one-sided bounds
pass the declared 10% ceiling. Location sensitivity was 80/200 (40%, lower bound
34.19%); scale sensitivity was 23/200 (11.5%, lower 7.99%). Both fail the 80%
lower-bound requirement. This failure remains authoritative.

A separate, explicitly posthoc [fixed-candidate replicate diagnosis](artifacts/readout-replicate-diagnostic-2026-11-06.json)
uses candidate zero across the same exposed 200 worlds, without selecting a cell.
Mean return-loss improvements at 12/24/48 months are 28.92%/16.15%/5.09% in the
location family, with paired whole-world bootstrap intervals above zero. Scale
return improvements are negative at all three horizons. Scale's 24-month true
drawdown loss improves 5.32% (interval 2.91–7.62%). This distinguishes average
forecast usefulness from a single trajectory's discovery power; it does not
repair the failed qualification or add independent Bitcoin cycles.

### Registered panel experiment and completed qualification

`research/panel_benchmark.py` reserves seed **20270417**. Each family-specific panel
has 128 independent development worlds and 128 new audit worlds. Each world has
720 steps and the same causal readout phases. Development pools raw paired CRPS
across worlds and selects one global candidate/horizon/target out of 216 cells.
The chosen algorithm is fitted separately on each audit world's earlier prefix.
No training is shared across worlds and no audit outcome selects an endpoint.

The new conditional test fixes all prices/context and all 24 indicator prefixes
through step 545. It samples only the chosen indicator's audit continuation
(steps 546–641), jointly within each world, from its **known synthetic Gaussian
conditional law**. The exact posterior conditions on every candidate prefix,
including shared AR state; 99 continuation draws give conservative tie/+1 ranks.
The fixed selection and fitted states are measurable under this conditioning, so
this test does not repeat development selection for each continuation. It tests
a different null from the earlier full-path CRT and cannot credit information
entirely contained in the fixed score history. Unknown market score laws do not
inherit its error control.

A declaration requires both p <= .05 and positive raw pooled audit loss gain.
Normalized gain is 100(R-C)/(R+C), with the zero/zero case zero; it is not an
investor utility. Three null families each use 500 panels; each of two positives
uses 200. Existing criteria remain: simultaneous one-sided 98.333% null upper
bounds <=10%, positive one-sided 95% lower bounds >=80%. Three panels each of
constant, linear-context and nonlinear-context indicators use their actual
point-mass continuation laws and must have p=1/no declaration. They check
context redundancy and protocol plumbing, not Gaussian-law validity.

The batched implementation agrees with the independent scalar path on all 216
losses, selected cells and randomization results. A new feature-boundary invariant
canonicalizes exactly constant fitting columns and falls back to identical
reference losses for inactive features. Without it, floating point residuals of
a constant such as 23 can be standardized into a false feature. The older frozen
experiment source is unchanged; its failure is not rewritten. Conditional sampler
tests compare exact multivariate Gaussian conditioning and Monte Carlo moments.
The [registered results](artifacts/panel-benchmark-2026-11-07.json) and complete
[portable packet](artifacts/panel-benchmark-2026-11-07.zip) bind all 1,909 panels
and unchanged source hashes. Runtime was 381 seconds with four workers. All
registered criteria pass:

| Family | Declarations | Relevant one-sided bound |
| --- | ---: | ---: |
| IID Gaussian null | 9/500 | Upper 3.539% |
| Clustered t3 null | 9/500 | Upper 3.539% |
| Autocorrelated-location null | 6/500 | Upper 2.727% |
| Leading location | 200/200 | Lower 98.513% |
| Leading scale | 198/200 | Lower 96.886% |
| Three deterministic sentinels | 0/9 | Every p=1 |

Independent verification recomputed every selection, pooled gain, rank p-value
and binomial bound, and checked disjoint world IDs and receipt/source hashes.
Thirty-six CRT rejections had negative gains and were correctly blocked; scale
panel 110 has p=.01 but gain -.01075265. Statistical unusualness alone is not
useful forecasting. This pass qualifies the finite known-law panel procedure,
not unlimited adaptation, Bitcoin significance, population economic benefit or
all endpoints simultaneously.

### Chronological market hill-climb contract

Josh requested actual divergent model experiments and meaningful improvement for
multi-year Bitcoin swing decisions. This expands implementation scope while
preserving a broad information objective, separate opportunity/downside reports,
and the hold on all pushes. No combined strategy wealth score is accepted.

`research/market_information.py` implements a distinct **direct conditional
empirical CDF**. Each origin uses the latest 24 strictly mature labels to fit
feature medians and raw outcome atoms. Sharing those fitting rows is ordinary
distribution fitting: there is no fitted residual model or claim of probability
calibration. The reference mixes pooled/context outcomes 50:50; the candidate
mixes pooled/context-plus-indicator outcomes 50:50, falling back to reference for
empty or duplicate-context cells. Every origin also records unconditional CRPS.
Thus an indicator cannot be credited solely for beating an underfit context model
while silently losing to the pooled distribution. Thirteen fixed references
include the incumbent, its four components, price trend/volatility/drawdown,
price/SMA, causal all-time drawdown, age and fixed four-year calendar sin/cos.
They are diagnostic competitors, not proof that every strong model is covered.

The input snapshot and next-day calendar outcomes are unchanged. Development
requires label availability <=2022-12-31. Outer origins start 2023-01-01. Older
origins with later labels are an exposed retrospective challenge. Full-snapshot
forecast counts per candidate are development **48/24/0**, outer **30/18/0**, and
challenge **13/25/19** at 12/24/48 months. These heavily overlapping observations
are not independent cycles; there is no four-year outer validation. Historical
public data and earlier inspections preclude claiming a genuinely blind test.
Pending forecasts are reconstructions, never prospective receipts.

The locked development CLI is `python -m research.indicator_trial --help`.
Its immutable bundle contains only <=2022-12-31 data and a manifest of original
and cropped source hashes. The portable [development bundle](artifacts/hillclimb-development-2026-11-07.zip)
has SHA256 `93e1e59601602aeb6248ddbbe19595a6ba5940f5b3d10113a12d7d67fb08fffd`.
It refuses post-cutoff observations, missing/duplicate dates and reused output
paths, records exact candidate/producer/data/code identities, and evaluates all
fixed references on the same origins. Current cached macro/volume vintages remain
unverified; they cannot establish real-time eligibility.

Three Astra medium agents worked independently in managed worktrees
`codex/swing-research-a`, `codex/swing-research-b`, `codex/swing-research-c`, with
at most six recorded development variants per agent. Seven variants were tried:
three causal price-anchor/occupancy weights, three bounded online log-trend
innovation filters, and one 24-month upside-energy share. The volume-divergence
idea was rejected before scoring because venue/units consistency was unverified.
Each agent froze a finalist and full attempt packets before parent-owned outer
replay. No finalist is a claimed broad improvement: all lose two-year return CRPS
to the unconditional baseline, despite some one-year downside gains. No default
production model changes are authorized from these results. Candidate research
can be retained as evidence even when its trading hypothesis fails.

The frozen [outer replay packet](artifacts/indicator-outer-replay-2026-11-07.zip)
(SHA256 `258a3f1a40b39b0106c104071450d3e6f5969e50466d0c41422ebb7d090b02a0`)
contains all three finalists, declarations, full source and every reference.
`python -m research.indicator_outer_replay --help` documents exact portable replay.
Every finalist loses every outer outcome cell to at least one fixed reference.
All three lose all one-year cells and two-year peak drawdown to unconditional;
only two-year return and entry loss improve unconditional. Candidate B's two-year
return CRPS is .280957 versus unconditional .304205, context .276072 and best
fixed .256821. Its entry loss is .123800 versus context .146430 and best fixed
.097276. These are separate descriptive comparisons, not a broad winner.
Independent raw-price/atom/maturity/quadratic-CRPS replay checked all 1,593 scored
candidate records (maximum difference 1.33e-15) and 756 unscored records. Archived
development losses reproduce exactly; B/C serialized score values differ by at
most 1.42e-14 from CSV rounding. No retuning followed the outer look.

A separately frozen development-only 2x2 readout study (`research/readout_study.py`)
compares indicator-only/combined with median/rank decoding on identical 24-label
pools, all thirteen references and frozen candidate B. Rank distance uses eight
nearest training-percentile observations, fractional boundary ties and half
uniform mass. Its full packet is in `research/candidates/swing_b/readout_study/`.
There is no general improvement: B's two-year combined return loss improves
.450009 to .424059, still worse than unconditional .331074; all one-year combined
losses regress. Nominal 80% return intervals cover only 37.5–39.6% of one-year
outcomes, versus 91.7% at two years. These empirical distributions are not
calibrated. Coverage, Brier events, atom-range violations, cell mass, weight
concentration and same-scored-origin Spearman alignment are descriptive reports.
Spearman is a separate implemented rank diagnostic; the earlier Kendall proposal
is not implemented. Concentration is not an effective independent sample count.

The frozen rank study also exposes a representation limitation: duplicating one
context coordinate reweights its distance contribution and can improve loss
without adding information. Its results therefore measure representation plus
readout, not conditional novelty. The original source/result is unchanged.
Implemented `research/readout_study_v2.py` collapses exact training-and-query
rank-equivalent coordinates. Tests cover duplication, monotone copies, permutation
and broken query relationships; disabling collapse fails the oracle. The single
v2 development study changes only twelve context-duplicate reference cells; all
432 duplicate-control forecasts now equal context-only exactly. Candidate B and
best-reference gaps are unchanged. Both packets and all 25,488 predictions were
independently audited. This is an additional representation trial, not independent
validation. It controls exact rank redundancy, not arbitrary nonlinear functions
of context. The 13-reference envelope is descriptive, not a causal
per-origin model selector; trend and volatility are context-duplicate controls.

Supporting self-financing policy probes in `research/policy_probes.py` have one
fixed historical replay. Both start with capital 1, no contributions or
cash yield, next-calendar-day execution, daily BTC/cash holdings, and separate
0/25/50bps per-leg costs. Exactly 24 prior monthly scores define the percentile;
continuous weight 1-percentile and 20/80 hysteresis (initial 50%, full BTC <=20%,
cash >=80%, otherwise hold) remain separate probes. Buyhold, cash and monthly
50/50 share first eligible execution and final mark. An explicitly ex-post
constant-allocation comparator matches realized time-average exposure; it is
neither causal nor a match for pathwise risk. Missing daily/monthly dates reject;
warmup/pending orders are explicit. Terminal liquidation is a separate diagnostic.
No policy defines the indicator winner.

The [fixed replay](artifacts/policy-probes-2026-11-07.json) and
[full ledgers](artifacts/policy-probes-2026-11-07.zip) use all three finalists plus
all five higher-risk fixed references. Decisions start 2023-01-31 after exactly
24 prior months; all policies execute first on 2023-02-01 and end 2026-07-30.
Independently recomputed all 214,368 ledger rows, fees, holdings, post-fee targets
and matched exposures. At 25bps candidate C's hysteresis ends at 2.4046 versus
its ex-post exposure-matched comparator 1.7565 (36.90% higher), with drawdown
-29.17% versus -28.41%. The relative advantage is 37.39% at zero costs and 36.41%
at 50bps. However, **three trades drive this result**. Its continuous rule loses
to its matched comparator (1.6206 versus 1.8025), and its forecast comparisons
remain weak. Buyhold ends at 2.7236 with full exposure and -52.97% drawdown;
these are different risk/exposure outcomes. This is a narrow research lead,
not an established timing edge or professional-use validation. Do not select
the successful rule after seeing this table or reset its trial history.

`research/direct_cdf_campaign.py` now coordinates future parallel experiments.
It freezes the development bundle, complete references, protocol, runtime and
evaluator code hashes. Global and per-worker budgets include all reserved slots,
including malformed candidates, failures and interruptions. Explicit reasoned
abandonment retains the slot and partial evidence; a late worker cannot replace
its terminal outcome. A serialized finalist freeze accepts only successful
attempt receipts. The single outer release is reserved before its input is read
and remains consumed after failure or interruption. Price/component history,
candidate development values, supplied producer/config artifacts and parameters
must match the frozen records exactly. The target source hash is first bound in
the reserved release request, not precommitted at campaign creation. Interrupted
administrative freezes fail closed as `FREEZE_RESERVED`.

The module docstring owns request schemas and CLI commands (`create`, `submit`,
`status`, `freeze`, `abandon`, `release`). Bounds are 999 slots, 16 MiB per supplied
file, 64 MiB per bundle and 50,000 daily rows/date-span days. Seventeen synthetic
tests and four failing mutations cover races, budgets, identities and release
reuse. Independent review and an unmocked synthetic lifecycle through both
evaluators pass, including 54 scored synthetic outer records. This is verification,
not another market trial. The original seven model attempts predate the shared
coordinator and remain individually archived; they were not retrospectively
relabelled as coordinator runs.

Supplied producer hashes establish artifact continuity only. The coordinator
does not execute the generator, verify imported model/data closure, or prove that
CSV values were produced causally. Those require a trusted producer adapter and
independent prefix tests. New campaigns must record exposure lineage; a new
directory or replayed receipt cannot restore unseen history. Exact prefix
matching requires a stable serialization, not an independently rounded rewrite.
The locked trial harness also now parses the same captured source/candidate bytes
that it hashes; path-replacement regressions and exact original-byte replay pass.

Next bounded work: make the stronger generative benchmarks part of future
candidate comparison guards, then implement one external-market falsification
adapter. Further indicator search must inherit all exposed results and keep the
same horizon/target/metric distinctions; no primary model has qualified.
The expanded user goal
is unmet: no candidate has demonstrated broad incremental market information or
professional-use reliability. Synthetic qualification cannot supply missing
multi-year outcomes, verified vintages or economic validation.

### Producer causality corrections

An upstream audit found a second reason not to certify reconstructed incumbent
values as point-in-time evidence. `calibrate_primary_outputs` globally skipped
all transforms below 66 months, then applied bottom persistence retrospectively
when more rows arrived. A synthetic 65-to-66-month extension changed 50 earlier
bottom components and DCA values. Commit `6da7fb0` removes this total-length gate;
each origin's existing mature-label/model-training guards remain in place.

The owning calibration-to-DCA oracle compares completed and partial prefixes,
future price shocks, regime warmups and extension warmups. Restoring the gate
fails eight prefix subtests. Isolated old/new source comparison is bit-exact for
series, downstream DCA and metadata at 66/80/160 months, including a case with
17 actual bottom-calibration training steps. This fixes history consistency,
not forecast performance. Frozen market data/results and canonical release
identities are unchanged. The local model fingerprint changes and remains an
unaccepted correctness revision.

The same audit reproduced whole-invocation total-market coverage changing ten
earlier output columns. Commits `949b226` and `bf153c7` route proxies per date,
using cumulative observations and trailing 90-row coverage. Inactive metrics
contribute neither scores nor expected-metric coverage; wholly inactive
categories contribute zero coverage weight. Historical feature exports retain
eligibility; current metric health describes the final-date route. Eligibility
participates in normalized-input/export content hashes.

The producer oracle independently inventories all 43 dated output columns,
feature frames and both attribution layers. Seven synthetic pipeline runs
(at most 943 days, 26.95 seconds) cover 364/365 observations, 72/90 versus 71/90
coverage, restored availability and perturbed future numeric inputs. Configuration
and source-mode metadata stay fixed. Aggregate benchmarks/newly resolved labels
and current health metadata are explicit exclusions. Old-route and wrong-coverage
mutations fail the oracle. Independent review caught and verified the
all-ineligible-category correction. Revised inputs and unknown timestamps remain
separate limitations; this is a tested fixed-input prefix contract.

The complete causal/coordinator slice passed **337 backend tests in 144 seconds**.
Local model fingerprint is now
`71657a22230f4ebd5488b5c869731bb1f5ea4acadee083f3beefea006fde204d`;
the acceptance CLI reports `changed=true`. Published canonical identity stays
unchanged. No source cache, market result, release acceptance or deployment was
updated to conceal that difference.

### Registered daily-price forecast baseline and completed development run

The CDF decoder's zero four-year development forecasts are a protocol-specific
training-pool constraint. A model of daily returns can forecast a long holding
path without 24 mature four-year labels. That does not create more independent
four-year market cycles or establish calibration. Before further indicator
tuning, test one conventional price-only predictive family as a stronger
reference challenge. One registered development run is complete; source and
parameters stayed fixed, with no outer fit or outcome-dependent retuning.

Reviewed source `6150199` implements a fixed Student-t5 volatility path model,
fitted on exactly 730 prior daily log returns. Its unit-variance shock is
sqrt(3/5)*t5; variance updates as .01*s² + .05*(r-mu)² + .94*h. Only mu and s
are estimated, under s~HalfNormal(.05) and mu|s~Normal(0,s²/365). These are
heuristic predeclared assumptions, not a fitted trading thesis. Each of 8,192
paths draws its joint parameters once and retains them. An unobserved next-day
entry shock updates variance but is excluded from holding profit/downside;
12/24/48-month outcomes share each maximum-horizon path.

The posterior is a finite-domain deterministic approximation in mu/s and log(s),
with fixed bounds, 65² coarse localization and 65²/129²/257² refinement. It must
pass density-L1 .005, log-normalizer-change 1e-4, scaled-moment-change 1e-3 and
edge-strip-mass 1e-6 checks, or return a visible failure. These are numerical
proxies, not rigorous excluded-tail or misspecification guarantees. Independent
original-coordinate integration and analytic holding-variance/H² drift-uncertainty
checks pass. A fixed [nine-case numerical preflight](artifacts/generative-price-preflight-2026-11-07.json)
converged without tuning or failures in 4.92 seconds. This does not test posterior
calibration. The chosen recursion has no stationary fourth moment; Student-t
log returns have no finite positive exponential price moments. Do not report
simulated mean wealth or precise extreme-tail claims.

The new scorecard must report exact matched-CDF origins separately from all
730-return-eligible origins. More forecast coverage is not superiority. Keep
all targets, horizons, roles and two predeclared simulation replicas separate;
failures withhold complete-support means. Seeds depend on fixed base/date/replica,
never full snapshot hashes or row positions, so future data cannot change earlier
Monte Carlo forecasts. Existing event thresholds and 50%/80% interval diagnostics
remain unchanged. Input/replica/code/runtime identities are frozen in the
[one-run registration](artifacts/generative-baseline-registration-2026-11-07.json)
before the first fit; no outcome-dependent retuning is authorized. It requests
109 fit origins, with 96/84/60 completed development outcomes per target at
12/24/48 months. Matched CDF counts remain 48/24/0. Additional four-year forecasts
do not supply a four-year outer comparison or independent market cycles. The
two replica bases are 20270529 and 20270530.

Monte Carlo paths represent draws from an underlying law, rather than the issued
finite CDF used by earlier readouts. Use finite-ensemble-unbiased CRPS and Brier
estimates for the generative law, retain empirical scores/corrections, and leave
exact reference-CDF scores unadjusted. This avoids rewarding more simulation
particles as if they added information. The independence assumption is essential;
see [Ferro's fair scoring rules](https://empslocal.ex.ac.uk/people/staff/ferro/Publications/ferro2013.pdf)
and the [scoringrules interpretation guide](https://scoringrules.readthedocs.io/en/latest/crps_estimators.html).

The [completed results](artifacts/generative-baseline-development-2026-11-07.json)
and [portable scorecard/reference/audit packet](artifacts/generative-baseline-development-2026-11-07.zip)
bind all 109 successful fits, 1,962 generated records and 855 aggregate cells.
Approximate wall time was 103 seconds. All 3,240 scored reference CRPS values
reproduce exactly. Independent audit verified every input window, raw outcome,
support, aggregate and replica comparison. Three fixed dates regenerated both
replicas: posterior/sample hashes match, and 36 scored records agree with
independent quadratic/U-statistic scores within 2.89e-15. Eighteen pending
records stay unscored. The full backend suite passes **356 tests in 150 seconds**.

Matched development CRPS (lower is better; two simulation replicas shown):

| Months | Outcome | Generative replicas | Unconditional | Best fixed CDF |
| --- | --- | --- | ---: | ---: |
| 12 | Terminal log return | .6550 / .6533 | .8585 | .8109 |
| 12 | Entry adverse loss | .3062 / .3059 | .3619 | .3512 |
| 12 | Peak drawdown loss | .3283 / .3278 | .2823 | .2602 |
| 24 | Terminal log return | .7052 / .7066 | .3311 | .4119 |
| 24 | Entry adverse loss | .1545 / .1548 | .2494 | .2270 |
| 24 | Peak drawdown loss | .2750 / .2760 | .3006 | .2740 |

The one-year return CRPS improvement is about 19% versus the fixed-CDF envelope,
but its loss-event Brier score is worse (~.277 versus ~.258) and nominal 80%
coverage is only 47.9–50%. Entry-loss CRPS/Brier improve at both matched horizons;
the two-year CRPS improvement is about 32% versus the fixed-CDF envelope. Neither
finding repairs the primary two-year return regression. Across 60 additional
four-year origins, return coverage is only 45–46.7% and peak-drawdown coverage
28.3%. There is no matched four-year CDF comparator. These overlapping outcomes
are not independent market cycles or a new holdout. More forecast availability
does not establish better forecasting.

Keep this model as a stronger *partial reference*, not the primary indicator or
a calibrated risk forecast. The scorecard correctly exposes improvements in one
loss alongside regressions in another; do not average them into a winner. No
source, prior, recursion, numerical tolerance or simulation budget was tuned
after the result.

## Verification and handoff

This task specifies the benchmark and implements synthetic pilots, a real-data
retrospective measurement tool and a failed whole-path qualification. It does not
demonstrate a better market indicator. No new market dataset was downloaded and
no production model was trained. Research readouts were fitted on strictly mature
historical labels. Astra medium and two other model perspectives independently
reviewed the design, timing and implementation. A reviewer caught cross-horizon
selection leakage before the registered run; the common-boundary invariant and a
deliberately failing mutation now guard that relationship.

The implementation plan now serves the requested information-indicator goal;
strategy-specific wealth optimization is explicitly outside the primary score.
Historical data quality, vintage eligibility, market false-positive rates and
external-market transfer remain unverified. Market readout feasibility is measured
under each stated protocol: mature-label CDF four-year development/outer forecasts
remain unavailable; the new generative four-year reconstruction is measurable
and fails important calibration checks.
Each synthetic experiment measures rates only under its specified procedure and
generator; none establishes the market scorecard's automatic promotion validity.
The strongest alternative explanation for an apparent future leaderboard gain
will be adaptive fitting to a few shared market eras. Keep that risk visible.

The independent actual-data E2E replay checked all 1,776 forecast records against
raw daily prices, strict split boundaries and a quadratic CRPS calculation. An
exact incumbent submission reproduced every prediction; a missing date failed
without altering the immutable baseline. A fixed noise submission changed only
its dependent result. Portable snapshot replay reproduces benchmark identity
`7b4a52c04577d92d40501965a5c01d801b62c3d31306d7297db08ded9cfb57cb`.
The scorecard slice passed all 195 backend tests, including 17 new focused tests.
The oracle/conditional-search slice passed all 206 backend tests, including 11
further tests. Its independent mathematical review found no blocking defect;
11 reintroduced defects were caught, including return-lag errors, incorrect
state prior scale, omitted future innovations, future-score leakage, wrong
Gaussian CRPS, invalid tie/+1 ranks, lost candidate dependence, audit selection,
failure to reselect on redraws and incorrectly marking the failed parent as passed.
Existing pandas future warnings remain; no hosted CI or frontend checks were needed for this
offline-only change. Eleven deliberately reintroduced defects were
caught in isolated copies, including entry lag, false drawdown, missing support,
label maturity, cross-horizon timing, CRPS, duplicate-context shrinkage, runtime
drift, unbounded attempts, corrupt receipts and nonfinite zero-loss references.

The published/frozen research model fingerprint remains
`21a4b0160e184a67f141c57202b46e455ccc92791961430493c7d250ee5c053d`.
Local producer correctness changes are unaccepted and must clear the release
gate before publication; no canonical identity was rewritten. Earlier research commits are
`573de0d`, `b260774`, `349b973`, `fe04721`, `e5d71b1` and `51bb110`; scorecard
implementation is `a35a3f9`, whole-path qualification is `92e8a27`, the observed-score
oracle is `631063b` and conditional randomization is `e5f26e2`. Josh explicitly
requested keeping all commits local; no push or deployment is authorized. The
remote advanced independently with automated data refresh `4d9789b`; it was not
merged into this held research checkout or used to alter the frozen evidence.
All reviewed slices above are merged into local main at `948677b`. Completed
task branches were deleted after ancestry and clean-tree checks. Two managed
worktrees were archived; the app refuses to remove its primary checkout, so
the remaining clean managed checkout is detached at the merged main revision.
No force removal was attempted. Local main is 79 commits ahead and one automated
data-refresh commit behind origin at this integration point; no push, remote
merge or deployment occurred. The two untracked
user directories `.codex/` and `.github/hooks/` are preserved. This document owns
the project-specific lessons; the skill-harvest/self-improvement review found no
additional global skill change necessary.

### Active-goal completion audit

| Requirement | Current authoritative evidence | Status |
| --- | --- | --- |
| Detect useful information under dependent worlds | Gaussian oracle and registered panel test, 398/400 positive declarations | Pass in finite known-law panel scope; previous single-path searches still fail |
| Control false promotion under declared dependent nulls | Whole-path CRT exchangeability under exact Q, full-search equivalence tests, 1,500 fresh null campaigns | Pass within the declared one-campaign synthetic scope |
| Chronological/provenance integrity | Strict label boundaries, frozen measurement hashes, 43-column producer oracle and immutable receipts | Verified fixed-input mechanics; historical market vintages explicitly unverified |
| Safe adaptive-search scope | Registered conditional tests, shared attempt/freeze/release ledger and explicit exposure lineage | Finite scope defined; unlimited human adaptation not qualified |
| Local-only changes | Atomic commits integrated into local main, frozen evidence and completed-branch cleanup | No push/deployment; clean app-primary worktree retained by app constraint |

Do not mark the goal complete while useful-signal sensitivity or the expanded
market-improvement objective remains unmet. Panel qualification, honest market
comparison and prospective validation are separate requirements. All work remains
local. The next bounded implementation is a frozen stronger-reference comparison
guard for future campaigns, followed by one external-market falsification adapter.
