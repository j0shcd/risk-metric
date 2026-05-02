import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from risk_engine.benchmark import evaluate_benchmark
from risk_engine.config import RuntimeConfig


class BenchmarkEdgeTests(unittest.TestCase):
    def _cfg(self, **kwargs) -> RuntimeConfig:
        cwd = Path.cwd()
        return RuntimeConfig(project_root=cwd, data_dir=cwd / "data", output_dir=cwd / "output", cache_dir=cwd / "data", **kwargs)

    def test_benchmark_disabled(self) -> None:
        cfg = self._cfg(benchmark_enabled=False)
        out = evaluate_benchmark(cfg, monthly_price=pd.Series(dtype=float), signals={})
        self.assertIn("benchmark_disabled", out.warnings)

    def test_benchmark_unavailable_when_missing_inputs(self) -> None:
        cfg = self._cfg()
        out = evaluate_benchmark(cfg, monthly_price=pd.Series(dtype=float), signals={"x": pd.Series(dtype=float)})
        self.assertTrue(any("benchmark_unavailable" in w for w in out.warnings))

    def test_low_event_warning_present(self) -> None:
        idx = pd.date_range("2018-01-31", periods=80, freq=pd.offsets.MonthEnd())
        price = pd.Series(np.linspace(100.0, 200.0, len(idx)), index=idx)
        signal = pd.Series(np.linspace(0.1, 0.9, len(idx)), index=idx)
        cfg = self._cfg(benchmark_top_drawdown_thresholds=[0.9], benchmark_bottom_rally_thresholds=[5.0])
        out = evaluate_benchmark(cfg, monthly_price=price, signals={"trend_heat": signal, "top_reversal_risk": signal, "bottom_reversal_risk": 1.0 - signal, "attention_score": signal})
        self.assertTrue(any("benchmark_low_event_count" in w for w in out.warnings))


if __name__ == "__main__":
    unittest.main()
