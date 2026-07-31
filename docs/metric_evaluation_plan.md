# Metric Evaluation Plan

Status: Phase 1 planning draft  
Owner: risk-metric repo  
Last updated: 2026-06-21  

This document is the single source of truth for the metric evaluation project. It defines the tests, artifacts, validation rules, implementation order, and frontend storytelling constraints for evaluating the strengths and weaknesses of the risk metrics in this repo.

The goal is not to prove that a metric is "right" in an absolute sense. The goal is to learn, with disciplined humility, where each metric is useful, where it is fragile, how much confidence the evidence deserves, and whether the metric survives realistic use.

## Goals

1. Identify what each metric predicts best: tops, bottoms, drawdowns, rallies, volatility, bad entries, good entries, or practical allocation decisions.
2. Separate true signal from eye-test pattern matching, lookahead leakage, overfitting, and lucky historical alignment.
3. Evaluate real-world usability with low-frequency weekly and monthly decision rules, transaction costs, missing data, stale sources, and simple baselines.
4. Produce reproducible artifacts that can be inspected locally, validated automatically, and later exported to the React dashboard.
5. Preserve claim discipline: every result must carry sample size, uncertainty, caveats, and validator warnings.

## Non-Goals

1. This project will not build an optimized trading system.
2. This project will not use high-frequency trading, leverage, shorts, derivatives, tax modeling, or broker-specific execution assumptions in the first implementation.
3. Synthetic market tests will not be treated as evidence of real-world predictive power. They are behavior and harness-validation tests.
4. Frontend presentation will not rank metrics as "best" unless the evidence survives uncertainty, baseline, leakage, and regime checks.

## Current Repo Context

The current codebase already has useful foundations:

- `risk_engine/benchmark.py` builds threshold, quantile, and local-extrema labels, then computes AUC, PR-AUC, lead recall, false alarm rate, event coverage, and aggregate benchmark summaries.
- `risk_engine/calibration.py` applies walk-forward style calibration to primary outputs and already includes simple financial-quality scoring.
- `risk_engine/pipeline.py` produces core series, metric/category breakdowns, source health, metric health, operational alerts, benchmark outputs, and financial benchmark artifacts.
- `risk_engine/web_export.py` exports versioned JSON artifacts under `data/web/v2/`.
- Tests already cover benchmark behavior, calibration, diagnostics, scoring, data-source contracts, web export contracts, and React rendering.

The new evaluation suite should extend these foundations, not replace them.

## Metric Semantics And Primary Claims

Each metric must be tagged with a semantic type before evaluation:

- `probability_like`: intended to approximate an event probability. Probability calibration tests may produce probability-language claims.
- `ordinal`: intended to rank relative risk or opportunity. Monotonicity and rank-correlation claims are allowed; raw probability claims are not.
- `index`: composite or descriptive index where direction and relative level matter more than probability interpretation.
- `policy_signal`: intended mainly to drive a practical policy. Strategy and guardrail tests are primary; calibration tests are secondary.

Initial semantic types:

| Metric | Type | Primary Confirmatory Outcome |
| --- | --- | --- |
| `top_reversal_risk` | `ordinal` | Future drawdown, top labels, defensive allocation usefulness |
| `bottom_reversal_risk` | `ordinal` | Future rally, bottom labels, opportunistic allocation usefulness |
| `dca_risk` | `policy_signal` | DCA timing quality, entry risk, practical cashflow usefulness |
| `btc_risk_signal` | `index` | Broad future downside/upside asymmetry and benchmark label ranking |
| `total_market_risk_signal` | `index` | Broad market-cycle context and benchmark label ranking |
| `trend_composite_score` | `index` | Trend/cycle extension and forward return asymmetry |
| `attention_score` | `index` | Future volatility, crowdedness, and extreme-event context |
| `headline_attention` | `index` | Future volatility and crowdedness |
| `cycle_extension_score` | `ordinal` | Future drawdown risk and late-cycle behavior |
| `cycle_frenzy_score` | `ordinal` | Future drawdown risk and top labels |
| `cycle_accumulation_score` | `ordinal` | Future rally and bottom labels |
| `cycle_p_frenzy` | `probability_like` | Fitted frenzy-regime probability and top labels |
| `cycle_p_accumulation` | `probability_like` | Fitted accumulation-regime probability and bottom labels |

All other metric/outcome combinations are exploratory unless promoted in this document before a run. Exploratory results can guide learning, but they cannot become headline dashboard claims without a later confirmatory run.

## Confirmatory Versus Exploratory Results

The suite must separate:

- `confirmatory_results`: predeclared metric/outcome/horizon relationships from this document and the resolved evaluation config.
- `exploratory_results`: all additional sweeps, alternative labels, regime slices, sensitivity checks, synthetic scenarios, and unexpected discoveries.

Confirmatory results may support dashboard claims if they pass claim gates. Exploratory results may appear in the dashboard only as diagnostics or leads for future investigation.

Primary initial confirmatory endpoints:

1. `top_reversal_risk` ranking of future drawdown/top labels at 6, 12, 24, and 36 months.
2. `bottom_reversal_risk` ranking of future rally/bottom labels at 6, 12, 24, and 36 months.
3. `dca_risk` improvement or risk reduction versus same-cashflow DCA at monthly cadence.
4. `attention_score` and `headline_attention` relationship with future realized volatility at 1, 3, 6, and 12 months.
5. `cycle_extension_score`, `cycle_frenzy_score`, and `cycle_p_frenzy` relationship with top-risk outcomes.
6. `cycle_accumulation_score` and `cycle_p_accumulation` relationship with bottom-opportunity outcomes.

## Live Availability And Source Latency

Date indexes alone are not enough for live-style evaluation. Every source and derived metric artifact must carry or infer:

- `observation_date`: date the value describes.
- `available_at_date`: earliest date the value could reasonably have been used.
- `source_updated_at`: fetch/update timestamp if known.
- `availability_assumption`: explicit rule used when true availability is unknown.
- `availability_confidence`: `known`, `estimated`, or `unknown`.
- `source_trust_tier`: `high`, `medium`, `low`, or `experimental`.
- `data_processing_state`: `raw`, `cleaned`, `interpolated`, `backfilled`, `derived`, or `unknown`.

If `available_at_date` is unknown, live-style claims must be downgraded at least one evidence level and tagged with `unknown_availability`. For known delayed sources, live-style tests must use `available_at_date`, not `observation_date`.

Source audits must include schema checks, range checks, discontinuity checks, source-mode changes, and suspicious constant-value periods. File hashes catch changed bytes; they do not catch changed vendor definitions or poisoned semantics.

## Researcher Degrees Of Freedom

The current metrics were designed after seeing much of Bitcoin's historical behavior. Therefore, even walk-forward validation of the current frozen code is best interpreted as historical validation of an existing design, not clean prospective discovery.

Every run must record:

- `metric_definition_frozen_at`: commit/date when the metric definition is considered frozen.
- `evaluation_data_end`: latest data included.
- `post_freeze_observations`: observations strictly after the frozen definition date.
- `post_freeze_events`: target events strictly after the frozen definition date.

Claims based mostly on pre-freeze data must include a `researcher_degrees_of_freedom` warning. Prospective-discovery language is allowed only for evidence from post-freeze data or future runs.

## Metrics Under Evaluation

Initial primary metrics:

- `btc_risk_signal`
- `total_market_risk_signal`
- `trend_composite_score`
- `top_reversal_risk`
- `bottom_reversal_risk`
- `dca_risk`
- `attention_score`
- `headline_attention`
- `cycle_extension_score`
- `cycle_frenzy_score`
- `cycle_accumulation_score`
- `cycle_p_frenzy`
- `cycle_p_accumulation`

Secondary metric families:

- Category breakdown signals, attention, coverage, reliability, and contribution columns.
- Metric breakdown signals, attention, reliability, coverage, normalized weights, and contribution columns.
- Source and metric health fields when testing degradation and coverage.

Each test result must identify whether it evaluates a primary metric, a category-level aggregate, an individual feature bundle, or a derived strategy policy.

## Outcomes Under Evaluation

Canonical outcome families:

1. Future return over 1, 3, 6, 12, 24, 36, and 48 months.
2. Future maximum drawdown over the same horizons.
3. Future maximum rally over the same horizons.
4. Future volatility expansion.
5. Threshold top labels: future drawdown exceeds configured thresholds.
6. Threshold bottom labels: future rally exceeds configured thresholds.
7. Quantile labels: future return in top or bottom quantiles.
8. Local-extrema labels: local tops and bottoms using lookback and forward windows.
9. Practical decision outcomes: CAGR, max drawdown, Calmar-like ratio, turnover, cost drag, time in market, cash deployment, and regret versus baseline.

