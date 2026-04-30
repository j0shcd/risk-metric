from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from .config import RuntimeConfig


@dataclass(frozen=True)
class BenchmarkResult:
    summary: pd.DataFrame
    by_label: pd.DataFrame
    by_signal: pd.DataFrame
    window_stats: pd.DataFrame
    config: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)


def _future_min_return(price: pd.Series, horizon: int) -> pd.Series:
    values = price.astype(float).to_numpy()
    out = np.full(len(values), np.nan, dtype=float)
    for i in range(len(values)):
        stop = i + horizon + 1
        if stop > len(values):
            continue
        base = values[i]
        if not np.isfinite(base) or base == 0.0:
            continue
        future = values[i + 1 : stop]
        if len(future) == 0 or not np.isfinite(future).any():
            continue
        out[i] = float(np.nanmin(future) / base - 1.0)
    return pd.Series(out, index=price.index, dtype=float)


def _future_max_return(price: pd.Series, horizon: int) -> pd.Series:
    values = price.astype(float).to_numpy()
    out = np.full(len(values), np.nan, dtype=float)
    for i in range(len(values)):
        stop = i + horizon + 1
        if stop > len(values):
            continue
        base = values[i]
        if not np.isfinite(base) or base == 0.0:
            continue
        future = values[i + 1 : stop]
        if len(future) == 0 or not np.isfinite(future).any():
            continue
        out[i] = float(np.nanmax(future) / base - 1.0)
    return pd.Series(out, index=price.index, dtype=float)


def _future_return(price: pd.Series, horizon: int) -> pd.Series:
    return price.shift(-horizon) / price - 1.0


def _auc(scores: pd.Series, labels: pd.Series) -> float:
    frame = pd.concat([scores, labels], axis=1).dropna()
    if frame.empty:
        return float("nan")
    y = frame.iloc[:, 1].astype(int)
    x = frame.iloc[:, 0].astype(float)

    n_pos = int((y == 1).sum())
    n_neg = int((y == 0).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")

    ranks = x.rank(method="average")
    rank_sum_pos = float(ranks[y == 1].sum())
    u = rank_sum_pos - (n_pos * (n_pos + 1) / 2.0)
    return float(u / (n_pos * n_neg))


def _pr_auc(scores: pd.Series, labels: pd.Series) -> float:
    frame = pd.DataFrame({"score": scores, "label": labels}).dropna().sort_values(by="score", ascending=False)
    if frame.empty:
        return float("nan")

    y = frame["label"].astype(int).to_numpy()
    n_pos = int((y == 1).sum())
    if n_pos == 0:
        return float("nan")

    tp = np.cumsum(y)
    fp = np.cumsum(1 - y)

    precision = tp / np.maximum(tp + fp, 1)
    recall = tp / n_pos

    precision = np.r_[1.0, precision]
    recall = np.r_[0.0, recall]

    area = np.trapz(precision, recall)
    return float(area)


def _threshold_metrics(scores: pd.Series, labels: pd.Series, threshold: float) -> Tuple[float, float, float]:
    frame = pd.concat([scores, labels], axis=1).dropna()
    if frame.empty:
        return float("nan"), float("nan"), float("nan")

    y = frame.iloc[:, 1].astype(int)
    pred = frame.iloc[:, 0].astype(float) >= float(threshold)

    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())

    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else float("nan")
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else float("nan")
    if np.isnan(precision) or np.isnan(recall) or (precision + recall) == 0:
        f1 = float("nan")
    else:
        f1 = float(2.0 * precision * recall / (precision + recall))
    return precision, recall, f1


def _best_f1_threshold(scores: pd.Series, labels: pd.Series) -> float:
    frame = pd.concat([scores, labels], axis=1).dropna()
    if frame.empty:
        return float("nan")

    unique_scores = np.unique(frame.iloc[:, 0].astype(float).to_numpy())
    if unique_scores.size == 0:
        return float("nan")

    best_threshold = float(unique_scores[0])
    best_f1 = float("-inf")
    for threshold in unique_scores:
        _, _, f1 = _threshold_metrics(frame.iloc[:, 0], frame.iloc[:, 1], float(threshold))
        score = -1.0 if np.isnan(f1) else float(f1)
        if score > best_f1:
            best_f1 = score
            best_threshold = float(threshold)
    return best_threshold


