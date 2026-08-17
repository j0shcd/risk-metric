# Dynamic DCA Weakness Diagnostics — Design Plan

Status: tranche 1 implemented; tranches 2-3 proposed (reviewed 2026-07-15)

Update 2026-08-01: the compact evidence suite described in
`docs/dca_evidence.md` now separates accumulation-only value, de-risking value,
and policy-independent signal value. Each test uses rolling starts and causal
price-only benchmarks, with future-suffix causality sentinels. The split avoids
conflating the opportunity cost of deferred contributions with the value of
selling and later re-entering.

## Session handoff (2026-08-17)

Read this section first if you are picking up this work cold. Start by reading
`docs/dca_evidence.md` (results) and `docs/adr/0008-align-dca-acceptance-with-investor-decisions.md`
(decision) — this plan assumes both as background.

**Shipped and committed this session** (backend engine → acceptance gate → docs →
web, in that order): the three-test DCA evidence suite (`risk_engine/evaluation/dca_evidence.py`),
the realigned model-acceptance policy (`config/model_acceptance.json`,
`risk_engine/model_acceptance.py`), ADR 0008 and `docs/dca_evidence.md`, and the web
Evidence tab (`web/src/dcaEvidence.js` + `DcaEvidencePanel` in `web/src/App.jsx`). All
targeted Python tests (38) and JS tests (33) pass.

**Central open question, not a bug — decide before doing more diagnostics work:**
DCA Risk does not pass its own new acceptance gate as an accumulation-timing tool
(Test 1: -21.46% vs Fixed DCA; Test 3: wrong-signed and not significant vs its
timing placebo). Only Test 2 (de-risking an existing position) is promising, and
it is *not* corroborated by Test 3. Before investing in tranches 2-3 below (which
assume the goal is to fix a bidirectional dynamic-DCA strategy), decide whether
the product should instead scope down to a de-risking-only recommendation — the
diagnostics below are moot if the accumulation side is dropped rather than fixed.

**Known cleanup needed (not fixed this session):**
- `EvidencePanel` in `web/src/App.jsx` (the old `evaluationSummary`/`claim_state`-driven
  component, ~245 lines) is now dead: the Evidence tab renders `DcaEvidencePanel`
  instead and nothing else calls `EvidencePanel`. `evaluationSummary` is still fetched
  in `web/src/data.js:loadDashboardData` and returned in `payload`, but `App()` no
  longer destructures it. The matching `evaluation_summary.json` mock fixture in
  `web/src/App.test.jsx` (the `claim_state`/`blocking_warnings`/`top_warnings` block)
  is asserted against by nothing. Decide whether to delete `EvidencePanel` and the
  dead fetch/fixture, or find them a home — don't leave them silently unused.
- `web/src/dcaEvidence.js` is hand-authored, copied from the numbers in
  `docs/dca_evidence.md` / `config/model_acceptance_canonical.json`. Nothing enforces
  the three stay in sync. If the evaluation is rerun and canonical metrics change,
  update all three together or the web copy will quietly go stale.
- Environment only, pre-existing (not introduced this session): `.venv` runs Python
  3.9.6; `tests/test_benchmark_gate.py` and `tests/test_social_source.py` fail to
  *collect* (`str | None` needs 3.10+), so a bare `pytest` run errors before it starts.
  Run targeted files (as above) or upgrade the venv interpreter.

**Next step if continuing tranches 2-3 as planned below:** start at D3 (regime-conditional
P&L decomposition) — it's the most likely to explain *why* Test 1 failed, which is the
prerequisite the rest of tranche 3 (D5-D9) builds on.

Goal: extend `risk_engine/evaluation/` so it can explain *why* the dynamic DCA strategy
underperforms fixed DCA, not just that it does — the prerequisite to improving it for
real-life-adjacent usage.

## 0. The headline finding: three strategies with divergent semantics

There are currently **three divergent "dynamic DCA" implementations**. The evaluation
harness now measures the production and evaluation variants separately, but they still do
not describe the browser strategy users interact with:

1. **Production** — `risk_engine/cycle_model.py:_simulate_dynamic_dca` (the strategy the
   `cycle_dynamic_dca_*` knobs in `risk_engine/config.py` control). Monthly, bidirectional,
   threshold-gated on the **raw** `frenzy_score`/`accumulation_score` composites (not the
   calibrated `cycle_p_*` probabilities), with cash buffer and fee/slippage. Its output
   (`financial_benchmark_summary`/`_curves`) is computed every pipeline run, written to
   `output/`, and consumed by `risk_engine/evaluation/runner.py` as a separate production
   policy family.
2. **Evaluation suite** — `risk_engine/evaluation/practical.py:344`, `risk_weighted_dca =
   (0.25 + 1.50 * favorable).clip(0, 2)` where `favorable = 1 - dca_risk`. Buy-only, monthly,
   no thresholds. **This is what the currently-failing honesty gates are verdicts about.**
3. **Frontend simulator** — `web/src/data.js:simulateDcaStrategy`. Step-multiplier buy/sell
   on user-tunable `buyStartRisk`/`sellStartRisk`, daily/weekly/monthly cadence, arbitrary
   start date. What real users actually experience.

