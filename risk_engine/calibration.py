from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from .config import RuntimeConfig


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


def _future_return(price: pd.Series, horizon: int) -> pd.Series:
    return price.shift(-horizon) / price - 1.0


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
    trapz = getattr(np, "trapezoid", None)
    if trapz is None:
        trapz = np.trapz
    return float(trapz(precision, recall))


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
    price: pd.Series,
    base: pd.Series,
    feat_a: pd.Series,
    feat_b: pd.Series,
    labels: pd.Series,
    *,
    min_train_months: int,
    resolution_horizon_months: int,
    label_weight: float,
    financial_weight: float,
    buy_threshold: float,
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
                "price": price.reindex(train_index),
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
            auc_term = float(auc) if np.isfinite(auc) else -1.0
            pr_term = float(pr) if np.isfinite(pr) else -1.0
            label_objective = auc_term + 0.25 * pr_term
            position = ((candidate - float(buy_threshold)) / max(1e-9, 1.0 - float(buy_threshold))).clip(0.0, 1.0)
            fin_objective = _financial_quality_from_position(position, train["price"])
            objective = float(label_weight) * label_objective + float(financial_weight) * fin_objective
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


def _max_drawdown(equity: pd.Series) -> float:
    clean = equity.dropna()
    if clean.empty:
        return float("nan")
    peak = clean.cummax()
    drawdown = clean / peak.replace({0.0: np.nan}) - 1.0
    return float(drawdown.min())


def _cagr(equity: pd.Series, periods_per_year: float = 12.0) -> float:
    clean = equity.dropna()
    if clean.empty:
        return float("nan")
    years = max(len(clean) / max(float(periods_per_year), 1e-9), 1.0 / max(float(periods_per_year), 1e-9))
    terminal = float(clean.iloc[-1])
    if not np.isfinite(terminal) or terminal <= 0.0:
        return float("nan")
    return float(terminal ** (1.0 / years) - 1.0)


def _calmar(cagr: float, max_drawdown: float) -> float:
    if not np.isfinite(cagr) or not np.isfinite(max_drawdown) or max_drawdown >= 0.0:
        return float("nan")
    return float(cagr / max(abs(float(max_drawdown)), 1e-9))


def _financial_quality_from_position(position: pd.Series, price: pd.Series) -> float:
    aligned = pd.DataFrame({"pos": position.astype(float), "price": price.astype(float)}).dropna()
    if len(aligned) < 12:
        return float("-inf")
    ret = aligned["price"].pct_change(fill_method=None).fillna(0.0)
    strat_ret = aligned["pos"].shift(1).fillna(0.0) * ret
    equity = (1.0 + strat_ret).cumprod()
    cagr = _cagr(equity, periods_per_year=12.0)
    mdd = _max_drawdown(equity)
    calmar = _calmar(cagr, mdd)
    cagr_term = float(cagr) if np.isfinite(cagr) else -1.0
    calmar_term = float(calmar) if np.isfinite(calmar) else -1.0
    mdd_term = 1.0 - min(abs(float(mdd)), 1.0) if np.isfinite(mdd) else -1.0
    return float(cagr_term + 0.50 * calmar_term + 0.50 * mdd_term)


