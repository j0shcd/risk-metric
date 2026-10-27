#!/usr/bin/env bash
# Parse locked inventories only. Never install or resolve project dependencies.
set -euo pipefail
cd "$(dirname "$0")/.."

version=2.7.0
case "$(uname -s)/$(uname -m)" in
  Linux/x86_64)
    platform=linux_amd64
    expected=160c6253e2922e9e0a6a9771c5c4c40a4b3c6090b34a3cdd5e80c96cc2e4218b
    ;;
  Darwin/arm64)
    platform=darwin_arm64
    expected=d4926ef8da134332543be276dff157e4c170f99ad91fc48e89448a8816bdf70b
    ;;
  *) echo 'Unsupported scanner platform; add a verified upstream digest first.' >&2; exit 2 ;;
esac

if [[ -n "${OSV_SCANNER:-}" ]]; then
  scanner="$OSV_SCANNER"
else
  security_tmp="$(mktemp -d "${TMPDIR:-/tmp}/risk-security.XXXXXX")"
  trap 'rm -rf "$security_tmp"' EXIT
  scanner="$security_tmp/osv-scanner"
  curl --fail --location --retry 2 --connect-timeout 15 --max-time 300 \
    "https://github.com/google/osv-scanner/releases/download/v${version}/osv-scanner_${platform}" \
    --output "$scanner"
fi

actual="$(shasum -a 256 "$scanner" | cut -d ' ' -f 1)"
if [[ "$actual" != "$expected" ]]; then
  echo 'Scanner checksum mismatch; refusing to execute.' >&2
  exit 2
fi
# Leave a caller-supplied binary untouched (including permissions).
if [[ -z "${OSV_SCANNER:-}" ]]; then chmod +x "$scanner"; fi

if [[ "$#" -eq 0 ]]; then
  OSV_SCANNER="$scanner" python3 scripts/test-security-gate.py
  set -- --lockfile=web/package-lock.json --lockfile=requirements.txt
fi
"$scanner" scan source --no-resolve --no-call-analysis=go "$@"
