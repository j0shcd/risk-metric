from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from risk_engine.benchmark import _auc, _future_max_return, _future_min_return, _future_return, _pr_auc

from .config import EvaluationConfig


@dataclass(frozen=True)
class WalkForwardBenchmarkResult:
    by_fold: pd.DataFrame
    by_label: pd.DataFrame
    by_signal: pd.DataFrame
    embargo_audit: pd.DataFrame
    config: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)


def _month_end_series(series: pd.Series) -> pd.Series:
    clean = series.astype(float).dropna().sort_index()
    if clean.empty:
        return clean
    if not isinstance(clean.index, pd.DatetimeIndex):
        raise ValueError("walk-forward benchmark requires a DatetimeIndex")
    return clean.resample("ME").last().dropna()


def _expanding_quantile_labels(
    monthly_price: pd.Series,
    *,
    horizon: int,
    quantile: float,
    side: str,
    min_history_months: int,
) -> tuple[pd.Series, pd.Series]:
    fwd = _future_return(monthly_price, horizon)
    labels = pd.Series(np.nan, index=monthly_price.index, dtype=float)
    cuts = pd.Series(np.nan, index=monthly_price.index, dtype=float)
    q = float(quantile)

    for i, date in enumerate(monthly_price.index):
        train_end = i - int(horizon)
        if train_end < int(min_history_months):
            continue
        history = fwd.iloc[:train_end].dropna()
        if len(history) < int(min_history_months):
            continue
        current = fwd.iloc[i]
        if not np.isfinite(current):
            continue
        if side == "top":
            cut = float(history.quantile(q))
            labels.iloc[i] = float(current <= cut)
        else:
            cut = float(history.quantile(1.0 - q))
            labels.iloc[i] = float(current >= cut)
        cuts.iloc[i] = cut

    return labels, cuts


def _build_walkforward_labels(
    monthly_price: pd.Series,
    config: EvaluationConfig,
) -> List[Dict[str, Any]]:
    labels: List[Dict[str, Any]] = []
    horizons = [12] if config.smoke_mode else [6, 12, 24, 36]
    quantiles = [0.20] if config.smoke_mode else [0.15, 0.20, 0.25]
    min_history = 36 if config.smoke_mode else 60

    for horizon in horizons:
        fwd_min = _future_min_return(monthly_price, horizon)
        fwd_max = _future_max_return(monthly_price, horizon)
        for drawdown in [0.30, 0.40, 0.50]:
            series = (fwd_min <= (-1.0 * float(drawdown))).astype(float).where(fwd_min.notna(), np.nan)
            labels.append(
                {
                    "label_id": f"wf_threshold_top_dd{int(round(drawdown * 100))}_h{horizon}",
                    "family": "threshold",
                    "side": "top",
                    "horizon_months": int(horizon),
                    "params": f"drawdown={drawdown:.2f}",
                    "label": series,
                    "cut": pd.Series(float(drawdown), index=monthly_price.index, dtype=float),
                    "label_method": "fixed_threshold",
                }
            )
        for rally in [0.50, 0.80, 1.20]:
            series = (fwd_max >= float(rally)).astype(float).where(fwd_max.notna(), np.nan)
            labels.append(
                {
                    "label_id": f"wf_threshold_bottom_up{int(round(rally * 100))}_h{horizon}",
                    "family": "threshold",
                    "side": "bottom",
                    "horizon_months": int(horizon),
                    "params": f"rally={rally:.2f}",
                    "label": series,
                    "cut": pd.Series(float(rally), index=monthly_price.index, dtype=float),
                    "label_method": "fixed_threshold",
                }
            )
        for quantile in quantiles:
            top, top_cut = _expanding_quantile_labels(
                monthly_price,
                horizon=horizon,
                quantile=quantile,
                side="top",
                min_history_months=min_history,
            )
            labels.append(
                {
                    "label_id": f"wf_quantile_top_q{int(round(quantile * 100))}_h{horizon}",
                    "family": "walkforward_quantile",
                    "side": "top",
                    "horizon_months": int(horizon),
                    "params": f"q={quantile:.2f},min_history={min_history},embargo={horizon}",
                    "label": top,
                    "cut": top_cut,
                    "label_method": "expanding_embargoed_quantile",
                }
            )
            bottom, bottom_cut = _expanding_quantile_labels(
                monthly_price,
                horizon=horizon,
                quantile=quantile,
                side="bottom",
                min_history_months=min_history,
            )
            labels.append(
                {
                    "label_id": f"wf_quantile_bottom_q{int(round((1.0 - quantile) * 100))}_h{horizon}",
                    "family": "walkforward_quantile",
                    "side": "bottom",
                    "horizon_months": int(horizon),
                    "params": f"q={1.0 - quantile:.2f},min_history={min_history},embargo={horizon}",
                    "label": bottom,
                    "cut": bottom_cut,
                    "label_method": "expanding_embargoed_quantile",
                }
            )
    return labels


