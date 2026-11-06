# Duplicate-invariant readout v2

This is an additional decoded-representation trial following v1 review, not independent validation. Code was committed as `076db34` before one development run. No candidate changed, no outer data were accessed, no configurations were tuned after results, and no failed study runs were discarded.

## Owning invariant

Two coordinates are equivalent only when their complete training rank vectors AND query ranks match exactly. Collapse each equivalence class to one equally weighted coordinate and sort canonical classes before mean absolute rank distance. This prevents duplicate features, positive monotone copies and repeated copies from reweighting distance. If equal training ranks produce different query ranks, retain both. The eight-neighbor rule, fractional boundary ties, 50:50 pooled mixture, 24 mature labels and every other study setting remain fixed.

The frozen v1 decoder is not overwritten. The new wrapper injects its decoder into the unchanged evaluator only within a scoped context and restores the original even on error. It is a single-threaded research entry point; do not concurrently call v1/v2 in the same interpreter. New receipts include both source hashes and the v2 protocol.

## Results and gaps

Only 12 of 354 cell CRPS values changed, all belonging to combined-rank `price_trend_12m` and `price_volatility_90d`, which exactly duplicate existing context. Those now match context-only weights, atoms and CRPS at every origin: 432 matched prediction records. All candidate B cells, all median cells, the unconditional comparator and the best-reference gaps remain unchanged.

| Months | Outcome | B combined-rank CRPS | Best same-arm reference | Gap (B minus best) |
|---:|---|---:|---|---:|
| 24 | terminal_log_return | 0.424059 | time_years_since_2012 (0.338022) | +0.086037 |
| 24 | entry_adverse_log_loss | 0.237583 | calendar_cycle_cos_4y (0.226636) | +0.010948 |
| 24 | peak_drawdown_log_loss | 0.256347 | calendar_cycle_sin_4y (0.246203) | +0.010144 |
| 12 | terminal_log_return | 0.879477 | calendar_cycle_cos_4y (0.833875) | +0.045602 |
| 12 | entry_adverse_log_loss | 0.357626 | time_years_since_2012 (0.351696) | +0.005930 |
| 12 | peak_drawdown_log_loss | 0.261713 | time_years_since_2012 (0.259635) | +0.002079 |

The primary 24-month return result remains .424059 against unconditional .331074 and best matched reference .338022. No broad improvement or scalar winner is established. Full old/new gaps for all 354 cells are in `v1_v2_comparison.csv`; all diagnostics and references are in `cells.csv` and the portable packet. There are 48 overlapping scored origins at 12 months and 24 at 24 months; no four-year study.

## Scope and limitations

V1 combined-rank gains can arise from pure coordinate reweighting and must not be called new information. V2 removes only exact rank-coordinate duplication. General nonlinear functions of context can still change neighborhood geometry and apparent learnability without adding information conditional on the underlying price history. Neither version establishes conditional-information novelty, probability calibration, significance or financial suitability. Uneven interval coverage and the sample-size/source-vintage limitations of v1 still apply.

Proposed additional baselines remain unimplemented: 48-month price anchor, recency-weighted unconditional distribution, joint price-state reference and combined cycle phase. They require separate preregistration and trial accounting.

## Verification and restart

Run `/private/tmp/risk-pr-review-wcp0ax41/python/bin/python -m unittest tests/test_readout_study_v2.py tests/test_readout_study.py tests/test_swing_b_generator.py -v`: 14 tests passed. New owning-boundary oracles cover both context-coordinate duplicates, unchanged CRPS under zero additional information, monotone/repeated copies, column permutation, query-breaking equivalence, effective neighbor mass eight and decoder restoration. Disabling the equivalence collapse produced the expected oracle failure; the synthetic fixture also exposes v1’s unequal duplicate weights.

The new receipt verifies. Old source, candidate generator and old portable receipt hashes match their recorded originals. Reproduce once into a new directory with `/private/tmp/risk-pr-review-wcp0ax41/python/bin/python -m research.readout_study_v2 --bundle /private/tmp/risk-hillclimb-inputs-gj866s2j --output-dir NEW_EXCLUSIVE_DIRECTORY`.

Next bounded step: root reviews and integrates the new version with explicit representation-study accounting. No production or push. This note owns the restart status; existing frozen notes and receipts remain unmodified. Brief versus delivered: exact duplicate invariant, regression oracle, code freeze, one additional development study and full old/new comparison delivered; broader redundancy control remains unaddressed. Skill-harvest review: this concrete trap is already encoded in the owning oracle and study limitations; no additional global skill proposed.
