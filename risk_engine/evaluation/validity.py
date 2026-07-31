from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from risk_engine.benchmark import _auc, _pr_auc

from .config import EvaluationConfig


@dataclass(frozen=True)
class ValidityDiagnosticsResult:
    label_audit: pd.DataFrame
    shift_probe: pd.DataFrame
    synthetic_sentinels: pd.DataFrame
    by_label: pd.DataFrame
    config: Dict[str, Any]
    warnings: List[str]


LABEL_AUDIT_COLUMNS = [
    "signal",
    "confirmatory",
    "label_id",
    "family",
    "side",
    "horizon_months",
    "n_obs",
    "n_events",
    "n_non_events",
    "event_rate",
    "event_cluster_count",
    "largest_event_cluster",
    "largest_event_cluster_share",
    "event_run_count",
    "label_audit_method",
]

SHIFT_PROBE_COLUMNS = [
    "signal",
    "confirmatory",
    "label_id",
    "family",
    "side",
    "horizon_months",
    "probe",
    "score_shift_rows",
    "observed_auc",
    "shifted_auc",
    "auc_delta_vs_observed",
    "leakage_probe_only",
]

SYNTHETIC_SENTINEL_COLUMNS = [
    "signal",
    "confirmatory",
    "label_id",
    "sentinel",
    "auc",
    "pr_auc",
    "n_obs",
    "n_events",
    "synthetic_only",
]