Important distinction:

- Academic tests ask, "Does the metric rank or calibrate future outcomes?"
- Practical tests ask, "Would a person following a simple rule have made better, robust decisions?"

## Global Evaluation Rules

Every test must follow these rules unless explicitly marked as a retrospective exploratory analysis.

1. No future data may be used to construct a decision, threshold, calibration, scaler, quantile, or regime label for a live-style result.
2. Walk-forward tests must use an embargo at least as long as the forward outcome horizon when training labels.
3. Monthly and weekly decisions must use the last value known at the decision timestamp, then execute at the next available close by default.
4. Strategy comparisons must normalize cashflow schedules. A DCA-like strategy must be compared against the same total invested cashflow.
5. All stochastic tests must use deterministic seeds and report the seed, iteration count, and sampling method.
6. All headline metrics must report sample size, effective sample size caveats, event count, coverage, and warning count.
7. Results from overlapping horizons must not be presented as independent observations.
8. Full-sample quantiles are allowed only for clearly marked retrospective diagnostics. They are not allowed in walk-forward claims.
9. Low-event, high-turnover, low-coverage, unstable, or single-regime results must be flagged before dashboard export.
10. The dashboard may summarize, but must not hide validator caveats.
11. A failed high-severity leakage or availability check blocks dashboard export for affected claims.
12. Synthetic tests can lower confidence or identify harness/behavior failures, but they cannot increase real-world confidence verdicts.
13. Candidate thresholds, policies, parameter grids, and primary endpoints must be frozen in the resolved config before each run.
14. Every headline claim must report effective sample size and cycle/event count, not only row count.

## Claim Promotion Gates

Validator verdicts must be gated before any result can become a dashboard headline.

Minimum gates for `supported`:

1. No high-severity leakage, embargo, or availability warning.
2. Result is confirmatory, not exploratory.
3. Minimum event count is met for the outcome family. Initial default: at least 8 events for short/medium horizons and at least 5 events for long-horizon cycle labels, unless the validator lowers confidence.
4. Effective sample size is adequate after overlap adjustment. Initial default: at least 30 effective observations for short/medium horizons and at least 12 for long horizons.
5. Result survives at least one structure-preserving null method.
6. Result survives family-level FDR at the configured threshold, or is explicitly marked `supported_with_caveats` instead of `supported`.
7. Recent-window performance is not catastrophically worse than full-history performance.
8. Result is not dominated by a single market regime or one event cluster.
9. Baseline comparison does not show an obvious naive feature or strategy matching the claimed advantage.
10. Practical strategy claims pass hard guardrails and do not depend on excessive turnover or unrealistic exposure.

Verdict rules:

- `supported`: all gates pass and evidence is stable.
- `supported_with_caveats`: main evidence is positive but one or more non-blocking weaknesses remain.
- `inconclusive`: direction is plausible but sample, uncertainty, or baseline evidence is too weak.
- `weak_or_unstable`: some evidence exists but fails robustness, recent, regime, or baseline checks.
- `rejected`: evidence contradicts the claim.
- `invalid_due_to_leakage`: leakage/availability failure blocks interpretation.

Evidence badges for frontend:

- `strong`: supported, confirmatory, stable, adequate sample, no major warnings.
- `moderate`: supported with caveats.
- `weak`: weak or unstable, or exploratory with interesting evidence.
- `inconclusive`: underpowered or conflicting evidence.
- `invalid`: blocked by leakage, availability, or broken assumptions.

## Phase Structure

### Phase 1: Test Design

Output:

- This document.
- Validator review notes appended to this document.
- A locked first implementation slice.

No production evaluation code should be written until this phase is reviewed.

### Phase 2: Test Implementation And Result Validation

Output:

- `risk_engine/evaluation/` package.
- Deterministic CLI runner.
- Smoke, standard, and expensive profiles.
- Local SQLite and JSON/JSONL artifacts.
- Automated validator report.
- Executed results using current repo data.
- External or subagent review of code quality and logic validity.

### Phase 3: Frontend Results Dashboard

Output:

- Compact web JSON exports.
- React views that make findings inspectable without overstating confidence.
- User-reviewed storytelling hierarchy before final copy and visual emphasis are locked.

## Recommended Architecture

Add a first-class evaluation namespace:

```text
risk_engine/evaluation/
  __init__.py
  cli.py
  config.py
  data.py
  registry.py
  schemas.py
  storage.py
  reports.py
  labels.py
  outcomes.py
  statistics.py
  bootstrap.py
  permutation.py
  walkforward.py

  testsuites/
    __init__.py
    data_audit.py
    calibration.py
    predictive_power.py
    leakage.py
    robustness.py
    strategy.py
    ablation.py
    regimes.py
    synthetic_market.py
    stability.py

  strategies/
    __init__.py
    policies.py
    baselines.py
    simulator.py
    costs.py
    guardrails.py

  generators/
    __init__.py
    bootstrap_paths.py
    brownian.py
    regime_switching.py
    bubble_crash.py

  validators/
    __init__.py
    assumptions.py
    leakage.py
    statistical_power.py
    result_sanity.py
    storytelling.py
```

Keep `risk_engine/benchmark.py` as the production benchmark used by the current pipeline. The new package is the research-grade evaluation harness. Shared primitives can be moved later only if duplication becomes genuinely painful.

## Storage Decision

Use local SQLite plus static artifacts by default.

Do not add Convex in Phase 2 unless we discover a real need for hosted collaborative querying or live dashboard state. The likely best fit is:

- SQLite for queryable local run history.
- JSONL/CSV for easy review and diffs.
- Compact JSON exports for the frontend.

Primary store:

```text
artifacts/evaluation/evaluation.sqlite
```

Run folder:

```text
artifacts/evaluation/runs/{run_id}/
  manifest.json
  config.resolved.json
  data_fingerprint.json
  summary.json
  results.jsonl
  warnings.jsonl
  assumptions.md
  validation_report.md
  tables/
    metric_validity.csv
    calibration_bins.csv
    bootstrap_intervals.csv
    permutation_nulls.csv
    walkforward_results.csv
    strategy_results.csv
    strategy_trades.csv
    strategy_equity_curves.csv
    robustness_results.csv
    ablation_results.csv
    regime_results.csv
    synthetic_results.csv
```

Frontend export:

```text
data/web/v2/evaluation_summary.json
data/web/v2/evaluation_metric_matrix.json
data/web/v2/evaluation_strategy_results.json
data/web/v2/evaluation_robustness.json
data/web/v2/evaluation_regimes.json
data/web/v2/evaluation_warnings.json
```

## CLI Profiles

Initial commands:

```bash
python -m risk_engine.evaluation.cli list-tests
python -m risk_engine.evaluation.cli run --profile smoke
python -m risk_engine.evaluation.cli run --profile standard
python -m risk_engine.evaluation.cli run --profile expensive
python -m risk_engine.evaluation.cli validate --run latest
python -m risk_engine.evaluation.cli export-web --run latest
python -m risk_engine.evaluation.cli compare --left RUN_A --right RUN_B
```

Profiles:

- `smoke`: deterministic, quick, CI-safe, small bootstrap/permutation counts, no network, no paid data.
- `standard`: full historical tests, practical strategies, ablations, robustness scenarios, moderate uncertainty estimation.
- `expensive`: deeper bootstrap/permutation, synthetic path ensembles, label sensitivity sweeps, richer counterfactuals.
- `dashboard`: read latest validated run and export compact frontend JSON.

## Configuration

Add:

```text
config/evaluation.default.json
config/evaluation.local.json.example
```

Draft default:

