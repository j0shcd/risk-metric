# Indicator benchmark and evaluation plan

Status: the registered six-month target/readout study is complete. None of seven
forecast variants beats Fixed DCA at the historical median; Gaussian uncertainty
remains poorly calibrated. Keep the continuous target as research infrastructure,
reject these variants for production, and specify a smaller forecast-scale and
decision-rule study before another assessment. Nineteen earlier indicator variants
remain unqualified under their unchanged two-year benchmark. The prospective paper
witness has no mature outcomes. No production model or acceptance gate changed.
Updated 2026-11-10.

This is the canonical maintainer record for the research benchmark, its measured
results and next bounded work. Legacy strategy-specific results remain in
[DCA evidence](dca_evidence.md). This replaces the older Phase 1/2 planning
narrative; Git preserves its implementation history. Published scoring,
acceptance policy and canonical metrics are unchanged. Research causality
corrections are published as code but remain unaccepted for production; no
canonical production identity was rewritten.

## Programme charter and current assessment

On November 7 Josh made the project's purpose a **small continuing research
programme**: keep the benchmark fixed, explore a few different ideas, record what
happens, and gradually improve if the evidence permits. A useful round can reject
an idea or reveal a measurement defect. It does not have to produce a trading
winner. The professional-use ambition remains a long-term hypothesis, not this
round's completion condition or a reason to wait without doing research.

The research question stays predictive: does a candidate improve forecasts of
future return or losses beyond strong simple references on identical dates?
Outputs do not trigger trades. The monthly unit, fixed historical snapshots,
12/24/48-month diagnostics, strict mature-label rules and separate outcome scores
remain unchanged. This round's declared primary check is two-year return forecast
error; improvement in another outcome cannot rescue its failure. We have no
adopted combined investor utility or universal automatic promotion score.

| Approach we have | Evidence and interpretation | Programme decision |
| --- | --- | --- |
| Existing composite and four components | Useful historical reference readings; no broad incremental information qualified; reconstructed vintages limit real-time claims | Keep as comparisons, not validated buy/sell advice |
| Simple price references and unconditional history | Competitive, sometimes strongest; they establish how much a new idea must add | Keep every fixed reference in the benchmark |
| Simulated price-path model | Better in some one-year return and entry-loss comparisons, worse in two-year return; uncertainty ranges often too narrow | Strong partial comparison, not an overall winner |
| Ten previous indicator variants | Price anchors, adaptive trend, gain shape, monetary state and attention did not qualify broadly | Preserve failures; do not retune them to repair exposed later-period scores |
| Chronology-assisted forecast | 19.7% development error reduction became about 74% worse than unconditional in the later check | Stop this branch; percentages concern forecast error, not investment returns |
| Artificial-market qualification | A separate continuous forecast/conditional-test procedure detected planted information 398/400 times and declared skill 24/1500 times under specified no-added-information cases | Finite scope only; not a sensitivity certificate for the current 97-date scalar readout or a market success-rate claim |
| Current scalar readout | Useful exact state worsens mean two-year forecast loss in the registered artificial law; nominal 80% intervals cover only 26.4% | Pause feature searches; preregister a separate readout study |
| Six-month target/readout study | Continuous labels fit; expanding Gaussian detects planted drift but remains miscalibrated and no market variant beats DCA at the median | Retain the experiment; no model promotion; stabilize scale and specify the decision objective next |
| Archived live baselines | Six forecasts reproduced exactly, zero mature outcomes | Continue separate forward collection; correctness is not predictive success |

### First completed round: three different remaining ideas

Registration `a36bd86` fixes three total benchmark attempts, one each for anomaly,
small supervised learner and ensemble. All source/configuration choices must be
frozen before any score. The shared v2 campaign is
`9fb56bebaac599590446489b4917ed97f1dd8581f7e206a8820f9e460de1c20c`,
retained under ignored `output/research-programme-round1-2026-11-07/`; its
[registration](artifacts/research-programme-round1-2026-11-07-registration.json)
binds the existing 17-family reference atlas and unchanged benchmark code.
The December 2022 development cutoff is unchanged. All earlier attempts and the
already-exposed later history remain part of the selection history. This is
exploratory research, not a new untouched test set.

Root independently executes each frozen generator and records its exact output,
then spends its one centrally recorded slot. A candidate must improve the primary
score against the strongest matched reference, retain the existing two-replica
numerical check where applicable, and disclose probability/uncertainty and other
horizon regressions. Only then is a frozen later-period falsification justified.
Even a favorable later result is descriptive because that history was already
seen. No reweighting, new decoder, changed target, changed benchmark or extra
unrecorded attempt is permitted in this round.

Source correctness, historical improvement and production suitability are separate
judgments. Useful reviewed measurement fixes can be integrated independently.
A failed candidate is retained as reproducible evidence and explicitly archived;
it is not merged as a model improvement. A candidate that holds up can become an
experimental programme contribution, without changing the published model or its
canonical acceptance record. Professional use still needs stronger independent
evidence and appropriate data rights.

### First-round results and practical assessment

All three experiments received their single registered measurement. None beats
the strongest matched reference on the declared two-year return task:

| Indicator approach | Two-year forecast error (lower is better) | Error relative to strongest reference |
| --- | ---: | ---: |
| Unconditional historical comparison | 0.331074 | Reference |
| Existing composite | 0.433748 | 31.0% more |
| New unusual-state/PCA indicator | 0.495501 | 49.7% more |
| New small learned indicator | 0.432134 | 30.5% more |
| New fixed valuation/rates/dollar ensemble | 0.540032 | 63.1% more |

These are forecasting errors, not investment returns. All rows use the same 24
monthly starts from December 2018 through November 2020. Their two-year outcomes
overlap and include just one negative return, so this is a narrow exposed-history
comparison, not 24 independent economic experiments. The existing composite's
four components have errors 0.429641–0.481966 on this same task; none beats the
unconditional comparison. The price-path model's two replicas are worse here
(0.705190/0.706628), despite improvements in other tasks. Full 17-family scores,
probability/uncertainty diagnostics and all candidate outcomes are retained in the
[result summary](artifacts/research-programme-round1-2026-11-07.json).

The anomaly representation fits usual relationships among short/long price trends
and volatility, then measures deviations. It uses no labels, has 96 available dates
and one neutral warm-up date. Its one-year peak-to-trough loss error improves
slightly, 0.259573 versus the best reference 0.260172 (about 0.23%). That secondary
finding cannot rescue the failed primary and is not a new chosen trading task.
The small learner uses a two-leaf tree with fixed shrinkage, at most 60 strictly
mature two-year labels, and price trend/drawdown inputs; 25 dates remain neutral.
The equal-weight ensemble combines price valuation, real yields and broad-dollar
appreciation; all 97 dates have all three coordinates available. Its 45-day macro
lag is a conservative reconstruction convention, not proof of historical vintages.

Each is tested as an extra scalar indicator through the **unchanged** forecast
readout. This does not establish that all anomaly detectors, trees or ensembles
fail, or that a different direct forecasting system would produce these scores.
There was no feature/weight/decoder tuning after feedback and no later-period
release. The protocol ledger remains OPEN with all three slots consumed: the
existing freeze API requires a nonempty finalist list, and we did not manufacture
an eligible finalist merely to change the administrative state.

The [portable evidence packet](artifacts/research-programme-round1-2026-11-07.zip)
contains captured inputs, all recorded comparisons, original code/configuration,
archived tests and independent audit. SHA256:
`2dc44327b609030f7739ecbbcacc0bf122bd569dbd3fb259905516a305aa296e`.
After unpacking, `python replay-generators.py --packet UNPACKED_DIRECTORY
--output-dir NEW_DIRECTORY` reproduces all 97 values of each candidate exactly in
the registered environment. Root verified byte-identical reproduction separately
from the worker outputs. Independent audit reconstructed 1,215 candidate forecast
records, 6,075 fixed-CDF reference records and 2,295 frontier comparisons; maximum
loss difference was 1.11e-15. A premeasurement captured-input parsing defect in the
ensemble was fixed without changing any candidate value; its replacement oracle
fails under the old behavior.

Failed implementations are preserved in this packet and local archive tags
`archive/research-anomaly-20261107` (`cd2402f`),
`archive/research-learner-20261107` (`502c2d3`) and
`archive/research-ensemble-20261107` (`8910b53`, including a test-only improvement).
They are not adopted or merged as model improvements. Their unmerged branch refs
are retained to obey the no-unmerged-branch-deletion rule; worker checkouts can be
archived once idle. No failed research source is silently added to production.

### Macro availability audit and second completed round

The [November 7 macro audit](artifacts/macro-availability-audit-2026-11-07.json)
separates an observation's date from when its particular value was available.
Our four FRED caches contain only dates and current values: no historical release
or revision identity. The collector does not request historical versions, and
monthly preprocessing carries observations forward. A 45-day lag cannot repair
revised or backfilled history. Coverage measured after removing missing rows
also does not establish a complete calendar or timely publication.

The audit checked the actual series and historical archive intervals. Under a
conservative convention—query at 00:00 UTC, use archive information dated no later
than two calendar days earlier—the 97 benchmark dates have this support:

| Cached input | Actual series | First archival vintage | Benchmark dates with an eligible latest observation |
| --- | --- | --- | ---: |
| Ten-year real yield | DFII10 | 2005-10-12 | 97/97 |
| Federal Reserve assets | WALCL | 2011-07-07 | 97/97 |
| Broad dollar index | DTWEXBGS | 2019-02-04 | 47/97 |
| Overnight reverse repos | RRPONTSYD | 2016-03-28 | 82/97 |

