# System Audit — 2026-07-15

## Scope and method

This audit covered the Python risk pipeline, source adapters, feature and calibration
logic, cycle model, evaluation harness, benchmark gate, web export and frontend,
Cloudflare Pages functions, D1 alert delivery, CI publishing, tests, and operational
documentation. Three independent review tracks examined the core model, quantitative
evaluation, and web/operations. Critical model and DCA findings received adversarial
cross-review before fixes were made.

The audit distinguishes:

- **Fixed now:** bounded defects with a clear intended behavior.
- **Open normal work:** important but larger than a safe audit-time patch.
- **Structural decision:** competing concepts or invalid architecture where deleting or
  replacing a subsystem requires owner approval.

## Executive verdict

The project has a sensible outer shape: source acquisition feeds a deterministic Python
pipeline, the pipeline exports versioned static artifacts, and the web application reads
those artifacts. The implementation is well tested at the unit level. The main problems
were not general code quality; they were semantic drift between independently developed
subsystems and research assumptions that had silently become production behavior.

Before this audit, historical calibration and the market trend feature contained future
information, dynamic-DCA deposits were counted as investment return, several source
units/provenance rules were inconsistent, and alerts could fail at D1's parameter limit
or send stale evidence. Those defects are fixed in the working tree.

The remaining central risk is conceptual multiplicity. There are multiple DCA meanings,
the evaluation harness tests every metric against every label without a declared
hypothesis map, retrospective data is mixed with point-in-time claims, and evidence can
be published independently of the score release it describes. Results should not be
treated as validated investment evidence until the structural decisions below are made
and all evaluation baselines are regenerated.

## Critical and high-severity findings fixed

### 1. Future leakage in the market log trend — critical

`risk_engine/features/market_features.py` fitted a regression over the entire price
history and used it at earlier dates. Adding future observations could therefore change a
historical feature value. It now computes an expanding, prefix-stable regression using
running sufficient statistics. `tests/test_market_features.py` proves that appending
future prices does not alter the historical prefix.

Impact: historical scores and any tests depending on this feature were overstated and
must be regenerated.

### 2. Future leakage in long-cycle calibration labels — critical

`risk_engine/calibration.py:446` formerly derived label cuts from full-sample future
outcome quantiles. The replacement derives each cut only from outcomes already resolved
at that decision date and embargoes by the maximum horizon. The metadata records
`label_cut_policy=expanding_resolved_outcomes_embargoed_by_max_horizon` at line 623.
The sparse full-sample fallback was removed rather than preserving a hidden leak.

Impact: calibrated score history and benchmark snapshots must be regenerated. Early
history may now be sparse; that is honest uncertainty, not a missing-data defect.

### 3. Dynamic-DCA contributions counted as returns — critical

`risk_engine/cycle_model.py:436-491` now tracks raw account value, cumulative
contributions, and contribution-normalized equity separately. The financial summary uses
the normalized series, while raw value and contributions remain available in exported
curves at lines 567-569. Flat-price regression tests now confirm that deposits increase
account value without generating return.

This repairs the immediate accounting error, but contribution-normalized wealth is not a
money-weighted return. A future canonical strategy specification should choose XIRR,
time-weighted return, or an explicitly documented wealth/contribution ratio.

### 4. Same-period signal execution — high

Dynamic-DCA decisions were applied to the same monthly close from which their signals
were computed. Signals are now shifted one month before execution at
`risk_engine/cycle_model.py:418-419`, with a regression test for next-month execution.

### 5. Attention calibration overwrote a different public concept — high

Calibration could replace `headline_attention` (the signal-agreement composite) with a
price-extremity calibration output. It now calibrates `attention_score` and preserves the
headline composite (`risk_engine/calibration.py:509`; regression assertion in
`tests/test_calibration.py:63`). Frontend copy was corrected to match the actual formulas.

### 6. Source unit and provenance errors — high

- CoinGecko USD volume is converted to base BTC before entering the legacy BTC-volume
  column, matching Binance semantics (`risk_engine/sources/btc_price_backfill.py`).
- Local base-BTC volume is converted back to USD before cycle-model use, and live/cache
  sources take precedence while local data only fills gaps (`risk_engine/sources/cycle.py`).
- FRED reverse-repo data is converted from billions to millions before subtraction from
  WALCL. Previously the arithmetic mixed three orders of magnitude.
- Social snapshots are no longer backfilled into historical dates. Exact-date matching
  prevents a current observation from masquerading as historical evidence
  (`risk_engine/sources/social.py`).

### 7. Misleading evaluation sample eligibility — high

Walk-forward counts now use paired, non-null score/label observations rather than label
counts alone. Promotion requires a strict production sample gate in
`risk_engine/evaluation/robustness.py`; looser aggregate results remain visible for
diagnosis but cannot promote a signal. Recent benchmarks now select the most recent
resolved observations rather than an arbitrary final calendar slice
(`risk_engine/benchmark.py:199-206`).

