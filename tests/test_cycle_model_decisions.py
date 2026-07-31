import unittest

import pandas as pd

from risk_engine.config import RuntimeConfig
from risk_engine.cycle_model import _build_signal_decisions, _top_trigger_categories


class CycleModelDecisionTests(unittest.TestCase):
    def _cfg(self, **kwargs) -> RuntimeConfig:
        from pathlib import Path

        cwd = Path.cwd()
        return RuntimeConfig(project_root=cwd, data_dir=cwd / "data", output_dir=cwd / "output", cache_dir=cwd / "data", **kwargs)

    def test_top_trigger_categories_returns_sorted_names(self) -> None:
        row = pd.Series({"valuation_hot": 0.8, "speculation_hot": 0.9, "attention_hot": 0.1, "macro_hot": 0.5})
        out = _top_trigger_categories(row, suffix="hot", limit=2)
        self.assertEqual(out, "speculation,valuation")

    def test_signal_decision_respects_confirmation_and_cooldown(self) -> None:
        idx = pd.date_range("2024-01-31", periods=8, freq=pd.offsets.MonthEnd())
        regime = pd.DataFrame(
            {
                "p_accumulation": [0.1, 0.8, 0.85, 0.2, 0.8, 0.85, 0.1, 0.1],
                "p_frenzy": [0.1] * 8,
            },
            index=idx,
        )
        features = pd.DataFrame(
            {
                "valuation_cold": [0.9] * 8,
                "speculation_cold": [0.8] * 8,
                "attention_cold": [0.1] * 8,
                "macro_cold": [0.2] * 8,
            },
            index=idx,
        )
        cfg = self._cfg(cycle_buy_threshold=0.75, cycle_confirmation_months=2, cycle_cooldown_months=2)
        out = _build_signal_decisions(features, regime, cfg)
        buy_dates = out.index[out["regime"] == "BUY"]
        self.assertEqual(len(buy_dates), 1)
        self.assertGreaterEqual(int(out.loc[buy_dates[0], "cooldown_state"]), 1)

    def test_cooldown_blocks_the_configured_number_of_full_months(self) -> None:
        idx = pd.date_range("2024-01-31", periods=5, freq=pd.offsets.MonthEnd())
        regime = pd.DataFrame(
            {
                "p_accumulation": [0.9, 0.1, 0.1, 0.1, 0.1],
                "p_frenzy": [0.1, 0.9, 0.9, 0.9, 0.9],
            },
            index=idx,
        )
        features = pd.DataFrame(
            {
                "valuation_cold": 0.9,
                "speculation_cold": 0.8,
                "attention_cold": 0.1,
                "macro_cold": 0.2,
                "valuation_hot": 0.9,
                "speculation_hot": 0.8,
                "attention_hot": 0.1,
                "macro_hot": 0.2,
            },
            index=idx,
        )
        cfg = self._cfg(cycle_buy_threshold=0.75, cycle_sell_threshold=0.75, cycle_confirmation_months=1, cycle_cooldown_months=2)

        out = _build_signal_decisions(features, regime, cfg)

        self.assertEqual(out["regime"].tolist(), ["BUY", "HOLD", "HOLD", "SELL", "HOLD"])


if __name__ == "__main__":
    unittest.main()
