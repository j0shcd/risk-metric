import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler

def calculate_sma(prices, window):
    """
    Calculates Simple Moving Average 
    """
    sma = prices.rolling(window=window).mean()
    return sma


def calculate_ema(prices, window):
    """
    Calculates Exponential Moving Average (EMA) over a given window.
    
    :param prices: Pandas Series with the price data.
    :param window: Integer, the period over which to calculate the EMA.
    :return: Pandas Series with the EMA.
    """
    return prices.ewm(span=window, adjust=False).mean()

def normalize_risk_metric(risk_levels):
    """
    Normalizes risk levels between 0 and 1 
    """
    risk_levels_min = risk_levels.min()
    risk_levels_max = risk_levels.max()
    normalized_risk = (risk_levels - risk_levels_min) / (risk_levels_max - risk_levels_min)
    
    return normalized_risk

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def calculate_z_score(data):
    """
    Standardizes the data using Z-score standardization and applies the sigmoid function.
    """
    scaler = StandardScaler()
    z_scores = scaler.fit_transform(data.values.reshape(-1, 1)).flatten()
    sigmoid_scores = sigmoid(z_scores)
    return sigmoid_scores
