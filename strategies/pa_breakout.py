import pandas as pd
import numpy as np
from utils.indicators import calculate_rsi

def generate_signals(df, **kwargs):
    """
    Price Action Fakeout Reversion (Turtle Soup).
    Instead of buying breakouts, it FADES them. If price sweeps the previous day's high
    but RSI is exhausted, we short back into the range.
    """
    rsi_period = kwargs.get('rsi_period', 14)
    rsi_extreme = kwargs.get('rsi_extreme', 35) # 35 implies 65 for overbought
    lookback_days = kwargs.get('lookback_days', 1)

    if len(df) < max(rsi_period, 48 * lookback_days):
        df['signal'] = 0
        df['dynamic_sl_points'] = 0
        df['dynamic_tp_points'] = 0
        return df

    # Calculate RSI
    df['RSI'] = calculate_rsi(df['close'], period=rsi_period)

    # Date processing for daily grouping
    df['time'] = pd.to_datetime(df['time'], utc=True)
    df['date'] = df['time'].dt.date
    
    daily_stats = df.groupby('date').agg({'high': 'max', 'low': 'min'})
    
    if lookback_days == 1:
        daily_stats['Range_High'] = daily_stats['high'].shift(1)
        daily_stats['Range_Low'] = daily_stats['low'].shift(1)
    else:
        daily_stats['Range_High'] = daily_stats['high'].shift(1).rolling(lookback_days).max()
        daily_stats['Range_Low'] = daily_stats['low'].shift(1).rolling(lookback_days).min()
        
    df = df.join(daily_stats[['Range_High', 'Range_Low']], on='date')
    
    df['close_prev'] = df['close'].shift(1)
    df['RSI_prev'] = df['RSI'].shift(1)
    
    # FADE THE HIGHS: Price sweeps above Range_High, but closes back under it, AND RSI was overbought
    sell_condition = (df['high'] > df['Range_High']) & (df['close'] < df['Range_High']) & (df['RSI_prev'] > (100 - rsi_extreme))
    
    # FADE THE LOWS: Price sweeps below Range_Low, but closes back above it, AND RSI was oversold
    buy_condition = (df['low'] < df['Range_Low']) & (df['close'] > df['Range_Low']) & (df['RSI_prev'] < rsi_extreme)
    
    df['signal'] = 0
    df.loc[buy_condition, 'signal'] = 1
    df.loc[sell_condition, 'signal'] = -1
    
    df['signal_prev'] = df['signal'].shift(1).fillna(0)
    df.loc[df['signal'] == df['signal_prev'], 'signal'] = 0
    
    df['dynamic_sl_points'] = 40
    rr_ratio = kwargs.get('rr_ratio', 2.0)
    df['dynamic_tp_points'] = (df['dynamic_sl_points'] * rr_ratio).astype(int)
    
    return df

def check_for_signals(df):
    df_signals = generate_signals(df)
    last_row = df_signals.iloc[-1]
    
    if last_row['signal'] == 1:
        print("PA Reversion: Swept Daily Low (BUY)")
    elif last_row['signal'] == -1:
        print("PA Reversion: Swept Daily High (SELL)")
        
    return last_row['signal'], last_row['dynamic_sl_points'], last_row['dynamic_tp_points']
