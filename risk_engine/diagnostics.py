from __future__ import annotations

from typing import Dict, Iterable, List

import numpy as np
import pandas as pd

from .scoring import MetricSpec
from .sources.common import series_staleness_days
from .types import FeatureBundle


def _safe_float(value: float | int | np.floating | None) -> float:
    if value is None:
        return float("nan")
    return float(value)


def _source_staleness_threshold_days(source_name: str) -> int:
    if source_name == "btc_price":
        return 3
    if source_name == "total_market_cap":
        return 14
    if source_name.startswith("onchain::"):
        return 7
    if source_name.startswith("social::"):
        return 21
    if source_name == "fear_greed_index":
        return 14
    return 30


def _source_contract_status(
    source_name: str,
    series: pd.Series,
    as_of: pd.Timestamp,
    available: bool,
) -> tuple[bool, str, int, int]:
    issues: List[str] = []
    duplicate_count = int(series.index.duplicated().sum())
    if duplicate_count > 0:
        issues.append("duplicate_timestamps")

    if not series.index.is_monotonic_increasing:
        issues.append("non_monotonic_index")

    non_numeric_count = 0
    if available:
        numeric = pd.to_numeric(series.dropna(), errors="coerce")
        non_numeric_count = int(numeric.isna().sum())
        if non_numeric_count > 0:
            issues.append("non_numeric_values")

        staleness_days = series_staleness_days(series.dropna(), as_of=as_of)
        threshold = _source_staleness_threshold_days(source_name)
        if staleness_days is not None and staleness_days > threshold:
            issues.append(f"stale:{staleness_days}d>{threshold}d")

    contract_passed = len(issues) == 0
    contract_issues = ";".join(issues)
    return contract_passed, contract_issues, duplicate_count, non_numeric_count


def build_source_health(source_map: Dict[str, pd.Series], as_of: pd.Timestamp, lookback_days: int = 30) -> pd.DataFrame:
    rows: List[dict] = []

    for source_name, series in source_map.items():
        source_series = series if series is not None else pd.Series(dtype=float)
        clean = source_series.dropna()
        threshold_days = _source_staleness_threshold_days(source_name)
        contract_passed, contract_issues, duplicate_count, non_numeric_count = _source_contract_status(
            source_name=source_name,
            series=source_series,
            as_of=as_of,
            available=not clean.empty,
        )
        if clean.empty:
            rows.append(
                {
                    "source": source_name,
                    "available": False,
                    "latest_timestamp": pd.NaT,
                    "staleness_days": np.nan,
                    "coverage_30d": 0.0,
                    "staleness_threshold_days": threshold_days,
                    "duplicate_timestamps": duplicate_count,
                    "non_numeric_values": non_numeric_count,
                    "contract_passed": contract_passed,
                    "contract_issues": contract_issues,
                }
            )
            continue

        tail = clean[clean.index >= (as_of - pd.Timedelta(days=lookback_days - 1))]
        rows.append(
            {
                "source": source_name,
                "available": True,
                "latest_timestamp": clean.index.max(),
                "staleness_days": _safe_float(series_staleness_days(clean, as_of=as_of)),
                "coverage_30d": _safe_float(tail.notna().mean() if len(tail) else 0.0),
                "staleness_threshold_days": threshold_days,
                "duplicate_timestamps": duplicate_count,
                "non_numeric_values": non_numeric_count,
                "contract_passed": contract_passed,
                "contract_issues": contract_issues,
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values(["available", "source"], ascending=[False, True]).reset_index(drop=True)


def build_metric_health(
    metric_specs: Iterable[MetricSpec],
    feature_bundles: Iterable[FeatureBundle],
    as_of: pd.Timestamp,
    lookback_days: int = 30,
    metric_source_modes: Dict[str, str] | None = None,
    reliability_adjustments: Dict[str, float] | None = None,
) -> pd.DataFrame:
    bundle_map = {bundle.name: bundle for bundle in feature_bundles}
    metric_source_modes = metric_source_modes or {}
    reliability_adjustments = reliability_adjustments or {}

    rows: List[dict] = []
    for spec in metric_specs:
        bundle_name = f"{spec.name}__{spec.target}__{spec.category}"
        bundle = bundle_map.get(bundle_name)
        source_mode = str(metric_source_modes.get(spec.name, "unknown"))
        mode_multiplier = float(reliability_adjustments.get(spec.name, 1.0))
        adjusted_base = float(np.clip(spec.base_reliability * mode_multiplier, 0.0, 1.0))

        if bundle is None:
            rows.append(
                {
                    "metric": spec.name,
                    "bundle": bundle_name,
                    "category": spec.category,
                    "target": spec.target,
                    "experimental": spec.experimental,
                    "base_reliability": spec.base_reliability,
                    "source_mode": source_mode,
                    "reliability_mode_multiplier": mode_multiplier,
                    "adjusted_base_reliability": adjusted_base,
                    "available": False,
                    "latest_timestamp": pd.NaT,
                    "staleness_days": np.nan,
                    "coverage_30d": 0.0,
                    "reliability_30d": 0.0,
                }
            )
            continue

        frame = bundle.frame
        raw = frame.get("raw", pd.Series(index=frame.index, dtype=float))
        rel = frame.get("reliability", pd.Series(index=frame.index, dtype=float))
        clean = raw.dropna()

        if clean.empty:
            rows.append(
                {
                    "metric": spec.name,
                    "bundle": bundle_name,
                    "category": spec.category,
                    "target": spec.target,
                    "experimental": spec.experimental,
                    "base_reliability": spec.base_reliability,
                    "source_mode": source_mode,
                    "reliability_mode_multiplier": mode_multiplier,
                    "adjusted_base_reliability": adjusted_base,
                    "available": False,
                    "latest_timestamp": pd.NaT,
                    "staleness_days": np.nan,
                    "coverage_30d": 0.0,
                    "reliability_30d": _safe_float(rel.tail(lookback_days).mean()),
                }
            )
            continue

        recent_mask = frame.index >= (as_of - pd.Timedelta(days=lookback_days - 1))
        recent_raw = raw[recent_mask]
        recent_rel = rel[recent_mask]

        rows.append(
            {
                "metric": spec.name,
                "bundle": bundle_name,
                "category": spec.category,
                "target": spec.target,
                "experimental": spec.experimental,
                "base_reliability": spec.base_reliability,
                "source_mode": source_mode,
                "reliability_mode_multiplier": mode_multiplier,
                "adjusted_base_reliability": adjusted_base,
                "available": True,
                "latest_timestamp": clean.index.max(),
                "staleness_days": _safe_float(series_staleness_days(clean, as_of=as_of)),
                "coverage_30d": _safe_float(recent_raw.notna().mean() if len(recent_raw) else 0.0),
                "reliability_30d": _safe_float(recent_rel.mean() if len(recent_rel) else 0.0),
            }
        )

    health = pd.DataFrame(rows)
    if health.empty:
        return health

    return health.sort_values(["available", "category", "target", "metric"], ascending=[False, True, True, True]).reset_index(drop=True)
