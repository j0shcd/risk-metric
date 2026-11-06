import unittest

import numpy as np

from research.location_scale_readout import MeanScaleFit, calibration_residuals, empirical_loss, fit_mean_scale


class LocationScaleReadoutTests(unittest.TestCase):
    def test_merge_crps_matches_independent_actual_atom_pair_distances(self):
        samples = np.array([[[0., -2., 0., 3.], [1., 1., 1., 1.]], [[-1., 2., 4., 4.], [0., 1., 2., 3.]]])
        locations = np.arange(12).reshape(2, 2, 3)/3
        scales = 1+locations/2
        outcomes = np.array([-2., .5, 7.])
        losses = empirical_loss(samples, locations, scales, outcomes)
        for d in range(2):
            for c in range(2):
                for i in range(3):
                    atoms = locations[d, c, i]+scales[d, c, i]*samples[d, c]
                    expected = np.mean(abs(atoms-outcomes[i]))-.5*np.mean(abs(atoms[:, None]-atoms))
                    self.assertAlmostEqual(losses[d, c, i], expected, places=12)
        with self.assertRaises(ValueError): empirical_loss(samples, locations, -scales, outcomes)

    def test_ridge_mean_and_scale_have_hand_computable_solution(self):
        x = np.array([[-1.], [-1.], [1.], [1.]])
        y = 2+3*x[:, 0]
        model = fit_mean_scale(x, y)
        self.assertAlmostEqual(model.outcome_mean, 2.)
        self.assertAlmostEqual(model.mean_coefficients[0], 3/1.1)
        np.testing.assert_allclose(model.scale_coefficients, 0, atol=1e-12)
        mean, scale = model.predict(np.array([[-2.], [0.], [2.]]))
        np.testing.assert_allclose(mean, [2-6/1.1, 2, 2+6/1.1])
        np.testing.assert_allclose(scale, 1)

    def test_calibration_cannot_refit_coefficients_or_query_forecasts(self):
        rng = np.random.default_rng(40)
        x, y = rng.normal(size=(128, 3)), rng.normal(size=128)
        model = fit_mean_scale(x[:64], y[:64])
        before = model.predict(x[96:])
        residuals = calibration_residuals(model, x[64:96], y[64:96])
        changed = calibration_residuals(model, x[64:96], 100+y[64:96])
        for a, b in zip(before, model.predict(x[96:])): np.testing.assert_array_equal(a, b)
        self.assertFalse(np.array_equal(residuals, changed))
        np.testing.assert_allclose(residuals, np.sort((y[64:96]-model.predict(x[64:96])[0])/model.predict(x[64:96])[1]))

    def test_constant_outcome_and_scale_limits_remain_finite(self):
        x = np.arange(12)[:, None].astype(float)
        model = fit_mean_scale(x, np.ones(12))
        mean, scale = model.predict(np.array([[-1e6], [1e6]]))
        np.testing.assert_array_equal(mean, 1)
        np.testing.assert_array_equal(scale, 1)
        atoms = calibration_residuals(model, x, np.ones(12))
        np.testing.assert_array_equal(empirical_loss(atoms, mean, scale, np.ones(2)), 0)
        extreme = MeanScaleFit(np.zeros(1), 0., np.zeros(1), np.array([1000.]))
        _, bounded = extreme.predict(np.array([[-100.], [0.], [100.]]))
        np.testing.assert_allclose(bounded, np.exp([-3., 0., 3.]))

    def test_batched_fit_predict_and_calibration_match_scalar_models(self):
        rng = np.random.default_rng(80)
        fit, cal, query = (rng.normal(size=(2, 3, n, 3)) for n in (64, 32, 8))
        y, cal_y = rng.normal(size=64), rng.normal(size=32)
        model = fit_mean_scale(fit, y)
        atoms = calibration_residuals(model, cal, cal_y)
        mean, scale = model.predict(query)
        for d in range(2):
            for c in range(3):
                scalar = fit_mean_scale(fit[d, c], y)
                m, s = scalar.predict(query[d, c])
                np.testing.assert_allclose(mean[d, c], m, atol=1e-12)
                np.testing.assert_allclose(scale[d, c], s, atol=1e-12)
                np.testing.assert_allclose(atoms[d, c], calibration_residuals(scalar, cal[d, c], cal_y), atol=1e-12)


if __name__ == "__main__":
    unittest.main()
