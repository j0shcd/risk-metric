import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from risk_engine.types import RiskOutput
from risk_engine.validation import ValidationResult
from risk_engine.web_export import WEB_V1_ARTIFACTS, export_web_v1


class WebExportTests(unittest.TestCase):
    def _sample_result(self) -> RiskOutput:
        index = pd.to_datetime(["2026-04-22", "2026-04-23", "2026-04-24"])
        series = pd.DataFrame(
            {
                "btc_risk_heat": [0.1, 0.2, 0.3],
                "btc_risk_attention": [0.4, 0.5, 0.6],
                "btc_risk_confidence": [0.7, 0.8, 0.9],
                "btc_risk_coverage": [0.5, 0.6, 0.7],
                "total_market_risk_heat": [0.1, 0.2, 0.3],
                "total_market_risk_attention": [0.2, 0.3, 0.4],
                "total_market_risk_confidence": [0.6, 0.7, 0.8],
                "total_market_risk_coverage": [0.4, 0.5, 0.6],
                "headline_attention": [0.34, 0.41, 0.48],
                "headline_heat": [0.04, 0.08, 0.12],
                "confidence_score": [0.67, 0.74, 0.82],
                "cycle_heat_score": [0.22, 0.24, 0.27],
                "cycle_cold_score": [0.71, 0.68, 0.65],
                "cycle_p_frenzy": [0.33, 0.35, 0.38],
                "cycle_p_accumulation": [0.79, 0.76, 0.72],
                "cycle_confidence": [0.8, 0.81, 0.82],
                "cycle_position": [1.0, 1.0, 1.0],
                "cycle_signal_regime": ["HOLD", "HOLD", "HOLD"],
                "btc_price": [70000.0, 71000.0, 72000.0],
                "total_market_cap": [2.5e12, 2.55e12, 2.6e12],
            },
            index=index,
        )

        category = pd.DataFrame(
            {
                "category_price_structure_heat": [0.1, 0.2, 0.3],
                "category_price_structure_attention": [0.2, 0.3, 0.4],
            },
            index=index,
        )

        metrics = pd.DataFrame(
            {
                "metric_btc_log_reg_deviation__btc__price_structure_heat": [0.2, 0.25, 0.3],
                "metric_btc_log_reg_deviation__btc__price_structure_attention": [0.1, 0.12, 0.15],
            },
            index=index,
        )

        return RiskOutput(
            series=series,
            feature_frames={},
            metric_health=pd.DataFrame(
                {
                    "metric": ["btc_log_reg_deviation"],
                    "bundle": ["btc_log_reg_deviation__btc__price_structure"],
                    "category": ["price_structure"],
                    "target": ["btc"],
                    "available": [True],
                    "latest_timestamp": [pd.Timestamp("2026-04-24")],
                }
            ),
            source_health=pd.DataFrame(
                {
                    "source": ["btc_price", "social::youtube_interest"],
                    "available": [True, False],
                    "latest_timestamp": [pd.Timestamp("2026-04-24"), pd.NaT],
                    "staleness_days": [0.0, None],
                }
            ),
            source_modes={
                "btc_price": "local_csv",
                "social::youtube_interest": "unavailable",
            },
            category_breakdowns={
                "btc": category,
                "total_market": category,
            },
            metric_breakdowns={
                "btc": metrics,
                "total_market": metrics,
            },
            benchmark_summary=pd.DataFrame(
                [
                    {
                        "kpi": "lead_recall_top",
                        "signal": "top_reversal_risk",
                        "expanding": 0.5,
                        "recent": 0.4,
                        "delta_recent_minus_expanding": -0.1,
                        "alert_rate": 0.2,
                    }
                ]
            ),
            benchmark_by_label=pd.DataFrame(
                [
                    {
                        "window": "recent",
                        "signal": "top_reversal_risk",
                        "label_id": "threshold_top_dd40_h12",
                        "family": "threshold",
                        "side": "top",
                        "lead_recall_at_alert_rate": 0.45,
                    }
                ]
            ),
            benchmark_by_signal=pd.DataFrame(
                [
                    {
                        "window": "recent",
                        "signal": "top_reversal_risk",
                        "auc": 0.61,
                        "pr_auc": 0.42,
                    }
                ]
            ),
            benchmark_window_stats=pd.DataFrame(
                [
                    {
                        "window": "expanding",
                        "side": "top",
                        "lead_recall_at_alert_rate": 0.52,
                    }
                ]
            ),
            benchmark_config={"alert_rate": 0.2, "label_families": ["threshold", "quantile"]},
            benchmark_warnings=["benchmark_note"],
            calibration_metadata={"walkforward_last_train_end": "2026-04-01"},
        )

    def test_export_writes_required_artifacts_and_manifest(self) -> None:
        result = self._sample_result()
        validation = ValidationResult(passed=True, errors=[], warnings=["non-critical source unavailable"])
        sanity = pd.DataFrame(
            [
                {
                    "check": "example",
                    "passed": True,
                    "value": 1.0,
                    "threshold": 0.0,
                    "comparator": ">",
                    "details": "ok",
                }
            ]
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            export_result = export_web_v1(
                result,
                validation,
                target_root=Path(tmp_dir) / "data" / "web",
                sanity_report=sanity,
                generated_at="2026-04-24T06:00:00Z",
            )

            generated_names = sorted(path.name for path in export_result.files)
            self.assertEqual(generated_names, sorted(WEB_V1_ARTIFACTS))

            manifest_path = export_result.root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], "v1")
            self.assertEqual(manifest["schema_version"], "1.0.0")
            self.assertEqual(sorted(manifest["artifacts"]), sorted(WEB_V1_ARTIFACTS))

            latest = json.loads((export_result.root / "latest_snapshot.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["date"], "2026-04-24")
            self.assertIn("btc_risk", latest)
            self.assertIn("total_market_risk", latest)
            self.assertIn("confidence_score", latest)
            self.assertIn("cycle_model", latest)
            self.assertIn("p_frenzy", latest["cycle_model"])

            history = json.loads((export_result.root / "history_core.json").read_text(encoding="utf-8"))
            self.assertEqual(history["index"], ["2026-04-22", "2026-04-23", "2026-04-24"])
            self.assertIn("headline_heat", history["columns"])
            self.assertIn("total_market_cap", history["columns"])

            diagnostics = json.loads((export_result.root / "diagnostics.json").read_text(encoding="utf-8"))
            self.assertIn("source_health", diagnostics)
            self.assertIn("metric_health", diagnostics)
            self.assertIn("source_modes", diagnostics)
            self.assertIn("sanity_report", diagnostics)
            self.assertIn("benchmark_summary", diagnostics)
            self.assertIn("benchmark_by_label", diagnostics)
            self.assertIn("benchmark_by_signal", diagnostics)
            self.assertIn("benchmark_window_stats", diagnostics)
            self.assertIn("benchmark_config", diagnostics)
            self.assertIn("benchmark_warnings", diagnostics)
            self.assertIn("calibration_metadata", diagnostics)
            self.assertEqual(diagnostics["benchmark_config"]["alert_rate"], 0.2)
            self.assertTrue(any(row["mode"] == "unavailable" for row in diagnostics["source_modes"]))


if __name__ == "__main__":
    unittest.main()