Consequence: "improving" one implementation against its gates can still leave the other two
unchanged. A canonical strategy definition remains an architectural decision.

## 1. Prioritized build order

### Tranche 1 (implemented)
- **D1. Wire production dynamic DCA into the harness** (done). Pass
  `result.financial_benchmark_summary`/`_curves` into the practical evaluation; reshape into
  `strategy_results.csv` rows with `policy_family="production_dca_cashflow"` so the existing
  `checks.py:summarize_practical_strategies` gates apply unchanged. Add
  `tables/threshold_reachability.csv`: what fraction of history the raw composites ever cross
  `cycle_dynamic_dca_buy_threshold`/`sell_threshold` — if rarely, the "dynamic" strategy
  degenerates to fixed DCA by construction, which alone would explain the flat results.
- **D2. Add the 4 DCA components to `DEFAULT_METRICS`** (done). One-line-ish change in
  `risk_engine/evaluation/config.py` (tag `confirmatory=False`); the walk-forward/regime/
  robustness machinery then evaluates each of `dca_top_reversal_component`,
  `dca_bottom_reversal_component`, `dca_cycle_extension_component`,
  `dca_cycle_regime_component` for free — showing whether the flat mean in
  `add_dca_risk_columns` dilutes a component with real skill.

### Tranche 2
- **D3. Regime-conditional P&L decomposition** (M). Reuse `strength.py:_market_regimes`
  (bull_trend/bear_drawdown/sideways_*) against `practical.curves`; per-regime CAGR/drawdown
  delta vs fixed DCA, with the existing low-sample eligibility gating. Answers "does it win
  in bears and lose in bulls?" — usually the most illuminating cut for an aggregate-flat
  strategy. Artifact: `tables/practical_regime_results.csv`.
- **D4. Oracle / perfect-foresight headroom** (M). A hindsight buy-multiplier series under
  the same clip/cap/cashflow constraints, run through the existing `_simulate_dca_cashflow`.
  `policy_family="oracle_diagnostic"`, excluded from all gates, explicit lookahead warning.
  One number that says whether there is any edge worth extracting at all — if headroom is
  tiny, stop tuning and say so.

### Tranche 3 (after reviewing tranche 1–2 results)
- **D5. Trade-level attribution vs fixed DCA** (M) — per-month `units_delta ×
  forward-return` hindsight value; which specific overweighted buys destroy value.
- **D6. Cost-sensitivity curve** (S) — breakeven `cost_bps` and CAGR-delta slope from the
  existing cost grid in `strategy_results.csv`; pure aggregation.
- **D7. Signal-lag analysis** (M) — median lag between price local extrema and `dca_risk`
  turns, split by tops vs bottoms (in `validity.py`; retrospective diagnostic, labeled as
  such). A late-turning signal is the classic mechanical reason risk-weighted DCA buys the
  recovery instead of the bottom.
- **D8. Start-date / cadence robustness** (M) — rolling start dates + weekly cadence,
  matching what users tune in the frontend simulator; report the distribution of
  `cagr_delta_vs_fixed_dca`, not a single number.
- **D9. Parameter-sensitivity grid** (L, exploratory only) — predeclared grid over the
  multiplier formula and `cycle_dynamic_dca_*` thresholds; report
  `pct_grid_beating_fixed_dca` to distinguish "signal is hopeless" from "constants are a bad
  pick within a viable family". `result_type="exploratory"`; never promote a grid winner
  without a later out-of-sample confirmatory run (per `docs/metric_evaluation_plan.md`,
  Confirmatory vs Exploratory).

## 2. Persistence & surfacing

Follow the existing three-layer pattern: per-run CSVs under `tables/` (via
`EvaluationStore.write_frame`), registered in the run manifest, summarized as
`EvaluationTestResult`s in `checks.py` (new non-blocking warning codes:
`dca_threshold_rarely_reachable`, `dca_component_dominated_by_single_signal`,
`dca_signal_lags_price_turns`; a new *blocking* one only if the production strategy also
fails the fixed-DCA gate). Aggregate the human-readable answer into a new
`weakness_report.json` (new module `risk_engine/evaluation/weakness_report.py`), and add a
`"weaknesses"` section to `web_summary.py:build_evaluation_web_summary` so the Evidence tab
can render it. Document the new test family in `docs/metric_evaluation_plan.md`.

## 3. Guardrails

- Sweeps (D8/D9) are diagnostics, not searches: everything `result_type="exploratory"`,
  no silent promotion of grid winners into config defaults; a proposed default change
  requires a full `--profile standard` run judged on the whole gate suite, not just the
  practical CAGR delta.
- Oracle (D4) and extrema-based lag analysis (D7) use full-sample hindsight by design —
  keep them out of every honesty-gate filter and flag them with explicit warning codes,
  mirroring the existing `uses_full_sample_quantile` pattern.
- Regime slices reuse existing eligibility gating; apply `_benjamini_hochberg` (or at
  minimum report comparison counts) once multiple diagnostic families multiply the number
  of "beats fixed DCA" comparisons.
- Heavy grids (D8/D9) gate behind `standard`/`expensive` profiles so `smoke` stays
  CI-fast, following the existing `smoke_mode` pattern.
