from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CalibrationResult:
    series: pd.DataFrame
    metadata: Dict[str, float | str]


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


def _expanding_percentile(series: pd.Series, min_history: int = 24) -> pd.Series:
    values = series.astype(float)
    out = pd.Series(index=values.index, dtype=float)
    observed: list[float] = []

    for i, value in enumerate(values.to_numpy()):
        if np.isnan(value):
            out.iloc[i] = np.nan
            continue
        observed.append(float(value))
        if len(observed) < min_history:
            out.iloc[i] = np.nan
            continue
        history = np.asarray(observed, dtype=float)
        out.iloc[i] = float((history <= value).mean())

    return out.clip(0.0, 1.0)


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
    return float(np.trapz(precision, recall))


def _candidate_grid(
    base: pd.Series,
    feature_a: pd.Series,
    feature_b: pd.Series,
) -> Iterable[Tuple[float, float, float, pd.Series]]:
    grid = np.linspace(0.0, 0.8, 9)
    for w_a in grid:
        for w_b in grid:
            total = float(w_a + w_b)
            if total > 0.9:
                continue
            w_base = float(1.0 - total)
            candidate = (w_base * base + w_a * feature_a + w_b * feature_b).clip(0.0, 1.0)
            yield w_base, float(w_a), float(w_b), candidate


def _candidate_grid_multi(
    base: pd.Series,
    feature_frame: pd.DataFrame,
    *,
    max_feature_sum: float = 0.9,
) -> Iterable[Tuple[float, np.ndarray, pd.Series]]:
    feature_cols = list(feature_frame.columns)
    if not feature_cols:
        candidate = base.clip(0.0, 1.0)
        yield 1.0, np.zeros(0, dtype=float), candidate
        return

    grid = np.linspace(0.0, 0.6, 7)
    for weights_tuple in product(grid, repeat=len(feature_cols)):
        weights = np.asarray(weights_tuple, dtype=float)
        total = float(np.nansum(weights))
        if total > max_feature_sum:
            continue
        w_base = float(1.0 - total)
        candidate = (w_base * base + feature_frame.mul(weights, axis=1).sum(axis=1)).clip(0.0, 1.0)
        yield w_base, weights, candidate


def _select_best_walkforward(
    base: pd.Series,
    feat_a: pd.Series,
    feat_b: pd.Series,
    labels: pd.Series,
    *,
    min_train_months: int,
    resolution_horizon_months: int,
) -> Tuple[pd.Series, Dict[str, float | str]]:
    out = pd.Series(index=base.index, dtype=float)

    selected_weights: list[Tuple[float, float, float]] = []
    last_train_end = ""

    for i, current_date in enumerate(base.index):
        if i < min_train_months:
            out.loc[current_date] = base.iloc[i]
            continue

        resolved_end_idx = i - int(max(resolution_horizon_months, 1))
        if resolved_end_idx <= 0:
            out.loc[current_date] = base.iloc[i]
            continue

        train_index = base.index[:resolved_end_idx]
        train = pd.DataFrame(
            {
                "base": base.reindex(train_index),
                "a": feat_a.reindex(train_index),
                "b": feat_b.reindex(train_index),
                "y": labels.reindex(train_index),
            }
        ).dropna()

        if len(train) < min_train_months:
            out.loc[current_date] = base.iloc[i]
            continue

        if int((train["y"] == 1).sum()) < 3 or int((train["y"] == 0).sum()) < 3:
            out.loc[current_date] = base.iloc[i]
            continue

        best_score = float("-inf")
        best_weights = (1.0, 0.0, 0.0)

        for w_base, w_a, w_b, _ in _candidate_grid(train["base"], train["a"], train["b"]):
            candidate = (w_base * train["base"] + w_a * train["a"] + w_b * train["b"]).clip(0.0, 1.0)
            auc = _auc(candidate, train["y"])
            pr = _pr_auc(candidate, train["y"])
            auc_term = float(auc) if np.isfinite(auc) else 0.0
            pr_term = float(pr) if np.isfinite(pr) else 0.0
            objective = auc_term + 0.25 * pr_term
            if objective > best_score:
                best_score = objective
                best_weights = (w_base, w_a, w_b)

        w_base, w_a, w_b = best_weights
        selected_weights.append((float(w_base), float(w_a), float(w_b)))
        out.loc[current_date] = float(
            (w_base * base.iloc[i] + w_a * feat_a.iloc[i] + w_b * feat_b.iloc[i])
        )
        last_train_end = str(train.index.max().date())

    valid_weights = np.asarray(selected_weights, dtype=float) if selected_weights else np.empty((0, 3))
    if valid_weights.size == 0:
        mean_weights = (1.0, 0.0, 0.0)
    else:
        mean_weights = (
            float(np.nanmean(valid_weights[:, 0])),
            float(np.nanmean(valid_weights[:, 1])),
            float(np.nanmean(valid_weights[:, 2])),
        )

    metadata = {
        "mean_w_base": mean_weights[0],
        "mean_w_feature_a": mean_weights[1],
        "mean_w_feature_b": mean_weights[2],
        "walkforward_steps": float(len(selected_weights)),
        "walkforward_last_train_end": last_train_end,
    }
    return out.clip(0.0, 1.0), metadata


