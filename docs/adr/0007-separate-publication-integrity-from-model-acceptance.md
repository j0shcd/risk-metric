# Separate publication integrity from automated model acceptance

Status: superseded for DCA acceptance metrics by ADR 0008.

The system will have two automated binary gates and no claim-promotion or manual model-approval workflow. The Publication Integrity Gate blocks stale, incomplete, invalid, or internally inconsistent daily releases. The Model Acceptance Gate runs only when the model fingerprint changes and compares a Candidate Model with the Canonical Model on the same frozen data; the candidate passes only by meaningfully improving the frozen six-month DCA Risk objective while all registered accumulation, de-risking, strategy, leakage, availability, sample, and concentration guardrails remain within declared non-inferiority bounds.

## Consequences

- Model endpoint definitions, practical-effect thresholds, uncertainty method, and non-inferiority bounds live in versioned tested configuration rather than being tuned during a run.
- Movement inside the declared uncertainty/non-inferiority band is unchanged, not improvement. A trivial numerical increase cannot promote a candidate.
- A failed candidate fails CI with no manual override path. Data-only releases do not rerun model acceptance.
- Baselines identify the Canonical Model by release ID, code fingerprint, and configuration hash; “SOTA” and ambiguous “foundation” names are retired.
- The old Cartesian retrospective benchmark remains a nonblocking diagnostic artifact.
- Dashboard language is ordinary intentionally maintained product content, not an automated evidence-promotion state machine.
