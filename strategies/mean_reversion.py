import pandas as pd
import numpy as np
from utils.indicators import calculate_rsi, calculate_bollinger_bands, calculate_atr
from utils.calculations import get_point_size

VERSION = "2.0"

def generate_signals(df, **kwargs):
    """
    Intraday Mean Reversion Strategy using Bollinger Bands and RSI.
    This strategy assumes that if the price moves too far away from the average (Bollinger Bands)
    and momentum is exhausted (RSI), the price will revert back to the mean.
    """
    # --- Strategy Parameters ---
    # Retrieve parameters from kwargs or use beginner-friendly defaults
    bb_period = kwargs.get('bb_period', 20)          # Number of candles for Bollinger Bands average
    bb_std = kwargs.get('bb_std', 2.0)               # Standard deviation multiplier for the bands
    rsi_period = kwargs.get('rsi_period', 14)        # Number of candles for RSI calculation
    rsi_overbought = kwargs.get('rsi_overbought', 70)# RSI level considered 'too high' (time to sell)
    rsi_oversold = kwargs.get('rsi_oversold', 30)    # RSI level considered 'too low' (time to buy)
    rr_ratio = kwargs.get('rr_ratio', 2.0)           # Risk/Reward multiplier
    atr_sl_mult = kwargs.get('atr_sl_mult', 1.0)     # ATR multiplier for Stop Loss

    # Ensure we have enough historical data to calculate our indicators
    if len(df) < max(bb_period, rsi_period):
        df['signal'] = 0
        df['dynamic_sl_points'] = 0
        df['dynamic_tp_points'] = 0
        return df

    # --- Indicator Calculation ---
    # Calculate Bollinger Bands
    df['Upper_BB'], df['SMA'], df['Lower_BB'] = calculate_bollinger_bands(df['close'], period=bb_period, std_dev_mult=bb_std)

    # Calculate RSI
    df['RSI'] = calculate_rsi(df['close'], period=rsi_period)

    # Mean reversion trades are usually quick, so we use a tight stop-loss (20 points)
    df['dynamic_sl_points'] = 20 

    # --- Setup for Signal Generation ---
    # We shift our indicators by 1 period. This is crucial in algorithmic trading to 
    # prevent "look-ahead bias". We make decisions based on the *previous* closed candle.
    df['close_prev'] = df['close'].shift(1)
    df['Upper_BB_prev'] = df['Upper_BB'].shift(1)
    df['Lower_BB_prev'] = df['Lower_BB'].shift(1)
    
    # Calculate ATR for dynamic Stop Loss
    df['ATR'] = calculate_atr(df, period=14)
    
    # Generate Buy and Sell conditions - Wait for cross back inside the bands
    buy_condition = (df['close_prev'] < df['Lower_BB_prev']) & (df['close'] > df['Lower_BB'])
    sell_condition = (df['close_prev'] > df['Upper_BB_prev']) & (df['close'] < df['Upper_BB'])
    
    # Generate Buy and Sell conditions (Continuous)
    df['signal'] = 0
    df.loc[buy_condition, 'signal'] = 1
    df.loc[sell_condition, 'signal'] = -1
    
    import config
    symbol = kwargs.get('symbol') or getattr(config, 'SYMBOL', 'XAUUSD')
    point_size = get_point_size(symbol)

    df['dynamic_sl_points'] = (df['ATR'] * atr_sl_mult / point_size).fillna(40).astype(int)
    df['dynamic_tp_points'] = (df['dynamic_sl_points'] * rr_ratio).astype(int)
    
    return df

def check_for_signals(df):
    """
    Live trading adapter. This function is called continuously to check the newest data.
    """
    # Calculate all signals for the dataset
    df_signals = generate_signals(df)
    
    # Get the very last row (the most recently closed candle)
    last_row = df_signals.iloc[-1]
    
    # Print alerts if a signal is found
    if last_row['signal'] == 1:
        print("Mean Reversion Engine: Buy Signal Detected")
    elif last_row['signal'] == -1:
        print("Mean Reversion Engine: Sell Signal Detected")
        
    # Return the latest signal, the dynamic stop loss, and the dynamic take profit for the risk manager
    return last_row['signal'], last_row['dynamic_sl_points'], last_row['dynamic_tp_points']
