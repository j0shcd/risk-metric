# DCA Risk Evidence

Status: current-source descriptive replay complete; production acceptance unresolved

Latest replay window: 2014-12-31 through 2026-10-31

Last evaluated: 2026-11-10

The [indicator benchmark redesign](metric_evaluation_plan.md) is the current plan
for future evaluation. It moves primary optimization from one contribution policy
to information value on identical fixed-notional opportunities. This page records
the implemented historical suite, not that proposed benchmark. Its policy cash
'deadline' and entry-relative drawdown naming have limitations recorded in the
plan. The November 9 replay below retains those policy semantics and adds an
explicitly separate equal-deployment diagnostic. The November 10 experiment tests
a new research target/readout; it changes no production model. August results
remain historical.

## Six-month target and readout results: 10 November 2026

Status: registered research iteration complete; **no new variant beats Fixed DCA
at the historical median**. Josh confirmed the continuous six-month deferral
target. The [research plan](metric_evaluation_plan.md#training-target-and-readout-implementation-request--november-10)
owns its definition, chronological training/calibration, synthetic assessment,
forecast losses and next proposed work. Production code, thresholds, source
settings and acceptance gates are unchanged.

All rows use the same 96 overlapping 48-contribution windows and frozen October
2026 snapshot as the earlier equal-deployment comparison: identical monthly
funding and closes, prior-month signals, 0.20% purchase costs, no sales/borrowing,
zero cash yield, and all unspent principal bought at the final close. Thus BTC
units and terminal wealth have the same relative difference, and each strategy
spends exactly 48 contribution units. Neither strategy receives earlier cash.

| Arm | Median BTC difference vs Fixed DCA | Wins | 10th–90th percentiles |
| --- | ---: | ---: | ---: |
| Fixed DCA | 0.00% | Reference | 0.00% to 0.00% |
| Incumbent | −19.22% | 23/96 | −72.26% to +11.54% |
| Incumbent, six-month cash-wait cap | −9.19% | 27/96 | −36.73% to +7.77% |
| Incumbent, DCA until component model first fits | −0.34% | 47/96 | −22.51% to +11.54% |
| Six-month target, empirical latest-24 | −31.24% | 4/96 | −42.96% to −0.06% |
| Empirical split-24, separate fit/calibration | −39.07% | 5/96 | −56.31% to −1.94% |
| Gaussian split-24, same fit/calibration support | −17.48% | 16/96 | −30.26% to +0.36% |
| Gaussian expanding, composite | −21.91% | 5/96 | −31.21% to −1.41% |
| Gaussian expanding, four components | −9.43% | 20/96 | −28.10% to +0.50% |
| Gaussian expanding, price-only | −20.15% | 5/96 | −36.35% to −1.15% |
| Gaussian expanding, pooled | −30.18% | 5/96 | −48.25% to −1.89% |

Quantiles describe dispersion across this finite, exposed, dependent history;
they are not confidence intervals or 96 independent trials. New forecasters buy
the current contribution as DCA during training warm-up, then use the frozen
probability adapter. The matched incumbent control uses precisely the component
model's learned/fallback mask. It shows why comparing −9.43% with −19.22% alone
would overstate learned improvement: even that control achieves −0.34%.
On paired windows, the component model wins 36/96 against the matched incumbent,
with median BTC ratio difference **−1.24%**. Against Gaussian price-only it wins
65/96, with paired median **+3.79%**. These are medians of window-by-window ratios,
not differences between the table's separate median rows.

The era diagnostic is adverse for every new forecaster: **zero wins in all 59
windows starting in 2018–2022**. The component version's median is +0.12% for
2014–2017 starts, −13.04% for 2018–2020 and −27.72% for 2021–2022. Its latest
November 2022–October 2026 window is −21.69%, versus incumbent −1.86%. The
component model reduces median contribution waiting to 3.44 months and terminal
sweeps to 5.70% of funding, but those mechanical changes do not make its timing
profitable. A six-month training target does not itself impose a six-month cash
deadline; only the explicitly capped incumbent row has that rule.

The [summary](artifacts/target-readout-2026-11-10/summary.json), adjacent per-window
and era CSVs, and [figure](artifacts/target-readout-2026-11-10/comparison.png) retain
all arms. The [portable packet](artifacts/target-readout-2026-11-10.zip) includes
frozen source/inputs, all synthetic and BTC forecast records, output hashes and
an independent checker. Two independent ledger implementations agree across
1,056 windows. The forecast audit finds poor coverage and a fitted Gaussian tail
instability; better policy results in some arms do not establish better forecasts.
The research plan records all failures rather than selecting a winner afterward.

Brief versus delivered: the confirmed continuous target and fully invested equal
budgets are implemented and tested. DCA outperformance, live point-in-time data
readiness and production acceptance are not achieved. Next bounded work is a new
registered scale/calibration and explicit expected-BTC decision study, as proposed
in the research plan; it has not run. No candidate is promoted from these results.

The website's Track record now displays this frozen equal-budget evidence, replacing
the August three-test presentation. Visitors select one of the 96 complete 48-month
periods and a monthly USD contribution. BTC, ending USD value and final catch-up
spend scale linearly; the selected relative result and cash waiting are unchanged
by the amount. The default is the latest period with $100/month, not a selected
winning period. All ten alternative/control summaries remain in the existing
view's disclosure. This adds no new market evaluation, source refresh or model
acceptance; the remaining research step above is unchanged.

## Fresh comparison: 9 November 2026

Status: replay complete against source `4211817`, with independent ledger checks.
This is a descriptive rerun of the existing accumulation contract, not model
selection or a production acceptance decision. Both strategies receive identical
monthly cashflows, trade at the same closes, pay the same 0.20% costs, and use
prior-month scores. The credential-free acceptance runtime fixture defines the
current model configuration. Cached inputs are frozen and truncated before model
execution at the last complete month, 31 October 2026; no provider refresh occurs.

Equal contributions do **not** imply equal deployment. The unchanged policy may
hold cash earning the existing assumed 3% annual yield. Report contributions,
executed purchases, BTC units, ending cash and total wealth separately. Alongside
the legacy variable-length windows sharing one endpoint, report every exact
48-month window to distinguish early-start and horizon effects.

A supplementary equal-deployment diagnostic uses the same 48 monthly budgets,
no sales, no borrowing, zero cash interest and a final-date sweep of all unspent
cash. Both strategies then spend exactly the same principal. BTC-unit advantage
measures entry timing under that additional deadline policy; it must not be
presented as the unchanged model policy or a deployment-independent measure of
signal quality. Delayed exposure is part of a timing strategy's economic cost;
equal final deployment does not equalize time in the market.

The replay script is `scripts/evaluate-dca-snapshot.py`. It captures source and
data bytes before importing the model, rejects network attempts, runs in its own
captured checkout and records resolved configuration, versions and output hashes.
Overlapping historical windows are dependent and already exposed to research.
Report exact finite-history medians, quantiles and counts; do not attach IID
confidence intervals or describe this as prospective evidence. Cached macro
release vintages remain unverified, and some inputs end before the BTC cutoff.

### Results under equal contributions and equal horizons

Each row below covers the same 96 overlapping windows, each containing exactly
48 monthly contributions. Starts range from December 2014 to November 2022;
endpoints range from November 2018 to October 2026. Wealth includes all remaining
cash. Changes are relative to Fixed DCA within each window, then summarized by
the median; they are not medians of dollar balances or forecasts.

| Risk-based accumulation scenario | Median wealth difference | Wins vs Fixed DCA | Median purchases / contributions |
| --- | ---: | ---: | ---: |
| Unchanged policy, cash allowed at 3% yield | -17.64% | 26/96 (27.08%) | 38.52% |
| Same full budget deployed, final-date sweep, zero yield | -19.22% | 23/96 (23.96%) | 100.00% |

In the equal-deployment row, the median BTC-unit difference is also **-19.22%**:
both strategies spend exactly 48 contribution units, end with zero cash, and
value their BTC at the same close. The central 80% of window differences runs
from -72.26% to +11.54%; this is historical dispersion, not a confidence interval.
The price-only comparator has a -15.45% median and wins 44/96 under the same
equal-deployment rule. This does not identify a universal best policy.

The early-history concern matters. An exploratory calendar split of the
equal-deployment results gives:

| Start years | Windows | Median BTC/wealth difference | Wins |
| --- | ---: | ---: | ---: |
| 2014–2017 | 37 | -63.58% | 0/37 |
| 2018–2020 | 36 | -18.00% | 5/36 |
| 2021–2022 | 23 | +7.55% | 18/23 |

The latest window, November 2022 through October 2026, is -1.86% with full
deployment, versus +0.15% with cash allowed. These post-hoc strata explain why a
single headline is incomplete; recent windows still overlap and share endpoints
and regimes, so they do not establish a new out-of-sample edge.

The unchanged compact suite's variable-length windows, all ending October 2026,
give a -21.95% median and 28/96 wins for accumulation. Fixed monthly buys plus
risk-based sells have a -15.45% median; risk-based buys and sells have -29.17%.
De-risking an existing one-BTC position retains its diagnostic pass, while the
48-month signal-ordering test fails. These are different investment questions.
Do not compare the new -21.95% directly with August's -21.46% as a pure source-code
effect: the data snapshot and endpoint also changed.

### Evidence, verification and remaining limits

The [portable evidence](artifacts/dca-evaluation-2026-11-09/summary.json) binds the
source/configuration/input inventory, raw and truncated identities, dependency
versions, generated table hashes and checked summaries. The adjacent CSVs retain
monthly price/score inputs and the per-window/full-period results. Raw macro
captures are retained only in the local scratch replay and are not republished.
The [static comparison figure](artifacts/dca-evaluation-2026-11-09/comparison.png)
shows the full start-date distribution and corresponding deployment amounts.

`scripts/check-dca-replay.py` independently reconciles cash and BTC ledgers,
cashflows, fees, final spend and zero-cash equality. Wrong table hashes, corrupted
cash accounting and unequal deployment were deliberately introduced in disposable
copies; all three were rejected. No model source or repository data was changed.
The compact suite's execution/suffix-invariance audit passed. This audit does not
verify historical release vintages or full-pipeline point-in-time correctness.

At the cutoff, DXY is 99 days stale, real yields 94 days, and YouTube 92 days.
The pipeline's original source-health table measures age against the run date,
so even a deliberately frozen BTC series can be marked stale there. Neither
healthy-looking estimated availability rules nor this replay establish live data
readiness. The pinned package versions were recovered offline from cached expanded
distributions with RECORD integrity checks; original wheel hashes were not
revalidated. Model execution used Python 3.12.16, rather than CI's 3.11.18.

Reproduce in a disposable checkout of source `4211817` with the captured data
inventory and the pinned requirements. With `<python>` naming that interpreter,
and an absent `<run>` directory:

```sh
env -i PATH=/usr/bin:/bin HOME=/private/tmp TMPDIR=/private/tmp \
  <python> -I scripts/evaluate-dca-snapshot.py \
  --root "$PWD" --as-of 2026-10-31 --output <run>
<python> -I scripts/check-dca-replay.py <run>
```

The replay/check scripts belong to this evidence commit and must be available in
that source checkout. The optional checker `--plot <path>` flag requires matplotlib
and saves a static figure without opening a window. The recorded figure used
matplotlib 3.11.2 in a separate plotting environment; the model inputs and scores
were generated with the pinned model environment.

Brief versus delivered: descriptive current-model/Fixed-DCA comparison, identical
monthly cashflows, prior-month actions and costs are as briefed. The user-confirmed
full-deployment check and exact-length windows supplement the legacy suite; no
threshold was optimized. Inference about future profitability, verified vintage
availability, and formal production acceptance remain unanswered.

Next bounded step: preserve these results without tuning on them; reproduce the
canonical model and candidate on a common frozen protocol before any production
acceptance decision. The separate information-value contract remains the open
decision in the research plan. No model, canonical baseline, threshold, provider
setting or deployment approval was changed by this replay.

## Underperformance diagnosis: scope and fixed diagnostic arms

Status: diagnosis complete against source `4362633`; all findings remain
exploratory and no production model changed. Reuse the accepted
equal-budget brief above: 48 monthly contributions, full terminal deployment,
no borrowing or sales, 0.20% purchase costs, zero cash yield for the matched-spend
comparison. This is a deterministic decomposition on the same exposed price
path, not evidence of market causation or a new protected test. The decision is
which failure mechanism and bounded follow-up deserve attention; no production
model, threshold or research acceptance contract will change.

Protocol commit `5000a26` fixed these 17 diagnostic arms before counterfactual
measurement, retaining every result: Fixed DCA; incumbent; price-only; raw directed four-component mean
without the second min/max transform; each of four existing normalized components
alone; each of four leave-one-component-out means; causal expanding percentile
of the composite (24 observations before use, incumbent during warm-up); inverted
composite as a direction diagnostic; incumbent with a six-month FIFO deployment
deadline; a blind six-month delay; and 80% Fixed DCA plus 20% incumbent as an exact
allocation identity. All score decisions use the previous month. The final sweep
is identical across arms. The six-month deadline follows the glossary's intended
indicator horizon; it is an exploratory control, not an adopted investor rule.

Quantify score/action frequency, repeated component information, FIFO waiting
times, budget still awaiting the terminal sweep, contribution-cohort BTC gains
or losses, and calendar-era differences. Compare alternative ledgers with the
already published incumbent and Fixed DCA outputs before interpreting them.
No threshold/weight search, hidden retries, significance leaderboard or winner
promotion is permitted. These arms add exposure history; they do not reopen the
research programme's spent trials or run new market-information benchmark trials.
The current forecast readout's synthetic limitation and the proposed separate
readout study remain owned by [the research record](metric_evaluation_plan.md).

### Why the current policy loses

The ledger identity is exact within the declared simulation. For monthly price
`P_t` and gross purchases `b_t`, the BTC difference from Fixed DCA is
`0.998 * sum((b_t - 1) / P_t)`, with `sum(b_t) = 48`. Equal final spend does not
remove the cost of delaying a contribution through a price increase. No market
impact, taxes, borrowing or changing transaction-cost curve is modeled.

1. **The policy waits too long on this history.** Across the 96 windows, the median
   dollar-weighted waiting time is 14.09 months. A median 61.48% of contributions
   still require the final sweep; the median window has only 12 scheduled-buy
   months. In the continuous incumbent ledger, two purchases in April/May 2015
   are followed by **37 consecutive no-buy months, June 2015 through June 2018**.
   The 0.25 threshold and three-contribution maximum purchase mean a later low
   score may take many months to deploy accumulated cash. The legacy 48-month
   rule only starts buying one contribution per month; it does not clear old cash.
2. **The loss is concentrated in missed early funding opportunities.** The first
   December 2014–November 2018 window loses 70.22% of BTC units. Under the stated
   FIFO bookkeeping, its 2015 and 2016 contribution cohorts account for -45.49
   and -24.39 percentage points of that window's difference. FIFO is one assignment
   of fungible dollars, not a unique economic attribution; the total BTC difference
   is independent of that convention. In this window, 83.09% of the budget waits
   for the terminal sweep.
3. **The bottom-weight selector never gets a learnable positive class.** Under
   `_long_cycle_labels` with the accepted 36/48-month horizons and 24-month
   lookback, there are 59 mature labels: **zero positive bottoms**, 59 negatives.
   A positive must be a two-year price low and have sufficiently high subsequent
   average 36/48-month returns, using frozen historical outcome cutoffs. The
   selector requires at least three observations of each class, so it never fits
   bottom weights in this snapshot. Its output is the base heuristic plus the
   existing persistence transform. Top labels have 10 positives/49 negatives;
   only 26 months are class-count eligible for top fitting, starting September
   2024. The early losses cannot be described as a mature learned timing model
   being repeatedly retrained throughout history.
4. **Equal averaging adds several versions of cycle information.** The normalized
   bottom and regime components have correlation 0.908 in these 143 months; all
   pairwise component correlations range from 0.658 to 0.908. The four-way average
   is not four independent confirmations. All-time min/max transforms also change
   numerical scale as new extremes arrive, while the policy retains 0.25. These
   are plausible construction weaknesses, not isolated causal explanations:
   removing that transform outright makes the measured policy worse.

### What the fixed controls actually improve

Every row uses the same 96 windows and full 48-contribution deployment. Values
are exact finite-history descriptions. The full
[17-arm results](artifacts/dca-diagnosis-2026-11-09/summary.csv),
[era breakdown](artifacts/dca-diagnosis-2026-11-09/eras.csv) and
[dispersion figure](artifacts/dca-diagnosis-2026-11-09/comparison.png) retain failures
as well as gains. The figure's bars are historical 10th–90th percentiles, not
confidence intervals. No significance test or winner-selection rule was used.

| Diagnostic arm | Median BTC difference vs Fixed DCA | Wins / 96 | Interpretation |
| --- | ---: | ---: | --- |
| Current composite | -19.22% | 23 | Reference being diagnosed |
| Current score + six-month FIFO deployment cap | -9.19% | 27 | Reduces waiting damage; still loses overall |
| Blind six-month delay | -20.39% | 0 | Delay control; not matched for realized exposure |
| Normalized top-reversal component alone | +2.41% | 56 | Promising post-hoc simplification, fragile across eras |
| Remove top-reversal component | -25.60% | 0 | Other components alone do not rescue this policy |
| Causal percentile of current composite | -14.54% | 20 | Scale change reduces loss, without a reliable win |
| Remove the extra min/max transform | -28.57% | 2 | Simple normalization removal fails |
| Reverse the composite | -48.12% | 0 | The score is not fixed by flipping its direction |
| 80% Fixed DCA + 20% current policy | -3.84% | 23 | Exact capital-allocation identity, not additional information |

The overlay's percentage difference is exactly 20% of the incumbent's difference
in each window, so its wins cannot improve. It reduces exposure to a losing policy.
The six-month cap reduces the difference between reported medians by 10.03
percentage points; the paired median window improvement is 12.27 points, a
different summary. Neither result establishes six months as an optimal delay.
The capped and blind controls also have different realized waiting times; their
gap does not isolate the score's predictive information from exposure timing.

Top-only earns its +2.41% median with a -43.78% tenth percentile. For 2014–2017
starts its median is **-31.86%**, versus +7.40% in 2018–2020 and +4.79% in
2021–2022. The latest window is +4.79%. Component/scaling ablations jointly change
the score, trigger frequency and purchase size under the fixed numerical policy.
They therefore do not isolate intrinsic information quality. A new top-only
production model, optimized weights or a calibrated profit forecast do not follow.

### What would improve the project next

There are measured reductions in historical policy damage, but **no newly
validated model improvement**. Recommended next work, in dependency order:

1. **Make learnability explicit before another training attempt.** Retain strict
   label maturity, and report per-selector class counts, fit count and fallback
   state. The existing `walkforward_steps_bottom` is already zero; the broad
   `calibration_applied` flag alone does not mean bottom weights were fitted.
   A claim of learned/calibrated bottom skill must require actual eligible fits.
   Specify a target with enough support to estimate, potentially continuous
   opportunity/return and downside outcomes. Changing the target is a separately
   registered study, not a silent repair of these labels or a new product claim.
2. **Complete the already-proposed readout study before more feature searches.**
   The [current sensitivity audit](metric_evaluation_plan.md#current-readout-sensitivity-audit--november-9)
   found useful synthetic state worsened the research decoder's primary two-year
   forecast loss. Its 24-label binning and limited outcome support are candidate
   mechanisms. Compare a small frozen set of simple continuous/shrunk distribution
   readouts with the unchanged decoder, using new synthetic histories and distinct
   information laws. Require useful-input sensitivity, no-information controls
   and calibrated uncertainty before spending another market candidate slot.
   This is separate from the legacy model's empty bottom class. Neither finding
   establishes that a new readout will beat Fixed DCA or that all market inputs
   lack information.
3. **Carry top-only and bounded deferral as hypotheses, not adopted fixes.**
   After the measurement/target contract is settled, a bounded comparison can
   retain the incumbent, Fixed DCA, top-only and one prespecified capped policy.
   Count this diagnosis in the exposure ledger, keep all adverse eras, and test
   new frozen observations without retuning on them. A DCA-heavy overlay can
   constrain policy damage mechanically, but it cannot demonstrate timing alpha.

Proper scoring rules assess the quality of a forecast distribution;
[Gneiting and Raftery](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf)
provide the foundation. Correct loss arithmetic does not establish that a
particular sparse forecast readout can extract useful information. Chronological
splits must also respect outcome maturity; the official
[TimeSeriesSplit documentation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
describes time ordering and an explicit training/test gap. A split label alone
cannot certify historical input vintages or make overlapping BTC cycles independent.

The stale recent macro inputs remain an operational and vintage limitation. They
do not explain away the demonstrated 2015–2018 cash deferral, and refreshing them
is not a measured model improvement. No providers were called in this diagnosis.

### Verification, portability and remaining decisions

The [protocol](artifacts/dca-diagnosis-2026-11-09/protocol.json),
[result identity](artifacts/dca-diagnosis-2026-11-09/summary.json) and
[verification record](artifacts/dca-diagnosis-2026-11-09/verification.json) bind
the frozen arms, authenticated input bytes, scripts and retained outputs.
`scripts/diagnose-dca-underperformance.py` regenerates the diagnosis from the
previous replay's hash-checked `daily_scores.csv`; it parses captured bytes rather
than reopening the source path. If that local file is gone, regenerate it with
the earlier replay script and recorded source/data/runtime identities first.
`scripts/plot-dca-diagnosis.py` regenerates the optional static figure without UI.
The separate `scripts/check-dca-diagnosis.py` uses cumulative funding and interval
overlap to reconstruct balances, waiting times, forced purchases and cohorts
without importing the simulator. With the same pinned `<python>` environment and
an absent `<diagnosis>` output directory:

```sh
<python> -I scripts/diagnose-dca-underperformance.py --root "$PWD" \
  --daily-scores <replay>/tables/daily_scores.csv --output <diagnosis>
<python> -I scripts/check-dca-diagnosis.py <diagnosis>
```

Nine focused tests pass, including deliberately failing the new overlay
terminal-sweep regression before its classification fix. An independent Codex
reviewer reconstructed all 1,632 arm/window BTC balances with separate cumulative
funding logic (maximum discrepancy below 1.1e-16), checked all 4,608 incumbent cohorts,
confirmed hashes/score lag and the zero-positive bottom class, and found no
remaining substantive accounting/timing issue. The corrected overlay sweep share
is 20% of the incumbent's, with median 12.2952%; the correction changes no BTC
result, arm choice, parameter or weighting. Claude review was unavailable because
its subscription session was logged out; no API-billed review was attempted.
The portable arithmetic checker also passes all 1,632 balances and 4,608 cohorts.
Deliberately corrupted output hashes, sweep classification and cohort balances
are each rejected. All corrected result tables reproduce byte for byte on replay.

Brief versus delivered: the existing equal-budget question, dates, prices, costs
and prior-month execution are unchanged. This adds the fixed exploratory
mechanism/ablation set and label-feasibility audit. No causal market inference,
protected holdout, universal best indicator, adopted utility, prospective profit
or production acceptance is delivered. The strongest alternative to an intrinsic
signal-quality explanation is the demonstrated score-to-action/deferral policy
interaction; the separate flawed research readout also limits broader inference.

Next bounded implementation step: specify the small synthetic readout study and
its target/learnability checks in the research record before execution. The genuinely
open decisions remain the indicator's informational claim/outcome contract and an
acceptable deployment-delay constraint if a trading policy is later adopted.
No existing horizon or production gate was replaced by this diagnosis.

## Performance diagnostic and acceptance investigation: 9 November 2026

Scope: reproduce the existing ADR 0008/0009 contract, explain the failing legacy
CI diagnostic and identify promotion prerequisites. This investigation changes no
model, threshold, canonical metric, cached source or publication setting. The
[dated source/hash evidence](artifacts/performance-acceptance-investigation-2026-11-09.json)
is bound to `357d26bb0df8739598ffacef4c2c68500869811d`.

The [main CI log](https://github.com/j0shcd/risk-metric/actions/runs/42620541874)
reports eight threshold failures: bottom recall and false alarms, plus dynamic-DCA
CAGR and Calmar, each against both reference files. Those two files are byte-identical,
so this is four failed comparisons repeated, not independent corroboration.

| Logged legacy metric | Current | May reference |
| --- | ---: | ---: |
| Bottom lead recall | 45.16% | 98.57% |
| Bottom false-alarm rate | 37.27% | 22.20% |
| Dynamic-DCA CAGR | 11.44% | 80.10% |
| Dynamic-DCA Calmar | 0.496 | 1.381 |

These deterministic logged estimates are descriptive, not uncertainty estimates or
forecasts. They do not establish a like-for-like deterioration:

- References were last refreshed in `9007fb5` (15 May). In `426cea6` (31 July),
  dynamic DCA moved from contemporaneous frenzy/accumulation scores to lagged
  `dca_risk`, and from contribution-inflated portfolio balances to cashflow-adjusted
  time-weighted returns. Old raw balance growth and current investment returns
  have different meanings. The old 80.10% CAGR is not a valid target for the new
  accounting contract.
- `335b2cc` replaced full-history outcome quantiles, partially resolved horizons
  and event-count-dependent fallback labels with matured-outcome causal cutoffs
  and fully resolved horizons. `6da7fb0` later removed total-history-dependent
  calibration gating. Bottom recall is therefore being compared across changed
  labels/calibration. No decomposition has quantified each change's contribution.
- The reference JSONs carry no frozen data/runtime/protocol identity. Their
  numerical thresholds cannot certify comparability on their own. Version and
  replay a common correct measurement protocol before interpreting the delta;
  do not refresh references or relax thresholds merely to make CI green.

The diagnostic is intentionally nonblocking under ADR 0009. Production acceptance
instead reads `dca_evidence_summary.csv` and three audit/calendar tables, then
compares with `model_acceptance_canonical.json`. Its present minimum candidate
values are mechanical policy arithmetic:

| Acceptance metric | Canonical | Minimum candidate |
| --- | ---: | ---: |
| Accumulation wealth delta versus Fixed DCA | -21.4606% | -20.4606% |
| Fixed-buy/risk-sell wealth delta versus Fixed DCA | -9.2251% | -11.2251% |
| De-risking Calmar delta versus hold | 0.403166 | 0.353166 |
| 48-month low-minus-high return spread (raw return units) | -9.386120 | -9.486120 |

The primary requires **one percentage point better than canonical**, not a
one-percent relative gain and not necessarily beating Fixed DCA. Passing these
relative thresholds can still preserve poor absolute accumulation or ordering
results. The horizon, suffix-invariance audit and availability booleans must also
be true. Suffix invariance is a software timing check, not causal investment proof;
the availability boolean only rejects `missing_rule`, not estimated/unknown vintages.

Verified blockers and the next bounded work:

1. **Recoverable reference:** commit `4995a45` reproduces both canonical data hash
   `02ab9289…` and model hash `21a4b016…`; the tracked acceptance runtime fixture
   plus unchanged policy also reproduce canonical config hash `db8dba1a…`.
   Current cache hash is `f3cb5602…`, and current source with that fixture is
   `a4f2c695…`. The existing workflow uses current caches, so `data_fingerprint_mismatch`
   is inevitable before any performance-based approval. Recover that snapshot in
   scratch, or deliberately version a new common snapshot and recompute *all*
   reference metrics. Never put a new hash on old metrics.
2. **Freeze the actual evaluation:** the workflow fixes `RISK_END_DATE=2026-05-14`,
   while the recorded canonical evidence uses daily data through 30 July and
   labels its monthly endpoint 31 July. Raw file hashes do not bind the resolved
   as-of date, evaluator settings, dependency versions or generated score tables.
   Recover the historical run manifest and reproduce the canonical metrics first;
   settle a common complete-month cutoff. The partial-month resampler limitation
   is already recorded in the research plan.
3. **Bind evidence to the evaluated model:** `build_candidate_summary` currently
   reads CSV tables then attaches the *current checkout's* identity. It does not
   verify a producing manifest or score/config hashes. This is not evidence that
   this workflow used stale tables, but it permits accidental relabeling when
   the CLI is pointed at historical artifacts. Add boundary checks that reject
   stale/wrong-revision tables before trusting a promotion summary.
4. **Run the compact suite and full acceptance workflow:** on the same frozen
   snapshot and resolved settings, rerun canonical and candidate, retain manifests,
   score/table hashes and the seven policy checks, and inspect validation warnings.
   The workflow currently does not upload its candidate/report files; make failed
   and successful evidence retrievable. The investigation itself did not run a
   fresh candidate; the later descriptive replay above covers the compact suite,
   but has not completed the canonical/candidate production comparison.
5. **Choose the promotion route explicitly:** a model candidate must satisfy the
   existing policy before a reviewed atomic canonical update binds its identity
   to its new metrics. A score-preserving maintenance edit has zero improvement
   and fails the primary rule by construction. A separately specified maintenance
   route would need exact frozen-output equivalence, acquisition/error-mode tests,
   reviewed scope and immutable identity binding; none exists today. Do not silently
   exempt files or replace the canonical fingerprint.

The [research record](metric_evaluation_plan.md#accepted-requirements) says the
future product objective is information value, not wealth under one arbitrary DCA
policy. That new production contract is not accepted yet. Recommendation: repair
reference/evidence reproducibility first, then decide whether to retain the legacy
policy or adopt a separately reviewed indicator contract. Do not tune a model to
this obsolete CI diagnostic to unlock publication. Daily publishing should remain
withheld until the applicable reviewed promotion and resolved-settings checks pass.

Brief versus delivered: existing contract reproduced from code, history, logs and
hashes; no new predictive or causal conclusion, model search or policy adoption.
Limitations at the time of investigation: canonical metrics were not rerun and
candidate metrics/dependencies/as-of semantics remained unbound. The later replay
above supplies current descriptive metrics and protocol identity; formal acceptance
and historical-vintage verification remain unresolved. Historical results remain
exposed/reconstructed. The strongest alternative to a genuine
performance decline is the demonstrated change in accounting and label contracts.

## What is being tested

This section preserves the August 2026 suite description and results. The fresh
November replay above supersedes its current-performance claims.

The suite separates three questions that the previous combined strategy test could not distinguish:

1. Does DCA Risk improve accumulation when selling is prohibited?
2. Does DCA Risk add value when de-risking an existing BTC position?
3. Does the score itself identify better and worse forward-looking regions, independent of a trading policy?

The tests are diagnostics of the existing frozen score and default 0.25/0.75 policy regions. They were designed after historical data had already been observed and must not be described as prospective proof.

## Common rules

- Every decision uses the prior month's score. The monthly close cannot trade on itself.
- Results are evaluated from every monthly start date leaving at least 48 months, not one selected start.
- DCA Risk is compared with a causal price-only risk score. The comparator ranks log price relative to its trailing 48-month median using expanding history only; it has no future normalization.
- Trades pay the configured 0.20% fee and slippage.
- Idle cash earns a declared 3% annual yield.
- Future-suffix mutation tests must leave all earlier scores, trades, and ledger states unchanged.

A stop-loss is intentionally outside the compact core: it answers a short-horizon loss-control question rather than whether broad valuation regions are informative. It can remain an exploratory benchmark without becoming another headline test.

## Test 1: accumulation only

Every strategy receives the same monthly contribution. Selling is prohibited.

- `fixed_dca` invests each contribution immediately.
- `risk_accumulation` accelerates purchases in the frozen low-risk region.
- `price_only_accumulation` applies the identical purchase mechanics to the causal price-only score.
- Deferred contributions must begin forced deployment after 48 months, matching the declared cycle-scale horizon and preventing permanent cash from masquerading as risk control.

Primary evidence across 93 rolling starts:

- DCA Risk accumulation beat Fixed DCA in 26.88% of windows.
- Median terminal wealth was 21.46% below Fixed DCA.
- It did outperform the price-only accumulation rule by 2.97 contribution-denominated wealth units at the median.

Verdict: not supported versus Fixed DCA. The score was better than this particular price-only timing rule, but deferral still imposed more opportunity cost than it recovered.

## Test 2: de-risking

Every strategy starts with exactly one BTC and no later contributions. This removes the early-funding and contribution-timing confound.

- `hold` never trades.
- `risk_derisking` sells progressively in the frozen high-risk region and redeploys progressively in the low-risk region.
- `price_only_derisking` uses the identical trade mechanics with the causal price-only score.

Primary evidence across 93 rolling starts:

- DCA Risk finished above hold in 68.82% of windows.
- It had a higher Calmar-like return/drawdown ratio in 90.32% of windows.
- Median maximum-drawdown reduction versus hold was 24.18 percentage points.
- Median Calmar improvement versus hold was 0.403 and versus the price-only policy was 0.457.

Cashflow-policy attribution adds the requested exit-only strategy under identical contributions:

| Strategy | Median wealth delta vs Fixed DCA | Win rate vs Fixed DCA |
| --- | ---: | ---: |
| Risk-varying buys only | -21.46% | 26.88% |
| Fixed monthly buys + risk-based sells | -9.23% | 5.38% |
| Risk-varying buys + risk-based sells | -26.01% | 26.88% |

This is an important split: risk-based selling helped an investor who already held one BTC, but did not beat Fixed DCA when layered onto an ongoing contribution plan. Exit timing appears more valuable than purchase timing, yet its value depends strongly on the investor's starting exposure and cashflow problem.

Verdict: historically promising for de-risking. This was the strongest part of the August snapshot, but it is reconstructed rather than prospective and the default thresholds were created with knowledge of Bitcoin history.

## Test 3: policy-independent signal value

Each observation is assigned to the frozen low (`≤0.25`), mid, or high (`≥0.75`) region. The test measures subsequent 48-month return, maximum drawdown, and maximum rally without simulating trades. Circularly shifted score histories provide timing placebos.

| Signal | Horizon | Low minus high return | Low minus high drawdown | Return placebo p |
| --- | ---: | ---: | ---: | ---: |
| DCA Risk | 48m | -938.61% | -0.57 pp | 0.881 |
| Price-only risk | 48m | +163.90% | +46.22 pp | 0.390 |

Positive values are directionally useful: low-risk regions later returned more, while high-risk regions later suffered worse drawdowns. DCA Risk has the wrong ordering over 48 months and is not unusual relative to its timing placebos. The simple causal price-only score has the expected ordering, but it also fails the timing-placebo threshold.

Only 92 overlapping DCA Risk observations remain, equivalent to roughly one non-overlapping 48-month observation after the conservative overlap adjustment. Bitcoin's available history therefore cannot provide a well-powered, independent four-year statistical test. The large percentages should not be read as precise effect estimates.

Verdict: not supported as an independently reliable region-ranking signal.

## Interpretation

The revised evidence is not equivalent to “never sell is best.” It says:

- DCA Risk has not earned its opportunity cost as an accumulation-timing tool.
- The default DCA Risk regions produced a strong historical de-risk/re-entry policy relative to hold and the chosen price-only rule.
- That de-risking result is not corroborated by the policy-independent four-year region test, so it should be treated as promising but vulnerable to policy/path dependence and researcher degrees of freedom.

The appropriate product claim remains conservative until prospective releases accumulate. The three artifacts should be read together rather than promoting the one favorable result in isolation.

## Why realized cap is not the primary “average investor” benchmark

Realized cap values each UTXO at the price when it last moved; realized price divides that aggregate value by supply. It is reasonably described as a proxy for aggregate network cost basis, but not as a ledger of the average person's deposits, emotions, taxes, or realized return. See the [Coin Metrics definition](https://docs.coinmetrics.io/asset-metrics/market/capact1yrusd) and [Glassnode methodology](https://docs.glassnode.com/guides-and-tutorials/metric-guides/realized-capitalization).

It is also not independent here: DCA Risk already includes an MVRV-derived component, and MVRV uses realized cap. Benchmarking the composite against a realized-cap strategy would partly compare the model with one of its own inputs. The current reproducible store contains a causal MVRV z-score proxy, not raw realized cap or realized price.

Realized price may still be useful later as a clearly labeled behavioral anchor—for example, “did the strategy acquire below aggregate network cost basis more often?”—but it should not be promoted as an independent average-investor return benchmark without a separately versioned raw series.

## Regression and leakage protection

The evaluator and unit tests assert that:

- full and rolling accumulation ledgers receive identical external cashflows;
- accumulation policies never sell;
- de-risking policies start with the same one-BTC position and receive no contributions;
- executions use the prior month's DCA Risk value;
- mutating all future DCA Risk values cannot alter earlier accumulation or de-risking states;
- mutating future prices cannot alter the earlier causal price-only score;
- DCA Risk construction itself is prefix-invariant to future component mutations.

Any causality-audit failure blocks DCA evidence claims.

The legacy production model-acceptance gate uses equal-cashflow accumulation wealth versus
Fixed DCA as its primary improvement target. Exit-only wealth, one-BTC de-risking
Calmar, and 48-month region ordering are non-inferiority guardrails; causality and
source availability must remain true, and a dedicated gate prevents the signal
horizon from silently reverting below 48 months. The former registered 6/12-month
DCA AUC hypotheses are now exploratory and cannot promote a model.

This gate now runs in the explicit `model-acceptance.yml` workflow, separately
from research CI. Its thresholds are unchanged. Research commits do not approve
a model; the daily publisher refuses unaccepted source and model-setting changes.
See [ADR 0009](adr/0009-separate-research-ci-from-production-promotion.md) and the
[research record](metric_evaluation_plan.md) for the programme's current objective.

## Reproduce

```bash
python evaluate_metrics.py run-artifacts \
  --profile standard \
  --artifact-dir output \
  --run-id dca-evidence-three-tests
```

The main artifacts are:

- `tables/dca_evidence_summary.csv`
- `tables/dca_accumulation_windows.csv`
- `tables/dca_derisking_windows.csv`
- `tables/dca_policy_attribution_windows.csv`
- `tables/dca_signal_value.csv`
- `tables/dca_causality_audit.csv`
