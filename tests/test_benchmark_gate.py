import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from risk_engine.benchmark_gate import evaluate_benchmark_gate
from risk_engine.config import RuntimeConfig
from risk_engine.types import RiskOutput


def _runtime() -> RuntimeConfig:
    cwd = Path.cwd()
    return RuntimeConfig(
        project_root=cwd,
        data_dir=cwd / "data",
        output_dir=cwd / "output",
        cache_dir=cwd / "data",
        benchmark_delta_warn_top_recall=-0.02,
        benchmark_delta_warn_top_pr_auc=-0.01,
        benchmark_delta_warn_top_false_alarm=0.03,
        benchmark_foundation_min_top_recall_delta=0.0,
        benchmark_foundation_min_top_pr_auc_delta=0.0,
        benchmark_foundation_max_top_false_alarm_delta=0.05,
    )


def _runtime_with_defaults() -> RuntimeConfig:
    cwd = Path.cwd()
    return RuntimeConfig(
        project_root=cwd,
        data_dir=cwd / "data",
        output_dir=cwd / "output",
        cache_dir=cwd / "data",
    )


def _result(
    by_signal: pd.DataFrame,
    summary: pd.DataFrame,
    financial_summary: pd.DataFrame | None = None,
) -> RiskOutput:
    return RiskOutput(
        series=pd.DataFrame(),
        feature_frames={},
        benchmark_by_signal=by_signal,
        benchmark_summary=summary,
        financial_benchmark_summary=financial_summary if financial_summary is not None else pd.DataFrame(),
    )


