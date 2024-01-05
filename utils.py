import numpy as np
import pandas as pd

def calculate_sma(prices, window):
    """
    Calculates Simple Moving Average 
    """
    sma = prices.rolling(window=window).mean()
    return sma


def normalize_risk_metric(risk_levels):
    """
    normalizes risk levels between 0 and 1. 
    """
    risk_levels_min = risk_levels.min()
    risk_levels_max = risk_levels.max()
    normalized_risk = (risk_levels - risk_levels_min) / (risk_levels_max - risk_levels_min)
    return normalized_risk
