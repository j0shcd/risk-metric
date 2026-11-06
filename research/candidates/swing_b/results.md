# Locked development results

Lower CRPS is better. Gaps are candidate minus comparator; positive means worse. No cell aggregate or significance claim. Three predeclared variants, three successful trials, zero failed trials. No further tuning.

| Candidate | Months | Outcome | n | CRPS | Gap vs unconditional | Best fixed reference | Gap vs best | Risk alignment |
|---|---:|---|---:|---:|---:|---|---:|---:|
| adaptive | 12 | terminal_log_return | 48 | 0.820350 | -0.038170 | calendar_cycle_cos_4y | +0.009456 | 0.511593 |
| adaptive | 12 | entry_adverse_log_loss | 48 | 0.344483 | -0.017417 | calendar_cycle_sin_4y | -0.006683 | 0.475441 |
| adaptive | 12 | peak_drawdown_log_loss | 48 | 0.257508 | -0.024785 | calendar_cycle_sin_4y | -0.002664 | 0.625862 |
| adaptive | 24 | terminal_log_return | 24 | 0.450009 | +0.118936 | time_years_since_2012 | +0.038130 | 0.688437 |
| adaptive | 24 | entry_adverse_log_loss | 24 | 0.237501 | -0.011852 | price_drawdown_12m | +0.010453 | 0.509501 |
| adaptive | 24 | peak_drawdown_log_loss | 24 | 0.303077 | +0.002509 | price_ath_drawdown | +0.029074 | 0.579723 |
| slow | 12 | terminal_log_return | 48 | 0.822279 | -0.036241 | calendar_cycle_cos_4y | +0.011386 | 0.199271 |
| slow | 12 | entry_adverse_log_loss | 48 | 0.339620 | -0.022280 | calendar_cycle_sin_4y | -0.011546 | 0.199631 |
| slow | 12 | peak_drawdown_log_loss | 48 | 0.256524 | -0.025769 | calendar_cycle_sin_4y | -0.003648 | 0.142731 |
| slow | 24 | terminal_log_return | 24 | 0.440332 | +0.109258 | time_years_since_2012 | +0.028452 | 0.291015 |
| slow | 24 | entry_adverse_log_loss | 24 | 0.243862 | -0.005491 | price_drawdown_12m | +0.016814 | 0.370353 |
| slow | 24 | peak_drawdown_log_loss | 24 | 0.287913 | -0.012655 | price_ath_drawdown | +0.013910 | 0.305442 |
| fast | 12 | terminal_log_return | 48 | 0.875419 | +0.016899 | calendar_cycle_cos_4y | +0.064525 | 0.168735 |
| fast | 12 | entry_adverse_log_loss | 48 | 0.369601 | +0.007702 | calendar_cycle_sin_4y | +0.018435 | 0.197282 |
| fast | 12 | peak_drawdown_log_loss | 48 | 0.278435 | -0.003858 | calendar_cycle_sin_4y | +0.018264 | 0.536468 |
| fast | 24 | terminal_log_return | 24 | 0.482530 | +0.151457 | time_years_since_2012 | +0.070651 | 0.431796 |
| fast | 24 | entry_adverse_log_loss | 24 | 0.233992 | -0.015361 | price_drawdown_12m | +0.006944 | 0.220430 |
| fast | 24 | peak_drawdown_log_loss | 24 | 0.298492 | -0.002076 | price_ath_drawdown | +0.024489 | 0.777025 |

## Finalist and negative evidence

`swing_b_adaptive` is preregistered for exploratory outer replay. This retains the preferred pre-scoring specification because its risk ordering is positive and stronger than the slow variant in all six 12/24-month cells. It is not a Pareto winner: slow improves four CRPS cells, and fast improves 24-month entry-loss CRPS and drawdown alignment. No parameter changes were made after observing outcomes.

Neither adaptive nor slow establishes a broad improvement. Adaptive loses four of six cells against the best fixed references, including all three 24-month cells. Its 24-month terminal-return CRPS is .450009 versus .331074 unconditional; its 24-month drawdown CRPS is .303077 versus .300568 unconditional. Only 12-month entry-loss and peak-drawdown CRPS beat both unconditional and best fixed references.

The 48-month scored forecast count is zero in every variant. Adaptive retrospective 48-month ordering is +.498372 return, +.610405 entry-loss, but −.284812 true drawdown. Those diagnostics are not forecast validation. Overlapping labels, only 48/24 scored origins at 12/24 months, pre-exposed market history, reconstructed source vintages, and development selection preclude a significance, calibration, financial utility or production claim. Strongest alternative explanation: a few historical cycle alignments.

No bootstrap or independent uncertainty interval was added to the locked protocol; differences are descriptive observed replay results. Root owns mechanical pseudo-OOS replay and cross-researcher comparison. Do not tune this finalist using outer results.
