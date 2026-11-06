"""Causal local-linear trend innovations; no outcome labels or fitted cutoffs."""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

VARIANTS = {
    'swing_b_adaptive': {'alpha': 0.08, 'beta': 0.004, 'damping': 0.98},
    'swing_b_slow': {'alpha': 0.04, 'beta': 0.002, 'damping': 0.98},
    'swing_b_fast': {'alpha': 0.16, 'beta': 0.008, 'damping': 0.98},
}

def monthly_prices(frame: pd.DataFrame) -> pd.Series:
    dates = pd.to_datetime(frame['Date'], errors='raise')
    prices = pd.to_numeric(frame['Price'], errors='raise')
    if dates.duplicated().any() or dates.isna().any():
        raise ValueError('Dates must be unique and nonmissing')
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError('Prices must be positive and finite')
    daily = pd.Series(prices.to_numpy(), index=pd.DatetimeIndex(dates)).sort_index()
    if daily.empty:
        raise ValueError('No prices')
    # Emit only completed calendar months; never date a partial month in the future.
    monthly = daily.resample('ME').last()
    monthly = monthly.loc[monthly.index <= daily.index.max()]
    if monthly.isna().any():
        raise ValueError('Missing entire calendar month')
    return monthly

def filter_risk(prices: pd.Series, *, alpha: float, beta: float, damping: float) -> pd.Series:
    """Update after output. State corrections bounded at four trailing return scales.

    Start level at first log price, slope zero, absolute monthly return scale .25.
    Scale has EW alpha 1/24 and floor .05; residual output remains unclipped.
    Model is structural reconstruction fixed in 2026, not a historical deployment.
    """
    if prices.empty:
        return pd.Series(index=prices.index, dtype=float)
    logs = np.log(prices.to_numpy(dtype=float))
    level, slope, scale = logs[0], 0., .25
    scores = []
    for i, current in enumerate(logs):
        prediction = level + damping * slope
        innovation = current - prediction
        scores.append(50. + 50. * np.tanh(innovation / (4. * scale)))
        correction = np.clip(innovation, -4. * scale, 4. * scale)
        level = prediction + alpha * correction
        slope = damping * slope + beta * correction
        if i:
            scale = max(.05, (23. * scale + abs(current - logs[i - 1])) / 24.)
    return pd.Series(scores, index=prices.index, dtype=float)

def generate(frame: pd.DataFrame) -> pd.DataFrame:
    prices = monthly_prices(frame)
    return pd.DataFrame({name: filter_risk(prices, **params) for name, params in VARIANTS.items()}).rename_axis('Date')

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    generate(pd.read_csv(args.inputs / 'btc_daily.csv')).to_csv(args.output)

if __name__ == '__main__':
    main()
