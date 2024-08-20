import schedule
import time
import subprocess
import sys
import yagmail
from datetime import datetime

def run_main_script():
    print(f"Running main script at {datetime.now()}")
    subprocess.run([sys.executable, "main.py", "--no-plot"])
    print(f"Finished running main script at {datetime.now()}")

# Schedule the job to run every 3 days
schedule.every(3).days.do(run_main_script)

# schedule.every(10).seconds.do(run_main_script)

if __name__ == "__main__":
    print(f"Scheduler started at {datetime.now()}")
    while True:
        schedule.run_pending()
        time.sleep(1)