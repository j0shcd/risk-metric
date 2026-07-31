from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd

from risk_engine.types import RiskOutput

from .checks import (
    build_availability_calendar,
    check_availability_calendar,
    check_benchmark_claim_gate_readiness,
    check_live_availability,
    check_series_integrity,
    check_source_quality,
    check_source_availability_metadata,
    summarize_dca_threshold_reachability,
    summarize_existing_benchmark,
    summarize_academic_diagnostics,
    summarize_practical_strategies,
    summarize_strength_mapping,
    summarize_validity_diagnostics,
    summarize_walkforward_benchmark,
    summarize_walkforward_robustness,
    validate_claim_gates,
)
from .config import EvaluationConfig, config_hash, config_to_dict
from .data import dataframe_fingerprint, file_fingerprint
from .schemas import DataFingerprint, EvaluationManifest, EvaluationTestResult, EvaluationWarning, utc_now_iso
from .storage import EvaluationStore
from .academic import evaluate_academic_diagnostics
from .practical import (
    PracticalStrategyResult,
    compute_threshold_reachability,
    evaluate_practical_strategies,
    evaluate_production_dynamic_dca,
)
from .robustness import evaluate_walkforward_robustness
from .strength import evaluate_strength_mapping
from .validity import evaluate_validity_diagnostics
from .walkforward import evaluate_walkforward_benchmark


@dataclass(frozen=True)
class EvaluationRunResult:
    manifest: EvaluationManifest
    run_dir: Path
    db_path: Path


