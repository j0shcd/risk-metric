import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from risk_engine.benchmark import evaluate_benchmark
from risk_engine.config import RuntimeConfig
from risk_engine.evaluation import build_evaluation_config, run_evaluation
from risk_engine.evaluation.academic import evaluate_academic_diagnostics
from risk_engine.evaluation.checks import (
    check_benchmark_claim_gate_readiness,
    check_source_availability_metadata,
    summarize_dca_threshold_reachability,
    summarize_practical_strategies,
    summarize_walkforward_robustness,
)
from risk_engine.evaluation.cli import _load_artifact_risk_output, main as evaluation_cli_main
from risk_engine.evaluation.config import config_hash
from risk_engine.evaluation.data import dataframe_fingerprint
from risk_engine.evaluation.practical import (
    _simulate_dca_cashflow,
    compute_threshold_reachability,
    evaluate_practical_strategies,
    evaluate_production_dynamic_dca,
)
from risk_engine.evaluation.robustness import evaluate_walkforward_robustness
from risk_engine.evaluation.strength import evaluate_strength_mapping
from risk_engine.evaluation.validity import evaluate_validity_diagnostics
from risk_engine.evaluation.walkforward import _expanding_quantile_labels, evaluate_walkforward_benchmark
from risk_engine.evaluation.web_summary import build_evaluation_web_summary
from risk_engine.types import RiskOutput