def _empty(columns: List[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _event_clusters(labels: pd.Series) -> int:
    y = pd.to_numeric(labels, errors="coerce").dropna().astype(int)
    if y.empty:
        return 0
    starts = (y == 1) & (y.shift(1, fill_value=0) != 1)
    return int(starts.sum())


def _largest_event_cluster(labels: pd.Series) -> int:
    y = pd.to_numeric(labels, errors="coerce").dropna().astype(int)
    if y.empty or int((y == 1).sum()) == 0:
        return 0
    groups = (y != y.shift(1)).cumsum()
    return int(y[y == 1].groupby(groups[y == 1]).size().max())


def _sentinel_rows(label_id: str, signal: str, labels: pd.Series, seed: int, confirmatory: bool) -> List[Dict[str, Any]]:
    y = pd.to_numeric(labels, errors="coerce").dropna()
    if y.empty:
        return []
    y_int = y.astype(int)
    if int((y_int == 1).sum()) == 0 or int((y_int == 0).sum()) == 0:
        return []
    rng = np.random.default_rng(int(seed))
    random_scores = pd.Series(rng.uniform(0.0, 1.0, size=len(y)), index=y.index)
    perfect = y.astype(float)
    inverted = 1.0 - perfect
    rows = []
    for name, scores in (
        ("perfect_label_sentinel", perfect),
        ("inverted_label_sentinel", inverted),
        ("random_uniform_sentinel", random_scores),
    ):
        rows.append(
            {
                "signal": signal,
                "confirmatory": confirmatory,
                "label_id": label_id,
                "sentinel": name,
                "auc": _auc(scores, y),
                "pr_auc": _pr_auc(scores, y),
                "n_obs": int(y.shape[0]),
                "n_events": int((y.astype(int) == 1).sum()),
                "synthetic_only": True,
            }
        )
    return rows


def evaluate_validity_diagnostics(
    by_fold: pd.DataFrame,
    by_label: pd.DataFrame,
    config: EvaluationConfig,
) -> ValidityDiagnosticsResult:
    if by_fold.empty or by_label.empty:
        return ValidityDiagnosticsResult(
            label_audit=_empty(LABEL_AUDIT_COLUMNS),
            shift_probe=_empty(SHIFT_PROBE_COLUMNS),
            synthetic_sentinels=_empty(SYNTHETIC_SENTINEL_COLUMNS),
            by_label=by_label.copy(),
            config={"enabled": False},
            warnings=["validity_diagnostics_unavailable:missing_walkforward_inputs"],
        )

    required = {"signal", "label_id", "decision_date", "score_value", "test_label", "horizon_months"}
    missing = sorted(required - set(by_fold.columns))
    if missing:
        return ValidityDiagnosticsResult(
            label_audit=_empty(LABEL_AUDIT_COLUMNS),
            shift_probe=_empty(SHIFT_PROBE_COLUMNS),
            synthetic_sentinels=_empty(SYNTHETIC_SENTINEL_COLUMNS),
            by_label=by_label.copy(),
            config={"enabled": False, "missing_columns": missing},
            warnings=["validity_diagnostics_unavailable:missing_columns"],
        )

    label_rows: List[Dict[str, Any]] = []
    shift_rows: List[Dict[str, Any]] = []
    sentinel_rows: List[Dict[str, Any]] = []
    summary_rows: List[Dict[str, Any]] = []

    for (signal, label_id), group in by_fold.groupby(["signal", "label_id"], dropna=False):
        ordered = group.sort_values("decision_date").reset_index(drop=True)
        labels = pd.to_numeric(ordered["test_label"], errors="coerce")
        scores = pd.to_numeric(ordered["score_value"], errors="coerce")
        label_frame = pd.DataFrame({"label": labels}).dropna()
        score_frame = pd.DataFrame({"score": scores, "label": labels}).dropna()
        if label_frame.empty:
            continue
        horizon = int(pd.to_numeric(ordered["horizon_months"], errors="coerce").dropna().iloc[0])
        family = str(ordered.get("family", pd.Series([""])).iloc[0])
        side = str(ordered.get("side", pd.Series([""])).iloc[0])
        confirmatory = bool(ordered.get("confirmatory", pd.Series([True])).fillna(True).astype(bool).iloc[0])
        n_events = int((label_frame["label"].astype(int) == 1).sum())
        clusters = _event_clusters(label_frame["label"])
        largest_cluster = _largest_event_cluster(label_frame["label"])
        event_rate = float(label_frame["label"].mean())
        label_rows.append(
            {
                "signal": signal,
                "confirmatory": confirmatory,
                "label_id": label_id,
                "family": family,
                "side": side,
                "horizon_months": horizon,
                "n_obs": int(label_frame.shape[0]),
                "n_events": n_events,
                "n_non_events": int((label_frame["label"].astype(int) == 0).sum()),
                "event_rate": event_rate,
                "event_cluster_count": clusters,
                "largest_event_cluster": largest_cluster,
                "largest_event_cluster_share": float(largest_cluster / n_events) if n_events else np.nan,
                "event_run_count": clusters,
                "label_audit_method": "walkforward_fold_event_cluster_scan",
            }
        )

        if score_frame.empty:
            continue

        observed_auc = _auc(score_frame["score"], score_frame["label"])
        probe_values: Dict[str, float] = {}
        for shift_name, shift in (
            ("past_score_one_horizon", horizon),
            ("past_score_one_month", 1),
            ("future_score_one_month", -1),
            ("future_score_one_horizon", -horizon),
        ):
            shifted = scores.shift(shift).reindex(score_frame.index)
            auc = _auc(shifted, score_frame["label"])
            probe_values[f"{shift_name}_auc"] = auc
            shift_rows.append(
                {
                    "signal": signal,
                    "confirmatory": confirmatory,
                    "label_id": label_id,
                    "family": family,
                    "side": side,
                    "horizon_months": horizon,
                    "probe": shift_name,
                    "score_shift_rows": int(shift),
                    "observed_auc": observed_auc,
                    "shifted_auc": auc,
                    "auc_delta_vs_observed": float(auc - observed_auc)
                    if np.isfinite(auc) and np.isfinite(observed_auc)
                    else np.nan,
                    "leakage_probe_only": True,
                }
            )

        sentinel_rows.extend(
            _sentinel_rows(
                str(label_id),
                str(signal),
                label_frame["label"],
                seed=int(config.seed) + len(sentinel_rows) + 1009,
                confirmatory=confirmatory,
            )
        )
        future_best = max(
            [
                value
                for key, value in probe_values.items()
                if key.startswith("future") and np.isfinite(value)
            ]
            or [np.nan]
        )
        future_auc_advantage = (
            float(future_best - observed_auc) if np.isfinite(future_best) and np.isfinite(observed_auc) else np.nan
        )
        summary_rows.append(
            {
                "signal": signal,
                "confirmatory": confirmatory,
                "label_id": label_id,
                "event_cluster_count": clusters,
                "event_run_count": clusters,
                "future_shift_best_auc": future_best,
                "future_shift_auc_advantage": future_auc_advantage,
                "passes_shift_leakage_probe": bool(
                    not np.isfinite(future_auc_advantage) or future_auc_advantage <= 0.15
                ),
                "passes_label_cluster_gate": bool(clusters >= 2 and (n_events == 0 or largest_cluster / max(n_events, 1) <= 0.80)),
            }
        )

    label_audit = pd.DataFrame(label_rows, columns=LABEL_AUDIT_COLUMNS)
    shift_probe = pd.DataFrame(shift_rows, columns=SHIFT_PROBE_COLUMNS)
    sentinels = pd.DataFrame(sentinel_rows, columns=SYNTHETIC_SENTINEL_COLUMNS)
    summary = pd.DataFrame(summary_rows)
    enriched = by_label.copy()
    if not summary.empty:
        enriched = enriched.merge(
            summary.drop(columns=["confirmatory"], errors="ignore"),
            how="left",
            on=["signal", "label_id"],
        )

    warnings: List[str] = []
    if label_audit.empty:
        warnings.append("label_audit_unavailable:no_rows")
    if shift_probe.empty:
        warnings.append("shift_probe_unavailable:no_rows")
    if sentinels.empty:
        warnings.append("synthetic_sentinels_unavailable:no_rows")
    return ValidityDiagnosticsResult(
        label_audit=label_audit.sort_values(["signal", "label_id"]).reset_index(drop=True)
        if not label_audit.empty
        else label_audit,
        shift_probe=shift_probe.sort_values(["signal", "label_id", "probe"]).reset_index(drop=True)
        if not shift_probe.empty
        else shift_probe,
        synthetic_sentinels=sentinels.sort_values(["signal", "label_id", "sentinel"]).reset_index(drop=True)
        if not sentinels.empty
        else sentinels,
        by_label=enriched.sort_values(["signal", "label_id"]).reset_index(drop=True),
        config={
            "enabled": True,
            "shift_probe_advantage_warn_threshold": 0.15,
            "label_cluster_method": "consecutive_event_runs",
            "synthetic_sentinels_increase_confidence": False,
        },
        warnings=warnings,
    )
