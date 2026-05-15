import unittest

import numpy as np
import pandas as pd

from risk_engine.normalization import build_feature_frame, robust_bounded_signal


class NormalizationTests(unittest.TestCase):
    def test_feature_frame_bounds(self) -> None:
        index = pd.date_range("2020-01-01", periods=600, freq="D")
        values = pd.Series(np.linspace(1.0, 10.0, 600), index=index)

        frame = build_feature_frame(values, base_reliability=0.8)

        signed = frame["signed_signal"].dropna()
        attention = frame["attention"].dropna()
        reliability = frame["reliability"].dropna()

        self.assertTrue(((signed >= -1.0) & (signed <= 1.0)).all())
        self.assertTrue(((attention >= 0.0) & (attention <= 1.0)).all())
        self.assertTrue(((reliability >= 0.0) & (reliability <= 1.0)).all())

    def test_no_future_leakage_in_rolling_signal(self) -> None:
        index = pd.date_range("2020-01-01", periods=700, freq="D")
        base = pd.Series(np.sin(np.arange(700) / 25.0) + np.arange(700) * 0.01 + 10.0, index=index)

        mutated = base.copy()
        mutated.iloc[-50:] = mutated.iloc[-50:] * 50.0

        original_signal = robust_bounded_signal(base)
        mutated_signal = robust_bounded_signal(mutated)

        comparison_horizon = 650
        left = original_signal.iloc[:comparison_horizon].fillna(0.0)
        right = mutated_signal.iloc[:comparison_horizon].fillna(0.0)

        np.testing.assert_allclose(left.values, right.values, atol=1e-10)

    def test_feature_carry_forward_uses_max_age_and_freshness_decay(self) -> None:
        index = pd.date_range("2024-01-01", periods=12, freq="D")
        values = pd.Series([10.0] + [np.nan] * 10 + [12.0], index=index)

        frame = build_feature_frame(values, base_reliability=1.0, max_carry_days=4, smooth_window=1)

        # Observed point plus four carry days; then carry expires.
        self.assertEqual(int(frame["raw_carried"].notna().iloc[:11].sum()), 5)
        self.assertTrue(frame["raw_carried"].iloc[5:11].isna().all())

        # Freshness decays linearly and resets when a new observation arrives.
        self.assertAlmostEqual(float(frame["freshness"].iloc[0]), 1.0)
        self.assertAlmostEqual(float(frame["freshness"].iloc[1]), 0.75)
        self.assertAlmostEqual(float(frame["freshness"].iloc[4]), 0.0)
        self.assertAlmostEqual(float(frame["freshness"].iloc[-1]), 1.0)

    def test_feature_frame_exposes_regime_and_surprise_channels(self) -> None:
        index = pd.date_range("2022-01-01", periods=500, freq="D")
        calm = np.linspace(100.0, 150.0, 250)
        turbulent = 150.0 + 15.0 * np.sin(np.arange(250) / 2.0)
        values = pd.Series(np.concatenate([calm, turbulent]), index=index)

        frame = build_feature_frame(values, base_reliability=1.0, smooth_window=1)

        for column in [
            "surprise",
            "regime_volatility_ratio",
            "signal_regime_scale",
            "attention_regime_scale",
        ]:
            self.assertIn(column, frame.columns)
            self.assertFalse(frame[column].dropna().empty)

        calm_signal_scale = frame["signal_regime_scale"].iloc[200:240].mean()
        turbulent_signal_scale = frame["signal_regime_scale"].iloc[420:460].mean()
        calm_attention_scale = frame["attention_regime_scale"].iloc[200:240].mean()
        turbulent_attention_scale = frame["attention_regime_scale"].iloc[420:460].mean()

        self.assertGreater(calm_signal_scale, turbulent_signal_scale)
        self.assertLess(calm_attention_scale, turbulent_attention_scale)

    def test_surprise_channel_lifts_attention_on_impulse(self) -> None:
        index = pd.date_range("2023-01-01", periods=420, freq="D")
        values = pd.Series(100.0 + np.sin(np.arange(420) / 25.0), index=index)
        values.iloc[360] = values.iloc[359] * 1.35

        frame = build_feature_frame(values, base_reliability=1.0, smooth_window=1)

        impulse_day = frame.index[360]
        surprise = float(frame.loc[impulse_day, "surprise"])
        attention = float(frame.loc[impulse_day, "attention"])
        level_only = abs(float(frame.loc[impulse_day, "signed_signal"]))

        self.assertGreater(surprise, 0.2)
        self.assertGreaterEqual(attention, level_only)


if __name__ == "__main__":
    unittest.main()
