from __future__ import annotations

from typing import Dict, Iterable, List

import numpy as np
import pandas as pd

from risk_engine.types import RiskOutput

from .config import EvaluationConfig
from .data import assert_monotonic_datetime_index
from .schemas import AvailabilityRule, EvaluationTestResult, EvaluationWarning

DCA_THRESHOLD_REACHABILITY_MIN_PCT = 0.02


def _warning(
    *,
    code: str,
    severity: str,
    message: str,
    test_id: str,
    blocks_dashboard: bool = False,
) -> EvaluationWarning:
    return EvaluationWarning(
        code=code,
        severity=severity,
        message=message,
        test_id=test_id,
        blocks_dashboard=blocks_dashboard,
    )


def _confirmatory_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "confirmatory" not in frame.columns:
        return frame
    confirmatory = frame["confirmatory"]
    if confirmatory.dtype == object:
        mask = confirmatory.map(
            lambda value: str(value).strip().lower() not in {"false", "0", "no"}
            if pd.notna(value)
            else True
        )
    else:
        mask = confirmatory.fillna(True).astype(bool)
    return frame[mask].copy()


def check_series_integrity(series: pd.DataFrame, config: EvaluationConfig) -> EvaluationTestResult:
    test_id = "data.series_integrity"
    warnings: List[EvaluationWarning] = []
    for issue in assert_monotonic_datetime_index(series):
        warnings.append(
            _warning(
                code=issue,
                severity="high",
                message=f"Risk series failed index check: {issue}",
                test_id=test_id,
                blocks_dashboard=True,
            )
        )

    missing_required = [column for column in config.required_columns if column not in series.columns]
    for column in missing_required:
        warnings.append(
            _warning(
                code="missing_required_column",
                severity="high",
                message=f"Required evaluation column is missing: {column}",
                test_id=test_id,
                blocks_dashboard=True,
            )
        )

    present_required = [column for column in config.required_columns if column in series.columns]
    coverage = {
        column: float(pd.to_numeric(series[column], errors="coerce").notna().mean())
        for column in present_required
    }
    for column, value in coverage.items():
        if value < 0.50:
            warnings.append(
                _warning(
                    code="low_required_column_coverage",
                    severity="medium",
                    message=f"Required column {column} has only {value:.1%} non-null coverage.",
                    test_id=test_id,
                )
            )

    status = "pass" if not any(w.blocks_dashboard for w in warnings) else "fail"
    return EvaluationTestResult(
        test_id=test_id,
        family="data_integrity",
        status=status,
        severity="high" if status == "fail" else "info",
        summary=f"Checked {len(series)} rows and {len(series.columns)} columns for temporal/index and required-column integrity.",
        result_type="diagnostic",
        claim_scope="structural",
        metrics={
            "rows": int(series.shape[0]),
            "columns": int(series.shape[1]),
            "required_columns_present": len(present_required),
            "required_columns_missing": len(missing_required),
            "required_column_coverage": coverage,
        },
        warnings=warnings,
    )


def check_source_quality(series: pd.DataFrame, source_health: pd.DataFrame, config: EvaluationConfig) -> EvaluationTestResult:
    test_id = "data.source_quality"
    warnings: List[EvaluationWarning] = []
    numeric = series.select_dtypes(include=[np.number]).copy()
    inspected_columns = [column for column in config.required_columns if column in numeric.columns]
    flatline_columns: List[str] = []
    jump_columns: List[str] = []
    out_of_bounds_columns: List[str] = []

    for column in inspected_columns:
        values = pd.to_numeric(numeric[column], errors="coerce").dropna()
        if values.shape[0] < 12:
            continue
        if values.tail(min(30, values.shape[0])).nunique(dropna=True) <= 1:
            flatline_columns.append(column)
        if column != "btc_price":
            out_of_bounds = int(((values < -1e-9) | (values > 1.0 + 1e-9)).sum())
            if out_of_bounds:
                out_of_bounds_columns.append(column)
        returns = values.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).dropna()
        if column == "btc_price" and not returns.empty and float(returns.abs().max()) > 0.50:
            jump_columns.append(column)

    for column in flatline_columns:
        warnings.append(
            _warning(
                code="source_flatline_recent_window",
                severity="medium",
                message=f"{column} is flat over the recent inspection window; source staleness or carry-forward should be reviewed.",
                test_id=test_id,
            )
        )
    for column in jump_columns:
        warnings.append(
            _warning(
                code="source_large_discontinuity",
                severity="medium",
                message=f"{column} has a large single-period discontinuity; source split/schema drift should be reviewed.",
                test_id=test_id,
            )
        )
    for column in out_of_bounds_columns:
        warnings.append(
            _warning(
                code="metric_out_of_bounds",
                severity="high",
                message=f"{column} contains values outside expected [0, 1] metric bounds.",
                test_id=test_id,
                blocks_dashboard=True,
            )
        )

    unavailable_sources = 0
    if not source_health.empty and "available" in source_health.columns:
        unavailable_sources = int((~source_health["available"].fillna(False).astype(bool)).sum())

    status = "fail" if any(w.blocks_dashboard for w in warnings) else ("warn" if warnings else "pass")
    return EvaluationTestResult(
        test_id=test_id,
        family="data_integrity",
        status=status,
        severity="high" if status == "fail" else ("medium" if status == "warn" else "info"),
        summary="Audited required series columns for bounds, recent flatlines, discontinuities, and source-health availability.",
        result_type="diagnostic",
        claim_scope="structural",
        metrics={
            "inspected_columns": inspected_columns,
            "flatline_columns": flatline_columns,
            "jump_columns": jump_columns,
            "out_of_bounds_columns": out_of_bounds_columns,
            "source_health_rows": int(source_health.shape[0]),
            "unavailable_sources": unavailable_sources,
        },
        warnings=warnings,
    )


def check_live_availability(series: pd.DataFrame, config: EvaluationConfig) -> EvaluationTestResult:
    test_id = "temporal.live_availability"
    warnings: List[EvaluationWarning] = []
    has_available_at = "available_at_date" in series.columns
    if not has_available_at:
        warnings.append(
            _warning(
                code="unknown_availability",
                severity="high",
                message=(
                    "No available_at_date column is present; live-style claims must be downgraded "
                    "until source latency is explicit."
                ),
                test_id=test_id,
                blocks_dashboard=True,
            )
        )

    future_available_rows = 0
    if has_available_at and isinstance(series.index, pd.DatetimeIndex):
        available_at = pd.to_datetime(series["available_at_date"], errors="coerce")
        observation = pd.Series(series.index, index=series.index)
        future_available_rows = int((available_at > observation).sum())

    status = "pass"
    severity = "info"
    if future_available_rows:
        status = "fail"
        severity = "high"
        warnings.append(
            _warning(
                code="available_after_observation",
                severity="high",
                message="Some rows have available_at_date after observation date; live simulations must lag these values.",
                test_id=test_id,
                blocks_dashboard=True,
            )
        )
    elif any(w.blocks_dashboard for w in warnings):
        status = "fail"
        severity = "high"
    elif warnings:
        status = "warn"
        severity = "medium"

    return EvaluationTestResult(
        test_id=test_id,
        family="temporal_validity",
        status=status,
        severity=severity,
        summary="Checked whether risk series exposes live availability metadata.",
        result_type="diagnostic",
        claim_scope="live_style_claims",
        metrics={
            "has_available_at_date": has_available_at,
            "future_available_rows": future_available_rows,
            "configured_source_latency_rules": len(config.source_latency_days),
        },
        warnings=warnings,
    )


