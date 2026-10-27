"""The privileged workflow must never run code from a pull request."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AutoMergeWorkflowTests(unittest.TestCase):
    def test_only_completed_successful_pr_ci_can_invoke_the_merge_guard(self):
        source = (ROOT / ".github/workflows/dependabot-auto-merge.yml").read_text()
        self.assertIn("workflow_run:", source)
        self.assertIn('workflows: ["CI Quality And Benchmark"]', source)
        self.assertIn("types: [completed]", source)
        self.assertIn("github.event.workflow_run.event == 'pull_request'", source)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", source)
        self.assertNotIn("pull_request_target:", source)
        self.assertIn("ref: main", source)
        self.assertIn("persist-credentials: false", source)
        self.assertNotIn("head_sha", source)
        self.assertNotIn("download-artifact", source)
        self.assertNotIn("cache:", source)
        self.assertEqual(re.findall(r"(?m)^        run: (.+)$", source), ["node scripts/dependabot-auto-merge.mjs"])
        self.assertNotIn("secrets.", source)
        self.assertIn("GH_TOKEN: ${{ github.token }}", source)

    def test_only_one_head_guarded_merge_sink_exists(self):
        driver = (ROOT / "scripts/dependabot-auto-merge.mjs").read_text()
        self.assertEqual(driver.count("mergePullRequest(input: $input)"), 1)
        self.assertIn("expectedHeadOid: pr.head.sha", driver)
        self.assertNotIn("enablePullRequestAutoMerge", driver)
        self.assertNotIn("node:child_process", driver)
        self.assertLess(driver.index("if (dryRun) return result;"), driver.index("const merged ="))
        ci = (ROOT / ".github/workflows/ci-quality-and-benchmark.yml").read_text()
        self.assertIn("node --test scripts/lib/*.test.mjs web/functions/api/_lib/*.test.mjs", ci)


if __name__ == "__main__":
    unittest.main()
