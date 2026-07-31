import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from risk_engine.config import RuntimeConfig
from risk_engine.cycle_model import _build_financial_benchmark_outputs, _simulate_dynamic_dca, build_cycle_model


class CycleModelTests(unittest.TestCase):
    def _cfg(self, **overrides) -> RuntimeConfig:
        cwd = Path.cwd()
        return RuntimeConfig(
            project_root=cwd,
            data_dir=cwd / "data",
            output_dir=cwd / "output",
            cache_dir=cwd / "data",
            **overrides,
        )

    def test_dynamic_dca_lags_signals_by_one_month(self) -> None:
        index = pd.date_range("2024-01-31", periods=3, freq=pd.offsets.MonthEnd())
        result = _simulate_dynamic_dca(
            price=pd.Series(100.0, index=index),
            dca_risk=pd.Series([0.0, 1.0, 1.0], index=index),
            cfg=self._cfg(cycle_dynamic_dca_buy_threshold=0.75),
        )

        self.assertEqual(float(result.iloc[0]["buy_usd"]), 0.0)
        self.assertGreater(float(result.iloc[1]["buy_usd"]), 0.0)
        self.assertEqual(float(result.iloc[1]["dca_risk_used"]), 0.0)

    def test_dynamic_dca_thresholds_include_base_actions_at_equality(self) -> None:
        index = pd.date_range("2024-01-31", periods=3, freq=pd.offsets.MonthEnd())
        result = _simulate_dynamic_dca(
            price=pd.Series(100.0, index=index),
            dca_risk=pd.Series([0.25, 0.75, 0.5], index=index),
            cfg=self._cfg(
                cycle_dynamic_dca_buy_threshold=0.75,
                cycle_dynamic_dca_sell_threshold=0.75,
                cycle_dynamic_dca_fee_rate=0.0,
                cycle_dynamic_dca_slippage_rate=0.0,
            ),
        )

        self.assertGreater(float(result.iloc[1]["buy_usd"]), 0.0)
        self.assertEqual(float(result.iloc[1]["dca_risk_used"]), 0.25)
        self.assertGreater(float(result.iloc[2]["sell_usd"]), 0.0)
        self.assertEqual(float(result.iloc[2]["dca_risk_used"]), 0.75)

    def test_dynamic_dca_rejects_overlapping_thresholds(self) -> None:
        index = pd.date_range("2024-01-31", periods=2, freq=pd.offsets.MonthEnd())
        with self.assertRaisesRegex(ValueError, "buy threshold must be below sell threshold"):
            _simulate_dynamic_dca(
                price=pd.Series(100.0, index=index),
                dca_risk=pd.Series(0.5, index=index),
                cfg=self._cfg(
                    cycle_dynamic_dca_buy_threshold=0.40,
                    cycle_dynamic_dca_sell_threshold=0.50,
                ),
            )

    def test_flat_price_contributions_do_not_count_as_return(self) -> None:
        index = pd.date_range("2020-01-31", periods=24, freq=pd.offsets.MonthEnd())
        price = pd.Series(100.0, index=index)
        decisions = pd.DataFrame({"position": 0.0}, index=index)
        dca_risk = pd.Series(0.5, index=index)

        summary, curves = _build_financial_benchmark_outputs(price, decisions, dca_risk, self._cfg(
            cycle_dynamic_dca_fee_rate=0.0,
            cycle_dynamic_dca_slippage_rate=0.0,
        ))

        dynamic = summary[summary["strategy"].astype(str) == "dynamic_dca"].iloc[0]
        fixed = summary[summary["strategy"].astype(str) == "fixed_dca"].iloc[0]
        self.assertAlmostEqual(float(dynamic["total_return"]), 0.0)
        self.assertAlmostEqual(float(dynamic["cagr"]), 0.0)
        self.assertAlmostEqual(float(dynamic["money_weighted_return"]), 0.0, places=8)
        self.assertAlmostEqual(float(fixed["money_weighted_return"]), 0.0, places=8)
        self.assertTrue((curves["dynamic_dca_equity"] == 1.0).all())
        self.assertEqual(float(curves["dynamic_dca_value"].iloc[-1]), 24.0)
        self.assertEqual(float(curves["dynamic_dca_total_contributed"].iloc[-1]), 24.0)
        self.assertEqual(float(curves["fixed_dca_total_contributed"].iloc[-1]), 24.0)

    def test_cycle_model_outputs_probabilities_and_signals(self) -> None:
        index = pd.date_range("2013-01-01", periods=5200, freq="D")
        trend = np.linspace(100.0, 80000.0, len(index))
        oscillation = 2000.0 * np.sin(np.arange(len(index)) / 140.0)
        btc_price = pd.Series(trend + oscillation, index=index, name="btc_price")

        onchain = pd.DataFrame(
            {
                "mvrv_ratio_z_proxy": np.linspace(-0.5, 6.0, len(index)),
                "puell_multiple": 0.8 + 0.7 * np.sin(np.arange(len(index)) / 180.0),
                "mvrv_implied_profitability_proxy": np.clip(
                    0.4 + 0.3 * np.sin(np.arange(len(index)) / 160.0), 0.0, 1.0
                ),
            },
            index=index,
        )

        context = pd.DataFrame(
            {
                "btc_volume_usd": 2.5e10 + 6e9 * np.sin(np.arange(len(index)) / 55.0),
                "google_trends_interest": 25.0 + 10.0 * np.sin(np.arange(len(index)) / 75.0),
                "wikipedia_pageviews": 1.8e5 + 4.0e4 * np.sin(np.arange(len(index)) / 45.0),
                "reddit_post_volume": 1800.0 + 300.0 * np.sin(np.arange(len(index)) / 60.0),
                "dxy": 100.0 + 3.0 * np.sin(np.arange(len(index)) / 95.0),
                "real_yield_10y": 1.2 + 0.4 * np.sin(np.arange(len(index)) / 110.0),
                "net_liquidity": 6.5e12 + 3.5e11 * np.sin(np.arange(len(index)) / 130.0),
            },
            index=index,
        )

        cfg = self._cfg()

        out = build_cycle_model(
            cfg=cfg,
            btc_price=btc_price,
            onchain_frame=onchain,
            context_frame=context,
            daily_index=index,
        )

        self.assertFalse(out.feature_snapshots.empty)
        self.assertFalse(out.regime_scores.empty)
        self.assertFalse(out.signal_decisions.empty)
        self.assertFalse(out.backtest_report.empty)
        self.assertFalse(out.financial_benchmark_summary.empty)
        self.assertFalse(out.financial_benchmark_curves.empty)

        for col in ["frenzy_score", "accumulation_score", "p_frenzy", "p_accumulation", "confidence"]:
            values = out.regime_scores[col].dropna()
            self.assertFalse(values.empty)
            self.assertTrue(((values >= 0.0) & (values <= 1.0)).all())

        regimes = set(out.signal_decisions["regime"].astype(str).unique().tolist())
        self.assertTrue(regimes.issubset({"BUY", "HOLD", "SELL"}))
        self.assertIn("cycle_p_frenzy", out.daily_projection.columns)
        self.assertIn("cycle_signal_regime", out.daily_projection.columns)


if __name__ == "__main__":
    unittest.main()