def check_source_availability_metadata(
    source_health: pd.DataFrame,
    source_modes: Dict[str, str],
    config: EvaluationConfig,
) -> EvaluationTestResult:
    test_id = "temporal.source_availability_metadata"
    warnings: List[EvaluationWarning] = []
    required_columns = {"source", "available", "latest_timestamp", "staleness_days", "staleness_threshold_days"}

    if source_health.empty:
        warnings.append(
            _warning(
                code="source_health_missing",
                severity="medium",
                message="Source health is empty; availability assumptions cannot be audited.",
                test_id=test_id,
            )
        )
        present_sources: List[str] = []
    else:
        present_sources = source_health.get("source", pd.Series(dtype=str)).dropna().astype(str).tolist()
        missing_columns = sorted(required_columns - set(source_health.columns))
        for column in missing_columns:
            warnings.append(
                _warning(
                    code="source_health_column_missing",
                    severity="medium",
                    message=f"Source health is missing column required for availability audit: {column}",
                    test_id=test_id,
                )
            )

    unknown_modes = sorted(name for name, mode in source_modes.items() if str(mode).strip().lower() in {"", "unknown"})
    if unknown_modes:
        warnings.append(
            _warning(
                code="unknown_source_modes",
                severity="medium",
                message=f"{len(unknown_modes)} source mode(s) are unknown; live-style claims should be downgraded.",
                test_id=test_id,
            )
        )

    unavailable_sources = 0
    stale_sources = 0
    if not source_health.empty and {"available", "staleness_days", "staleness_threshold_days"}.issubset(source_health.columns):
        available = source_health["available"].fillna(False).astype(bool)
        unavailable_sources = int((~available).sum())
        staleness = pd.to_numeric(source_health["staleness_days"], errors="coerce")
        threshold = pd.to_numeric(source_health["staleness_threshold_days"], errors="coerce")
        stale_sources = int((available & staleness.notna() & threshold.notna() & (staleness > threshold)).sum())

    if unavailable_sources:
        warnings.append(
            _warning(
                code="unavailable_sources",
                severity="medium",
                message=f"{unavailable_sources} source(s) are unavailable in source health.",
                test_id=test_id,
            )
        )
    if stale_sources:
        warnings.append(
            _warning(
                code="stale_sources",
                severity="medium",
                message=f"{stale_sources} source(s) are stale relative to their thresholds.",
                test_id=test_id,
            )
        )

    latency_rules = dict(config.source_latency_days)
    status = "pass" if not warnings else "warn"
    return EvaluationTestResult(
        test_id=test_id,
        family="temporal_validity",
        status=status,
        severity="info" if status == "pass" else "medium",
        summary="Audited source-health metadata and configured latency assumptions for live-style evaluation readiness.",
        result_type="diagnostic",
        claim_scope="live_style_claims",
        metrics={
            "source_health_rows": int(source_health.shape[0]),
            "present_sources": present_sources,
            "source_modes_count": len(source_modes),
            "unknown_source_modes": unknown_modes,
            "unavailable_sources": unavailable_sources,
            "stale_sources": stale_sources,
            "configured_latency_rules": latency_rules,
        },
        warnings=warnings,
    )


def _rule_matches(rule: AvailabilityRule, name: str, entity_type: str) -> bool:
    if rule.entity_type != entity_type:
        return False
    if rule.name.endswith("::*"):
        return name.startswith(rule.name[:-1])
    return rule.name == name


def _find_availability_rule(config: EvaluationConfig, name: str, entity_type: str) -> AvailabilityRule | None:
    for rule in config.availability_rules:
        if _rule_matches(rule, name, entity_type):
            return rule
    return None


def build_availability_calendar(result: RiskOutput, config: EvaluationConfig) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []

    if not result.source_health.empty and "source" in result.source_health.columns:
        for _, row in result.source_health.iterrows():
            name = str(row.get("source", ""))
            rule = _find_availability_rule(config, name, "source")
            latest = pd.to_datetime(row.get("latest_timestamp"), errors="coerce")
            latency_days = int(rule.latency_days) if rule else None
            available_at = latest + pd.Timedelta(days=latency_days) if pd.notna(latest) and latency_days is not None else pd.NaT
            rows.append(
                {
                    "entity_type": "source",
                    "name": name,
                    "source_mode": result.source_modes.get(name, ""),
                    "available": bool(row.get("available", False)),
                    "observation_date": latest,
                    "available_at_date": available_at,
                    "latency_days": latency_days,
                    "availability_assumption": rule.availability_assumption if rule else "missing_rule",
                    "availability_confidence": rule.availability_confidence if rule else "unknown",
                    "source_trust_tier": rule.source_trust_tier if rule else "unknown",
                    "data_processing_state": rule.data_processing_state if rule else "unknown",
                    "staleness_days": row.get("staleness_days"),
                    "staleness_threshold_days": row.get("staleness_threshold_days"),
                }
            )

    if not result.metric_health.empty and "metric" in result.metric_health.columns:
        for _, row in result.metric_health.iterrows():
            name = str(row.get("metric", ""))
            rule = _find_availability_rule(config, name, "metric")
            latest = pd.to_datetime(row.get("latest_timestamp"), errors="coerce")
            latency_days = int(rule.latency_days) if rule else None
            available_at = latest + pd.Timedelta(days=latency_days) if pd.notna(latest) and latency_days is not None else pd.NaT
            rows.append(
                {
                    "entity_type": "metric",
                    "name": name,
                    "source_mode": row.get("source_mode", ""),
                    "available": bool(row.get("available", False)),
                    "observation_date": latest,
                    "available_at_date": available_at,
                    "latency_days": latency_days,
                    "availability_assumption": rule.availability_assumption if rule else "derived_from_source_rules_pending",
                    "availability_confidence": rule.availability_confidence if rule else "unknown",
                    "source_trust_tier": rule.source_trust_tier if rule else "unknown",
                    "data_processing_state": rule.data_processing_state if rule else "derived",
                    "staleness_days": row.get("staleness_days"),
                    "staleness_threshold_days": None,
                }
            )

    calendar = pd.DataFrame(rows)
    if calendar.empty:
        return calendar
    return calendar.sort_values(["entity_type", "name"]).reset_index(drop=True)


def check_availability_calendar(calendar: pd.DataFrame, config: EvaluationConfig) -> EvaluationTestResult:
    test_id = "data.availability_calendar"
    warnings: List[EvaluationWarning] = []
    if calendar.empty:
        warnings.append(
            _warning(
                code="availability_calendar_empty",
                severity="medium",
                message="Availability calendar is empty; live-style claim readiness cannot be assessed.",
                test_id=test_id,
            )
        )
        return EvaluationTestResult(
            test_id=test_id,
            family="temporal_validity",
            status="warn",
            severity="medium",
            summary="Availability calendar could not be built from health metadata.",
            result_type="diagnostic",
            claim_scope="live_style_claims",
            metrics={"rows": 0},
            warnings=warnings,
        )

    unknown_availability = int(calendar["availability_confidence"].astype(str).str.lower().eq("unknown").sum())
    estimated_availability = int(calendar["availability_confidence"].astype(str).str.lower().eq("estimated").sum())
    missing_rules = int(calendar["availability_assumption"].astype(str).eq("missing_rule").sum())
    future_available = 0
    if {"available_at_date", "observation_date"}.issubset(calendar.columns):
        available_at = pd.to_datetime(calendar["available_at_date"], errors="coerce")
        observed = pd.to_datetime(calendar["observation_date"], errors="coerce")
        future_available = int((available_at > observed).sum())

    if unknown_availability:
        warnings.append(
            _warning(
                code="unknown_availability_rules",
                severity="medium",
                message=f"{unknown_availability} availability-calendar row(s) have unknown availability confidence.",
                test_id=test_id,
            )
        )
    if missing_rules:
        warnings.append(
            _warning(
                code="missing_availability_rule",
                severity="medium",
                message=f"{missing_rules} source row(s) are missing configured availability rules.",
                test_id=test_id,
            )
        )

    status = "pass" if not warnings else "warn"
    return EvaluationTestResult(
        test_id=test_id,
        family="temporal_validity",
        status=status,
        severity="info" if status == "pass" else "medium",
        summary="Built source/metric availability calendar from health metadata and configured latency assumptions.",
        result_type="diagnostic",
        claim_scope="live_style_claims",
        metrics={
            "rows": int(calendar.shape[0]),
            "source_rows": int((calendar["entity_type"] == "source").sum()),
            "metric_rows": int((calendar["entity_type"] == "metric").sum()),
            "unknown_availability_rows": unknown_availability,
            "estimated_availability_rows": estimated_availability,
            "missing_rule_rows": missing_rules,
            "delayed_rows": future_available,
            "max_latency_days": None
            if calendar["latency_days"].dropna().empty
            else int(pd.to_numeric(calendar["latency_days"], errors="coerce").max()),
        },
        warnings=warnings,
    )


