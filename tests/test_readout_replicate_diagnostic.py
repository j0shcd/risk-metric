import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from research.location_scale_search import ContinuousConfig, prepare, search_statistics
from research.readout_replicate_diagnostic import run
from research.search_qualification import SearchConfig, world


ROOT = Path(__file__).resolve().parents[1]


class ReadoutReplicateDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads(
            (ROOT / "docs/artifacts/location-scale-search-2026-11-06.json").read_bytes()
        )
        # Keep the registered recipe and exposed seeds; shorten only replication.
        cls.reference["config"]["positive_worlds"] = 2
        for name in ("location_scale_search.py", "location_scale_readout.py", "search_qualification.py"):
            cls.reference["registration"]["code_sha256"][name] = hashlib.sha256(
                (ROOT / "research" / name).read_bytes()
            ).hexdigest()
        cls.config = ContinuousConfig(**cls.reference["config"])
        cls.summary, cls.records = run(cls.reference)

    def test_parent_failure_fixed_candidate_and_every_cell_are_preserved(self):
        self.assertFalse(self.reference["all_criteria_pass"])
        self.assertFalse(self.summary["parent_all_criteria_pass"])
        self.assertEqual(self.summary["role"], "post_hoc_explanation_not_qualification")
        self.assertEqual(self.summary["candidate"], 0)
        expected = {
            (family, replicate, horizon, target)
            for family in ("leading_location", "leading_scale")
            for replicate in range(2)
            for horizon in (12, 24, 48)
            for target in range(3)
        }
        actual = [(r["family"], r["world"], r["horizon"], r["target"]) for r in self.records]
        self.assertEqual(len(actual), 36)
        self.assertEqual(set(actual), expected)
        for family in ("leading_location", "leading_scale"):
            cells = self.summary["results"][family]
            self.assertEqual(set(cells), {f"h{h}_target{t}" for h in (12, 24, 48) for t in range(3)})
            for cell in cells.values():
                self.assertEqual(cell["worlds"], 2)
                self.assertEqual(cell["overlapping_origins_per_world"], 96)

    def test_every_stored_crps_matches_independent_forecast_atom_calculation(self):
        base = SearchConfig(seed=self.config.seed, steps=self.config.steps, candidates=self.config.candidates)
        prices = {
            (family, replicate): world(base, domain, replicate, family)[0]
            for family, domain in (("leading_location", 403), ("leading_scale", 404))
            for replicate in range(2)
        }
        for record in self.records:
            decisions = np.asarray(record["audit_decisions"])
            np.testing.assert_array_equal(decisions, np.arange(546, 642))
            # Reconstruct targets directly from the actual path, independently
            # of prepare()/outcomes() and the optimized empirical CRPS routine.
            horizon = record["horizon"]
            paths = prices[record["family"], record["world"]][
                decisions[:, None] + 1 + np.arange(horizon + 1)
            ]
            targets = (
                paths[:, -1] - paths[:, 0],
                paths[:, 0] - paths.min(axis=1),
                (np.maximum.accumulate(paths, axis=1) - paths).max(axis=1),
            )
            observed = targets[record["target"]]
            for name in ("reference", "candidate"):
                forecast = record[name]
                location = np.asarray(forecast["location"])
                scale = np.asarray(forecast["scale"])
                residuals = np.asarray(forecast["calibration_residuals"])
                self.assertEqual(location.shape, (96,))
                self.assertEqual(scale.shape, (96,))
                self.assertEqual(residuals.shape, (96,))
                self.assertTrue(np.all(scale > 0))
                atoms = location[:, None] + scale[:, None] * residuals[None, :]
                loss = np.mean(np.abs(atoms - observed[:, None]), axis=1)
                loss -= .5 * np.mean(np.abs(atoms[:, :, None] - atoms[:, None, :]), axis=(1, 2))
                np.testing.assert_allclose(forecast["crps"], loss, rtol=1e-11, atol=1e-12)

    def test_summary_aggregates_paired_worlds_without_selecting_a_cell(self):
        for family, cells in self.summary["results"].items():
            for horizon in self.config.horizons:
                for target in range(3):
                    records = [r for r in self.records if (r["family"], r["horizon"], r["target"]) == (family, horizon, target)]
                    reference = np.array([r["reference"]["crps"] for r in records])
                    candidate = np.array([r["candidate"]["crps"] for r in records])
                    summary = cells[f"h{horizon}_target{target}"]
                    self.assertAlmostEqual(summary["mean_crps_improvement"], float((reference.mean(axis=1) - candidate.mean(axis=1)).mean()))
                    self.assertAlmostEqual(summary["crps_skill_percent"], float(100 * (1 - candidate.sum() / reference.sum())))

    def test_fixed_candidate_matches_registered_core_selected_cell(self):
        base = SearchConfig(seed=self.config.seed, steps=self.config.steps, candidates=self.config.candidates)
        price, context, scores = world(base, 403, 0, "leading_location")
        fixed = (scores[:, 0] + .5 * context[:, 0])[None, :, None]
        # Restrict to the already designated candidate zero, then let the
        # unchanged registered core choose its development-best outcome cell.
        config = replace(self.config, candidates=1)
        audit_skill, selected, _ = search_statistics(prepare(config, price, context), fixed)
        horizon = config.horizons[int(selected[0]) // 3]
        target = int(selected[0]) % 3
        record = next(r for r in self.records if (r["family"], r["world"], r["horizon"], r["target"]) == ("leading_location", 0, horizon, target))
        reconstructed_skill = 100 * (1 - np.sum(record["candidate"]["crps"]) / np.sum(record["reference"]["crps"]))
        self.assertAlmostEqual(float(audit_skill[0]), float(reconstructed_skill), places=10)

    def test_parent_readout_drift_rejected_before_any_world_is_replayed(self):
        for name in ("location_scale_search.py", "location_scale_readout.py", "search_qualification.py"):
            with self.subTest(name=name):
                reference = copy.deepcopy(self.reference)
                reference["registration"]["code_sha256"][name] = "changed"
                with patch("research.readout_replicate_diagnostic.world") as replay:
                    with self.assertRaisesRegex(ValueError, "parent readout changed"):
                        run(reference)
                    replay.assert_not_called()


if __name__ == "__main__":
    unittest.main()
