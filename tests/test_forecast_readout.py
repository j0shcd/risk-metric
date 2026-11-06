import unittest

import numpy as np

from research.forecast_readout import (
    calibrate_residuals,
    crps_empirical,
    fit_location,
    training_percentile,
)


class ForecastReadoutTests(unittest.TestCase):
    def test_crps_hand_calculation_and_deterministic_forecast(self):
        # E|X-1|=1, E|X-X'|/2=.5 for equal masses at 0 and 2.
        self.assertAlmostEqual(float(crps_empirical(np.array([0, 2]), 1)), 0.5)
        np.testing.assert_allclose(crps_empirical(np.array([2]), np.array([0, 2, 5])), [2, 0, 3])

    def test_crps_matches_independent_quadratic_definition(self):
        samples = np.array([-5, -1, 0, 0, 2, 9.0])
        outcomes = np.array([-12, -1, 0, 1, 20.0])
        expected = [np.mean(abs(samples - y)) - np.mean(abs(samples[:, None] - samples)) / 2 for y in outcomes]
        np.testing.assert_allclose(crps_empirical(samples, outcomes), expected)
        np.testing.assert_allclose(crps_empirical(samples + 7, outcomes + 7), expected)
        np.testing.assert_allclose(crps_empirical(samples * 3, outcomes * 3), np.array(expected) * 3)

    def test_readout_normalization_is_training_only_with_explicit_ties(self):
        reference = np.array([0, 1, 1, 2.0])
        np.testing.assert_allclose(training_percentile(reference, np.array([-10, 0, 1, 2, 100.])), [-.5, -.375, 0, .375, .5])
        prefix = training_percentile(reference, np.array([.5, 1.5]))
        extended = training_percentile(reference, np.array([.5, 1.5, 1000]))
        np.testing.assert_array_equal(prefix, extended[:2])

    def test_frozen_readout_is_invariant_to_strictly_increasing_rescaling(self):
        rng = np.random.default_rng(42)
        context, risk = rng.normal(size=(2, 100))
        outcomes = .4 * context - risk + rng.normal(size=100)
        first = fit_location(context, outcomes, indicator=risk)
        second = fit_location(np.exp(context), outcomes, indicator=100 * risk + 15)
        query_context, query_risk = rng.normal(size=(2, 30))
        np.testing.assert_allclose(first.predict(query_context, query_risk), second.predict(np.exp(query_context), 100 * query_risk + 15))

    def test_wrong_direction_refits_context_instead_of_clipping_only(self):
        context = np.linspace(-1, 1, 100)
        risk = context + .1 * np.sin(np.arange(100))
        outcomes = 2 * risk + context
        reference = fit_location(context, outcomes)
        constrained = fit_location(context, outcomes, indicator=risk, indicator_direction=-1)
        self.assertEqual(constrained.coefficients[-1], 0)
        np.testing.assert_allclose(constrained.predict(context, risk), reference.predict(context))

    def test_constant_indicator_and_separate_residual_calibration(self):
        context = np.linspace(-1, 1, 30)
        outcomes = -context
        model = fit_location(context, outcomes, indicator=np.ones(30))
        self.assertEqual(model.coefficients[-1], 0)
        heldout_outcomes = model.predict(context, np.ones(30)) + 4
        forecast = calibrate_residuals(model, context, heldout_outcomes, np.ones(30))
        np.testing.assert_allclose(forecast.residuals, 4)
        self.assertAlmostEqual(float(forecast.loss(context, heldout_outcomes, np.ones(30)).mean()), 0)

    def test_invalid_support_is_not_silently_filtered(self):
        with self.assertRaises(ValueError):
            fit_location(np.arange(10), np.arange(10), indicator=np.array([1, np.nan]))
        with self.assertRaises(ValueError):
            crps_empirical(np.array([0, np.nan]), 1)
        with self.assertRaises(ValueError):
            crps_empirical(np.array([0, 1]), np.nan)
        model = fit_location(np.arange(10), np.arange(10), indicator=-np.arange(10))
        with self.assertRaises(ValueError):
            model.predict(np.arange(10), np.arange(9))


if __name__ == "__main__":
    unittest.main()
