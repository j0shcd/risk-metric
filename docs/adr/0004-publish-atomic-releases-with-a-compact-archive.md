# Publish atomic releases with a compact prospective archive

Every public score, explanation, evidence summary, and public JSON payload identifies one immutable Release. Publishing builds and validates the complete release before moving the public `latest` pointer. Git retains code, schemas, registered hypotheses, and small benchmark manifests; Pages serves the current validated bundle; R2 retains only a compact Prospective Archive. Public JSON is generated statically without operational user state.

## Consequences

- The archive stores normalized values actually consumed by the model, source/unit/availability provenance, raw-content hashes, score, configuration identity, and release manifest. It does not mirror web history, charts, caches, bulky evaluation tables, or provider payloads unless a small raw payload is uniquely necessary.
- Storage economy is a product constraint: this is a small noncommercial side project, not institutional research infrastructure. The initial archive budget should be approximately 250 MB total, with warnings well before that point and hard failure rather than paid overflow. Representation or retention of nonessential diagnostics must shrink before the budget grows.
- Expensive evaluation artifacts are retained only for meaningful model or registered-benchmark versions, not every daily release.
- Public JSON consumes the same immutable release identity as the dashboard.