The dollar input is a trade-weighted goods-and-services index, **not ICE DXY**.
It was introduced in 2019 with older observations backfilled. That backfill
cannot serve as a contemporary pre-2019 input. Reverse-repo history before its
first archive entry likewise cannot be certified from this archive. This does
not prove no original source existed then. Missing reverse-repo entries are not
zero. The audit also found changes to older observations and finite entries
later withdrawn as missing; an as-of selector must retain those withdrawals.
ALFRED dates can represent source release dates rather than first FRED ingestion;
these counts do not establish exact intraday availability.

Thirteen bounded API responses were captured for the audit before the source-use
review was completed. [FRED's current service/API terms](https://fred.stlouisfed.org/legal/)
restrict the proposed machine-learning use and API caching. New captures and
detailed numerical examples are therefore quarantined privately as audit evidence,
excluded from model inputs and public evidence packets. The public artifact
contains metadata, counts and hashes only. An independent review caught numerical
examples in the unpublished draft; that local history was replaced before any
push. A publication-boundary regression rejects the original detailed artifact.
This is a source-admission decision for this round, not retrospective clearance
of legacy caches or references.

The [Federal Reserve Board's own policy](https://www.federalreserve.gov/disclaimer.htm)
offers a possible original-source route. Sample H.15 and H.4.1 releases were
checked, but a date-shaped URL does not guarantee the original values: some pages
contain later corrections, and release formats change. Full required coverage,
original-versus-corrected versions and target-field extraction remain unresolved.
The generic interval adapter is retained under local tag
`archive/macro-vintage-adapter-20261107` (`de65db0`), with synthetic tests and
independent arithmetic checks; it is not an admitted macro model pipeline.

With no new macro feed admitted, three Astra workers froze independent price-only
hypotheses. The [second registration](artifacts/research-programme-round2-2026-11-07-registration.json)
binds campaign `245d1825d1f50e97d89489e1f21d4c8092d73b44a41131c1260eca6ab8a13163`:
three total attempts, one each for sign persistence, drawdown recovery and a
forward-updating volatility state. All used the owned BTC price snapshot only,
with one- or two-day close lags. No new FRED payload or macro value entered these
calculations. The benchmark code, 17-family atlas, readout, dates, label rules and
declared two-year return objective stayed fixed.

| New hypothesis | What the scalar measures | Two-year forecast error | Error above strongest reference |
| --- | --- | ---: | ---: |
| Sign persistence | Whether adjacent up/down days tend to follow each other | 0.505273 | 52.6% |
| Drawdown recovery | Progress back toward the previous peak, retaining the deepest fall in that excursion | 0.516677 | 56.1% |
| Volatility state | A causal probability filter for sustained unusually high daily variation | 0.468936 | 41.6% |
| Unconditional history | The same mature historical outcomes without the new scalar | 0.331074 | Reference |

All three fail the primary comparison. None beats the lowest matched CRPS in any
of the six scored horizon/outcome cells either. Some loss-probability errors
(Brier scores) improve; those separate diagnostics cannot rescue the primary failure. No later-period release, retries,
parameter changes or model promotion followed. These are forecast errors, not
investment returns. The primary comparison still has only 24 overlapping monthly
starts and one negative two-year return; four-year predictive scoring has no
eligible starts. Sixteen indicator variants had been tried at the end of this round. The third
round below adds three more. This weak exposed-history sample cannot establish universal failure
of these model families or a reliable probability of future trading success.

Before scoring, root captured every producer/configuration and reproduced all 97
rows per arm byte for byte. The shared `owned_indicator_input.derive` boundary
passes the exact immutable, hash-attested input bytes to each reviewed transform.
It rejects path/mutable inputs and wrong identities before execution. Replacing
the original path cannot change the derived values. This addresses a repeated
hash-then-reopen defect; it is not a Python sandbox or a proof of arbitrary import
purity. The fixed trial API's default `higher_risk` metadata is arbitrary for the
undirected persistence and regime states. Their ordering diagnostics must not be
read as registered risk-direction evidence; distribution scores are unaffected.

The [second-round result summary](artifacts/research-programme-round2-2026-11-07.json)
retains every scored outcome and its strongest matched comparison. The [portable packet](artifacts/research-programme-round2-2026-11-07.zip) preserves
the price input, frozen sources/configurations/tests, original root capture receipt,
replay validator, recorded forecasts and independent audit. SHA256:
`53a20b5af70a48ab1f6c39ae4f72ebed7138c4e3eefbf46879a79daa0692d934`.
Its 31 tests pass. After checking the ZIP identity and unpacking, run
`python replay-verified.py --packet . --output-dir NEW_DIRECTORY` and
`python audit-scores.py --packet . --source-root benchmark-code --output NEW_REPORT.json`
in the registered Python/NumPy/pandas environment. The replay validates every
captured identity before executing reviewed Python from private copies; it does
not sandbox that Python. Independent arithmetic reconstructed 291 scalar values
and checked 1,215 predictions, 648 scored records and 2,295 frontier cells across
17 references. Maximum CRPS discrepancy was 1.72e-15; weights, outcomes and interval
coverage matched exactly.
It excludes new macro captures and does not redistribute the legacy raw macro
bundle. Generator replay and recorded-score arithmetic are portable; rebuilding
the original reference atlas still requires its separately identified frozen
bundle. Failed source branches are archived without merging them as improvements: local
tags `archive/round2-persistence-20261107` (`7ca3609`),
`archive/round2-recovery-20261107` (`1606873`) and
`archive/round2-regime-20261107` (`1b62110`). Two clean worker checkouts were
archived; the app requires its clean primary checkout to remain, detached at main.
Unmerged branch refs are retained. The superseded detailed macro draft is retained
only under a private local archive tag, outside main ancestry; do not publish
archive tags or private captures.
The campaign ledger remains OPEN with all three slots consumed and no eligible
finalist, for the same administrative reason as round one. Do not reopen its budget.

### Original Board release audit: implemented source reconstruction

The November 8 source audit is implemented under a
[contract frozen before monthly acquisition](artifacts/fed-h41-2026-11-08-source-contract.json).
It covers 157 monthly queries from December 2009 through December 2022, including
five years before the first benchmark date. The source's calendar JSON, discovered
in its own release-index script, determines actual listed dates; selections include
11 Fridays and three Mondays. No Thursday schedule was invented. A printed release
date must be no later than query minus two calendar days. That is an inclusive date
threshold, not a claim the release was known at midnight on the earlier date.

All 157 selected pages were captured and their byte identities verified. The
[public monthly dataset](artifacts/fed-h41-published-monthly-2026-11-08.csv) contains
**156 usable levels, including 96 of 97 benchmark months**. The sole unavailable
slot is November 2019: its indexed November 28 URL prints November 29, after that
query's November 28 cutoff. The original selection remains missing; there is no
silent older-release substitution. These counts pass the source contract's
prespecified completeness conditions; they are not statistical confidence bounds.

The [audit artifact](artifacts/fed-h41-2026-11-08-audit.json) records the exact source,
contract and dataset identities. Nine accepted editions have a documented
collateral-only correction; 147 have no identified total-assets correction after
the scoped announcement review. **Zero editions are authenticated originals.**
Root accepts the declared continuity assumptions for exploratory reconstructed
research only. The announcement feed is not proven exhaustive. This dataset
assembles published monthly levels from separate editions; it is not a complete
historical revised curve available at each query, a certified real-time feed or
professional-use clearance. Board statistical information has a different source
policy from FRED services. No new FRED captures entered these inputs.

The offline extractor matches the consolidated-statement title, units, exact total-
assets row and current Wednesday column. It supports table renumbering and older
text versus modern HTML layouts. Independent review found a malformed HTML span
could disguise one cell as several columns. The repaired boundary requires five
independent target cells, valid earlier Wednesday comparison dates and a current
observation within seven days of release, including Monday holiday releases.
Fifteen tests pass; restoring the old parser produces eleven regression failures.
The repair changes none of the 156 accepted values. An independent text-stream
extractor matches all values and dates exactly, including 35 nonzero-elimination
and 35 different district-total witnesses. Parser correctness is separate from
original-vintage uncertainty. Full site HTML stays private; public artifacts
contain Board statistical levels, source URLs, hashes and audit metadata.

### Third completed round: reconstructed balance-sheet information

Registration `b6c8c7b` binds the
[third-round contract](artifacts/research-programme-round3-2026-11-08-registration.json)
and campaign `34b036a70b46a11326879f94e13199811cc90c8ea098b6ccde16b97d499d16b4`.
Three Astra workers chose one independent mechanism each. The fixed reference
atlas, twelve scoring modules, 97 evaluation dates, readout and declared primary
objective stayed unchanged. Each source/configuration was committed before any
fitness feedback. Root authenticated all inputs and code before execution, parsed
fresh immutable price/macro bytes for each arm, and reproduced all 97 worker rows
byte for byte. Fourteen tamper cases reject before captured Python loads;
replacing original paths or mutating one arm's frames cannot change later arms.

| Frozen hypothesis | Meaning | Available states / 97 | Two-year CRPS | Error above strongest reference |
| --- | --- | ---: | ---: | ---: |
| Relative balance-sheet level | Current assets' rank against 36 prior calendar months, requiring 30 valid observations | 96 | 0.495194 | 49.6% |
| Balance-sheet growth acceleration | Latest six monthly log changes versus the previous six, normalized by total absolute change | 84 | 0.505535 | 52.7% |
| Price/asset coupling | Trailing twelve monthly return/change correlation, requiring nine valid calendar pairs | 96 | 0.516788 | 56.1% |
| Unconditional history | Mature historical outcomes without the extra scalar | — | 0.331074 | Reference |

All three fail the primary comparison. None beats the lowest matched CRPS in any
of the six scored horizon/outcome cells. Other probability and interval diagnostics
remain separate in the [complete result summary](artifacts/research-programme-round3-2026-11-08.json);
no favorable secondary statistic rescues the main failure. These are forecast
errors, not investment returns. November 2019 is explicitly neutral. The growth
arm's requirement for thirteen consecutive source levels propagates that gap
through thirteen query windows; its missing rule was frozen before feedback.
No date was removed from the common benchmark. Missing-data behavior is a
limitation, not an established explanation for the losses.

The independent audit reconstructed all 291 scalar readings, checked 1,215
prediction records including 648 scored records, and verified all 2,295 frontier
cells, 270 numerical guards and seventeen reference identities. Atoms, maturity
pools, weights, outcomes, interval coverage and widths match exactly; maximum CRPS
discrepancy is 2.00e-15. All three states are undirected, so the trial API's default
`higher_risk` metadata must not be read as a favorable risk-ordering claim.

There was no later-period release, retry, decoder change or parameter adjustment.
The three slots are exhausted; the ledger stays administratively OPEN with no
eligible finalist. Nineteen indicator variants have now been tried. Failed sources
remain under local tags `archive/round3-level-20261108` (`6319778`),
`archive/round3-change-20261108` (`fe2a333`) and
`archive/round3-coupling-20261108` (`38eebdf`), and in the
[portable evidence packet](artifacts/research-programme-round3-2026-11-08.zip).
Packet SHA256: `afcf977f7c31ad79cc9cb7ee7209413171b6a1a7919f22312dd00c7cd10ebee9`.
No failed candidate is merged as a model improvement; reviewed source extraction
and measurement safeguards are useful programme contributions on their own.

The packet contains both candidate inputs, sources/configurations/tests, recorded
comparisons, independent arithmetic audit and verified replay tools. It excludes
new FRED payloads, raw site HTML and the legacy raw macro bundle. Authenticate its
external SHA first. In CPython 3.12.16 / NumPy 2.4.6 / pandas 2.3.3, unpack and run:

```
python replay-generators.py --packet . --output-dir NEW_GENERATOR_DIRECTORY
python audit-scores.py --packet . --source-root benchmark-code --output NEW_REPORT.json
python -m unittest discover -s tests
python test-controller.py --packet . --report NEW_CONTROLLER_REPORT.json
```

Rebuilding the source CSV additionally needs the private owned Board capture
directory `RAW`; use `source-audit/replay-source.py --packet source-audit
--raw-root RAW --output-dir NEW_SOURCE_DIRECTORY`. It verifies all frozen
source dependencies and 157 raw bodies before running trusted captured Python
from private copies, then requires exact CSV identity. Tampering with exception
tiers, code, bodies or runtime must fail before execution. Compiler/build and
executable identity are evidence only; semantic CPython 3.12.16 is the source
replay requirement. These checks do not sandbox Python or authenticate a jointly
rewritten archive. Cross-platform candidate floating-point identity has not been
independently demonstrated. Original reference samples are not regenerated by
the arithmetic replay; their previously audited atlas is retained.

### What the failures and earlier qualification establish

The source audit succeeded, and the new predictive experiments failed. That does
not prove macro information is universally useless or that the benchmark cannot
detect it. It does show that these exact three scalars, missing rules and fixed
readout did not add enough information on the exposed dates to beat strong simple
references. The primary comparison still contains only 24 overlapping monthly
starts and one negative two-year return; four-year predictive scoring has no
eligible starts. No professional-use qualification follows.

The earlier 398/400 positive declarations and 24/1500 null declarations concerned
a **different** known-law procedure: a continuous location/scale forecast with a
residual distribution, independent synthetic worlds and a conditional test.
Those results remain valid within their registered finite scope. They do not
measure sensitivity or error control for the present 97-query, latest-24-mature-
label median-bin empirical-CDF readout. Neither may be used to certify the other.
The [scientific assessment in the packet](artifacts/research-programme-round3-2026-11-08.zip)
records the inspected code paths and the distinction.

Brief versus delivered: the requested source-availability audit produced a
qualified reconstructed dataset, not authenticated original history. The small
registered research round used only admitted inputs and the unchanged benchmark;
all three ideas failed and are preserved. No promised forecasting gain, new
production model, FRED-use clearance or real-time historical certification was
substituted for those results. Backend verification passes 482 tests. The packet passes 35 focused unit tests,
two controller tests and three private-source replay tests; independent
generator, score-arithmetic and source-data replays also pass.

### Current readout sensitivity audit — November 9

Preregistration `56260b1` precedes implementation `6eb610d` and all audit-world
scores. The [registration](artifacts/direct-cdf-sensitivity-2026-11-09-registration.json)
and [implementation freeze](artifacts/direct-cdf-sensitivity-2026-11-09-implementation.json)
bind the experiment. All twelve market benchmark modules remain unchanged.
The caller is the actual `market_information.score_candidate`: the same latest
24 strictly mature rows fit medians and supply outcome atoms, with the existing
50:50 pooled/local weights. This differs from older split/residual procedures.

All 128 world/law jobs completed: 64 independent history IDs paired across two
price laws and four scalar inputs. Exact state, noisy observation and unrelated
state share the same prices within a world. A constant input checks the no-split
identity. One law has no predictable returns; the other has persistent Gaussian
monthly drift, deliberately large as a stress test. Neither is a fitted Bitcoin
model. The original 97 query dates give 48 scored one-year starts, 24 two-year
starts and zero four-year starts per world. Daily warm-up creates no extra monthly
training origins. Artificial controls do not add to the nineteen historical
indicator variants or create additional Bitcoin cycles.

Known-law forecasts condition on all past prices, optionally adding the current
scalar; older scalar releases are deliberately excluded. Terminal forecasts are
analytically Gaussian. Downside scores describe two finite 128-path ensembles,
with simulation noise retained. These information sets and forecasting procedures
differ from the decoder's two price contexts; the gaps below are separate
estimands, not a proportion of information recovered. Gaussian filtering follows
the [linear state-space calculation](https://www.stat.cmu.edu/~cshalizi/dst/26/lectures/08/lecture-08.html).

For informative-law **two-year terminal returns**:

| Input | Known-law gain from current input | Fixed decoder gain versus price contexts |
| --- | ---: | ---: |
| Noisy state | +.02356 [.01018, .03701] | −.03051 [−.04786, −.01213] |
| Exact state | +.05937 [.03241, .08650] | −.02139 [−.04214, −.00032] |

Values are mean CRPS differences in dimensionless log-return units; positive is
lower loss. Brackets are pointwise 95% paired whole-history percentile bootstrap
intervals over 64 IDs, using 4,000 resamples. They are not simultaneous intervals,
a promotion rule or evidence of market error control. The exact-state decoder
interval only narrowly excludes zero. No stable win-count claim follows.

The useful exact input improves the known-law forecast but worsens the decoder's
primary forecast on average. This establishes a limitation under this law, not
universal insensitivity. Exact state improves one-year entry-loss CRPS versus
contexts by .01533 [.00665, .02496], while remaining worse than pooled history
by .03975 [.02549, .05626]. Every nonconstant input has worse mean CRPS than pooled
history in every scored cell. The [complete results](artifacts/direct-cdf-sensitivity-2026-11-09.json)
retain all horizons, outcomes, Brier scores, interval coverage/width and bank
noise separately; coverage and width differences are not generic improvements.

Informative-law two-year nominal 80% intervals cover 26.4% with exact state,
27.5% for contexts and 29.2% for pooled history; the known-law exact-state forecast
covers 79.4%. The median local input cell has three observations, and 63.2% of
outcomes fall outside the historical atom range. Sparse, stale training pools and
limited support are plausible contributors; no causal ablation was performed.
Under the null law, oracle input gains are exactly zero and useless splits worsen
mean forecast loss. That does not certify adaptive false-positive control.

Independent reviews checked Gaussian conditioning, terminal covariance, endpoint
timing and the unchanged caller. Thirteen engineering tests and 42 focused tests
passed; the full backend suite passed 495 tests. A reviewer found an unbound
scoring import before audit scores; the boundary regression failed before the
fix and passes using the already-frozen scoring module. Decoder atoms/weights,
actual outcomes, oracle moments and bank metrics are retained; oracle samples
require deterministic regeneration. Effectively zero positive-world sign counts
can change under floating-point summation order and are not used as win claims.

A turn interruption removed temporary uncommitted results and documentation.
The committed registration and implementation survived. Recovery uses those
unchanged sources/seeds in persistent project output storage; it reproduces
the already-recorded summary SHA
`955a9db4f6ef7c68098b16783252c8ec21fb8585886f8c3664bb4226e7046d1d`.
This is a reproducibility replay, not a new replication or scientific retry.

Recovery completed all 128 jobs with no omitted worlds and reproduced the original
summary SHA exactly. The independent result audit and packet tests pass.
Packet SHA-256: `5d70273cbe489be289e7210a3ab2edd9850af230b92a1a0a47db3e4dbd8ea5ad`.

The [portable packet](artifacts/direct-cdf-sensitivity-2026-11-09.zip) includes
frozen source, registration, pinned dependencies, all world files and an
independent arithmetic audit. Authenticate its external SHA recorded below before
executing trusted Python; it is not a sandbox or an external authenticity seal.
No raw macro captures or FRED payloads are included. CPython 3.12.16, NumPy 2.4.6
and pandas 2.3.3 are required; cross-platform bitwise identity is unverified.
From an unpacked packet, use new output/report paths:

```sh
python audit-results.py --packet . --results results --report NEW_AUDIT.json
python -m unittest tests.test_readout_sensitivity tests.test_readout_synthetic_world
python -m research.readout_sensitivity run --freeze docs/artifacts/direct-cdf-sensitivity-2026-11-09-implementation.json --output NEW_RESULTS_DIR
```

Brief versus delivered: the fixed-readout audit is complete under two declared
laws. It found available information and a primary decoder regression. It did
not qualify an indicator, alter the market benchmark or rescue prior failures.
The older 398/400 and 24/1500 results concern a different procedure. Lessons stay
in this canonical record; skill-harvest identified no new global skill needed.

### Next bounded research step

The separate [November 9 incumbent DCA diagnosis](dca_evidence.md#underperformance-diagnosis-scope-and-fixed-diagnostic-arms)
now quantifies cash-deferral damage and confirms zero positive mature bottom labels
under the legacy 36/48-month classification target. Its fixed policy/component
ablations are exposed-history supporting simulations, not new market-information
trials, a replacement primary objective or a rescue of the nineteen failed variants.
The top-only positive median remains fragile across eras. Count these diagnostics
in the exposure history; retain their adverse results when specifying any later
market comparison. The label-feasibility issue is separate from the synthetic
readout limitation above and strengthens the need to make target and fit/fallback
status explicit before claiming a learned improvement.

Pause more feature searches through this readout. Historical scores remain valid
measurements of this procedure, but cannot be treated as a broad information test.
Specify a separate limited readout study before execution: simple forecasters,
an explicit hypothesis about stale labels/discrete outcome support, fresh seeds,
and both persistent-drift and distinct volatility/nonlinear information controls.
Separate development laws from frozen assessment laws; keep the old decoder as a
fixed reference and report return, downside and calibration separately. Only
then consider a newly registered market comparison or benchmark version. Do not
retune the frozen benchmark on these worlds to turn nineteen failures into wins.
The November 10 study below supersedes this proposal with a registered candidate
set, completed assessment and retained failures. No alternative decoder is promoted.
November 30 collection remains separate; no scheduler was installed.

### Training-target and readout implementation request — November 10

Status: implemented, frozen and assessed on November 10. All 96 synthetic jobs and
the single historical comparison completed without failed arms or network attempts.
The candidate changes are research-only; none qualifies as a production upgrade.
Josh asked to tackle the training-target and forecast-readout issues and then
test the changes against Fixed DCA. The previously confirmed comparison remains
48 identical monthly contributions, equal final deployment, common dates/prices,
costs and prior-month execution. The frozen October 2026 dataset remains the
comparison input; a new provider refresh is not part of this iteration.

Josh chose the continuous six-month buy-deferral gain/loss target. At score date
`t`, the common ledger executes at the next month's close `t+1`; the target is
`log(P[t+1] / P[t+7])`. Positive means waiting six months buys more BTC for the
same notional, before identical proportional costs. Its realized outcome becomes
available the day after `t+7`, strictly before a training origin can use it.
This is an experimental target, not a changed production or investor-utility
contract. Older twelve/twenty-four/forty-eight-month research scores and their
primary outcome remain separately identified. Restoring future-aware cutoffs
to manufacture positive legacy classes is rejected.

Source inspection found the existing `research/location_scale_readout.py`
continuous mean/scale estimator and the frozen empirical-CDF implementation.
The separately versioned study reuses those owners. The relevant
design layers are target-to-action alignment, actual label availability,
fit/calibration separation, forecast support and uncertainty, and the effect of
warm-up/fallback behavior on the equal-budget result. Neither a wider target
support nor a new forecast distribution establishes improved profitability.

After the target choice, the protocol froze the complete readout/candidate set
and execution mapping: old-readout and price-only references, independent synthetic
controls, separate engineering fixtures and one historical comparison. All failed
arms are retained. Strict label maturity, fit-only preprocessing, explicit
learned/fallback state and a matched warm-up control separate learning from
mechanically buying as DCA during training. The exposed period remains exposed;
the original benchmark and production gate are unchanged.

The [registration](artifacts/target-readout-2026-11-10-registration.json) fixes a
new protocol with old empirical latest-24 and matched split controls, a continuous
Gaussian mean/scale readout on the matched split, and an expanding-fit variant.
The implementation estimates residual location/scale on eight separate later
calibration rows. Fit labels must mature before the first calibration origin.
It requires at least sixteen fit rows, fit-only scaling, price-context
residualization and explicit inactive/duplicate-feature identities.
Gaussian tails allow forecasts beyond a stale finite atom range; they do not
guarantee calibration, so coverage/Brier/CRPS and fit/fallback counts stay visible.
The Gaussian residual distribution is a testable model assumption, not accepted
truth. Expanding data can also hurt under regime change; retain that comparison.

Implementation was frozen before the new independent null, drift and volatility
worlds were scored. Six-month forecast loss is primary for this new action-target
study; two-year losses remain a separate diagnostic and do not regrade previous
market experiments. No model selection or retuning on assessment histories is
allowed. All predeclared market variants ran once on the already exposed snapshot.

The new research risk score is the fitted probability of positive deferral gain,
not the old ordinal score. It feeds the frozen 0.25 purchase region and
three-contribution maximum with full final deployment. When a forecast cannot be
fitted, the adapter buys the current contribution as Fixed DCA. A warm-up-matched
incumbent control measures that mechanical fallback separately. Its early
exposure advantage cannot be attributed to learning. All variants use the
same 96 windows and fees, no sales or borrowing, and zero cash interest in the
equal-spend comparison. Production scoring, canonical identity and gates stay
unchanged. This separately versioned research adapter is the reversible change;
production integration depends on results and its existing acceptance process.

#### Completed assessment and interpretation

Registration `e62e3f8` preceded implementation assessment at `188e061`.
The [implementation freeze](artifacts/target-readout-2026-11-10-implementation.json)
has SHA256 `17b3a4cf72d9ac33426f84c52a0736ceebc2a25c1d3016f48e42c333e4b83692`.
The [results](artifacts/target-readout-2026-11-10/summary.json) retain every arm.
The run used Python 3.12.16, NumPy 2.4.6 and pandas 2.3.3 with one BLAS thread,
empty environment, scratch HOME/TMPDIR, blocked socket operations and a separate
3,600-second watchdog (CPU 3,500 seconds, per-file 64 MiB, core dumps disabled).
It finished in 72.49 seconds, exit zero; no replacement assessment or tuning ran.
The runtime was recovered offline from expanded cached packages with RECORD checks;
original wheel hashes were not revalidated. No provider, dependency or model-setting
change was needed.

The target removes the legacy rare-class barrier: the expanding models first fit
at February 2018 and produce 105 fitted origins, rather than waiting for both
extreme cycle classes. Empirical latest-24 first fits July 2017 (112 origins).
Forecast comparisons use the same 97 mature origins, February 2018–February 2026.
This is a working continuous learner, not evidence that its predictions are good.

All seven variants use the target and the fixed probability adapter described
above. The [DCA evidence](dca_evidence.md#six-month-target-and-readout-results-10-november-2026)
owns the full 11-arm trading comparison. The four-component Gaussian's median
BTC difference is **−9.43%**, with 20/96 wins, versus the incumbent's **−19.22%**
and 23/96 wins. The warm-up-matched incumbent is **−0.34%**, with 47/96 wins.
Comparing the same windows directly, the component model wins only 36/96 against
that control; its median BTC ratio difference is **−1.24%**. Against Gaussian
price-only it wins 65/96, with a paired median **+3.79%**, while still losing to
DCA. These paired ratios are not differences of separate median summaries.

Changing forecast distributions does not establish a forecast improvement:

| Forecaster, common 97 BTC origins | Six-month CRPS (lower is better) | Event Brier | Nominal 80% coverage |
| --- | ---: | ---: | ---: |
| Empirical latest-24, composite | 0.462731 | 0.406349 | 56.70% |
| Empirical split-24, composite | 0.526984 | 0.449410 | 41.24% |
| Gaussian split-24, composite | 2.494831 | 0.385173 | 50.52% |
| Gaussian expanding, composite | 0.472446 | 0.354808 | 48.45% |
| Gaussian expanding, components | 0.710187 | 0.355726 | 49.48% |
| Gaussian expanding, price-only | 0.481378 | 0.363391 | 49.48% |
| Gaussian expanding, pooled | 0.505887 | 0.405748 | 39.18% |

The matched split isolates distribution choice from fit/calibration support.
Gaussian split CRPS is worse than empirical split on BTC and in **all 18**
synthetic law/horizon/feature cells. A genuine fitted tail instability explains
much of its BTC loss: September 2022 mean 272.689, standard deviation 221.896,
CRPS 171.233, accounting for 70.76% of the total. No clipping or removal was
applied after seeing it. Continuous support permits extrapolation but does not
make extrapolation reliable. Four components improve this fixed trading adapter
relative to the Gaussian price-only control while worsening forecast CRPS.

Synthetic primary results below compare exact state with **the same method's**
price-only forecast. Each cell averages dates within each of 32 independent worlds,
then averages worlds. Positive CRPS gain means improvement. Brackets are paired
whole-world percentile 95% intervals, pointwise across 4,000 bootstrap resamples;
they are not simultaneous guarantees or a calibrated selection/error-control test.
All nuisance, price-only, 24-month, Brier, width and coverage results remain in
the [synthetic table](artifacts/target-readout-2026-11-10/synthetic_summary.json).

| Six-month CRPS gain from exact state | Null law | Persistent drift | Persistent volatility |
| --- | --- | --- | --- |
| Empirical latest-24 | −0.00478 [−0.00642, −0.00324] | +0.00839 [+0.00416, +0.01288] | −0.00456 [−0.00609, −0.00312] |
| Empirical split-24 | −0.00088 [−0.00140, −0.00032] | −0.00159 [−0.00248, −0.00068] | −0.00156 [−0.00230, −0.00084] |
| Gaussian split-24 | −0.17381 [−0.27601, −0.08581] | −0.30905 [−0.64882, −0.01980] | −0.22490 [−0.56301, +0.10628] |
| Gaussian expanding | −0.01389 [−0.02938, +0.00228] | +0.07118 [+0.02022, +0.11534] | −0.00212 [−0.04934, +0.05047] |

Expanding Gaussian detects planted drift information, but its exact-state CRPS
0.39861 is still worse than the old price-only 0.33797. It does not establish
volatility sensitivity. No method has a positive mean 24-month exact-state gain
in these laws. The new 24-month diagnostic uses this study's deferral target;
it does not replace or regrade the earlier two-year return benchmark. Under null
and volatility laws, adding state does not produce a persuasive forecast benefit.
All methods' uncertainty remains too narrow in aggregate; Gaussian expanding's
six-month coverage is only 35–46% across these feature/law cells. Eight highly
overlapping calibration outcomes and the heuristic inflation do not provide
a calibrated predictive distribution.

#### Verification, reproducibility and next bounded work

`scripts/check-target-readout-study.py` imports no producer code. It reconstructs
all 1,056 contribution/cash/BTC ledgers with a separate cash recurrence and
independently rescores 161,280 synthetic forecast records, checks strict chronology,
common synthetic support, all output hashes, means and market forecast summaries.
An independent reviewer additionally checked all 72 paired-bootstrap cells and
686 scored market records, source/input identities and common dates. No arithmetic,
timing or chronology defect remained. Deliberate wrong hashes, doubled funding,
corrupted BTC balances with refreshed hashes and unavailable labels were rejected.
Engineering regressions also rejected future-suffix contamination, duplicate and
linearly redundant feature effects, and mislabeled variance inflation before the
assessment freeze. The [verification record](artifacts/target-readout-2026-11-10/verification.json)
records the checks, runtime limits and portability status.
The complete backend suite passes **540 tests**. Its first run passed 539/540:
the portability fixture intentionally denies `/private/tmp`, conflicting with the
supplied scratch TMPDIR. All three portability tests and then the full suite pass
with macOS's native temp directory. No source fix or assessment rerun was needed.

The [portable packet](artifacts/target-readout-2026-11-10.zip) retains all issued
assessment forecasts, derived tables, frozen source/tests/protocol, exact BTC and
derived component inputs, and the independent checker. It contains no raw macro
captures. In its `source` directory, use the recorded requirements and run:

```sh
env -i PATH=/usr/bin:/bin HOME=/private/tmp TMPDIR=/private/tmp \
  PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
  <python> -m research.target_readout_study run \
  --freeze docs/artifacts/target-readout-2026-11-10-implementation.json \
  --output <absent-run-directory>
<python> -I scripts/check-target-readout-study.py <run-directory>
```

The packet's SHA256 is
`608e991b392d5b7863ce80a26bbd1ff536afe0de172b2cf7663ae59e4098dcfb`.
After extraction, all 125 manifest file hashes, 26 engineering tests and the full
forecast/ledger checker pass. This verifies portability without spending another
assessment slot. From its `source` directory, the checker can inspect `../results`
directly. The adjacent public artifact directory contains compact summaries;
the packet's `results` directory contains the complete hash-checked run.

Use an external 3,600-second subprocess timeout when replaying: the driver's
internal check operates between worlds and cannot interrupt a single blocked job.
The original assessment had this hard watchdog. The optional checker `--plot`
flag saves a static image and opens no window; the recorded plot uses a separate
matplotlib 3.11.2 environment and does not regenerate forecasts.

**Brief versus delivered:** user-approved six-month continuous target, chronological
readout, predeclared synthetic controls and one same-budget, fully deployed 48-month
DCA comparison are as briefed. The readout's empirical support and label feasibility
issues are addressed mechanically; calibrated forecasts and improved DCA performance
are **not achieved**. No research winner was adopted, no provider was activated,
and production code/settings/acceptance policy remain unchanged.

**Limitations and not checked:** this is one exposed BTC path with overlapping
windows, reconstructed legacy component availability and stale source limitations.
It cannot establish future profitability or point-in-time live validity. Synthetic
laws have limited scope and the intervals are unadjusted pointwise diagnostics.
Warm-up differs across latest-24 and split variants; matched forecast support and
the warm-up control expose that distinction. The adapter uses Pr(gain > 0) and a
legacy 0.25 threshold; it does not optimize expected BTC or the whole cash path.
The new target alone was not isolated from its score semantics in an otherwise
identical production learner, so no causal effect of changing only the target is
claimed. No fresh forward outcomes or independent market acceptance were collected.

Next bounded step (proposed, not executed): register a small forecast-scale study
with pooled/constant-scale shrinkage and calibration outcomes separated by their
full horizon; retain all current readouts as references and qualify drift, volatility
and null behavior on fresh worlds before another market score. Separately specify
an explicit expected-BTC incremental deferral decision with funding and a maximum
cash-wait constraint, including DCA, matched fallback and price-only controls.
That objective and its constraints need to be frozen before choosing an adapter;
do not retune the 0.25 threshold to rescue these exposed results. Keep the current
production model and existing acceptance gate unchanged.

### Publication and operations

Josh explicitly authorized committing and pushing the accumulated work on
November 7, superseding the earlier local-only hold. The remote-only automated
refresh `4d9789b` is merged without rewriting any frozen research dataset.
Workers never push. Each subsequent push still follows the global confirmation
rule; authorization for this accumulated publication is already supplied.
Publishing code is separate from approving a production model. The daily workflow
now checks the accepted model identity before any data fetch/publish; unaccepted
causality revisions must fail that check. The legacy acceptance commands move unchanged to a separate explicit
production-evaluation workflow; research CI retains mandatory correctness/security
checks. Daily source and resolved-configuration guards block unaccepted publication.
No policy threshold or canonical identity changes. [ADR 0009](adr/0009-separate-research-ci-from-production-promotion.md)
records this distinction. A full local legacy production-evaluation run was stopped
after more than ten minutes; no completed production performance result is claimed.
The source identity remains unaccepted, regardless of research CI success.

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
  adopted investor objective, production data-vendor contract or production-gate change.
- Constraints: local development and reproducible snapshots, plus one explicit
  bounded no-key live paper capture; existing free infrastructure and no paid services.
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

**Completed registered falsification:** source and method were frozen before
execution; review closed private-path traversal and incomplete-failure-receipt
bugs first. One canonical private-output boundary now covers acquisition,
derivation and scoring, with a sink inventory/path oracle. No provider scoring
preceded those repairs. Failure receipts bind requests and errors; interrupted
reservations stay visibly incomplete and cannot be reused. Registration is
`723970fe069c27447510105f115efb4e0399558a716f22f8b368ba0b06f8d24a`.
The original acquisition metadata retains its actual historical producer hash;
the scoring registration separately binds the repaired shared helper.

[Aggregate results](artifacts/monthly-portability-2026-11-07.json) retain all 234
cells and 18 class-support summaries. The private packet contains 39,312 forecast
records across 13 models, two eras, 168 origins per era, three horizons and three
targets. The unconditional forecast dominates **each** unchanged candidate across
all three two-year outcomes in **both** eras under the registered descriptive
criterion. Two-year terminal-return CRPS (lower is better):

| Model | 1990–2003 older-family falsification | 2004–2017 shared-era challenge |
| --- | ---: | ---: |
| Unconditional | 0.229197 | 0.193960 |
| A, no-memory displacement | 0.242262 | 0.206133 |
| B, adaptive innovations | 0.237577 | 0.207302 |
| C, upside energy | 0.239006 | 0.211850 |

All three return alignments are negative in the older era and positive in the
later era; the separate negative-in-both-eras rejection did not trigger. That
does not reverse the CRPS rejection. Four-year negative/nonnegative return counts
are 29/139 and 31/137, respectively, but only one disjoint negative-return path is
available within each era. External class support is broader than the frozen BTC
sample without becoming many independent crises.

The [independent audit](artifacts/monthly-portability-independent-audit-2026-11-07.json)
reconstructed raw index composition, all generator recurrences/references,
monthly paths, strict training pools, weights, all 39,312 forecast diagnostics,
234 cells and class/non-overlap/rejection rules without importing the runner or
scorer. Maximum individual CRPS discrepancy was `3.72e-15`; aggregate CRPS
`1.11e-16`, with exact event/coverage/count/rejection agreement. Raw provider rows,
atoms and per-origin predictions remain private; committed artifacts contain
aggregate experimental measurements and identities only.

This rejects the broad portability claim under the declared monthly protocol.
It does not prove zero BTC information or compare daily risk/executable policies.
No equity tuning, replacement variant or pooled BTC score follows. Historical
vintages, shared shocks and professional-use reliability remain unverified.

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
| Synthetic / external suite | Independent-world panel passes; unchanged candidates fail registered monthly equity falsification | Neither synthetic qualification nor external testing establishes BTC market error control |
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
- Current cached input fingerprint differs from the canonical summary. The
  [9 November investigation](dca_evidence.md#performance-diagnostic-and-acceptance-investigation-9-november-2026)
  recovered both canonical data and source fingerprints exactly from `4995a45`.
  Reproduce its metrics with bound as-of/evaluator settings before comparison,
  or version and rerun every reference on a new snapshot. Never copy a new hash
  onto old metrics to make comparison pass. The acceptance builder also needs
  manifest/table-to-model binding; the workflow cutoff and recorded canonical
  evidence currently differ.
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
and the historical push hold (superseded by explicit publication approval on November 7). No combined strategy wealth score is accepted.

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

**Implemented v2 stronger-reference guard.** `research/benchmark_frontier.py`
constructs a hash-bound atlas from the existing frozen reference and generative
packets. Its [metadata](artifacts/benchmark-frontier-development-2026-11-07.json)
and [portable atlas](artifacts/benchmark-frontier-development-2026-11-07.zip) pin
all 13 fixed direct-CDF references, context/unconditional distributions and both
generative replicas. No new market fitting or candidate trial built this atlas.
The file SHA-256 is
`22b67b6dc9ea4aaa661ff220a6dff372b7d2ef54de64044f6d6ab961e07834db`.

Every new `shared-direct-cdf-campaign-v2` requires `benchmark_atlas` in its create
specification. Shared validation rejects missing/weakened reference inventories,
wrong source/code/runtime/protocol, and resealed substitutes for the registered
Student-t5 family, 8,192 iid paths and seeds 20270529/20270530. Per-record replica,
seed, sample shape and score interpretation must also agree. Synthetic tests patch
private expected identities explicitly; no public synthetic override exists.
The v1 historical receipts remain unchanged and are not accepted as v2 campaigns.

Candidate issued-CDF losses are recomputed from atoms/weights without ensemble
correction. Generative fair losses retain their distinct estimand. Comparisons
use identical origin/outcome support; extra generative-only dates are excluded.
Failures and unavailable cells remain visible, with incomplete means withheld.
CRPS, event Brier loss, interval coverage/width and ordering are separate. The
numerical Monte Carlo guard requires both replica gains positive and their
absolute difference below 20% of the smaller gain, separately per loss; this is
not significance or market error control. Completion/freeze means valid
measurement, **not promotion**. Supplied artifact hashes remain cooperative
continuity checks, not proof that producers executed or a security seal.

Thirty-five focused tests, failing bug mutations and an independent 765-cell /
90-guard arithmetic review cover the atlas and campaign handoff. The independent
review found and closed a weaker-family substitution bug at the shared validator.

A [new divergent development campaign](artifacts/divergent-campaign-v2-registration-2026-11-07.json)
was created with three total reserved slots, one per Astra worker; failures and
interruptions count. Campaign ID is
`4ffb8ade2609c2f80e8faad8d84f35cd8cb403c3efeb59c8dc318e7ee70ecbf4`,
local path `output/divergent-campaign-v2-2026-11-07/`. All earlier development,
outer and generative results are declared exposed. Single specifications must be
reviewed and committed before submission; no new candidate score has been read
at that registration point. The [completed results](artifacts/divergent-campaign-v2-2026-11-07.json)
and [portable campaign/audit packet](artifacts/divergent-campaign-v2-2026-11-07.zip)
now retain all three attempts; the campaign is FROZEN and no outer release was
reserved. Archive SHA-256 is
`49948772afd80fa1094a6bc96780b4ad18d2048a880617c5da6873a4809866db`.

The independent Astra arms used different mechanisms, with one specification
committed before each measurement:

| Arm | Fixed mechanism | Primary 24-month return CRPS | Unconditional / best matched CRPS |
| --- | --- | ---: | ---: |
| Monetary state | 12-month ten-year real-yield change, 45-day observation lag, fixed 1 percentage-point tanh scale | 0.454196 | 0.331074 |
| Attention state | English Wikipedia all-agent Bitcoin views: 30-day mean versus prior non-overlapping 365-day mean, two-day lag | 0.481079 | 0.331074 |
| Structural price state | Concentration of positive daily log returns over exactly 730 days | 0.481286 | 0.331074 |

None of the 18 mature development CRPS coordinates (three arms × two horizons ×
three outcomes) beats its strongest matched reference. There are no 48-month
forecasts in this readout. The monetary arm improves two-year entry-loss CRPS
versus the old direct-CDF family (0.218178 versus 0.227048), but loses to the
stronger generative benchmark (0.154522). This is why the full frontier is
required; beating a selected weak reference is not a competitive result.

All 97 common dates remain present. Monetary and structural inputs are available
at every common origin; attention has 78 available and 19 explicitly neutral
warm-up origins. Macroeconomic lag assumptions do not repair revised historical
vintages; attention counts include automated traffic and are not investor counts.
The structural score deliberately omits downside severity. Independent review
fixed an extreme-count overflow before attention scoring; all actual outputs
remained byte-identical. No window, direction or parameter was changed using
these scores.

Independent arithmetic audits checked each arm's 216 scored distributions, 765
comparison cells and 90 Monte Carlo guards; all 29,160 training atoms were
reconstructed exactly from daily paths and strict maturity. Maximum individual
CRPS discrepancy was below `8.89e-16`; Brier, interval/ordering/support comparisons
and guards agreed. All three receipt trees and the extracted portable campaign
were verified. These are failed development hypotheses, retained for reproducibility,
not model promotions. Further search inherits every exposed result.

**Completed fixed return-transport diagnostic.** The registered study tested a
restrictive decoder against missing indicator information. Existing median bits use up to eight cells from 24 overlapping
labels, with fixed 50:50 shrinkage and no movement of outcome support; these
restrictions are plausible bottlenecks, not an established explanation for failure.
Prior continuous-rank experiments already failed to rescue broad performance.

The study froze one ridge model (penalty 24, unpenalized intercept) on
training-only percentile/center/scale features. Canonicalize duplicate/complement coordinates
including query equivalence; query values cannot fit transforms. Forecast atoms
are the full-fit query prediction plus signed PRESS residuals
`e_i/(1-H_ii)`, with uniform weights. The feature design and penalty stay fixed
for each 23-label deletion; this is label-held-out residual construction, not
fully cross-fitted preprocessing or calibrated probabilities. No residual
recentering/rescaling, clipping or ensemble correction is allowed.

The inventory is intercept-only, context-only, context plus each of the 13 fixed
references/three old finalists/three new arms, and two attention-availability
controls: 23 models. Keep all 17 frozen forecast references too. Only terminal
returns at 12/24 months are studied, on the same 48/24 development origins;
24-month CRPS is primary, event Brier and coverage/width remain separate. No
transport of path-loss outcomes, new early origins, equity fitting or outer replay.
An intercept-only model already widens the pooled CDF by 24/23, so it is an
essential control. Indicator information requires improvement against the **same
decoder's** context model (attention against context plus availability mask),
not simply against the old decoder. Unrestricted ridge coefficients do not
validate the fixed higher-risk direction.

[Ridge's objective](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html)
and [the jackknife literature](https://stat.cmu.edu/~ryantibs/papers/jackknife.pdf)
provide methodological context, not a coverage theorem for these overlapping
labels or this full-fit-centered residual CDF. Source and inventory were reviewed
and [registration](artifacts/return-transport-registration-2026-11-07.json)
committed at `f21176f` before fitting. Registration ID is
`da57ed28fdb04e262c6d1f2bdb4da10f46f89d3f2858981e9d9dc2fd496dde7e`.
[All results](artifacts/return-transport-2026-11-07.json) and the
[self-contained input/result/audit packet](artifacts/return-transport-2026-11-07.zip)
retain all 23 models, 1,656 forecasts, 782 comparisons, 276 availability strata,
46 matched-decoder contrasts and 92 numerical Monte Carlo guards. Archive SHA-256:
`835dbb9d5df73a1b4bf63adf51e12dcfc8df88c2309f27225bb8550233c735a6`.
All 42 original input-role bytes/paths/hashes are retained without silently
rebasing the registration. No outer or equity fit occurred in this study.

The result is a **stronger chronology control**, not rescue of the new indicators:

| 24-month return forecaster | CRPS | Event Brier | Central 80% coverage |
| --- | ---: | ---: | ---: |
| Original unconditional CDF, strongest prior reference | 0.331074 | 0.039424 | 70.8% |
| Transport intercept only | 0.338484 | 0.043041 | 95.8% |
| Transport context only | 0.434866 | 0.038267 | 62.5% |
| Transport context + chronological age | 0.265783 | 0.036314 | 83.3% |

The chronology model reduces primary CRPS by 19.72% versus the strongest old
reference and improves the same-decoder context model. Its 80% intervals are
narrower as well as covering more observed outcomes. But these are **24
overlapping origins, December 2018–November 2020, with one negative return**.
Event discrimination and calibration are not established. Training ranks make
age equivalent to chronological position, with query rank one: this is a rolling
trend/recency model for mature return labels. It does not establish an economic
law about Bitcoin aging or a learned four-year cycle.

At 12 months the chronology model regresses: CRPS 1.021460 versus unconditional
0.858520 and generative 0.653258; 80% coverage is only 25%. Even the best
12-month transport model loses to the generative reference. The new structural
indicator helps this decoder's weak two-year context model (0.390000 versus
0.434866) but loses to unconditional and chronology controls. Monetary and
attention features do not rescue primary performance. Attention plus availability
is worse than the matched mask-only model; fixed training-availability strata
retain that result rather than selecting favorable periods.

Independent audit reconstructed each of 1,656 forecasts using full and 24 deleted-
label augmented least-squares fits, without calling the runner/scorer/generators.
All transforms, mature pools, 782 cells, 276 strata, 46 contrasts and 92 guards
were checked. Maximum CRPS discrepancy was `2.67e-15`; event/coverage/guard
choices agreed exactly. Forty-three code files, 42 input identities, all parent
receipts and runtime were verified. Eight new synthetic tests pass; reintroduced
formula, query, warmup-support and missingness-reporting bugs fail their oracles.

No further decoder or penalty search is accepted. The old/new indicator-rescue
path has not produced a competitive indicator. The chronology control's narrow
gain warrants **one frozen chronological falsification**, not promotion:

- Preserve the exact rank/ridge/PRESS kernel and use only intercept, context,
  context+age. No variants or horizon-specific tuning.
- Original frozen full snapshot through July 2026, outer origins from 2023,
  exactly 30 mature 12-month and 18 mature 24-month forecasts. Latest 24 labels
  must be available strictly before each query. Raw daily/monthly history through
  2022 is already verified byte-value identical to the owned development snapshot.
- Previously issued development forecasts must stay exact. Newly matured older
  origins remain separate from outer origins.
- Compare with all 13 fixed CDF references and context/unconditional on identical
  support. Both generative outer references are **unavailable**, not beaten;
  extending that model is unnecessary for this stopping check.
- Retain 12/24 CRPS, event Brier, interval coverage/width, event counts, overlap
  diagnostics and every origin. Primary is 24-month return CRPS; no combined score.
- Failure to improve same-decoder context rejects incremental chronology
  assistance on this check. Losing to unconditional stops the claimed benchmark-
  improvement path. Favorable or mixed results authorize neither tuning nor
  promotion, and cannot establish superiority to unavailable generative forecasts.
- Explicitly record selection after inspecting 23 models and primary-target
  results, plus previously exposed outer history. This is not a fresh holdout.

**Completed outer falsification: both stopping conditions triggered.** The
wrapper was independently reviewed and [registration](artifacts/transport-outer-registration-2026-11-07.json)
committed at `21c94d2` before the one replay. Registration ID is
`d25fd91dc7517d312d42b6241086be22efb46020fedd8c6100ccd7963c63d981`.
[Full results](artifacts/transport-outer-2026-11-07.json) and the
[owned-input/result/audit packet](artifacts/transport-outer-2026-11-07.zip)
retain all 144 outer forecasts, 720 CDF peers and 108 comparisons. Archive SHA-256:
`1261bec633496e438a4e29224aac16aaa968b9386234c4eaa836785c0d831378`.

| Outer return forecaster | 12-month CRPS, 30 origins | 24-month CRPS, 18 origins |
| --- | ---: | ---: |
| Unconditional CDF | 0.520563 | 0.304205 |
| Transport intercept | 0.523895 | 0.313330 |
| Transport context | 0.444378 | 0.308208 |
| Transport context + chronology | 0.538629 | 0.529023 |

Chronology is about 74% worse than unconditional on primary two-year loss and
also loses to matched transport context. Its two-year Brier loss is 0.304205 and
80% coverage 50%; the development improvement did not persist. There are only two
negative returns among 18 two-year outer origins and one disjoint two-year path;
one-year outer has eight negatives among 30 origins and three disjoint paths.
Disjoint paths are not asserted independent. The context model's one-year gain
remains a separate mixed result, not a replacement primary objective.

Independent audit recomputed all 144 outer forecasts and 216 prior development
checks via full/deleted-label augmented least squares, plus all 720 issued-CDF
peers, 108 cells, calendar/maturity/class/non-overlap/stopping logic. Maximum
numerical difference was `4.44e-15`; aggregate differences were zero. Previously
issued development forecasts remain exact. Both unavailable generative replicas
stay explicit. Seven outer-wrapper tests pass, including a regression that fixes
the historical 43-file test inventory rather than silently adding unrelated new
research modules to it; its old behavior fails under simulated inventory growth.
No measurement source, kernel, parameter or stored outcome changed in that fix.

The chronology improvement branch and retrospective decoder-rescue path are
**stopped**. Do not tune another penalty, phase, horizon or nearby feature to
repair this result. A fresh reviewer using a different model independently agreed:
the apparatus can establish correct scores on this reconstruction, while exposed
history alone cannot establish the requested professional-use qualification.
The next evidence must be archived before outcomes. No primary model has
qualified; synthetic qualification, historical development and future market
validation remain distinct claims.

### Implemented observed-vintage paper archive

One source-to-shadow-archive vertical slice is implemented before further market
optimization. The current generic v2 archive remains frozen; it accepts a known
publication assertion or unknown vintage, but cannot express the sufficient fact
that exact public bytes were observed **by retrieval completion**. A current
capture does not reveal first publication and cannot repair a historical decision.
Never invent `published_at` from a bucket timestamp or retrieval time.

The accepted v3 contract uses actual runtime capture, issuance and publication
bounds; executes a registered producer on owned captured bytes; and binds raw
responses, selected closed prefix, code/helpers, configuration, runtime and
forecasts. Require every consumed parent to satisfy
`selected close <= capture completion <= issuance <= content-publication bound < entry observation`.
Clock reversals, future/open-bar use, capture after decision, unknown parents,
changed bytes/config/runtime and cohort relabeling must fail. A postwrite clock
sample bounds when immutable forecast content was published; incomplete/late
publication remains visibly incomplete and ineligible. Source age remains a
quality observation, separate from prospective chronology/lineage eligibility.
Local hashes do not authenticate providers, clocks or an adversarial full rewrite;
independently retained heads would be needed for stronger tamper evidence.

Use only frozen baselines initially: unconditional/context empirical CDFs and the
unchanged Student-t price model, terminal returns at 12/24 months. This is an
operational paper witness, not a newly qualified indicator, strategy or forecast
calibration claim. The first November 7 witness belongs to its own immutable
`operational_witness` cohort. The next formal monthly decision is November 30;
it cannot be issued or backdated now. No scheduler, alerts, trade, publication,
paid service or production deployment is included.

The source survey for this slice is recorded here, checked November 7:

| Source | Decision for this bounded slice |
| --- | --- |
| [Coin Metrics Community](https://docs.coinmetrics.io/packages/coin-metrics-community-data) `btc/PriceUSD/1d` | Selected for local noncommercial paper research only; working no-key entitlement metadata verified below |
| [Bitstamp OHLC](https://www.bitstamp.net/api/) | Runner-up, not adopted: commercial data agreement and exact historical/UTC coverage remain unresolved |
| [Coinbase market data](https://www.coinbase.com/legal/market_data) | Excluded: current terms require prior consent for AI/ML development, validation, benchmarking and operation |
| [Kraken OHLC](https://docs.kraken.com/api-reference/market-data/get-ohlc-data) | Latest 720 entries including open bar cannot supply the fixed 730-return fit/history requirement |
| [CoinGecko Demo](https://www.coingecko.com/en/api/pricing) | Free history limitation does not meet the multiyear daily requirement; no account/paid upgrade adopted |
| [Coin Metrics GitHub archive](https://github.com/coinmetrics/data) | Official but stale for this witness: latest BTC file commit May 24, 2026; not a current-close fallback |

The [specific PriceUSD definition](https://docs.coinmetrics.io/network-data/network-data-overview/market/price#usd-denominated-closing-price)
and [timestamp FAQ](https://docs.coinmetrics.io/service-and-support/faqs) give a
beginning-of-day row timestamp for that day's closing price: row D means a close
at D+1 00:00 UTC. Normalize to that **close instant**, not D's start. This is a
provider USD reference close, not an asserted executable exchange price.
At `2026-11-07T02:24:44.696638Z`, unauthenticated metadata from the documented
[catalog query](https://community-api.coinmetrics.io/v4/catalog-v2/asset-metrics?assets=btc&metrics=PriceUSD)
returned `community:true`, daily coverage from July 18, 2010 through the
November 6 row (November 7 close). No price observations were fetched in that
preflight. This verifies advertised access then, not continuity or price truth;
the collector must check actual responses. Generic package documentation still
names a conflicting hostname; the working documented community host is pinned.

The current community documentation and official archive declare
[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). Keep actual captures
and forecasts local in ignored storage, with licence/provenance recorded.
Commercial, professional and trading rights are not established by this research
choice. No professional-use eligibility or redistribution permission is inferred.
Public requests send no account identifiers, credentials or portfolio data;
the provider can observe IP/request metadata, and no Swiss/EU-only log residency
is claimed.

Collector bounds: fixed verified-TLS no-key HTTPS host/path, no cookies/proxy
credentials/cross-host redirects, six requests including retries, two-second
spacing, 2 MiB per response, 10,000 rows and a subprocess wall deadline under
60 seconds. Raw responses are retained before numeric parsing. Require finite
positive consecutive closed daily prices; no interpolation, source stitching,
open-bar values or silent replacement of prior captures. The pure registered
producer performs no network I/O. Source/config/code/cohort registration and
independent offline review preceded the one actual paper capture/append.
The expanded user goal
is unmet: no candidate has demonstrated broad incremental market information or
professional-use reliability. Synthetic qualification cannot supply missing
multi-year outcomes, verified vintages or economic validation.

### First live operational witness and next formal cohort

The separately registered November 7 operational cohort was issued once after
registration commit `e670866` and explicit runner commit `0ef13a7`.
[Metadata](artifacts/paper-shadow-operational-2026-11-07-witness.json) and the
[independent audit](artifacts/paper-shadow-operational-2026-11-07-audit.json)
contain provenance, counts and hashes; provider prices and forecast atoms remain
in ignored `output/paper-shadow-operational-2026-11-07/`. The eight original
registered source files are preserved byte-identically in its `source_vintage/`
directory and Git. Later validator corrections cannot relabel this observation.

One successful HTTP response supplied 3,597 consecutive reference closes from
January 2, 2017 through November 7, 2026. Capture ran from
`2026-11-07T03:03:28.281695Z` to `03:03:28.829042Z`. Forecast content was issued at
`03:03:29.541316Z`, committed at `03:03:29.574213Z` and durably published locally
by `03:03:29.592073Z`, before the registered 22:00 UTC cutoff and November 8
00:00 UTC reference entry. First-publication time remains unknown. The public
scientific-state head is
`09de3de1aa43f84d6c68bc674b2412b2299d10a677f7c308b1f5e422614b79a7`.

Six forecasts cover three frozen baselines at 12/24 months: unconditional CDF,
context CDF and Student-t/GARCH parameter-mixture simulation. The independent
review reproduced all selected prices, mature-label pools, context weights,
calendar endpoints and all 8,192 simulated atoms per horizon, with zero numerical
difference. This is operational lineage evidence. There are **zero mature
outcomes**, no measured prospective score and no professional-use qualification.
The first 12-month label is available November 9, 2027; the first 24-month label
November 9, 2028. Monthly overlapping observations will not become independent
market cycles simply by accumulating more rows.

The v3 boundary binds every scientific file, including failed/pending attempts
and orphan captures, separately from event-chain linkage. It pins function bodies,
default arguments, source files, configuration and runtime. Its
[48-observation stress measurement](artifacts/paper-shadow-v3-2026-11-07-performance.json)
used two 8,192-atom forecasts per observation: 27.6 seconds total, final append
1.04 seconds and verification 0.92 seconds. Local clock/host integrity and pure
producer behavior remain trusted; this is not an independent timestamp authority
or a Python execution sandbox. Old v2 observations are not reclassified.

Before any outcome matured, review found that the generic resolution API could
assign different outcomes or source vintages to different models for the same
observation/target/horizon. Correction `bdd2585` enforces one common numeric
outcome, source capture identity and exact close timestamp across those models,
at both public append and persisted replay boundaries. Different horizons remain
distinct. Equal common outcomes are accepted. Independent guard-removal mutation
produced five assertion failures; the original actual witness still verifies
against its entire saved state and head, with zero resolutions. This guard does
not itself derive a true market outcome: a future reviewed resolver must calculate
the label from owned closed-price evidence before supplying it to this API.

The November 30 formal monthly cohort remains **unissued** and separate. Its
registration was first refreshed before that future decision to bind the
corrected validator: previous ID
`82f968f419f9b63683ecc02fae0a64f409c609ee3266be54cd1470e7919d6000`
is retained in Git at `e670866`; the validator revision was
`8a5353903819c5702d29681cd90091138532b88cf0d75c052cce36171d2b2908`.
Only `shadow_archive_v3.py` changed among the eight bound source files at that
step. The subsequent transport-only revision below is now current. Baseline
parameters, numerical forecast producers, calendar, cohort dates and configuration
are unchanged. The already-issued operational registration was not rewritten.
The explicit runner rejects a missing live flag, a different current UTC day, changed
source/config/runtime or reused output directory before acquisition. No scheduler
is installed. On the registered day, before 22:00 UTC, the next bounded action is:

```bash
python scripts/run-paper-shadow.py \
  --registration docs/artifacts/paper-shadow-monthly-2026-11-30-registration.json \
  --output-dir output/paper-shadow-monthly-2026-11-30 \
  --live-capture
```

Use the registered Python 3.12.16 / NumPy 2.4.6 / pandas 2.3.3 environment. A
failed run leaves its reserved output directory and failure evidence. Do not
retry under a new directory or registration, backdate, or alter a registration
to make an observed result fit. The archive consumes an issuance day within that
archive; it does not enforce a global attempt budget across separately created
directories, and a capture failure can precede issuance. This protocol-level
restriction depends on the trusted local operator preserving all attempts.
The current noncommercial provider choice does not establish rights to use this
feed in a professional trading product. The next scientific step is unchanged
baseline collection, not another retrospective decoder rescue. An informative
future baseline is a reference to beat, not evidence that a candidate beat it.

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
demonstrate a better market indicator. External monthly-equity falsification
and one local noncommercial live price capture are separately documented above;
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
initially requested keeping all commits local. On November 7 he explicitly
authorized publishing the accumulated commits; this supersedes that hold. The
remote advanced independently with automated data refresh `4d9789b`; it was not
used to alter the frozen evidence; it was subsequently merged for authorized
publication, preserving the independent snapshots.
Research correctness repairs and benchmark history are integrated into main.
The three newly failed experimental implementations are retained under archive
tags and in the portable evidence packet, rather than adopted into the model.
The original main checkout remains the integration owner; ignored private paper
captures and important French source files stay there. Untracked user directories
`.codex/` and `.github/hooks/` remain untouched. No force push or manual deployment
is part of this publication. Workers do not push.

Latest checks and publication scope: the full backend suite, unchanged web tests,
script tests, build, release-integrity validation and existing security scan are
run before the authorized main push. Workflow validation uses actionlint 1.7.12.
The final integrated backend suite passed **459 tests in 426.0 seconds**
(`/private/tmp/research-programme-backend-20261107.log`); the three archived arms
separately passed 4, 5 and 7 focused tests, with deliberate defect mutations caught.
Existing pandas future warnings remain. Node script tests passed 59/59; frontend
checks passed 70/70, and the production build and both release-integrity checks
passed. The locked dependency security scan passed 172 npm / 11 Python packages and
its canaries. The slow legacy evaluator's cache-format-only rewrite was restored
to the merged remote bytes after its process stopped; it is not published. Hosted CI
results are observable in [Actions](https://github.com/j0shcd/risk-metric/actions)
and are separate from these local checks; a passing research run does not grant
production acceptance. Both production policy and canonical identity remain
unchanged. A partial legacy evaluation was stopped and is not used as a finding.

This document owns project-specific lessons and the next bounded contract.
README's general benchmark entry point remains accurate and links here; no new
user-facing claim or documentation owner was needed. The skill-harvest and loaded-
skill self-improvement review found no additional global skill change necessary.

### Hosted publication check and portable test correction

The authorized 155-commit publication reached main at `cbb00db`. Hosted
[CI 42369901823](https://github.com/j0shcd/risk-metric/actions/runs/42369901823)
passed dependency security and the web test/build job. The backend job ran all 459
tests and failed only two archive fixture setups: both hardcoded macOS's
`/private/tmp`, which is absent on the Linux runner. These were test errors, not
forecast-score or model-acceptance failures. The legacy diagnostic was skipped
following the unit-test failure.

The test-only correction creates those temporary roots beneath
`Path(tempfile.gettempdir()).resolve()`: the platform chooses the location and
macOS aliases are resolved before the archive's strict ownership checks. A new
regression supplies a synthetic native temp root through a symlink and requires
the canonical parent. All 16 focused tests pass locally and under the exact CI
environment in independent review. Reintroducing the hardcoded path fails the
regression. The initial sweep was limited to tests and missed the collector's own hardcoded
worker directory. This first repair changed no benchmark, producer or result.
Its approved publication reached main at `2f46056`; hosted
[CI 42370953200](https://github.com/j0shcd/risk-metric/actions/runs/42370953200)
ran 460 tests and failed one remaining runtime use of the same path, while security
and web checks again passed. The first repair was incomplete; neither hosted
backend run is reported as passing.

The complete correction changes only the collector worker's temporary root to
`Path(tempfile.gettempdir()).resolve()`. Before fixing it, a new mechanical oracle
failed both a scan of all versioned Python tempfile creators and a runtime
public timeout-capture test that makes `/private/tmp` unavailable. After correction,
all 46 focused archive/collector/oracle tests pass under the CI settings; an
independent 19-test portability/adapter run also passes. The source sentinel covers
keyword and positional literal roots (including Path-wrapped roots), with positive
witnesses; it is not a universal alias/dataflow proof. Current source inventory
has no alias bypass. Other surviving `/private/tmp` strings are inert synthetic
config paths, not actual directory creation.

The transport source change requires a new **unissued** November 30 registration:
`39ec7003ecfb24f4adae5a8f4634990766cac27f80cd0cb6aaa063a6a413dbe9`.
Only `coinmetrics_shadow.py` changes among its bound source files, and only the
loaded `fetch` function changes semantic identity. Forecast calculations, all
parameters, dates and input/label conventions are unchanged. The already-issued
operational registration, all six forecasts and the entire saved archive state
still verify unchanged. Its original source vintage remains preserved. No new
live capture or research fitness trial was run for these portability fixes.
A new approved publication and hosted verification complete the repair workflow;
research results and the frozen benchmark remain unchanged.

### Active-goal completion audit

| Requirement | Current authoritative evidence | Status |
| --- | --- | --- |
| Detect useful information under dependent worlds | Gaussian oracle and registered panel test, 398/400 positive declarations | Pass in finite known-law panel scope; previous single-path searches still fail |
| Control false promotion under declared dependent nulls | Whole-path CRT exchangeability under exact Q, full-search equivalence tests, 1,500 fresh null campaigns | Pass within the declared one-campaign synthetic scope |
| Chronological/provenance integrity | Strict label boundaries, 43-column producer oracle, immutable receipts and first audited live operational witness | Fixed-input mechanics and current capture lineage verified; historical market vintages and future outcomes remain unverified |
| Safe adaptive-search scope | Registered conditional tests, shared attempt/freeze/release ledger and explicit exposure lineage | Finite scope defined; unlimited human adaptation not qualified |
| Broad incremental BTC information | Nineteen indicator variants fail qualification; chronology improvement fails frozen outer check | No candidate promoted; not a prerequisite for finishing a useful research round |
| Prospective market validation | Six frozen forecasts issued in one operational observation; no mature outcomes | Pending future labels; no prospective performance claim |
| Publication control | Explicit approval for accumulated main push; daily source/effective-setting guards; unchanged production gate | Research may be shared; no model promoted |

The earlier professional-use qualification objective remains unmet. The active
project direction is now the continuing research programme above; a completed
round need not establish professional suitability. Panel qualification, honest
market comparison and prospective validation remain separate requirements. Full-reference guarding, monthly falsification, the three-slot campaign
and the one decoder diagnostic are complete within their declared measurement
scope. The chronology-control outer falsification is complete and failed. The
first operational witness is issued; the next formal monthly decision is
November 30, 2026, under its separately frozen protocol. Do not restart historical
search merely to fill the waiting period. A new candidate needs a materially new
registered information hypothesis and a credible fresh evaluation opportunity.
Historical exposure, missing independent cycles, professional feed rights and
prospective validation remain unresolved; no result is relabeled a fresh holdout.
The requested professional-use indicator remains unqualified. The current
programme continues by recording bounded research rounds, including negative
results; live validation is one track rather than a block on all research.
