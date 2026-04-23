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


def build_source_health(source_map: Dict[str, pd.Series], as_of: pd.Timestamp, lookback_days: int = 30) -> pd.DataFrame:
    rows: List[dict] = []

    for source_name, series in source_map.items():
        clean = series.dropna() if series is not None else pd.Series(dtype=float)
        if clean.empty:
            rows.append(
                {
                    "source": source_name,
                    "available": False,
                    "latest_timestamp": pd.NaT,
                    "staleness_days": np.nan,
                    "coverage_30d": 0.0,
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
) -> pd.DataFrame:
    bundle_map = {bundle.name: bundle for bundle in feature_bundles}

    rows: List[dict] = []
    for spec in metric_specs:
        bundle_name = f"{spec.name}__{spec.target}__{spec.category}"
        bundle = bundle_map.get(bundle_name)

        if bundle is None:
            rows.append(
                {
                    "metric": spec.name,
                    "bundle": bundle_name,
                    "category": spec.category,
                    "target": spec.target,
                    "experimental": spec.experimental,
                    "base_reliability": spec.base_reliability,
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
