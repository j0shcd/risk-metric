"""Causal slow cost displacement with occupancy memory; research only."""
from __future__ import annotations

import numpy as np
import pandas as pd

PARAMETERS = {
    "anchor_halflife_days": 365.0,
    "memory_halflife_days": 180.0,
    "log_displacement_scale": 1.0,
    "memory_weight": 0.5,
    "observation_lag_days": 1,
}


def generate_indicator(observations: pd.DataFrame, dates=None, *, memory_weight=0.5,
                       anchor_halflife_days=365.0, memory_halflife_days=180.0):
    """Return a finite risk score on requested month ends from Date/Price data.

    Uses actual elapsed days, a one-calendar-day observation lag, and no labels.
    Empty history is neutral. No price-volume interpretation of cost is claimed.
    """
    if not 0 <= memory_weight <= 1:
        raise ValueError("memory_weight must be in [0,1]")
    if anchor_halflife_days <= 0 or memory_halflife_days <= 0:
        raise ValueError("halflives must be positive")
    frame = observations.loc[:, ["Date", "Price"]].copy()
    frame["Date"] = pd.to_datetime(frame["Date"], utc=True).dt.tz_localize(None).dt.normalize()
    frame["Price"] = pd.to_numeric(frame["Price"], errors="raise")
    frame = frame.sort_values("Date")
    if frame["Date"].duplicated().any() or frame["Date"].isna().any():
        raise ValueError("observation dates must be unique and nonmissing")
    if not np.isfinite(frame["Price"]).all() or (frame["Price"] <= 0).any():
        raise ValueError("prices must be positive and finite")
    if dates is None:
        if frame.empty:
            return pd.Series(dtype=float, name="swing_a")
        dates = pd.date_range(frame["Date"].min(), frame["Date"].max(), freq="ME")
    queries = pd.DatetimeIndex(pd.to_datetime(dates, utc=True)).tz_localize(None).normalize()
    if queries.has_duplicates or queries.hasnans:
        raise ValueError("query dates must be unique and nonmissing")
    values, last_day, anchor, memory = [], None, None, 0.0
    for day, price in frame.itertuples(index=False, name=None):
        log_price = float(np.log(price))
        if last_day is None:
            anchor = log_price
        else:
            elapsed = (day - last_day).days
            anchor_alpha = -np.expm1(-np.log(2) * elapsed / anchor_halflife_days)
            anchor += anchor_alpha * (log_price - anchor)
        displacement = np.tanh((log_price - anchor) / PARAMETERS["log_displacement_scale"])
        if last_day is not None:
            memory_alpha = -np.expm1(-np.log(2) * (day - last_day).days / memory_halflife_days)
            memory += memory_alpha * (displacement - memory)
        risk = 0.5 + 0.5 * ((1-memory_weight) * displacement + memory_weight * memory)
        values.append((day + pd.Timedelta(days=1), risk))
        last_day = day
    if not values:
        return pd.Series(0.5, index=queries, name="swing_a")
    available = pd.Series(dict(values)).sort_index()
    result = available.reindex(available.index.union(queries)).sort_index().ffill().reindex(queries).fillna(0.5)
    result.name = "swing_a"
    return result
