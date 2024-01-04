import numpy as np
import pandas as pd

from dataRetrieval import BinanceAPI
from dataRetrieval import get_historical_data

def calculate_sma(prices, window):
    """
    Calculates Simple Moving Average 
    """
    sma = prices.rolling(window=window).mean()
    return sma


def get_historical_smas(daily_data_path, daily_window, weekly_window):
    """
    Retrieves historical SMAs and the original price data in the same DataFrame
    """
    daily_data = get_historical_data(daily_data_path)

    # # Ensure the index is a DatetimeIndex for resampling to work
    # if not isinstance(weekly_data.index, pd.DatetimeIndex):
    daily_data.set_index('Date', inplace=True)

    daily_data['Daily_SMA'] = calculate_sma(daily_data['Price'], window=daily_window)
    daily_data['Weekly_SMA'] = calculate_sma(daily_data['Price'], window=weekly_window)

    return daily_data