import os
from dotenv import load_dotenv

# ==============================================================================
# TRADING BOT CONFIGURATION CENTER
# ==============================================================================
# This is the master control file for your trading bot. 
# Any changes you make here will globally affect how the bot trades, connects, 
# and runs backtests. Edit these values to suit your strategy.

# ------------------------------------------------------------------------------
# 1. ENVIRONMENT & SECRETS
# ------------------------------------------------------------------------------
# The load_dotenv() function securely loads your MT5 login credentials from 
# the 'credentials.env' file so they aren't hardcoded in plaintext.
load_dotenv()

_mt5_login_env = os.getenv("MT5_LOGIN")
MT5_LOGIN = int(_mt5_login_env) if _mt5_login_env else None
MT5_PASSWORD = os.getenv("MT5_PASSWORD")
MT5_SERVER = os.getenv("MT5_SERVER")

# ENVIRONMENT: "SANDBOX" for testing, "PRODUCTION" for real money.
ENVIRONMENT = os.getenv("ENVIRONMENT", "SANDBOX")

# MODE: 
# - "BACKTEST": Runs the bot instantly over historical data to test your strategy.
# - "LIVE": Connects to MT5 and trades live in the market.
MODE = os.getenv("MODE", "BACKTEST")


# ------------------------------------------------------------------------------
# 2. GLOBAL TRADING PARAMETERS
# ------------------------------------------------------------------------------
# SYMBOL: The financial asset you want to trade (e.g., "XAUUSD", "EURUSD").
SYMBOL = "GBPJPY"

# TIMEFRAME: The chart timeframe you are trading on.
# Common MT5 integer values:
# 1 = M1 (1 Minute)
# 5 = M5 (5 Minutes)
# 15 = M15 (15 Minutes)
# 16385 = H1 (1 Hour)
TIMEFRAME = 15 

# RISK_PERCENT: What percentage of your account balance you want to risk per trade.
# Example: 1.0 means you will lose exactly 1% of your account if the Stop Loss hits.
RISK_PERCENT = 1.0

# STOP_LOSS_POINTS: A fallback fixed Stop Loss distance (in points). 
# Strategies usually calculate this dynamically, but this acts as a safety net.
STOP_LOSS_POINTS = 150

# MAGIC_NUMBER: A unique ID attached to every trade the bot takes. 
# This ensures the bot only manages its own trades and doesn't touch your manual trades.
MAGIC_NUMBER = 999111

# ACTIVE_STRATEGY: Which strategy script the bot should use to find trades.
# Available options out-of-the-box:
# - "mean_reversion"
# - "pa_breakout"
# - "supertrend"
# - "tick_vwap"
# - "zscore_momentum"
ACTIVE_STRATEGY = "mean_reversion"


# ------------------------------------------------------------------------------
# 3. BACKTESTING ENGINE PARAMETERS
# ------------------------------------------------------------------------------
# BACKTEST_INITIAL_BALANCE: The starting virtual money for your backtest.
BACKTEST_INITIAL_BALANCE = 10000.0

# BACKTEST_DATA_FILE: The local file where historical data is cached.
BACKTEST_DATA_FILE = "historical_data.csv"

# TRAIN_SPLIT_RATIO: The percentage of data used for In-Sample Optimization vs Out-of-Sample.
# 0.60 means 60% of the timeline is used to find the best parameters, and 
# TEST_SPLIT_RATIO defines the validation window size.
TRAIN_SPLIT_RATIO = 0.6  # 60% of data used for training/optimisation
TEST_SPLIT_RATIO = 0.4   # 40% of data used for blind Out-Of-Sample validation (increased from 30%)
# SLIPPAGE_POINTS: Frictional cost deducted from every trade (in points).
SLIPPAGE_POINTS = 20


# ------------------------------------------------------------------------------
# 4. REGULATORY SAFEGUARDS (ASIC)
# ------------------------------------------------------------------------------
# Max leverage caps enforced by the Australian Securities & Investments Commission.
# The risk engine will throttle your lot sizes to ensure you never breach these.
ASIC_LEVERAGE_FOREX = 30
ASIC_LEVERAGE_GOLD = 20


# ------------------------------------------------------------------------------
# 5. STRATEGY OPTIMIZATION GRIDS
# ------------------------------------------------------------------------------
# When running in BACKTEST mode, the engine will cross-multiply every value 
# in these lists to find the absolute best combination of parameters (Grid Search).
# To test a single exact setting, just leave one number in the list (e.g., [20]).

GRID_MEAN_REVERSION = {
    'bb_period': [20, 50],
    'bb_std': [1.5, 2.0],
    'rsi_period': [14],
    'rsi_overbought': [70, 75],
    'rsi_oversold': [30, 25],
    'rr_ratio': [0.2, 0.3, 0.5, 1.0, 1.5, 2.0, 3.0], 
    'atr_sl_mult': [1.0, 1.5, 2.0]
}

GRID_PA_BREAKOUT = {
    'rsi_period': [14],
    'rsi_extreme': [35, 40], # RSI must be exhausted when breaking the daily level
    'lookback_days': [1, 2]
}

GRID_TICK_VWAP = {
    'vwap_period': [24, 48], 
    'dev_mult': [1.5, 2.0], 
    'rsi_filter': [60, 65] # Loosened from 70/80 to get more trades
}

GRID_ZSCORE_MOMENTUM = {
    'z_period': [20, 50],
    'z_entry': [1.5, 2.0], # Fade the extreme deviations
    'rr_ratio': [0.2, 0.3, 0.5, 1.0, 1.5, 2.0, 3.0],
    'atr_sl_mult': [1.0, 1.5, 2.0]
}

GRID_SUPERTREND = {
    'atr_period': [10, 14, 20],
    'atr_multiplier': [2.0, 3.0, 4.0],
    'rr_ratio': [2.0, 3.0, 5.0]
}