### 8. DCA policy-family mixing — high

The evaluation harness previously presented several unrelated experimental strategies
as peers to the production strategy. Only the production dynamic-DCA implementation is
now eligible as the policy family; other curves are explicitly marked
`production_benchmark_reference` (`risk_engine/evaluation/practical.py:385,430`). Costs
and execution lag are read from the implementation rather than independently assumed.

### 9. Alert delivery correctness — critical/high

- D1 updates are batched below the 100-bound-parameter limit and nested API failures are
  checked (`scripts/lib/d1-alert-updates.mjs`).
- Alert snapshots must contain valid risk/date values and be no more than two days old
  (`scripts/lib/alert-snapshot.mjs`). The currently checked-in snapshot fails this guard,
  so the system fails closed instead of emailing obsolete risk.
- A resubscription rotates its unsubscribe token and clears the prior zone; an
  unsubscribe consumes its token (`web/functions/api/subscribe.js:108`,
  `web/functions/api/unsubscribe.js:23`).
- CI serializes publish runs and passes `SITE_URL` and `ALERT_FROM_EMAIL` repository
  variables (`.github/workflows/daily-web-publish.yml:125-126`).

## Structural decisions — resolved

All seven structural decisions were resolved on 2026-07-16 and are recorded in
`docs/adr/0001` through `docs/adr/0007`. The sections below retain the original audit
context; their recommendations are now accepted implementation direction.

### A. Choose one canonical DCA contract

There are still three meanings distributed across the cycle model, the evaluation
harness, and frontend threshold presentation. They disagree on execution timing,
accounting objective, and what a multiplier means.

**Recommendation:** define one shared monthly strategy contract: decision timestamp,
next executable price, cash/contribution schedule, multiplier bounds, costs, and return
metric. Make the Python implementation canonical; export its policy/curve schema to the
frontend; delete or demote alternative implementations to named research references.
This will invalidate current DCA baselines.

### B. Replace the metric × label Cartesian product with a hypothesis registry

`risk_engine/evaluation/walkforward.py:216-247` evaluates each available metric against
each label. This treats economically nonsensical pairs as hypotheses and ignores intended
direction. Multiple-testing correction over a badly specified family does not repair the
meaning problem.

**Recommendation:** add a registry declaring allowed signal/outcome pairs, expected
direction, horizon, primary statistic, and whether the test is confirmatory or
exploratory. Remove unregistered pairs from promotion logic while retaining an explicitly
exploratory matrix if desired.

### C. Decide whether historical claims are point-in-time or retrospective

Several macro, social, market-cap, and on-chain inputs are current-vintage/revised
histories. Even after preventing direct backfills, a run today is not necessarily the
dataset available on a historical decision date.

**Recommendation:** either store timestamped source vintages and availability lags, or
label the affected model/evaluation as retrospective and bar it from point-in-time
promotion claims. The cheaper and more honest near-term choice is the retrospective
downgrade.

### D. Make score and evidence one atomic release

The publish flow can replace score artifacts while preserving, deleting, or mixing an
evaluation summary from a different run. Stable URLs do not expose a shared run ID,
config hash, input hash, or source as-of metadata.

**Recommendation:** publish into an immutable release directory, validate a manifest,
then atomically move a single `latest` pointer. Score, diagnostics, evaluation, and alert
snapshot must share a release ID. Do not preserve stale evidence under a new score.

### E. Redesign alert state as an idempotent outbox

Sending email and updating D1 are separate external effects. A crash between them can
duplicate mail or lose zone state. Public subscription routes also lack meaningful abuse
controls, and confirmation/unsubscribe mutate state through GET links.

**Recommendation:** introduce a transition/outbox row keyed by subscriber, release ID,
and target zone; claim/send/finalize idempotently. Add per-IP/email rate limits and use a
GET confirmation page followed by a POST mutation. This should happen before alerts are
promoted beyond a small test audience.

### F. Remove or replace duplicated on-chain proxies

The MVRV input is a ratio-derived z-score proxy, not the canonical MVRV-Z series. Supply
in profit and supply in loss are derived from the same ratio and are deterministic
complements, so treating both as independent evidence double-counts one signal.

**Recommendation:** keep the renamed MVRV ratio proxy if useful, but remove one side of
the profit/loss pair from weighting unless true independent series are sourced. Approval
is required because this changes/deletes model components and historical outputs.

### G. Retire the retrospective benchmark as a production gate

The legacy benchmark layer and the newer evaluation framework overlap. The gate compares
checked snapshots named “SOTA” and “foundation,” although they can represent identical
or stale model artifacts, and retrospective metrics can block production publishing.

**Recommendation:** retain the benchmark report as a regression diagnostic, but make the
registered walk-forward hypothesis suite the only evidence gate. Rename baselines by
immutable release ID rather than status claims such as SOTA.

## Open normal-sized work

These issues are real but were not patched because they require focused follow-up rather
than a safe local correction:

