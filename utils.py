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
    Normalizes risk levels between 0 and 1 and applies diminishing returns if alpha and beta are provided.
    """
    risk_levels_min = risk_levels.min()
    risk_levels_max = risk_levels.max()
    normalized_risk = (risk_levels - risk_levels_min) / (risk_levels_max - risk_levels_min)
    
    return normalized_risk

def apply_diminishing_returns(risk, coefficients):
    """
    Applies a diminishing returns function to the risk levels.
    `alpha` and `beta` should be the coefficients from the price regression.
    """
    ### delete line when want to Re-enable diminishing returns:
    coefficients = None
    if coefficients is None:
        print("No regression coefficients; Diminishing returns not applied.")
        return risk
    
    current_time = np.arange(len(risk))
    decay_factor = np.exp(np.polyval(coefficients, current_time))
    adjusted_risk = risk * decay_factor
    return adjusted_risk
