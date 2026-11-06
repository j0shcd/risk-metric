# Frozen development readout study

Completed one registered study, with no post-result tuning, candidate edits or outer data access. Producer commit `595b04e`; candidate remains frozen at `8837516`. The experiment compares four fixed readout arms for all 13 references and candidate B on identical origins and mature training pools.

Primary: 24-month terminal log return. The downside outcomes and 12-month cells are separate diagnostics/guardrails, never a weighted total. Each 12-month cell has 48 overlapping forecast origins; each 24-month cell has 24. There is no four-year study or four-year validation.

## Observed findings

The coarse-decoder hypothesis is not a general explanation for candidate B’s weakness. On 24-month return, rank combined improves B from .450009 to .424059 but remains worse than unconditional .331074 and the same-arm best fixed reference .338022. Removing context is more helpful: median indicator-only reaches .336686, still slightly worse than unconditional and worse than the corresponding fixed-reference best .293753. Rank indicator-only is worse at .385751.

Rank combined improves B’s 24-month drawdown CRPS from .303077 to .256347, but the same-arm calendar-sine reference reaches .246203. The change regresses all three 12-month combined CRPS coordinates and marginally regresses 24-month entry-loss CRPS. No scalar winner or broad improvement is established.

Nominal 80% interval coverage is only 37.5–39.6% for B’s 12-month return arms (unconditional 39.6%), versus 91.7% across B’s 24-month return arms (unconditional 95.8%). This is descriptive evidence of uneven forecast reliability; dependence and tiny effective sample sizes preclude a calibration verdict. Same-origin B return alignment is +.7465 at 12 months and +.8104 at 24 months, yet proper forecasting loss can still be poor. Directional rank association is not probability calibration or incremental information.

## Candidate B: every arm and coordinate

| Months | Outcome | Arm | CRPS | Unconditional | Matched context | Best fixed reference (same arm) | Gap vs best |
|---:|---|---|---:|---:|---:|---|---:|
| 24 | terminal_log_return | indicator_median | 0.336686 | 0.331074 | 0.453800 | time_years_since_2012 (0.293753) | +0.042934 |
| 24 | terminal_log_return | combined_median | 0.450009 | 0.331074 | 0.453800 | time_years_since_2012 (0.411880) | +0.038130 |
| 24 | terminal_log_return | indicator_rank | 0.385751 | 0.331074 | 0.444897 | dca_bottom_reversal_component (0.280927) | +0.104824 |
| 24 | terminal_log_return | combined_rank | 0.424059 | 0.331074 | 0.444897 | time_years_since_2012 (0.338022) | +0.086037 |
| 24 | entry_adverse_log_loss | indicator_median | 0.238928 | 0.249353 | 0.238338 | calendar_cycle_cos_4y (0.220722) | +0.018206 |
| 24 | entry_adverse_log_loss | combined_median | 0.237501 | 0.249353 | 0.238338 | price_drawdown_12m (0.227048) | +0.010453 |
| 24 | entry_adverse_log_loss | indicator_rank | 0.237088 | 0.249353 | 0.242496 | calendar_cycle_cos_4y (0.211183) | +0.025905 |
| 24 | entry_adverse_log_loss | combined_rank | 0.237583 | 0.249353 | 0.242496 | calendar_cycle_cos_4y (0.226636) | +0.010948 |
| 24 | peak_drawdown_log_loss | indicator_median | 0.277575 | 0.300568 | 0.297130 | calendar_cycle_sin_4y (0.245053) | +0.032523 |
| 24 | peak_drawdown_log_loss | combined_median | 0.303077 | 0.300568 | 0.297130 | price_ath_drawdown (0.274003) | +0.029074 |
| 24 | peak_drawdown_log_loss | indicator_rank | 0.258611 | 0.300568 | 0.278970 | calendar_cycle_sin_4y (0.213422) | +0.045190 |
| 24 | peak_drawdown_log_loss | combined_rank | 0.256347 | 0.300568 | 0.278970 | calendar_cycle_sin_4y (0.246203) | +0.010144 |
| 12 | terminal_log_return | indicator_median | 0.887624 | 0.858520 | 0.854808 | calendar_cycle_cos_4y (0.817595) | +0.070029 |
| 12 | terminal_log_return | combined_median | 0.820350 | 0.858520 | 0.854808 | calendar_cycle_cos_4y (0.810894) | +0.009456 |
| 12 | terminal_log_return | indicator_rank | 0.897782 | 0.858520 | 0.898505 | calendar_cycle_cos_4y (0.832782) | +0.064999 |
| 12 | terminal_log_return | combined_rank | 0.879477 | 0.858520 | 0.898505 | calendar_cycle_cos_4y (0.833875) | +0.045602 |
| 12 | entry_adverse_log_loss | indicator_median | 0.362414 | 0.361899 | 0.353230 | time_years_since_2012 (0.347952) | +0.014462 |
| 12 | entry_adverse_log_loss | combined_median | 0.344483 | 0.361899 | 0.353230 | calendar_cycle_sin_4y (0.351166) | -0.006683 |
| 12 | entry_adverse_log_loss | indicator_rank | 0.362782 | 0.361899 | 0.366023 | time_years_since_2012 (0.351574) | +0.011208 |
| 12 | entry_adverse_log_loss | combined_rank | 0.357626 | 0.361899 | 0.366023 | time_years_since_2012 (0.351696) | +0.005930 |
| 12 | peak_drawdown_log_loss | indicator_median | 0.264409 | 0.282293 | 0.263792 | calendar_cycle_sin_4y (0.258343) | +0.006066 |
| 12 | peak_drawdown_log_loss | combined_median | 0.257508 | 0.282293 | 0.263792 | calendar_cycle_sin_4y (0.260172) | -0.002664 |
| 12 | peak_drawdown_log_loss | indicator_rank | 0.257933 | 0.282293 | 0.276326 | calendar_cycle_sin_4y (0.253207) | +0.004726 |
| 12 | peak_drawdown_log_loss | combined_rank | 0.261713 | 0.282293 | 0.276326 | time_years_since_2012 (0.259635) | +0.002079 |