```json
{
  "run_profile": "standard",
  "start_date": "2012-01-01",
  "frequency": "monthly",
  "decision_frequencies": ["monthly", "weekly"],
  "primary_decision_frequency": "monthly",
  "metrics": [
    "btc_risk_signal",
    "top_reversal_risk",
    "bottom_reversal_risk",
    "dca_risk",
    "trend_composite_score",
    "attention_score",
    "headline_attention",
    "cycle_extension_score"
  ],
  "targets": ["btc"],
  "horizons_months": [1, 3, 6, 12, 24, 36, 48],
  "seeds": [7, 19, 43],
  "bootstrap": {
    "smoke_iterations": 100,
    "standard_iterations": 500,
    "expensive_iterations": 2000,
    "block_sizes_months": [1, 3, 6, 12]
  },
  "permutation": {
    "smoke_iterations": 100,
    "standard_iterations": 500,
    "expensive_iterations": 2000
  },
  "strategy": {
    "execution_lag_days": 1,
    "cost_bps": [0, 10, 25, 50, 100],
    "default_cost_bps": 25,
    "allow_leverage": false,
    "allow_shorting": false,
    "max_turnover_per_year": 6.0,
    "max_trades_per_year": 12,
    "max_allocation_change_per_period": 0.50,
    "min_coverage_for_trade": 0.60
  },
  "claim_gates": {
    "min_short_horizon_events": 8,
    "min_long_horizon_events": 5,
    "min_short_horizon_effective_observations": 30,
    "min_long_horizon_effective_observations": 12,
    "fdr_threshold": 0.10
  },
  "storage": {
    "backend": "sqlite",
    "path": "artifacts/evaluation/evaluation.sqlite"
  }
}
```

## Test Families

### A. Data Integrity And Temporal Validity

Purpose: catch silent data problems before evaluating metric quality.

Tests:

- `data.timestamp_contract`: parse dates, monotonicity, duplicates, gaps, row count, start/end.
- `data.availability_calendar`: first valid date, last valid date, coverage ratio for every metric and source.
- `data.source_revision_risk`: record source mode, file hash, and whether the source may be revised or backfilled.
- `data.metric_coverage_by_period`: coverage by year, cycle period, and recent window.

Artifacts:

- `data_fingerprint.json`
- `tables/data_audit.csv`
- `tables/availability_calendar.csv`
- `tables/source_schema_audit.csv`
- `tables/source_latency_assumptions.csv`

System-wide risks addressed:

- Data poisoning, silent source changes, partial history comparisons, missing older regimes, duplicate timestamps.

Limitations:

- These tests cannot prove historical source values match what was available live at the time.

Priority: P0.

### B. Label And Outcome Audit

Purpose: ensure target labels are not silently driving misleading conclusions.

Tests:

- `labels.threshold_audit`: event counts and event rates for future drawdown/rally labels.
- `labels.quantile_audit`: quantile cutoffs, event balance, and full-sample-warning status.
- `labels.local_extrema_audit`: local top/bottom density, clustering, overlap, and lookback/forward sensitivity.
- `labels.overlap_audit`: overlap between top and bottom labels and between adjacent horizons.
- `labels.event_clustering`: median event gap and maximum event cluster length.
- `labels.target_validity`: whether each label represents a plausible real decision problem for the metric being evaluated.

Artifacts:

- `tables/label_audit.csv`
- `tables/outcome_audit.csv`

System-wide risks addressed:

- Hindsight extrema, arbitrary thresholds, event scarcity, pseudo-replication from overlapping horizons.

Limitations:

- Top and bottom labels are proxy definitions, not natural ground truth.
- Calendar-era labels or hindsight extrema cannot drive headline claims unless a live-causal equivalent also supports the conclusion.

Priority: P0.

### C. Leakage And Causality Probes

Purpose: detect accidental future information in metrics, labels, calibration, resampling, or strategy execution.

Tests:

- `leakage.shift_probe`: evaluate metric shifted by -90, -30, -7, -1, 0, +1, +7, +30, +90 days against outcomes.
- `leakage.embargo_audit`: assert walk-forward training labels resolve before prediction date.
- `leakage.full_sample_quantile_detector`: flag full-sample quantiles used in live-style claims.
- `leakage.sentinel_features`: verify known leak features dominate, random noise stays near chance, and lagged noise behaves as expected.
- `leakage.resampling_guard`: assert weekly/monthly decision rows use only prior or same-date metric values.
- `leakage.feature_lineage`: record raw columns, transforms, joins, forward-fill rules, resampling rules, and availability assumptions for every evaluated series.

Artifacts:

- `tables/leakage_shift_probe.csv`
- `tables/leakage_sentinels.csv`
- `tables/embargo_audit.csv`
- `tables/feature_lineage.csv`

System-wide risks addressed:

- Lookahead leakage, target leakage, future-filled resampling, full-history calibration, broken test harness.

Limitations:

- Autocorrelation can make shifts look similar. This is a warning system, not an automatic proof.

Priority: P0.

### D. Calibration And Monotonicity

Purpose: determine whether metric levels have interpretable relationships with future outcomes.

Tests:

- `calibration.reliability_bins`: bin scores into quintiles/deciles and compute event rate, forward return, drawdown, rally, count, and bootstrap interval.
- `calibration.monotonicity`: Spearman between bin midpoint and outcome, adjacent inversion count, and weighted inversion magnitude.
- `calibration.extreme_buckets`: top/bottom 5% and 10% score buckets with event rate and forward outcomes.
- `calibration.raw_ece`: expected calibration error when a score is interpreted as a probability.
- `calibration.walkforward_isotonic_ece`: optional P1/P2 isotonic calibration trained only on past data.

Rules:

- Raw ECE can produce probability-language claims only for `probability_like` metrics.
- For `ordinal`, `index`, and `policy_signal` metrics, calibration outputs must be framed as monotonicity, ranking, or policy usefulness unless a separate probability calibration is trained and validated walk-forward.

Artifacts:

- `tables/calibration_bins.csv`
- `tables/extreme_bucket_results.csv`
- `tables/monotonicity_scores.csv`

System-wide risks addressed:

- Eye-test calibration, non-monotonic metrics, overconfident probability interpretation, single-cycle extremes.

Limitations:

- Some metrics are ordinal or percentile-like rather than true probabilities. Raw ECE should be interpreted cautiously.

Priority: P0 for bins, monotonicity, and extremes. P1 for isotonic ECE.

### E. Predictive Power

Purpose: measure whether metrics rank future outcomes better than chance and simple baselines.

Tests:

- `predictive.auc_pr_by_label`: AUC and PR-AUC by metric, label, horizon, side, and window.
- `predictive.rank_correlation`: Spearman/Kendall correlation with future return, max drawdown, max rally, and volatility.
- `predictive.baseline_comparison`: compare against price percentile, drawdown from ATH, trailing return, moving-average distance, realized volatility, and simple calendar heuristics.
- `predictive.incremental_value`: P1 walk-forward baseline model versus baseline plus metric.

Rules:

- Confirmatory and exploratory results must be emitted separately.
- Baseline comparisons must be horizon-matched and availability-matched.
- A metric cannot claim unique predictive power if a simpler same-availability baseline matches it within uncertainty.

Artifacts:

- `tables/predictive_by_label.csv`
- `tables/predictive_continuous_outcomes.csv`
- `tables/baseline_comparison.csv`
- `tables/incremental_value.csv`
- `tables/confirmatory_results.csv`
- `tables/exploratory_results.csv`

System-wide risks addressed:

- Lucky ranking, base-rate-sensitive PR-AUC, obvious price-cycle baseline masquerading as proprietary skill.

Limitations:

- Predictive ranking does not automatically imply practical strategy usefulness.

Priority: P0 for AUC/PR-AUC and rank correlation. P1 for incremental models.

### F. Uncertainty, Nulls, And Multiple Testing

Purpose: prevent overclaiming based on one noisy historical path.

Tests:

- `uncertainty.block_bootstrap`: confidence intervals for AUC, PR-AUC, Spearman, calibration-bin event rates, and strategy deltas.
- `uncertainty.permutation_null`: circular shifts, block permutations, within-regime permutations, and rank shuffles.
- `uncertainty.fdr_correction`: Benjamini-Hochberg q-values by family and global suite.
- `uncertainty.effective_sample_warning`: warn when overlapping horizons or clustered events make nominal sample size misleading.
- `uncertainty.cycle_count`: report approximate number of independent cycle/event clusters supporting each result.

Effective sample size:

- Initial implementation may use a conservative heuristic: divide nominal observations by the maximum of 1, horizon months, and event cluster size where applicable.
- Long-horizon BTC results cannot receive a `strong` evidence badge solely from many overlapping monthly rows.
- Cycle/event-cluster count must be displayed beside observation count for long-horizon claims.

Artifacts:

- `tables/bootstrap_intervals.csv`
- `tables/permutation_nulls.csv`
- `tables/fdr_results.csv`
- `tables/effective_sample_size.csv`

System-wide risks addressed:

- False discoveries, pseudo-precision, autocorrelation, multiple comparisons, lucky metric/horizon winners.

Limitations:

- Block bootstrap is still imperfect in regime-changing markets.

Priority: P0.

### G. Walk-Forward And Time Stability

Purpose: test whether skill would have been knowable at the time and whether it decays.

