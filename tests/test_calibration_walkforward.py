import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from risk_engine.calibration import _financial_quality_from_position, _long_cycle_labels, calibrate_primary_outputs
from risk_engine.config import RuntimeConfig
from risk_engine.pipeline import add_dca_risk_columns


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

    def test_calibrated_dca_prefix_is_invariant_across_history_gate(self) -> None:
        # Exercise the production calibration -> component-normalization boundary,
        # including the former 65/66-month switch and partial calendar months.
        dates = pd.date_range("2000-01-01", "2009-12-31", freq="D")
        x = np.arange(len(dates), dtype=float) / 30.0
        frame = pd.DataFrame({
            "btc_price": np.exp(4 + x*.01 + .2*np.sin(x/4)),
            "top_reversal_risk": .5 + .3*np.sin(x/4),
            "bottom_reversal_risk": .5 - .3*np.sin(x/4),
            "attention_score": .4,
            "trend_composite_score": .5,
            "cycle_extension_score": .5 + .2*np.sin(x/6),
            "cycle_frenzy_score": .5 + .2*np.cos(x/6),
        }, index=dates)
        cfg = RuntimeConfig(project_root=Path.cwd(), data_dir=Path("/private/tmp"),
                            output_dir=Path("/private/tmp"), cache_dir=Path("/private/tmp"))
        def produce(data):
            return add_dca_risk_columns(calibrate_primary_outputs(data, cfg=cfg).series)
        columns = ["top_reversal_risk", "bottom_reversal_risk", "attention_score", "dca_risk",
                   "dca_top_reversal_component", "dca_bottom_reversal_component",
                   "dca_cycle_extension_component", "dca_cycle_regime_component"]
        full = produce(frame)
        month_ends = pd.date_range("2000-01-31", periods=120, freq="ME")
        cutoffs = [month_ends[n-1] for n in (1, 12, 24, 36, 48, 64, 65, 66, 72, 96)]
        cutoffs += [pd.Timestamp("2000-01-15"), pd.Timestamp("2005-07-15")]
        for cutoff in cutoffs:
            with self.subTest(cutoff=cutoff):
                prefix = produce(frame.loc[:cutoff])
                pd.testing.assert_frame_equal(prefix[columns], full.loc[prefix.index, columns])
        shocked = frame.copy()
        shocked.loc[shocked.index > "2005-05-31", "btc_price"] *= 1000
        after = produce(shocked)
        pd.testing.assert_frame_equal(full.loc[:"2005-05-31", columns], after.loc[:"2005-05-31", columns])

    def test_upstream_regime_and_extension_warmups_are_prefix_invariant(self) -> None:
        from risk_engine.cycle_model import _build_monthly_inputs, _build_feature_snapshot, _build_regime_scores
        from risk_engine.pipeline import _build_cycle_extension_signals
        cfg = RuntimeConfig(project_root=Path.cwd(), data_dir=Path("/private/tmp"),
                            output_dir=Path("/private/tmp"), cache_dir=Path("/private/tmp"))
        months = pd.date_range("2013-01-31", periods=96, freq="ME")
        monthly = pd.Series(np.exp(4 + np.arange(96)*.01 + .2*np.sin(np.arange(96)/4)), index=months)
        def regime(prices):
            empty = pd.DataFrame(index=prices.index)
            inputs = _build_monthly_inputs(prices, empty, empty)
            return _build_regime_scores(_build_feature_snapshot(inputs, cfg), cfg)
        full = regime(monthly)
        # Rolling feature warmups and the expanding percentile's 24 observations,
        # including the 24 + 24 - 1 price/trend composite threshold.
        for count in (1, 2, 3, 5, 6, 11, 12, 13, 23, 24, 25, 46, 47, 48, 60):
            with self.subTest(regime_months=count):
                pd.testing.assert_frame_equal(regime(monthly.iloc[:count]), full.iloc[:count])
        dates = pd.date_range("2000-01-01", periods=1600, freq="D")
        prices = pd.Series(np.exp(4 + np.arange(1600)*.001 + .2*np.sin(np.arange(1600)/80)), index=dates)
        full = _build_cycle_extension_signals(prices)
        # Raw rolling windows and first finite expanding-rank outputs:
        # 200+365-1, 350+365-1, 366+365-1, 700+730-1 observations.
        for count in (49, 50, 199, 200, 349, 350, 563, 564, 699, 700, 713, 714, 729, 730, 1428, 1429):
            with self.subTest(extension_days=count):
                pd.testing.assert_frame_equal(_build_cycle_extension_signals(prices.iloc[:count]), full.iloc[:count])

    def test_long_cycle_labels_are_stable_when_future_rows_are_appended(self) -> None:
        idx = pd.date_range("2000-01-31", periods=180, freq=pd.offsets.MonthEnd())
        x = np.arange(len(idx), dtype=float)
        price = pd.Series(100.0 + 2.0 * x + 50.0 * np.sin(x / 7.0), index=idx)

        prefix_top, prefix_bottom = _long_cycle_labels(price.iloc[:150], horizons_months=[12, 18])
        full_top, full_bottom = _long_cycle_labels(price, horizons_months=[12, 18])

        resolved_top = prefix_top.dropna()
        resolved_bottom = prefix_bottom.dropna()
        pd.testing.assert_series_equal(resolved_top, full_top.reindex(resolved_top.index))
        pd.testing.assert_series_equal(resolved_bottom, full_bottom.reindex(resolved_bottom.index))


if __name__ == "__main__":
    unittest.main()
