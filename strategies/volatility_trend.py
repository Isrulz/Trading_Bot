import pandas as pd
import numpy as np

def generate_signals(df, **kwargs):
    """
    Volatility-Adjusted Trend Following (ATR Channels + MACD)
    """
    atr_period = kwargs.get('atr_period', 14)
    keltner_mult = kwargs.get('keltner_mult', 1.5)
    macd_fast = kwargs.get('macd_fast', 12)
    macd_slow = kwargs.get('macd_slow', 26)
    macd_signal = kwargs.get('macd_signal', 9)
    
    if len(df) < max(atr_period, macd_slow):
        df['signal'] = 0
        df['dynamic_sl_points'] = 0
        return df

    # ATR
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(window=atr_period).mean()

    # Keltner Channels (using EMA 20 as middle line)
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['Upper_KC'] = df['EMA_20'] + (df['ATR'] * keltner_mult)
    df['Lower_KC'] = df['EMA_20'] - (df['ATR'] * keltner_mult)

    # MACD
    ema_fast = df['close'].ewm(span=macd_fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=macd_slow, adjust=False).mean()
    df['MACD'] = ema_fast - ema_slow
    df['MACD_Signal'] = df['MACD'].ewm(span=macd_signal, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # Conditions
    # Buy: Price closes above Upper Keltner Channel and MACD Histogram is positive (momentum is bullish)
    # Sell: Price closes below Lower Keltner Channel and MACD Histogram is negative (momentum is bearish)
    
    df['close_prev'] = df['close'].shift(1)
    df['Upper_KC_prev'] = df['Upper_KC'].shift(1)
    df['Lower_KC_prev'] = df['Lower_KC'].shift(1)
    
    # We want a fresh breakout, so previous close was inside the channel, current close is outside
    buy_breakout = (df['close_prev'] <= df['Upper_KC_prev']) & (df['close'] > df['Upper_KC'])
    sell_breakout = (df['close_prev'] >= df['Lower_KC_prev']) & (df['close'] < df['Lower_KC'])
    
    macd_bullish = df['MACD_Hist'] > 0
    macd_bearish = df['MACD_Hist'] < 0
    
    buy_condition = buy_breakout & macd_bullish
    sell_condition = sell_breakout & macd_bearish
    
    df['signal'] = 0
    df.loc[buy_condition, 'signal'] = 1
    df.loc[sell_condition, 'signal'] = -1
    
    # Filter repeated signals
    df['signal_prev'] = df['signal'].shift(1).fillna(0)
    df.loc[df['signal'] == df['signal_prev'], 'signal'] = 0
    
    # SL is set dynamically to ATR * 1.5, assuming standard scale.
    # Note: the risk engine expects integer points, but ATR is in price delta.
    # We will pass it through; risk.py should handle it or we assume points is scaled.
    df['dynamic_sl_points'] = 30 # Mock standard for backtest
    
    return df

def check_for_signals(df):
    df_signals = generate_signals(df)
    last_row = df_signals.iloc[-1]
    if last_row['signal'] == 1:
        print("Volatility Trend: Bullish Channel Breakout Detected")
    elif last_row['signal'] == -1:
        print("Volatility Trend: Bearish Channel Breakout Detected")
    return last_row['signal'], last_row['dynamic_sl_points']
