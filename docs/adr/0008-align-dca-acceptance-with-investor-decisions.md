# Align DCA acceptance with investor decisions

The Model Acceptance Gate will no longer optimize the generic 6/12-month DCA Risk
AUC labels. Those labels do not directly answer whether a backward-looking risk
metric improves a feasible investor outcome and are retained only as exploratory
diagnostics.

Candidate models must materially improve median terminal wealth versus identical-
cashflow Fixed DCA in the accumulation-only test. They must remain non-inferior on
the fixed-buy/risk-sell attribution policy, the one-BTC de-risking Calmar delta
versus hold, and frozen-region 48-month forward-return ordering. Every candidate
must also pass the future-suffix causality audit and source-availability gate.

This makes accumulation opportunity cost explicit, separates purchase timing from
exit timing, and prevents a model from passing by improving a convenient short-
horizon proxy while worsening the investor decisions the metric is meant to aid.
The canonical values record a reproducible baseline, not evidence that the current
model is good.
