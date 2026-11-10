import math
import unittest

import numpy as np
import pandas as pd

from research import decision_readout as readout
from research.distribution_readout import mixture_forecasts, weighted_crps


def fixture(n=90):
    rng = np.random.default_rng(314159)
    x = np.sin(np.arange(n)/7)
    price = np.exp(np.cumsum(.02+.05*x+.08*rng.normal(size=n)))
    frame = pd.DataFrame({"price": price, "context_trend": x, "context_volatility": np.cos(np.arange(n)/11),
                          "dca_risk": .5+.4*x, "exact": x, "nuisance": rng.normal(size=n),
                          "constant": .5, "duplicate": x}, index=pd.date_range("2000-01-31", periods=n, freq="ME"))
    for i, col in enumerate(readout.COMPONENTS):
        frame[col] = .5+.3*np.sin(np.arange(n)/(5+i))
    return frame


class DecisionReadoutTests(unittest.TestCase):
    def test_target_matches_actual_entry_and_six_month_deferral(self):
        prices = np.array([500, 100, 110, 120, 130, 140, 150, 50, 60], float)
        y = readout.deferral_targets(prices, 6)
        self.assertAlmostEqual(y[0], math.log(100/50))
        self.assertAlmostEqual(math.expm1(y[0]), (1/50)/(1/100)-1)
        self.assertTrue(np.isnan(y[-1]))

    def test_every_training_and_calibration_label_is_strictly_available(self):
        f = fixture()
        for method in readout.METHODS:
            fit, cal, _ = readout.split_indices(f.index, 70, 6, method)
            self.assertTrue(fit and cal)
            for j in fit+cal:
                self.assertLess(f.index[j+7]+pd.Timedelta(days=1), f.index[70])
            if method != "empirical_latest24":
                self.assertEqual(len(cal), 8)
                for j in fit:
                    self.assertLess(f.index[j+7]+pd.Timedelta(days=1), f.index[cal[0]])

    def test_insufficient_labels_report_fallback_without_fake_prediction(self):
        result = readout.forecast_at(fixture(), 20)
        self.assertFalse(result["trained"])
        self.assertEqual(result["reason"], "insufficient_mature_training")
        self.assertNotIn("risk", result)

    def test_future_prices_and_missing_features_cannot_change_issued_forecast(self):
        f = fixture()
        before = readout.forecast_at(f, 65)
        f.iloc[66:, :] = np.nan
        after = readout.forecast_at(f, 65)
        self.assertEqual(before, after)

    def test_query_and_calibration_values_do_not_fit_preprocessing(self):
        f = fixture()
        context = f[["context_trend", "context_volatility"]].to_numpy()
        indicators = f[["dca_risk"]].to_numpy()
        fit = np.arange(16)
        _, before = readout.transformed_features(context, indicators, fit)
        context[20:] *= 100
        indicators[20:] += 100
        _, after = readout.transformed_features(context, indicators, fit)
        self.assertEqual(before, after)

    def test_constant_and_known_context_duplicate_have_exact_reference_forecasts(self):
        f = fixture()
        reference = readout.forecast_at(f, 75, feature="price_only")
        for feature in ("constant", "duplicate"):
            candidate = readout.forecast_at(f, 75, feature=feature)
            self.assertEqual(candidate["active_indicator_n"], 0)
            for key in ("mean", "sigma", "risk", "lo80", "hi80", "variance_inflation"):
                self.assertEqual(candidate[key], reference[key])

    def test_empirical_reference_calls_unchanged_weighting(self):
        f = fixture()
        result = readout.forecast_at(f, 75, method="empirical_latest24")
        y = readout.deferral_targets(f.price)
        train = result["train_indices"]
        features = f[["context_trend", "context_volatility", "dca_risk"]].to_numpy()
        expected = mixture_forecasts(features[train], features[train], features[75])["candidate"]
        np.testing.assert_array_equal(result["weights"], expected)
        score = readout.score_forecast(result, .7)
        self.assertAlmostEqual(score["crps"], weighted_crps(y[train], expected, .7))

    def test_gaussian_crps_against_independent_quantile_integral(self):
        from statistics import NormalDist
        mean, sigma, observed = .2, .7, -1.1
        forecast = {"kind": "gaussian", "trained": True, "mean": mean, "sigma": sigma,
                    "risk": 1-NormalDist(mean, sigma).cdf(0),
                    "lo80": mean-readout.NORMAL80*sigma, "hi80": mean+readout.NORMAL80*sigma}
        q = (np.arange(20000)+.5)/20000
        values = np.array([NormalDist(mean, sigma).inv_cdf(float(p)) for p in q])
        errors = observed-values
        integral = float(2*np.mean(np.where(errors >= 0, q*errors, (q-1)*errors)))
        self.assertAlmostEqual(readout.score_forecast(forecast, observed)["crps"], integral, places=5)

    def test_single_sign_continuous_targets_can_fit(self):
        f = fixture()
        f["price"] = np.exp(np.arange(len(f))*.03)
        result = readout.forecast_at(f, 75)
        self.assertTrue(result["trained"])
        self.assertEqual(result["positive_fit_labels"], 0)
        self.assertGreater(result["negative_fit_labels"], 0)
        self.assertGreater(result["sigma"], 0)

    def test_redundant_indicator_copies_cannot_change_forecasts(self):
        f = fixture()
        f["dca_risk"] = .5+.3*np.sin(np.arange(len(f))/5)**2
        for col in readout.COMPONENTS:
            f[col] = f.dca_risk
        single = readout.forecast_at(f, 75, feature="composite")
        copies = readout.forecast_at(f, 75, feature="components")
        self.assertEqual(copies["active_indicator_n"], 1)
        for key in ("mean", "sigma", "risk", "variance_inflation"):
            self.assertAlmostEqual(single[key], copies[key], places=12)

    def test_variance_inflation_metadata_is_a_variance_multiplier(self):
        result = readout.forecast_at(fixture(), 75)
        expected = 1+(result["active_features"]+1)/result["fit_n"]
        self.assertAlmostEqual(result["variance_inflation"], expected)

    def test_redundant_feature_family_preserves_forecasts(self):
        f = fixture()
        context = f[["context_trend", "context_volatility"]].to_numpy()
        u, v = np.sin(np.arange(len(f))/5), np.cos(np.arange(len(f))/3)
        y = readout.deferral_targets(f.price)
        fit, cal, _ = readout.split_indices(f.index, 75, 6, "gaussian_expanding")
        base = readout.gaussian_forecast(context, np.column_stack((u, v)), y, fit, cal, 75)
        redundant = np.column_stack((u, v, 2*u+v, -u, np.ones(len(f)), context[:, 0]))
        extra = readout.gaussian_forecast(context, redundant, y, fit, cal, 75)
        self.assertEqual(extra["active_indicator_n"], 2)
        for key in ("mean", "sigma", "risk", "variance_inflation"):
            self.assertAlmostEqual(base[key], extra[key], places=12)


if __name__ == "__main__":
    unittest.main()
