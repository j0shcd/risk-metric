"""Causal path-asymmetry candidate; no fitted parameters or outcome labels."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd


def generate(prices: pd.Series, window: int = 24) -> pd.Series:
    """Monthly upside return energy share, on completed calendar months only."""
    if window < 2:
        raise ValueError('window must be at least two months')
    prices = prices.sort_index()
    if prices.index.has_duplicates or not isinstance(prices.index, pd.DatetimeIndex):
        raise ValueError('prices must have unique dated observations')
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError('prices must be finite and positive')
    if prices.empty:
        return pd.Series(dtype=float, name='swing_c')
    monthly = prices.resample('ME').last()
    monthly = monthly[monthly.index <= prices.index.max()]
    returns = np.log(monthly).diff()
    up = returns.clip(lower=0).pow(2).rolling(window, min_periods=2).sum()
    down = returns.clip(upper=0).pow(2).rolling(window, min_periods=2).sum()
    return (100 * up.div((up + down).replace(0, np.nan))).fillna(50).rename('swing_c')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    frame = pd.read_csv(args.input_dir / 'btc_daily.csv', parse_dates=['Date'])
    generate(frame.set_index('Date')['Price']).rename_axis('Date').to_csv(args.output)


if __name__ == '__main__':
    main()
