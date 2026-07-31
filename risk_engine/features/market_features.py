from __future__ import annotations

import numpy as np
import pandas as pd


def _log_regression_deviation(series: pd.Series, min_periods: int = 30) -> pd.Series:
    """Return a causal expanding power-law deviation.

    Each fitted value uses only observations available on or before that date.
    The cumulative-sum formulation keeps the expanding fit linear in the
    number of observations rather than refitting every prefix independently.
    """
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric[numeric > 0.0].dropna()
    out = pd.Series(index=series.index, dtype=float)
    if len(valid) < max(int(min_periods), 2):
        return out

    x = np.log(np.arange(1, len(valid) + 1, dtype=float))
    y = np.log(valid.to_numpy(dtype=float))
    count = np.arange(1, len(valid) + 1, dtype=float)
    sum_x = np.cumsum(x)
    sum_y = np.cumsum(y)
    sum_xx = np.cumsum(x * x)
    sum_xy = np.cumsum(x * y)
    denominator = count * sum_xx - sum_x * sum_x

    slope = np.divide(
        count * sum_xy - sum_x * sum_y,
        denominator,
        out=np.full_like(count, np.nan),
        where=np.abs(denominator) > 1e-12,
    )
    intercept = (sum_y - slope * sum_x) / count
    fitted = np.exp(intercept + slope * x)
    deviation = valid.to_numpy(dtype=float) / fitted
    deviation[count < max(int(min_periods), 2)] = np.nan
    out.loc[valid.index] = deviation
    return out


def _rolling_realized_volatility(series: pd.Series, window: int = 30) -> pd.Series:
    returns = np.log(series.astype(float)).diff()
    return returns.rolling(window, min_periods=max(10, window // 3)).std(ddof=0) * np.sqrt(365.0)


def _drawdown_from_ath(series: pd.Series) -> pd.Series:
    values = series.astype(float)
    rolling_peak = values.cummax()
    return (values / rolling_peak.replace({0.0: np.nan}) - 1.0).clip(lower=-1.0, upper=0.0)


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
    frame["btc_drawdown_from_ath"] = _drawdown_from_ath(btc_price)
    frame["btc_realized_vol_30d"] = _rolling_realized_volatility(btc_price, window=30)

    frame["total_trend_extension_50d_350d"] = (
        total_market_cap.rolling(50, min_periods=50).mean()
        / total_market_cap.rolling(350, min_periods=350).mean()
    )
    frame["total_running_roi_1y"] = total_market_cap.pct_change(365, fill_method=None)
    frame["total_log_reg_deviation"] = _log_regression_deviation(total_market_cap)
    frame["total_drawdown_from_ath"] = _drawdown_from_ath(total_market_cap)
    frame["total_realized_vol_30d"] = _rolling_realized_volatility(total_market_cap, window=30)

    # A direct price/market-cap ratio is scale-equivalent for downstream
    # normalization and remains stable when future rows are appended.
    frame["btc_dominance_proxy"] = btc_price / total_market_cap.replace({0.0: np.nan})

    return frame
