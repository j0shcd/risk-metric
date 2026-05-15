import unittest

import numpy as np
import pandas as pd

from risk_engine.calibration import calibrate_primary_outputs
from risk_engine.validation import build_walkforward_sanity_report


def _passed_checks(report: pd.DataFrame) -> int:
    if report.empty or "passed" not in report.columns:
        return 0
    return int(report["passed"].fillna(False).sum())


class CalibrationTests(unittest.TestCase):
    def test_walkforward_calibration_keeps_bounds_and_emits_metadata(self) -> None:
        index = pd.date_range("2016-01-01", periods=2400, freq="D")
        x = np.arange(len(index), dtype=float)

        btc_price = pd.Series(
            1000.0 + 35.0 * x + 2500.0 * np.sin(x / 40.0),
            index=index,
            name="btc_price",
        )
        # First-draft signal with trend-following bias.
        raw_signal = pd.Series(
            (0.50 + 0.25 * np.tanh((x - x.mean()) / 380.0) + 0.04 * np.sin(x / 55.0)).clip(0.0, 1.0),
            index=index,
            name="btc_risk_signal",
        )
        # Attention peaks near the middle in this synthetic setup (a known undesirable behavior).
        raw_attention = pd.Series(
            (0.60 - 0.50 * (2.0 * (raw_signal - 0.5).abs()) + 0.03 * np.sin(x / 28.0)).clip(0.0, 1.0),
            index=index,
            name="headline_attention",
        )

        frame = pd.DataFrame(
            {
                "btc_price": btc_price,
                "btc_risk_signal": raw_signal,
                "top_reversal_risk": raw_signal,
                "bottom_reversal_risk": 1.0 - raw_signal,
                "trend_composite_score": raw_signal,
                "attention_score": raw_attention,
                "headline_attention": raw_attention,
            }
        )

        before = build_walkforward_sanity_report(frame)
        calibrated = calibrate_primary_outputs(frame).series
        after = build_walkforward_sanity_report(calibrated)

        self.assertGreaterEqual(_passed_checks(after), _passed_checks(before))
        self.assertTrue(((calibrated["top_reversal_risk"].dropna() >= 0.0) & (calibrated["top_reversal_risk"].dropna() <= 1.0)).all())
        self.assertTrue(
            ((calibrated["bottom_reversal_risk"].dropna() >= 0.0) & (calibrated["bottom_reversal_risk"].dropna() <= 1.0)).all()
        )
        self.assertTrue(
            ((calibrated["headline_attention"].dropna() >= 0.0) & (calibrated["headline_attention"].dropna() <= 1.0)).all()
        )

        meta = calibrate_primary_outputs(frame).metadata
        self.assertEqual(meta.get("calibration_applied"), 1.0)
        self.assertIn("walkforward_last_train_end", meta)
        self.assertIn("top_mean_w_base", meta)
        self.assertIn("bottom_mean_w_base", meta)
        self.assertEqual(meta.get("top_objective"), "composite_long_cycle_label_and_financial")
        self.assertIn("top_mean_w_price_extremity", meta)
        self.assertIn("top_mean_w_momentum_exhaustion", meta)
        self.assertIn("top_mean_w_attention_blowoff", meta)
        self.assertIn("top_train_event_count_mean", meta)
        self.assertIn("objective_label_weight", meta)
        self.assertIn("objective_financial_weight", meta)


if __name__ == "__main__":
    unittest.main()
