"""Live regression: known-bad inventories must fail without package installation.

Set OSV_SCANNER to the checksum-verified local binary to avoid re-downloading it.
The fixtures contain metadata only; never install these packages.
"""
import json
import subprocess
import tempfile
from pathlib import Path


root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="risk-security-canary-") as directory:
    folder = Path(directory)
    npm = folder / "package-lock.json"
    npm.write_text(json.dumps({
        "name": "security-canary-never-install", "version": "1.0.0", "lockfileVersion": 3,
        "packages": {
            "": {"name": "security-canary-never-install", "version": "1.0.0", "dependencies": {"vite": "8.0.16", "tensorlake": "0.5.144"}},
            "node_modules/vite": {"version": "8.0.16", "resolved": "https://registry.npmjs.org/vite/-/vite-8.0.16.tgz"},
            "node_modules/tensorlake": {"version": "0.5.144", "resolved": "https://registry.npmjs.org/tensorlake/-/tensorlake-0.5.144.tgz"},
        },
    }))
    python = folder / "requirements.txt"
    python.write_text("requests==2.31.0\n")
    result = subprocess.run([
        "bash", str(root / "scripts/security-check.sh"), "--format=json",
        f"--lockfile={npm}", f"--lockfile={python}",
    ], capture_output=True, text=True, check=False)
    if result.returncode != 1:
        raise SystemExit(f"Expected vulnerability exit 1; got {result.returncode}\n{result.stderr}\n{result.stdout}")
    report = json.loads(result.stdout)
    identifiers = {
        vuln["id"]
        for source in report["results"]
        for package in source["packages"]
        for vuln in package.get("vulnerabilities", [])
    }
    expected = {"GHSA-9jrq-w75r-8gcw", "MAL-2026-17650", "GHSA-9hjg-9r4m-mvj7"}
    if not expected <= identifiers:
        raise SystemExit(f"Missing known CVE/malware canaries: {expected - identifiers}\n{result.stderr}\n{result.stdout}")
    print("PASS: vulnerable Vite, vulnerable Requests, and known npm malware rejected without installation")
