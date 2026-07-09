import pandas as pd
import numpy as np
from utils.indicators import calculate_zscore, calculate_atr
from utils.calculations import get_point_size

VERSION = "2.0"

def generate_signals(df, **kwargs):
    """
    Statistical Z-Score Reversion.
    Calculates the Z-Score of the current closing price relative to a rolling distribution. 
    FADES the move when Z-Score hits an extreme (e.g. +2.0 or -2.0).
    """
    z_period = kwargs.get('z_period', 20)
    z_entry = kwargs.get('z_entry', 1.5)
    rr_ratio = kwargs.get('rr_ratio', 2.0)
    atr_sl_mult = kwargs.get('atr_sl_mult', 1.0)
    
    if len(df) < z_period:
        df['signal'] = 0
        df['dynamic_sl_points'] = 0
        df['dynamic_tp_points'] = 0
        return df
        
    df['Z_Score'] = calculate_zscore(df['close'], period=z_period)
    
    df['Z_prev'] = df['Z_Score'].shift(1)
    
    # Reversion logic
    # Buy when Z-score drops below -entry
    buy_condition = (df['Z_prev'] >= -z_entry) & (df['Z_Score'] < -z_entry)
    
    # Sell when Z-score pops above +entry
    sell_condition = (df['Z_prev'] <= z_entry) & (df['Z_Score'] > z_entry)
    
    # Generate Signals (Continuous)
    df['signal'] = 0
    df.loc[buy_condition, 'signal'] = 1
    df.loc[sell_condition, 'signal'] = -1
    
    # Calculate ATR for dynamic Stop Loss
    df['ATR'] = calculate_atr(df, period=14)
    import config
    symbol = kwargs.get('symbol') or getattr(config, 'SYMBOL', 'XAUUSD')
    point_size = get_point_size(symbol)

    df['dynamic_sl_points'] = (df['ATR'] * atr_sl_mult / point_size).fillna(40).astype(int)
    df['dynamic_tp_points'] = (df['dynamic_sl_points'] * rr_ratio).astype(int)
    
    return df

def check_for_signals(df):
    df_signals = generate_signals(df)
    last_row = df_signals.iloc[-1]
    
    if last_row['signal'] == 1:
        print("Z-Score Reversion: Statistical Floor (BUY)")
    elif last_row['signal'] == -1:
        print("Z-Score Reversion: Statistical Ceiling (SELL)")
        
    return last_row['signal'], last_row['dynamic_sl_points'], last_row['dynamic_tp_points']
