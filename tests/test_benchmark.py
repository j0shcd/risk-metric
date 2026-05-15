import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from risk_engine.benchmark import evaluate_benchmark
from risk_engine.config import RuntimeConfig


class BenchmarkTests(unittest.TestCase):
    def test_benchmark_generates_multilabel_metrics(self) -> None:
        index = pd.date_range("2013-01-31", periods=180, freq=pd.offsets.MonthEnd())
        x = np.arange(len(index), dtype=float)

        price = pd.Series(
            1000.0 + 150.0 * x + 4000.0 * np.sin(x / 6.0),
            index=index,
            name="btc_price",
        )

        signals = {
            "trend_composite_score": pd.Series((0.5 + 0.3 * np.sin(x / 9.0)).clip(0.0, 1.0), index=index),
            "top_reversal_risk": pd.Series((0.5 + 0.35 * np.sin(x / 8.0 + 0.3)).clip(0.0, 1.0), index=index),
            "bottom_reversal_risk": pd.Series((0.5 - 0.35 * np.sin(x / 8.0 + 0.3)).clip(0.0, 1.0), index=index),
            "attention_score": pd.Series((0.4 + 0.25 * np.abs(np.sin(x / 7.0))).clip(0.0, 1.0), index=index),
        }

        cwd = Path.cwd()
        cfg = RuntimeConfig(
            project_root=cwd,
            data_dir=cwd / "data",
            output_dir=cwd / "output",
            cache_dir=cwd / "data",
        )

        result = evaluate_benchmark(cfg, monthly_price=price, signals=signals)

        self.assertFalse(result.summary.empty)
        self.assertFalse(result.by_label.empty)
        self.assertFalse(result.by_signal.empty)
        self.assertFalse(result.window_stats.empty)

        families = set(result.by_label["family"].astype(str).unique().tolist())
        self.assertIn("threshold", families)
        self.assertIn("quantile", families)
        self.assertIn("local_extrema", families)

        self.assertIn("lead_recall_at_alert_rate", result.by_label.columns)
        self.assertIn("median_lead_months", result.by_label.columns)
        self.assertIn("false_alarm_rate", result.by_label.columns)
        self.assertIn("event_coverage", result.by_label.columns)
        self.assertIn("event_weight", result.by_label.columns)
        self.assertIn("aggregation_method", result.by_signal.columns)
        self.assertIn("effective_weight_sum", result.by_signal.columns)
        self.assertIn("effective_label_count", result.by_signal.columns)

    def test_benchmark_respects_recent_window_config(self) -> None:
        index = pd.date_range("2016-01-31", periods=120, freq=pd.offsets.MonthEnd())
        x = np.arange(len(index), dtype=float)

        price = pd.Series(1000.0 + 80.0 * x + 1200.0 * np.sin(x / 5.0), index=index)
        signal = pd.Series((0.5 + 0.2 * np.sin(x / 6.0)).clip(0.0, 1.0), index=index)

        cwd = Path.cwd()
        cfg = RuntimeConfig(
            project_root=cwd,
            data_dir=cwd / "data",
            output_dir=cwd / "output",
            cache_dir=cwd / "data",
            benchmark_recent_window_months=24,
        )

        result = evaluate_benchmark(
            cfg,
            monthly_price=price,
            signals={
                "trend_composite_score": signal,
                "top_reversal_risk": signal,
                "bottom_reversal_risk": 1.0 - signal,
                "attention_score": signal,
            },
        )

        windows = set(result.by_label["window"].astype(str).unique().tolist())
        self.assertIn("expanding", windows)
        self.assertIn("recent", windows)

    def test_event_weight_is_soft_capped(self) -> None:
        index = pd.date_range("2017-01-31", periods=120, freq=pd.offsets.MonthEnd())
        price = pd.Series(np.linspace(1000.0, 6000.0, len(index)), index=index)
        signal = pd.Series(np.linspace(0.1, 0.9, len(index)), index=index)

        cwd = Path.cwd()
        cfg = RuntimeConfig(
            project_root=cwd,
            data_dir=cwd / "data",
            output_dir=cwd / "output",
            cache_dir=cwd / "data",
            benchmark_event_weight_pivot=5,
        )
        result = evaluate_benchmark(
            cfg,
            monthly_price=price,
            signals={
                "trend_composite_score": signal,
                "top_reversal_risk": signal,
                "bottom_reversal_risk": 1.0 - signal,
                "attention_score": signal,
            },
        )
        weights = result.by_label["event_weight"].dropna()
        self.assertTrue(((weights >= 0.0) & (weights <= 1.0)).all())


if __name__ == "__main__":
    unittest.main()
