import numpy as np
import pandas as pd

import processing as proc
import visualization as viz
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler

import utils as utils

"""
INDIVIDUAL INDICATOR RISKS
"""

def simple_risk(daily_data_path, plot=False):
    data = proc.get_historical_smas(daily_data_path=daily_data_path, 
                                    daily_window=50, 
                                    weekly_window=350)
    

    data['simple_risk'] = data['Daily_SMA']/data['Weekly_SMA']

    data['simple_risk'] = utils.normalize_risk_metric(data['simple_risk'])

    # data.to_csv('./Data/combined_data.csv')
    if plot:
        viz.plot_simple_risk(data)

    return data[['Price', 'simple_risk']]


def log_risk(daily_data_path, plot=False):
    data = proc.calculate_log_regression_overvaluation(data_path=daily_data_path, extension_years=3, plot=plot)

    if plot:
        viz.plot_overvaluation(data)
        viz.plot_log_fit(data)

    # NEED TO NORMALIZE IT
    data['overvaluation_risk'] = utils.normalize_risk_metric(data['Overvaluation'])

    return data[['Price', 'overvaluation_risk']]


"""
COMPOUND RISK MODELS (COMPRISING MULTIPLE INDICATORS)
"""

def average_risk(daily_data_path, plot=False, weight_log=1, weight_sma=1):
    # Get the individual indicators
    sma_risk = simple_risk(daily_data_path)
    overvaluation_risk = log_risk(daily_data_path)

    # Merge the two dataframes on their index (Date)
    avg_risk = pd.merge(sma_risk, overvaluation_risk, left_index=True, right_index=True, suffixes=('', '_ovr'))

    # Remove the 'Price_ovr' column
    avg_risk = avg_risk.drop(columns=['Price_ovr'])

    # Calculate the average risk using the specified weights
    avg_risk['risk_levels'] = (weight_sma * avg_risk['simple_risk'] + weight_log * avg_risk['overvaluation_risk']) / (weight_log + weight_sma)

    print(avg_risk.sample(20))

    if plot:
        viz.plot_risk_and_price(avg_risk[['Price', 'risk_levels']])

    return avg_risk[['Price', 'risk_levels']]
