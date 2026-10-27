"""Security policy checks that run without installing project dependencies."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DependencySecurityTests(unittest.TestCase):
    def test_python_inventory_is_fully_pinned_and_hashed(self):
        text = (ROOT / "requirements.txt").read_text().replace("\\\n", " ")
        pins = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.fullmatch(r"([\w-]+)==([\d.]+)(?:\s+--hash=sha256:[a-f0-9]{64})+", line)
            self.assertIsNotNone(match, f"Unpinned or unhashed requirement: {line}")
            self.assertNotIn(match[1], pins)
            pins[match[1]] = tuple(map(int, match[2].split(".")))
        self.assertTrue({"numpy", "pandas", "requests", "urllib3"} <= pins.keys())
        self.assertGreaterEqual(pins["requests"], (2, 34, 2))
        self.assertGreaterEqual(pins["urllib3"], (2, 8, 0))
        # Keep generated pins within the supported source bounds.
        for source in (ROOT / "requirements.in").read_text().splitlines():
            source = source.strip()
            if not source or source.startswith("#"):
                continue
            match = re.fullmatch(r"([\w-]+)(.+)", source)
            self.assertIsNotNone(match, source)
            self.assertIn(match[1], pins)
            for constraint in match[2].split(","):
                bound = re.fullmatch(r"(>=|<)([\d.]+)", constraint)
                self.assertIsNotNone(bound, constraint)
                expected = tuple(map(int, bound[2].split(".")))
                if bound[1] == ">=":
                    self.assertGreaterEqual(pins[match[1]], expected, source)
                else:
                    self.assertLess(pins[match[1]], expected, source)

    def test_npm_artifacts_have_registry_urls_and_integrity(self):
        manifest = json.loads((ROOT / "web/package.json").read_text())
        lock = json.loads((ROOT / "web/package-lock.json").read_text())
        self.assertEqual(lock["lockfileVersion"], 3)
        self.assertEqual(lock["packages"][""]["dependencies"], manifest["dependencies"])
        self.assertEqual(lock["packages"][""]["devDependencies"], manifest["devDependencies"])
        for name, package in lock["packages"].items():
            if not name:
                continue
            self.assertTrue(package["resolved"].startswith("https://registry.npmjs.org/"), name)
            self.assertRegex(package["integrity"], r"^sha512-[A-Za-z0-9+/]+=*$", name)
        for package, floor in [("vite", (8, 3, 3)), ("vitest", (4, 1, 12)), ("undici", (7, 30, 1))]:
            version = lock["packages"][f"node_modules/{package}"]["version"]
            self.assertGreaterEqual(tuple(map(int, version.split("."))), floor)
        self.assertIn("ignore-scripts=true", (ROOT / "web/.npmrc").read_text().splitlines())

    def test_scanner_rejects_untrusted_binary_without_executing_or_modifying_it(self):
        with tempfile.TemporaryDirectory(prefix="risk security $(not-a-command) ") as directory:
            binary = Path(directory) / "scanner"
            marker = Path(directory) / "executed"
            original = f'#!/bin/sh\ntouch "{marker}"\n'.encode()
            binary.write_bytes(original)
            binary.chmod(0o700)
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/security-check.sh")],
                env={**os.environ, "OSV_SCANNER": str(binary)},
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("checksum mismatch", result.stderr)
            self.assertFalse(marker.exists())
            self.assertEqual(binary.read_bytes(), original)

    def test_trusted_web_preparation_is_explicit_when_install_scripts_are_disabled(self):
        scripts = json.loads((ROOT / "web/package.json").read_text())["scripts"]
        for command in ["dev", "build", "test", "test:watch"]:
            self.assertTrue(scripts[command].startswith("npm run prepare:web && "), command)
        for hook in ["predev", "prebuild", "pretest"]:
            self.assertNotIn(hook, scripts)


if __name__ == "__main__":
    unittest.main()
