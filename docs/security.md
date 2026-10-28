# Security maintenance

This is the maintainer record for dependency exposure, monitoring, and recovery.
Update it when an audit, runtime change, or monitoring activation changes the
facts below. The [dated inventory](artifacts/dependency-audit-2026-10-27.json)
retains the exact package versions and advisory IDs from this audit.

## Operational status on 2026-10-28

**Setup is not complete.** Read this section before changing security settings
or claiming that cloud monitoring or automatic merging is active. The audit
below is historical evidence; this section owns the current activation status.

| Control | Verified state | Remaining work |
| --- | --- | --- |
| Application dependencies | Both locked inventories passed a fresh local scan on October 28: 182 npm packages and 11 Python pins; vulnerability and malware canaries passed | Keep scanning the complete locks before installs and updates |
| Repository configuration | Security fixes, Dependabot configuration and the guarded merger are pushed to main at `e594313` | Verify execution in GitHub |
| Cloud CI and scanning | Latest [manual CI run](https://github.com/j0shcd/risk-metric/actions/runs/40645974867) failed at startup; no successful first cloud scan has been verified | Read its startup annotation, correct the reported cause, then start a fresh CI run |
| Main protection | GitHub reports main protected and status-check enforcement applies to everyone, including admins | Required-check lists are still empty; select the three checks and verify strict, up-to-date enforcement |
| Guarded auto-merge | Repository Allow auto-merge is enabled; the guard refuses merges while the required protection is incomplete | Complete protection, pass cloud CI, and observe an eligible real security patch |
| Dependabot service | Update/graph jobs have run; npm/Python routine updates are disabled in configuration | Verify dependency graph, vulnerability alerts, security-update PRs and the separate malware-alert setting in GitHub |
| Supplemental monitor | Daily security and software updates heartbeat is ACTIVE and its saved prompt includes Risk Metric | This local-app monitor does not establish that GitHub's cloud schedule works |
| Upstream Actions | Bundled Undici findings remain open in the October 27 audit | Follow the upstream-release and November 3 escalation plan below |

### Next bounded steps and ownership

Josh owns the GitHub settings changes because the connected app has no
administration access and browser control was declined. Agents own local
patches, verification and this runbook. Do not widen access, relax protection,
or add a privileged token to work around an unavailable setting.

1. Read **Summary → Annotations** on the latest failed CI run above. October 27
   annotations identified the old exact-Action allowlist; the October 28 run
   also failed at startup, but its annotation has not been retrieved. Confirm
   the current reason before changing code. The API refused to retry the old
   startup-failed run. Use **Run workflow** on the
   [CI workflow](https://github.com/j0shcd/risk-metric/actions/workflows/ci-quality-and-benchmark.yml),
   on main, after correcting the reported setting.
2. If the annotation still identifies the Action allowlist, retain the
   full-SHA requirement and owner restriction, and allow these reviewed pins:

   ```text
   actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
   actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0
   ```

3. In **Settings → Branches → classic main protection**, require
   `dependency-security / scan`, `test-and-benchmark-gate` and
   `web-test-and-build`, with GitHub Actions as their source. Require branches
   up to date and **Do not allow bypassing the above settings**. Keep force
   pushes and deletions disabled. `.github/dependabot.yml` is not the required
   dependency-security check. If the real checks are absent from the selector,
   get CI running first, then refresh the protection form.
4. Verify dependency graph, Dependabot vulnerability alerts, security updates,
   malware alerts and failure notifications in GitHub. Successful routine
   Dependabot jobs and a YAML file do not prove these settings are enabled.
5. Record a successful cloud CI run, a successful first and next scheduled
   security scan, and actual CI/Pages runtime versions. Observe the guard on a
   real eligible patch when one exists; never introduce a vulnerable production
   dependency to manufacture proof. Until then, live merging remains unproven.

After each step, refresh this table from live evidence and link the successful
run or remaining error. Agent restart point: inspect the latest startup
annotation, rather than repeat the dependency audit or rebuild the merger.
There is no open design decision; activation and provider-setting verification
are the remaining work.

## Audit on 2026-10-27

Scope: this repository's npm runtime, build, test and optional dependencies;
the complete Python dependency tree; Node/Python runtimes; and the production
dependencies of its pinned GitHub Actions. Reviewed September–October notices
and all known matching advisories, including older unresolved findings.
Compared the local checkout with public GitHub `main` and retained the newer
remote workflow's placement of Node setup before release scripts.

**Application result:** the initial npm lock had seven affected packages and
24 distinct advisories (four high-severity and three moderate package groups).
The patched lock has 182 npm package entries; Python has 11 exact pins.
OSV-Scanner and npm audit report zero known application dependency findings.
This result does not include the unresolved upstream Actions findings below.

| Dependency | Initial local version | Patched version | Exposure |
| --- | --- | --- | --- |
| Vite | 8.0.16 | 8.3.5 | Development-server file disclosure, editor command injection, custom middleware script execution; several require configuration/platform conditions absent here |
| Vitest and @vitest/mocker | 4.1.9 | 4.1.12 | Mock registration injection and file traversal in development/browser tooling |
| Undici, through jsdom | 7.29.0 | 7.30.1 | HTTP/WebSocket denial of service, TLS and cache-handling issues in test tooling |
| Browserslist | 4.28.2 | 4.29.5 | Resource exhaustion and unsafe custom-stat handling during builds |
| source-map-js | 1.2.1 | 1.2.2 | Resource exhaustion from indexed source maps |
| baseline-browser-mapping | 2.10.38 | 2.11.33 | Process termination on invalid build-tool input |

Public `main` had Undici 7.28.0, rather than the local 7.29.0; it is also
affected. Its direct manifests matched this checkout. Production serves a
static React bundle, not a Vite server. The Pages Functions use platform APIs
and local modules. No React Server Components packages were present.
Version matches establish vulnerable components, not successful exploitation.

Primary examples: [Vite file disclosure](https://github.com/vitejs/vite/security/advisories/GHSA-rq7h-c2jc-7f22),
[Vitest injection](https://github.com/vitest-dev/vitest/security/advisories/GHSA-qxg6-89mg-rqv8),
[Undici content-encoding denial of service](https://github.com/advisories/GHSA-xjj6-f33q-929c).
All 24 IDs, CVE aliases and publication dates are in the dated inventory.

Python previously used open-ended minimums, so neither a complete historical
installation nor the precise deployed Python tree can be reconstructed from
that manifest. `requirements.in` now owns direct bounds and security floors;
`requirements.txt` pins every dependency and distribution hash. Pandas stays
on 2.x to avoid an unrelated model migration. Requests is 2.34.2, urllib3 is
2.8.0, and certifi is 2026.10.23. The [urllib3 HTTPS proxy fix](https://github.com/advisories/GHSA-8988-9cw3-xx77)
is included; no custom proxy/TLS-override use was found in application code.

### Malware assessment

The exact local npm lock versions and installed lock inventory had no known
malware match. Tensorlake 0.5.144 and @subql/common 5.8.3 from the October
campaigns were absent. OSV also found no known malware in the newly pinned
Python/application inventories. A live canary verifies that its feed detects
`MAL-2026-17650` for Tensorlake without downloading the package.

Sources: [Tensorlake investigation](https://www.stepsecurity.io/blog/tensorlake-npm-compromised-hostage-token-worm),
[SubQuery investigation](https://www.stepsecurity.io/blog/subql-ecosystem-compromised).
This was not workstation forensics or an audit of historical CI caches,
credential use, other repositories, or all previously installed packages.
There is no evidence here that justifies declaring the machine compromised.
If a malicious version is later found to have executed, isolate and investigate
the host, remove persistence, and rotate exposed credentials from a clean host.
An upgrade alone cannot close that incident.

## Remaining exposure and next steps

1. **Upstream CI libraries.** Checkout was updated from v6.0.2 to v7.0.1 and
   Setup Python from v6.2.0 to v7.1.0, both pinned by full commit SHA. Their
   production inventories still include Undici 6.27.0 and 6.29.0 respectively.
   Checkout has eight matching advisory IDs; Setup Python has two, both also
   in Checkout's set. These are tracked separately in the dated inventory.
   The shipped JavaScript contains Undici code; production-lock matches do
   not prove every affected function is reachable in these workflows.
   Keep scan/test jobs read-only with no persisted checkout credentials or
   application secrets. Use hosted ephemeral runners and reviewed official
   downloads. Track upstream releases daily; replace the pins as soon as their
   shipped dependencies are patched. If no fix is available by 2026-11-03,
   review a bounded replacement of the affected bootstrap actions or a
   reproducibly rebuilt fork. Close only with verified bundle versions and a
   passing cloud run. No vulnerability suppression was added to hide them.
2. **Local runtime.** The ambient Node was 24.16.0, below the October security
   floor. With explicit approval, the shared Volta default was upgraded to
   24.22.1 and verified with `node --version` and `volta which node`. Existing
   processes still require restart. Tests also used an official, SHA-256-checked
   Node 22.23.4 in a temporary directory.
   Supported floors are 22.23.4, 24.22.1 and 26.12.1. CI now downloads the exact
   patched Node archive with a pinned checksum, without sudo or curl-to-shell.
3. **Python trust store.** CI requests Python 3.11.18 explicitly. It must fail
   rather than fall back if the provider has not published that build yet.
   Python 3.12.16 was available locally for verification; the old 3.11.15
   installation is not the audited runtime. The Python floor and certifi pin
   include the eMudhra/emSign CA response. Verify actual CI and Pages build
   runtimes after rollout; local configuration is not deployment proof.
4. **Cloud activation.** The rollout was pushed to `main` at `8213969`.
   Cloudflare serves JavaScript byte-identical to the tested patched build
   (`index-m-8lZCEt.js`, SHA-256
   `5030091624d58459bdad0c4f2edf6ef47e5fb7f44b7e36c2d3f04717fe874e30`).
   October 27 startup annotations identified an exact-pin allowlist permitting
   only the older Actions. Josh approved updating those pins and chose to make
   the settings changes himself. Current activation evidence and the next
   steps are in the operational status section above. Verify the next scheduled
   publish; do not dispatch alert sending as a test. Check Pages root-directory/version overrides: the
   frontend's `.node-version` requests 22.23.4, but account settings can
   override it. Cloudflare manages the separate Workers runtime; a Node build
   pin does not establish Workers patch status. Enable dependency graph,
   Dependabot alerts, security updates, and the separate malware-alert option.
   Require the security check through branch protection and enable failure
   notifications. The Actions rejection was verified in GitHub
   annotations; the Dependabot settings remain for Josh to enable/verify.

Runtime sources: [Node October security release](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases),
[Python 3.11.18 security release](https://www.python.org/downloads/release/python-31118/),
[Cloudflare build overrides](https://developers.cloudflare.com/pages/configuration/build-image/),
[malware-alert activation](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-malware-alerts).

## Monitoring and safe updates

`.github/workflows/dependency-security.yml` is configured to run daily at 05:17 UTC, on pull
requests and main pushes, and on manual dispatch. CI and daily publishing
call it before installing project dependencies. It needs only read access
and no application secrets. Scanner download failures, checksum mismatches,
advisory-service failures and known findings fail the job. GitHub schedules
can be delayed or disabled; check run freshness as well as the last result.

`scripts/security-check.sh` verifies the official OSV-Scanner v2.7.0 binary
against a committed SHA-256, then parses explicit lockfiles with dependency
resolution and call analysis disabled. It first checks metadata-only canaries
for vulnerable Vite, vulnerable Requests and known npm malware. It never
installs those fixtures. Online scanning sends package identifiers and
versions to OSV; npm audit sends dependency metadata to npm. No application
data or secrets are needed. Known-advisory checks cannot detect undisclosed
malware or prove that a correctly signed package is safe.

Dependabot is configured for security-update PRs for npm and Python; routine
version PRs are disabled with `open-pull-requests-limit: 0`. Security updates
have their own GitHub limit and bypass cooldown. Actions version checks remain
weekly because bundled-library fixes may arrive without an advisory against
the action itself. Routine Actions updates have a seven-day cooldown. There is
no automatic merge for routine updates. The guarded security-patch policy below
is pushed and authorized, but remains inactive until branch protection is
complete and cloud CI is verified. CI rejects Python lock upgrades outside `requirements.in`.
The existing daily Codex security/software-updates automation also
tracks runtime releases, residual Actions findings and cloud-monitor health.
That is a local-app monitor, separate from GitHub's cloud schedule.

### Guarded security-patch auto-merge

Josh authorized automatic merging of narrowly eligible security patches on
2026-10-27. The implementation is in `scripts/lib/dependabot-policy.mjs` and
`scripts/dependabot-auto-merge.mjs`; the privileged workflow is
`.github/workflows/dependabot-auto-merge.yml`.

Only a completed, successful `CI Quality And Benchmark` pull-request run can
start it. The job checks out **main only**, does not install dependencies, and
never executes PR code or downloads PR artifacts/caches. It uses the built-in
GitHub token only; no PAT, app key, application secret or new service is needed.

Every condition must hold:

- An open, non-draft, same-repository Dependabot PR targets main. Author IDs and
  all commit signatures are checked; human-authored follow-up commits deny it.
- The exact current head/base pair passed all three canonical CI jobs, with no
  missing, skipped, stale or failing job: `dependency-security / scan`,
  `test-and-benchmark-gate`, and `web-test-and-build`.
- Only `web/package.json` plus `web/package-lock.json`, or only
  `requirements.txt`, changed. Every resolved upgrade is a strict X.Y.Z patch
  increase within the same major/minor. No added/removed packages, source-bound
  changes, script/engine changes, registry changes, or same-version hash changes
  are accepted. npm integrity and Python distribution hashes stay mandatory.
- OSV confirms at least one reviewed vulnerability affected an old version and
  no known finding affects any proposed changed version. Labels and PR wording
  are not security evidence. Known malware needs incident review and cannot
  auto-merge. Missing/malformed/incomplete responses or service errors deny it.
- Repository **Allow auto-merge** is enabled, and main has a classic branch
  protection rule requiring the three checks, up-to-date branches, and admin
  enforcement. Missing or unreadable protection data denies merging; there is
  no permission-broadening fallback.

The sole write is GitHub's squash-merge mutation with `expectedHeadOid` set to
that verified head. GitHub enforces its current protections and reviews; the
job never approves a PR, forces a merge, or bypasses a rule. It does not leave a
native auto-merge request queued against a PR that may later change. If a review
or deployment requirement is still outstanding, merge is withheld; rerun CI
once those requirements are satisfied to reevaluate. Minor/major/prerelease
updates, Actions/runtime changes, new dependencies and ambiguous cases remain
manual. Security updates that require them are still reported, not discarded.

Limits: these guards do not prove a new package release is free of undisclosed
malware. Candidate code runs only in the existing unprivileged CI jobs with
install scripts disabled. Validation allows at most two dependency files,
1 MiB per file, 12 changed packages, 20 signed commits and 40 unique advisory
lookups. Requests time out after 20 seconds; the workflow is bounded to ten
minutes. Failures withhold the write. GitHub-token merges do not themselves
start other Actions push workflows; the next scheduled scan remains important.

Activation status is owned by the operational status section above. The guard
currently supports classic branch protection; a ruleset-only setup needs
explicit support. Existing routine upgrade PRs are not eligible. Disable
**Allow auto-merge** to disarm the guard immediately.

Verification: Node fixtures exercise successful guarded merging, dry-run
withholding, identity/signature checks, every policy rejection and API errors.
Workflow sentinels protect the trusted checkout and single SHA-guarded merge
sink. Live OSV metadata accepted Vitest 4.1.9 → 4.1.12 as a known security patch
(655 ms), and refused Requests 2.32.4 because newer findings still affect it.
All 80 Node tests passed (56 guard cases plus 24 existing tests), along with
two privileged-workflow sentinels and four Node setup regressions. Deliberately
removing bot validation, security evidence, the expected-head binding, or
malformed-result rejection made the regressions fail; all were restored.
Independent review rechecked the production boundary and final fixtures.
No production PR has been merged by this implementation.

Selected approach: GitHub-native Dependabot plus open-source OSV avoids an
additional commercial integration for this public repository. Alternatives
reviewed were Renovate (more updater configuration), npm audit/pip-audit
(useful cross-checks; unresolved pip resolution can execute package code),
Socket (additional malware behavior analysis and app permissions), and Snyk
(additional account and usage limits). Reassess Socket if known-advisory
coverage proves insufficient. Do not install another app silently.

Run locally before installing or changing dependencies:

```sh
bash scripts/security-check.sh
python -m pip install --require-hashes --only-binary=:all: -r requirements.txt
cd web && npm run reinstall
```

The frontend installer resolves requested updates as metadata, scans the new
lock, then runs `npm ci --ignore-scripts` outside iCloud. `.npmrc` disables
dependency install scripts; trusted cleanup/data sync are explicit commands
inside dev/build/test, since automatic pre-hooks are also suppressed.
Cloudflare must retain this `.npmrc` in its build root.

To refresh Python pins, use the command recorded at the top of
`requirements.txt`, on Python 3.11, with `--upgrade` when deliberately updating
existing pins. Scan the result before installing it. Review lock diffs, run
backend tests, frontend tests/build and alert/release tests, then commit the
bounded update. Do not push or deploy as a side effect of a routine audit.

## Verification record

The 2026-10-27 run verified zero known findings in both application inventories,
malware/CVE canary rejection, checksum rejection, 42 frontend tests, the
production build and 24 alert/release tests, using Node 22.23.4. The full Python suite
passed 138 tests on Python 3.12.16; the final security-policy file separately
passed four checks. The deployed UI without unrelated local edits passed 33
frontend tests and its production build; four integrated Node setup regressions
also passed. Regression checks were deliberately made to fail by
restoring old Vite/Requests versions, disabling scanner checksum validation,
and suppressing trusted frontend preparation, then restored and rerun.
Independent review checked workflow syntax, install ordering and package setup
behavior. The application deployment was verified. GitHub scans had not passed
their first cloud run; see the operational status section for current evidence.
The existing daily security automation was updated and remains ACTIVE; its
Risk Metric coverage is confirmed in the saved automation prompt. Dependabot
version-update jobs ran on GitHub and created six routine PRs; npm/Python
configuration was then narrowed to security fixes. Account-level security
updates and malware alerts still need their settings verified.
