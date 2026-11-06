from dataclasses import replace
import unittest
from unittest.mock import patch

import numpy as np

from research import panel_benchmark as panel
from research.location_scale_readout import calibration_residuals, empirical_loss, fit_mean_scale
from research.location_scale_search import feature_phases, phases


SMALL = replace(panel.PanelConfig(), seed=1, development_worlds=2, audit_worlds=3, randomizations=9)


class PanelBenchmarkTests(unittest.TestCase):
    def test_batch_and_scalar_panels_agree_for_every_stochastic_family(self):
        for family in range(5):
            with self.subTest(family=family):
                batch = panel.one_panel(SMALL, family, 0)
                scalar = panel.one_panel(SMALL, family, 0, batched=False)
                for key in ("selected_cell", "selected_candidate", "pvalue", "promote", "development_ids", "audit_ids"):
                    self.assertEqual(batch[key], scalar[key])
                for key in ("development_reference_mean", "development_candidate_mean", "audit_reference_world_means",
                            "audit_candidate_world_means", "randomized_statistics"):
                    np.testing.assert_allclose(batch[key], scalar[key], atol=1e-10)
                self.assertFalse(set(batch["development_ids"]).intersection(batch["audit_ids"]))
                self.assertEqual(batch["prefix_cutoff"], 545)

    def test_all_development_cells_match_scalar_and_ignore_future_audit(self):
        base, price, context, scores, _ = panel.generated_worlds(SMALL, 3, 0, "development")
        reference, candidate = panel.development_panel_losses(base, price, context, scores)
        for w in range(len(price)):
            a, b = panel.development_losses(base, price[w], context[w], scores[w])
            np.testing.assert_allclose(reference[w], a, atol=1e-11)
            np.testing.assert_allclose(candidate[w], b, atol=1e-11)
        price[:, 546:] += 1000
        scores[:, 496:] -= 1000
        new_reference, new_candidate = panel.development_panel_losses(base, price, context, scores)
        np.testing.assert_array_equal(reference, new_reference)
        np.testing.assert_array_equal(candidate, new_candidate)

    def test_audit_predictions_match_frozen_scalar_models_and_are_point_causal(self):
        base, price, context, scores, _ = panel.generated_worlds(SMALL, 4, 0, "audit")
        cell, candidate = 5, 0
        states, reference, outcome = panel.fit_audit_panel(base, price, context, scores, cell, candidate)
        indices = phases(base)
        observed = scores[:, indices[-1], candidate][None]
        loss = panel.audit_losses(states, observed, outcome)
        for w in range(len(price)):
            scalar, ref, y = panel.fit_audit_world(base, price[w], context[w], scores[w], cell, candidate)
            np.testing.assert_allclose(reference[w], ref, atol=1e-11)
            np.testing.assert_array_equal(outcome[w], y)
            for key in ("projection", "feature_mean", "mean_beta", "scale_beta", "residuals"):
                np.testing.assert_allclose(states[w][key], scalar[key], atol=1e-11)
            prepared = panel.prepare(base, price[w], context[w])
            _, features = feature_phases(context[w], scores[w, :, candidate][None, :, None], indices)
            labels = prepared["outcomes"][base.horizons[cell//3]]
            model = fit_mean_scale(features[0], labels[0][:, cell % 3])
            residual = calibration_residuals(model, features[1], labels[1][:, cell % 3])
            mean, scale = model.predict(features[3])
            expected = empirical_loss(residual, mean, scale, y)[0, 0]
            np.testing.assert_allclose(loss[0, w], expected, atol=1e-11)
        changed = observed.copy(); changed[:, :, 4:] += 100
        after = panel.audit_losses(states, changed, outcome)
        np.testing.assert_array_equal(loss[:, :, :4], after[:, :, :4])
        self.assertFalse(np.array_equal(loss[:, :, 4:], after[:, :, 4:]))

    def test_audit_data_cannot_change_the_global_development_choice(self):
        before = panel.one_panel(SMALL, 3, 0)
        original = panel.generated_worlds
        def changed(config, family_index, number, role):
            base, price, context, scores, identities = original(config, family_index, number, role)
            if role == "audit":
                price[:, 546:] += np.arange(price.shape[1]-546)*100
                scores[:, 546:] *= -3
            return base, price, context, scores, identities
        with patch.object(panel, "generated_worlds", side_effect=changed):
            after = panel.one_panel(SMALL, 3, 0)
        for key in ("selected_cell", "selected_candidate", "development_reference_mean", "development_candidate_mean"):
            self.assertEqual(before[key], after[key])

    def test_deterministic_sentinels_use_point_mass_law_and_never_declare(self):
        for family_index in range(5, 8):
            with self.subTest(family=family_index):
                result = panel.one_panel(SMALL, family_index, 0)
                self.assertEqual(result["pvalue"], 1.)
                self.assertFalse(result["promote"])
                np.testing.assert_array_equal(result["randomized_statistics"], result["observed_statistic"])
                if family_index < 7:
                    self.assertEqual((result["selected_cell"], result["selected_candidate"]), (0, 0))
                    self.assertEqual(result["raw_gain"], 0.)

    def test_conditional_sampler_sees_all_candidates_and_only_fixed_prefix(self):
        original = panel.draw_future_scores
        with patch.object(panel, "draw_future_scores", wraps=original) as sampler:
            result = panel.one_panel(SMALL, 0, 0)
        history, sigma, candidate, length, draws, _ = sampler.call_args.args
        self.assertEqual(history.shape, (SMALL.audit_worlds, 546, 24))
        np.testing.assert_array_equal(sigma, np.linspace(.1, 2., 24))
        self.assertEqual((candidate, length, draws), (result["selected_candidate"], 96, SMALL.randomizations))


if __name__ == "__main__":
    unittest.main()
