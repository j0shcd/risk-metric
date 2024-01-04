import pandas as pd
import numpy as np

from binance.spot import Spot as Client
from cleanCSV import cleanCSV

def get_historical_data(file_path):
    try:
        df = pd.read_csv(file_path, parse_dates=['Date'])
        return df
    except Exception as e:
        print(f"An error occurred while reading the CSV file: {e}")
        raise


class BinanceAPI:
    def __init__(self):
        self.spot_client = Client(base_url='https://api1.binance.com')

    def get_new_data(self, symbol='BTCUSDT', interval='1d', datapoints=50):
        try:
            if datapoints < 1000:
                klines = self.spot_client.klines(symbol=symbol, interval=interval, limit=datapoints)
                return klines
            else:
                raise ValueError(f"Request limit exceeded: {datapoints} data points requested, must be under 1000.")
        except Exception as e:
            # Log the exception or handle it as needed
            print(f"An error occurred: {e}")
            raise