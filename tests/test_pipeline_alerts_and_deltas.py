import tempfile
import unittest
from pathlib import Path

import pandas as pd

from risk_engine.pipeline import (
    _build_operational_alert_policy,
    _delta_records,
    _load_benchmark_baseline,
    _metric_reliability_adjustments,
)


class PipelineAlertsAndDeltasTests(unittest.TestCase):
    def test_operational_alert_policy_respects_min_history(self) -> None:
        index = pd.date_range("2020-01-31", periods=12, freq=pd.offsets.MonthEnd())
        scores = pd.Series([0.1, 0.2, 0.9, 0.8, 0.95, 0.7, 0.6, 0.99, 0.4, 0.3, 0.2, 0.1], index=index)
        out = _build_operational_alert_policy(scores, alert_rate=0.2, cooldown_months=2, min_history_months=6)
        self.assertTrue(out["alert"].iloc[:5].fillna(0.0).eq(0.0).all())

    def test_operational_alert_policy_respects_cooldown(self) -> None:
        index = pd.date_range("2020-01-31", periods=10, freq=pd.offsets.MonthEnd())
        scores = pd.Series([0.1, 0.2, 0.3, 0.95, 0.96, 0.97, 0.98, 0.2, 0.99, 1.0], index=index)
        out = _build_operational_alert_policy(scores, alert_rate=0.2, cooldown_months=2, min_history_months=1)
        alert_dates = out.index[out["alert"] > 0.5]
        for i in range(1, len(alert_dates)):
            months = (alert_dates[i].year - alert_dates[i - 1].year) * 12 + (alert_dates[i].month - alert_dates[i - 1].month)
            self.assertGreaterEqual(months, 3)

    def test_delta_records_emits_metric_deltas(self) -> None:
        cur = pd.DataFrame([{"window": "recent", "signal": "top", "auc": 0.7}])
        base = pd.DataFrame([{"window": "recent", "signal": "top", "auc": 0.6}])
        rows = _delta_records(cur, base, key_cols=["window", "signal"], metric_cols=["auc"])
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["auc_delta"], 0.1, places=6)

    def test_load_benchmark_baseline_invalid_json_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{bad", encoding="utf-8")
            out = _load_benchmark_baseline(path)
            self.assertEqual(out, {})

    def test_metric_reliability_adjustments(self) -> None:
        out = _metric_reliability_adjustments(
            {
                "a": "cmc_api",
                "b": "local_cache",
                "c": "unavailable",
            }
        )
        self.assertEqual(out["a"], 1.0)
        self.assertEqual(out["b"], 0.75)
        self.assertEqual(out["c"], 0.0)


if __name__ == "__main__":
    unittest.main()
