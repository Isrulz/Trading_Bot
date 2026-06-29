import os
from dotenv import load_dotenv

# 1. Load the secrets from the .env file into the operating system's memory
load_dotenv()

# 2. Safely parse the credentials
# MT5 requires the login to be an integer, not a string
MT5_LOGIN = int(os.getenv("MT5_LOGIN"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD")
MT5_SERVER = os.getenv("MT5_SERVER")
ENVIRONMENT = os.getenv("ENVIRONMENT", "SANDBOX")

# 3. Define Global Trading Parameters
SYMBOL = "XAUUSD"
TIMEFRAME = 16385 # MT5 specific integer for H1 (1 Hour) timeframe
RISK_PERCENT = 1.0
STOP_LOSS_POINTS = 150
MAGIC_NUMBER = 999111