def _lead_time_metrics(
    scores: pd.Series,
    labels: pd.Series,
    *,
    alert_rate: float,
    horizon_months: int,
) -> Tuple[float, float, float, float]:
    frame = pd.concat([scores, labels], axis=1).dropna()
    if frame.empty:
        return float("nan"), float("nan"), float("nan"), float("nan")

    ranked = frame.iloc[:, 0].astype(float)
    threshold = float(ranked.quantile(max(0.0, min(1.0, 1.0 - alert_rate))))
    alerts = ranked >= threshold

    event_index = frame.index[frame.iloc[:, 1].astype(int) == 1]
    n_events = len(event_index)
    if n_events == 0:
        false_alarm_rate = float((alerts.sum() / len(alerts)) if len(alerts) else float("nan"))
        return float("nan"), float("nan"), false_alarm_rate, float("nan")

    hit_count = 0
    lead_months: List[int] = []

    for event_date in event_index:
        start = event_date - pd.DateOffset(months=max(int(horizon_months), 1))
        window = alerts.loc[(alerts.index >= start) & (alerts.index <= event_date)]
        if window.any():
            hit_count += 1
            first_alert = window[window].index[0]
            lead = int((event_date.to_period("M") - first_alert.to_period("M")).n)
            lead_months.append(max(0, lead))

    recall = float(hit_count / n_events)
    median_lead = float(np.median(lead_months)) if lead_months else float("nan")

    false_alerts = 0
    alert_months = int(alerts.sum())
    for alert_date in alerts.index[alerts]:
        future_events = event_index[
            (event_index >= alert_date)
            & (event_index <= alert_date + pd.DateOffset(months=max(int(horizon_months), 1)))
        ]
        if len(future_events) == 0:
            false_alerts += 1

    false_alarm_rate = float(false_alerts / alert_months) if alert_months > 0 else float("nan")
    coverage = recall
    return recall, median_lead, false_alarm_rate, coverage


def _window_view(
    monthly: pd.DataFrame,
    *,
    recent_window_months: int,
) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {"expanding": monthly}
    if recent_window_months > 0:
        out["recent"] = monthly.tail(recent_window_months)
    return out


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    frame = pd.DataFrame({"value": values, "weight": weights}).replace([np.inf, -np.inf], np.nan).dropna()
    if frame.empty:
        return float("nan")
    w = frame["weight"].astype(float).clip(lower=0.0)
    if float(w.sum()) <= 0.0:
        return float("nan")
    return float(np.average(frame["value"].astype(float), weights=w))


