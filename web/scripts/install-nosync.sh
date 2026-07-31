#!/usr/bin/env bash
#
# This project lives under ~/Documents, which iCloud Drive syncs. iCloud races
# npm's atomic renames during install, producing "<pkg> 2" collision dirs and
# corrupt installs (missing files like vite/dist/node/cli.js).
#
# Fix: install in a temp dir OUTSIDE iCloud, then move the finished tree into
# node_modules.nosync (the ".nosync" suffix is excluded from iCloud sync) and
# expose it via a node_modules symlink. The install never touches iCloud, so it
# can't collide. Use this instead of a bare `npm install`.
#
# Usage:
#   npm run reinstall            # clean install from package-lock.json
#   npm run reinstall <pkg>...   # add/update packages
#
set -euo pipefail
cd "$(dirname "$0")/.."

node scripts/clean-icloud-conflicts.mjs --apply

TMP="$(mktemp -d "${TMPDIR:-/tmp}/rm-web-install.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

cp package.json "$TMP"/
[ -f package-lock.json ] && cp package-lock.json "$TMP"/

echo "[install-nosync] installing in $TMP (outside iCloud)..."
( cd "$TMP" && npm install "$@" )

# Bring back any lockfile/manifest changes npm made (e.g. when adding packages).
cp "$TMP/package.json" ./package.json
[ -f "$TMP/package-lock.json" ] && cp "$TMP/package-lock.json" ./package-lock.json

echo "[install-nosync] relocating node_modules into iCloud-excluded node_modules.nosync..."
rm -rf node_modules.nosync node_modules
mv "$TMP/node_modules" node_modules.nosync
ln -s node_modules.nosync node_modules
node scripts/clean-icloud-conflicts.mjs --apply

echo "[install-nosync] done. node_modules -> node_modules.nosync ($(ls node_modules | wc -l | tr -d ' ') entries)"