def _expanding_alerts(
    scores: pd.Series,
    *,
    alert_rate: float,
    min_history_months: int,
) -> tuple[pd.Series, pd.Series]:
    alerts = pd.Series(np.nan, index=scores.index, dtype=float)
    thresholds = pd.Series(np.nan, index=scores.index, dtype=float)
    rate = max(0.0, min(1.0, float(alert_rate)))
    for i in range(len(scores)):
        history = scores.iloc[:i].dropna()
        current = scores.iloc[i]
        if len(history) < int(min_history_months) or not np.isfinite(current):
            continue
        threshold = float(history.quantile(1.0 - rate))
        thresholds.iloc[i] = threshold
        alerts.iloc[i] = float(current >= threshold)
    return alerts, thresholds


def _binary_alert_metrics(alerts: pd.Series, labels: pd.Series) -> Dict[str, float]:
    frame = pd.DataFrame({"alert": alerts, "label": labels}).dropna()
    if frame.empty:
        return {
            "alert_precision": float("nan"),
            "alert_recall": float("nan"),
            "false_alarm_rate": float("nan"),
            "alert_rate_realized": float("nan"),
        }
    pred = frame["alert"].astype(int) == 1
    y = frame["label"].astype(int) == 1
    tp = int((pred & y).sum())
    fp = int((pred & ~y).sum())
    fn = int((~pred & y).sum())
    precision = float(tp / (tp + fp)) if (tp + fp) else float("nan")
    recall = float(tp / (tp + fn)) if (tp + fn) else float("nan")
    false_alarm_rate = float(fp / (tp + fp)) if (tp + fp) else float("nan")
    return {
        "alert_precision": precision,
        "alert_recall": recall,
        "false_alarm_rate": false_alarm_rate,
        "alert_rate_realized": float(pred.mean()),
    }


