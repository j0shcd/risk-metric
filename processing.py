import numpy as np
import pandas as pd

from dataRetrieval import BinanceAPI
from dataRetrieval import get_historical_data

from visualization import plot_log_fit

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

# def calculate_log_regression_overvaluation(data_path):
#     # Load the data
#     data = get_historical_data(data_path)
#     data.set_index('Date', inplace=True)

#     # Check for non-positive values in the price data
#     if (data['Price'] <= 0).any():
#         raise ValueError("Price data contains non-positive values.")

#     # Perform logarithmic regression (fit a line to the log of the prices)
#     t = np.arange(len(data))
#     price_log = np.log(data['Price'])
#     coefficients = np.polyfit(t, price_log, 3)  # hyperbolic fit to the log of the prices

#     # Calculate the model's price
#     data['Model_Price'] = np.exp(np.polyval(coefficients, t))

#     # Calculate the overvaluation/undervaluation metric
#     data['Overvaluation'] = data['Price'] / data['Model_Price']

#     return data[['Overvaluation', 'Price', 'Model_Price']]


def calculate_log_regression_overvaluation(data_path, extension_years=3):
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

    # Calculate the model's price for the extended time series
    extended_price_log = np.polyval(coefficients, extended_t)
    data = data.reindex(data.index.union(future_index))  # Reindex to include the future dates
    data['Model_Price'] = np.exp(extended_price_log)

    # Calculate the overvaluation/undervaluation metric
    data['Overvaluation'] = data['Price'] / data['Model_Price']

    return data[['Overvaluation', 'Price', 'Model_Price']]

    # Only return the 'Overvaluation' and 'Model_Price' for the original data range for 'Price'
    # return data.loc[:, ['Overvaluation', 'Model_Price']].iloc[:len(t)], data.loc[:, ['Model_Price']].iloc[len(t):]


