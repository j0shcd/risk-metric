import os
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.yml"))
ACTION = ROOT / ".github/actions/setup-node/action.yml"
PIN = (ROOT / "web/.node-version").read_text().strip()
DIGEST = "1805bcd35e6815559bd2eb97db438d3fdb0eb3a5e6a977b7c1badca76337e9ce"


def setup_script():
    match = re.search(r"      run: \|\n((?:        [^\n]*\n)+)", ACTION.read_text())
    if match is None:
        raise AssertionError("Missing shared Node setup shell")
    return textwrap.dedent(match.group(1))


class WorkflowNodeSetupTests(unittest.TestCase):
    def run_setup(self, installed_version=PIN, checksum_ok=True):
        with tempfile.TemporaryDirectory(prefix="node setup ") as directory:
            root = Path(directory)
            shadow = root / "runner/bin"
            mocks = root / "mocks"
            web = root / "web"
            for path in (shadow, mocks, web):
                path.mkdir(parents=True)
            (web / ".node-version").write_text(PIN + "\n")

            def executable(path, body):
                path.write_text("#!/bin/sh\nset -eu\n" + body + "\n")
                path.chmod(0o755)

            executable(shadow / "node", "echo v24.16.0")
            executable(shadow / "npm", "echo wrong-runner-npm")
            executable(shadow / "npx", "echo wrong-runner-npx")
            executable(shadow / "python", "echo configured-python")
            executable(mocks / "uname", 'case "$1" in -s) echo Linux;; -m) echo x86_64;; *) exit 1;; esac')
            executable(mocks / "curl", 'while [ "$#" -gt 0 ]; do if [ "$1" = --output ]; then echo fixture > "$2"; exit 0; fi; shift; done; exit 1')
            executable(mocks / "sha256sum", 'read -r digest archive; test "$digest" = "$EXPECTED_DIGEST"; test "$CHECKSUM_OK" = 1')
            # Never download or extract real artifacts in this shell regression.
            executable(mocks / "tar", '''
                test "$1" = -xJf
                test "$3" = -C
                touch "$EXTRACTED_MARKER"
                target="$4/node-v$PIN-linux-x64/bin"
                mkdir -p "$target"
                printf '#!/bin/sh\\necho v%s\\n' "$INSTALLED_VERSION" > "$target/node"
                printf '#!/bin/sh\\necho patched-npm\\n' > "$target/npm"
                printf '#!/bin/sh\\necho patched-npx\\n' > "$target/npx"
                chmod +x "$target/node" "$target/npm" "$target/npx"
            ''')
            github_path = root / "github-path"
            github_path.touch()
            extracted = root / "extracted"
            env = {
                **os.environ,
                "PATH": f"{shadow}:{mocks}:{os.environ['PATH']}",
                "GITHUB_PATH": str(github_path), "RUNNER_TEMP": str(root),
                "EXPECTED_DIGEST": DIGEST, "CHECKSUM_OK": str(int(checksum_ok)),
                "EXTRACTED_MARKER": str(extracted), "PIN": PIN,
                "INSTALLED_VERSION": installed_version,
            }
            result = subprocess.run(
                ["/bin/bash", "-eo", "pipefail", "-c", setup_script() + "\npython --version"],
                cwd=root, env=env, capture_output=True, text=True, timeout=10,
            )
            entries = github_path.read_text().splitlines()
            next_step = subprocess.run(
                ["/bin/bash", "-c", "node --version && npm --version && npx --version && python --version"],
                env={**env, "PATH": ":".join([*reversed(entries), env["PATH"]])},
                capture_output=True, text=True, timeout=10,
            )
            return result, next_step, entries, extracted.exists()

    def test_verified_node_wins_in_following_steps_without_shadowing_python(self):
        result, next_step, _, _ = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(), [f"v{PIN}", "configured-python"])
        self.assertEqual(next_step.returncode, 0, next_step.stderr)
        self.assertEqual(next_step.stdout.splitlines(), [f"v{PIN}", "patched-npm", "patched-npx", "configured-python"])

    def test_version_mismatch_does_not_select_unverified_runtime(self):
        for version in ("22.23.3", "24.22.1", "22.23.5"):
            with self.subTest(version=version):
                result, _, entries, _ = self.run_setup(installed_version=version)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(entries, [])

    def test_bad_checksum_is_rejected_before_extraction_or_selection(self):
        result, _, entries, extracted = self.run_setup(checksum_ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(entries, [])
        self.assertFalse(extracted)

    def test_setup_precedes_every_node_command(self):
        consumers = 0
        for workflow in WORKFLOWS:
            seen_setup = False
            for step in re.split(r"(?m)^      - name: ", workflow.read_text())[1:]:
                if "uses: ./.github/actions/setup-node" in step:
                    seen_setup = True
                    consumers += 1
                elif re.search(r"\b(?:node|npm)\s", step):
                    self.assertTrue(seen_setup, f"{workflow.name}: {step.splitlines()[0]}")
            self.assertNotIn("deb.nodesource.com", workflow.read_text())
        self.assertEqual(consumers, 2)


if __name__ == "__main__":
    unittest.main()
