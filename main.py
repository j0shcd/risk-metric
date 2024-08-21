import sys
import models as models
from update import update_data
from cleanCSV import cleanCSV
from config import REPO_PATH

if __name__ == '__main__':
    daily_data_path = f"{REPO_PATH}/data/btc_daily.csv"
    weekly_data_path = f"{REPO_PATH}/data/btc_weekly.csv"

    # Check if the script is run with the 'no-plot' argument
    no_plot = '--no-plot' in sys.argv

    # Check if the update function added new data
    data_updated = update_data(daily_data_path, weekly_data_path)

    # If new data was added, clean the CSV
    if data_updated:
        cleanCSV(daily_data_path)
        cleanCSV(weekly_data_path)

    # models.MA_risk(daily_data_path, plot=True)
    # models.log_risk(daily_data_path, plot=True)
    models.average_risk(daily_data_path, 
                        MA = "SMA", 
                        plot = not no_plot, 
                        weight_log=0, # turned off log
                        weight_sma=1)
    
