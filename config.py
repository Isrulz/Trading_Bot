import os
from dotenv import load_dotenv

# 1. Load the secrets from the .env file into the operating system's memory
load_dotenv()

# 2. Safely parse the credentials
_mt5_login_env = os.getenv("MT5_LOGIN")
MT5_LOGIN = int(_mt5_login_env) if _mt5_login_env else None
MT5_PASSWORD = os.getenv("MT5_PASSWORD")
MT5_SERVER = os.getenv("MT5_SERVER")
ENVIRONMENT = os.getenv("ENVIRONMENT", "SANDBOX")
MODE = os.getenv("MODE", "BACKTEST") # 'LIVE' or 'BACKTEST'

# 3. Define Global Trading Parameters
SYMBOL = "XAUUSD"
TIMEFRAME = 16385 # MT5 specific integer for H1 (1 Hour) timeframe
RISK_PERCENT = 1.0
STOP_LOSS_POINTS = 150
MAGIC_NUMBER = 999111
ACTIVE_STRATEGY = "volatility_trend" # 'mean_reversion', 'session_breakout', or 'volatility_trend'

# 4. Backtesting Parameters
BACKTEST_INITIAL_BALANCE = 10000.0
BACKTEST_DATA_FILE = "historical_data.csv"
TRAIN_SPLIT_RATIO = 0.70

# 5. ASIC Leverage Limits
ASIC_LEVERAGE_FOREX = 30
ASIC_LEVERAGE_GOLD = 20

# 6. Strategy Optimization Grids
GRID_MEAN_REVERSION = {
    'bb_period': [20, 50],
    'bb_std': [2.0, 2.5],
    'rsi_period': [14, 21],
    'rsi_overbought': [70, 75],
    'rsi_oversold': [30, 25]
}

GRID_SESSION_BREAKOUT = {
    'asian_session_end': [8], # 08:00 UTC
    'breakout_buffer_points': [10, 20],
    'volume_ma_period': [10, 20],
    'volume_factor': [1.0, 1.5]
}

GRID_VOLATILITY_TREND = {
    'atr_period': [10, 14],
    'keltner_mult': [1.5, 2.0],
    'macd_fast': [12],
    'macd_slow': [26],
    'macd_signal': [9]
}