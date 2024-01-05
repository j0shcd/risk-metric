import processing as proc
import visualization as viz
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler

def simple_risk(daily_data_path, weekly_data_path):
    data = proc.get_historical_smas(daily_data_path=daily_data_path, 
                                    daily_window=50, 
                                    weekly_window=350)
    

    data['risk levels'] = data['Daily_SMA']/data['Weekly_SMA']
    
    # # Standardize the values
    # risk_levels_mean = data['risk levels'].mean()
    # risk_levels_std = data['risk levels'].std()
    # data['risk levels'] = (data['risk levels'] - risk_levels_mean) / risk_levels_std

    # Normalize the values
    risk_levels_min = data['risk levels'].min()
    risk_levels_max = data['risk levels'].max()
    data['risk levels'] = (data['risk levels'] - risk_levels_min) / (risk_levels_max - risk_levels_min)

    # data.to_csv('./Data/combined_data.csv')

    viz.plot_simple_risk(data)


def log_reg(daily_data_path):
    data = proc.calculate_log_regression_overvaluation(data_path=daily_data_path, extension_years=3)
    viz.plot_overvaluation(data)
    # viz.plot_log_fit(data)