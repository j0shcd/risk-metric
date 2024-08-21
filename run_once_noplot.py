import schedule
import time
import subprocess
import sys
import yagmail
from datetime import datetime
from config import REPO_PATH

def run_main_script():
    print(f"Running main script at {datetime.now()}")
    subprocess.run([sys.executable, f"{REPO_PATH}/main.py", "--no-plot"])
    print(f"Finished running main script at {datetime.now()}")

if __name__ == "__main__":
    run_main_script()