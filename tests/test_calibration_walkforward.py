import unittest

import numpy as np
import pandas as pd

from risk_engine.calibration import _financial_quality_from_position, calibrate_primary_outputs


class CalibrationWalkforwardTests(unittest.TestCase):
    def test_financial_quality_prefers_exposed_in_uptrend(self) -> None:
        idx = pd.date_range("2020-01-31", periods=24, freq=pd.offsets.MonthEnd())
        price = pd.Series(np.linspace(100.0, 200.0, len(idx)), index=idx)
        q_on = _financial_quality_from_position(pd.Series(1.0, index=idx), price)
        q_off = _financial_quality_from_position(pd.Series(0.0, index=idx), price)
        self.assertGreater(q_on, q_off)

    def test_calibration_noop_without_btc_price(self) -> None:
        idx = pd.date_range("2024-01-01", periods=120, freq="D")
        series = pd.DataFrame({"top_reversal_risk": 0.5, "headline_attention": 0.4}, index=idx)
        out = calibrate_primary_outputs(series)
        self.assertEqual(float(out.metadata.get("calibration_applied", 1.0)), 0.0)
        pd.testing.assert_frame_equal(out.series, series)

    def test_calibration_bounds_when_applied(self) -> None:
        idx = pd.date_range("2016-01-01", periods=4200, freq="D")
        x = np.arange(len(idx), dtype=float)
        series = pd.DataFrame(
            {
                "btc_price": 1000.0 + 20.0 * x + 2000.0 * np.sin(x / 90.0),
                "top_reversal_risk": (0.5 + 0.3 * np.sin(x / 130.0)).clip(0.0, 1.0),
                "bottom_reversal_risk": (0.5 - 0.3 * np.sin(x / 130.0)).clip(0.0, 1.0),
                "attention_score": (0.3 + 0.2 * np.abs(np.sin(x / 70.0))).clip(0.0, 1.0),
                "headline_attention": (0.3 + 0.2 * np.abs(np.sin(x / 70.0))).clip(0.0, 1.0),
                "trend_composite_score": (0.4 + 0.2 * np.sin(x / 95.0)).clip(0.0, 1.0),
            },
            index=idx,
        )
        out = calibrate_primary_outputs(series)
        self.assertIn("top_reversal_risk", out.series.columns)
        vals = out.series["top_reversal_risk"].dropna()
        self.assertTrue(((vals >= 0.0) & (vals <= 1.0)).all())


if __name__ == "__main__":
    unittest.main()
