from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .config import EvaluationConfig


@dataclass(frozen=True)
class AcademicDiagnosticsResult:
    reliability_bins: pd.DataFrame
    monotonicity: pd.DataFrame
    by_label: pd.DataFrame
    config: Dict[str, Any]
    warnings: List[str]


RELIABILITY_BIN_COLUMNS = [
    "signal",
    "confirmatory",
    "label_id",
    "family",
    "side",
    "horizon_months",
    "bin_method",
    "score_bin",
    "n_obs",
    "n_events",
    "event_rate",
    "event_rate_ci_low",
    "event_rate_ci_high",
    "mean_score",
    "min_score",
    "max_score",
    "low_bin_count_warning",
]

MONOTONICITY_COLUMNS = [
    "signal",
    "confirmatory",
    "label_id",
    "family",
    "side",
    "horizon_months",
    "spearman_score_label",
    "bin_count",
    "min_bin_obs",
    "nondecreasing_event_rate_share",
    "passes_monotonicity_gate",
    "monotonicity_method",
    "calibration_scope",
]


def _empty(columns: List[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _spearman(x: pd.Series, y: pd.Series) -> float:
    frame = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"), "y": pd.to_numeric(y, errors="coerce")}).dropna()
    if frame.shape[0] < 3 or frame["x"].nunique() < 2 or frame["y"].nunique() < 2:
        return float("nan")
    return float(frame["x"].rank(method="average").corr(frame["y"].rank(method="average")))


def _safe_qcut(values: pd.Series, bins: int) -> pd.Series:
    ranked = pd.to_numeric(values, errors="coerce").rank(method="first")
    if ranked.dropna().nunique() < 2:
        return pd.Series(np.nan, index=values.index, dtype=float)
    try:
        return pd.qcut(ranked, q=int(bins), labels=False, duplicates="drop").astype(float)
    except ValueError:
        return pd.Series(np.nan, index=values.index, dtype=float)


def _monotonic_direction(event_rates: pd.Series) -> tuple[float, bool]:
    clean = pd.to_numeric(event_rates, errors="coerce").dropna()
    if clean.shape[0] < 3:
        return float("nan"), False
    diffs = clean.diff().dropna()
    nondecreasing_share = float((diffs >= -1e-12).mean()) if not diffs.empty else float("nan")
    return nondecreasing_share, bool(np.isfinite(nondecreasing_share) and nondecreasing_share >= 0.75)


def evaluate_academic_diagnostics(
    by_fold: pd.DataFrame,
    by_label: pd.DataFrame,
    config: EvaluationConfig,
) -> AcademicDiagnosticsResult:
    if by_fold.empty or by_label.empty:
        return AcademicDiagnosticsResult(
            reliability_bins=_empty(RELIABILITY_BIN_COLUMNS),
            monotonicity=_empty(MONOTONICITY_COLUMNS),
            by_label=by_label.copy(),
            config={"enabled": False},
            warnings=["academic_diagnostics_unavailable:missing_walkforward_inputs"],
        )

    required = {"signal", "label_id", "decision_date", "score_value", "test_label", "horizon_months"}
    missing = sorted(required - set(by_fold.columns))
    if missing:
        return AcademicDiagnosticsResult(
            reliability_bins=_empty(RELIABILITY_BIN_COLUMNS),
            monotonicity=_empty(MONOTONICITY_COLUMNS),
            by_label=by_label.copy(),
            config={"enabled": False, "missing_columns": missing},
            warnings=["academic_diagnostics_unavailable:missing_columns"],
        )

    bin_count = 5 if config.smoke_mode else 10
    min_bin_obs = 3 if config.smoke_mode else 10
    bin_rows: List[Dict[str, Any]] = []
    monotonic_rows: List[Dict[str, Any]] = []

    for (signal, label_id), group in by_fold.groupby(["signal", "label_id"], dropna=False):
        ordered = group.sort_values("decision_date").copy()
        frame = pd.DataFrame(
            {
                "score": pd.to_numeric(ordered["score_value"], errors="coerce"),
                "label": pd.to_numeric(ordered["test_label"], errors="coerce"),
            },
            index=ordered.index,
        ).dropna()
        if frame.empty:
            continue

        bins = _safe_qcut(frame["score"], bin_count)
        frame = frame.assign(score_bin=bins.reindex(frame.index))
        family = str(ordered.get("family", pd.Series([""])).iloc[0])
        side = str(ordered.get("side", pd.Series([""])).iloc[0])
        confirmatory = bool(ordered.get("confirmatory", pd.Series([True])).fillna(True).astype(bool).iloc[0])
        horizon = int(pd.to_numeric(ordered["horizon_months"], errors="coerce").dropna().iloc[0])

        grouped = (
            frame.dropna(subset=["score_bin"])
            .groupby("score_bin", dropna=False)
            .agg(
                n_obs=("label", "count"),
                n_events=("label", "sum"),
                event_rate=("label", "mean"),
                mean_score=("score", "mean"),
                min_score=("score", "min"),
                max_score=("score", "max"),
            )
            .reset_index()
            .sort_values("score_bin")
        )
        for _, row in grouped.iterrows():
            n_obs = int(row["n_obs"])
            event_rate = float(row["event_rate"]) if np.isfinite(row["event_rate"]) else float("nan")
            se = np.sqrt(event_rate * (1.0 - event_rate) / n_obs) if n_obs > 0 and np.isfinite(event_rate) else np.nan
            bin_rows.append(
                {
                    "signal": signal,
                    "confirmatory": confirmatory,
                    "label_id": label_id,
                    "family": family,
                    "side": side,
                    "horizon_months": horizon,
                    "bin_method": f"score_quantile_{bin_count}",
                    "score_bin": int(row["score_bin"]) if np.isfinite(row["score_bin"]) else -1,
                    "n_obs": n_obs,
                    "n_events": int(row["n_events"]),
                    "event_rate": event_rate,
                    "event_rate_ci_low": float(max(0.0, event_rate - 1.96 * se)) if np.isfinite(se) else np.nan,
                    "event_rate_ci_high": float(min(1.0, event_rate + 1.96 * se)) if np.isfinite(se) else np.nan,
                    "mean_score": float(row["mean_score"]),
                    "min_score": float(row["min_score"]),
                    "max_score": float(row["max_score"]),
                    "low_bin_count_warning": bool(n_obs < min_bin_obs),
                }
            )

        min_group_obs = int(grouped["n_obs"].min()) if not grouped.empty else 0
        nondecreasing_share, shape_passes = _monotonic_direction(grouped.get("event_rate", pd.Series(dtype=float)))
        passes_monotonicity = bool(shape_passes and min_group_obs >= min_bin_obs)
        monotonic_rows.append(
            {
                "signal": signal,
                "confirmatory": confirmatory,
                "label_id": label_id,
                "family": family,
                "side": side,
                "horizon_months": horizon,
                "spearman_score_label": _spearman(frame["score"], frame["label"]),
                "bin_count": int(grouped.shape[0]),
                "min_bin_obs": min_group_obs,
                "nondecreasing_event_rate_share": nondecreasing_share,
                "passes_monotonicity_gate": passes_monotonicity,
                "monotonicity_method": f"score_quantile_{bin_count}_event_rate_nondecreasing_share",
                "calibration_scope": "posthoc_walkforward_holdout_quantiles_not_deployable_thresholds",
            }
        )

    reliability_bins = pd.DataFrame(bin_rows, columns=RELIABILITY_BIN_COLUMNS)
    monotonicity = pd.DataFrame(monotonic_rows, columns=MONOTONICITY_COLUMNS)
    enriched = by_label.copy()
    if not monotonicity.empty:
        enriched = enriched.merge(
            monotonicity[
                [
                    "signal",
                    "label_id",
                    "spearman_score_label",
                    "nondecreasing_event_rate_share",
                    "passes_monotonicity_gate",
                ]
            ],
            how="left",
            on=["signal", "label_id"],
        )

    warnings: List[str] = []
    if reliability_bins.empty:
        warnings.append("academic_reliability_bins_unavailable:no_rows")
    if monotonicity.empty:
        warnings.append("academic_monotonicity_unavailable:no_rows")
    return AcademicDiagnosticsResult(
        reliability_bins=reliability_bins.sort_values(["signal", "label_id", "score_bin"]).reset_index(drop=True)
        if not reliability_bins.empty
        else reliability_bins,
        monotonicity=monotonicity.sort_values(["signal", "label_id"]).reset_index(drop=True)
        if not monotonicity.empty
        else monotonicity,
        by_label=enriched.sort_values(["signal", "label_id"]).reset_index(drop=True),
        config={
            "enabled": True,
            "bin_count": int(bin_count),
            "min_bin_obs": int(min_bin_obs),
            "monotonicity_gate": "nondecreasing_event_rate_share>=0.75",
        },
        warnings=warnings,
    )
