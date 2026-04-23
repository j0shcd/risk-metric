from __future__ import annotations

import numpy as np
import pandas as pd


def _log_regression_deviation(series: pd.Series) -> pd.Series:
    valid = series.dropna()
    if len(valid) < 30:
        return pd.Series(index=series.index, dtype=float)

    # Deterministic power-law-like log fit using log(time) and log(price).
    t = np.arange(len(valid), dtype=float) + 1.0
    x = np.log(t)
    y = np.log(valid.values)

    slope, intercept = np.polyfit(x, y, deg=1)
    y_hat = intercept + slope * x
    model = np.exp(y_hat)

    deviation = valid.values / model
    out = pd.Series(index=series.index, dtype=float)
    out.loc[valid.index] = deviation
    return out


def build_market_features(
    btc_price: pd.Series,
    total_market_cap: pd.Series,
) -> pd.DataFrame:
    frame = pd.DataFrame(index=btc_price.index)

    frame["btc_trend_extension_50d_350d"] = (
        btc_price.rolling(50, min_periods=50).mean()
        / btc_price.rolling(350, min_periods=350).mean()
    )
    frame["btc_running_roi_1y"] = btc_price.pct_change(365, fill_method=None)
    frame["btc_log_reg_deviation"] = _log_regression_deviation(btc_price)

    frame["total_trend_extension_50d_350d"] = (
        total_market_cap.rolling(50, min_periods=50).mean()
        / total_market_cap.rolling(350, min_periods=350).mean()
    )
    frame["total_running_roi_1y"] = total_market_cap.pct_change(365, fill_method=None)
    frame["total_log_reg_deviation"] = _log_regression_deviation(total_market_cap)

    frame["btc_dominance_proxy"] = (btc_price / btc_price.max()) / (total_market_cap / total_market_cap.max())

    return frame
