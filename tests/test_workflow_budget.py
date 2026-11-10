"""Routine commits must not consume Actions runners or depend on their billing."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def events(source):
    block = source.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    return set(re.findall(r"(?m)^  ([a-z_]+):", block))


class WorkflowBudgetTests(unittest.TestCase):
    def test_only_automatic_runner_is_the_daily_security_scan(self):
        workflows = {p.name: p.read_text() for p in (ROOT/".github/workflows").glob("*.yml")}
        self.assertEqual(set(workflows), {"ci-quality-and-benchmark.yml", "dependency-security.yml",
                                         "daily-web-publish.yml", "model-acceptance.yml"})
        for name, source in workflows.items():
            expected = {"workflow_dispatch"}
            if name == "dependency-security.yml":
                expected |= {"schedule", "workflow_call"}
                self.assertIn('cron: "17 5 * * *"', source)
            self.assertEqual(events(source), expected, name)
        self.assertTrue((ROOT/".github/dependabot.yml").exists())

    def test_optional_validation_does_not_run_performance_experiments(self):
        source = (ROOT/".github/workflows/ci-quality-and-benchmark.yml").read_text()
        self.assertIn("python -m unittest discover -s tests", source)
        self.assertIn("node --test scripts/lib/*.test.mjs", source)
        self.assertIn("npm test", source)
        self.assertNotIn("benchmark_gate", source)
        self.assertNotIn("risk_engine.evaluation.cli", source)


if __name__ == "__main__":
    unittest.main()