class BenchmarkGateTests(unittest.TestCase):
    def test_gate_passes_on_improvement(self) -> None:
        baseline = {
            "by_signal": [
                {
                    "window": "recent",
                    "signal": "top_reversal_risk",
                    "auc": 0.40,
                    "pr_auc": 0.20,
                    "lead_recall_at_alert_rate": 0.30,
                    "false_alarm_rate": 0.60,
                }
            ],
            "summary": [
                {
                    "kpi": "lead_recall_top",
                    "signal": "top_reversal_risk",
                    "expanding": 0.50,
                    "recent": 0.30,
                    "delta_recent_minus_expanding": -0.20,
                }
            ],
        }
        foundation = {
            "by_signal": [
                {
                    "window": "recent",
                    "signal": "top_reversal_risk",
                    "auc": 0.38,
                    "pr_auc": 0.18,
                    "lead_recall_at_alert_rate": 0.28,
                    "false_alarm_rate": 0.63,
                }
            ],
            "summary": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            sota_path = Path(tmp) / "sota.json"
            foundation_path = Path(tmp) / "foundation.json"
            sota_path.write_text(json.dumps(baseline), encoding="utf-8")
            foundation_path.write_text(json.dumps(foundation), encoding="utf-8")

            by_signal = pd.DataFrame(
                [
                    {
                        "window": "recent",
                        "signal": "top_reversal_risk",
                        "auc": 0.45,
                        "pr_auc": 0.27,
                        "lead_recall_at_alert_rate": 0.36,
                        "false_alarm_rate": 0.61,
                    }
                ]
            )
            summary = pd.DataFrame(
                [
                    {
                        "kpi": "lead_recall_top",
                        "signal": "top_reversal_risk",
                        "expanding": 0.52,
                        "recent": 0.36,
                        "delta_recent_minus_expanding": -0.16,
                    }
                ]
            )

            with patch("risk_engine.benchmark_gate.run_pipeline", return_value=_result(by_signal, summary)):
                report = evaluate_benchmark_gate(_runtime(), sota_path=sota_path, foundation_path=foundation_path)

        self.assertTrue(report.passed)
        self.assertTrue(any("Gate status: PASS" in line for line in report.lines))

    def test_gate_fails_on_pr_auc_regression(self) -> None:
        baseline = {
            "by_signal": [
                {
                    "window": "recent",
                    "signal": "top_reversal_risk",
                    "auc": 0.40,
                    "pr_auc": 0.20,
                    "lead_recall_at_alert_rate": 0.30,
                    "false_alarm_rate": 0.60,
                }
            ],
            "summary": [],
        }
        foundation = {
            "by_signal": [
                {
                    "window": "recent",
                    "signal": "top_reversal_risk",
                    "auc": 0.39,
                    "pr_auc": 0.14,
                    "lead_recall_at_alert_rate": 0.29,
                    "false_alarm_rate": 0.62,
                }
            ],
            "summary": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            sota_path = Path(tmp) / "sota.json"
            foundation_path = Path(tmp) / "foundation.json"
            sota_path.write_text(json.dumps(baseline), encoding="utf-8")
            foundation_path.write_text(json.dumps(foundation), encoding="utf-8")

            by_signal = pd.DataFrame(
                [
                    {
                        "window": "recent",
                        "signal": "top_reversal_risk",
                        "auc": 0.42,
                        "pr_auc": 0.15,
                        "lead_recall_at_alert_rate": 0.31,
                        "false_alarm_rate": 0.60,
                    }
                ]
            )

            with patch(
                "risk_engine.benchmark_gate.run_pipeline",
                return_value=_result(by_signal, pd.DataFrame()),
            ):
                report = evaluate_benchmark_gate(_runtime(), sota_path=sota_path, foundation_path=foundation_path)

        self.assertFalse(report.passed)
        self.assertTrue(any("Gate status: FAIL" in line for line in report.lines))

    def test_gate_fails_when_below_foundation(self) -> None:
        sota = {
            "by_signal": [
                {
                    "window": "recent",
                    "signal": "top_reversal_risk",
                    "auc": 0.30,
                    "pr_auc": 0.10,
                    "lead_recall_at_alert_rate": 0.20,
                    "false_alarm_rate": 0.70,
                }
            ],
            "summary": [],
        }
        foundation = {
            "by_signal": [
                {
                    "window": "recent",
                    "signal": "top_reversal_risk",
                    "auc": 0.45,
                    "pr_auc": 0.25,
                    "lead_recall_at_alert_rate": 0.35,
                    "false_alarm_rate": 0.55,
                }
            ],
            "summary": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            sota_path = Path(tmp) / "sota.json"
            foundation_path = Path(tmp) / "foundation.json"
            sota_path.write_text(json.dumps(sota), encoding="utf-8")
            foundation_path.write_text(json.dumps(foundation), encoding="utf-8")

            by_signal = pd.DataFrame(
                [
                    {
                        "window": "recent",
                        "signal": "top_reversal_risk",
                        "auc": 0.42,
                        "pr_auc": 0.20,
                        "lead_recall_at_alert_rate": 0.30,
                        "false_alarm_rate": 0.63,
                    }
                ]
            )
            with patch(
                "risk_engine.benchmark_gate.run_pipeline",
                return_value=_result(by_signal, pd.DataFrame()),
            ):
                report = evaluate_benchmark_gate(_runtime(), sota_path=sota_path, foundation_path=foundation_path)
        self.assertFalse(report.passed)
        self.assertTrue(any("[vs foundation]" in line for line in report.lines))

    def test_default_gate_allows_tiny_foundation_pr_auc_dip(self) -> None:
        baseline = {
            "by_signal": [
                {
                    "window": "recent",
                    "signal": "top_reversal_risk",
                    "auc": 0.585455,
                    "pr_auc": 0.865467,
                    "lead_recall_at_alert_rate": 1.0,
                    "false_alarm_rate": 0.066667,
                }
            ],
            "summary": [],
        }
        foundation = baseline

        with tempfile.TemporaryDirectory() as tmp:
            sota_path = Path(tmp) / "sota.json"
            foundation_path = Path(tmp) / "foundation.json"
            sota_path.write_text(json.dumps(baseline), encoding="utf-8")
            foundation_path.write_text(json.dumps(foundation), encoding="utf-8")

            by_signal = pd.DataFrame(
                [
                    {
                        "window": "recent",
                        "signal": "top_reversal_risk",
                        "auc": 0.590909,
                        "pr_auc": 0.864177,
                        "lead_recall_at_alert_rate": 1.0,
                        "false_alarm_rate": 0.066667,
                    }
                ]
            )
            with patch(
                "risk_engine.benchmark_gate.run_pipeline",
                return_value=_result(by_signal, pd.DataFrame()),
            ):
                report = evaluate_benchmark_gate(_runtime_with_defaults(), sota_path=sota_path, foundation_path=foundation_path)

        self.assertTrue(report.passed)
        self.assertTrue(any("Gate status: PASS" in line for line in report.lines))

    def test_default_gate_still_fails_larger_foundation_pr_auc_dip(self) -> None:
        baseline = {
            "by_signal": [
                {
                    "window": "recent",
                    "signal": "top_reversal_risk",
                    "auc": 0.585455,
                    "pr_auc": 0.865467,
                    "lead_recall_at_alert_rate": 1.0,
                    "false_alarm_rate": 0.066667,
                }
            ],
            "summary": [],
        }
        foundation = baseline

        with tempfile.TemporaryDirectory() as tmp:
            sota_path = Path(tmp) / "sota.json"
            foundation_path = Path(tmp) / "foundation.json"
            sota_path.write_text(json.dumps(baseline), encoding="utf-8")
            foundation_path.write_text(json.dumps(foundation), encoding="utf-8")

            by_signal = pd.DataFrame(
                [
                    {
                        "window": "recent",
                        "signal": "top_reversal_risk",
                        "auc": 0.590909,
                        "pr_auc": 0.862000,
                        "lead_recall_at_alert_rate": 1.0,
                        "false_alarm_rate": 0.066667,
                    }
                ]
            )
            with patch(
                "risk_engine.benchmark_gate.run_pipeline",
                return_value=_result(by_signal, pd.DataFrame()),
            ):
                report = evaluate_benchmark_gate(_runtime_with_defaults(), sota_path=sota_path, foundation_path=foundation_path)

        self.assertFalse(report.passed)
        self.assertTrue(any("[vs foundation] top PR-AUC delta" in line for line in report.lines))

    def test_gate_falls_back_to_expanding_signal_rows_when_recent_is_missing(self) -> None:
        baseline = {
            "by_signal": [
                {
                    "window": "expanding",
                    "signal": "top_reversal_risk",
                    "auc": 0.50,
                    "pr_auc": 0.30,
                    "lead_recall_at_alert_rate": 0.60,
                    "false_alarm_rate": 0.20,
                }
            ],
            "summary": [],
        }
        foundation = baseline

        with tempfile.TemporaryDirectory() as tmp:
            sota_path = Path(tmp) / "sota.json"
            foundation_path = Path(tmp) / "foundation.json"
            sota_path.write_text(json.dumps(baseline), encoding="utf-8")
            foundation_path.write_text(json.dumps(foundation), encoding="utf-8")

            by_signal = pd.DataFrame(
                [
                    {
                        "window": "expanding",
                        "signal": "top_reversal_risk",
                        "auc": 0.52,
                        "pr_auc": 0.32,
                        "lead_recall_at_alert_rate": 0.62,
                        "false_alarm_rate": 0.19,
                    }
                ]
            )
            with patch(
                "risk_engine.benchmark_gate.run_pipeline",
                return_value=_result(by_signal, pd.DataFrame()),
            ):
                report = evaluate_benchmark_gate(_runtime(), sota_path=sota_path, foundation_path=foundation_path)

        self.assertTrue(report.passed)
        self.assertTrue(any("recent window unavailable" in line for line in report.lines))
        self.assertTrue(any("top_reversal_risk.auc: current=0.520000" in line for line in report.lines))
        self.assertFalse(any("top_reversal_risk.auc: current=nan" in line for line in report.lines))

    def test_gate_treats_less_negative_max_drawdown_as_improvement(self) -> None:
        baseline = {
            "by_signal": [],
            "summary": [],
            "financial_summary": [
                {
                    "strategy": "dynamic_dca",
                    "cagr": 0.70,
                    "calmar": 1.10,
                    "max_drawdown": -0.62,
                    "total_return": 100.0,
                }
            ],
        }
        foundation = baseline

        with tempfile.TemporaryDirectory() as tmp:
            sota_path = Path(tmp) / "sota.json"
            foundation_path = Path(tmp) / "foundation.json"
            sota_path.write_text(json.dumps(baseline), encoding="utf-8")
            foundation_path.write_text(json.dumps(foundation), encoding="utf-8")

            financial_summary = pd.DataFrame(
                [
                    {
                        "strategy": "dynamic_dca",
                        "cagr": 0.72,
                        "calmar": 1.20,
                        "max_drawdown": -0.54,
                        "total_return": 110.0,
                    }
                ]
            )
            with patch(
                "risk_engine.benchmark_gate.run_pipeline",
                return_value=_result(pd.DataFrame(), pd.DataFrame(), financial_summary),
            ):
                report = evaluate_benchmark_gate(_runtime(), sota_path=sota_path, foundation_path=foundation_path)

        self.assertTrue(report.passed)
        self.assertTrue(any("depth_delta_vs_sota=-0.080000" in line for line in report.lines))

    def test_gate_fails_when_max_drawdown_depth_regresses(self) -> None:
        baseline = {
            "by_signal": [],
            "summary": [],
            "financial_summary": [
                {
                    "strategy": "dynamic_dca",
                    "cagr": 0.70,
                    "calmar": 1.10,
                    "max_drawdown": -0.62,
                    "total_return": 100.0,
                }
            ],
        }
        foundation = baseline

        with tempfile.TemporaryDirectory() as tmp:
            sota_path = Path(tmp) / "sota.json"
            foundation_path = Path(tmp) / "foundation.json"
            sota_path.write_text(json.dumps(baseline), encoding="utf-8")
            foundation_path.write_text(json.dumps(foundation), encoding="utf-8")

            financial_summary = pd.DataFrame(
                [
                    {
                        "strategy": "dynamic_dca",
                        "cagr": 0.72,
                        "calmar": 1.20,
                        "max_drawdown": -0.70,
                        "total_return": 110.0,
                    }
                ]
            )
            with patch(
                "risk_engine.benchmark_gate.run_pipeline",
                return_value=_result(pd.DataFrame(), pd.DataFrame(), financial_summary),
            ):
                report = evaluate_benchmark_gate(_runtime(), sota_path=sota_path, foundation_path=foundation_path)

        self.assertFalse(report.passed)
        self.assertTrue(any("[vs SOTA] dynamic DCA max-drawdown depth delta 0.080000" in line for line in report.lines))
        self.assertTrue(
            any("[vs foundation] dynamic DCA max-drawdown depth delta 0.080000" in line for line in report.lines)
        )


if __name__ == "__main__":
    unittest.main()
