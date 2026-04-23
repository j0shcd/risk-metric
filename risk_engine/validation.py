from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd

from .types import RiskOutput


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    errors: List[str]


def _check_index(series: pd.DataFrame, errors: List[str]) -> None:
    if not series.index.is_monotonic_increasing:
        errors.append("Output index is not monotonic increasing.")
    if series.index.has_duplicates:
        errors.append("Output index has duplicate timestamps.")


def _check_bounds(series: pd.DataFrame, errors: List[str]) -> None:
    bounded_columns = {
        "btc_risk_heat": (-1.0, 1.0),
        "btc_risk_attention": (0.0, 1.0),
        "total_market_risk_heat": (-1.0, 1.0),
        "total_market_risk_attention": (0.0, 1.0),
        "headline_attention": (0.0, 1.0),
        "headline_direction": (-1.0, 1.0),
        "confidence_score": (0.0, 1.0),
    }

    for column, (low, high) in bounded_columns.items():
        if column not in series.columns:
            errors.append(f"Missing output column: {column}")
            continue

        values = series[column].dropna()
        if values.empty:
            errors.append(f"Column has no usable values: {column}")
            continue

        if (values < low).any() or (values > high).any():
            errors.append(f"Column out of bounds [{low}, {high}]: {column}")


def _check_recent_signal_presence(series: pd.DataFrame, errors: List[str], lookback_days: int = 30) -> None:
    tail = series.tail(lookback_days)
    required_columns = [
        "btc_risk_heat",
        "btc_risk_attention",
        "headline_attention",
        "headline_direction",
        "confidence_score",
    ]
    for column in required_columns:
        if tail[column].dropna().empty:
            errors.append(f"No recent values in required column: {column}")


def _check_feature_reliability(feature_frames: dict, errors: List[str]) -> None:
    for name, frame in feature_frames.items():
        if "reliability" not in frame.columns:
            errors.append(f"Feature frame missing reliability column: {name}")
            continue
        rel = frame["reliability"].dropna()
        if rel.empty:
            continue
        if (rel < 0.0).any() or (rel > 1.0).any():
            errors.append(f"Feature reliability out of [0, 1] bounds: {name}")


def _check_output_staleness(
    series: pd.DataFrame,
    errors: List[str],
    columns: List[str],
    max_staleness_days: int = 7,
) -> None:
    now = pd.Timestamp.utcnow().tz_localize(None).normalize()
    for column in columns:
        values = series[column].dropna()
        if values.empty:
            continue
        last_date = values.index.max().normalize()
        staleness_days = int((now - last_date).days)
        if staleness_days > max_staleness_days:
            errors.append(
                f"Column appears stale ({staleness_days}d > {max_staleness_days}d): {column}"
            )


def _check_source_health(result: RiskOutput, errors: List[str]) -> None:
    if result.source_health.empty:
        errors.append("Missing source health report.")
        return

    required_sources = {"btc_price"}
    available_sources = set(
        result.source_health.loc[result.source_health["available"].fillna(False), "source"].astype(str).tolist()
    )
    missing = sorted(required_sources - available_sources)
    if missing:
        errors.append(f"Critical sources unavailable: {', '.join(missing)}")


def _check_metric_health(result: RiskOutput, errors: List[str]) -> None:
    if result.metric_health.empty:
        errors.append("Missing metric health report.")
        return

    required_targets = {"btc", "total_market"}
    available = result.metric_health[result.metric_health["available"].fillna(False)]
    available_targets = set(available["target"].astype(str).tolist())
    missing_targets = sorted(required_targets - available_targets)
    if missing_targets:
        errors.append(f"No available metrics for targets: {', '.join(missing_targets)}")


def validate_output(result: RiskOutput) -> ValidationResult:
    errors: List[str] = []

    _check_index(result.series, errors)
    _check_bounds(result.series, errors)
    _check_recent_signal_presence(result.series, errors)
    _check_feature_reliability(result.feature_frames, errors)
    _check_output_staleness(
        result.series,
        errors,
        columns=[
            "btc_risk_heat",
            "btc_risk_attention",
            "total_market_risk_heat",
            "total_market_risk_attention",
            "headline_attention",
            "headline_direction",
            "confidence_score",
        ],
    )
    _check_source_health(result, errors)
    _check_metric_health(result, errors)

    return ValidationResult(passed=not errors, errors=errors)
