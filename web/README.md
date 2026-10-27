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
syncs local data artifacts and runs `npm run clean:icloud`, which
removes byte-identical iCloud collision files, removes empty collision
directories, and moves differing collision copies into
`.icloud-conflicts.nosync/` so they are outside iCloud sync and can be reviewed
without breaking the app.

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

`.npmrc` disables dependency install scripts. The explicit setup commands
preserve cleanup and data sync even though npm also suppresses automatic
`pre*` hooks under that setting. Use the version in `.node-version`; the
full [security record](../docs/security.md) covers runtime floors, cloud
monitoring and the remaining upstream GitHub Actions findings.
