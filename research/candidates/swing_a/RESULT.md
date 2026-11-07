# Development result and finalist preregistration

Decision: no demonstrated broad improvement; do not promote to production. The
occupancy-memory hypothesis failed its opportunity-first test. Preregister the
no-memory ablation (`memory_weight=0`) solely for the parent's mechanical outer
diagnostic, because it has the lowest return CRPS at both testable horizons within
this family. No new variants will be tuned after the outer replay.

All scores below are CRPS (lower is better). Separate outcomes/horizons are never
averaged. The best fixed reference is identified independently per cell and is a
descriptive oracle across 13 prespecified references, not a deployable selector.

| Horizon | Target | n | w=0 finalist | w=.5 | w=1 | Incumbent | Unconditional | Best fixed reference |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 12 | terminal_log_return | 48 | 0.855343 | 0.886059 | 0.908580 | 0.880342 | 0.858520 | calendar_cycle_cos_4y 0.810894 |
| 12 | entry_adverse_log_loss | 48 | 0.341412 | 0.349213 | 0.351699 | 0.357313 | 0.361899 | calendar_cycle_sin_4y 0.351166 |
| 12 | peak_drawdown_log_loss | 48 | 0.255046 | 0.254054 | 0.244160 | 0.273098 | 0.282293 | calendar_cycle_sin_4y 0.260172 |
| 24 | terminal_log_return | 24 | 0.456734 | 0.477084 | 0.496247 | 0.433748 | 0.331074 | time_years_since_2012 0.411880 |
| 24 | entry_adverse_log_loss | 24 | 0.236041 | 0.226005 | 0.224762 | 0.241535 | 0.249353 | price_drawdown_12m 0.227048 |
| 24 | peak_drawdown_log_loss | 24 | 0.303706 | 0.309671 | 0.311153 | 0.303272 | 0.300568 | price_ath_drawdown 0.274003 |

Regressions and interpretation:

- No-memory beats the incumbent in all 12-month cells and 24-month entry loss,
  but loses to it in 24-month return and true drawdown. It does not dominate the
  strong baseline set. Its 24-month return CRPS is substantially worse than the
  unconditional mature-label distribution; an attractive rank relationship is
  insufficient to establish useful distribution forecasts.
- Memory improves 12-month true drawdown and 24-month entry loss but worsens
  both return horizons, 12-month entry loss and 24-month true drawdown relative
  to no-memory. This is not a Pareto gain.
- No-memory direction diagnostics for return are +0.519/+0.642/+0.572 at
  12/24/48 months. Four-year true-drawdown alignment is negative (-0.423);
  higher risk does not consistently mean more future peak-to-trough loss.
- All 48-month forecast cells have n=0. Their rank diagnostics use 48 complete
  historical labels and do not validate four-year forecast skill.
- The 12/24-month forecast counts are 48/24 overlapping origins, not independent
  cycle replications. These exploratory differences have no asserted market
  significance, probability calibration, financial utility or confidence guarantee.

## Reproduction and audit

Producer: `python -m research.candidates.swing_a.generate --bundle BUNDLE --output NEW_CSV`.
Exact scorer commands, output directories and trial hashes are in `attempts.jsonl`.
All trial requests, full predictions, comparisons, reports and artifact manifests
are preserved in `development_trials.zip`; the frozen score CSV is adjacent.
Code and all input/output hashes are recorded in `finalist.json`. All three planned
variants ran once; no extra variants or failed attempts.

Six isolated tests passed. Two mutations (removing one-day lag; allowing nonfinite
half-lives) each made the corresponding regression fail and were restored. Raw
bundle smoke run produced 132 finite monthly values, of which the locked evaluator
uses 97 common dates. Source timestamps/revisions remain unverified.

Brief vs delivered: monthly causal price-history state, three independent proposals,
three frozen variants, all attempts and one diagnostic finalist delivered. A useful
multi-year improvement was not established. Parent owns all post-2022 replay and
integration; production is unchanged. Next bounded step is that frozen replay or
archiving the negative result. There is no open parameter decision. No shared
documentation change or global skill update is justified by this isolated trial.
