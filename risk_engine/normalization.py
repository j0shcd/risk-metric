from __future__ import annotations

import numpy as np
import pandas as pd


EPSILON = 1e-9


def _safe_scale(window_values: pd.Series, median: float) -> float:
    mad = (window_values - median).abs().median()
    scale = 1.4826 * mad
    if scale > EPSILON:
        return float(scale)

    std = float(window_values.std(ddof=0))
    if std > EPSILON:
        return std

    return float("nan")


def _adaptive_regime_scales(
    bounded_signal: pd.Series,
    short_window: int = 30,
    long_window: int = 252,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Estimate volatility-regime-aware scaling for heat and attention."""
    # Use first differences of bounded signal as a scale-free realized-vol proxy.
    realized_vol = bounded_signal.diff().abs().rolling(
        short_window,
        min_periods=max(5, short_window // 3),
    ).mean()
    baseline_vol = realized_vol.rolling(
        long_window,
        min_periods=max(20, long_window // 6),
    ).median()

    vol_ratio = (
        realized_vol
        / baseline_vol.replace({0.0: np.nan})
    ).replace([np.inf, -np.inf], np.nan)
    vol_ratio = vol_ratio.fillna(1.0).clip(lower=0.25, upper=4.0)

    # In high-vol regimes, reduce directional confidence and elevate attention.
    heat_scale = vol_ratio.pow(-0.35).clip(lower=0.70, upper=1.35)
    attention_scale = vol_ratio.pow(0.35).clip(lower=0.70, upper=1.45)
    return heat_scale, attention_scale, vol_ratio


def robust_bounded_signal(
    series: pd.Series,
    window: int = 365,
    min_periods: int = 90,
    lower_q: float = 0.05,
    upper_q: float = 0.95,
) -> pd.Series:
    """Compute a rolling, winsorized robust-z score bounded into [-1, 1]."""
    values = series.astype(float)
    result = pd.Series(index=values.index, dtype=float)

    for i in range(len(values)):
        start = max(0, i - window + 1)
        window_values = values.iloc[start : i + 1].dropna()

        if len(window_values) < min_periods:
            result.iloc[i] = np.nan
            continue

        low = window_values.quantile(lower_q)
        high = window_values.quantile(upper_q)

        clipped_window = window_values.clip(lower=low, upper=high)
        current_raw = values.iloc[i]
        current = float(np.clip(current_raw, low, high))

        median = float(clipped_window.median())
        scale = _safe_scale(clipped_window, median)

        if np.isnan(scale):
            result.iloc[i] = 0.0
            continue

        robust_z = (current - median) / scale
        result.iloc[i] = np.tanh(robust_z / 3.0)

    return result


def build_feature_frame(
    raw_series: pd.Series,
    base_reliability: float = 1.0,
    max_carry_days: int = 7,
    direction: float = 1.0,
    smooth_window: int = 7,
) -> pd.DataFrame:
    observed_raw = raw_series.astype(float)
    observed_mask = observed_raw.notna()

    carried = observed_raw.ffill()
    if max_carry_days <= 0:
        carried = observed_raw.copy()
        age_days = pd.Series(np.where(observed_mask, 0.0, np.nan), index=observed_raw.index, dtype=float)
    else:
        obs_idx = pd.Series(pd.NaT, index=observed_raw.index, dtype="datetime64[ns]")
        obs_idx.loc[observed_mask] = observed_raw.index[observed_mask]
        last_obs = obs_idx.ffill()
        age_delta = observed_raw.index.to_series().sub(last_obs)
        age_days = age_delta.dt.days.astype(float)
        carried.loc[age_days > float(max_carry_days)] = np.nan

    bounded = robust_bounded_signal(carried)
    heat_regime_scale, attention_regime_scale, volatility_ratio = _adaptive_regime_scales(bounded)

    base_heat = direction * bounded
    signed_heat = (base_heat * heat_regime_scale).clip(lower=-1.0, upper=1.0)

    # Surprise captures short-horizon acceleration beyond level-only extremeness.
    level_impulse = np.tanh(base_heat.diff(5).abs() / 0.35)
    relative_raw_impulse = (
        (carried - carried.shift(1)).abs() / (carried.shift(1).abs() + EPSILON)
    ).replace([np.inf, -np.inf], np.nan)
    raw_impulse = np.tanh(relative_raw_impulse / 0.20)
    surprise = np.maximum(level_impulse.fillna(0.0), raw_impulse.fillna(0.0)).clip(0.0, 1.0)
    attention_level = base_heat.abs().clip(0.0, 1.0)
    attention = (
        (0.65 * attention_level + 0.35 * surprise) * attention_regime_scale
    ).clip(0.0, 1.0)

    availability = carried.notna().astype(float)
    if max_carry_days <= 0:
        freshness = observed_mask.astype(float)
    else:
        freshness = (1.0 - (age_days / float(max_carry_days))).clip(lower=0.0, upper=1.0).fillna(0.0)
    rolling_availability = availability.rolling(smooth_window, min_periods=1).mean()
    rolling_freshness = freshness.rolling(smooth_window, min_periods=1).mean()
    reliability = (rolling_availability * rolling_freshness * base_reliability).clip(0.0, 1.0)

    frame = pd.DataFrame(
        {
            "signed_heat": signed_heat.rolling(smooth_window, min_periods=1).mean().clip(-1.0, 1.0),
            "attention": attention.rolling(smooth_window, min_periods=1).mean().clip(0.0, 1.0),
            "reliability": reliability,
            "freshness": freshness.clip(0.0, 1.0),
            "age_days": age_days,
            "raw": observed_raw,
            "raw_carried": carried,
            "surprise": surprise.rolling(smooth_window, min_periods=1).mean().clip(0.0, 1.0),
            "regime_volatility_ratio": volatility_ratio.rolling(smooth_window, min_periods=1).mean().clip(0.25, 4.0),
            "heat_regime_scale": heat_regime_scale.rolling(smooth_window, min_periods=1).mean().clip(0.70, 1.35),
            "attention_regime_scale": attention_regime_scale.rolling(smooth_window, min_periods=1).mean().clip(0.70, 1.45),
        },
        index=observed_raw.index,
    )

    return frame