def _lead_recall_false_alarm(
    scores: pd.Series,
    labels: pd.Series,
    *,
    alert_rate: float,
    horizon_months: int,
) -> Tuple[float, float]:
    frame = pd.concat([scores, labels], axis=1).dropna()
    if frame.empty:
        return float("nan"), float("nan")

    ranked = frame.iloc[:, 0].astype(float)
    threshold = float(ranked.quantile(max(0.0, min(1.0, 1.0 - alert_rate))))
    alerts = ranked >= threshold

    event_index = frame.index[frame.iloc[:, 1].astype(int) == 1]
    n_events = len(event_index)
    if n_events == 0:
        false_alarm_rate = float((alerts.sum() / len(alerts)) if len(alerts) else float("nan"))
        return float("nan"), false_alarm_rate

    hit_count = 0
    for event_date in event_index:
        start = event_date - pd.DateOffset(months=max(int(horizon_months), 1))
        window = alerts.loc[(alerts.index >= start) & (alerts.index <= event_date)]
        if window.any():
            hit_count += 1
    recall = float(hit_count / n_events)

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
    return recall, false_alarm_rate


def _select_best_walkforward_top_features(
    base: pd.Series,
    feature_frame: pd.DataFrame,
    labels: pd.Series,
    *,
    min_train_months: int,
    resolution_horizon_months: int,
    alert_rate: float,
) -> Tuple[pd.Series, Dict[str, float | str]]:
    out = pd.Series(index=base.index, dtype=float)
    feature_cols = list(feature_frame.columns)

    selected: List[Tuple[float, np.ndarray]] = []
    train_event_counts: List[float] = []
    last_train_end = ""

    for i, current_date in enumerate(base.index):
        if i < min_train_months:
            out.loc[current_date] = base.iloc[i]
            continue

        resolved_end_idx = i - int(max(resolution_horizon_months, 1))
        if resolved_end_idx <= 0:
            out.loc[current_date] = base.iloc[i]
            continue

        train_index = base.index[:resolved_end_idx]
        train = pd.DataFrame({"base": base.reindex(train_index), "y": labels.reindex(train_index)})
        for col in feature_cols:
            train[col] = feature_frame[col].reindex(train_index)
        train = train.dropna()

        if len(train) < min_train_months:
            out.loc[current_date] = base.iloc[i]
            continue

        n_events = int((train["y"] == 1).sum())
        n_non_events = int((train["y"] == 0).sum())
        if n_events < 3 or n_non_events < 3:
            out.loc[current_date] = base.iloc[i]
            continue

        train_event_counts.append(float(n_events))
        best_key = (float("-inf"), float("-inf"), float("-inf"))
        best_weights = (1.0, np.zeros(len(feature_cols), dtype=float))

        for w_base, w_feats, candidate in _candidate_grid_multi(
            train["base"],
            train[feature_cols],
        ):
            recall_alert, false_alarm_rate = _lead_recall_false_alarm(
                candidate,
                train["y"],
                alert_rate=alert_rate,
                horizon_months=resolution_horizon_months,
            )
            pr = _pr_auc(candidate, train["y"])

            recall_term = float(recall_alert) if np.isfinite(recall_alert) else float("-inf")
            pr_term = float(pr) if np.isfinite(pr) else float("-inf")
            far_term = float(false_alarm_rate) if np.isfinite(false_alarm_rate) else float("inf")
            key = (recall_term, pr_term, -far_term)
            if key > best_key:
                best_key = key
                best_weights = (float(w_base), np.asarray(w_feats, dtype=float))

        w_base, w_feats = best_weights
        selected.append((w_base, w_feats.copy()))

        current_features = feature_frame.loc[current_date, feature_cols].astype(float)
        if current_features.isna().any() or pd.isna(base.loc[current_date]):
            out.loc[current_date] = float(base.loc[current_date])
        else:
            out.loc[current_date] = float(
                (w_base * float(base.loc[current_date])) + float(np.dot(w_feats, current_features.to_numpy()))
            )
        last_train_end = str(train.index.max().date())

    if selected:
        base_weights = np.asarray([item[0] for item in selected], dtype=float)
        feature_weights = np.asarray([item[1] for item in selected], dtype=float)
        mean_w_base = float(np.nanmean(base_weights))
        mean_feature_weights = (
            np.nanmean(feature_weights, axis=0) if feature_weights.size else np.zeros(len(feature_cols), dtype=float)
        )
    else:
        mean_w_base = 1.0
        mean_feature_weights = np.zeros(len(feature_cols), dtype=float)

    metadata: Dict[str, float | str] = {
        "mean_w_base": mean_w_base,
        "walkforward_steps": float(len(selected)),
        "walkforward_last_train_end": last_train_end,
        "top_train_event_count_mean": float(np.nanmean(train_event_counts)) if train_event_counts else float("nan"),
    }
    for idx, col in enumerate(feature_cols):
        metadata[f"mean_w_{col}"] = float(mean_feature_weights[idx]) if idx < len(mean_feature_weights) else 0.0
    return out.clip(0.0, 1.0), metadata


