# Security maintenance

This is the maintainer record for dependency exposure, monitoring, and recovery.
Update it when an audit, runtime change, or monitoring activation changes the
facts below. The [dated inventory](artifacts/dependency-audit-2026-10-27.json)
retains the exact package versions and advisory IDs from this audit.

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
   GitHub rejected Dependency security and CI at startup because its exact-pin
   allowlist still permits only the two older Actions. Josh approved updating
   those two pins and chose to make the account-settings changes himself.
   After he updates the allowlist, rerun the failed security/CI runs and verify
   the next scheduled publish; do not dispatch alert sending as a test. Check Pages root-directory/version overrides: the
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

`.github/workflows/dependency-security.yml` runs daily at 05:17 UTC, on pull
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
no automatic merge. CI rejects Python lock upgrades outside `requirements.in`. The existing daily Codex security/software-updates automation also
tracks runtime releases, residual Actions findings and cloud-monitor health.
That is a local-app monitor, separate from GitHub's cloud schedule.

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
behavior. The application deployment is verified; GitHub scans remain blocked
by the account allowlist until its approved update is applied.
The existing daily security automation was updated and remains ACTIVE; its
Risk Metric coverage is confirmed in the saved automation prompt. Dependabot
version-update jobs ran on GitHub and created six routine PRs; npm/Python
configuration was then narrowed to security fixes. Account-level security
updates and malware alerts still need their settings verified.
