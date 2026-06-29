import os
from dotenv import load_dotenv

# 1. Safely load secrets from the .env file
load_dotenv()

# --- BROKER CREDENTIALS ---
# Casting login to an integer is required by the MT5 Python library
MT5_LOGIN = int(os.getenv("MT5_LOGIN")) 
MT5_PASSWORD = os.getenv("MT5_PASSWORD")
MT5_SERVER = os.getenv("MT5_SERVER")

# --- TRADING PARAMETERS ---
# By keeping these here, you can instantly reconfigure the bot
SYMBOL = "XAUUSD"
TIMEFRAME = "H1"          # 1-Hour candles
MAGIC_NUMBER = 999111     # Bot ID tag
RISK_PERCENT = 1.0        # Risk 1% of account balance per trade
MAX_SL_POINTS = 200       # Maximum allowed stop loss