def _select_best_walkforward_top_features(
    price: pd.Series,
    base: pd.Series,
    feature_frame: pd.DataFrame,
    labels: pd.Series,
    *,
    min_train_months: int,
    resolution_horizon_months: int,
    alert_rate: float,
    label_weight: float,
    financial_weight: float,
    sell_threshold: float,
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
        train = pd.DataFrame(
            {
                "price": price.reindex(train_index),
                "base": base.reindex(train_index),
                "y": labels.reindex(train_index),
            }
        )
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
        best_score = float("-inf")
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
            recall_term = float(recall_alert) if np.isfinite(recall_alert) else -1.0
            pr_term = float(pr) if np.isfinite(pr) else -1.0
            far_term = float(false_alarm_rate) if np.isfinite(false_alarm_rate) else 1.0
            label_objective = recall_term + 0.35 * pr_term - 0.40 * far_term
            position = (
                1.0 - ((candidate - float(sell_threshold)) / max(1e-9, 1.0 - float(sell_threshold))).clip(0.0, 1.0)
            ).clip(0.0, 1.0)
            fin_objective = _financial_quality_from_position(position, train["price"])
            score = float(label_weight) * label_objective + float(financial_weight) * fin_objective
            if score > best_score:
                best_score = score
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


def _long_cycle_labels(
    monthly_price: pd.Series,
    *,
    horizons_months: List[int],
    lookback_months: int = 24,
) -> Tuple[pd.Series, pd.Series]:
    horizons = [int(h) for h in horizons_months if int(h) > 0]
    if not horizons:
        horizons = [36]
    fwd_frame = pd.DataFrame(index=monthly_price.index)
    for horizon in horizons:
        fwd_frame[f"h{horizon}"] = _future_return(monthly_price, horizon)
    fwd_mean = fwd_frame.mean(axis=1, skipna=True)
    resolved = fwd_mean.dropna()
    q_low = float(resolved.quantile(0.20)) if not resolved.empty else np.nan
    q_high = float(resolved.quantile(0.80)) if not resolved.empty else np.nan

    past_max = monthly_price.rolling(int(max(lookback_months, 1)), min_periods=int(max(lookback_months, 1))).max()
    past_min = monthly_price.rolling(int(max(lookback_months, 1)), min_periods=int(max(lookback_months, 1))).min()
    top_extreme = monthly_price >= past_max
    bottom_extreme = monthly_price <= past_min

    top = ((fwd_mean <= q_low) & top_extreme).astype(float).where(fwd_mean.notna() & past_max.notna(), np.nan)
    bottom = ((fwd_mean >= q_high) & bottom_extreme).astype(float).where(fwd_mean.notna() & past_min.notna(), np.nan)

    # Ensure enough events for walk-forward; if too sparse fallback to quantile-only labels.
    top_events = int((top.dropna().astype(int) == 1).sum())
    bottom_events = int((bottom.dropna().astype(int) == 1).sum())
    if top_events < 3:
        top = (fwd_mean <= q_low).astype(float).where(fwd_mean.notna(), np.nan)
    if bottom_events < 3:
        bottom = (fwd_mean >= q_high).astype(float).where(fwd_mean.notna(), np.nan)
    return top, bottom


def calibrate_primary_outputs(
    series: pd.DataFrame,
    *,
    cfg: RuntimeConfig | None = None,
    min_train_months: int = 24,
    resolution_horizon_months: int = 36,
) -> CalibrationResult:
    runtime = cfg
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

    monthly = pd.DataFrame(index=output.resample(pd.offsets.MonthEnd()).last().index)
    monthly["price"] = output["btc_price"].astype(float).resample(pd.offsets.MonthEnd()).last()
    monthly["top"] = output[top_col].astype(float).resample(pd.offsets.MonthEnd()).last()
    monthly["bottom"] = output[bottom_col].astype(float).resample(pd.offsets.MonthEnd()).last()
    monthly["trend"] = output[trend_col].astype(float).resample(pd.offsets.MonthEnd()).last()
    monthly["attention"] = output[attention_col].astype(float).resample(pd.offsets.MonthEnd()).mean()

    monthly = monthly.dropna(subset=["price"]) 

    if len(monthly) < (min_train_months + resolution_horizon_months + 6):
        return CalibrationResult(series=output, metadata={"calibration_applied": 0.0})

    price_percentile = _expanding_percentile(monthly["price"], min_history=min_train_months)
    momentum_6m = monthly["price"].pct_change(6, fill_method=None)
    momentum_pct = _expanding_percentile(momentum_6m, min_history=min_train_months)
    attention_pct = _expanding_percentile(monthly["attention"], min_history=min_train_months)

    drawdown = monthly["price"] / monthly["price"].cummax().replace({0.0: np.nan}) - 1.0
    drawdown_depth = (-drawdown).clip(0.0, 0.90) / 0.90

    horizons = (
        [int(h) for h in runtime.cycle_calibration_horizons_months]
        if runtime is not None and getattr(runtime, "cycle_calibration_horizons_months", None)
        else [int(resolution_horizon_months)]
    )
    top_label, bottom_label = _long_cycle_labels(monthly["price"], horizons_months=horizons, lookback_months=24)

    monthly["price_extremity_pct"] = (
        output.get("price_extremity_pct", pd.Series(index=output.index, dtype=float))
        .astype(float)
        .resample(pd.offsets.MonthEnd())
        .last()
        .reindex(monthly.index)
    )
    monthly["momentum_exhaustion_pct"] = (
        output.get("momentum_exhaustion_pct", pd.Series(index=output.index, dtype=float))
        .astype(float)
        .resample(pd.offsets.MonthEnd())
        .last()
        .reindex(monthly.index)
    )
    monthly["attention_blowoff_pct"] = (
        output.get("attention_blowoff_pct", pd.Series(index=output.index, dtype=float))
        .astype(float)
        .resample(pd.offsets.MonthEnd())
        .last()
        .reindex(monthly.index)
    )

    top_features = pd.DataFrame(index=monthly.index)
    top_features["price_extremity_pct"] = monthly["price_extremity_pct"].fillna(price_percentile)
    top_features["momentum_exhaustion_pct"] = monthly["momentum_exhaustion_pct"].fillna(momentum_pct)
    top_features["attention_blowoff_pct"] = monthly["attention_blowoff_pct"].fillna(attention_pct)
    top_features = top_features.clip(0.0, 1.0)

    top_calibrated, top_meta = _select_best_walkforward_top_features(
        price=monthly["price"],
        base=monthly["top"].clip(0.0, 1.0),
        feature_frame=top_features,
        labels=top_label,
        min_train_months=min_train_months,
        resolution_horizon_months=max(horizons),
        alert_rate=0.20,
        label_weight=float(runtime.cycle_financial_label_weight if runtime is not None else 0.50),
        financial_weight=float(runtime.cycle_financial_kpi_weight if runtime is not None else 0.50),
        sell_threshold=float(runtime.cycle_dynamic_dca_sell_threshold if runtime is not None else 0.75),
    )

    bottom_calibrated, bottom_meta = _select_best_walkforward(
        price=monthly["price"],
        base=monthly["bottom"].clip(0.0, 1.0),
        feat_a=drawdown_depth.clip(0.0, 1.0),
        feat_b=(1.0 - momentum_pct).clip(0.0, 1.0),
        labels=bottom_label,
        min_train_months=min_train_months,
        resolution_horizon_months=max(horizons),
        label_weight=float(runtime.cycle_financial_label_weight if runtime is not None else 0.50),
        financial_weight=float(runtime.cycle_financial_kpi_weight if runtime is not None else 0.50),
        buy_threshold=float(runtime.cycle_dynamic_dca_buy_threshold if runtime is not None else 0.75),
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
        "top_objective": "composite_long_cycle_label_and_financial",
        "calibration_horizons_months": ",".join([str(h) for h in horizons]),
        "objective_label_weight": float(runtime.cycle_financial_label_weight if runtime is not None else 0.50),
        "objective_financial_weight": float(runtime.cycle_financial_kpi_weight if runtime is not None else 0.50),
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
