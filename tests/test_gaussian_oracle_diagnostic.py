import hashlib
from pathlib import Path
import unittest

import numpy as np

from research.gaussian_oracle_diagnostic import paired_summary, run
from research.search_qualification import SearchConfig


class GaussianOracleDiagnosticTests(unittest.TestCase):
    def test_summary_uses_paired_whole_worlds_and_ratio_of_total_losses(self):
        reference = np.array([[1., 1.], [3., 3.]])
        candidate = np.array([[0., 0.], [3., 3.]])
        summary = paired_summary(reference, candidate, 6)
        self.assertEqual(summary["crps_skill_percent"], 25.)
        self.assertEqual(summary["mean_crps_improvement"], .5)
        self.assertEqual(summary["worlds"], 2)
        repeated = paired_summary(np.repeat(reference, 10, axis=1), np.repeat(candidate, 10, axis=1), 6)
        # Duplicating overlapping rows within worlds cannot manufacture precision.
        self.assertEqual(summary["skill_world_bootstrap_95"], repeated["skill_world_bootstrap_95"])
        self.assertEqual(summary["mean_improvement_world_bootstrap_95"], repeated["mean_improvement_world_bootstrap_95"])
        with self.assertRaises(ValueError): paired_summary(reference, candidate[:, :1], 6)

    def test_posthoc_replay_keeps_parent_failure_and_all_horizons(self):
        from dataclasses import asdict
        config = asdict(SearchConfig(evaluation_worlds=2))
        source = Path(__file__).resolve().parents[1]/"research/search_qualification.py"
        reference = {"protocol": "whole-path-distribution-search-v1", "all_criteria_pass": False, "config": config,
                     "registration": {"code_sha256": {"search_qualification.py": hashlib.sha256(source.read_bytes()).hexdigest()}}}
        summary, forecasts = run(reference)
        self.assertFalse(summary["parent_all_criteria_pass"])
        self.assertEqual(summary["role"], "post_hoc_explanation_not_qualification")
        self.assertEqual(set(summary["results"]), {"12", "24", "48"})
        self.assertEqual(len(forecasts), 2*24*3)
        for row in forecasts:
            self.assertEqual(row["execution_step"], row["decision_step"]+1)
            self.assertEqual(row["end_step"], row["execution_step"]+row["horizon"])
        reference["registration"]["code_sha256"]["search_qualification.py"] = "changed"
        with self.assertRaisesRegex(ValueError, "parent generator/search changed"): run(reference)


if __name__ == "__main__":
    unittest.main()