def evaluate_walkforward_benchmark(series: pd.DataFrame, config: EvaluationConfig) -> WalkForwardBenchmarkResult:
    if "btc_price" not in series.columns:
        return WalkForwardBenchmarkResult(
            by_fold=pd.DataFrame(),
            by_label=pd.DataFrame(),
            by_signal=pd.DataFrame(),
            embargo_audit=pd.DataFrame(),
            config={"enabled": False},
            warnings=["walkforward_benchmark_unavailable:missing_btc_price"],
        )

    monthly_price = _month_end_series(series["btc_price"])
    if monthly_price.empty:
        return WalkForwardBenchmarkResult(
            by_fold=pd.DataFrame(),
            by_label=pd.DataFrame(),
            by_signal=pd.DataFrame(),
            embargo_audit=pd.DataFrame(),
            config={"enabled": False},
            warnings=["walkforward_benchmark_unavailable:empty_price"],
        )

    signal_names = [metric.name for metric in config.metrics if metric.name in series.columns]
    signal_confirmatory = {
        metric.name: bool(metric.confirmatory)
        for metric in config.metrics
        if metric.name in series.columns
    }
    hypothesis_lookup = {
        (item.signal, item.label_id): item for item in config.registered_hypotheses
    }
    monthly_signals = {
        name: _month_end_series(series[name]).reindex(monthly_price.index)
        for name in signal_names
    }
    if not monthly_signals:
        return WalkForwardBenchmarkResult(
            by_fold=pd.DataFrame(),
            by_label=pd.DataFrame(),
            by_signal=pd.DataFrame(),
            embargo_audit=pd.DataFrame(),
            config={"enabled": False},
            warnings=["walkforward_benchmark_unavailable:no_signals"],
        )

    min_history = 36 if config.smoke_mode else 60
    labels = _build_walkforward_labels(monthly_price, config)
    rows: List[Dict[str, Any]] = []
    fold_rows: List[Dict[str, Any]] = []
    audit_rows: List[Dict[str, Any]] = []
    for label_def in labels:
        y = label_def["label"].reindex(monthly_price.index)
        cuts = label_def["cut"].reindex(monthly_price.index)
        horizon = int(label_def["horizon_months"])
        for signal_name, scores in monthly_signals.items():
            hypothesis = hypothesis_lookup.get((signal_name, str(label_def["label_id"])))
            confirmatory = bool(signal_confirmatory.get(signal_name, True)) and hypothesis is not None
            evidence_tier = "registered" if hypothesis is not None else "exploratory"
            expected_direction = (
                hypothesis.expected_direction if hypothesis is not None else "unspecified"
            )
            evaluated_scores = 1.0 - scores if expected_direction == "lower_score_more_events" else scores
            alerts, alert_thresholds = _expanding_alerts(
                evaluated_scores, alert_rate=0.20, min_history_months=min_history
            )
            metrics = _binary_alert_metrics(alerts, y)
            pair_frame = pd.DataFrame(
                {
                    "score": evaluated_scores,
                    "raw_score": scores,
                    "label": y,
                    "label_cut": cuts,
                    "alert": alerts,
                    "alert_threshold": alert_thresholds,
                },
                index=monthly_price.index,
            )
            paired = pair_frame[["score", "label"]].dropna()
            resolved = paired["label"]
            for i, (decision_date, audit_row) in enumerate(pair_frame.iterrows()):
                label_value = audit_row["label"]
                if not np.isfinite(label_value):
                    continue
                label_train_end_pos = i - horizon - 1
                score_train_end_pos = i - 1
                label_train_end = monthly_price.index[label_train_end_pos] if label_train_end_pos >= 0 else pd.NaT
                score_train_end = monthly_price.index[score_train_end_pos] if score_train_end_pos >= 0 else pd.NaT
                train_start = monthly_price.index[0] if len(monthly_price.index) else pd.NaT
                embargo_start_pos = max(label_train_end_pos + 1, 0)
                embargo_start = monthly_price.index[embargo_start_pos] if embargo_start_pos < len(monthly_price.index) else pd.NaT
                train_label_count = int(y.iloc[: label_train_end_pos + 1].dropna().shape[0]) if label_train_end_pos >= 0 else 0
                train_score_count = int(scores.iloc[:i].dropna().shape[0])
                embargo_ok = bool(label_def["label_method"] == "fixed_threshold" or (pd.notna(label_train_end) and label_train_end < decision_date))
                threshold_available = bool(np.isfinite(audit_row["alert_threshold"]))
                threshold_uses_prior_scores = bool(
                    not threshold_available or (pd.notna(score_train_end) and score_train_end < decision_date)
                )
                outcome_end_pos = i + horizon
                outcome_end = monthly_price.index[outcome_end_pos] if outcome_end_pos < len(monthly_price.index) else pd.NaT
                fold_rows.append(
                    {
                        "fold_id": f"{label_def['label_id']}::{signal_name}::{pd.Timestamp(decision_date).date().isoformat()}",
                        "window": "walkforward",
                        "signal": signal_name,
                        "confirmatory": confirmatory,
                        "evidence_tier": evidence_tier,
                        "hypothesis_id": hypothesis.hypothesis_id if hypothesis is not None else "",
                        "expected_direction": expected_direction,
                        "label_id": label_def["label_id"],
                        "family": label_def["family"],
                        "side": label_def["side"],
                        "horizon_months": horizon,
                        "decision_date": decision_date,
                        "score_date": decision_date,
                        "outcome_start_date": monthly_price.index[i + 1] if (i + 1) < len(monthly_price.index) else pd.NaT,
                        "outcome_end_date": outcome_end,
                        "outcome_resolved_at_date": outcome_end,
                        "train_start": train_start,
                        "label_train_end": label_train_end,
                        "score_train_end": score_train_end,
                        "test_start": decision_date,
                        "test_end": decision_date,
                        "embargo_start": embargo_start,
                        "embargo_months": horizon,
                        "min_history_months": int(min_history),
                        "label_method": label_def["label_method"],
                        "threshold_method": "expanding_score_quantile",
                        "label_cut": audit_row["label_cut"],
                        "selected_alert_threshold": audit_row["alert_threshold"],
                        "train_label_count": train_label_count,
                        "train_score_count": train_score_count,
                        "score_value": audit_row["score"],
                        "raw_score_value": audit_row["raw_score"],
                        "test_label": label_value,
                        "test_alert": audit_row["alert"],
                        "is_label_resolved": bool(np.isfinite(label_value)),
                        "is_score_available": bool(np.isfinite(audit_row["score"])),
                        "is_alert_threshold_available": threshold_available,
                        "is_evaluable_alert_row": bool(
                            np.isfinite(label_value) and np.isfinite(audit_row["score"]) and threshold_available
                        ),
                        "uses_full_sample_quantile": False,
                        "uses_same_window_threshold_selection": False,
                        "score_threshold_uses_only_prior_scores": threshold_uses_prior_scores,
                        "embargo_boundary_ok": embargo_ok,
                    }
                )
                audit_rows.append(
                    {
                        "fold_id": f"{label_def['label_id']}::{signal_name}::{pd.Timestamp(decision_date).date().isoformat()}",
                        "signal": signal_name,
                        "confirmatory": confirmatory,
                        "evidence_tier": evidence_tier,
                        "hypothesis_id": hypothesis.hypothesis_id if hypothesis is not None else "",
                        "expected_direction": expected_direction,
                        "label_id": label_def["label_id"],
                        "decision_date": decision_date,
                        "label_train_end": label_train_end,
                        "score_train_end": score_train_end,
                        "test_start": decision_date,
                        "embargo_months": horizon,
                        "label_training_uses_only_resolved_outcomes": embargo_ok,
                        "score_threshold_uses_only_prior_scores": threshold_uses_prior_scores,
                        "threshold_available": threshold_available,
                        "uses_full_sample_quantile": False,
                        "uses_same_window_threshold_selection": False,
                    }
                )
            rows.append(
                {
                    "window": "walkforward",
                    "signal": signal_name,
                    "confirmatory": confirmatory,
                    "evidence_tier": evidence_tier,
                    "hypothesis_id": hypothesis.hypothesis_id if hypothesis is not None else "",
                    "expected_direction": expected_direction,
                    "primary_statistic": hypothesis.primary_statistic if hypothesis is not None else "",
                    "endpoint": hypothesis.endpoint if hypothesis is not None else "",
                    "label_id": label_def["label_id"],
                    "family": label_def["family"],
                    "side": label_def["side"],
                    "horizon_months": int(label_def["horizon_months"]),
                    "params": label_def["params"],
                    "label_method": label_def["label_method"],
                    "threshold_method": "expanding_score_quantile",
                    "embargo_months": int(label_def["horizon_months"]),
                    "min_history_months": int(min_history),
                    "n_obs": int(resolved.shape[0]),
                    "n_events": int((resolved.astype(int) == 1).sum()) if not resolved.empty else 0,
                    "n_non_events": int((resolved.astype(int) == 0).sum()) if not resolved.empty else 0,
                    "auc": _auc(evaluated_scores, y),
                    "pr_auc": _pr_auc(evaluated_scores, y),
                    **metrics,
                }
            )

    by_label = pd.DataFrame(rows)
    if by_label.empty:
        return WalkForwardBenchmarkResult(
            by_fold=pd.DataFrame(fold_rows),
            by_label=by_label,
            by_signal=pd.DataFrame(),
            embargo_audit=pd.DataFrame(audit_rows),
            config={"enabled": True},
            warnings=["walkforward_benchmark_unavailable:no_rows"],
        )

    by_label["effective_observations"] = np.floor(
        pd.to_numeric(by_label["n_obs"], errors="coerce")
        / pd.to_numeric(by_label["horizon_months"], errors="coerce").clip(lower=1)
    )
    by_label["min_events_required"] = np.where(
        pd.to_numeric(by_label["horizon_months"], errors="coerce") <= 24,
        int(config.claim_gates.min_events_short_medium),
        int(config.claim_gates.min_events_long),
    )
    by_label["min_effective_obs_required"] = np.where(
        pd.to_numeric(by_label["horizon_months"], errors="coerce") <= 24,
        int(config.claim_gates.min_effective_obs_short_medium),
        int(config.claim_gates.min_effective_obs_long),
    )
    by_label["eligible_for_aggregate"] = (
        (pd.to_numeric(by_label["n_events"], errors="coerce") >= 3)
        & (pd.to_numeric(by_label["n_non_events"], errors="coerce") >= 3)
    )
    by_label["passes_sample_gate"] = (
        (pd.to_numeric(by_label["n_events"], errors="coerce") >= by_label["min_events_required"])
        & (pd.to_numeric(by_label["n_non_events"], errors="coerce") >= by_label["min_events_required"])
        & (pd.to_numeric(by_label["effective_observations"], errors="coerce") >= by_label["min_effective_obs_required"])
    )
    by_label["eligible_for_promotion"] = (
        by_label["evidence_tier"].astype(str).eq("registered")
        & by_label["passes_sample_gate"].fillna(False)
        & by_label["eligible_for_aggregate"].fillna(False)
    )
    by_label["eligibility_reason"] = "eligible"
    by_label.loc[
        pd.to_numeric(by_label["n_events"], errors="coerce") < 3,
        "eligibility_reason",
    ] = "insufficient_events"
    by_label.loc[
        (pd.to_numeric(by_label["n_events"], errors="coerce") >= 3)
        & (pd.to_numeric(by_label["n_non_events"], errors="coerce") < 3),
        "eligibility_reason",
    ] = "insufficient_non_events"
    by_label.loc[
        by_label["eligible_for_aggregate"].fillna(False)
        & ~by_label["passes_sample_gate"].fillna(False),
        "eligibility_reason",
    ] = "aggregate_only_below_claim_sample_gate"

    aggregate = by_label[
        by_label["evidence_tier"].astype(str).eq("registered")
        & by_label["eligible_for_aggregate"].fillna(False)
    ].copy()
    by_signal_rows: List[Dict[str, Any]] = []
    for signal, group in aggregate.groupby("signal", dropna=False):
        by_signal_rows.append(
            {
                "window": "walkforward",
                "signal": signal,
                "confirmatory": bool(group["confirmatory"].fillna(True).astype(bool).all())
                if "confirmatory" in group.columns
                else True,
                "evidence_tier": "registered",
                "eligible_for_promotion": bool(group["eligible_for_promotion"].fillna(False).all()),
                "eligible_label_count": int(len(group)),
                "effective_label_count": int(len(group)),
                "effective_weight_sum": float(len(group)),
                "mean_auc": float(group["auc"].mean(skipna=True)),
                "mean_pr_auc": float(group["pr_auc"].mean(skipna=True)),
                "mean_alert_recall": float(group["alert_recall"].mean(skipna=True)),
                "mean_false_alarm_rate": float(group["false_alarm_rate"].mean(skipna=True)),
                "aggregation_method": "unweighted_walkforward_eligible_labels_v1",
            }
        )
    by_signal = pd.DataFrame(by_signal_rows).sort_values("signal").reset_index(drop=True) if by_signal_rows else pd.DataFrame()
    by_fold = pd.DataFrame(fold_rows)
    if not by_fold.empty:
        by_fold = by_fold.sort_values(["signal", "label_id", "decision_date"]).reset_index(drop=True)
    embargo_audit = pd.DataFrame(audit_rows)
    if not embargo_audit.empty:
        embargo_audit = embargo_audit.sort_values(["signal", "label_id", "decision_date"]).reset_index(drop=True)

    return WalkForwardBenchmarkResult(
        by_fold=by_fold,
        by_label=by_label.sort_values(["signal", "label_id"]).reset_index(drop=True),
        by_signal=by_signal,
        embargo_audit=embargo_audit,
        config={
            "enabled": True,
            "profile": config.profile,
            "alert_rate": 0.20,
            "min_history_months": int(min_history),
            "quantile_label_method": "expanding_embargoed_quantile",
            "threshold_method": "expanding_score_quantile",
        },
        warnings=[],
    )
