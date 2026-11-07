# Upside gain concentration — fixed astra_b proposal

Hypothesis: an advance carried by a few positive daily moves is a more fragile
opportunity state than diffuse accumulation. This tests gain concentration,
not upside/downside energy share, price displacement or adaptive innovations.
It does not establish new information beyond flexible price baselines.

At each completed month end, require exactly 731 consecutive UTC daily closes
ending on that date. For the 730 daily log returns, set g=max(r,0), then
H=sum(g²)/sum(g)² and risk=(730H-1)/729, clipped to [0,1]. Compute after
scaling gains by their within-window maximum to avoid numerical underflow.
Higher risk means more concentrated upside. No gains means risk0 (explicit
prior, not evidence of a safe asset). Missing, stale, nonfinite or nonpositive
window closes mean neutral0.5 with a status flag. Queries remain present.
No interpolation; duplicate, noncalendar or unordered source dates fail closed.

All parameters fixed before this campaign's measurement. No training labels,
learning cutoff, optimizer or online updates beyond the trailing window.
This is a 2026 reconstruction, not a historical deployment. Source close/UTC
conventions and point-in-time vintages remain unverified. Only the existing
pre2023 development bundle is authorized for root's one astra_b submission.
No campaign, outer or equity scores informed this specification.

Falsification: primary24-month terminal-return CRPS must be compared with
unconditional, context and the full17-reference atlas on identical origins;
retain separate12/24-month downside coordinates and unfavorable risk ordering.
No favorable ordering/proper-score advantage is evidence against usefulness;
regressions must not be averaged away. Tiny overlapping BTC samples cannot
establish a stable regime law. Jump-driven adoption may persist; a single gain
can affect this score for two years. Flat and steadily falling windows share
risk0. The state deliberately omits downside severity and direction of net
return. No promotion to production or policy follows from this trial.

API: generate(Date/Price frame, optional month-end dates) returns Date-indexed
astra_b_upside_concentration plus status. CLI --inputs points to the locked
bundle containing btc_daily.csv; --output exclusively creates a CSV. Root owns
submission; no scorer was run during implementation. Config JSON freezes the
protocol and source hash. Next step is independent source review, then exactly
one root-owned registered development measurement; no parameter alternatives.

Synthetic verification: python -m unittest tests.test_structural_state -q.
Tests cover k equal gains' exact law, zero/upside prior, amplitude/price-scale
invariance, gain order, numerical extremes, missing/stale windows and causal
prefix/future poisoning. Replacing H by1 and extending windows one day into
the future both make regression tests fail. No provider or market fit required.