Tests:

- `walkforward.expanding_evaluation`: train thresholds/calibrators on past data, embargo unresolved labels, test next period.
- `walkforward.rolling_windows`: evaluate 3-year, 5-year, and 8-year rolling windows.
- `walkforward.performance_decay`: compare full history, first half, second half, recent 3 years, recent 5 years.
- `walkforward.hyperparameter_audit`: P1/P2 audit of selected parameters, train score, test score, and optimism gap.

Rules:

- `frozen_fixed_rule_walkforward` uses predeclared thresholds and policies only.
- `walkforward_optimized` may choose among a small frozen candidate library, but must report candidate count, selected parameters, train score, test score, and optimism gap.
- The resolved config must snapshot every threshold, policy, and parameter candidate before the run starts.

Artifacts:

- `tables/walkforward_results.csv`
- `tables/rolling_window_results.csv`
- `tables/performance_decay.csv`
- `tables/hyperparameter_audit.csv`

System-wide risks addressed:

- Hindsight tuning, concept drift, regime decay, too many candidate thresholds.

Limitations:

- Bitcoin has few truly independent cycles. Long-horizon walk-forward results will often be underpowered.

Priority: P0 for expanding evaluation and performance decay. P1 for rolling windows and hyperparameter audit.

### H. Practical Strategy And Autopilot Tests

Purpose: evaluate whether metrics help with simple real-world low-frequency decisions.

Default execution:

- Monthly primary, weekly secondary.
- Signal observed at decision close.
- Execution at next available close.
- No leverage.
- No shorting.
- Default practical transaction cost: 25 bps.
- Report sensitivity at 0, 10, 25, 50, and 100 bps.

Policies:

- Buy and hold.
- Weekly DCA.
- Monthly DCA.
- Calendar DCA: Monday, first day of month, last day of month.
- Randomized same-cashflow timing baseline.
- Naive momentum baseline: 200d trend.
- Naive drawdown baseline: buy more below ATH.
- Volatility baseline: reduce exposure when realized volatility is high.
- Risk-weighted DCA: invest more when risk is low, less when risk is high.
- Allocation bands: BTC exposure decreases as risk rises.
- Hysteresis allocation bands: reduce churn.
- Conservative autopilot: buy more on low risk, never sell existing BTC.
- Sell-pressure rule: reduce only when high risk persists.

Artifacts:

- `tables/decision_audit_monthly.csv`
- `tables/decision_audit_weekly.csv`
- `tables/strategy_results.csv`
- `tables/strategy_trades.csv`
- `tables/strategy_equity_curves.csv`
- `tables/random_timing_baseline.csv`

Required KPIs:

- Total return.
- CAGR.
- Max drawdown.
- Volatility.
- Sharpe-like ratio.
- Sortino-like ratio.
- Calmar-like ratio.
- Time in market.
- Trade count.
- Turnover.
- Transaction cost drag.
- Worst 1-month, 3-month, and 12-month periods.
- Delta versus fair baseline.
- Percentile versus randomized timing baseline.
- Average BTC exposure.
- BTC beta or beta-like exposure proxy.
- Cash utilization.
- Return sacrificed per drawdown reduction.
- Exposure-adjusted return and drawdown comparisons where feasible.

Rules:

- Separate lump-sum allocation strategies from cashflow/DCA strategies.
- DCA-like policies compare primarily to same-cashflow DCA.
- Allocation policies compare primarily to buy-and-hold, cash/BTC rebalance, and exposure-aware baselines.

System-wide risks addressed:

- Strategy overfitting, unfair baselines, impractical churn, high cost sensitivity, eye-test usefulness without actual decision value.

Limitations:

- Taxes, liquidity, exchange risk, spreads beyond simple costs, and behavioral discipline are not modeled in the first version.

Priority: P0 for no-lookahead, simulator, DCA, buy-and-hold, costs, and fair baselines. P1 for walk-forward strategy selection.

### I. Degraded Data And Operational Robustness

Purpose: measure whether metrics survive real-world data outages, stale sources, partial coverage, and noisy inputs.

Scenarios:

- Random missing metric values.
- Block outage of 7, 30, and 90 days.
- One source unavailable.
- One category unavailable.
- On-chain metrics delayed by 1, 3, and 7 days.
- Social/sentiment metrics stale by 7, 14, and 30 days.
- Source returns a constant repeated value.
- Source resumes after outage.
- Price available but auxiliary sources missing.
- Regime-correlated outage: source fails during high-volatility or high-attention periods.
- Source-correlated outage: one source family fails while related signals remain available.
- Stale-but-plausible bad data: old values continue to update timestamps or remain within plausible ranges.

Artifacts:

- `tables/degraded_source_summary.csv`
- `tables/degraded_decision_diff.csv`
- `tables/coverage_sensitivity.csv`

Required fields:

- Scenario.
- Missing source/category/metric.
- Missing fraction.
- Max gap days.
- Score MAE versus clean.
- Decision change rate.
- Allocation change rate.
- Return delta versus clean.
- Drawdown delta versus clean.
- Coverage delta.
- Confidence delta.
- Fallback used.
- Missingness mechanism: random, block, regime-correlated, source-correlated, adversarial, or stale-plausible.

Rules:

- Confidence and/or coverage should decline when important inputs degrade. If a score stays confident through missing or stale data, emit a warning.

System-wide risks addressed:

- Silent confidence, future-filling, data poisoning, operational brittleness, robustness through ignored missingness.

Limitations:

- Synthetic outages may not perfectly match real outage mechanisms.

Priority: P0.

### J. Guardrails And Weird Recommendation Tests

Purpose: detect strategies that are statistically interesting but practically strange or unsafe.

Guardrails:

- No leverage by default.
- No shorting by default.
- No negative cash.
- No negative BTC.
- Max annual turnover.
- Max trades per year.
- Max allocation change per period.
- Min coverage for trade.
- Max consecutive cash periods warning.
- Flag large allocation changes from tiny score changes.
- Flag trading during low-coverage or stale-source periods.
- Flag single fragile source dominance.
- Emit `hard_violation`, `soft_warning`, and `human_review_required` levels.

Artifacts:

- `tables/strategy_guardrails.csv`
- `warnings.jsonl`

System-wide risks addressed:

- Technically profitable but unusable policies, fragile source dependence, hidden leverage, churn, trading on stale data.

Limitations:

- Guardrails are partly judgment calls. They should warn, not automatically erase evidence.

Priority: P0.

### K. Regime-Specific Strengths And Weaknesses

Purpose: answer "when is each metric strongest?"

Predeclared regime families:

- Calendar eras: pre-2017, 2017 mania/crash, 2018-2019 bear/recovery, 2020-2021 liquidity boom, 2022 tightening/crash, 2023-2026 ETF/macro era.
- Trend regimes: above/below 200d moving average, trailing return positive/negative.
- Volatility regimes: high/medium/low realized volatility using expanding thresholds.
- Drawdown regimes: near ATH, moderate drawdown, deep drawdown.
- Liquidity/macro regimes where data coverage is adequate.
- Cycle model regimes already produced by the pipeline.

Rules:

- Live-style regime labels must use only information available at the time.
- Handpicked calendar eras are allowed only as descriptive retrospective slices.
- Low-sample regimes must be flagged and should not feed headline rankings.
- Outputs must split `live_causal_regimes` from `retrospective_slices`.
- Retrospective slices cannot drive "strongest metric" claims by themselves.
- Multiple-testing correction must be applied within regime analysis.

Artifacts:

- `tables/regime_results.csv`
- `tables/metric_strengths_weaknesses.csv`
- `tables/live_causal_regimes.csv`
- `tables/retrospective_slices.csv`

System-wide risks addressed:

- Single-regime skill, concept drift, hindsight storytelling, overgeneralizing from one cycle.

Limitations:

- Regime definitions can encode assumptions. The dashboard must show definitions and confidence flags.

Priority: P1.

### L. Ablation, Redundancy, And Contribution

Purpose: learn whether performance comes from broad robust composition or one fragile component.

Tests:

- `ablation.full_reference`: full model reference.
- `ablation.drop_one_metric`: approximate or recompute without each metric where feasible.
- `ablation.drop_one_category`: category removal.
- `ablation.category_only`: price-only, on-chain-only, social-only, sentiment-only, cycle-only, total-market-only.
- `ablation.equal_weight`: compare existing category weights to equal category weights.
- `redundancy.correlation_matrix`: Pearson/Spearman/rolling correlations among metrics.
- `redundancy.residual_skill`: residual metric skill after controlling for price percentile, drawdown, returns, and volatility.
- `dominance.single_metric_warning`: flag if headline performance depends heavily on one fragile component.

