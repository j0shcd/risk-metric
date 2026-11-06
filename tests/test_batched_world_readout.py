import unittest

import numpy as np

from research.batched_world_readout import calibration_residuals_worlds, fit_mean_scale_worlds, world_features
from research.location_scale_readout import calibration_residuals, fit_mean_scale
from research.location_scale_search import feature_phases


class BatchedWorldReadoutTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(41)
        self.context = rng.normal(size=(3, 24, 2))
        self.context[1, :, 1] = 7  # Constant feature, both in and out of fit.
        self.scores = rng.normal(size=(3, 24, 2))
        self.scores[0, :, 0] = 3 + 2 * self.context[0, :, 0] - self.context[0, :, 1]
        self.labels = rng.normal(size=(3, 24)) * np.array([.1, 3, 20])[:, None] + np.array([0, 5, -7])[:, None]
        self.indices = tuple(np.arange(i, i + 6) for i in (0, 6, 12, 18))

    def test_features_fits_predictions_and_residuals_match_scalar(self):
        reference, candidate, transforms = world_features(self.context, self.scores, self.indices)
        self.assertFalse(transforms['active'][0, 0])
        self.assertEqual(transforms['indicator_scale'][0, 0], 1.)
        self.assertEqual(transforms['context_scale'][1, 1], 1.)
        fit = fit_mean_scale_worlds(candidate[0], self.labels[:, self.indices[0]])
        mean, scale = fit.predict(candidate[2])
        residual = calibration_residuals_worlds(fit, candidate[1], self.labels[:, self.indices[1]])
        for w in range(3):
            ref, cand = feature_phases(self.context[w], self.scores[w][None], self.indices)
            for phase in range(4):
                np.testing.assert_allclose(reference[phase][w], ref[phase][0], atol=1e-11)
                np.testing.assert_allclose(candidate[phase][w], cand[phase][0], atol=1e-11)
            scalar = fit_mean_scale(cand[0], self.labels[w, self.indices[0]])
            for name in ('feature_mean', 'mean_coefficients', 'scale_coefficients'):
                np.testing.assert_allclose(getattr(fit, name)[w], getattr(scalar, name)[0], atol=1e-11)
            self.assertAlmostEqual(fit.outcome_mean[w], scalar.outcome_mean)
            loc, spread = scalar.predict(cand[2])
            np.testing.assert_allclose(mean[w], loc[0], atol=1e-11)
            np.testing.assert_allclose(scale[w], spread[0], atol=1e-11)
            np.testing.assert_allclose(residual[w], calibration_residuals(scalar, cand[1], self.labels[w, self.indices[1]])[0], atol=1e-11)

    def test_perturb_one_world_cannot_change_other_worlds(self):
        ref, cand, transforms = world_features(self.context, self.scores, self.indices)
        fit = fit_mean_scale_worlds(cand[0], self.labels[:, self.indices[0]])
        residual = calibration_residuals_worlds(fit, cand[1], self.labels[:, self.indices[1]])
        context, scores, labels = self.context.copy(), self.scores.copy(), self.labels.copy()
        context[0] += 5
        scores[0] *= 4
        labels[0] -= 20
        ref2, cand2, transforms2 = world_features(context, scores, self.indices)
        fit2 = fit_mean_scale_worlds(cand2[0], labels[:, self.indices[0]])
        residual2 = calibration_residuals_worlds(fit2, cand2[1], labels[:, self.indices[1]])
        for x, y in zip(ref + cand, ref2 + cand2):
            np.testing.assert_array_equal(x[1:], y[1:])
        for key in transforms:
            np.testing.assert_array_equal(transforms[key][1:], transforms2[key][1:])
        for name in ('feature_mean', 'outcome_mean', 'mean_coefficients', 'scale_coefficients'):
            np.testing.assert_array_equal(getattr(fit, name)[1:], getattr(fit2, name)[1:])
        np.testing.assert_array_equal(residual[1:], residual2[1:])

    def test_ridge_formula_and_validation(self):
        x = np.array([-2., -1., 1., 2.])
        model = fit_mean_scale_worlds(x.reshape(1, 1, 4, 1), (3 + 2*x)[None])
        expected = 2 * np.mean(x*x) / (np.mean(x*x) + .1)
        self.assertAlmostEqual(model.mean_coefficients[0, 0, 0], expected)
        self.assertAlmostEqual(model.outcome_mean[0], 3.)
        with self.assertRaises(ValueError):
            fit_mean_scale_worlds(np.zeros((2, 1, 4, 2)), np.zeros((1, 4)))
        with self.assertRaises(ValueError):
            world_features(self.context, self.scores, (*self.indices[:3], np.array([999])))
        with self.assertRaises(ValueError):
            calibration_residuals_worlds(model, x.reshape(1, 1, 4, 1), np.ones((2, 4)))

    def test_constant_nonzero_float_cannot_become_a_roundoff_feature(self):
        rng = np.random.default_rng(43)
        context = rng.normal(size=(2, 720, 2))
        scores = np.full((2, 720, 1), 7/23)
        scores[:, 546:] += 1000  # An unseen value cannot create a fitted coefficient.
        indices = tuple(np.arange(start, start+length) for start, length in ((12, 192), (254, 96), (400, 96), (546, 96)))
        _, features, transform = world_features(context, scores, indices)
        np.testing.assert_array_equal(transform["active"], False)
        for phase in features:
            np.testing.assert_array_equal(phase[..., -1], 0.)


if __name__ == '__main__':
    unittest.main()
