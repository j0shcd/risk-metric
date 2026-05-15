import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from risk_engine.config import RuntimeConfig
from risk_engine.cycle_model import build_cycle_model


class CycleModelTests(unittest.TestCase):
    def test_cycle_model_outputs_probabilities_and_signals(self) -> None:
        index = pd.date_range("2013-01-01", periods=5200, freq="D")
        trend = np.linspace(100.0, 80000.0, len(index))
        oscillation = 2000.0 * np.sin(np.arange(len(index)) / 140.0)
        btc_price = pd.Series(trend + oscillation, index=index, name="btc_price")

        onchain = pd.DataFrame(
            {
                "mvrv_z_score": np.linspace(-0.5, 6.0, len(index)),
                "puell_multiple": 0.8 + 0.7 * np.sin(np.arange(len(index)) / 180.0),
                "supply_in_profit": np.clip(0.4 + 0.3 * np.sin(np.arange(len(index)) / 160.0), 0.0, 1.0),
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

        cwd = Path.cwd()
        cfg = RuntimeConfig(
            project_root=cwd,
            data_dir=cwd / "data",
            output_dir=cwd / "output",
            cache_dir=cwd / "data",
        )

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
