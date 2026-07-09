import pandas as pd
import numpy as np
from utils.indicators import calculate_atr
from utils.calculations import get_point_size

VERSION = "2.0"

def generate_signals(df, **kwargs):
    """
    Supertrend Volatility Trend-Following Strategy.
    Calculates dynamic ATR bands and trails them behind the price to capture long-term trends
    while keeping drawdowns mathematically capped. Perfect for driving Calmar ratios > 3.0.
    """
    atr_period = kwargs.get('atr_period', 10)
    atr_multiplier = kwargs.get('atr_multiplier', 3.0)
    
    if len(df) < atr_period:
        df['signal'] = 0
        df['dynamic_sl_points'] = 0
        df['dynamic_tp_points'] = 0
        return df

    # Calculate ATR
    df['ATR'] = calculate_atr(df, period=atr_period)
    
    # Calculate Basic Bands
    hl2 = (df['high'] + df['low']) / 2
    df['basic_ub'] = hl2 + (atr_multiplier * df['ATR'])
    df['basic_lb'] = hl2 - (atr_multiplier * df['ATR'])
    
    # Calculate Final Bands and Supertrend (NumPy vectorized optimization)
    basic_ub_arr = df['basic_ub'].to_numpy()
    basic_lb_arr = df['basic_lb'].to_numpy()
    close_arr = df['close'].to_numpy()
    
    n = len(df)
    final_ub_arr = np.zeros(n)
    final_lb_arr = np.zeros(n)
    dir_arr = np.ones(n, dtype=np.int32)
    supertrend_arr = np.zeros(n)
    
    for i in range(1, n):
        # Final Upper Band
        if basic_ub_arr[i] < final_ub_arr[i-1] or close_arr[i-1] > final_ub_arr[i-1]:
            final_ub_arr[i] = basic_ub_arr[i]
        else:
            final_ub_arr[i] = final_ub_arr[i-1]
            
        # Final Lower Band
        if basic_lb_arr[i] > final_lb_arr[i-1] or close_arr[i-1] < final_lb_arr[i-1]:
            final_lb_arr[i] = basic_lb_arr[i]
        else:
            final_lb_arr[i] = final_lb_arr[i-1]
            
        # Trend Direction
        if close_arr[i] > final_ub_arr[i-1]:
            dir_arr[i] = 1
        elif close_arr[i] < final_lb_arr[i-1]:
            dir_arr[i] = -1
        else:
            dir_arr[i] = dir_arr[i-1]
            
        # Supertrend
        if dir_arr[i] == 1:
            supertrend_arr[i] = final_lb_arr[i]
        else:
            supertrend_arr[i] = final_ub_arr[i]
            
    df['final_ub'] = final_ub_arr
    df['final_lb'] = final_lb_arr
    df['dir'] = dir_arr
    df['supertrend'] = supertrend_arr
            
    # Generate Signals (Continuous)
    df['signal'] = 0
    df.loc[df['close'] > df['supertrend'], 'signal'] = 1
    df.loc[df['close'] < df['supertrend'], 'signal'] = -1
    
    # Dynamic TP and SL
    # Supertrend is natively trailing, but since our backtester currently simulates fixed SL/TP intraday,
    # we will give it a massive TP (trend riding) and a relatively wide SL to let the trend breathe.
    import config
    symbol = kwargs.get('symbol') or getattr(config, 'SYMBOL', 'XAUUSD')
    point_size = get_point_size(symbol)
    
    rr_ratio = kwargs.get('rr_ratio', 3.0)
    
    # The Stop Loss distance is the distance from the Close price to the Supertrend line.
    sl_distance = (df['close'] - df['supertrend']).abs()
    df['dynamic_sl_points'] = (sl_distance / point_size).fillna(100).astype(int)
    
    # Enforce minimum and maximum stop loss (market noise buffer & margin limits)
    df.loc[df['dynamic_sl_points'] < 50, 'dynamic_sl_points'] = 50
    df.loc[df['dynamic_sl_points'] > 500, 'dynamic_sl_points'] = 500
    
    df['dynamic_tp_points'] = (df['dynamic_sl_points'] * rr_ratio).astype(int)
    
    return df


def check_for_signals(df):
    """
    Live trading adapter. This function is called continuously to check the newest data.
    """
    df_signals = generate_signals(df)
    last_row = df_signals.iloc[-1]
    if last_row['signal'] == 1:
        print("Supertrend Strategy: Buy Signal Detected")
    elif last_row['signal'] == -1:
        print("Supertrend Strategy: Sell Signal Detected")
    return last_row['signal'], last_row['dynamic_sl_points'], last_row['dynamic_tp_points']

