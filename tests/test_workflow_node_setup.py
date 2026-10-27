import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.yml"))


def setup_script(workflow):
    match = re.search(
        r"      - name: Setup Node[^\n]*\n        run: \|\n((?:          [^\n]*\n)+)",
        workflow.read_text(),
    )
    if match is None:
        raise AssertionError(f"Missing Node setup in {workflow.name}")
    return textwrap.dedent(match.group(1))


class WorkflowNodeSetupTests(unittest.TestCase):
    def run_setup(self, workflow, installed_version="22.23.4"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installed = root / "installed/bin"
            shadow = root / "runner/bin"
            mocks = root / "mocks"
            for path in (installed, shadow, mocks):
                path.mkdir(parents=True)

            def executable(path, body):
                path.write_text("#!/bin/sh\n" + body + "\n")
                path.chmod(0o755)

            real_node = shlex.quote(shutil.which("node"))
            for path, version in ((installed, installed_version), (shadow, "24.21.0")):
                override = shlex.quote(
                    f'Object.defineProperty(process.versions, "node", {{value: "{version}"}});'
                )
                executable(
                    path / "node",
                    f'if [ "$1" = "-e" ]; then exec {real_node} -e {override}"$2"; '
                    f'elif [ "$1" = "-p" ]; then echo {version.split(".")[0]}; '
                    f'else echo v{version}; fi',
                )
                executable(path / "npm", f"echo npm-for-node-{version}")
                executable(path / "npx", f"echo npx-for-node-{version}")
            executable(shadow / "python", "echo configured-python")
            executable(installed / "python", "echo wrong-system-python")
            # Installation succeeds, exactly as in the reported failure. Never
            # run apt, sudo, or network calls from this regression test.
            executable(mocks / "curl", "echo ':'")
            executable(mocks / "sudo", 'if [ "$1" = "-E" ]; then cat >/dev/null; fi')
            github_path = root / "github-path"
            github_path.touch()
            env = {
                **os.environ,
                "PATH": f"{shadow}:{mocks}:{os.environ['PATH']}",
                "GITHUB_PATH": str(github_path),
                "RUNNER_TEMP": str(root),
            }
            # Relocate the package's Linux installation prefix into the fixture
            # so the actual workflow shell can run safely on macOS as well.
            script = setup_script(workflow).replace("/usr/bin", str(installed))
            result = subprocess.run(
                ["/bin/bash", "-eo", "pipefail", "-c", script + "\npython --version"],
                env=env, capture_output=True, text=True, timeout=10,
            )
            entries = github_path.read_text().splitlines()
            next_step = subprocess.run(
                ["/bin/bash", "-c", "node --version && npm --version && npx --version && python --version"],
                env={**env, "PATH": ":".join([*reversed(entries), env["PATH"]])},
                capture_output=True, text=True, timeout=10,
            )
            return result, next_step

    def test_installed_node_wins_now_and_in_following_steps(self):
        self.assertEqual(len(WORKFLOWS), 2)
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow.name):
                result, next_step = self.run_setup(workflow)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout.splitlines(), ["v22.23.4", "npm-for-node-22.23.4", "configured-python"])
                self.assertEqual(next_step.returncode, 0, next_step.stderr)
                self.assertEqual(next_step.stdout.splitlines(), ["v22.23.4", "npm-for-node-22.23.4", "npx-for-node-22.23.4", "configured-python"])

    def test_unpatched_or_wrong_installed_version_is_rejected(self):
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow.name):
                for version in ("22.22.0", "22.23.3", "24.22.1"):
                    result, _ = self.run_setup(workflow, installed_version=version)
                    self.assertNotEqual(result.returncode, 0, version)

    def test_newer_22_patches_are_accepted(self):
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow.name):
                for version in ("22.23.5", "22.24.0"):
                    result, _ = self.run_setup(workflow, installed_version=version)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_setup_precedes_every_node_command(self):
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow.name):
                seen_setup = False
                for step in re.split(r"(?m)^      - name: ", workflow.read_text())[1:]:
                    if step.startswith("Setup Node"):
                        seen_setup = True
                    elif re.search(r"\bnode\s", step):
                        self.assertTrue(seen_setup, step.splitlines()[0])


if __name__ == "__main__":
    unittest.main()