The best-reference column is a retrospective per-cell envelope, not a reference chosen before each origin. All 354 cells, including every reference and comparator, are in `cells.csv`; complete predictions, atoms, weights, fixed four-bin reliability diagnostics and source/code hashes are in `development_packet.zip`.

## Protocol and interpretation

Training-only empirical percentile = (number strictly below + half number equal)/24. Query percentiles use training rows only. Rank distance is mean absolute coordinate distance. Eight neighbors receive fractional equal-distance boundary membership; weights are half uniform and half neighbor mass. Median combined falls back exactly to context if its cell is empty; median indicator-only falls back to uniform. Context median and context rank are separate matched comparators. Concentration 1/sum(weight²) measures weight concentration, not independent observations.

Return event is log return<0. Entry-loss and true-drawdown events are log loss>log(2), corresponding to a loss exceeding 50%; equality is excluded. Central 50/80% intervals use inclusive endpoint coverage and the weighted inverse empirical CDF. Outside-range flags use all atom extrema. Reliability bins are fixed [0,.25),[.25,.5),[.5,.75),[.75,1]. These diagnostics do not recalibrate forecasts. Same-origin Spearman correlation is reported for every nonconstant reference; declared alignment remains null for references with undeclared direction. No direction is inferred after seeing outcomes.

## Verification and restart

Run `/private/tmp/risk-pr-review-wcp0ax41/python/bin/python -m unittest tests/test_readout_study.py tests/test_swing_b_generator.py -v`: 9 tests pass. They cover fractional boundary ties, permutation/monotone invariance, training-only ranks, exact fallback, log-event boundaries, forecast support, strict maturity and future-suffix invariance. Runtime-only mutations deliberately using a .5 log-loss threshold and wrong query percentile each failed their sentinel. Initial test fixture lacked required provenance; that fixture was corrected before the first study run. No failed study runs or alternate configurations were discarded.

The six combined-median cells match the prior locked study’s CRPS within 1e-14 and identical scored-origin hashes. The artifact receipt verifies. Reproduce the fixed run with `/private/tmp/risk-pr-review-wcp0ax41/python/bin/python -m research.readout_study --bundle /private/tmp/risk-hillclimb-inputs-gj866s2j --output-dir NEW_EXCLUSIVE_DIRECTORY`. No dependencies installed, production modified or outer data consumed.

Next bounded step: root independently reviews and integrates this diagnostic. Proposed missing baselines remain unimplemented: causal 48-month price anchor, recency-weighted unconditional distribution, joint price-state context and joint cycle phase. Their parameters would require declaration before a separate study. Do not quietly append them to this run.

Brief vs delivered: fixed 2×2, candidate + 13 references, same 24-label mature pool/support, primary 24-month return, separate downside coordinates, all requested calibration diagnostics, atomic source freeze and one recorded development run delivered. No broad improvement, financial utility, calibrated probabilities, statistical significance or prospective validity demonstrated. Strong alternative explanation: few market episodes plus decoder-specific interactions with stale overlapping label pools.

Limitations: source vintages and UTC closes unverified; overlapping origin counts do not measure independent evidence; selection/readout multiplicity remains; diagnostic intervals have no uncertainty guarantees. Existing shared scientific documentation need not be changed in this worker checkout; this note is the restartable study owner until root integration. Skill-harvest/self-improvement review found no new cross-project rule beyond existing causal/provenance and preregistration instructions.
