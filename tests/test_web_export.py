import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from risk_engine.types import RiskOutput
from risk_engine.validation import ValidationResult
from risk_engine.web_export import (
    WEB_V2_ARTIFACTS,
    _canonical_json_number,
    export_web_v2,
    validate_web_release,
)


class WebExportTests(unittest.TestCase):
    def _sample_result(self) -> RiskOutput:
        index = pd.to_datetime(["2026-04-22", "2026-04-23", "2026-04-24"])
        series = pd.DataFrame(
            {
                "btc_risk_signal": [0.1, 0.2, 0.3],
                "btc_risk_attention": [0.4, 0.5, 0.6],
                "btc_risk_confidence": [0.7, 0.8, 0.9],
                "btc_risk_coverage": [0.5, 0.6, 0.7],
                "total_market_risk_signal": [0.1, 0.2, 0.3],
                "total_market_risk_attention": [0.2, 0.3, 0.4],
                "total_market_risk_confidence": [0.6, 0.7, 0.8],
                "total_market_risk_coverage": [0.4, 0.5, 0.6],
                "headline_attention": [0.34, 0.41, 0.48],
                "trend_composite_score": [0.04, 0.08, 0.12],
                "cycle_extension_score": [0.24, 0.29, 0.35],
                "confidence_score": [0.67, 0.74, 0.82],
                "cycle_frenzy_score": [0.22, 0.24, 0.27],
                "cycle_accumulation_score": [0.71, 0.68, 0.65],
                "cycle_p_frenzy": [0.33, 0.35, 0.38],
                "cycle_p_accumulation": [0.79, 0.76, 0.72],
                "cycle_confidence": [0.8, 0.81, 0.82],
                "cycle_position": [1.0, 1.0, 1.0],
                "cycle_signal_regime": ["HOLD", "HOLD", "HOLD"],
                "top_reversal_risk": [0.42, 0.45, 0.48],
                "bottom_reversal_risk": [0.61, 0.58, 0.55],
                "dca_risk": [0.2, 0.35, 0.48],
                "dca_top_reversal_component": [0.5, 1.0, 1.0],
                "dca_bottom_reversal_component": [0.5, 1.0, 1.0],
                "dca_cycle_extension_component": [0.5, 1.0, 1.0],
                "dca_cycle_regime_component": [0.5, 1.0, 1.0],
                "dca_component_coverage": [1.0, 1.0, 1.0],
                "attention_score": [0.34, 0.41, 0.48],
                "btc_price": [70000.0, 71000.0, 72000.0],
                "total_market_cap": [2.5e12, 2.55e12, 2.6e12],
            },
            index=index,
        )

        category = pd.DataFrame(
            {
                "category_price_structure_signal": [0.1, 0.2, 0.3],
                "category_price_structure_attention": [0.2, 0.3, 0.4],
            },
            index=index,
        )

        metrics = pd.DataFrame(
            {
                "metric_btc_log_reg_deviation__btc__price_structure_signal": [0.2, 0.25, 0.3],
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
            benchmark_baseline={"summary": []},
            benchmark_deltas={"summary": []},
            benchmark_regression_warnings=["benchmark_top_recall_regression:-0.03<-0.02"],
            operational_alert_policy={"top_alert_rate": 0.15, "bottom_alert_rate": 0.25},
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
            export_result = export_web_v2(
                result,
                validation,
                target_root=Path(tmp_dir) / "data" / "web",
                sanity_report=sanity,
                generated_at="2026-04-24T06:00:00Z",
            )

            generated_names = sorted(path.name for path in export_result.files)
            self.assertEqual(generated_names, sorted(WEB_V2_ARTIFACTS))

            manifest_path = export_result.root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], "v2")
            self.assertEqual(manifest["schema_version"], "2.0.0")
            self.assertEqual(sorted(manifest["artifacts"]), sorted(WEB_V2_ARTIFACTS))
            self.assertTrue(manifest["release_id"].startswith("web-v2-"))
            self.assertEqual(validate_web_release(export_result.root)["release_id"], manifest["release_id"])
            self.assertEqual(set(manifest["integrity"]), set(WEB_V2_ARTIFACTS) - {"manifest.json"})

            latest = json.loads((export_result.root / "latest_snapshot.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["release_id"], manifest["release_id"])
            self.assertEqual(latest["date"], "2026-04-24")
            self.assertIn("btc_risk", latest)
            self.assertIn("total_market_risk", latest)
            self.assertIn("confidence_score", latest)
            self.assertIn("cycle_extension_score", latest)
            self.assertIn("top_reversal_risk", latest)
            self.assertIn("bottom_reversal_risk", latest)
            self.assertIn("dca_risk", latest)
            self.assertIn("dca_model", latest)
            self.assertIn("attention_score", latest)
            self.assertIsNotNone(latest["top_reversal_risk"])
            self.assertIsNotNone(latest["bottom_reversal_risk"])
            self.assertIsNotNone(latest["dca_risk"])
            self.assertIn("cycle_regime_component", latest["dca_model"])
            self.assertIsNotNone(latest["cycle_extension_score"])
            self.assertIsNotNone(latest["attention_score"])
            self.assertIn("cycle_model", latest)
            self.assertIn("frenzy_score", latest["cycle_model"])
            self.assertIn("p_frenzy", latest["cycle_model"])

            history = json.loads((export_result.root / "history_core.json").read_text(encoding="utf-8"))
            self.assertEqual(history["index"], ["2026-04-22", "2026-04-23", "2026-04-24"])
            self.assertIn("trend_composite_score", history["columns"])
            self.assertIn("total_market_cap", history["columns"])
            self.assertIn("dca_risk", history["columns"])
            self.assertIn("dca_cycle_regime_component", history["columns"])

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
            self.assertIn("benchmark_baseline", diagnostics)
            self.assertIn("benchmark_deltas", diagnostics)
            self.assertIn("benchmark_regression_warnings", diagnostics)
            self.assertIn("financial_benchmark_summary", diagnostics)
            self.assertIn("financial_benchmark_curves", diagnostics)
            self.assertIn("operational_alert_policy", diagnostics)
            self.assertIn("calibration_metadata", diagnostics)
            self.assertEqual(diagnostics["benchmark_config"]["alert_rate"], 0.2)
            self.assertTrue(any(row["mode"] == "unavailable" for row in diagnostics["source_modes"]))


class CanonicalJsonNumberTests(unittest.TestCase):
    """scripts/lib/release-integrity.mjs recomputes each artifact's canonical
    digest in JS after JSON.parse, so _canonical_json_number must match what
    JS's native Number-to-string produces byte-for-byte, or CI's
    validate-web-release.mjs will reject every release (manifest canonical
    content digests do not match artifacts)."""

    def test_whole_number_floats_serialize_without_decimal_point(self) -> None:
        # JS's JSON.stringify(JSON.parse("1.0")) is "1", not "1.0".
        self.assertEqual(_canonical_json_number(1.0), "1")
        self.assertEqual(_canonical_json_number(-42.0), "-42")

    def test_small_magnitude_floats_use_plain_decimal_like_javascript(self) -> None:
        # JS's Number#toString only switches to scientific notation below 1e-6;
        # Python's repr()/json.dumps switch around 1e-4.
        self.assertEqual(_canonical_json_number(2.20577400667163e-05), "0.0000220577400667163")
        self.assertEqual(_canonical_json_number(-0.00033224551075938504), "-0.00033224551075938504")

    def test_floats_below_1e_minus_6_use_scientific_notation_like_javascript(self) -> None:
        self.assertEqual(_canonical_json_number(-5.403790920555968e-07), "-5.403790920555968e-7")

    def test_negative_zero_serializes_as_zero(self) -> None:
        self.assertEqual(_canonical_json_number(-0.0), "0")


if __name__ == "__main__":
    unittest.main()