def calibrate_primary_outputs(
    series: pd.DataFrame,
    *,
    min_train_months: int = 24,
    resolution_horizon_months: int = 12,
) -> CalibrationResult:
    required = {"btc_price"}
    if not required.issubset(set(series.columns)):
        return CalibrationResult(series=series.copy(), metadata={"calibration_applied": 0.0})

    output = series.copy()

    top_col = "top_reversal_risk" if "top_reversal_risk" in output.columns else "btc_risk_heat"
    bottom_col = (
        "bottom_reversal_risk"
        if "bottom_reversal_risk" in output.columns
        else ("cycle_p_accumulation" if "cycle_p_accumulation" in output.columns else None)
    )
    trend_col = "trend_heat" if "trend_heat" in output.columns else "headline_heat"
    attention_col = "attention_score" if "attention_score" in output.columns else "headline_attention"

    if bottom_col is None:
        output["bottom_reversal_risk"] = (1.0 - output[top_col].astype(float)).clip(0.0, 1.0)
        bottom_col = "bottom_reversal_risk"

    monthly = pd.DataFrame(index=output.resample("M").last().index)
    monthly["price"] = output["btc_price"].astype(float).resample("M").last()
    monthly["top"] = output[top_col].astype(float).resample("M").last()
    monthly["bottom"] = output[bottom_col].astype(float).resample("M").last()
    monthly["trend"] = output[trend_col].astype(float).resample("M").last()
    monthly["attention"] = output[attention_col].astype(float).resample("M").mean()

    monthly = monthly.dropna(subset=["price"]) 

    if len(monthly) < (min_train_months + resolution_horizon_months + 6):
        return CalibrationResult(series=output, metadata={"calibration_applied": 0.0})

    price_percentile = _expanding_percentile(monthly["price"], min_history=min_train_months)
    momentum_6m = monthly["price"].pct_change(6, fill_method=None)
    momentum_pct = _expanding_percentile(momentum_6m, min_history=min_train_months)
    attention_pct = _expanding_percentile(monthly["attention"], min_history=min_train_months)

    drawdown = monthly["price"] / monthly["price"].cummax().replace({0.0: np.nan}) - 1.0
    drawdown_depth = (-drawdown).clip(0.0, 0.90) / 0.90

    top_label = (_future_min_return(monthly["price"], resolution_horizon_months) <= -0.40).astype(float)
    top_label = top_label.where(_future_min_return(monthly["price"], resolution_horizon_months).notna(), np.nan)

    bottom_label = (_future_max_return(monthly["price"], resolution_horizon_months) >= 0.80).astype(float)
    bottom_label = bottom_label.where(_future_max_return(monthly["price"], resolution_horizon_months).notna(), np.nan)

    monthly["price_extremity_pct"] = (
        output.get("price_extremity_pct", pd.Series(index=output.index, dtype=float))
        .astype(float)
        .resample("M")
        .last()
        .reindex(monthly.index)
    )
    monthly["momentum_exhaustion_pct"] = (
        output.get("momentum_exhaustion_pct", pd.Series(index=output.index, dtype=float))
        .astype(float)
        .resample("M")
        .last()
        .reindex(monthly.index)
    )
    monthly["attention_blowoff_pct"] = (
        output.get("attention_blowoff_pct", pd.Series(index=output.index, dtype=float))
        .astype(float)
        .resample("M")
        .last()
        .reindex(monthly.index)
    )

    top_features = pd.DataFrame(index=monthly.index)
    top_features["price_extremity_pct"] = monthly["price_extremity_pct"].fillna(price_percentile)
    top_features["momentum_exhaustion_pct"] = monthly["momentum_exhaustion_pct"].fillna(momentum_pct)
    top_features["attention_blowoff_pct"] = monthly["attention_blowoff_pct"].fillna(attention_pct)
    top_features = top_features.clip(0.0, 1.0)

    top_calibrated, top_meta = _select_best_walkforward_top_features(
        base=monthly["top"].clip(0.0, 1.0),
        feature_frame=top_features,
        labels=top_label,
        min_train_months=min_train_months,
        resolution_horizon_months=resolution_horizon_months,
        alert_rate=0.20,
    )

    bottom_calibrated, bottom_meta = _select_best_walkforward(
        base=monthly["bottom"].clip(0.0, 1.0),
        feat_a=drawdown_depth.clip(0.0, 1.0),
        feat_b=(1.0 - momentum_pct).clip(0.0, 1.0),
        labels=bottom_label,
        min_train_months=min_train_months,
        resolution_horizon_months=resolution_horizon_months,
    )

    attention_extremity = (2.0 * (top_calibrated - 0.5).abs()).clip(0.0, 1.0)
    attention_calibrated = (0.80 * monthly["attention"].clip(0.0, 1.0) + 0.20 * attention_extremity).clip(0.0, 1.0)

    top_daily = top_calibrated.reindex(output.index, method="ffill")
    bottom_daily = bottom_calibrated.reindex(output.index, method="ffill")
    attention_daily = attention_calibrated.reindex(output.index, method="ffill")

    output["top_reversal_risk"] = top_daily.clip(0.0, 1.0)
    output["bottom_reversal_risk"] = bottom_daily.clip(0.0, 1.0)

    if "attention_score" in output.columns:
        output["attention_score"] = attention_daily.clip(0.0, 1.0)
    if "headline_attention" in output.columns:
        output["headline_attention"] = attention_daily.clip(0.0, 1.0)

    metadata: Dict[str, float | str] = {
        "calibration_applied": 1.0,
        "top_objective": "recall20_then_prauc_then_far",
        "top_mean_w_base": float(top_meta.get("mean_w_base", 1.0)),
        "top_mean_w_price_extremity": float(top_meta.get("mean_w_price_extremity_pct", 0.0)),
        "top_mean_w_momentum_exhaustion": float(top_meta.get("mean_w_momentum_exhaustion_pct", 0.0)),
        "top_mean_w_attention_blowoff": float(top_meta.get("mean_w_attention_blowoff_pct", 0.0)),
        # Backward-compatible alias.
        "top_mean_w_momentum": float(top_meta.get("mean_w_momentum_exhaustion_pct", 0.0)),
        "top_train_event_count_mean": float(top_meta.get("top_train_event_count_mean", float("nan"))),
        "bottom_mean_w_base": float(bottom_meta.get("mean_w_base", 1.0)),
        "bottom_mean_w_drawdown_depth": float(bottom_meta.get("mean_w_feature_a", 0.0)),
        "bottom_mean_w_anti_momentum": float(bottom_meta.get("mean_w_feature_b", 0.0)),
        "walkforward_steps_top": float(top_meta.get("walkforward_steps", 0.0)),
        "walkforward_steps_bottom": float(bottom_meta.get("walkforward_steps", 0.0)),
        "walkforward_last_train_end": str(
            top_meta.get("walkforward_last_train_end") or bottom_meta.get("walkforward_last_train_end") or ""
        ),
    }
    return CalibrationResult(series=output, metadata=metadata)
