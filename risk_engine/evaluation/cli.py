from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from risk_engine.config import load_runtime_config
from risk_engine.pipeline import run_pipeline
from risk_engine.pipeline import add_dca_risk_columns
from risk_engine.types import RiskOutput

from .config import build_evaluation_config
from .runner import run_evaluation
from .web_summary import write_evaluation_web_summary


def _read_optional_csv(path: Path, *, index_col: int | None = None, parse_dates: bool = False) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    kwargs = {}
    if index_col is not None:
        kwargs["index_col"] = index_col
    if parse_dates:
        kwargs["parse_dates"] = True
    return pd.read_csv(path, **kwargs)


def _read_source_modes(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    frame = pd.read_csv(path)
    if frame.shape[1] < 2:
        return {}
    first, second = frame.columns[:2]
    return dict(zip(frame[first].astype(str), frame[second].astype(str)))


def _load_artifact_risk_output(artifact_dir: Path) -> RiskOutput:
    series_path = artifact_dir / "risk_scores_full.csv"
    if not series_path.exists():
        raise FileNotFoundError(f"artifact risk series not found: {series_path}")
    series = pd.read_csv(series_path, index_col=0, parse_dates=True)
    dca_columns = {
        "dca_risk",
        "dca_top_reversal_component",
        "dca_bottom_reversal_component",
        "dca_cycle_extension_component",
        "dca_cycle_regime_component",
        "dca_component_coverage",
    }
    missing_dca_columns = dca_columns - set(series.columns)
    if missing_dca_columns:
        recomputed = add_dca_risk_columns(series.copy())
        for column in sorted(missing_dca_columns):
            if column in recomputed.columns:
                series[column] = recomputed[column]
    return RiskOutput(
        series=series,
        feature_frames={},
        source_health=_read_optional_csv(artifact_dir / "source_health.csv"),
        metric_health=_read_optional_csv(artifact_dir / "metric_health.csv"),
        source_modes=_read_source_modes(artifact_dir / "source_modes.csv"),
        benchmark_by_label=_read_optional_csv(artifact_dir / "benchmark_by_label.csv"),
        benchmark_by_signal=_read_optional_csv(artifact_dir / "benchmark_by_signal.csv"),
        benchmark_summary=_read_optional_csv(artifact_dir / "benchmark_summary.csv"),
        benchmark_window_stats=_read_optional_csv(artifact_dir / "benchmark_window_stats.csv"),
        cycle_regime_scores=_read_optional_csv(
            artifact_dir / "cycle_regime_scores_monthly.csv",
            index_col=0,
            parse_dates=True,
        ),
        financial_benchmark_summary=_read_optional_csv(artifact_dir / "financial_benchmark_summary.csv"),
        financial_benchmark_curves=_read_optional_csv(
            artifact_dir / "financial_benchmark_curves_monthly.csv",
            index_col=0,
            parse_dates=True,
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run metric evaluation harness.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_tests = subparsers.add_parser("list-tests", help="List evaluation tests currently implemented.")
    list_tests.set_defaults(command="list-tests")

    run = subparsers.add_parser("run", help="Run the evaluation harness.")
    run.add_argument("--profile", default="smoke", choices=["smoke", "standard", "expensive", "dashboard"])
    run.add_argument("--output-dir", default=None, help="Evaluation artifact root. Defaults to <runtime output>/evaluation.")
    run.add_argument("--run-id", default=None)
    run.add_argument("--seed", type=int, default=1729)

    artifacts = subparsers.add_parser("run-artifacts", help="Run evaluation from existing output artifacts.")
    artifacts.add_argument("--profile", default="smoke", choices=["smoke", "standard", "expensive", "dashboard"])
    artifacts.add_argument("--artifact-dir", default="output", help="Directory containing risk_scores_full.csv and benchmark artifacts.")
    artifacts.add_argument("--output-dir", default=None, help="Evaluation artifact root. Defaults to <artifact-dir>/evaluation.")
    artifacts.add_argument("--run-id", default=None)
    artifacts.add_argument("--seed", type=int, default=1729)
    artifacts.set_defaults(command="run-artifacts")

    web_summary = subparsers.add_parser("export-web-summary", help="Export a frontend evidence summary from an evaluation run.")
    web_summary.add_argument("--run-dir", required=True, help="Evaluation run directory containing manifest.json and tables/.")
    web_summary.add_argument(
        "--target",
        default="data/web/v2/evaluation_summary.json",
        help="JSON target path for the frontend contract.",
    )
    web_summary.set_defaults(command="export-web-summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list-tests":
        for test_id in [
            "data.series_integrity",
            "data.source_quality",
            "data.availability_calendar",
            "temporal.live_availability",
            "temporal.source_availability_metadata",
            "academic.existing_benchmark_snapshot",
            "validator.benchmark_claim_gate_readiness",
            "walkforward.expanding_benchmark",
            "robustness.walkforward_nulls",
            "academic.calibration_monotonicity",
            "validity.label_leakage_sentinels",
            "robustness.strength_mapping",
            "practical.monthly_strategy_suite",
            "practical.dca_threshold_reachability",
            "practical.dca_evidence",
            "validator.claim_gates",
        ]:
            print(test_id)
        return 0

    if args.command == "export-web-summary":
        payload = write_evaluation_web_summary(Path(args.run_dir), Path(args.target))
        source_run = payload.get("source_run", {})
        claim_state = payload.get("claim_state", {})
        print(f"Exported evaluation summary: {args.target}")
        print(f"Run: {source_run.get('run_id')}")
        print(f"Claim state: {claim_state.get('status')}")
        return 0

    if args.command == "run-artifacts":
        artifact_dir = Path(args.artifact_dir).resolve()
        result = _load_artifact_risk_output(artifact_dir)
        output_dir = Path(args.output_dir).resolve() if args.output_dir else artifact_dir / "evaluation"
        dca_buy_threshold = 0.75
        dca_sell_threshold = 0.75
        dca_policy_kwargs = {}
    else:
        runtime_cfg = load_runtime_config()
        result = run_pipeline(runtime_cfg)
        output_dir = Path(args.output_dir).resolve() if args.output_dir else runtime_cfg.output_dir / "evaluation"
        dca_buy_threshold = float(runtime_cfg.cycle_dynamic_dca_buy_threshold)
        dca_sell_threshold = float(runtime_cfg.cycle_dynamic_dca_sell_threshold)
        dca_policy_kwargs = {
            "cycle_dynamic_dca_base_contribution": runtime_cfg.cycle_dynamic_dca_base_contribution,
            "cycle_dynamic_dca_max_buy_multiplier": runtime_cfg.cycle_dynamic_dca_max_buy_multiplier,
            "cycle_dynamic_dca_max_sell_fraction": runtime_cfg.cycle_dynamic_dca_max_sell_fraction,
            "cycle_dynamic_dca_cash_buffer_ratio": runtime_cfg.cycle_dynamic_dca_cash_buffer_ratio,
            "cycle_dynamic_dca_fee_rate": runtime_cfg.cycle_dynamic_dca_fee_rate,
            "cycle_dynamic_dca_slippage_rate": runtime_cfg.cycle_dynamic_dca_slippage_rate,
        }
    eval_cfg = build_evaluation_config(
        output_dir=output_dir,
        profile=args.profile,
        run_id=args.run_id,
        seed=args.seed,
        cycle_dynamic_dca_buy_threshold=dca_buy_threshold,
        cycle_dynamic_dca_sell_threshold=dca_sell_threshold,
        **dca_policy_kwargs,
    )
    evaluation = run_evaluation(result, eval_cfg)
    print(f"Evaluation run: {evaluation.manifest.run_id}")
    print(f"Status: {evaluation.manifest.status}")
    print(f"Run directory: {evaluation.run_dir}")
    print(f"SQLite index: {evaluation.db_path}")
    if evaluation.manifest.warnings:
        print("Warnings:")
        for warning in evaluation.manifest.warnings:
            test_label = f" [{warning.test_id}]" if warning.test_id else ""
            print(f" - {warning.severity}:{warning.code}{test_label} {warning.message}")
    return 0 if evaluation.manifest.status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
