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

def MA_risk(daily_data_path, MA = "SMA", plot=False):

    if (MA=="SMA"):
        data = proc.get_historical_smas(daily_data_path=daily_data_path, 
                                        daily_window=50, 
                                        weekly_window=350)
    elif (MA=="EMA"):
        data = proc.get_historical_emas(daily_data_path=daily_data_path, 
                                        daily_window=50, 
                                        weekly_window=350)
    else: 
        raise Exception(f"Unknown moving average type. Given MA: {MA}")
    

    data['MA_risk'] = data['Daily_SMA']/data['Weekly_SMA']

    data['MA_risk'] = utils.calculate_z_score(data['MA_risk'])

    # data.to_csv('./Data/combined_data.csv')
    if plot:
        viz.plot_MA_risk(data)

    return data[['Price', 'MA_risk']]


def log_risk(daily_data_path, plot=False):
    data = proc.calculate_log_regression_overvaluation(data_path=daily_data_path, extension_years=3, plot=plot)

    if plot:
        viz.plot_overvaluation(data)
        viz.plot_log_fit(data)
     
    data['overvaluation_risk'] = utils.calculate_z_score(data['overvaluation_risk'])

    return data[['Price', 'overvaluation_risk']]


"""
COMPOUND RISK MODELS (COMPRISING MULTIPLE INDICATORS)
"""

def average_risk(daily_data_path, MA="SMA", plot=False, weight_log=1, weight_sma=1):
    # Get the individual risks
    sma_risk = MA_risk(daily_data_path=daily_data_path, 
                           MA=MA, 
                           plot=False)
    overvaluation_risk = log_risk(daily_data_path=daily_data_path, 
                                     plot=False)

    # Apply Z-score standardization and sigmoid scaling on individual risks
    sma_risk['standardized_MA_risk'] = utils.calculate_z_score(sma_risk['MA_risk'])
    overvaluation_risk['standardized_overvaluation_risk'] = utils.calculate_z_score(overvaluation_risk['overvaluation_risk'])

    # Merge the two dataframes on their index (Date)
    avg_risk = pd.merge(sma_risk[['Price', 'standardized_MA_risk']], 
                        overvaluation_risk[['Price', 'standardized_overvaluation_risk']], 
                        left_index=True, 
                        right_index=True, 
                        suffixes=('', '_ovr'))

    # Calculate the weighted average of the standardized risks
    avg_risk['average_risk'] = (weight_sma * avg_risk['standardized_MA_risk'] + 
                                weight_log * avg_risk['standardized_overvaluation_risk']) / (weight_log + weight_sma)

    # Normalize the average risk between 0 and 1
    avg_risk['risk_levels'] = utils.normalize_risk_metric(avg_risk['average_risk'])

    # Remove the 'Price_ovr' column
    avg_risk = avg_risk.drop(columns=['Price_ovr'])

    print(avg_risk.sample(10))

    if plot:
        # Assuming plot_risk_and_price function takes a dataframe with 'Price' and 'normalized_average_risk' columns
        viz.plot_risk_and_price(avg_risk[['Price', 'risk_levels']])
        # viz.plot_risk_color_coded(avg_risk[['Price', 'risk_levels']])
        # viz.interactive_color_coded_risk(avg_risk[['Price', 'risk_levels']])

    # Return the DataFrame with the new 'normalized_average_risk' column
    return avg_risk[['Price', 'risk_levels']]