1. `false_alarm_rate` in `risk_engine/evaluation/walkforward.py:185` is actually
   `FP / (TP + FP)`, i.e. false discovery rate. Rename the field or change the formula and
   migrate consumers.
2. Reliability-bin confidence intervals use a naive normal approximation
   (`risk_engine/evaluation/academic.py:153-169`) despite serial dependence and small
   event counts. Prefer block bootstrap or a documented Wilson interval for descriptive
   bins.
3. Null/FDR logic is weaker than the number of overlapping labels, horizons, and regimes
   suggests. Rebuild it after the hypothesis registry exists.
4. Artifact-mode evaluation has hardcoded assumptions and can silently lack the full DCA
   inputs. Require a manifest declaring artifact schema, cadence, and capabilities.
5. The frontend discards some degradation/provenance detail and eagerly loads large
   historical payloads (roughly 30 MB in the current artifact set). Split history by
   range or stream/lazy-load it.
6. There is no explicit retention/expiry policy for subscribers, alert transitions, or
   evaluation runs.
7. Cloudflare configuration remains partly manual; capture D1 bindings, variables, and
   deployment configuration as code. Pin CI/bootstrap dependencies more tightly.
8. Source availability calendars need realistic publication delays, not only observation
   timestamps.
9. The current checked-in web snapshot is dated 2026-06-20 and contains no `dca_risk`.
   A cache-only publish correctly failed because the BTC cache was 62 days stale. A fresh
   source-enabled publish is required before alerts or the current web display are
   operationally trustworthy.

## Architecture assessment

### What should remain

- The separation between data/model code and static web presentation is appropriate for
  a low-frequency risk product.
- Versioned web schemas, source-health outputs, deterministic configuration, and the
  evaluation artifact store are useful foundations.
- The test suite covers many important boundaries and made the bounded corrections
  comparatively safe.

### Where boundaries should be strengthened

1. **Source observations:** every value should carry observation time, availability time,
   retrieval time, unit, source, and vintage policy.
2. **Model contract:** features should declare allowed inputs and causal lookback; public
   scores should be immutable products of a config/input hash.
3. **Hypothesis contract:** signal/outcome/direction/horizon should be registered before
   evaluation or promotion.
4. **Release contract:** all public artifacts and alerts should reference one validated
   release manifest.
5. **Strategy contract:** financial simulations should share accounting, execution, and
   cost semantics rather than reimplement them by subsystem.

## Verification

- Python: **125 tests passed** in 173.376 seconds using a temporary environment with the
  declared dependencies.
- Frontend Vitest: **29 tests passed** across 6 files.
- Node alert/release tests: **24 tests passed**.
- Production web build: **passed** (462.03 kB JavaScript, 149.27 kB gzip).
- `git diff --check`: **passed**.
- Cache-only publish smoke test: **failed closed as intended** because source data was 62
  days stale. No tracked artifacts were changed.
- Browser runtime smoke test: **failed closed as intended** with the explicit message
  `Published manifest is missing release_id`; the checked-in legacy release must be
  replaced by one fresh atomic publish before the new dashboard can render.
- Remote GitHub Actions state was not verified: `gh` is unavailable and the repository's
  workflow page was not accessible from the available browser session.

## Baseline consequences

Do not compare post-audit results directly with the checked benchmark snapshots. The
causal trend, causal calibration labels, source-unit fixes, next-period execution, and
DCA accounting all change historical outputs. Once the structural choices are resolved,
run a fresh source-enabled pipeline, full standard/expensive evaluation, and benchmark
registration from the same immutable release.

## Accepted structural resolutions

The seven structural decisions were subsequently resolved and implemented:

1. The DCA Risk Indicator is the primary product surface; methodology, supporting
   indicators, scenarios, and evidence are secondary routes.
2. Dynamic DCA is a lagged, threshold-driven strategy compared with fixed DCA under the
   same cash flows, costs, and return accounting.
3. Registered hypotheses are separated from quarantined exploratory sweeps.
4. Prospective evidence is archived as compact NDJSON with an immutable release identity,
   optional upload, collision rejection, and a hard 250 MB budget.
5. Web publication uses atomic, content-addressed releases; alerts refuse stale, mixed,
   malformed, or incomplete releases.
6. Alert state uses D1 delivery records, retry-stable encrypted tokens, POST mutations,
   cooldown claims, and bounded email-domain/global send limits.
7. Model promotion is binary and automated: a candidate must improve the registered
   accumulation objective while satisfying non-inferiority and integrity gates. The
   retrospective benchmark remains diagnostic and non-blocking.

The duplicated supply-in-profit/loss model inputs were removed. A single explicitly
named MVRV ratio z-score proxy remains in scoring; implied profitability is display-only.

The frozen canonical acceptance baseline is now recorded in
`config/model_acceptance_canonical.json`. It establishes reproducibility, not a claim of
model quality: the current registered evidence remains weak and the full evaluation does
not justify promotional performance claims.