def _aggregate_group(group: pd.DataFrame, metrics: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    weights = group["event_weight"].astype(float).clip(lower=0.0) if "event_weight" in group.columns else pd.Series(
        1.0,
        index=group.index,
        dtype=float,
    )
    for metric in metrics:
        out[metric] = _weighted_mean(group[metric], weights)

    primary = pd.DataFrame(
        {
            "value": group.get("lead_recall_at_alert_rate", pd.Series(dtype=float)),
            "weight": weights,
        }
    ).replace([np.inf, -np.inf], np.nan)
    primary = primary.dropna()
    effective_weight_sum = float(primary["weight"].sum()) if not primary.empty else 0.0
    effective_label_count = int((primary["weight"] > 0.0).sum()) if not primary.empty else 0

    out["effective_weight_sum"] = effective_weight_sum
    out["effective_label_count"] = effective_label_count
    out["aggregation_method"] = "soft_event_weighted_v1"
    return out


def _build_labels(cfg: RuntimeConfig, monthly_price: pd.Series) -> List[Dict[str, Any]]:
    labels: List[Dict[str, Any]] = []

    families = {item.strip().lower() for item in cfg.benchmark_label_families}

    if "threshold" in families:
        for horizon in cfg.benchmark_horizons_months:
            fwd_min = _future_min_return(monthly_price, horizon)
            fwd_max = _future_max_return(monthly_price, horizon)

            for drawdown in cfg.benchmark_top_drawdown_thresholds:
                series = (fwd_min <= (-1.0 * float(drawdown))).astype(float)
                series = series.where(fwd_min.notna(), np.nan)
                labels.append(
                    {
                        "label_id": f"threshold_top_dd{int(round(drawdown * 100))}_h{horizon}",
                        "family": "threshold",
                        "side": "top",
                        "horizon_months": int(horizon),
                        "params": f"drawdown={drawdown:.2f}",
                        "series": series,
                    }
                )

            for rally in cfg.benchmark_bottom_rally_thresholds:
                series = (fwd_max >= float(rally)).astype(float)
                series = series.where(fwd_max.notna(), np.nan)
                labels.append(
                    {
                        "label_id": f"threshold_bottom_up{int(round(rally * 100))}_h{horizon}",
                        "family": "threshold",
                        "side": "bottom",
                        "horizon_months": int(horizon),
                        "params": f"rally={rally:.2f}",
                        "series": series,
                    }
                )

    if "quantile" in families:
        for horizon in cfg.benchmark_horizons_months:
            fwd = _future_return(monthly_price, horizon)
            resolved = fwd.dropna()
            for q in cfg.benchmark_quantile_levels:
                qv = float(q)
                if resolved.empty:
                    q_low = np.nan
                    q_high = np.nan
                else:
                    q_low = float(resolved.quantile(qv))
                    q_high = float(resolved.quantile(1.0 - qv))

                top = (fwd <= q_low).astype(float).where(fwd.notna(), np.nan)
                bottom = (fwd >= q_high).astype(float).where(fwd.notna(), np.nan)

                labels.append(
                    {
                        "label_id": f"quantile_top_q{int(round(qv * 100))}_h{horizon}",
                        "family": "quantile",
                        "side": "top",
                        "horizon_months": int(horizon),
                        "params": f"q={qv:.2f},cut={q_low:.6f}" if np.isfinite(q_low) else f"q={qv:.2f},cut=nan",
                        "series": top,
                    }
                )
                labels.append(
                    {
                        "label_id": f"quantile_bottom_q{int(round((1.0 - qv) * 100))}_h{horizon}",
                        "family": "quantile",
                        "side": "bottom",
                        "horizon_months": int(horizon),
                        "params": f"q={1.0 - qv:.2f},cut={q_high:.6f}" if np.isfinite(q_high) else f"q={1.0 - qv:.2f},cut=nan",
                        "series": bottom,
                    }
                )

    if "local_extrema" in families:
        for lookback in cfg.benchmark_local_extrema_lookbacks:
            for forward in cfg.benchmark_local_extrema_forwards:
                past_max = monthly_price.rolling(lookback, min_periods=lookback).max()
                past_min = monthly_price.rolling(lookback, min_periods=lookback).min()
                fwd_min = _future_min_return(monthly_price, forward)
                fwd_max = _future_max_return(monthly_price, forward)

                top = ((monthly_price >= past_max) & (fwd_min <= 0.0)).astype(float)
                top = top.where(past_max.notna() & fwd_min.notna(), np.nan)
                bottom = ((monthly_price <= past_min) & (fwd_max >= 0.0)).astype(float)
                bottom = bottom.where(past_min.notna() & fwd_max.notna(), np.nan)

                labels.append(
                    {
                        "label_id": f"local_extrema_top_lb{lookback}_fw{forward}",
                        "family": "local_extrema",
                        "side": "top",
                        "horizon_months": int(forward),
                        "params": f"lookback={lookback},forward={forward}",
                        "series": top,
                    }
                )
                labels.append(
                    {
                        "label_id": f"local_extrema_bottom_lb{lookback}_fw{forward}",
                        "family": "local_extrema",
                        "side": "bottom",
                        "horizon_months": int(forward),
                        "params": f"lookback={lookback},forward={forward}",
                        "series": bottom,
                    }
                )

    return labels


def evaluate_benchmark(
    cfg: RuntimeConfig,
    monthly_price: pd.Series,
    signals: Dict[str, pd.Series],
    *,
    calibration_metadata: Dict[str, Any] | None = None,
) -> BenchmarkResult:
    if not cfg.benchmark_enabled:
        return BenchmarkResult(
            summary=pd.DataFrame(),
            by_label=pd.DataFrame(),
            by_signal=pd.DataFrame(),
            window_stats=pd.DataFrame(),
            config={"enabled": False},
            warnings=["benchmark_disabled"],
        )

    monthly_price = monthly_price.astype(float).dropna()
    if monthly_price.empty or not signals:
        return BenchmarkResult(
            summary=pd.DataFrame(),
            by_label=pd.DataFrame(),
            by_signal=pd.DataFrame(),
            window_stats=pd.DataFrame(),
            config={},
            warnings=["benchmark_unavailable:missing_monthly_price_or_signals"],
        )

    aligned_signals = {
        key: value.astype(float).reindex(monthly_price.index)
        for key, value in signals.items()
    }
    label_defs = _build_labels(cfg, monthly_price)

    rows_by_label: List[Dict[str, Any]] = []
    for label in label_defs:
        label_series = label["series"].reindex(monthly_price.index)
        for signal_name, signal_series in aligned_signals.items():
            joined = pd.DataFrame(
                {
                    "score": signal_series,
                    "label": label_series,
                },
                index=monthly_price.index,
            )
            for window_name, window_frame in _window_view(
                joined,
                recent_window_months=cfg.benchmark_recent_window_months,
            ).items():
                score = window_frame["score"]
                y = window_frame["label"]

                auc = _auc(score, y)
                pr_auc = _pr_auc(score, y)
                threshold = _best_f1_threshold(score, y)
                precision, recall, f1 = _threshold_metrics(score, y, threshold)
                recall_alert, median_lead, false_alarm_rate, event_coverage = _lead_time_metrics(
                    score,
                    y,
                    alert_rate=cfg.benchmark_alert_rate,
                    horizon_months=int(label["horizon_months"]),
                )

                resolved = y.dropna()
                n_obs = int(resolved.shape[0])
                n_events = int((resolved.astype(int) == 1).sum())

                rows_by_label.append(
                    {
                        "window": window_name,
                        "signal": signal_name,
                        "label_id": label["label_id"],
                        "family": label["family"],
                        "side": label["side"],
                        "horizon_months": int(label["horizon_months"]),
                        "params": label["params"],
                        "n_obs": n_obs,
                        "n_events": n_events,
                        "auc": auc,
                        "pr_auc": pr_auc,
                        "lead_recall_at_alert_rate": recall_alert,
                        "median_lead_months": median_lead,
                        "false_alarm_rate": false_alarm_rate,
                        "event_coverage": event_coverage,
                        "calibrated_threshold": float(threshold) if np.isfinite(threshold) else np.nan,
                        "precision": precision,
                        "recall": recall,
                        "f1": f1,
                    }
                )

    by_label = pd.DataFrame(rows_by_label)

    if by_label.empty:
        return BenchmarkResult(
            summary=pd.DataFrame(),
            by_label=by_label,
            by_signal=pd.DataFrame(),
            window_stats=pd.DataFrame(),
            config={},
            warnings=["benchmark_unavailable:no_label_rows"],
        )

    aggregate_cols = [
        "auc",
        "pr_auc",
        "lead_recall_at_alert_rate",
        "median_lead_months",
        "false_alarm_rate",
        "event_coverage",
        "precision",
        "recall",
        "f1",
    ]

    event_weight_pivot = float(max(int(getattr(cfg, "benchmark_event_weight_pivot", 5)), 1))
    by_label["event_weight"] = (by_label["n_events"].fillna(0.0).astype(float) / event_weight_pivot).clip(0.0, 1.0)

    by_signal_rows: List[Dict[str, Any]] = []
    for (window, signal), group in by_label.groupby(["window", "signal"], dropna=False):
        row: Dict[str, Any] = {"window": window, "signal": signal}
        row.update(_aggregate_group(group, aggregate_cols))
        by_signal_rows.append(row)
    by_signal = pd.DataFrame(by_signal_rows).sort_values(["window", "signal"]).reset_index(drop=True)

    window_stat_cols = [
        "lead_recall_at_alert_rate",
        "auc",
        "pr_auc",
        "false_alarm_rate",
        "event_coverage",
    ]
    window_stats_rows: List[Dict[str, Any]] = []
    for (window, side), group in by_label.groupby(["window", "side"], dropna=False):
        row: Dict[str, Any] = {"window": window, "side": side}
        row.update(_aggregate_group(group, window_stat_cols))
        window_stats_rows.append(row)
    window_stats = pd.DataFrame(window_stats_rows).sort_values(["window", "side"]).reset_index(drop=True)

    summary_rows: List[Dict[str, Any]] = []
    for side, signal in (("top", "top_reversal_risk"), ("bottom", "bottom_reversal_risk")):
        expanding = by_label[
            (by_label["window"] == "expanding")
            & (by_label["side"] == side)
            & (by_label["signal"] == signal)
        ]
        recent = by_label[
            (by_label["window"] == "recent")
            & (by_label["side"] == side)
            & (by_label["signal"] == signal)
        ]

        exp_value = (
            _weighted_mean(expanding["lead_recall_at_alert_rate"], expanding["event_weight"])
            if not expanding.empty
            else float("nan")
        )
        rec_value = (
            _weighted_mean(recent["lead_recall_at_alert_rate"], recent["event_weight"])
            if not recent.empty
            else float("nan")
        )
        exp_weight = float(expanding["event_weight"].fillna(0.0).sum()) if not expanding.empty else 0.0
        rec_weight = float(recent["event_weight"].fillna(0.0).sum()) if not recent.empty else 0.0
        exp_labels = int((expanding["event_weight"].fillna(0.0) > 0.0).sum()) if not expanding.empty else 0
        rec_labels = int((recent["event_weight"].fillna(0.0) > 0.0).sum()) if not recent.empty else 0
        summary_rows.append(
            {
                "kpi": f"lead_recall_{side}",
                "signal": signal,
                "expanding": exp_value,
                "recent": rec_value,
                "delta_recent_minus_expanding": rec_value - exp_value
                if np.isfinite(rec_value) and np.isfinite(exp_value)
                else np.nan,
                "alert_rate": float(cfg.benchmark_alert_rate),
                "expanding_effective_weight_sum": exp_weight,
                "recent_effective_weight_sum": rec_weight,
                "expanding_effective_label_count": exp_labels,
                "recent_effective_label_count": rec_labels,
                "aggregation_method": "soft_event_weighted_v1",
            }
        )
        exp_far = (
            _weighted_mean(expanding["false_alarm_rate"], expanding["event_weight"])
            if not expanding.empty
            else float("nan")
        )
        rec_far = (
            _weighted_mean(recent["false_alarm_rate"], recent["event_weight"])
            if not recent.empty
            else float("nan")
        )
        summary_rows.append(
            {
                "kpi": f"false_alarm_{side}",
                "signal": signal,
                "expanding": exp_far,
                "recent": rec_far,
                "delta_recent_minus_expanding": rec_far - exp_far
                if np.isfinite(rec_far) and np.isfinite(exp_far)
                else np.nan,
                "alert_rate": float(cfg.benchmark_alert_rate),
                "expanding_effective_weight_sum": exp_weight,
                "recent_effective_weight_sum": rec_weight,
                "expanding_effective_label_count": exp_labels,
                "recent_effective_label_count": rec_labels,
                "aggregation_method": "soft_event_weighted_v1",
            }
        )

    summary = pd.DataFrame(summary_rows)

    warnings: List[str] = []
    expected_families = {name.strip().lower() for name in cfg.benchmark_label_families}
    available_families = set(by_label["family"].astype(str).str.lower().unique().tolist())
    missing = sorted(expected_families - available_families)
    if missing:
        warnings.append(f"benchmark_missing_label_families:{','.join(missing)}")

    low_event_rows = by_label[by_label["n_events"].fillna(0) < 3]
    if not low_event_rows.empty:
        warnings.append(
            f"benchmark_low_event_count:{int(low_event_rows.shape[0])}_rows_have_fewer_than_3_events"
        )
        total_eff_weight = float(by_label["event_weight"].fillna(0.0).sum())
        warnings.append(
            f"benchmark_weighted_effective_size:event_weight_sum={total_eff_weight:.3f},pivot={event_weight_pivot:.1f}"
        )

    if calibration_metadata:
        calibration_time = calibration_metadata.get("walkforward_last_train_end")
        if calibration_time:
            warnings.append(f"benchmark_calibration_reference:{calibration_time}")

    benchmark_config = {
        "enabled": bool(cfg.benchmark_enabled),
        "horizons_months": [int(x) for x in cfg.benchmark_horizons_months],
        "recent_window_months": int(cfg.benchmark_recent_window_months),
        "alert_rate": float(cfg.benchmark_alert_rate),
        "label_families": [str(x) for x in cfg.benchmark_label_families],
        "quantile_levels": [float(x) for x in cfg.benchmark_quantile_levels],
        "top_drawdown_thresholds": [float(x) for x in cfg.benchmark_top_drawdown_thresholds],
        "bottom_rally_thresholds": [float(x) for x in cfg.benchmark_bottom_rally_thresholds],
        "local_extrema_lookbacks": [int(x) for x in cfg.benchmark_local_extrema_lookbacks],
        "local_extrema_forwards": [int(x) for x in cfg.benchmark_local_extrema_forwards],
        "event_weight_pivot": int(event_weight_pivot),
        "aggregation_method": "soft_event_weighted_v1",
    }

    return BenchmarkResult(
        summary=summary,
        by_label=by_label,
        by_signal=by_signal,
        window_stats=window_stats,
        config=benchmark_config,
        warnings=warnings,
    )