Rules:

- Every ablation result must include `ablation_method`: `recomputed`, `approximate`, or `diagnostic_only`.
- Approximate ablations cannot support strong contribution claims.
- Collinearity warnings must be emitted when drop-one interpretation is unreliable.

Artifacts:

- `tables/ablation_results.csv`
- `tables/redundancy_matrix.csv`
- `tables/residual_skill.csv`

System-wide risks addressed:

- False ensemble confidence, duplicated price momentum, fragile single-source dominance.

Limitations:

- Leave-one-out recomputation may be expensive. Approximate contribution tests must be labeled as approximate.

Priority: P1 for correlation and category tests. P2 for full recomputation.

### M. Synthetic And Counterfactual Tests

Purpose: validate behavior and test harness sanity in controlled worlds.

Synthetic models:

- GBM null: drift and volatility but no true cycle signal.
- Regime-switching GBM: known hidden states controlling return distribution.
- Bubble-crash model: accumulation, acceleration, blow-off, crash, recovery.
- Historical block bootstrap: recombine real return blocks.
- Adversarial scenarios: forever-rising high-volatility market, sideways chop, false breakouts, sudden exogenous crash, slow grind-down bear, sudden V-bottom.

Injected synthetic metrics:

- Perfect state metric.
- Noisy state metric.
- Lagged state metric.
- Inverted state metric.
- Random metric.
- Price-only heuristic metric.

Expected harness behavior:

- Perfect and noisy metrics rank well.
- Lagged metrics degrade.
- Inverted metrics fail or reverse.
- Random metrics stay near chance after multiple-testing controls.
- GBM null should not produce persistent significant skill.

Rules:

- Synthetic tests cannot increase real-world confidence verdicts.
- Synthetic dashboard views must be labeled controlled scenario diagnostics.
- Generator parameters and seeds must be recorded in artifacts.

Artifacts:

- `tables/synthetic_results.csv`
- `tables/counterfactual_behavior.csv`

System-wide risks addressed:

- Broken evaluation harness, uncalibrated false positive rate, policies that behave strangely in controlled scenarios.

Limitations:

- Synthetic data tests the assumptions of the generator. It cannot validate real predictive power.

Priority: P0 for small harness-validation synthetic tests. P1/P2 for richer counterfactual worlds.

### N. Failure Case And Interpretability Reports

Purpose: make failures inspectable instead of hiding them in averages.

Cases:

- Best periods.
- Worst periods.
- False positives.
- False negatives.
- Early signals.
- Late signals.
- Underperformance versus DCA.
- Drawdown improved but return suffered.
- Good return but impractical churn.
- Low-coverage decisions.
- Representative randomly selected cases for comparison against extreme cases.

Rules:

- Case selection rules must be frozen before the run.
- Failure cases must link to aggregate evidence and validator warnings.
- Anecdotes cannot override aggregate evidence.

Artifacts:

- `tables/failure_cases.csv`
- `tables/metric_strengths_weaknesses.csv`

Required fields:

- Metric.
- Period start/end.
- Case type.
- Score at decision.
- Coverage.
- Future returns at 1, 3, 6, 12 months.
- Future max drawdown/rally.
- Strategy decision.
- Baseline decision.
- Outcome.
- Explanation fields from metric/category breakdowns.
- Warning flags.

System-wide risks addressed:

- Post-hoc storytelling, hiding bad cases, uninspectable averages.

Limitations:

- Failure cases are examples. They should support, not replace, aggregate evidence.

Priority: P1.

## Automated Result Validator

Every completed run must produce `validation_report.md` and structured warnings in `warnings.jsonl`.

Validator checks:

1. Is there any leakage suspicion from shift probes, embargo audit, or full-sample quantile detector?
2. Is sample size adequate for the claim?
3. Is event count adequate for the label/horizon?
4. Are forward horizons overlapping enough to reduce effective confidence?
5. Does the result survive block bootstrap uncertainty?
6. Does the result beat permutation nulls?
7. Does the result survive FDR correction within its family?
8. Does the result hold in recent data?
9. Does it hold across more than one label definition or outcome?
10. Does a naive baseline match or beat it?
11. Is performance concentrated in one calendar era or market regime?
12. Is the metric mostly redundant with price percentile, drawdown, or momentum?
13. Are missing data or stale source scenarios damaging the result?
14. Is the practical strategy high-turnover, high-cost, or guardrail-violating?
15. Is the claim contradicted by synthetic harness tests?
16. Is the frontend wording proportional to the evidence?
17. Was the metric definition frozen before the evaluated data window?
18. Is live availability known, estimated, or unknown?
19. Are confirmatory and exploratory outputs separated?
20. Does the proposed evidence badge match the claim gates?

Validator verdicts:

- `supported`
- `supported_with_caveats`
- `inconclusive`
- `weak_or_unstable`
- `rejected`
- `invalid_due_to_leakage`

Example validator output:

```json
{
  "metric": "top_reversal_risk",
  "claim": "Ranks future drawdown risk over 12-36 month horizons",
  "verdict": "supported_with_caveats",
  "confidence": "medium",
  "evidence_badge": "moderate",
  "major_risks": [
    "Long-horizon labels overlap heavily",
    "Recent-window event count is low",
    "Skill is concentrated around one cycle top"
  ],
  "frontend_language": "Historically strongest around major cycle-top risk, with lower confidence in recent regimes."
}
```

## External Review Requirement

Two reviews are required before Phase 3 dashboard work:

1. Plan validator review after Phase 1 draft.
2. Implementation/results validator review after Phase 2 execution.

Both reviews should focus more on logic validity than code style:

- Bad assumptions.
- Silent biases.
- Leakage.
- Concept drift.
- Data poisoning.
- Overfitting.
- Multiple testing.
- Overconfident result interpretation.

## Implementation Order

### Phase 2 Milestone 1: Boring Durable Harness

1. Add `risk_engine/evaluation/schemas.py`, `config.py`, `storage.py`, `data.py`, and `cli.py`.
2. Create run folders, run manifests, config snapshots, data fingerprints, and SQLite tables.
3. Implement `list-tests`, `run --profile smoke`, `validate --run latest`.
4. Write unit tests for schemas, storage, fingerprinting, and deterministic run IDs/config hashes.

Exit criteria:

- A smoke run creates a complete run folder and SQLite rows.
- The validator can read a run and produce a report.

### Phase 2 Milestone 2: Academic Smoke Suite

1. Data integrity audit.
2. Label audit.
3. Leakage shift probe.
4. Reliability bins.
5. Monotonicity.
6. AUC/PR-AUC and Spearman with small bootstrap/permutation counts.
7. FDR correction.
8. Synthetic sentinel harness with perfect/noisy/inverted/random metrics.

Exit criteria:

- For each primary metric, the run answers what it appears to predict, whether the relationship is monotonic, whether it survives null tests, and what caveats apply.

### Phase 2 Milestone 3: Practical Usability Suite

1. No-lookahead decision calendar.
2. Strategy simulator.
3. Buy-and-hold, DCA, calendar, random timing, momentum, drawdown, and volatility baselines.
4. Risk-weighted DCA, allocation bands, hysteresis, conservative autopilot, and sell-pressure policies.
5. Transaction cost grid.
6. Guardrails.

Exit criteria:

- Each primary metric has practical strategy results, fair baseline deltas, transaction cost sensitivity, and guardrail warnings.

### Phase 2 Milestone 4: Robustness And Strength Mapping

1. Degraded data scenarios.
2. Walk-forward evaluation with embargo.
3. Rolling windows and performance decay.
4. Regime-specific results.
5. Ablation and redundancy.
6. Failure cases.

Exit criteria:

- For each metric, the suite identifies where it is strongest, weakest, fragile, redundant, or operationally unreliable.

### Phase 2 Milestone 5: Run Full Evaluation And Validate Results

1. Run standard profile.
2. Run expensive profile only where added value is clear.
3. Generate validation report.
4. Spawn independent validator/external review.
5. Update this document with result interpretation rules discovered during implementation.

Exit criteria:

- Results are validated enough to discuss dashboard design without inventing the story prematurely.

### Phase 3: Frontend Dashboard

Design principles:

1. Lead with evidence quality, not just performance rank.
2. Group results by question:
   - What does each metric predict?
   - When is each metric strongest?
   - How useful is it in simple decisions?
   - How robust is it to missing data and regime changes?
   - What are the biggest caveats?
