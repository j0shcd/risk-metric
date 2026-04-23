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
    direction: float = 1.0,
    smooth_window: int = 7,
) -> pd.DataFrame:
    bounded = robust_bounded_signal(raw_series)
    signed_heat = (direction * bounded).clip(lower=-1.0, upper=1.0)
    attention = signed_heat.abs().clip(upper=1.0)

    availability = raw_series.notna().astype(float)
    reliability = (availability.rolling(smooth_window, min_periods=1).mean() * base_reliability).clip(0.0, 1.0)

    frame = pd.DataFrame(
        {
            "signed_heat": signed_heat.rolling(smooth_window, min_periods=1).mean().clip(-1.0, 1.0),
            "attention": attention.rolling(smooth_window, min_periods=1).mean().clip(0.0, 1.0),
            "reliability": reliability,
            "raw": raw_series,
        },
        index=raw_series.index,
    )

    return frame
