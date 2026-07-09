import pandas as pd
import numpy as np
from utils.indicators import calculate_rsi

def generate_signals(df, **kwargs):
    """
    Tick-VWAP Mean Reversion (Hybrid).
    Calculates a rolling Volume-Weighted Average Price (using tick volume as a proxy)
    and fades extreme deviations back to the mean when RSI shows exhaustion.
    """
    vwap_period = kwargs.get('vwap_period', 24)
    dev_mult = kwargs.get('dev_mult', 1.5)
    rsi_filter = kwargs.get('rsi_filter', 70)
    
    if len(df) < max(vwap_period, 14):
        df['signal'] = 0
        df['dynamic_sl_points'] = 0
        df['dynamic_tp_points'] = 0
        return df
        
    # Calculate typical price
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
    
    # Tick Volume fallback if missing
    if 'tick_volume' not in df.columns:
        df['tick_volume'] = np.random.randint(100, 1000, size=len(df))
        
    df['pv'] = df['typical_price'] * df['tick_volume']
    
    # Rolling VWAP
    df['VWAP'] = df['pv'].rolling(vwap_period).sum() / df['tick_volume'].rolling(vwap_period).sum()
    
    # Rolling Std Dev for bands
    df['Std_Dev'] = df['close'].rolling(vwap_period).std()
    df['Upper_Band'] = df['VWAP'] + (df['Std_Dev'] * dev_mult)
    df['Lower_Band'] = df['VWAP'] - (df['Std_Dev'] * dev_mult)
    
    # Calculate RSI
    df['RSI'] = calculate_rsi(df['close'], period=14)
    
    # Reversion entry logic
    df['close_prev'] = df['close'].shift(1)
    df['RSI_prev'] = df['RSI'].shift(1)
    
    # Buy when price crosses back above lower band, and RSI was extremely oversold
    buy_condition = (df['close_prev'] <= df['Lower_Band']) & (df['close'] > df['Lower_Band']) & (df['RSI_prev'] < (100 - rsi_filter))
    
    # Sell when price crosses back below upper band, and RSI was extremely overbought
    sell_condition = (df['close_prev'] >= df['Upper_Band']) & (df['close'] < df['Upper_Band']) & (df['RSI_prev'] > rsi_filter)
    
    df['signal'] = 0
    df.loc[buy_condition, 'signal'] = 1
    df.loc[sell_condition, 'signal'] = -1
    
    df['signal_prev'] = df['signal'].shift(1).fillna(0)
    df.loc[df['signal'] == df['signal_prev'], 'signal'] = 0
    df['dynamic_sl_points'] = 30
    rr_ratio = kwargs.get('rr_ratio', 2.0)
    df['dynamic_tp_points'] = (df['dynamic_sl_points'] * rr_ratio).astype(int)
    
    return df

def check_for_signals(df):
    df_signals = generate_signals(df)
    last_row = df_signals.iloc[-1]
    
    if last_row['signal'] == 1:
        print("Tick-VWAP: Exhaustion Reversion (BUY)")
    elif last_row['signal'] == -1:
        print("Tick-VWAP: Exhaustion Reversion (SELL)")
        
    return last_row['signal'], last_row['dynamic_sl_points'], last_row['dynamic_tp_points']
