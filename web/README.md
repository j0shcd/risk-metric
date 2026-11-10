# risk-metric-web

Dashboard frontend (Vite + React).

## Setup

> [!IMPORTANT]
> Install with `npm run reinstall`, **not** a bare `npm install`.

This repo lives under `~/Documents`, which iCloud Drive syncs. iCloud races
npm's file operations during install, producing `"<pkg> 2"` collision
directories and corrupt installs (e.g. a missing `vite/dist/node/cli.js`,
surfacing as `vite: command not found` or `ERR_MODULE_NOT_FOUND`).

`npm run reinstall` (→ `scripts/install-nosync.sh`) avoids this: it installs in
a temp dir outside iCloud, then moves the result into `node_modules.nosync`
(the `.nosync` suffix is excluded from iCloud sync) and symlinks
`node_modules` → `node_modules.nosync`.
It scans the candidate lockfile for known vulnerabilities/malware before
installing it with `npm ci --ignore-scripts`. Requested updates are first
resolved as metadata only. The scanner uses curl and shasum; its default
regression canary also needs Python 3.

```sh
npm run reinstall            # clean install from package-lock.json
npm run reinstall <pkg>...   # add/update packages
```

A bare `npm install` will work momentarily but clobbers the symlink (npm
rewrites `node_modules` as a real directory in the iCloud-synced tree), which
reintroduces the collisions. If you see `"<pkg> 2"` directories, run
`npm run reinstall` to repair.

The web scripts explicitly run `npm run prepare:web` before dev/build/test. It
recreates `public/data` from the active release and runs `npm run clean:icloud`, which
removes byte-identical iCloud collision files, removes empty collision
directories, and moves differing collision copies into
`.icloud-conflicts.nosync/` so they are outside iCloud sync and can be reviewed
without breaking the app.

Preparation can remove tracked copies of older generated releases. Keep those
generated changes out of UI commits when they were clean before the run. For
read-only verification of an already prepared checkout, run the installed
`./node_modules/.bin/vitest run` from `web/` to skip the preparation hooks.

## Scripts

| Command | Description |
| --- | --- |
| `npm run dev` | Start the Vite dev server |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Preview the production build |
| `npm test` | Run the test suite (Vitest) |
| `npm run check:icloud` | Dry-run iCloud collision cleanup |
| `npm run clean:icloud` | Clean/quarantine iCloud collision files |
| `npm run reinstall` | iCloud-safe dependency install (see Setup) |
| `npm run prepare:web` | Clean conflict copies and synchronize local data artifacts |

`dev`, `build`, and `test` work normally through the `node_modules` symlink — no
special handling needed.

Track record uses the existing November 10 evidence CSVs under
`docs/artifacts/target-readout-2026-11-10/` through Vite raw imports. The dev server
allows that public artifact directory in addition to `web/`; it does not expose
the whole repository. `src/dcaEvidence.js` derives periods and summaries from those
files and scales results for the monthly amount. The comparison module loads only
when Track record is selected. There is no second dataset,
provider request, new public API, saved preference or model run. The comparator is
the recorded incumbent buying rule; experimental variants remain in the disclosure.

For a manual check, preview the build and open Track record. The initial period is
November 2022–October 2026 at $100/month. Select December 2014–November 2018 and
$250.25: both budgets become $12,012, with 19.31074872 BTC for regular buying and
5.75120461 BTC for score-based buying. Empty, zero, fractional-cent and out-of-range
amounts replace the result with an inline error. Supported amounts are $0.01 to
$1,000,000 with up to two decimal places. At 390px, controls stack and expanded
comparison rows keep their column labels. `npm test` includes a separate ledger
check of all 96 periods against the frozen source and a deliberate double-fee
mutation was rejected during implementation verification.

`.npmrc` disables dependency install scripts. The explicit setup commands
preserve cleanup and data sync even though npm also suppresses automatic
`pre*` hooks under that setting. Use the version in `.node-version`; the
full [security record](../docs/security.md) covers runtime floors, cloud
monitoring and the remaining upstream GitHub Actions findings.
