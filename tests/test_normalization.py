import unittest

import numpy as np
import pandas as pd

from risk_engine.normalization import build_feature_frame, robust_bounded_signal


class NormalizationTests(unittest.TestCase):
    def test_feature_frame_bounds(self) -> None:
        index = pd.date_range("2020-01-01", periods=600, freq="D")
        values = pd.Series(np.linspace(1.0, 10.0, 600), index=index)

        frame = build_feature_frame(values, base_reliability=0.8)

        signed = frame["signed_heat"].dropna()
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


if __name__ == "__main__":
    unittest.main()