3. Use heatmaps for metric x test matrices.
4. Use calibration curves or binned bars for score meaning.
5. Use equity curves sparingly and always beside drawdown/cost/turnover.
6. Use tables for validator warnings and sample sizes.
7. Use small multiples for regime windows and rolling stability.
8. Avoid leaderboard-only storytelling.
9. Require user review before final headline copy and visual hierarchy are locked.
10. Every headline claim must link to sample size, event count, uncertainty, and warnings.
11. Show where a metric failed near where it worked.
12. Validator warnings must be first-class display data, not hidden only in footnotes.
13. Avoid "strongest metric" language unless confirmatory claim gates pass.

Candidate frontend artifacts:

- `evaluation_summary.json`: top-level validated claims, caveats, run metadata.
- `evaluation_metric_matrix.json`: metric x test heatmap values and confidence flags.
- `evaluation_strategy_results.json`: practical strategy KPIs and baseline comparisons.
- `evaluation_robustness.json`: degraded source and null-test results.
- `evaluation_regimes.json`: regime-specific strengths and weaknesses.
- `evaluation_warnings.json`: validator warnings and display guidance.

Evidence badge schema:

```json
{
  "claim_id": "top_reversal_risk_future_drawdown_12m",
  "badge": "moderate",
  "verdict": "supported_with_caveats",
  "metric": "top_reversal_risk",
  "claim": "Ranks future drawdown risk over 12 months",
  "sample_size": 120,
  "effective_sample_size": 24,
  "event_count": 9,
  "cycle_count": 3,
  "uncertainty_summary": "Bootstrap interval excludes chance in the standard run",
  "warning_count": 2,
  "major_warnings": ["researcher_degrees_of_freedom", "limited_cycle_count"]
}
```

## Open Decisions

These should be confirmed before Phase 2 implementation:

1. Primary practical cadence: recommendation is monthly primary, weekly secondary.
2. Execution timing: recommendation is signal at close, execution at next available close.
3. Default practical cost: recommendation is 25 bps, with 0/10/25/50/100 bps sensitivity.
4. Database: recommendation is SQLite/local artifacts, not Convex for Phase 2.
5. First primary metrics: recommendation is the initial primary list in this document.
6. Expensive run budget: recommendation is standard first, then selectively expensive.
7. Exact initial guardrail thresholds: draft defaults are in the config section and should be adjusted after first smoke runs.
8. Metric definition freeze date: should be set to the commit/date when Phase 2 begins unless a more precise historical freeze point is chosen.

## Phase 1 Validator Review Notes

An independent validator reviewed the first draft and gave the plan an overall verdict of strong but not implementation-locked. The required clarifications have been incorporated above.

Validator-critical additions:

1. Explicit live availability and source latency assumptions.
2. Confirmatory versus exploratory result separation.
3. Hard claim promotion gates and frontend evidence badges.
4. Metric semantic types.
5. Effective sample size and cycle-count reporting.
6. Frozen policy, threshold, and parameter candidate sets.
7. Synthetic-test rule: synthetic tests cannot increase real-world confidence.
8. Researcher degrees-of-freedom and post-freeze warning class.
9. Failure-case selection rules and representative cases.

Remaining Phase 2 caution:

- Implementation should treat these as schema and validator requirements, not optional commentary. If a result cannot supply the required metadata, it should be downgraded or blocked from headline display.

## Current Recommendation

Start Phase 2 with the boring durable harness and a narrow smoke suite. The fastest path to trustworthy insight is not the fanciest test; it is a reproducible run folder, data fingerprint, deterministic artifacts, and a validator that refuses to let weak evidence become strong claims.

## Phase 2 Implementation Log

### 2026-06-21: Milestone 1 Harness Slice

Implemented:

1. `risk_engine/evaluation/` package with schemas, config, data fingerprinting, storage, checks, runner, and CLI.
2. `evaluate_metrics.py` top-level entry point.
3. Local SQLite index at `output/evaluation/evaluation.sqlite`.
4. Per-run artifact folders under `output/evaluation/runs/<run_id>/`.
5. Smoke profile tests:
   - `data.series_integrity`
   - `temporal.live_availability`
   - `academic.existing_benchmark_snapshot`
   - `validator.claim_gates`
6. Deterministic unit coverage in `tests/test_evaluation_harness.py`.
7. Real local smoke run:
   - Run ID: `phase2-smoke-local`
   - Profile: `smoke`
   - Status: `pass`
   - Run directory: `output/evaluation/runs/phase2-smoke-local`
   - Warning: `phase2_harness_only`

Current limitations:

1. This slice validates the harness and artifact contract only. It does not promote any metric-strength claims.
2. `temporal.live_availability` currently warns because the risk series does not yet expose full `available_at_date` metadata. Live-style dashboard claims must remain downgraded until source latency is explicit.
3. Existing benchmark artifacts are wrapped as a snapshot. Full-sample quantiles and same-window F1 thresholds remain retrospective diagnostics unless replaced by walk-forward versions in later milestones.
4. Claim gates currently block high-severity structural failures and add a harness-only warning. Later milestones must add event-count, effective-sample-size, FDR/null, regime-concentration, and baseline-comparison gates before any headline claim is allowed.

Next implementation slice:

1. Add explicit availability metadata/source-latency audit helpers.
2. Add confirmatory/exploratory result tagging to all result rows.
3. Add walk-forward label/threshold variants that do not reuse full-sample quantiles for live-style claims.
4. Add validator gates for event counts, effective sample size, and low recent-window stability.

### 2026-06-21: Milestone 1B Metadata And Initial Claim Gates

Implemented:

1. Availability rules in evaluation config, including latency assumptions, confidence, trust tier, and processing state.
2. `tables/availability_calendar.csv` artifact built from `source_health`, `metric_health`, `source_modes`, and availability rules.
3. Result-level `result_type` and `claim_scope` fields so artifacts distinguish structural diagnostics, exploratory snapshots, and claim-readiness checks.
4. `data.availability_calendar` test for availability-calendar completeness.
5. `temporal.source_availability_metadata` test for source-health/source-mode readiness.
6. `validator.benchmark_claim_gate_readiness` test using existing benchmark rows:
   - event-count gates
   - overlap-adjusted effective observation gates
   - benchmark aggregate eligibility
   - signal-level aggregate support from `benchmark_by_signal`
7. Explicit warnings that current quantile labels and same-window best-F1 thresholds remain retrospective/exploratory.

Current interpretation:

1. The suite can now say whether existing benchmark rows are even sample-ready for future claims.
2. Passing these gates is necessary but not sufficient. It still does not mean a metric is supported.
3. Null tests, FDR, regime concentration, baseline dominance, live availability, and walk-forward thresholding remain unimplemented gates.
4. Existing benchmark outputs remain retrospective diagnostics until walk-forward label and threshold variants are added.

### 2026-06-21: Milestone 2A Walk-Forward Benchmark Sidecar

Implemented:

1. `risk_engine/evaluation/walkforward.py` with an expanding walk-forward benchmark sidecar.
2. Fixed threshold labels for drawdown/rally outcomes.
3. Expanding, embargoed quantile labels:
   - Quantile cuts are fit only on already resolved historical forward returns.
   - Embargo equals the outcome horizon.
   - Full-sample quantile cuts are not used in this sidecar.
4. Expanding score-quantile alert thresholds:
   - Alert thresholds are fit only on prior scores.
   - Same-window best-F1 threshold selection is not used in this sidecar.
5. Per-run artifacts:
   - `tables/walkforward_by_label.csv`
   - `tables/walkforward_by_signal.csv`
6. Evaluation test:
   - `walkforward.expanding_benchmark`
7. Unit coverage for:
   - Expanding quantile cuts ignoring unresolved future regimes.
   - Walk-forward method/audit columns.
   - Evaluation manifest/artifact integration.

Real smoke run:

- Run ID: `phase2-smoke-walkforward`
- Status: `pass`
- Walk-forward label rows: 104
- Walk-forward signal rows: 13
- Test status: `walkforward.expanding_benchmark:pass`

Current interpretation:

1. The project now has a causal benchmark sidecar, separate from the existing retrospective benchmark.
2. The sidecar is not yet a complete academic validation layer. It still needs fold-level audit tables, null/permutation tests, FDR, regime concentration checks, and baseline dominance checks.
3. Dashboard headline claims remain blocked by `phase2_harness_only` until those additional gates exist.
4. Existing benchmark warnings now distinguish retrospective artifacts from the new walk-forward sidecar.

### 2026-06-21: Milestone 2B Fold Audit Robustness

