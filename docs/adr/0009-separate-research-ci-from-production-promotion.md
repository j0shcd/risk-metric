# Separate research CI from production promotion

Status: accepted, 2026-11-07, following Josh's change of project purpose to a
small continuing research programme.

## Decision

Research commits must pass security, backend tests and web checks. They need not
beat a legacy investment strategy to be published as experimental source code.
The fixed information benchmark, reference atlas, attempts and negative evidence
remain authoritative for research comparisons; this decision changes none of
their scores, targets, data or rules.

The existing production model-acceptance commands move unchanged to the explicit
`model-acceptance.yml` workflow. Its policy, thresholds, frozen reference and
canonical identity remain unchanged. It has no override that converts failure
into acceptance, no canonical-update step and no publication step.

Before any scheduled fetch or dashboard publication, the daily workflow must
require the accepted source/runtime-file fingerprint and compare resolved model
settings with the accepted fixture. Operational credentials, locations and
declared refresh/date controls are excluded from the second comparison; all
other fields, including future fields, are checked. Diagnostics print field
names, never credentials. Optional social sources are aligned with the fixture's
disabled setting. Existing unaccepted engine revisions therefore stop refresh;
the previously published artifacts remain the dashboard's input.

## Consequences

- A green research CI run proves checks passed, not that a model is profitable,
  calibrated, production-approved or suitable for trading.
- Successful production evaluation still requires a separately reviewed canonical
  update before the daily source guard permits a changed model. This workflow
  does not grant automatic model approval.
- Source correctness fixes can be shared without silently deploying them as a
  different dashboard model. Refresh may remain stopped while research proceeds.
- Older CI-trigger statements in ADR 0007 are superseded. ADR 0008 still defines
  the legacy acceptance metrics; they are not the research programme's objective.
- Current results, limitations and the next round belong in the
  [research record](../metric_evaluation_plan.md), rather than this decision.
