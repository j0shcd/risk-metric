# Risk Metric

Risk Metric helps long-horizon Bitcoin investors judge whether the coming months are
more favorable for accumulation or de-risking, explain that judgment, and test simple
ways of acting on it historically.

## Language

**DCA Risk Indicator**:
The product's central 0–1 metric for long-horizon accumulation and de-risking conditions. It is intended to characterize approximately the next six months, not short-term trading opportunities or a literal event probability.
_Avoid_: DCA strategy, trading signal, probability

**Dynamic DCA Strategy**:
A rules-based strategy that uses risk-indicator thresholds to vary purchases and to sell or “DCA out” when conditions become sufficiently heated.
_Avoid_: DCA Risk Indicator, short-term strategy

**Fixed DCA**:
A benchmark strategy that invests the same external contribution on every scheduled date without reference to a risk indicator.
_Avoid_: Baseline model

**Scenario Planner**:
A small user-facing historical simulator for comparing simple strategies and indicators under shared accounting and execution rules. Its results illustrate historical scenarios and are not evidence that a user-selected strategy is validated or optimal.
_Avoid_: Backtest proof, strategy optimizer

**Validation Benchmark**:
The reproducible research suite that tests the DCA Risk Indicator using statistical metrics, realistic strategy simulations, robustness checks, and fixed reference strategies.
_Avoid_: Scenario Planner, SOTA snapshot

**Registered Hypothesis**:
A frozen indicator, outcome, direction, horizon, statistic, policy, and pass criterion that may contribute to product evidence in its declared evaluation version.
_Avoid_: Interesting correlation, post-hoc test

**Exploratory Sweep**:
Quarantined analysis across alternative metrics, outcomes, horizons, regimes, thresholds, ablations, and parameters. It may generate a future Registered Hypothesis but cannot promote a product claim in the evaluation version that discovered it.
_Avoid_: Validation Benchmark, confirmatory evidence

**Retrospective Reconstruction**:
Historical analysis using the best dataset available now when one or more inputs cannot be proven to match the vintage available on the decision date.
_Avoid_: Point-in-time backtest, as-known-then evidence

**Point-in-Time Eligible Evidence**:
Historical evidence for which every required observation has an acceptable availability rule and vintage policy, allowing a claim about what could have been known at the decision time.
_Avoid_: Retrospective Reconstruction

**Prospective Evidence**:
Evidence from a model output and its inputs frozen before the evaluated outcome window began.
_Avoid_: Reconstructed backtest

**Release**:
An immutable, validated set of public scores, explanations, provenance, and evidence that share one release identity.
_Avoid_: Deployment, latest snapshot

**Canonical Model**:
The model definition used to produce public DCA Risk releases, identified by immutable code and configuration fingerprints.
_Avoid_: SOTA, latest experiment

**Candidate Model**:
A changed model definition evaluated automatically against the Canonical Model on the same frozen data. It becomes canonical only by passing the Model Acceptance Gate.
_Avoid_: Canonical Model, manually approved model

**Publication Integrity Gate**:
The automated pass/fail checks that prevent an incomplete, stale, internally inconsistent, or invalid Release from becoming public.
_Avoid_: Model performance gate

**Model Acceptance Gate**:
The automated pass/fail comparison that requires a Candidate Model to meaningfully improve the frozen primary validation objective while remaining within registered non-regression guardrails.
_Avoid_: Manual model review, claim promotion

**Prospective Archive**:
A deliberately compact record containing the frozen score, normalized model inputs, provenance, and configuration identity needed to evaluate a release after its outcomes mature.
_Avoid_: Full source backup, web artifact mirror


**Alert Delivery**:
A durable record of one subscriber's threshold-zone notification for one Release. Its identity is the subscriber, release, and entered zone—not an individual send attempt.
_Avoid_: Email attempt, current subscriber zone

**Component Metric**:
An underlying model input or intermediate indicator used to construct or explain the DCA Risk Indicator. Component metrics are supporting evidence rather than the product's primary output.
_Avoid_: Headline metric, primary score

**MVRV Ratio Proxy**:
The project's expanding standardization of the market-value-to-realized-value ratio. It is one valuation feature and is not the canonical MVRV-Z statistic.
_Avoid_: MVRV Z-score, supply profitability evidence

**Derived Profitability View**:
A display-only hot/cold transformation of the MVRV Ratio Proxy used for intuitive explanation. It carries no independent model weight and is not corroborating evidence.
_Avoid_: Supply in profit, supply in loss, independent on-chain metric
