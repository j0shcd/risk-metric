from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

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

    drawdown = monthly["price"] / monthly["price"].cummax().replace({0.0: np.nan}) - 1.0
    drawdown_depth = (-drawdown).clip(0.0, 0.90) / 0.90

    top_label = (_future_min_return(monthly["price"], resolution_horizon_months) <= -0.40).astype(float)
    top_label = top_label.where(_future_min_return(monthly["price"], resolution_horizon_months).notna(), np.nan)

    bottom_label = (_future_max_return(monthly["price"], resolution_horizon_months) >= 0.80).astype(float)
    bottom_label = bottom_label.where(_future_max_return(monthly["price"], resolution_horizon_months).notna(), np.nan)

    top_calibrated, top_meta = _select_best_walkforward(
        base=monthly["top"].clip(0.0, 1.0),
        feat_a=price_percentile.clip(0.0, 1.0),
        feat_b=momentum_pct.clip(0.0, 1.0),
        labels=top_label,
        min_train_months=min_train_months,
        resolution_horizon_months=resolution_horizon_months,
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
        "top_mean_w_base": float(top_meta.get("mean_w_base", 1.0)),
        "top_mean_w_price_extremity": float(top_meta.get("mean_w_feature_a", 0.0)),
        "top_mean_w_momentum": float(top_meta.get("mean_w_feature_b", 0.0)),
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
