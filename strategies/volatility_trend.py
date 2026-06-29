import pandas as pd
import numpy as np

def generate_signals(df, **kwargs):
    """
    Volatility-Adjusted Trend Following Strategy.
    Uses Keltner Channels (based on Average True Range) to find trends,
    and MACD to confirm that momentum is on our side.
    """
    # --- Strategy Parameters ---
    atr_period = kwargs.get('atr_period', 14)       # Periods to calculate market volatility (ATR)
    keltner_mult = kwargs.get('keltner_mult', 1.5)  # Multiplier for channel width
    macd_fast = kwargs.get('macd_fast', 12)         # Fast moving average for MACD
    macd_slow = kwargs.get('macd_slow', 26)         # Slow moving average for MACD
    macd_signal = kwargs.get('macd_signal', 9)      # Smoothing period for MACD signal line
    
    # Ensure we have enough historical data
    if len(df) < max(atr_period, macd_slow):
        df['signal'] = 0
        df['dynamic_sl_points'] = 0
        return df

    # --- Indicator: ATR (Average True Range) ---
    # ATR measures market volatility. We calculate 3 ranges to find the "True Range".
    high_low = df['high'] - df['low']                               # 1. Distance from High to Low
    high_close = np.abs(df['high'] - df['close'].shift())           # 2. Distance from High to previous Close
    low_close = np.abs(df['low'] - df['close'].shift())             # 3. Distance from Low to previous Close
    
    # The True Range is the maximum of these three values
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    
    # The Average True Range (ATR) is simply the moving average of the True Range
    df['ATR'] = true_range.rolling(window=atr_period).mean()

    # --- Indicator: Keltner Channels ---
    # Keltner Channels use an Exponential Moving Average (EMA) as the middle line
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    
    # Upper channel expands when volatility (ATR) is high
    df['Upper_KC'] = df['EMA_20'] + (df['ATR'] * keltner_mult)
    
    # Lower channel expands when volatility (ATR) is high
    df['Lower_KC'] = df['EMA_20'] - (df['ATR'] * keltner_mult)

    # --- Indicator: MACD (Moving Average Convergence Divergence) ---
    # MACD shows the relationship between two moving averages of prices
    ema_fast = df['close'].ewm(span=macd_fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=macd_slow, adjust=False).mean()
    df['MACD'] = ema_fast - ema_slow
    
    # The Signal line is a moving average of the MACD line itself
    df['MACD_Signal'] = df['MACD'].ewm(span=macd_signal, adjust=False).mean()
    
    # The Histogram is the difference between MACD and its Signal line (shows momentum strength)
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # --- Trading Logic ---
    # Shift previous values to avoid look-ahead bias (making decisions on closed data)
    df['close_prev'] = df['close'].shift(1)
    df['Upper_KC_prev'] = df['Upper_KC'].shift(1)
    df['Lower_KC_prev'] = df['Lower_KC'].shift(1)
    
    # Breakout logic: Look for a "fresh" breakout. 
    # This means the previous candle closed inside the channel, but the current one closed outside.
    buy_breakout = (df['close_prev'] <= df['Upper_KC_prev']) & (df['close'] > df['Upper_KC'])
    sell_breakout = (df['close_prev'] >= df['Lower_KC_prev']) & (df['close'] < df['Lower_KC'])
    
    # MACD Confirmation: Momentum must support the direction of the breakout
    macd_bullish = df['MACD_Hist'] > 0  # Positive momentum
    macd_bearish = df['MACD_Hist'] < 0  # Negative momentum
    
    # Combine the breakout and MACD confirmation to generate final conditions
    buy_condition = buy_breakout & macd_bullish
    sell_condition = sell_breakout & macd_bearish
    
    # --- Signal Generation ---
    df['signal'] = 0
    df.loc[buy_condition, 'signal'] = 1
    df.loc[sell_condition, 'signal'] = -1
    
    # Filter repeated signals (don't stack multiple trades in the same direction)
    df['signal_prev'] = df['signal'].shift(1).fillna(0)
    df.loc[df['signal'] == df['signal_prev'], 'signal'] = 0
    
    # Provide a standard 30-point stop loss for risk management
    df['dynamic_sl_points'] = 30 
    
    return df

def check_for_signals(df):
    """
    Live trading adapter. Extracts the latest candle's signal for execution.
    """
    df_signals = generate_signals(df)
    last_row = df_signals.iloc[-1]
    
    if last_row['signal'] == 1:
        print("Volatility Trend: Bullish Channel Breakout Detected")
    elif last_row['signal'] == -1:
        print("Volatility Trend: Bearish Channel Breakout Detected")
        
    return last_row['signal'], last_row['dynamic_sl_points']
