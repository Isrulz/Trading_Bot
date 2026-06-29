import pandas as pd
import numpy as np
import config

def generate_signals(df):
    """
    Vectorized calculation of the Moving Average Crossover strategy.
    Returns the dataframe with 'signal' and 'dynamic_sl_points' columns.
    """
    slow_period = getattr(config, 'STRATEGY_SLOW_PERIOD', 200)
    fast_period = getattr(config, 'STRATEGY_FAST_PERIOD', 50)
    
    if len(df) < slow_period:
        df['signal'] = 0
        df['dynamic_sl_points'] = 0
        return df

    df['SMA_Fast'] = df['close'].rolling(window=fast_period).mean()
    df['SMA_Slow'] = df['close'].rolling(window=slow_period).mean()

    # Shifted values to avoid look-ahead bias and calculate cross
    df['SMA_Fast_prev'] = df['SMA_Fast'].shift(1)
    df['SMA_Slow_prev'] = df['SMA_Slow'].shift(1)

    # Buy Signal: Fast crosses ABOVE Slow
    buy_condition = (df['SMA_Fast_prev'] <= df['SMA_Slow_prev']) & (df['SMA_Fast'] > df['SMA_Slow'])
    # Sell Signal: Fast crosses BELOW Slow
    sell_condition = (df['SMA_Fast_prev'] >= df['SMA_Slow_prev']) & (df['SMA_Fast'] < df['SMA_Slow'])

    df['signal'] = 0
    df.loc[buy_condition, 'signal'] = 1
    df.loc[sell_condition, 'signal'] = -1
    
    df['dynamic_sl_points'] = 0  # Default to 0 so main uses config.STOP_LOSS_POINTS
    
    return df

def check_for_signals(df):
    """
    Adapter for LIVE mode to get the latest signal.
    """
    df_signals = generate_signals(df)
    last_row = df_signals.iloc[-1]
    
    if last_row['signal'] == 1:
        print("Strategy Engine: Bullish Crossover Detected (BUY SIGNAL)")
    elif last_row['signal'] == -1:
        print("Strategy Engine: Bearish Crossover Detected (SELL SIGNAL)")
        
    return last_row['signal'], last_row['dynamic_sl_points']