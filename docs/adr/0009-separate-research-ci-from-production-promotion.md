# Separate research CI from production promotion

Status: accepted, 2026-11-07, following Josh's change of project purpose to a
small continuing research programme. Execution location revised 2026-11-10 at
Josh's request: runner billing must not block ordinary work.

## Decision

Research commits must pass relevant local security, backend tests and web checks. They need not
beat a legacy investment strategy to be published as experimental source code.
The fixed information benchmark, reference atlas, attempts and negative evidence
remain authoritative for research comparisons; this decision changes none of
their scores, targets, data or rules. Automatic PR/main validation and its legacy
performance diagnostic are removed. The optional hosted validation workflow is
manual-only; Cloudflare retains its own build/deployment check. A daily dependency
security scan remains automatic, with native Dependabot alerts/security PRs.
Dependency changes require an exact-candidate local security scan even if Actions
billing prevents the daily scan. No new hook, attestation or hosted merge gate is
introduced. GitHub's existing empty required-check list is unchanged.

The former alternative was narrower automatic CI and fewer duplicate scans. It
still depended on billable runners and duplicated local checks/Cloudflare builds,
so local-first validation is preferred. Hosted validation remains available when
an independent environment is specifically needed.

The existing production model-acceptance commands move unchanged to the explicit
`model-acceptance.yml` workflow. Its policy, thresholds, frozen reference and
canonical identity remain unchanged. It has no override that converts failure
into acceptance, no canonical-update step and no publication step.

Before any fetch or dashboard publication, the manual publisher must
require the accepted source/runtime-file fingerprint and compare resolved model
settings with the accepted fixture. Operational credentials, locations and
declared refresh/date controls are excluded from the second comparison; all
other fields, including future fields, are checked. Diagnostics print field
names, never credentials. Optional social sources are aligned with the fixture's
disabled setting. Existing unaccepted engine revisions therefore stop refresh;
the previously published artifacts remain the dashboard's input. Its daily cron
is removed while the model is unaccepted; publishing requires an explicit manual
invocation. The inactive CI-dependent automatic security-patch merger and its
dedicated tooling/tests are removed. Dependency updates are verified locally and
merged explicitly; no protection is bypassed or loosened to replace it.

## Consequences

- Passing local or optional hosted checks proves checks passed, not that a model is profitable,
  calibrated, production-approved or suitable for trading.
- Successful production evaluation still requires a separately reviewed canonical
  update before the publisher's source guard permits a changed model. This workflow
  does not grant automatic model approval.
- Source correctness fixes can be shared without silently deploying them as a
  different dashboard model. Refresh may remain stopped while research proceeds.
- Older automatic-CI/refresh requirements in this record and ADR 0007 are superseded. ADR 0008 still defines
  the legacy acceptance metrics; they are not the research programme's objective.
- Current results, limitations and the next round belong in the
  [research record](../metric_evaluation_plan.md), rather than this decision.