def _git_commit(project_root: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    return value or None


def _resolve_project_root(config: EvaluationConfig) -> Path:
    candidates = [Path.cwd(), config.output_dir, Path(config.plan_path)]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            resolved = resolved.parent
        for parent in [resolved, *resolved.parents]:
            if (parent / ".git").exists():
                return parent
    return Path.cwd()


def _collect_fingerprints(result: RiskOutput, config: EvaluationConfig) -> List[DataFingerprint]:
    fingerprints = [dataframe_fingerprint("risk_series", result.series)]
    if not result.benchmark_by_label.empty:
        fingerprints.append(dataframe_fingerprint("benchmark_by_label", result.benchmark_by_label))
    if not result.benchmark_by_signal.empty:
        fingerprints.append(dataframe_fingerprint("benchmark_by_signal", result.benchmark_by_signal))

    plan_path = Path(config.plan_path)
    if plan_path.exists():
        fingerprints.append(file_fingerprint(plan_path, name="metric_evaluation_plan"))
    return fingerprints


def _validation_report_markdown(manifest: EvaluationManifest) -> str:
    lines = [
        f"# Metric Evaluation Run {manifest.run_id}",
        "",
        f"- Profile: `{manifest.profile}`",
        f"- Status: `{manifest.status}`",
        f"- Config hash: `{manifest.config_hash}`",
        f"- Seed: `{manifest.seed}`",
        "",
        "## Tests",
        "",
    ]
    for result in manifest.tests:
        lines.append(f"- `{result.test_id}`: **{result.status}** - {result.summary}")
    lines.extend(["", "## Warnings", ""])
    if manifest.warnings:
        for warning in manifest.warnings:
            test_label = f" `{warning.test_id}`" if warning.test_id else ""
            lines.append(f"- `{warning.severity}:{warning.code}`{test_label} {warning.message}")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def run_evaluation(result: RiskOutput, config: EvaluationConfig) -> EvaluationRunResult:
    store = EvaluationStore(config.output_dir)
    store.initialize()

    artifacts: List[str] = []
    run_dir = store.run_dir(config.run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts.append(store.write_json(config.run_id, "resolved_config.json", config_to_dict(config)))
    artifacts.append(store.write_json(config.run_id, "config.resolved.json", config_to_dict(config)))
    artifacts.append(store.write_frame(config.run_id, "risk_series.csv", result.series))
    if not result.benchmark_by_label.empty:
        artifacts.append(store.write_frame(config.run_id, "benchmark_by_label.csv", result.benchmark_by_label))
    if not result.benchmark_by_signal.empty:
        artifacts.append(store.write_frame(config.run_id, "benchmark_by_signal.csv", result.benchmark_by_signal))

    availability_calendar = build_availability_calendar(result, config)
    availability_artifact = store.write_frame(config.run_id, "tables/availability_calendar.csv", availability_calendar)
    walkforward = evaluate_walkforward_benchmark(result.series, config)
    robustness = evaluate_walkforward_robustness(walkforward.by_fold, walkforward.by_label, config)
    academic = evaluate_academic_diagnostics(walkforward.by_fold, robustness.by_label, config)
    validity = evaluate_validity_diagnostics(walkforward.by_fold, academic.by_label, config)
    strength = evaluate_strength_mapping(result.series, walkforward.by_fold, validity.by_label, config)
    practical = evaluate_practical_strategies(result.series, config)
    production_practical = evaluate_production_dynamic_dca(
        result.financial_benchmark_summary,
        result.financial_benchmark_curves,
    )
    if not production_practical.results.empty:
        practical = PracticalStrategyResult(
            results=pd.concat([practical.results, production_practical.results], ignore_index=True, sort=False)
            if not practical.results.empty
            else production_practical.results,
            curves=pd.concat([practical.curves, production_practical.curves], ignore_index=True, sort=False)
            if not practical.curves.empty
            else production_practical.curves,
            trades=pd.concat([practical.trades, production_practical.trades], ignore_index=True, sort=False)
            if not practical.trades.empty
            else production_practical.trades,
            config={**practical.config, "production_dynamic_dca": production_practical.config},
            warnings=[*practical.warnings, *production_practical.warnings],
        )
    else:
        practical = PracticalStrategyResult(
            results=practical.results,
            curves=practical.curves,
            trades=practical.trades,
            config={**practical.config, "production_dynamic_dca": production_practical.config},
            warnings=[*practical.warnings, *production_practical.warnings],
        )
    if not practical.results.empty:
        # Recompute guardrails over the merged frame; production rows without
        # turnover/cost data pass rather than fail a gate they have no data for.
        turnover = practical.results.get("turnover_per_year", pd.Series(0.0, index=practical.results.index))
        cost_drag = practical.results.get("cost_drag_per_year", pd.Series(0.0, index=practical.results.index))
        practical.results["passes_turnover_guardrail"] = pd.to_numeric(
            turnover,
            errors="coerce",
        ).fillna(0.0) <= float(config.claim_gates.max_turnover_per_year)
        practical.results["passes_cost_drag_guardrail"] = pd.to_numeric(
            cost_drag,
            errors="coerce",
        ).fillna(0.0) <= float(config.claim_gates.max_cost_drag)
    threshold_reachability = compute_threshold_reachability(
        result.series[["dca_risk"]] if "dca_risk" in result.series.columns else pd.DataFrame(),
        buy_threshold=config.cycle_dynamic_dca_buy_threshold,
        sell_threshold=config.cycle_dynamic_dca_sell_threshold,
    )
    walkforward_by_fold_artifact = store.write_frame(
        config.run_id,
        "tables/walkforward_by_fold.csv",
        walkforward.by_fold,
    )
    walkforward_by_label_artifact = store.write_frame(
        config.run_id,
        "tables/walkforward_by_label.csv",
        strength.by_label,
    )
    walkforward_by_signal_artifact = store.write_frame(
        config.run_id,
        "tables/walkforward_by_signal.csv",
        walkforward.by_signal,
    )
    walkforward_embargo_audit_artifact = store.write_frame(
        config.run_id,
        "tables/walkforward_embargo_audit.csv",
        walkforward.embargo_audit,
    )
    walkforward_nulls_artifact = store.write_frame(
        config.run_id,
        "tables/walkforward_nulls.csv",
        robustness.nulls,
    )
    walkforward_baselines_artifact = store.write_frame(
        config.run_id,
        "tables/walkforward_baselines.csv",
        robustness.baselines,
    )
    reliability_bins_artifact = store.write_frame(
        config.run_id,
        "tables/reliability_bins.csv",
        academic.reliability_bins,
    )
    monotonicity_artifact = store.write_frame(
        config.run_id,
        "tables/monotonicity.csv",
        academic.monotonicity,
    )
    label_audit_artifact = store.write_frame(
        config.run_id,
        "tables/label_audit.csv",
        validity.label_audit,
    )
    shift_probe_artifact = store.write_frame(
        config.run_id,
        "tables/shift_probe.csv",
        validity.shift_probe,
    )
    synthetic_sentinels_artifact = store.write_frame(
        config.run_id,
        "tables/synthetic_sentinels.csv",
        validity.synthetic_sentinels,
    )
    strategy_results_artifact = store.write_frame(
        config.run_id,
        "tables/strategy_results.csv",
        practical.results,
    )
    strategy_curves_artifact = store.write_frame(
        config.run_id,
        "tables/strategy_equity_curves.csv",
        practical.curves,
    )
    strategy_trades_artifact = store.write_frame(
        config.run_id,
        "tables/strategy_trades.csv",
        practical.trades,
    )
    threshold_reachability_artifact = store.write_frame(
        config.run_id,
        "tables/threshold_reachability.csv",
        threshold_reachability,
    )
    degraded_data_artifact = store.write_frame(
        config.run_id,
        "tables/degraded_data.csv",
        strength.degraded_data,
    )
    regime_results_artifact = store.write_frame(
        config.run_id,
        "tables/regime_results.csv",
        strength.regime_results,
    )
    rolling_stability_artifact = store.write_frame(
        config.run_id,
        "tables/rolling_stability.csv",
        strength.rolling_stability,
    )

    tests: List[EvaluationTestResult] = [
        check_series_integrity(result.series, config),
        check_source_quality(result.series, result.source_health, config),
        check_live_availability(result.series, config),
        check_availability_calendar(availability_calendar, config),
        check_source_availability_metadata(result.source_health, result.source_modes, config),
        summarize_existing_benchmark(result.benchmark_by_label, result.benchmark_by_signal),
        check_benchmark_claim_gate_readiness(result.benchmark_by_label, result.benchmark_by_signal, config),
        summarize_walkforward_benchmark(
            walkforward.by_fold,
            strength.by_label,
            walkforward.by_signal,
            walkforward.embargo_audit,
        ),
        summarize_walkforward_robustness(robustness.nulls, robustness.baselines, strength.by_label),
        summarize_academic_diagnostics(academic.reliability_bins, academic.monotonicity, strength.by_label),
        summarize_validity_diagnostics(
            validity.label_audit,
            validity.shift_probe,
            validity.synthetic_sentinels,
            strength.by_label,
        ),
        summarize_strength_mapping(
            strength.degraded_data,
            strength.regime_results,
            strength.rolling_stability,
            strength.by_label,
        ),
        summarize_practical_strategies(practical.results, practical.curves, practical.trades),
        summarize_dca_threshold_reachability(threshold_reachability),
    ]
    tests_by_id = {test.test_id: test for test in tests}
    tests_by_id["data.availability_calendar"].artifacts.append(availability_artifact)
    tests_by_id["walkforward.expanding_benchmark"].artifacts.extend(
        [
            walkforward_by_fold_artifact,
            walkforward_by_label_artifact,
            walkforward_by_signal_artifact,
            walkforward_embargo_audit_artifact,
        ]
    )
    tests_by_id["robustness.walkforward_nulls"].artifacts.extend(
        [walkforward_nulls_artifact, walkforward_baselines_artifact]
    )
    tests_by_id["academic.calibration_monotonicity"].artifacts.extend(
        [reliability_bins_artifact, monotonicity_artifact]
    )
    tests_by_id["validity.label_leakage_sentinels"].artifacts.extend(
        [label_audit_artifact, shift_probe_artifact, synthetic_sentinels_artifact]
    )
    tests_by_id["robustness.strength_mapping"].artifacts.extend(
        [degraded_data_artifact, regime_results_artifact, rolling_stability_artifact]
    )
    tests_by_id["practical.monthly_strategy_suite"].artifacts.extend(
        [strategy_results_artifact, strategy_curves_artifact, strategy_trades_artifact]
    )
    tests_by_id["practical.dca_threshold_reachability"].artifacts.append(threshold_reachability_artifact)
    artifacts.extend(
        [
            availability_artifact,
            walkforward_by_fold_artifact,
            walkforward_by_label_artifact,
            walkforward_by_signal_artifact,
            walkforward_embargo_audit_artifact,
            walkforward_nulls_artifact,
            walkforward_baselines_artifact,
            reliability_bins_artifact,
            monotonicity_artifact,
            label_audit_artifact,
            shift_probe_artifact,
            synthetic_sentinels_artifact,
            strategy_results_artifact,
            strategy_curves_artifact,
            strategy_trades_artifact,
            threshold_reachability_artifact,
            degraded_data_artifact,
            regime_results_artifact,
            rolling_stability_artifact,
        ]
    )
    validator_warnings = validate_claim_gates(tests)
    test_warnings = [warning for test in tests for warning in test.warnings]
    all_warnings = [*test_warnings, *validator_warnings]
    status = "fail" if any(w.blocks_dashboard for w in all_warnings) else "pass"

    fingerprints = _collect_fingerprints(result, config)
    summary_payload = {
        "run_id": config.run_id,
        "profile": config.profile,
        "status": status,
        "test_count": len(tests),
        "warning_count": len(all_warnings),
    }
    artifacts.append(store.write_json(config.run_id, "summary.json", summary_payload))
    artifacts.append(store.write_json(config.run_id, "data_fingerprint.json", fingerprints))
    artifacts.append(store.write_jsonl(config.run_id, "results.jsonl", tests))
    artifacts.append(store.write_jsonl(config.run_id, "warnings.jsonl", all_warnings))

    manifest = EvaluationManifest(
        run_id=config.run_id,
        profile=config.profile,
        generated_at=utc_now_iso(),
        plan_path=config.plan_path,
        config_hash=config_hash(config),
        seed=config.seed,
        status=status,
        git_commit=_git_commit(_resolve_project_root(config)),
        data_fingerprints=fingerprints,
        tests=tests,
        warnings=all_warnings,
        artifacts=artifacts,
    )
    report_artifact = store.write_text(config.run_id, "validation_report.md", _validation_report_markdown(manifest))
    manifest_artifact = str((store.run_dir(config.run_id) / "manifest.json").relative_to(store.root))
    manifest = EvaluationManifest(
        run_id=manifest.run_id,
        profile=manifest.profile,
        generated_at=manifest.generated_at,
        plan_path=manifest.plan_path,
        config_hash=manifest.config_hash,
        seed=manifest.seed,
        status=manifest.status,
        git_commit=manifest.git_commit,
        data_fingerprints=manifest.data_fingerprints,
        tests=manifest.tests,
        warnings=manifest.warnings,
        artifacts=[*manifest.artifacts, report_artifact, manifest_artifact],
    )
    store.write_json(config.run_id, "manifest.json", manifest)
    store.record_manifest(manifest)
    return EvaluationRunResult(manifest=manifest, run_dir=run_dir, db_path=store.db_path)
