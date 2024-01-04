import pandas as pd
import numpy as np

def cleanCSV(file_path):
    df = pd.read_csv(file_path, parse_dates=['Date'])
    df.sort_values('Date', inplace=True)
    df.set_index('Date', inplace=True)

    # Replace commas in the 'Price', 'Open', 'High', 'Low' columns and convert them to floats
    price_columns = ['Price', 'Open', 'High', 'Low']
    for col in price_columns:
        # Convert to string if not already, then replace and convert to float
        df[col] = df[col].astype(str).str.replace(',', '').astype(float).round(2)

    # Convert 'Change %' from percentage to a float
    df['Change %'] = df['Change %'].astype(str).str.rstrip('%').astype(float) / 100
    df['Change %'] = df['Change %'].round(2)

    # Convert 'Vol.' and round to 2 decimal places
    df['Vol.'] = df['Vol.'].apply(convert_volume).round(2)

    df.to_csv(file_path, float_format='%.2f')  # This ensures the CSV will save numbers with two decimal points

def convert_volume(vol):
    if pd.isna(vol):
        return np.nan
    if isinstance(vol, str):  # Check if vol is a string
        try:
            if 'K' in vol:
                return float(vol.replace('K', '')) * 1e3
            elif 'M' in vol:
                return float(vol.replace('M', '')) * 1e6
            elif 'B' in vol:
                return float(vol.replace('B', '')) * 1e9
            else:
                return float(vol)  # If no suffix, convert directly to float
        except ValueError:
            return np.nan  # Handle cases where conversion is not possible
    elif isinstance(vol, (int, float)):
        return float(vol)  # If vol is already a number, just return it as float
    else:
        return np.nan  # Handle other unexpected cases