def summarize_existing_benchmark(
    benchmark_by_label: pd.DataFrame,
    benchmark_by_signal: pd.DataFrame,
) -> EvaluationTestResult:
    test_id = "academic.existing_benchmark_snapshot"
    warnings: List[EvaluationWarning] = []
    if benchmark_by_label.empty or benchmark_by_signal.empty:
        warnings.append(
            _warning(
                code="benchmark_artifact_missing",
                severity="medium",
                message="Existing benchmark artifacts are empty; run pipeline benchmark before relying on academic snapshot results.",
                test_id=test_id,
            )
        )

    by_label_rows = int(benchmark_by_label.shape[0])
    by_signal_rows = int(benchmark_by_signal.shape[0])
    eligible_rows = 0
    if "eligible_for_aggregate" in benchmark_by_label.columns:
        eligible_rows = int(benchmark_by_label["eligible_for_aggregate"].fillna(False).sum())

    signals: List[str] = []
    if "signal" in benchmark_by_signal.columns:
        signals = sorted(benchmark_by_signal["signal"].dropna().astype(str).unique().tolist())

    status = "pass" if not warnings else "warn"
    return EvaluationTestResult(
        test_id=test_id,
        family="academic_predictive_power",
        status=status,
        severity="info" if status == "pass" else "medium",
        summary="Captured existing benchmark coverage so Phase 2 can reuse current label metrics without changing their meaning.",
        result_type="exploratory",
        claim_scope="retrospective_benchmark_snapshot",
        metrics={
            "by_label_rows": by_label_rows,
            "by_signal_rows": by_signal_rows,
            "eligible_label_rows": eligible_rows,
            "signals": signals,
        },
        warnings=warnings,
    )


def check_benchmark_claim_gate_readiness(
    benchmark_by_label: pd.DataFrame,
    benchmark_by_signal: pd.DataFrame,
    config: EvaluationConfig,
) -> EvaluationTestResult:
    test_id = "validator.benchmark_claim_gate_readiness"
    warnings: List[EvaluationWarning] = []
    if benchmark_by_label.empty:
        warnings.append(
            _warning(
                code="benchmark_gate_unavailable",
                severity="medium",
                message="Benchmark label rows are missing; claim-gate readiness cannot be evaluated.",
                test_id=test_id,
            )
        )
        return EvaluationTestResult(
            test_id=test_id,
            family="claim_validation",
            status="warn",
            severity="medium",
            summary="Benchmark claim-gate readiness could not be evaluated.",
            result_type="diagnostic",
            claim_scope="benchmark_claims",
            metrics={"label_rows": 0, "signal_rows": int(benchmark_by_signal.shape[0])},
            warnings=warnings,
        )

    frame = benchmark_by_label.copy()
    if "window" in frame.columns:
        frame = frame[frame["window"].astype(str) == "expanding"].copy()

    required = {"signal", "label_id", "family", "horizon_months", "n_obs", "n_events"}
    missing = sorted(required - set(frame.columns))
    for column in missing:
        warnings.append(
            _warning(
                code="benchmark_gate_column_missing",
                severity="medium",
                message=f"Benchmark rows are missing column required for claim gates: {column}",
                test_id=test_id,
            )
        )
    if missing:
        return EvaluationTestResult(
            test_id=test_id,
            family="claim_validation",
            status="warn",
            severity="medium",
            summary="Benchmark claim-gate readiness has incomplete inputs.",
            result_type="diagnostic",
            claim_scope="benchmark_claims",
            metrics={
                "label_rows": int(frame.shape[0]),
                "signal_rows": int(benchmark_by_signal.shape[0]),
                "missing_columns": missing,
            },
            warnings=warnings,
        )

    frame["horizon_months"] = pd.to_numeric(frame["horizon_months"], errors="coerce")
    frame["n_obs"] = pd.to_numeric(frame["n_obs"], errors="coerce")
    frame["n_events"] = pd.to_numeric(frame["n_events"], errors="coerce")
    invalid_horizon = frame["horizon_months"].isna() | (frame["horizon_months"] <= 0)
    if invalid_horizon.any():
        warnings.append(
            _warning(
                code="invalid_benchmark_horizon",
                severity="medium",
                message=f"{int(invalid_horizon.sum())} benchmark label row(s) have invalid horizons.",
                test_id=test_id,
            )
        )
    safe_horizon = frame["horizon_months"].where(~invalid_horizon)
    frame["effective_observations"] = np.floor(frame["n_obs"] / safe_horizon)
    frame["min_events_required"] = np.where(
        frame["horizon_months"] <= 24,
        int(config.claim_gates.min_events_short_medium),
        int(config.claim_gates.min_events_long),
    )
    frame["min_effective_obs_required"] = np.where(
        frame["horizon_months"] <= 24,
        int(config.claim_gates.min_effective_obs_short_medium),
        int(config.claim_gates.min_effective_obs_long),
    )
    frame["passes_event_gate"] = frame["n_events"] >= frame["min_events_required"]
    frame["passes_effective_obs_gate"] = frame["effective_observations"] >= frame["min_effective_obs_required"]
    benchmark_eligible = (
        frame["eligible_for_aggregate"].fillna(False).astype(bool)
        if "eligible_for_aggregate" in frame.columns
        else pd.Series(True, index=frame.index)
    )
    frame["passes_benchmark_eligibility"] = benchmark_eligible
    frame["passes_sample_gate"] = (
        frame["passes_event_gate"] & frame["passes_effective_obs_gate"] & frame["passes_benchmark_eligibility"]
    )

    if "family" in frame.columns and frame["family"].astype(str).str.lower().eq("quantile").any():
        warnings.append(
            _warning(
                code="retrospective_quantile_labels",
                severity="medium",
                message="Existing benchmark includes full-sample quantile labels; these retrospective rows remain exploratory. Use walk-forward artifacts for causal quantile checks.",
                test_id=test_id,
            )
        )
    if "calibrated_threshold" in frame.columns:
        warnings.append(
            _warning(
                code="same_window_threshold_selection",
                severity="medium",
                message="Existing benchmark rows include same-window best-F1 thresholds; threshold-dependent claims remain exploratory. Use walk-forward artifacts for causal alert thresholds.",
                test_id=test_id,
            )
        )

    failing = frame[~frame["passes_sample_gate"].fillna(False)]
    if not failing.empty:
        warnings.append(
            _warning(
                code="insufficient_claim_gate_samples",
                severity="medium",
                message=f"{len(failing)} benchmark label row(s) fail event-count or effective-sample claim gates.",
                test_id=test_id,
            )
        )

    signal_frame = benchmark_by_signal.copy()
    if not signal_frame.empty and "window" in signal_frame.columns:
        signal_frame = signal_frame[signal_frame["window"].astype(str) == "expanding"].copy()

    aggregate_missing: List[str] = []
    aggregate_ready_rows = 0
    aggregate_failing_rows = 0
    if signal_frame.empty:
        warnings.append(
            _warning(
                code="benchmark_signal_aggregate_missing",
                severity="medium",
                message="Benchmark signal aggregate rows are missing; signal-level claim readiness cannot be assessed.",
                test_id=test_id,
            )
        )
    else:
        aggregate_required = {"signal", "effective_weight_sum", "effective_label_count"}
        aggregate_missing = sorted(aggregate_required - set(signal_frame.columns))
        if aggregate_missing:
            warnings.append(
                _warning(
                    code="benchmark_signal_gate_column_missing",
                    severity="medium",
                    message=(
                        "Benchmark signal aggregate rows are missing column(s) required for claim gates: "
                        + ",".join(aggregate_missing)
                    ),
                    test_id=test_id,
                )
            )
        else:
            signal_frame["effective_weight_sum"] = pd.to_numeric(signal_frame["effective_weight_sum"], errors="coerce")
            signal_frame["effective_label_count"] = pd.to_numeric(signal_frame["effective_label_count"], errors="coerce")
            signal_frame["passes_aggregate_gate"] = (
                signal_frame["effective_weight_sum"] >= float(config.claim_gates.min_events_long)
            ) & (signal_frame["effective_label_count"] >= float(config.claim_gates.min_effective_obs_long))
            aggregate_ready_rows = int(signal_frame["passes_aggregate_gate"].fillna(False).sum())
            aggregate_failing_rows = int((~signal_frame["passes_aggregate_gate"].fillna(False)).sum())
            if aggregate_failing_rows:
                warnings.append(
                    _warning(
                        code="insufficient_signal_aggregate_support",
                        severity="medium",
                        message=f"{aggregate_failing_rows} signal aggregate row(s) fail claim-readiness support gates.",
                        test_id=test_id,
                    )
                )

            passing_signals = set(frame.loc[frame["passes_sample_gate"].fillna(False), "signal"].astype(str))
            aggregate_signals = set(signal_frame.loc[signal_frame["passes_aggregate_gate"].fillna(False), "signal"].astype(str))
            missing_aggregate_support = sorted(passing_signals - aggregate_signals)
            if missing_aggregate_support:
                warnings.append(
                    _warning(
                        code="passing_label_missing_signal_aggregate",
                        severity="medium",
                        message=(
                            "Some signals have passing label rows but no passing aggregate support: "
                            + ",".join(missing_aggregate_support)
                        ),
                        test_id=test_id,
                    )
                )

    grouped = (
        frame.groupby("signal", dropna=False)
        .agg(
            rows=("label_id", "count"),
            passing_rows=("passes_sample_gate", "sum"),
            min_events=("n_events", "min"),
            min_effective_observations=("effective_observations", "min"),
        )
        .reset_index()
        .sort_values("signal")
    )

    status = "pass" if not warnings else "warn"
    return EvaluationTestResult(
        test_id=test_id,
        family="claim_validation",
        status=status,
        severity="info" if status == "pass" else "medium",
        summary="Checked benchmark rows against initial event-count and effective-sample claim gates.",
        result_type="diagnostic",
        claim_scope="benchmark_claims",
        metrics={
            "label_rows": int(frame.shape[0]),
            "signal_rows": int(signal_frame.shape[0]),
            "passing_rows": int(frame["passes_sample_gate"].fillna(False).sum()),
            "failing_rows": int((~frame["passes_sample_gate"].fillna(False)).sum()),
            "aggregate_ready_rows": aggregate_ready_rows,
            "aggregate_failing_rows": aggregate_failing_rows,
            "aggregate_missing_columns": aggregate_missing,
            "signal_gate_summary": grouped.to_dict(orient="records"),
        },
        warnings=warnings,
    )