Implemented:

1. Row-level walk-forward fold audit artifact:
   - `tables/walkforward_by_fold.csv`
2. Compact embargo/leakage audit artifact:
   - `tables/walkforward_embargo_audit.csv`
3. Audit fields include:
   - `decision_date`
   - `score_date`
   - `outcome_start_date`
   - `outcome_end_date`
   - `outcome_resolved_at_date`
   - `label_train_end`
   - `score_train_end`
   - `embargo_months`
   - `selected_alert_threshold`
   - `train_label_count`
   - `train_score_count`
   - `uses_full_sample_quantile`
   - `uses_same_window_threshold_selection`
   - `embargo_boundary_ok`
4. Validator checks now block if:
   - Fold audit columns are missing.
   - Embargo boundary checks fail.
   - Label training uses unresolved outcomes.
   - Score thresholds use non-prior scores.
   - Walk-forward rows contain retrospective quantile labels.
5. Unit coverage for:
   - Persisted fold audit artifacts.
   - Exact embargo boundary on expanding quantile labels.
   - Insufficient-history behavior.
   - Leakage/audit booleans.

Real smoke run:

- Run ID: `phase2-smoke-fold-audit`
- Status: `pass`
- Fold rows: 15,496
- Embargo audit rows: 15,496
- Label leakage failures: 0
- Threshold leakage failures: 0
- Embargo failures: 0

Current interpretation:

1. The walk-forward sidecar is now inspectable, not merely causal by implementation.
2. Early rows may have unavailable alert thresholds until min-history is reached; this is tracked separately and is not leakage.
3. Next robustness layer should add structure-preserving null/baseline tests and then FDR/regime-concentration gates.

### 2026-06-21: Milestone 2C Structure-Preserving Nulls And Random Baselines

Implemented:

1. Deterministic circular-shift nulls for walk-forward fold rows.
2. Seeded random-uniform baseline scores for each walk-forward signal/label row.
3. Robustness artifacts:
   - `tables/walkforward_nulls.csv`
   - `tables/walkforward_baselines.csv`
4. Enriched `tables/walkforward_by_label.csv` with:
   - `null_method`
   - `null_iterations`
   - `auc_null_mean`
   - `auc_null_p95`
   - `auc_empirical_p_right`
   - `pr_auc_empirical_p_right`
   - `p_value_method`
   - `p_value_resolution`
   - `p_value_caveat`
   - `is_formal_significance`
   - `multiple_testing_corrected`
   - `random_auc`
   - `random_pr_auc`
   - `beats_random_auc`
   - `survives_circular_shift_null`
   - `robustness_warning_count`
5. Evaluation test:
   - `robustness.walkforward_nulls`
6. Unit coverage for deterministic seeded outputs and bounded p-values.

Real smoke run:

- Run ID: `phase2-smoke-nulls`
- Status: `pass`
- Null rows: 6,448
- Baseline rows: 104
- Walk-forward label rows: 104
- Rows not surviving circular-shift null: 99
- Rows matched or beaten by seeded random baseline: 58

Current interpretation:

1. The null and baseline layer is descriptive, not formal significance.
2. P-values are empirical, coarse in smoke mode, uncorrected for multiple testing, and caveated for overlapping horizons/autocorrelation/sparse events.
3. Many walk-forward rows currently fail null/baseline robustness, so dashboard claims should remain blocked.
4. Next robustness layer should add FDR/multiple-testing correction and regime concentration checks before any supported evidence badge is possible.

### 2026-06-21: Milestone 2D FDR And Event-Concentration Gates

Implemented:

1. Benjamini-Hochberg FDR correction across all walk-forward label rows.
2. Enriched `tables/walkforward_by_label.csv` with:
   - `auc_fdr_q_value`
   - `pr_auc_fdr_q_value`
   - `fdr_alpha`
   - `auc_passes_fdr`
   - `pr_auc_passes_fdr`
   - `multiple_testing_method`
   - `event_year_count`
   - `max_event_year_share`
   - `event_concentration_hhi`
   - `dominant_event_year`
   - `passes_regime_concentration_gate`
   - `regime_concentration_method`
   - `passes_initial_robustness_gates`
3. Claim-gate defaults for event concentration:
   - Maximum single-year event share: `0.67`
   - Minimum event years: `2`
4. Validator warnings now distinguish:
   - rows failing the circular-shift null
   - rows failing FDR correction
   - rows matched or beaten by random baseline
   - rows with event-year concentration too high for claim promotion
5. Unit coverage for deterministic q-values, FDR metadata, concentration columns, and persisted artifacts.

Validation:

- `python3 -m pytest tests/test_evaluation_harness.py` could not run because the system Python has no `pytest`.
- `python3 -m unittest tests.test_evaluation_harness` could not run with system Python because `numpy` is unavailable there.
- Bundled runtime passed:
  - `/Users/josh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest tests.test_evaluation_harness`
  - 13 tests, all passing.
- `evaluate_metrics.py list-tests` passed with the bundled runtime.
- A real `evaluate_metrics.py run --profile smoke --run-id phase2-smoke-fdr-regime` was started but interrupted after about 90 seconds because it was still inside the existing calibration loop, before the evaluation layer. This slice is unit-validated but still needs a fresh real smoke run once pipeline runtime is acceptable.

Current interpretation:

1. The walk-forward robustness table now has an initial multiple-testing and event-concentration gate.
2. This still does not promote any metric claim. A row must now beat random, survive the circular-shift null, pass FDR, and avoid concentrated events before it clears the initial robustness gates.
3. The concentration check is intentionally simple calendar-year concentration. A richer market-regime concentration check should replace or augment it in Milestone 4.
4. Next slice should add academic calibration/monotonicity diagnostics or begin the practical usability suite, depending on whether we want more predictive-shape evidence or strategy evidence first.

### 2026-06-22: Milestone 2E Academic Shape And Validity Diagnostics

Implemented:

1. `risk_engine/evaluation/academic.py`
   - post-hoc walk-forward reliability bins
   - Spearman score/label association
   - monotonic event-rate diagnostics
   - explicit `calibration_scope` warning that bins are descriptive, not deployable thresholds
2. `risk_engine/evaluation/validity.py`
   - label audit rows
   - event-run counts and largest event-cluster share
   - future/past score-shift probes
   - synthetic perfect/inverted/random sentinels
3. New artifacts:
   - `tables/reliability_bins.csv`
   - `tables/monotonicity.csv`
   - `tables/label_audit.csv`
   - `tables/shift_probe.csv`
   - `tables/synthetic_sentinels.csv`
4. Enriched `tables/walkforward_by_label.csv` with:
   - `spearman_score_label`
   - `nondecreasing_event_rate_share`
   - `passes_monotonicity_gate`
   - `event_cluster_count`
   - `event_run_count`
   - `future_shift_best_auc`
   - `future_shift_auc_advantage`
   - `passes_shift_leakage_probe`
   - `passes_label_cluster_gate`
5. Validator changes:
   - underpowered reliability bins prevent monotonicity from passing
   - future-shift leakage probe failures block dashboard claims
   - one-class synthetic sentinel cases are treated as not applicable rather than false support
   - missing diagnostic inputs preserve stable empty CSV schemas

Independent validation:

- Academic validator found underpowered-bin and post-hoc calibration interpretation risks. Fixed.
- Validity validator found non-blocking leakage, score-filtered label clusters, one-class sentinel, and empty-schema risks. Fixed.

### 2026-06-22: Milestone 2F Practical Usability Suite

Implemented:

1. `risk_engine/evaluation/practical.py`
2. Monthly allocation-policy simulator:
   - target from month close
   - applied exposure in the next month
   - transaction costs charged in the applied exposure period
   - turnover, drawdown, CAGR, Calmar, Sharpe, average exposure, cost drag
3. Baselines:
   - buy-and-hold
   - half allocation
   - 6-month momentum
   - deep-drawdown buy
   - seeded random timing
4. Same-cashflow DCA ledger:
   - fixed monthly DCA
   - seeded random same-cashflow DCA
   - `risk_weighted_dca`
   - identical external monthly contribution schedule
   - cash, units, buy amount, total contributed, terminal wealth
5. Guardrails:
   - turnover guardrail tightened to `6.0` per year
   - cost-drag guardrail uses annualized cost drag
   - guardrail failures block practical dashboard claims
6. New artifacts:
   - `tables/strategy_results.csv`
   - `tables/strategy_equity_curves.csv`
   - `tables/strategy_trades.csv`

Independent validation:

