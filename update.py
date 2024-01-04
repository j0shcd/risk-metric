import pandas as pd

from dataRetrieval import BinanceAPI

def update_data(daily_data_path, weekly_data_path):
    daily_updated = False
    weekly_updated = False

    # Calculate how many days and weeks of data are missing
    missing_days = get_data_recency(daily_data_path)
    missing_weeks = get_data_recency(weekly_data_path) // 7

    # Initialize Binance API
    binance = BinanceAPI()

    # Update daily data if needed
    if missing_days > 0:
        print(f"Adding {missing_days} missing days to {daily_data_path}...")

        new_daily_data = binance.get_new_data('BTCUSDT', '1d', missing_days)
        update_csv_with_binance_data(new_daily_data, daily_data_path)
        daily_updated = True
        print("done")
    else:
        print(f"{daily_data_path} is up to date!")


    # Update weekly data if needed
    if missing_weeks > 0:
        print(f"Adding {missing_weeks} missing weeks to {weekly_data_path}...")

        new_weekly_data = binance.get_new_data('BTCUSDT', '1w', missing_weeks)
        update_csv_with_binance_data(new_weekly_data, weekly_data_path)
        weekly_updated = True
        print("done")
    else:
        print(f"{weekly_data_path} is up to date!")

    return daily_updated or weekly_updated

def get_data_recency(file_path):
    """
    Returns the number of days since the last entry in the CSV file.
    """
    df = pd.read_csv(file_path, parse_dates=['Date'])
    last_date = df['Date'].max()
    current_date = pd.Timestamp.now()
    return (current_date - last_date).days

def update_csv_with_binance_data(bin_data, file_path):
    """
    Main function to format and append Binance data to CSV.
    """
    formatted_data = format_binance_data(bin_data)
    append_to_csv(file_path, formatted_data)

def format_binance_data(bin_data):
    """
    Formats data received from Binance API to match the CSV structure.
    """
    # Define the column names as per the Binance API format
    columns = ['Open Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close Time', 
               'Quote Asset Volume', 'Number of Trades', 'Taker Buy Base Asset Volume', 
               'Taker Buy Quote Asset Volume', 'Ignore']

    # Convert the data to a DataFrame
    formatted_data = pd.DataFrame(bin_data, columns=columns)

    # Convert timestamp to datetime for Open Time
    formatted_data['Open Time'] = pd.to_datetime(formatted_data['Open Time'], unit='ms')

    # Calculate 'Change %'
    formatted_data['Change %'] = ((formatted_data['Close'].astype(float) / 
                                  formatted_data['Open'].astype(float)) - 1) * 100
    formatted_data['Change %'] = formatted_data['Change %'].round(2)

    # Select and rename the columns to match your CSV format
    formatted_data = formatted_data[['Open Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Change %']]
    formatted_data.rename(columns={'Open Time': 'Date', 'Close': 'Price', 'Volume': 'Vol.'}, inplace=True)
    formatted_data.set_index('Date', inplace=True)

    # Format numbers with comma as thousands separator and one decimal place
    for col in ['Open', 'High', 'Low', 'Price', 'Vol.']:
        formatted_data[col] = formatted_data[col].astype(float).map('{:,.1f}'.format)

    print(formatted_data.head())
    return formatted_data

def append_to_csv(file_path, new_data):
    """
    Appends new formatted data to an existing CSV file, placing newer data at the beginning.
    """
    # Read existing data
    existing_data = pd.read_csv(file_path, parse_dates=['Date'])
    existing_data.set_index('Date', inplace=True)

    # Combine new and existing data
    updated_data = pd.concat([new_data, existing_data])

    # Drop duplicates to avoid any overlap
    updated_data = updated_data[~updated_data.index.duplicated(keep='first')]

    # Sort by date in descending order (newest first)
    updated_data.sort_index(ascending=True, inplace=True)

    # Write back to CSV
    updated_data.to_csv(file_path)
