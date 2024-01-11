import numpy as np
import pandas as pd

from dataRetrieval import BinanceAPI
from dataRetrieval import get_historical_data

from visualization import plot_log_fit

import utils as utils


def get_historical_smas(daily_data_path, daily_window, weekly_window):
    """
    Retrieves historical Simple MAs and the original price data in the same DataFrame
    """
    daily_data = get_historical_data(daily_data_path)

    # # Ensure the index is a DatetimeIndex for resampling to work
    # if not isinstance(weekly_data.index, pd.DatetimeIndex):
    daily_data.set_index('Date', inplace=True)

    daily_data['Daily_SMA'] = utils.calculate_sma(daily_data['Price'], window=daily_window)
    daily_data['Weekly_SMA'] = utils.calculate_sma(daily_data['Price'], window=weekly_window)

    return daily_data


def get_historical_emas(daily_data_path, daily_window, weekly_window):
    """
    Retrieves historical Exponential MAs and the original price data in the same DataFrame
    """
    daily_data = get_historical_data(daily_data_path)

    # # Ensure the index is a DatetimeIndex for resampling to work
    # if not isinstance(weekly_data.index, pd.DatetimeIndex):
    daily_data.set_index('Date', inplace=True)

    daily_data['Daily_SMA'] = utils.calculate_ema(daily_data['Price'], window=daily_window)
    daily_data['Weekly_SMA'] = utils.calculate_ema(daily_data['Price'], window=weekly_window)

    return daily_data

def calculate_log_regression_overvaluation(data_path, extension_years=3, plot=False):
    # Load the data
    data = get_historical_data(data_path)
    data.set_index('Date', inplace=True)

    # Check for non-positive values in the price data
    if (data['Price'] <= 0).any():
        raise ValueError("Price data contains non-positive values.")

    # Perform logarithmic regression (fit a curve to the log of the prices)
    t = np.arange(len(data))
    price_log = np.log(data['Price'])
    coefficients = np.polyfit(t, price_log, 3.5)  # hyperbolic fit to the log of the prices

    # Prepare the extended time series
    freq = pd.infer_freq(data.index)
    future_periods = extension_years * 365  # Assuming daily data, adjust for other frequencies
    future_index = pd.date_range(start=data.index[-1] + pd.Timedelta(days=1), periods=future_periods, freq=freq)
    extended_t = np.arange(len(data) + len(future_index))

    # Calculate the model's price
    extended_price_log = np.polyval(coefficients, extended_t)
    data['Model_Price'] = np.exp(extended_price_log[:len(t)])  # Only for the original period

    # Calculate the overvaluation/undervaluation metric
    data['overvaluation_risk'] = data['Price'] / data['Model_Price']

    # Return only the original date range data if not plotting
    if not plot:
        return data[['Price', 'overvaluation_risk']], coefficients
    else:
        data = data.reindex(data.index.union(future_index))  # Include future dates if plotting
        data.loc[future_index, 'Model_Price'] = np.exp(extended_price_log[len(t):])
        return data[['Price', 'overvaluation_risk', 'Model_Price']], coefficients