- First practical validator found that the initial allocation-only suite could overstate DCA and strategy claims. Fixed with same-cashflow DCA ledger, exposure-adjusted KPIs, aligned cost timing, and expanded baselines.
- Second practical/strength validator confirmed same-cashflow DCA, exposure-adjusted KPIs, timing, and baseline sufficiency were materially addressed. Remaining guardrail severity concern was fixed by making turnover/cost failures dashboard-blocking.

### 2026-06-22: Milestone 2G Strength Mapping And Robustness

Implemented:

1. `risk_engine/evaluation/strength.py`
2. Degraded-score scenarios:
   - `missing_20pct_ffill`
   - `stale_3m`
   - `noise_10pct`
3. Market-regime split using expanding monthly return, drawdown, and volatility context:
   - `bull_trend`
   - `bear_drawdown`
   - `sideways_quiet`
   - `sideways_volatile`
   - `unknown`
4. Rolling-window stability:
   - smoke profile: 36-month windows
   - standard profile: 60-month windows
5. New artifacts:
   - `tables/degraded_data.csv`
   - `tables/regime_results.csv`
   - `tables/rolling_stability.csv`
6. Enriched `tables/walkforward_by_label.csv` with:
   - `worst_degraded_auc_delta`
   - `rolling_auc_min`
   - `rolling_auc_max`
   - `rolling_auc_range`
   - `degraded_data_evaluable`
   - `rolling_stability_evaluable`
   - `passes_degraded_data_gate`
   - `passes_rolling_stability_gate`
7. Claim discipline:
   - not-evaluable degraded/rolling rows no longer pass by default
   - underpowered regime rows do not publish numeric AUC/PR-AUC
   - underpowered regime rows are explicitly marked `underpowered_descriptive_only`

### 2026-06-22: Current Verification

Focused tests:

- Bundled runtime:
  - `/Users/josh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest tests.test_evaluation_harness`
  - 17 tests, all passing.
- `evaluate_metrics.py list-tests` passed and currently lists:
  - `data.series_integrity`
  - `data.availability_calendar`
  - `temporal.live_availability`
  - `temporal.source_availability_metadata`
  - `academic.existing_benchmark_snapshot`
  - `validator.benchmark_claim_gate_readiness`
  - `walkforward.expanding_benchmark`
  - `robustness.walkforward_nulls`
  - `academic.calibration_monotonicity`
  - `validity.label_leakage_sentinels`
  - `robustness.strength_mapping`
  - `practical.monthly_strategy_suite`
  - `validator.claim_gates`

Direct real-data smoke run:

- Run ID: `phase2-smoke-direct-current-v3`
- Run directory: `output/evaluation/runs/phase2-smoke-direct-current-v3`
- Status: `fail`
- Structural data integrity: `pass`
- Walk-forward benchmark: `pass`
- Dashboard claims: blocked by `validity.label_leakage_sentinels`
- Main blocking warning:
  - `future_shift_probe_advantage`: 43 walk-forward label rows are materially improved by future-shifted scores.
- Artifact counts:
  - `walkforward_by_label.csv`: 104 rows, 68 columns
  - `reliability_bins.csv`: 520 rows
  - `label_audit.csv`: 104 rows
  - `degraded_data.csv`: 312 rows
  - `regime_results.csv`: 520 rows
  - `rolling_stability.csv`: 884 rows
  - `strategy_results.csv`: 120 rows
  - `strategy_equity_curves.csv`: 20,760 rows
  - `strategy_trades.csv`: 11,346 rows

Current interpretation:

1. Phase 2 now produces a broad enough local artifact suite to inspect academic predictive shape, leakage, robustness, regimes, degraded data, and practical monthly usability.
2. The latest direct real-data run intentionally does not promote dashboard claims. The future-shift probe finds enough suspicious future-score advantage that claims must remain blocked pending deeper investigation.
3. The old full CLI `evaluate_metrics.py run` path still spends significant time in the full pipeline calibration step before reaching evaluation. The direct run validates the evaluation layer against current local artifacts, but the full pipeline runtime should be improved or bypassed with a first-class `run --from-artifacts` option before treating end-to-end operation as polished.

### 2026-06-22: Milestone 2H Artifact CLI, Hardened Gates, And Standard Run

Implemented:

1. First-class artifact execution:
   - `evaluate_metrics.py run-artifacts --profile smoke --artifact-dir output --run-id <id>`
   - `evaluate_metrics.py run-artifacts --profile standard --artifact-dir output --run-id <id>`
2. Artifact loader behavior:
   - reads `risk_scores_full.csv`
   - reads existing benchmark/source/metric health artifacts when present
   - derives `dca_risk` with `add_dca_risk_columns` when the stored artifact predates that column
3. Source-quality audit:
   - `data.source_quality`
   - recent flatline checks
   - metric bound checks
   - BTC price discontinuity check
   - source-health availability summary
4. Hardened dashboard claim gates:
   - missing live `available_at_date` now blocks live-style dashboard claims
   - zero rows passing initial robustness gates blocks dashboard claims
   - practical turnover/cost guardrail failures block practical dashboard claims
   - no metric policy beating buy-and-hold blocks practical dashboard claims
   - no risk-weighted DCA beating fixed DCA blocks practical dashboard claims
5. Unit coverage:
   - `run-artifacts` CLI path
   - derived `dca_risk` from artifact inputs
   - source-quality registry
   - same-cashflow DCA contribution equality
   - cost drag reducing buy-and-hold return
   - underpowered regime rows do not publish numeric AUC

Focused verification:

- Bundled runtime:
  - `/Users/josh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest tests.test_evaluation_harness`
  - 18 tests, all passing.

Supported smoke artifact run:

- Command:
  - `/Users/josh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 evaluate_metrics.py run-artifacts --profile smoke --artifact-dir output --run-id phase2-smoke-artifacts-cli-final-status`
- Run directory:
  - `output/evaluation/runs/phase2-smoke-artifacts-cli-final-status`
- Status: `fail`
- Structural integrity: pass
- Dashboard claims blocked by:
  - unknown live availability
  - no rows passing initial robustness gates
  - future-shift leakage probe advantage
  - no practical metric policy beating buy-and-hold
  - no risk-weighted DCA beating fixed DCA

Supported standard artifact run:

- Command:
  - `/Users/josh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 evaluate_metrics.py run-artifacts --profile standard --artifact-dir output --run-id phase2-standard-artifacts-cli-final`
- Run directory:
  - `output/evaluation/runs/phase2-standard-artifacts-cli-final`
- Status: `fail`
- Tests:
  - `data.series_integrity`: pass
  - `data.source_quality`: warn
  - `temporal.live_availability`: fail
  - `robustness.walkforward_nulls`: fail
  - `walkforward.expanding_benchmark`: pass
  - `validity.label_leakage_sentinels`: fail
  - `practical.monthly_strategy_suite`: fail
- Standard artifact counts:
  - `walkforward_by_label.csv`: 624 rows, 70 columns
  - `walkforward_by_fold.csv`: 70,980 rows
  - `walkforward_nulls.csv`: 84,912 rows
  - `reliability_bins.csv`: 6,240 rows
  - `label_audit.csv`: 624 rows
  - `degraded_data.csv`: 1,872 rows
  - `regime_results.csv`: 3,120 rows
  - `rolling_stability.csv`: 2,634 rows
  - `strategy_results.csv`: 300 rows
  - `strategy_equity_curves.csv`: 51,900 rows
  - `strategy_trades.csv`: 28,365 rows

Standard run result interpretation:

1. No dashboard claims are currently supported.
2. No walk-forward label rows pass the initial robustness gates.
3. 220 walk-forward label rows show material future-shift score advantage and must be investigated before any predictive-strength storytelling.
4. 624 walk-forward label rows fail FDR correction.
5. 545 walk-forward label rows fail monotonicity diagnostics.
6. 237 walk-forward label rows are fragile under degraded-data scenarios.
7. 259 walk-forward label rows have unstable rolling AUC ranges.
8. 260 metric-policy strategy rows underperform buy-and-hold CAGR.
9. Risk-weighted DCA does not beat fixed monthly DCA in any evaluated cost row.
10. Live-style claims remain blocked because the series does not expose explicit `available_at_date` metadata.

Phase 2 status:

- The implementation now satisfies the Phase 2 artifact-suite objective and has run a standard profile through a supported local artifact path.
- The result is negative/conservative: Phase 2 produced evidence and blockers, not promoted claims.
- Phase 3 should not begin as a claim dashboard. If frontend work begins, it should present an evidence-quality/blocked-claims dashboard and make the failures first-class.
