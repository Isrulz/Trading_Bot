import pandas as pd
import numpy as np

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)

def generate_signals(df, **kwargs):
    """
    Intraday Mean Reversion: Bollinger Bands + RSI
    """
    bb_period = kwargs.get('bb_period', 20)
    bb_std = kwargs.get('bb_std', 2.0)
    rsi_period = kwargs.get('rsi_period', 14)
    rsi_overbought = kwargs.get('rsi_overbought', 70)
    rsi_oversold = kwargs.get('rsi_oversold', 30)

    if len(df) < max(bb_period, rsi_period):
        df['signal'] = 0
        df['dynamic_sl_points'] = 0
        return df

    # Bollinger Bands
    df['SMA'] = df['close'].rolling(window=bb_period).mean()
    df['STD'] = df['close'].rolling(window=bb_period).std()
    df['Upper_BB'] = df['SMA'] + (df['STD'] * bb_std)
    df['Lower_BB'] = df['SMA'] - (df['STD'] * bb_std)

    # RSI
    df['RSI'] = calculate_rsi(df['close'], period=rsi_period)

    df['dynamic_sl_points'] = 20 # fixed tight SL for mean reversion

    df['close_prev'] = df['close'].shift(1)
    df['Upper_BB_prev'] = df['Upper_BB'].shift(1)
    df['Lower_BB_prev'] = df['Lower_BB'].shift(1)
    df['RSI_prev'] = df['RSI'].shift(1)

    # Buy: Price pierced lower BB and RSI is oversold
    buy_condition = (df['close_prev'] < df['Lower_BB_prev']) & (df['RSI_prev'] < rsi_oversold)
    
    # Sell: Price pierced upper BB and RSI is overbought
    sell_condition = (df['close_prev'] > df['Upper_BB_prev']) & (df['RSI_prev'] > rsi_overbought)

    df['signal'] = 0
    df.loc[buy_condition, 'signal'] = 1
    df.loc[sell_condition, 'signal'] = -1
    
    df['signal_prev'] = df['signal'].shift(1).fillna(0)
    df.loc[df['signal'] == df['signal_prev'], 'signal'] = 0
    
    return df

def check_for_signals(df):
    df_signals = generate_signals(df)
    last_row = df_signals.iloc[-1]
    if last_row['signal'] == 1:
        print("Mean Reversion Engine: Buy Signal Detected")
    elif last_row['signal'] == -1:
        print("Mean Reversion Engine: Sell Signal Detected")
    return last_row['signal'], last_row['dynamic_sl_points']