def summarize_walkforward_benchmark(
    walkforward_by_fold: pd.DataFrame,
    walkforward_by_label: pd.DataFrame,
    walkforward_by_signal: pd.DataFrame,
    embargo_audit: pd.DataFrame,
) -> EvaluationTestResult:
    test_id = "walkforward.expanding_benchmark"
    warnings: List[EvaluationWarning] = []
    if walkforward_by_fold.empty or walkforward_by_label.empty or walkforward_by_signal.empty or embargo_audit.empty:
        warnings.append(
            _warning(
                code="walkforward_benchmark_missing",
                severity="medium",
                message="One or more walk-forward benchmark artifacts are empty; causal benchmark evidence is incomplete.",
                test_id=test_id,
            )
        )

    missing_methods: List[str] = []
    missing_fold_columns: List[str] = []
    missing_audit_columns: List[str] = []
    audit_boundary_failures = 0
    if not walkforward_by_fold.empty:
        required_fold = {
            "fold_id",
            "decision_date",
            "label_train_end",
            "score_train_end",
            "test_start",
            "embargo_months",
            "selected_alert_threshold",
            "embargo_boundary_ok",
        }
        missing_fold_columns = sorted(required_fold - set(walkforward_by_fold.columns))
        for column in missing_fold_columns:
            warnings.append(
                _warning(
                    code="walkforward_fold_audit_column_missing",
                    severity="high",
                    message=f"Walk-forward fold artifact is missing audit column: {column}",
                    test_id=test_id,
                    blocks_dashboard=True,
                )
            )
        if "embargo_boundary_ok" in walkforward_by_fold.columns:
            audit_boundary_failures = int((~walkforward_by_fold["embargo_boundary_ok"].fillna(False).astype(bool)).sum())
            if audit_boundary_failures:
                warnings.append(
                    _warning(
                        code="walkforward_embargo_boundary_failure",
                        severity="high",
                        message=f"{audit_boundary_failures} walk-forward fold row(s) fail embargo boundary checks.",
                        test_id=test_id,
                        blocks_dashboard=True,
                    )
                )

    if not embargo_audit.empty:
        required_audit = {
            "fold_id",
            "decision_date",
            "label_train_end",
            "test_start",
            "label_training_uses_only_resolved_outcomes",
            "score_threshold_uses_only_prior_scores",
        }
        missing_audit_columns = sorted(required_audit - set(embargo_audit.columns))
        for column in missing_audit_columns:
            warnings.append(
                _warning(
                    code="walkforward_embargo_audit_column_missing",
                    severity="high",
                    message=f"Walk-forward embargo audit is missing column: {column}",
                    test_id=test_id,
                    blocks_dashboard=True,
                )
            )
        for column, code in (
            ("label_training_uses_only_resolved_outcomes", "walkforward_label_leakage"),
            ("score_threshold_uses_only_prior_scores", "walkforward_threshold_leakage"),
        ):
            if column in embargo_audit.columns:
                failures = int((~embargo_audit[column].fillna(False).astype(bool)).sum())
                if failures:
                    warnings.append(
                        _warning(
                            code=code,
                            severity="high",
                            message=f"{failures} walk-forward audit row(s) fail {column}.",
                            test_id=test_id,
                            blocks_dashboard=True,
                        )
                    )

    if not walkforward_by_label.empty:
        required_methods = {"label_method", "threshold_method", "embargo_months", "min_history_months"}
        missing_methods = sorted(required_methods - set(walkforward_by_label.columns))
        for column in missing_methods:
            warnings.append(
                _warning(
                    code="walkforward_audit_column_missing",
                    severity="high",
                    message=f"Walk-forward result is missing audit column: {column}",
                    test_id=test_id,
                    blocks_dashboard=True,
                )
            )
        if "family" in walkforward_by_label.columns:
            full_sample_quantile = walkforward_by_label["family"].astype(str).str.lower().eq("quantile").any()
            if full_sample_quantile:
                warnings.append(
                    _warning(
                        code="full_sample_quantile_leakage",
                        severity="high",
                        message="Walk-forward benchmark includes non-walk-forward quantile labels.",
                        test_id=test_id,
                        blocks_dashboard=True,
                    )
                )

    status = "fail" if any(w.blocks_dashboard for w in warnings) else ("warn" if warnings else "pass")
    return EvaluationTestResult(
        test_id=test_id,
        family="walkforward_predictive_power",
        status=status,
        severity="high" if status == "fail" else ("medium" if status == "warn" else "info"),
        summary="Built causal walk-forward benchmark snapshot with embargoed quantile labels and expanding alert thresholds.",
        result_type="confirmatory_candidate",
        claim_scope="walkforward_benchmark_claims",
        metrics={
            "by_label_rows": int(walkforward_by_label.shape[0]),
            "by_signal_rows": int(walkforward_by_signal.shape[0]),
            "by_fold_rows": int(walkforward_by_fold.shape[0]),
            "embargo_audit_rows": int(embargo_audit.shape[0]),
            "eligible_label_rows": int(walkforward_by_label.get("eligible_for_aggregate", pd.Series(dtype=bool)).fillna(False).sum())
            if not walkforward_by_label.empty
            else 0,
            "missing_audit_columns": missing_methods,
            "missing_fold_columns": missing_fold_columns,
            "missing_embargo_audit_columns": missing_audit_columns,
            "audit_boundary_failures": audit_boundary_failures,
            "families": sorted(walkforward_by_label.get("family", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
            if not walkforward_by_label.empty
            else [],
        },
        warnings=warnings,
    )


def summarize_walkforward_robustness(nulls: pd.DataFrame, baselines: pd.DataFrame, enriched_by_label: pd.DataFrame) -> EvaluationTestResult:
    test_id = "robustness.walkforward_nulls"
    warnings: List[EvaluationWarning] = []
    if nulls.empty:
        warnings.append(
            _warning(
                code="walkforward_nulls_missing",
                severity="medium",
                message="Walk-forward circular-shift null rows are missing; claim promotion must remain blocked.",
                test_id=test_id,
            )
        )
    if baselines.empty:
        warnings.append(
            _warning(
                code="walkforward_baselines_missing",
                severity="medium",
                message="Walk-forward random baseline rows are missing; baseline dominance cannot be assessed.",
                test_id=test_id,
            )
        )

    low_iteration_rows = 0
    null_not_survived = 0
    random_matches = 0
    fdr_not_survived = 0
    concentrated_rows = 0
    initial_robust_rows = 0
    confirmatory_by_label = _confirmatory_rows(enriched_by_label)
    if not confirmatory_by_label.empty:
        if "null_iterations" in confirmatory_by_label.columns:
            low_iteration_rows = int((pd.to_numeric(confirmatory_by_label["null_iterations"], errors="coerce") < 31).sum())
            if low_iteration_rows:
                warnings.append(
                    _warning(
                        code="walkforward_null_iterations_low",
                        severity="low",
                        message=f"{low_iteration_rows} walk-forward row(s) have coarse or missing null iteration counts.",
                        test_id=test_id,
                    )
                )
        if "survives_circular_shift_null" in confirmatory_by_label.columns:
            null_not_survived = int((~confirmatory_by_label["survives_circular_shift_null"].fillna(False).astype(bool)).sum())
            if null_not_survived:
                warnings.append(
                    _warning(
                        code="walkforward_null_not_survived",
                        severity="medium",
                        message=f"{null_not_survived} walk-forward label row(s) do not survive circular-shift null checks.",
                        test_id=test_id,
                    )
                )
        if {"auc", "random_auc"}.issubset(confirmatory_by_label.columns):
            observed_auc = pd.to_numeric(confirmatory_by_label["auc"], errors="coerce")
            random_auc = pd.to_numeric(confirmatory_by_label["random_auc"], errors="coerce")
            random_matches = int((random_auc.notna() & observed_auc.notna() & (random_auc >= observed_auc)).sum())
            if random_matches:
                warnings.append(
                    _warning(
                        code="walkforward_random_baseline_matches",
                        severity="medium",
                        message=f"{random_matches} walk-forward label row(s) are matched or beaten by the seeded random baseline.",
                        test_id=test_id,
                    )
                )
        if (
            "multiple_testing_corrected" in confirmatory_by_label.columns
            and not confirmatory_by_label["multiple_testing_corrected"].fillna(False).astype(bool).all()
        ):
            warnings.append(
                _warning(
                    code="walkforward_multiple_testing_uncorrected",
                    severity="medium",
                    message="Walk-forward null p-values are descriptive and not yet FDR/multiple-testing corrected.",
                    test_id=test_id,
                )
            )
        if "auc_passes_fdr" in confirmatory_by_label.columns:
            fdr_not_survived = int((~confirmatory_by_label["auc_passes_fdr"].fillna(False).astype(bool)).sum())
            if fdr_not_survived:
                warnings.append(
                    _warning(
                        code="walkforward_fdr_not_survived",
                        severity="medium",
                        message=f"{fdr_not_survived} walk-forward label row(s) do not survive FDR correction.",
                        test_id=test_id,
                    )
                )
        if "passes_regime_concentration_gate" in confirmatory_by_label.columns:
            concentrated_rows = int(
                (~confirmatory_by_label["passes_regime_concentration_gate"].fillna(False).astype(bool)).sum()
            )
            if concentrated_rows:
                warnings.append(
                    _warning(
                        code="walkforward_event_concentration",
                        severity="medium",
                        message=(
                            f"{concentrated_rows} walk-forward label row(s) have event-year concentration "
                            "too high for claim promotion."
                        ),
                        test_id=test_id,
                    )
                )
        if "p_value_caveat" in confirmatory_by_label.columns:
            warnings.append(
                _warning(
                    code="walkforward_p_value_caveat",
                    severity="low",
                    message="Circular-shift p-values are descriptive because horizons overlap and events are autocorrelated/sparse.",
                    test_id=test_id,
                )
            )
        if "passes_initial_robustness_gates" in confirmatory_by_label.columns:
            initial_robust_rows = int(confirmatory_by_label["passes_initial_robustness_gates"].fillna(False).astype(bool).sum())
            if initial_robust_rows == 0:
                warnings.append(
                    _warning(
                        code="walkforward_no_initial_robust_rows",
                        severity="high",
                        message="No walk-forward label rows pass initial null, random-baseline, FDR, and concentration gates.",
                        test_id=test_id,
                        blocks_dashboard=True,
                    )
                )

    status = "fail" if any(w.blocks_dashboard for w in warnings) else ("warn" if warnings else "pass")
    return EvaluationTestResult(
        test_id=test_id,
        family="uncertainty_nulls",
        status=status,
        severity="high" if status == "fail" else ("medium" if status == "warn" else "info"),
        summary="Evaluated deterministic circular-shift nulls and seeded random baselines for walk-forward rows.",
        result_type="diagnostic",
        claim_scope="walkforward_benchmark_claims",
        metrics={
            "null_rows": int(nulls.shape[0]),
            "baseline_rows": int(baselines.shape[0]),
            "walkforward_label_rows": int(enriched_by_label.shape[0]),
            "low_iteration_rows": low_iteration_rows,
            "null_not_survived_rows": null_not_survived,
            "random_baseline_matches": random_matches,
            "fdr_not_survived_rows": fdr_not_survived,
            "event_concentrated_rows": concentrated_rows,
            "initial_robust_rows": initial_robust_rows,
        },
        warnings=warnings,
    )


def summarize_academic_diagnostics(
    reliability_bins: pd.DataFrame,
    monotonicity: pd.DataFrame,
    enriched_by_label: pd.DataFrame,
) -> EvaluationTestResult:
    test_id = "academic.calibration_monotonicity"
    warnings: List[EvaluationWarning] = []
    if reliability_bins.empty:
        warnings.append(
            _warning(
                code="academic_reliability_bins_missing",
                severity="medium",
                message="Reliability-bin diagnostics are missing; score meaning cannot be inspected by quantile.",
                test_id=test_id,
            )
        )
    if monotonicity.empty:
        warnings.append(
            _warning(
                code="academic_monotonicity_missing",
                severity="medium",
                message="Monotonicity diagnostics are missing; score ordering cannot be inspected.",
                test_id=test_id,
            )
        )

    confirmatory_monotonicity = _confirmatory_rows(monotonicity)
    confirmatory_reliability_bins = _confirmatory_rows(reliability_bins)
    monotonicity_failures = 0
    low_bin_rows = 0
    if not confirmatory_monotonicity.empty and "passes_monotonicity_gate" in confirmatory_monotonicity.columns:
        monotonicity_failures = int((~confirmatory_monotonicity["passes_monotonicity_gate"].fillna(False).astype(bool)).sum())
        if monotonicity_failures:
            warnings.append(
                _warning(
                    code="academic_monotonicity_not_supported",
                    severity="medium",
                    message=f"{monotonicity_failures} walk-forward label row(s) do not show monotonic event-rate ordering.",
                    test_id=test_id,
                )
            )
    if not confirmatory_reliability_bins.empty and "low_bin_count_warning" in confirmatory_reliability_bins.columns:
        low_bin_rows = int(confirmatory_reliability_bins["low_bin_count_warning"].fillna(False).astype(bool).sum())
        if low_bin_rows:
            warnings.append(
                _warning(
                    code="academic_low_bin_counts",
                    severity="medium",
                    message=f"{low_bin_rows} reliability-bin row(s) have low observation counts.",
                    test_id=test_id,
                )
            )
    if not reliability_bins.empty:
        warnings.append(
            _warning(
                code="academic_posthoc_bins",
                severity="low",
                message=(
                    "Reliability bins use post-hoc quantiles over walk-forward holdout rows; they are descriptive "
                    "score-meaning diagnostics, not deployable calibration thresholds."
                ),
                test_id=test_id,
            )
        )

    status = "pass" if not warnings else "warn"
    return EvaluationTestResult(
        test_id=test_id,
        family="academic_predictive_shape",
        status=status,
        severity="info" if status == "pass" else "medium",
        summary="Built post-hoc reliability-bin and monotonicity diagnostics from causal walk-forward fold rows.",
        result_type="diagnostic",
        claim_scope="walkforward_benchmark_claims",
        metrics={
            "reliability_bin_rows": int(reliability_bins.shape[0]),
            "monotonicity_rows": int(monotonicity.shape[0]),
            "walkforward_label_rows": int(enriched_by_label.shape[0]),
            "monotonicity_failures": monotonicity_failures,
            "low_bin_rows": low_bin_rows,
            "mean_spearman_score_label": float(
                pd.to_numeric(confirmatory_monotonicity.get("spearman_score_label", pd.Series(dtype=float)), errors="coerce").mean()
            )
            if not confirmatory_monotonicity.empty
            else None,
        },
        warnings=warnings,
    )


def summarize_validity_diagnostics(
    label_audit: pd.DataFrame,
    shift_probe: pd.DataFrame,
    synthetic_sentinels: pd.DataFrame,
    enriched_by_label: pd.DataFrame,
) -> EvaluationTestResult:
    test_id = "validity.label_leakage_sentinels"
    warnings: List[EvaluationWarning] = []
    for frame, code, message in (
        (label_audit, "label_audit_missing", "Label-audit rows are missing; event clustering and sparsity cannot be assessed."),
        (shift_probe, "shift_probe_missing", "Shift-probe rows are missing; leakage sentinel checks cannot be assessed."),
        (
            synthetic_sentinels,
            "synthetic_sentinels_missing",
            "Synthetic sentinel rows are missing; harness sanity checks cannot be assessed.",
        ),
    ):
        if frame.empty:
            warnings.append(_warning(code=code, severity="medium", message=message, test_id=test_id))

    label_cluster_failures = 0
    shift_probe_failures = 0
    sentinel_failures = 0
    confirmatory_by_label = _confirmatory_rows(enriched_by_label)
    confirmatory_sentinels = _confirmatory_rows(synthetic_sentinels)
    if "passes_label_cluster_gate" in confirmatory_by_label.columns:
        label_cluster_failures = int((~confirmatory_by_label["passes_label_cluster_gate"].fillna(False).astype(bool)).sum())
        if label_cluster_failures:
            warnings.append(
                _warning(
                    code="label_cluster_gate_failed",
                    severity="medium",
                    message=f"{label_cluster_failures} walk-forward label row(s) have too few or too concentrated event clusters.",
                    test_id=test_id,
                )
            )
    if "passes_shift_leakage_probe" in confirmatory_by_label.columns:
        shift_probe_failures = int((~confirmatory_by_label["passes_shift_leakage_probe"].fillna(False).astype(bool)).sum())
        if shift_probe_failures:
            warnings.append(
                _warning(
                    code="future_shift_probe_advantage",
                    severity="high",
                    message=f"{shift_probe_failures} walk-forward label row(s) are materially improved by future-shifted scores.",
                    test_id=test_id,
                    blocks_dashboard=True,
                )
            )

    if not confirmatory_sentinels.empty and {"sentinel", "auc"}.issubset(confirmatory_sentinels.columns):
        perfect = confirmatory_sentinels[confirmatory_sentinels["sentinel"].astype(str) == "perfect_label_sentinel"]
        inverted = confirmatory_sentinels[confirmatory_sentinels["sentinel"].astype(str) == "inverted_label_sentinel"]
        perfect_auc = pd.to_numeric(perfect["auc"], errors="coerce") if not perfect.empty else pd.Series(dtype=float)
        inverted_auc = pd.to_numeric(inverted["auc"], errors="coerce") if not inverted.empty else pd.Series(dtype=float)
        perfect_bad = int((perfect_auc.isna() | (perfect_auc < 0.99)).sum()) if not perfect.empty else 0
        inverted_bad = int((inverted_auc.isna() | (inverted_auc > 0.01)).sum()) if not inverted.empty else 0
        sentinel_failures = perfect_bad + inverted_bad
        if sentinel_failures:
            warnings.append(
                _warning(
                    code="synthetic_sentinel_harness_failure",
                    severity="high",
                    message="Synthetic perfect/inverted sentinels did not produce expected AUC bounds.",
                    test_id=test_id,
                    blocks_dashboard=True,
                )
            )

    status = "fail" if any(w.blocks_dashboard for w in warnings) else ("warn" if warnings else "pass")
    return EvaluationTestResult(
        test_id=test_id,
        family="validity_leakage",
        status=status,
        severity="high" if status == "fail" else ("medium" if status == "warn" else "info"),
        summary="Audited label sparsity/clustering, future-shift leakage probes, and synthetic harness sentinels.",
        result_type="diagnostic",
        claim_scope="walkforward_benchmark_claims",
        metrics={
            "label_audit_rows": int(label_audit.shape[0]),
            "shift_probe_rows": int(shift_probe.shape[0]),
            "synthetic_sentinel_rows": int(synthetic_sentinels.shape[0]),
            "label_cluster_failures": label_cluster_failures,
            "shift_probe_failures": shift_probe_failures,
            "sentinel_failures": sentinel_failures,
        },
        warnings=warnings,
    )


def summarize_practical_strategies(
    strategy_results: pd.DataFrame,
    strategy_curves: pd.DataFrame,
    strategy_trades: pd.DataFrame,
) -> EvaluationTestResult:
    test_id = "practical.monthly_strategy_suite"
    warnings: List[EvaluationWarning] = []
    if strategy_results.empty:
        warnings.append(
            _warning(
                code="practical_strategy_results_missing",
                severity="medium",
                message="Practical strategy results are missing; usability claims cannot be assessed.",
                test_id=test_id,
            )
        )
    if strategy_curves.empty:
        warnings.append(
            _warning(
                code="practical_strategy_curves_missing",
                severity="medium",
                message="Practical strategy equity curves are missing; drawdown and path behavior cannot be inspected.",
                test_id=test_id,
            )
        )

    metric_rows = 0
    baseline_rows = 0
    dca_rows = 0
    turnover_failures = 0
    cost_drag_failures = 0
    buy_hold_underperformance = 0
    missing_exposure_adjusted_rows = 0
    dca_underperformance = 0
    production_dca_rows = 0
    production_dca_rows_with_fixed_delta = 0
    production_dca_beating_fixed_rows = 0
    metric_policy_with_buy_hold_delta = 0
    if not strategy_results.empty:
        policy_family = strategy_results.get("policy_family", pd.Series(dtype=str)).astype(str)
        metric_rows = int((policy_family == "metric_policy").sum())
        baseline_rows = int((policy_family == "baseline").sum())
        dca_rows = int((policy_family == "dca_cashflow").sum())
        production_dca_rows = int((policy_family == "production_dca_cashflow").sum())
        if metric_rows == 0 or baseline_rows == 0 or dca_rows == 0:
            warnings.append(
                _warning(
                    code="practical_strategy_family_missing",
                    severity="medium",
                    message="Practical suite must include metric policies, allocation baselines, and same-cashflow DCA rows.",
                    test_id=test_id,
                )
            )
        if production_dca_rows == 0:
            warnings.append(
                _warning(
                    code="practical_production_dynamic_dca_unavailable",
                    severity="medium",
                    message=(
                        "Production dynamic-DCA financial benchmark rows are unavailable; "
                        "production cashflow claims are not applicable for this run."
                    ),
                    test_id=test_id,
                )
            )
        if "passes_turnover_guardrail" in strategy_results.columns:
            turnover_failures = int((~strategy_results["passes_turnover_guardrail"].fillna(False).astype(bool)).sum())
            if turnover_failures:
                warnings.append(
                    _warning(
                        code="practical_turnover_guardrail_failed",
                        severity="high",
                        message=f"{turnover_failures} strategy row(s) exceed the turnover guardrail.",
                        test_id=test_id,
                        blocks_dashboard=True,
                    )
                )
        if "passes_cost_drag_guardrail" in strategy_results.columns:
            cost_drag_failures = int((~strategy_results["passes_cost_drag_guardrail"].fillna(False).astype(bool)).sum())
            if cost_drag_failures:
                warnings.append(
                    _warning(
                        code="practical_cost_drag_guardrail_failed",
                        severity="high",
                        message=f"{cost_drag_failures} strategy row(s) exceed the cost-drag guardrail.",
                        test_id=test_id,
                        blocks_dashboard=True,
                    )
                )
        if "cagr_delta_vs_buy_hold" in strategy_results.columns:
            deltas = pd.to_numeric(strategy_results["cagr_delta_vs_buy_hold"], errors="coerce")
            metric_delta_mask = policy_family.eq("metric_policy") & deltas.notna()
            metric_policy_with_buy_hold_delta = int(metric_delta_mask.sum())
            buy_hold_underperformance = int((metric_delta_mask & (deltas < 0.0)).sum())
            if buy_hold_underperformance:
                warnings.append(
                    _warning(
                        code="practical_buy_hold_underperformance",
                        severity="medium",
                        message=f"{buy_hold_underperformance} metric-policy strategy row(s) underperform buy-and-hold CAGR.",
                        test_id=test_id,
                    )
                )
            if metric_policy_with_buy_hold_delta and buy_hold_underperformance == metric_policy_with_buy_hold_delta:
                warnings.append(
                    _warning(
                        code="practical_no_metric_policy_beats_buy_hold",
                        severity="high",
                        message="No metric-policy strategy row beats buy-and-hold CAGR after costs.",
                        test_id=test_id,
                        blocks_dashboard=True,
                    )
                )
        if "cagr_delta_vs_fixed_dca" in strategy_results.columns:
            dca_delta = pd.to_numeric(strategy_results["cagr_delta_vs_fixed_dca"], errors="coerce")
            dca_mask = strategy_results.get("strategy", pd.Series(dtype=str)).astype(str).eq("risk_weighted_dca") & dca_delta.notna()
            dca_underperformance = int((dca_mask & (dca_delta < 0.0)).sum())
            if int(dca_mask.sum()) and dca_underperformance == int(dca_mask.sum()):
                warnings.append(
                    _warning(
                        code="practical_no_risk_weighted_dca_beats_fixed_dca",
                        severity="high",
                        message="Risk-weighted DCA does not beat fixed monthly DCA in any evaluated cost row.",
                        test_id=test_id,
                        blocks_dashboard=True,
                    )
                )
            production_mask = (
                policy_family.eq("production_dca_cashflow")
                & strategy_results.get("strategy", pd.Series(dtype=str)).astype(str).eq("dynamic_dca")
                & dca_delta.notna()
            )
            production_dca_rows_with_fixed_delta = int(production_mask.sum())
            production_dca_beating_fixed_rows = int((production_mask & (dca_delta > 0.0)).sum())
            if production_dca_rows_with_fixed_delta and production_dca_beating_fixed_rows == 0:
                warnings.append(
                    _warning(
                        code="practical_no_production_dynamic_dca_beats_fixed_dca",
                        severity="high",
                        message="Production dynamic DCA does not beat fixed monthly DCA in any evaluated row.",
                        test_id=test_id,
                        blocks_dashboard=True,
                    )
                )
        if "cagr_per_avg_exposure" in strategy_results.columns:
            exposure_adjusted = pd.to_numeric(strategy_results["cagr_per_avg_exposure"], errors="coerce")
            missing_exposure_adjusted_rows = int((policy_family.eq("metric_policy") & exposure_adjusted.isna()).sum())
            if missing_exposure_adjusted_rows:
                warnings.append(
                    _warning(
                        code="practical_exposure_adjusted_kpi_missing",
                        severity="medium",
                        message=f"{missing_exposure_adjusted_rows} metric-policy row(s) lack exposure-adjusted CAGR.",
                        test_id=test_id,
                    )
                )

    status = "fail" if any(w.blocks_dashboard for w in warnings) else ("warn" if warnings else "pass")
    return EvaluationTestResult(
        test_id=test_id,
        family="practical_usability",
        status=status,
        severity="high" if status == "fail" else ("medium" if status == "warn" else "info"),
        summary="Simulated predeclared monthly allocation policies, baselines, transaction costs, turnover, and drawdown guardrails.",
        result_type="diagnostic",
        claim_scope="practical_strategy_claims",
        metrics={
            "strategy_result_rows": int(strategy_results.shape[0]),
            "strategy_curve_rows": int(strategy_curves.shape[0]),
            "strategy_trade_rows": int(strategy_trades.shape[0]),
            "metric_policy_rows": metric_rows,
            "baseline_rows": baseline_rows,
            "dca_cashflow_rows": dca_rows,
            "production_dca_cashflow_rows": production_dca_rows,
            "turnover_failures": turnover_failures,
            "cost_drag_failures": cost_drag_failures,
            "buy_hold_underperformance_rows": buy_hold_underperformance,
            "metric_policy_with_buy_hold_delta": metric_policy_with_buy_hold_delta,
            "risk_weighted_dca_underperformance_rows": dca_underperformance,
            "production_dynamic_dca_rows_with_fixed_delta": production_dca_rows_with_fixed_delta,
            "production_dynamic_dca_beating_fixed_rows": production_dca_beating_fixed_rows,
            "missing_exposure_adjusted_rows": missing_exposure_adjusted_rows,
        },
        warnings=warnings,
    )


def summarize_dca_threshold_reachability(threshold_reachability: pd.DataFrame) -> EvaluationTestResult:
    test_id = "practical.dca_threshold_reachability"
    warnings: List[EvaluationWarning] = []
    if threshold_reachability.empty:
        warnings.append(
            _warning(
                code="dca_threshold_reachability_unavailable",
                severity="medium",
                message=(
                    "DCA threshold reachability could not be evaluated because production cycle regime "
                    "scores were unavailable."
                ),
                test_id=test_id,
            )
        )
        return EvaluationTestResult(
            test_id=test_id,
            family="practical_usability",
            status="warn",
            severity="medium",
            summary="Production dynamic-DCA threshold reachability was not applicable for this run.",
            result_type="diagnostic",
            claim_scope="production_dca_claims",
            metrics={
                "rows": 0,
                "reachability_floor": DCA_THRESHOLD_REACHABILITY_MIN_PCT,
                "rarely_reachable_rows": 0,
            },
            warnings=warnings,
        )

    reachability = pd.to_numeric(
        threshold_reachability.get(
            "pct_action_gate_reachable",
            pd.Series(np.nan, index=threshold_reachability.index),
        ),
        errors="coerce",
    )
    observations = pd.to_numeric(
        threshold_reachability.get("observations", pd.Series(np.nan, index=threshold_reachability.index)),
        errors="coerce",
    )
    rare_mask = reachability.notna() & observations.gt(0) & (reachability < DCA_THRESHOLD_REACHABILITY_MIN_PCT)
    rarely_reachable_rows = int(rare_mask.sum())
    if rarely_reachable_rows:
        labels = []
        for _, row in threshold_reachability.loc[rare_mask].iterrows():
            label = str(row.get("threshold_name", row.get("action", "threshold")))
            pct = pd.to_numeric(pd.Series([row.get("pct_action_gate_reachable")]), errors="coerce").iloc[0]
            labels.append(f"{label}={pct:.2%}" if np.isfinite(pct) else label)
        warnings.append(
            _warning(
                code="dca_threshold_rarely_reachable",
                severity="medium",
                message=(
                    "Production dynamic-DCA threshold reachability is below the predeclared "
                    f"{DCA_THRESHOLD_REACHABILITY_MIN_PCT:.0%} history floor for: {', '.join(labels)}."
                ),
                test_id=test_id,
                blocks_dashboard=False,
            )
        )

    status = "warn" if warnings else "pass"
    return EvaluationTestResult(
        test_id=test_id,
        family="practical_usability",
        status=status,
        severity="medium" if status == "warn" else "info",
        summary="Checked whether raw production cycle composites historically crossed dynamic-DCA buy/sell gates.",
        result_type="diagnostic",
        claim_scope="production_dca_claims",
        metrics={
            "rows": int(threshold_reachability.shape[0]),
            "reachability_floor": DCA_THRESHOLD_REACHABILITY_MIN_PCT,
            "rarely_reachable_rows": rarely_reachable_rows,
            "min_pct_action_gate_reachable": float(reachability.min()) if reachability.notna().any() else np.nan,
        },
        warnings=warnings,
    )


def summarize_dca_evidence(
    evidence_summary: pd.DataFrame,
    causality_audit: pd.DataFrame,
) -> EvaluationTestResult:
    test_id = "practical.dca_evidence"
    warnings: List[EvaluationWarning] = []
    if evidence_summary.empty:
        warnings.append(
            _warning(
                code="dca_evidence_unavailable",
                severity="high",
                message="DCA evidence could not be evaluated because price/risk overlap was insufficient.",
                test_id=test_id,
                blocks_dashboard=True,
            )
        )
        return EvaluationTestResult(
            test_id=test_id,
            family="practical_usability",
            status="fail",
            severity="high",
            summary="The compact DCA evidence suite was unavailable.",
            result_type="diagnostic",
            claim_scope="dca_risk_claims",
            warnings=warnings,
        )

    statuses = evidence_summary.get("status", pd.Series("fail", index=evidence_summary.index)).astype(str)
    failed_tests = evidence_summary.loc[~statuses.eq("pass"), "test"].astype(str).tolist()
    if failed_tests:
        warnings.append(
            _warning(
                code="dca_evidence_not_supported",
                severity="high",
                message=f"DCA evidence is not supported by: {', '.join(failed_tests)}.",
                test_id=test_id,
                blocks_dashboard=True,
            )
        )

    causality_passes = bool(
        not causality_audit.empty
        and causality_audit.get(
            "passes_causality_audit", pd.Series(False, index=causality_audit.index)
        ).fillna(False).astype(bool).all()
    )
    if not causality_passes:
        warnings.append(
            _warning(
                code="dca_strategy_causality_audit_failed",
                severity="high",
                message="Future signal mutations changed earlier DCA decisions or the execution lag invariant failed.",
                test_id=test_id,
                blocks_dashboard=True,
            )
        )

    status = "fail" if any(warning.blocks_dashboard for warning in warnings) else "pass"
    return EvaluationTestResult(
        test_id=test_id,
        family="practical_usability",
        status=status,
        severity="high" if status == "fail" else "info",
        summary="Separated DCA evidence into accumulation-only value, de-risking value, and policy-independent signal value.",
        result_type="diagnostic",
        claim_scope="dca_risk_claims",
        metrics={
            "evidence_tests": int(evidence_summary.shape[0]),
            "passing_evidence_tests": int(statuses.eq("pass").sum()),
            "causality_audit_passes": causality_passes,
        },
        warnings=warnings,
    )


def summarize_strength_mapping(
    degraded_data: pd.DataFrame,
    regime_results: pd.DataFrame,
    rolling_stability: pd.DataFrame,
    enriched_by_label: pd.DataFrame,
) -> EvaluationTestResult:
    test_id = "robustness.strength_mapping"
    warnings: List[EvaluationWarning] = []
    if degraded_data.empty:
        warnings.append(
            _warning(
                code="degraded_data_missing",
                severity="medium",
                message="Degraded-data scenario rows are missing; source fragility cannot be assessed.",
                test_id=test_id,
            )
        )
    if regime_results.empty:
        warnings.append(
            _warning(
                code="regime_results_missing",
                severity="medium",
                message="Regime-specific rows are missing; market-regime strengths cannot be assessed.",
                test_id=test_id,
            )
        )
    if rolling_stability.empty:
        warnings.append(
            _warning(
                code="rolling_stability_missing",
                severity="medium",
                message="Rolling-window rows are missing; performance decay cannot be assessed.",
                test_id=test_id,
            )
        )

    degraded_failures = 0
    rolling_failures = 0
    low_regime_rows = 0
    confirmatory_by_label = _confirmatory_rows(enriched_by_label)
    confirmatory_regime_results = _confirmatory_rows(regime_results)
    if "passes_degraded_data_gate" in confirmatory_by_label.columns:
        degraded_failures = int((~confirmatory_by_label["passes_degraded_data_gate"].fillna(False).astype(bool)).sum())
        if degraded_failures:
            warnings.append(
                _warning(
                    code="degraded_data_gate_failed",
                    severity="medium",
                    message=f"{degraded_failures} walk-forward label row(s) are fragile under degraded-score scenarios.",
                    test_id=test_id,
                )
            )
    if "passes_rolling_stability_gate" in confirmatory_by_label.columns:
        rolling_failures = int((~confirmatory_by_label["passes_rolling_stability_gate"].fillna(False).astype(bool)).sum())
        if rolling_failures:
            warnings.append(
                _warning(
                    code="rolling_stability_gate_failed",
                    severity="medium",
                    message=f"{rolling_failures} walk-forward label row(s) have unstable rolling AUC ranges.",
                    test_id=test_id,
                )
            )
    if not confirmatory_regime_results.empty and "regime_result_eligible" in confirmatory_regime_results.columns:
        low_regime_rows = int((~confirmatory_regime_results["regime_result_eligible"].fillna(False).astype(bool)).sum())
        if low_regime_rows:
            warnings.append(
                _warning(
                    code="low_regime_sample_rows",
                    severity="low",
                    message=f"{low_regime_rows} regime row(s) are underpowered and should be treated descriptively.",
                    test_id=test_id,
                )
            )

    status = "pass" if not warnings else "warn"
    return EvaluationTestResult(
        test_id=test_id,
        family="robustness_strength_mapping",
        status=status,
        severity="info" if status == "pass" else "medium",
        summary="Mapped degraded-data fragility, market-regime behavior, and rolling-window stability.",
        result_type="diagnostic",
        claim_scope="robustness_claims",
        metrics={
            "degraded_data_rows": int(degraded_data.shape[0]),
            "regime_result_rows": int(regime_results.shape[0]),
            "rolling_stability_rows": int(rolling_stability.shape[0]),
            "degraded_failures": degraded_failures,
            "rolling_failures": rolling_failures,
            "low_regime_rows": low_regime_rows,
        },
        warnings=warnings,
    )


def validate_claim_gates(results: Iterable[EvaluationTestResult]) -> List[EvaluationWarning]:
    warnings: List[EvaluationWarning] = []
    for result in results:
        for warning in result.warnings:
            if warning.blocks_dashboard:
                warnings.append(
                    EvaluationWarning(
                        code="dashboard_export_blocked",
                        severity="high",
                        message=f"{result.test_id} blocks dashboard claims because {warning.code} was raised.",
                        test_id=result.test_id,
                        blocks_dashboard=True,
                    )
                )
    if not warnings:
        warnings.append(
            EvaluationWarning(
                code="phase2_harness_only",
                severity="low",
                message="This run validates the evaluation harness; it does not yet promote metric claims.",
                test_id="validator.claim_gates",
                blocks_dashboard=False,
            )
        )
    return warnings
