import pandas as pd
import config

def check_for_signals(df):
    """
    Calculates a Trend-Following Moving Average Crossover strategy.
    Returns a tuple: (signal, stop_loss_points)
    Signal: 1 (Buy), -1 (Sell), 0 (Hold)
    """
    # 1. Parameter Setup
    # Pull the periods from config.py, or default to 50 and 200 if they aren't there
    slow_period = getattr(config, 'STRATEGY_SLOW_PERIOD', 200)
    fast_period = getattr(config, 'STRATEGY_FAST_PERIOD', 50)
    
    # Safety check: We cannot calculate a 200-period average with only 100 candles
    if len(df) < slow_period:
        return 0, 0

    # 2. Calculate the Mathematical Indicators
    df['SMA_Fast'] = df['close'].rolling(window=fast_period).mean()
    df['SMA_Slow'] = df['close'].rolling(window=slow_period).mean()

    # 3. Extract the exact current and previous candle data to detect a "cross"
    current = df.iloc[-1]
    previous = df.iloc[-2]

    signal = 0
    # We return 0 here to instruct main.py to use your default config.STOP_LOSS_POINTS
    dynamic_sl_points = 0 

    # 4. Buy Logic: Fast moving average crosses ABOVE the Slow moving average
    if previous['SMA_Fast'] <= previous['SMA_Slow'] and current['SMA_Fast'] > current['SMA_Slow']:
        signal = 1
        print("Strategy Engine: Bullish Crossover Detected (BUY SIGNAL)")

    # 5. Sell Logic: Fast moving average crosses BELOW the Slow moving average
    elif previous['SMA_Fast'] >= previous['SMA_Slow'] and current['SMA_Fast'] < current['SMA_Slow']:
        signal = -1
        print("Strategy Engine: Bearish Crossover Detected (SELL SIGNAL)")

    return signal, dynamic_sl_points