class EvaluationHarnessTests(unittest.TestCase):
    def _risk_output(self) -> RiskOutput:
        index = pd.date_range("2018-01-31", periods=72, freq=pd.offsets.MonthEnd())
        x = np.arange(len(index), dtype=float)
        price = pd.Series(1000.0 + 100.0 * x + 900.0 * np.sin(x / 4.0), index=index, name="btc_price")
        top = pd.Series((0.5 + 0.4 * np.sin(x / 5.0)).clip(0.0, 1.0), index=index)
        bottom = pd.Series((1.0 - top).clip(0.0, 1.0), index=index)
        series = pd.DataFrame(
            {
                "btc_price": price,
                "top_reversal_risk": top,
                "bottom_reversal_risk": bottom,
                "dca_risk": 0.5 * top + 0.5 * bottom,
            },
            index=index,
        )
        cfg = RuntimeConfig(
            project_root=Path.cwd(),
            data_dir=Path.cwd() / "data",
            output_dir=Path.cwd() / "output",
            cache_dir=Path.cwd() / "data",
            benchmark_horizons_months=[12],
            benchmark_label_families=["threshold"],
            benchmark_top_drawdown_thresholds=[0.20],
            benchmark_bottom_rally_thresholds=[0.30],
            benchmark_recent_window_months=24,
        )
        benchmark = evaluate_benchmark(
            cfg,
            monthly_price=price,
            signals={
                "top_reversal_risk": top,
                "bottom_reversal_risk": bottom,
            },
        )
        return RiskOutput(
            series=series,
            feature_frames={},
            source_health=pd.DataFrame(
                {
                    "source": ["btc_price"],
                    "available": [True],
                    "latest_timestamp": [index[-1]],
                    "staleness_days": [1.0],
                    "staleness_threshold_days": [3],
                }
            ),
            source_modes={"btc_price": "local_csv"},
            benchmark_by_label=benchmark.by_label,
            benchmark_by_signal=benchmark.by_signal,
            benchmark_summary=benchmark.summary,
            benchmark_window_stats=benchmark.window_stats,
            benchmark_config=benchmark.config,
            cycle_regime_scores=pd.DataFrame(
                {
                    "frenzy_score": (0.2 + 0.2 * np.sin(x / 8.0)).clip(0.0, 1.0),
                    "accumulation_score": (0.3 + 0.2 * np.cos(x / 7.0)).clip(0.0, 1.0),
                },
                index=index,
            ),
            financial_benchmark_summary=pd.DataFrame(
                {
                    "strategy": ["buy_and_hold", "fixed_dca", "dynamic_dca"],
                    "total_return": [2.0, 1.5, 1.4],
                    "cagr": [0.20, 0.16, 0.15],
                    "max_drawdown": [-0.55, -0.40, -0.38],
                    "calmar": [0.36, 0.40, 0.39],
                    "annualized_volatility": [0.60, 0.42, 0.40],
                }
            ),
            financial_benchmark_curves=pd.DataFrame(
                {
                    "price": price,
                    "buy_and_hold_equity": np.linspace(1.0, 3.0, len(index)),
                    "fixed_dca_equity": np.linspace(1.0, 2.5, len(index)),
                    "dynamic_dca_equity": np.linspace(1.0, 2.4, len(index)),
                    "dynamic_dca_cash": np.linspace(0.0, 10.0, len(index)),
                    "dynamic_dca_units": np.linspace(0.01, 0.05, len(index)),
                    "dynamic_dca_exposure": np.linspace(0.8, 0.9, len(index)),
                    "dynamic_dca_buy_usd": np.ones(len(index)),
                    "dynamic_dca_sell_usd": np.zeros(len(index)),
                    "dynamic_dca_trade_cost_usd": np.full(len(index), 0.001),
                },
                index=index,
            ),
        )

    def test_config_hash_is_stable_across_run_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            first = build_evaluation_config(output_dir=base, profile="smoke", run_id="run-a")
            second = build_evaluation_config(output_dir=base, profile="smoke", run_id="run-b")
            self.assertEqual(config_hash(first), config_hash(second))

    def test_dataframe_fingerprint_changes_when_data_changes(self) -> None:
        index = pd.date_range("2026-01-01", periods=2, freq="D")
        frame = pd.DataFrame({"x": [1.0, 2.0]}, index=index)
        changed = pd.DataFrame({"x": [1.0, 3.0]}, index=index)
        self.assertNotEqual(dataframe_fingerprint("f", frame).sha256, dataframe_fingerprint("f", changed).sha256)

    def test_run_evaluation_writes_manifest_and_sqlite_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "evaluation"
            cfg = build_evaluation_config(output_dir=output_dir, profile="smoke", run_id="test-run")
            result = run_evaluation(self._risk_output(), cfg)

            manifest_path = result.run_dir / "manifest.json"
            self.assertTrue(manifest_path.exists())
            self.assertTrue(result.db_path.exists())

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["run_id"], "test-run")
            self.assertEqual(manifest["profile"], "smoke")
            self.assertIn("data.series_integrity", {item["test_id"] for item in manifest["tests"]})
            self.assertIn("data.source_quality", {item["test_id"] for item in manifest["tests"]})
            self.assertIn("temporal.live_availability", {item["test_id"] for item in manifest["tests"]})
            self.assertIn("temporal.source_availability_metadata", {item["test_id"] for item in manifest["tests"]})
            self.assertIn("validator.benchmark_claim_gate_readiness", {item["test_id"] for item in manifest["tests"]})
            self.assertIn("walkforward.expanding_benchmark", {item["test_id"] for item in manifest["tests"]})
            self.assertIn("robustness.walkforward_nulls", {item["test_id"] for item in manifest["tests"]})
            self.assertIn("academic.calibration_monotonicity", {item["test_id"] for item in manifest["tests"]})
            self.assertIn("validity.label_leakage_sentinels", {item["test_id"] for item in manifest["tests"]})
            self.assertIn("robustness.strength_mapping", {item["test_id"] for item in manifest["tests"]})
            self.assertIn("practical.monthly_strategy_suite", {item["test_id"] for item in manifest["tests"]})
            self.assertIn("practical.dca_threshold_reachability", {item["test_id"] for item in manifest["tests"]})
            self.assertIn("risk_series", {item["name"] for item in manifest["data_fingerprints"]})
            self.assertTrue((result.run_dir / "tables" / "availability_calendar.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "walkforward_by_fold.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "walkforward_by_label.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "walkforward_by_signal.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "walkforward_embargo_audit.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "walkforward_nulls.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "walkforward_baselines.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "reliability_bins.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "monotonicity.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "label_audit.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "shift_probe.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "synthetic_sentinels.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "strategy_results.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "strategy_equity_curves.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "strategy_trades.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "threshold_reachability.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "degraded_data.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "regime_results.csv").exists())
            self.assertTrue((result.run_dir / "tables" / "rolling_stability.csv").exists())
            walkforward_by_label = pd.read_csv(result.run_dir / "tables" / "walkforward_by_label.csv")
            self.assertIn("auc_fdr_q_value", set(walkforward_by_label.columns))
            self.assertIn("passes_regime_concentration_gate", set(walkforward_by_label.columns))
            self.assertIn("spearman_score_label", set(walkforward_by_label.columns))
            self.assertIn("event_cluster_count", set(walkforward_by_label.columns))
            self.assertIn("passes_shift_leakage_probe", set(walkforward_by_label.columns))
            self.assertIn("passes_degraded_data_gate", set(walkforward_by_label.columns))
            self.assertIn("runs/test-run/tables/availability_calendar.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/walkforward_by_fold.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/walkforward_by_label.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/walkforward_embargo_audit.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/walkforward_nulls.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/walkforward_baselines.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/reliability_bins.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/monotonicity.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/label_audit.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/shift_probe.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/synthetic_sentinels.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/strategy_results.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/strategy_equity_curves.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/strategy_trades.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/threshold_reachability.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/degraded_data.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/regime_results.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/tables/rolling_stability.csv", set(manifest["artifacts"]))
            self.assertIn("runs/test-run/manifest.json", set(manifest["artifacts"]))
            self.assertIn("unknown_availability", {item["code"] for item in manifest["warnings"]})
            self.assertIn("unknown_availability", (result.run_dir / "validation_report.md").read_text(encoding="utf-8"))

            with sqlite3.connect(result.db_path) as conn:
                rows = conn.execute("SELECT test_id, status FROM test_results ORDER BY test_id").fetchall()
                self.assertIn(("data.series_integrity", "pass"), rows)
                warnings = conn.execute("SELECT code FROM warnings").fetchall()
                self.assertIn(("unknown_availability",), warnings)
                validator_warning_codes = {row[0] for row in warnings}
                self.assertTrue({"phase2_harness_only", "dashboard_export_blocked"} & validator_warning_codes)

    def test_missing_required_column_blocks_dashboard_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "evaluation"
            cfg = build_evaluation_config(output_dir=output_dir, profile="smoke", run_id="bad-run")
            output = self._risk_output()
            bad_series = output.series.drop(columns=["dca_risk"])
            bad_output = RiskOutput(
                series=bad_series,
                feature_frames={},
                benchmark_by_label=output.benchmark_by_label,
                benchmark_by_signal=output.benchmark_by_signal,
            )
            result = run_evaluation(bad_output, cfg)
            self.assertEqual(result.manifest.status, "fail")
            warning_codes = {warning.code for warning in result.manifest.warnings}
            self.assertIn("dashboard_export_blocked", warning_codes)

    def test_list_tests_exposes_smoke_registry_without_running_pipeline(self) -> None:
        with patch("builtins.print") as mocked_print:
            exit_code = evaluation_cli_main(["list-tests"])
        self.assertEqual(exit_code, 0)
        printed = [call.args[0] for call in mocked_print.call_args_list]
        self.assertIn("data.series_integrity", printed)
        self.assertIn("data.source_quality", printed)
        self.assertIn("temporal.live_availability", printed)
        self.assertIn("temporal.source_availability_metadata", printed)
        self.assertIn("validator.benchmark_claim_gate_readiness", printed)
        self.assertIn("walkforward.expanding_benchmark", printed)
        self.assertIn("robustness.walkforward_nulls", printed)
        self.assertIn("academic.calibration_monotonicity", printed)
        self.assertIn("validity.label_leakage_sentinels", printed)
        self.assertIn("robustness.strength_mapping", printed)
        self.assertIn("practical.monthly_strategy_suite", printed)
        self.assertIn("practical.dca_threshold_reachability", printed)
        self.assertIn("validator.claim_gates", printed)

    def test_production_dynamic_dca_summary_reshapes_into_strategy_rows(self) -> None:
        index = pd.date_range("2020-01-31", periods=4, freq=pd.offsets.MonthEnd())
        summary = pd.DataFrame(
            {
                "strategy": ["buy_and_hold", "fixed_dca", "dynamic_dca"],
                "total_return": [0.40, 0.25, 0.30],
                "cagr": [0.12, 0.08, 0.10],
                "max_drawdown": [-0.30, -0.20, -0.18],
                "calmar": [0.40, 0.40, 0.56],
                "annualized_volatility": [0.50, 0.30, 0.28],
                "ending_value": [np.nan, 400.0, 420.0],
            }
        )
        curves = pd.DataFrame(
            {
                "price": [100.0, 120.0, 110.0, 130.0],
                "buy_and_hold_equity": [1.0, 1.2, 1.1, 1.4],
                "fixed_dca_equity": [1.0, 1.1, 1.05, 1.25],
                "dynamic_dca_equity": [1.0, 1.15, 1.08, 1.30],
                "dynamic_dca_exposure": [0.9, 0.9, 0.8, 0.85],
                "dynamic_dca_buy_usd": [1.0, 1.5, 0.0, 1.0],
                "dynamic_dca_sell_usd": [0.0, 0.0, 0.25, 0.0],
                "dynamic_dca_trade_cost_usd": [0.001, 0.002, 0.001, 0.001],
                "fixed_dca_value": [100.0, 200.0, 300.0, 400.0],
                "dynamic_dca_value": [100.0, 210.0, 315.0, 420.0],
            },
            index=index,
        )

        result = evaluate_production_dynamic_dca(summary, curves)

        self.assertFalse(result.results.empty)
        dynamic = result.results[result.results["strategy"].astype(str) == "dynamic_dca"].iloc[0]
        self.assertEqual(dynamic["policy_family"], "production_dca_cashflow")
        self.assertAlmostEqual(float(dynamic["cagr_delta_vs_fixed_dca"]), 0.02)
        self.assertAlmostEqual(float(dynamic["cagr_delta_vs_buy_hold"]), -0.02)
        self.assertEqual(dynamic["signal"], "dca_risk")
        self.assertAlmostEqual(float(dynamic["terminal_wealth_delta_vs_fixed_dca"]), 20.0)
        self.assertIn("turnover_per_year", result.results.columns)
        self.assertFalse(result.curves.empty)
        self.assertFalse(result.trades.empty)

    def test_threshold_reachability_computes_known_crossings(self) -> None:
        index = pd.date_range("2021-01-31", periods=5, freq=pd.offsets.MonthEnd())
        regime = pd.DataFrame({"dca_risk": [0.10, 0.20, 0.80, 0.75, 0.25]}, index=index)

        result = compute_threshold_reachability(regime, buy_threshold=0.75, sell_threshold=0.75)

        buy = result[result["action"].astype(str) == "buy"].iloc[0]
        sell = result[result["action"].astype(str) == "sell"].iloc[0]
        self.assertEqual(int(buy["observations"]), 4)
        self.assertEqual(int(buy["crossing_count"]), 2)
        self.assertEqual(buy["signal_column"], "dca_risk")
        self.assertEqual(buy["comparison"], "<=")
        self.assertAlmostEqual(float(buy["pct_action_gate_reachable"]), 0.5)
        self.assertEqual(str(pd.Timestamp(buy["first_crossing_date"]).date()), "2021-02-28")
        self.assertEqual(int(sell["crossing_count"]), 2)
        self.assertAlmostEqual(float(sell["pct_action_gate_reachable"]), 0.5)

    def test_generic_dca_cashflow_reports_flow_neutral_returns(self) -> None:
        index = pd.date_range("2024-01-31", periods=24, freq=pd.offsets.MonthEnd())
        summary, curve, _ = _simulate_dca_cashflow(
            pd.Series(100.0, index=index),
            pd.Series(0.0, index=index),
            cost_bps=0.0,
            strategy="cash_only",
            signal="dca_risk",
        )

        self.assertAlmostEqual(float(summary["total_return"]), 0.0)
        self.assertAlmostEqual(float(summary["money_weighted_return"]), 0.0, places=8)
        self.assertAlmostEqual(float(curve["equity"].iloc[-1]), 1.0)

    def test_walkforward_tags_registered_and_exploratory_hypotheses(self) -> None:
        index = pd.date_range("2010-01-31", periods=180, freq=pd.offsets.MonthEnd())
        x = np.arange(len(index), dtype=float)
        series = pd.DataFrame(
            {
                "btc_price": 100.0 * np.exp(x / 120.0 + 0.35 * np.sin(x / 8.0)),
                "dca_risk": (0.5 + 0.4 * np.sin(x / 7.0)).clip(0.0, 1.0),
                "top_reversal_risk": (0.5 + 0.3 * np.cos(x / 9.0)).clip(0.0, 1.0),
            },
            index=index,
        )
        with tempfile.TemporaryDirectory() as tmp:
            cfg = build_evaluation_config(output_dir=Path(tmp), profile="standard", run_id="registry")
            result = evaluate_walkforward_benchmark(series, cfg)

        registered = result.by_label[result.by_label["evidence_tier"].astype(str) == "registered"]
        exploratory = result.by_label[result.by_label["evidence_tier"].astype(str) == "exploratory"]
        self.assertEqual(set(registered["signal"].astype(str)), {"dca_risk"})
        self.assertEqual(
            set(registered["hypothesis_id"].astype(str)),
            {item.hypothesis_id for item in cfg.registered_hypotheses},
        )
        self.assertFalse(exploratory["eligible_for_promotion"].fillna(False).any())
        self.assertTrue(
            result.by_label.loc[result.by_label["eligible_for_promotion"].fillna(False), "evidence_tier"]
            .astype(str)
            .eq("registered")
            .all()
        )

    def test_production_dynamic_dca_and_threshold_warnings_trigger(self) -> None:
        strategy_results = pd.DataFrame(
            {
                "policy_family": ["baseline", "dca_cashflow", "production_dca_cashflow"],
                "strategy": ["baseline_buy_hold", "risk_weighted_dca", "dynamic_dca"],
                "cagr_delta_vs_fixed_dca": [np.nan, 0.01, 0.0],
                "turnover_per_year": [0.0, 0.0, 0.0],
                "cost_drag_per_year": [0.0, 0.0, 0.0],
                "passes_turnover_guardrail": [True, True, True],
                "passes_cost_drag_guardrail": [True, True, True],
            }
        )
        practical = summarize_practical_strategies(strategy_results, pd.DataFrame({"x": [1.0]}), pd.DataFrame())
        self.assertEqual(practical.status, "fail")
        self.assertIn(
            "practical_no_production_dynamic_dca_beats_fixed_dca",
            {warning.code for warning in practical.warnings},
        )

        reachability = pd.DataFrame(
            {
                "threshold_name": ["cycle_dynamic_dca_buy_threshold"],
                "observations": [100],
                "pct_action_gate_reachable": [0.01],
            }
        )
        threshold = summarize_dca_threshold_reachability(reachability)
        self.assertEqual(threshold.status, "warn")
        warning = threshold.warnings[0]
        self.assertEqual(warning.code, "dca_threshold_rarely_reachable")
        self.assertFalse(warning.blocks_dashboard)

    def test_non_confirmatory_metrics_are_excluded_from_practical_metric_policy_signals(self) -> None:
        index = pd.date_range("2018-01-31", periods=48, freq=pd.offsets.MonthEnd())
        x = np.arange(len(index), dtype=float)
        series = pd.DataFrame(
            {
                "btc_price": 1000.0 + 25.0 * x,
                "top_reversal_risk": (0.5 + 0.25 * np.sin(x / 4.0)).clip(0.0, 1.0),
                "dca_top_reversal_component": (0.5 + 0.25 * np.cos(x / 4.0)).clip(0.0, 1.0),
            },
            index=index,
        )
        with tempfile.TemporaryDirectory() as tmp:
            cfg = build_evaluation_config(output_dir=Path(tmp), profile="smoke", run_id="practical-confirmatory")
            result = evaluate_practical_strategies(series, cfg)

        metric_rows = result.results[result.results["policy_family"].astype(str) == "metric_policy"]
        self.assertFalse(metric_rows.empty)
        self.assertIn("top_reversal_risk", set(metric_rows["signal"].astype(str)))
        self.assertNotIn("dca_top_reversal_component", set(metric_rows["signal"].astype(str)))

    def test_run_artifacts_cli_uses_existing_output_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp) / "artifacts"
            output_dir = Path(tmp) / "evaluation"
            artifact_dir.mkdir()
            output = self._risk_output()
            output.series.drop(columns=["dca_risk"]).to_csv(artifact_dir / "risk_scores_full.csv")
            output.benchmark_by_label.to_csv(artifact_dir / "benchmark_by_label.csv", index=False)
            output.benchmark_by_signal.to_csv(artifact_dir / "benchmark_by_signal.csv", index=False)
            output.source_health.to_csv(artifact_dir / "source_health.csv", index=False)
            output.cycle_regime_scores.to_csv(artifact_dir / "cycle_regime_scores_monthly.csv")
            output.financial_benchmark_summary.to_csv(artifact_dir / "financial_benchmark_summary.csv", index=False)
            output.financial_benchmark_curves.to_csv(artifact_dir / "financial_benchmark_curves_monthly.csv")
            pd.DataFrame({"source": ["btc_price"], "mode": ["local_csv"]}).to_csv(
                artifact_dir / "source_modes.csv",
                index=False,
            )

            exit_code = evaluation_cli_main(
                [
                    "run-artifacts",
                    "--profile",
                    "smoke",
                    "--artifact-dir",
                    str(artifact_dir),
                    "--output-dir",
                    str(output_dir),
                    "--run-id",
                    "artifact-cli",
                ]
            )

            self.assertIn(exit_code, {0, 2})
            manifest = json.loads((output_dir / "runs" / "artifact-cli" / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("data.source_quality", {item["test_id"] for item in manifest["tests"]})
            written_series = pd.read_csv(output_dir / "runs" / "artifact-cli" / "risk_series.csv")
            self.assertIn("dca_risk", set(written_series.columns))
            self.assertIn("dca_top_reversal_component", set(written_series.columns))
            strategy_results = pd.read_csv(output_dir / "runs" / "artifact-cli" / "tables" / "strategy_results.csv")
            self.assertIn("production_dca_cashflow", set(strategy_results["policy_family"].dropna().astype(str)))

    def test_artifact_loader_preserves_existing_dca_risk_when_backfilling_components(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            index = pd.date_range("2022-01-31", periods=3, freq=pd.offsets.MonthEnd())
            published = pd.Series([0.11, 0.42, 0.87], index=index, name="dca_risk")
            pd.DataFrame(
                {
                    "btc_price": [100.0, 110.0, 105.0],
                    "dca_risk": published,
                },
                index=index,
            ).to_csv(artifact_dir / "risk_scores_full.csv")

            loaded = _load_artifact_risk_output(artifact_dir)

        pd.testing.assert_series_equal(loaded.series["dca_risk"], published, check_names=False, check_freq=False)
        self.assertIn("dca_top_reversal_component", set(loaded.series.columns))
        self.assertTrue(loaded.series["dca_top_reversal_component"].isna().all())

    def test_source_availability_metadata_warns_on_unknown_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = build_evaluation_config(output_dir=Path(tmp), profile="smoke", run_id="source-audit")
            source_health = pd.DataFrame(
                {
                    "source": ["btc_price"],
                    "available": [True],
                    "latest_timestamp": [pd.Timestamp("2026-01-01")],
                    "staleness_days": [1.0],
                    "staleness_threshold_days": [3],
                }
            )
            result = check_source_availability_metadata(source_health, {"btc_price": "unknown"}, cfg)
            self.assertEqual(result.status, "warn")
            self.assertEqual(result.result_type, "diagnostic")
            self.assertIn("unknown_source_modes", {warning.code for warning in result.warnings})

    def test_benchmark_claim_gate_readiness_flags_underpowered_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = build_evaluation_config(output_dir=Path(tmp), profile="smoke", run_id="gate")
            benchmark = pd.DataFrame(
                {
                    "window": ["expanding", "expanding"],
                    "signal": ["top_reversal_risk", "top_reversal_risk"],
                    "label_id": ["threshold_top_dd30_h12", "threshold_top_dd40_h36"],
                    "family": ["threshold", "quantile"],
                    "horizon_months": [12, 36],
                    "n_obs": [60, 120],
                    "n_events": [2, 6],
                    "calibrated_threshold": [0.7, 0.8],
                }
            )
            by_signal = pd.DataFrame(
                {
                    "window": ["expanding"],
                    "signal": ["top_reversal_risk"],
                    "effective_weight_sum": [2.0],
                    "effective_label_count": [2],
                }
            )
            result = check_benchmark_claim_gate_readiness(benchmark, by_signal, cfg)
            warning_codes = {warning.code for warning in result.warnings}
            self.assertEqual(result.status, "warn")
            self.assertEqual(result.result_type, "diagnostic")
            self.assertIn("insufficient_claim_gate_samples", warning_codes)
            self.assertIn("retrospective_quantile_labels", warning_codes)
            self.assertIn("same_window_threshold_selection", warning_codes)
            self.assertIn("insufficient_signal_aggregate_support", warning_codes)
            self.assertEqual(result.metrics["passing_rows"], 0)

    def test_benchmark_claim_gate_readiness_passes_sufficient_threshold_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = build_evaluation_config(output_dir=Path(tmp), profile="smoke", run_id="gate-pass")
            benchmark = pd.DataFrame(
                {
                    "window": ["expanding"],
                    "signal": ["top_reversal_risk"],
                    "label_id": ["threshold_top_dd30_h12"],
                    "family": ["threshold"],
                    "horizon_months": [12],
                    "n_obs": [480],
                    "n_events": [10],
                    "eligible_for_aggregate": [True],
                }
            )
            by_signal = pd.DataFrame(
                {
                    "window": ["expanding"],
                    "signal": ["top_reversal_risk"],
                    "effective_weight_sum": [12.0],
                    "effective_label_count": [12],
                }
            )
            result = check_benchmark_claim_gate_readiness(benchmark, by_signal, cfg)
            self.assertEqual(result.status, "pass")
            self.assertEqual(result.metrics["passing_rows"], 1)
            self.assertEqual(result.metrics["aggregate_ready_rows"], 1)

    def test_walkforward_quantile_labels_ignore_unresolved_future_regime(self) -> None:
        index = pd.date_range("2015-01-31", periods=72, freq=pd.offsets.MonthEnd())
        returns = np.full(len(index), 0.01)
        returns[10:18] = -0.03
        returns[55:63] = 0.30
        price = pd.Series(1000.0 * np.cumprod(1.0 + returns), index=index)

        labels, cuts = _expanding_quantile_labels(
            price,
            horizon=6,
            quantile=0.20,
            side="bottom",
            min_history_months=24,
        )
        first_cut_date = cuts.dropna().index[0]
        train_end_pos = price.index.get_loc(first_cut_date) - 6
        train_returns = price.shift(-6).div(price).sub(1.0).iloc[:train_end_pos].dropna()
        full_sample_cut = price.shift(-6).div(price).sub(1.0).dropna().quantile(0.80)

        self.assertAlmostEqual(float(cuts.loc[first_cut_date]), float(train_returns.quantile(0.80)))
        self.assertLess(float(cuts.loc[first_cut_date]), float(full_sample_cut))
        self.assertFalse(labels.dropna().empty)

    def test_walkforward_quantile_embargo_boundary_is_exact(self) -> None:
        index = pd.date_range("2010-01-31", periods=72, freq=pd.offsets.MonthEnd())
        returns = np.full(len(index), 0.01)
        returns[24:30] = -0.40
        price = pd.Series(1000.0 * np.cumprod(1.0 + returns), index=index)

        labels, cuts = _expanding_quantile_labels(
            price,
            horizon=6,
            quantile=0.20,
            side="top",
            min_history_months=24,
        )

        first_cut_date = cuts.dropna().index[0]
        self.assertEqual(first_cut_date, pd.Timestamp("2012-07-31"))
        fwd = price.shift(-6).div(price).sub(1.0)
        expected_history = fwd.iloc[:24].dropna()
        leaky_history = fwd.iloc[:30].dropna()
        self.assertAlmostEqual(float(cuts.loc[first_cut_date]), float(expected_history.quantile(0.20)))
        self.assertNotAlmostEqual(float(cuts.loc[first_cut_date]), float(leaky_history.quantile(0.20)))

    def test_walkforward_quantile_empty_when_history_is_insufficient(self) -> None:
        index = pd.date_range("2010-01-31", periods=30, freq=pd.offsets.MonthEnd())
        price = pd.Series(np.linspace(100.0, 130.0, len(index)), index=index)
        labels, cuts = _expanding_quantile_labels(
            price,
            horizon=6,
            quantile=0.20,
            side="bottom",
            min_history_months=24,
        )
        self.assertTrue(labels.dropna().empty)
        self.assertTrue(cuts.dropna().empty)

    def test_walkforward_benchmark_uses_causal_methods_and_audit_columns(self) -> None:
        index = pd.date_range("2014-01-31", periods=96, freq=pd.offsets.MonthEnd())
        x = np.arange(len(index), dtype=float)
        price = pd.Series(1000.0 + 50.0 * x + 700.0 * np.sin(x / 5.0), index=index)
        signal = pd.Series((0.5 + 0.4 * np.sin(x / 6.0)).clip(0.0, 1.0), index=index)
        series = pd.DataFrame(
            {
                "btc_price": price,
                "top_reversal_risk": signal,
                "bottom_reversal_risk": 1.0 - signal,
                "dca_risk": (0.5 + 0.30 * np.sin(x / 7.0)).clip(0.0, 1.0),
            },
            index=index,
        )
        with tempfile.TemporaryDirectory() as tmp:
            cfg = build_evaluation_config(output_dir=Path(tmp), profile="smoke", run_id="wf")
            result = evaluate_walkforward_benchmark(series, cfg)

        self.assertFalse(result.by_label.empty)
        self.assertFalse(result.by_signal.empty)
        self.assertFalse(result.by_fold.empty)
        self.assertFalse(result.embargo_audit.empty)
        self.assertIn("walkforward_quantile", set(result.by_label["family"]))
        self.assertTrue((result.by_label["threshold_method"] == "expanding_score_quantile").all())
        self.assertTrue((result.by_label["label_method"].isin(["fixed_threshold", "expanding_embargoed_quantile"])).all())
        self.assertTrue((result.by_label["embargo_months"] == result.by_label["horizon_months"]).all())
        required_fold_columns = {
            "fold_id",
            "decision_date",
            "label_train_end",
            "score_train_end",
            "test_start",
            "selected_alert_threshold",
            "embargo_boundary_ok",
            "uses_full_sample_quantile",
            "uses_same_window_threshold_selection",
        }
        self.assertTrue(required_fold_columns.issubset(set(result.by_fold.columns)))
        self.assertTrue(result.by_fold["embargo_boundary_ok"].fillna(False).astype(bool).all())
        self.assertFalse(result.by_fold["uses_full_sample_quantile"].fillna(True).astype(bool).any())
        self.assertFalse(result.by_fold["uses_same_window_threshold_selection"].fillna(True).astype(bool).any())
        self.assertTrue(
            result.embargo_audit["label_training_uses_only_resolved_outcomes"].fillna(False).astype(bool).all()
        )

    def test_walkforward_robustness_is_seeded_and_bounded(self) -> None:
        index = pd.date_range("2014-01-31", periods=96, freq=pd.offsets.MonthEnd())
        x = np.arange(len(index), dtype=float)
        series = pd.DataFrame(
            {
                "btc_price": 1000.0 + 70.0 * x + 800.0 * np.sin(x / 5.0),
                "top_reversal_risk": (0.5 + 0.35 * np.sin(x / 6.0)).clip(0.0, 1.0),
                "bottom_reversal_risk": (0.5 - 0.35 * np.sin(x / 6.0)).clip(0.0, 1.0),
                "dca_risk": (0.5 + 0.30 * np.sin(x / 7.0)).clip(0.0, 1.0),
            },
            index=index,
        )
        with tempfile.TemporaryDirectory() as tmp:
            first_cfg = build_evaluation_config(output_dir=Path(tmp) / "a", profile="smoke", run_id="null-a", seed=1729)
            second_cfg = build_evaluation_config(output_dir=Path(tmp) / "b", profile="smoke", run_id="null-b", seed=1729)
            walkforward = evaluate_walkforward_benchmark(series, first_cfg)
            first = evaluate_walkforward_robustness(walkforward.by_fold, walkforward.by_label, first_cfg)
            second = evaluate_walkforward_robustness(walkforward.by_fold, walkforward.by_label, second_cfg)

        pd.testing.assert_frame_equal(first.nulls, second.nulls)
        pd.testing.assert_frame_equal(first.baselines, second.baselines)
        self.assertFalse(first.nulls.empty)
        self.assertFalse(first.baselines.empty)
        self.assertIn("circular_shift", set(first.nulls["null_method"]))
        self.assertIn("random_uniform_seeded", set(first.baselines["baseline_method"]))
        p_values = pd.to_numeric(first.by_label["auc_empirical_p_right"], errors="coerce").dropna()
        self.assertFalse(p_values.empty)
        self.assertTrue(((p_values >= 0.0) & (p_values <= 1.0)).all())
        q_values = pd.to_numeric(first.by_label["auc_fdr_q_value"], errors="coerce").dropna()
        self.assertTrue(q_values.empty or ((q_values >= 0.0) & (q_values <= 1.0)).all())
        registered = first.by_label["evidence_tier"].astype(str).eq("registered")
        self.assertTrue(first.by_label.loc[registered, "multiple_testing_corrected"].fillna(False).astype(bool).all())
        self.assertFalse(first.by_label.loc[~registered, "multiple_testing_corrected"].fillna(False).astype(bool).any())
        self.assertIn("event_year_count", set(first.by_label.columns))
        self.assertIn("max_event_year_share", set(first.by_label.columns))
        self.assertIn("passes_initial_robustness_gates", set(first.by_label.columns))

    def test_fdr_and_confirmatory_aggregation_exclude_non_confirmatory_rows(self) -> None:
        index = pd.date_range("2014-01-31", periods=96, freq=pd.offsets.MonthEnd())
        x = np.arange(len(index), dtype=float)
        series = pd.DataFrame(
            {
                "btc_price": 1000.0 + 70.0 * x + 800.0 * np.sin(x / 5.0),
                "top_reversal_risk": (0.5 + 0.35 * np.sin(x / 6.0)).clip(0.0, 1.0),
                "dca_risk": (0.5 + 0.30 * np.sin(x / 7.0)).clip(0.0, 1.0),
                "dca_top_reversal_component": (0.5 + 0.35 * np.cos(x / 6.0)).clip(0.0, 1.0),
            },
            index=index,
        )
        with tempfile.TemporaryDirectory() as tmp:
            cfg = build_evaluation_config(output_dir=Path(tmp), profile="smoke", run_id="confirmatory-fdr")
            walkforward = evaluate_walkforward_benchmark(series, cfg)
            robustness = evaluate_walkforward_robustness(walkforward.by_fold, walkforward.by_label, cfg)

        self.assertIn("confirmatory", set(robustness.by_label.columns))
        confirmatory_rows = robustness.by_label[robustness.by_label["confirmatory"].fillna(True).astype(bool)]
        diagnostic_rows = robustness.by_label[~robustness.by_label["confirmatory"].fillna(True).astype(bool)]
        self.assertFalse(confirmatory_rows.empty)
        self.assertFalse(diagnostic_rows.empty)
        self.assertTrue(confirmatory_rows["evidence_tier"].astype(str).eq("registered").all())
        self.assertTrue(pd.to_numeric(diagnostic_rows["auc_empirical_p_right"], errors="coerce").notna().any())
        self.assertTrue(pd.to_numeric(diagnostic_rows["auc_fdr_q_value"], errors="coerce").isna().all())
        self.assertFalse(diagnostic_rows["multiple_testing_corrected"].fillna(True).astype(bool).any())

        synthetic = pd.DataFrame(
            {
                "confirmatory": [True, False],
                "null_iterations": [31, 0],
                "survives_circular_shift_null": [True, False],
                "multiple_testing_corrected": [True, False],
                "auc_passes_fdr": [True, False],
                "passes_regime_concentration_gate": [True, False],
                "passes_initial_robustness_gates": [True, False],
                "auc": [0.8, 0.2],
                "random_auc": [0.5, 0.9],
                "p_value_caveat": ["caveat", "caveat"],
            }
        )
        summary = summarize_walkforward_robustness(pd.DataFrame({"x": [1]}), pd.DataFrame({"x": [1]}), synthetic)
        self.assertEqual(summary.metrics["fdr_not_survived_rows"], 0)
        self.assertEqual(summary.metrics["initial_robust_rows"], 1)
        self.assertNotIn("walkforward_no_initial_robust_rows", {warning.code for warning in summary.warnings})

    def test_academic_diagnostics_add_bins_and_monotonicity(self) -> None:
        index = pd.date_range("2014-01-31", periods=96, freq=pd.offsets.MonthEnd())
        x = np.arange(len(index), dtype=float)
        series = pd.DataFrame(
            {
                "btc_price": 1000.0 + 70.0 * x + 800.0 * np.sin(x / 5.0),
                "top_reversal_risk": (0.5 + 0.35 * np.sin(x / 6.0)).clip(0.0, 1.0),
                "bottom_reversal_risk": (0.5 - 0.35 * np.sin(x / 6.0)).clip(0.0, 1.0),
                "dca_risk": 0.5,
            },
            index=index,
        )
        with tempfile.TemporaryDirectory() as tmp:
            cfg = build_evaluation_config(output_dir=Path(tmp), profile="smoke", run_id="academic")
            walkforward = evaluate_walkforward_benchmark(series, cfg)
            robustness = evaluate_walkforward_robustness(walkforward.by_fold, walkforward.by_label, cfg)
            academic = evaluate_academic_diagnostics(walkforward.by_fold, robustness.by_label, cfg)

        self.assertFalse(academic.reliability_bins.empty)
        self.assertFalse(academic.monotonicity.empty)
        self.assertIn("event_rate", set(academic.reliability_bins.columns))
        self.assertIn("passes_monotonicity_gate", set(academic.monotonicity.columns))
        self.assertIn("spearman_score_label", set(academic.by_label.columns))

    def test_validity_diagnostics_add_label_and_leakage_probes(self) -> None:
        index = pd.date_range("2014-01-31", periods=96, freq=pd.offsets.MonthEnd())
        x = np.arange(len(index), dtype=float)
        series = pd.DataFrame(
            {
                "btc_price": 1000.0 + 70.0 * x + 800.0 * np.sin(x / 5.0),
                "top_reversal_risk": (0.5 + 0.35 * np.sin(x / 6.0)).clip(0.0, 1.0),
                "bottom_reversal_risk": (0.5 - 0.35 * np.sin(x / 6.0)).clip(0.0, 1.0),
                "dca_risk": 0.5,
            },
            index=index,
        )
        with tempfile.TemporaryDirectory() as tmp:
            cfg = build_evaluation_config(output_dir=Path(tmp), profile="smoke", run_id="validity")
            walkforward = evaluate_walkforward_benchmark(series, cfg)
            robustness = evaluate_walkforward_robustness(walkforward.by_fold, walkforward.by_label, cfg)
            academic = evaluate_academic_diagnostics(walkforward.by_fold, robustness.by_label, cfg)
            validity = evaluate_validity_diagnostics(walkforward.by_fold, academic.by_label, cfg)

        self.assertFalse(validity.label_audit.empty)
        self.assertFalse(validity.shift_probe.empty)
        self.assertFalse(validity.synthetic_sentinels.empty)
        self.assertIn("event_cluster_count", set(validity.label_audit.columns))
        self.assertIn("future_shift_auc_advantage", set(validity.by_label.columns))
        perfect = validity.synthetic_sentinels[
            validity.synthetic_sentinels["sentinel"].astype(str) == "perfect_label_sentinel"
        ]
        self.assertTrue((pd.to_numeric(perfect["auc"], errors="coerce").dropna() >= 0.99).all())

    def test_strength_mapping_adds_degraded_regime_and_rolling_flags(self) -> None:
        index = pd.date_range("2014-01-31", periods=96, freq=pd.offsets.MonthEnd())
        x = np.arange(len(index), dtype=float)
        series = pd.DataFrame(
            {
                "btc_price": 1000.0 + 80.0 * x + 700.0 * np.sin(x / 5.0),
                "top_reversal_risk": (0.5 + 0.35 * np.sin(x / 6.0)).clip(0.0, 1.0),
                "bottom_reversal_risk": (0.5 - 0.35 * np.sin(x / 6.0)).clip(0.0, 1.0),
                "dca_risk": 0.5,
            },
            index=index,
        )
        with tempfile.TemporaryDirectory() as tmp:
            cfg = build_evaluation_config(output_dir=Path(tmp), profile="smoke", run_id="strength")
            walkforward = evaluate_walkforward_benchmark(series, cfg)
            robustness = evaluate_walkforward_robustness(walkforward.by_fold, walkforward.by_label, cfg)
            academic = evaluate_academic_diagnostics(walkforward.by_fold, robustness.by_label, cfg)
            validity = evaluate_validity_diagnostics(walkforward.by_fold, academic.by_label, cfg)
            strength = evaluate_strength_mapping(series, walkforward.by_fold, validity.by_label, cfg)

        self.assertFalse(strength.degraded_data.empty)
        self.assertFalse(strength.regime_results.empty)
        self.assertFalse(strength.rolling_stability.empty)
        self.assertIn("missing_20pct_ffill", set(strength.degraded_data["scenario"].astype(str)))
        self.assertIn("regime_result_eligible", set(strength.regime_results.columns))
        self.assertIn("passes_degraded_data_gate", set(strength.by_label.columns))
        underpowered = strength.regime_results[~strength.regime_results["regime_result_eligible"].fillna(False).astype(bool)]
        if not underpowered.empty:
            self.assertTrue(pd.to_numeric(underpowered["auc"], errors="coerce").isna().all())
        self.assertIn("degraded_data_evaluable", set(strength.by_label.columns))

    def test_practical_strategies_include_baselines_and_cost_grid(self) -> None:
        index = pd.date_range("2014-01-31", periods=96, freq=pd.offsets.MonthEnd())
        x = np.arange(len(index), dtype=float)
        series = pd.DataFrame(
            {
                "btc_price": 1000.0 + 80.0 * x + 700.0 * np.sin(x / 5.0),
                "top_reversal_risk": (0.5 + 0.35 * np.sin(x / 6.0)).clip(0.0, 1.0),
                "bottom_reversal_risk": (0.5 - 0.35 * np.sin(x / 6.0)).clip(0.0, 1.0),
                "dca_risk": (0.45 + 0.30 * np.sin(x / 7.0)).clip(0.0, 1.0),
            },
            index=index,
        )
        with tempfile.TemporaryDirectory() as tmp:
            cfg = build_evaluation_config(output_dir=Path(tmp), profile="smoke", run_id="practical")
            practical = evaluate_practical_strategies(series, cfg)

        self.assertFalse(practical.results.empty)
        self.assertFalse(practical.curves.empty)
        self.assertIn("baseline_buy_hold", set(practical.results["strategy"].astype(str)))
        self.assertIn("baseline_fixed_monthly_dca", set(practical.results["strategy"].astype(str)))
        self.assertIn("risk_weighted_dca", set(practical.results["strategy"].astype(str)))
        self.assertIn("metric_hysteresis_bands", set(practical.results["strategy"].astype(str)))
        self.assertIn(25.0, set(pd.to_numeric(practical.results["cost_bps"], errors="coerce")))
        self.assertIn("passes_turnover_guardrail", set(practical.results.columns))
        self.assertIn("cost_drag_per_year", set(practical.results.columns))
        self.assertIn("cagr_per_avg_exposure", set(practical.results.columns))
        self.assertIn("cagr_delta_vs_fixed_dca", set(practical.results.columns))
        dca_curves = practical.curves[practical.curves["strategy"].astype(str).eq("risk_weighted_dca")]
        fixed_curves = practical.curves[practical.curves["strategy"].astype(str).eq("baseline_fixed_monthly_dca")]
        self.assertFalse(dca_curves.empty)
        self.assertAlmostEqual(float(dca_curves["contribution_usd"].dropna().nunique()), 1.0)
        self.assertEqual(
            float(dca_curves["total_contributed_usd"].dropna().iloc[-1]),
            float(fixed_curves["total_contributed_usd"].dropna().iloc[-1]),
        )
        buy_hold = practical.results[
            practical.results["strategy"].astype(str).eq("baseline_buy_hold")
            & (pd.to_numeric(practical.results["cost_bps"], errors="coerce") == 0.0)
        ]["total_return"].iloc[0]
        buy_hold_cost = practical.results[
            practical.results["strategy"].astype(str).eq("baseline_buy_hold")
            & (pd.to_numeric(practical.results["cost_bps"], errors="coerce") == 25.0)
        ]["total_return"].iloc[0]
        self.assertLess(float(buy_hold_cost), float(buy_hold))
        self.assertTrue(
            set(practical.results["execution_lag"].dropna().astype(str)).issubset(
                {
                    "target_from_month_close_applied_next_month",
                    "signal_month_close_buy_schedule_applied_next_month",
                }
            )
        )

    def test_web_summary_exports_blocked_claim_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            tables = run_dir / "tables"
            tables.mkdir()
            manifest = {
                "run_id": "phase3-test",
                "profile": "standard",
                "status": "fail",
                "generated_at": "2026-06-22T00:00:00Z",
                "config_hash": "abc",
                "git_commit": "def",
                "seed": 1729,
                "tests": [
                    {
                        "test_id": "robustness.walkforward_nulls",
                        "family": "uncertainty_nulls",
                        "status": "fail",
                        "severity": "high",
                        "claim_scope": "walkforward_benchmark_claims",
                        "summary": "No robust rows.",
                    }
                ],
            }
            (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (run_dir / "summary.json").write_text(json.dumps({"run_id": "phase3-test"}), encoding="utf-8")
            (run_dir / "warnings.jsonl").write_text(
                json.dumps(
                    {
                        "code": "walkforward_no_initial_robust_rows",
                        "severity": "high",
                        "test_id": "robustness.walkforward_nulls",
                        "message": "No walk-forward label rows pass initial gates.",
                        "blocks_dashboard": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            pd.DataFrame(
                {
                    "passes_initial_robustness_gates": [False, True],
                    "survives_circular_shift_null": [False, True],
                    "auc_passes_fdr": [False, False],
                    "pr_auc_passes_fdr": [False, True],
                    "passes_regime_concentration_gate": [True, True],
                    "auc": [0.4, 0.7],
                    "pr_auc": [0.2, 0.3],
                }
            ).to_csv(tables / "walkforward_by_label.csv", index=False)
            pd.DataFrame({"probe": ["future_score_one_month"], "auc_delta_vs_observed": [0.1]}).to_csv(
                tables / "shift_probe.csv",
                index=False,
            )
            pd.DataFrame({"passes_label_cluster_gate": [True, False]}).to_csv(tables / "label_audit.csv", index=False)
            pd.DataFrame({"passes_degraded_data_gate": [True]}).to_csv(tables / "degraded_data.csv", index=False)
            pd.DataFrame({"passes_rolling_stability_gate": [False]}).to_csv(tables / "rolling_stability.csv", index=False)
            pd.DataFrame({"auc": [0.6, None]}).to_csv(tables / "regime_results.csv", index=False)
            pd.DataFrame(
                {
                    "policy_family": ["metric_policy", "metric_policy", "baseline"],
                    "strategy": ["metric_allocation_bands", "risk_weighted_dca", "baseline_buy_hold"],
                    "cost_bps": [0, 0, 0],
                    "cagr": [0.2, 0.1, 0.3],
                    "max_drawdown": [-0.4, -0.2, -0.5],
                    "turnover_per_year": [1.0, 1.0, 0.0],
                    "cost_drag_per_year": [0.0, 0.0, 0.0],
                    "cagr_delta_vs_buy_hold": [-0.1, -0.2, None],
                    "cagr_delta_vs_fixed_dca": [None, -0.05, None],
                }
            ).to_csv(tables / "strategy_results.csv", index=False)

            payload = build_evaluation_web_summary(run_dir)

        self.assertEqual(payload["claim_state"]["status"], "blocked")
        self.assertEqual(payload["claim_state"]["blocking_warning_count"], 1)
        self.assertEqual(payload["robustness"]["initial_robust_rows"], 1)
        self.assertEqual(payload["validity"]["future_shift_material_advantage_label_rows"], 0)
        self.assertEqual(payload["validity"]["future_shift_material_advantage_probe_rows"], 1)
        self.assertEqual(payload["practical"]["metric_policy_beats_buy_hold_rows"], 0)
        self.assertEqual(payload["practical"]["risk_weighted_dca_beats_fixed_rows"], 0)


if __name__ == "__main__":
    unittest.main()
