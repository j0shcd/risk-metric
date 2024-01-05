import models as models
from update import update_data
from cleanCSV import cleanCSV

if __name__ == '__main__':
    daily_data_path = './data/btc_daily.csv'
    weekly_data_path = './data/btc_weekly.csv'

    # Check if the update function added new data
    data_updated = update_data(daily_data_path, weekly_data_path)

    # If new data was added, clean the CSV
    if data_updated:
        cleanCSV(daily_data_path)
        cleanCSV(weekly_data_path)

    # models.simple_risk(daily_data_path, weekly_data_path)
    models.log_reg(daily_data_path)
    
