from dataclasses import replace
import unittest
from unittest.mock import patch

import numpy as np

from research.distribution_readout import mixture_forecasts, weighted_crps
from research.market_dataset import canonical_bytes
from research.search_qualification import (
    SearchConfig, batch_crps, binomial_upper, campaign, forecast_weights, outcomes, phase_indices, relative_skill, run, world,
)


class SearchQualificationTests(unittest.TestCase):
    def test_vectorized_kernel_matches_actual_scorecard_decoder(self):
        rng = np.random.default_rng(2)
        context, scores = rng.normal(size=(72, 2)), rng.normal(size=(72, 5))
        atoms, observed = rng.normal(size=24), rng.normal(size=24)
        reference, candidate = forecast_weights(context[:24], scores[:24], context[24:48], scores[24:48], context[48:], scores[48:])
        losses = batch_crps(atoms, candidate, observed[:, None])
        for i in range(24):
            for c in range(5):
                fit = np.column_stack((context[:24], scores[:24, c]))
                cal = np.column_stack((context[24:48], scores[24:48, c]))
                query = np.r_[context[48+i], scores[48+i, c]]
                scalar = mixture_forecasts(fit, cal, query)
                np.testing.assert_array_equal(reference[i], scalar["reference"])
                np.testing.assert_array_equal(candidate[i, c], scalar["candidate"])
                self.assertAlmostEqual(losses[i, c], weighted_crps(atoms, scalar["candidate"], observed[i]))

    def test_all_phases_use_strict_label_maturity_and_short_path_is_insufficient(self):
        config = SearchConfig()
        for horizon in config.horizons:
            phases = phase_indices(config, horizon)
            for left, right in zip(phases, phases[1:]):
                self.assertLess(left[-1]+horizon+2, right[0])
                self.assertEqual(len(left), 24)
        latest_development_label = max(phase_indices(config, h)[2][-1]+h+2 for h in config.horizons)
        earliest_audit = min(phase_indices(config, h)[3][0] for h in config.horizons)
        self.assertLess(latest_development_label, earliest_audit)
        self.assertIsNone(phase_indices(replace(config, steps=140), 48))
        self.assertEqual(campaign(replace(config, steps=140), 1, 0, "gaussian_p95")["status"], "insufficient_evidence")

    def test_path_outcomes_exclude_return_before_entry_and_distinguish_losses(self):
        price = np.array([0., 9., 1., 3., 0., 2.])
        np.testing.assert_array_equal(outcomes(price, np.array([1]), 3), [[1., 1., 3.]])

    def test_audit_labels_cannot_select_candidate_or_target(self):
        config = replace(SearchConfig(), candidates=4, horizons=(48,))
        original = world(config, 7, 0, "leading_location")
        first = campaign(config, 7, 0, "leading_location")
        # Change only prices after every development label resolves.
        last_development_end = max(phase_indices(config, h)[2][-1]+h+2 for h in config.horizons)
        altered = original[0].copy()
        altered[last_development_end+1:] += np.arange(len(altered)-last_development_end-1)*1000
        with patch("research.search_qualification.world", return_value=(altered, *original[1:])):
            second = campaign(config, 7, 0, "leading_location")
        for field in ("selected_horizon", "selected_target", "selected_candidate", "development_skill"):
            self.assertEqual(first[field], second[field])
        self.assertNotEqual(first["audit_skill"], second["audit_skill"])

    def test_binomial_bounds_and_strict_frozen_threshold(self):
        self.assertAlmostEqual(binomial_upper(0, 200, .05), 1-.05**(1/200))
        self.assertEqual(binomial_upper(200, 200, .05), 1)
        self.assertLess(binomial_upper(10, 200, .05/3), .10)
        self.assertGreater(binomial_upper(11, 200, .05/3), .10)
        config = replace(SearchConfig(), calibration_worlds=20, evaluation_worlds=1)
        # Threshold uses only separate calibration worlds, not evaluation values.
        def fake(config, domain, index, family):
            return {"status": "eligible", "audit_skill": float(index if domain < 200 else 19), "development_skill": 0}
        with patch("research.search_qualification.campaign", side_effect=fake):
            summary, records = run(config)
        self.assertEqual(summary["threshold"], 19)
        self.assertTrue(all(v["flags"] == 0 for v in summary["families"].values()))
        self.assertEqual(len(records), 65)

    def test_zero_loss_point_forecasts_have_finite_serializable_zero_gain(self):
        np.testing.assert_array_equal(relative_skill(np.zeros(3), 0.), np.zeros(3))
        with self.assertRaises(ValueError): relative_skill(np.ones(3), 0.)
        config = replace(SearchConfig(), candidates=1, calibration_worlds=20, evaluation_worlds=1)
        summary, records = run(config)
        self.assertTrue(canonical_bytes(records))
        self.assertTrue(canonical_bytes(summary))


if __name__ == "__main__":
    unittest.main()
