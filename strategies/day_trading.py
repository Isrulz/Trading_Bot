import pandas as pd
import numpy as np

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    
    atr = true_range.rolling(window=period).mean()
    return atr

def generate_signals(df):
    """
    High-winrate day trading strategy combining Trend (EMA), Mean Reversion (RSI), and Momentum (MACD).
    Looser conditions allow for a higher volume of trades.
    """
    if len(df) < 200:
        df['signal'] = 0
        df['dynamic_sl_points'] = 0
        return df

    # 1. Indicators
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # RSI
    df['RSI'] = calculate_rsi(df['close'], period=14)
    
    # MACD
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_12 - ema_26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # ATR
    df['ATR'] = calculate_atr(df, period=14)

    df['dynamic_sl_points'] = 0

    # 2. Conditions
    uptrend = df['EMA_50'] > df['EMA_200']
    downtrend = df['EMA_50'] < df['EMA_200']

    # Shift indicators to avoid lookahead bias
    df['RSI_prev'] = df['RSI'].shift(1)
    df['MACD_prev'] = df['MACD'].shift(1)
    df['MACD_Signal_prev'] = df['MACD_Signal'].shift(1)
    
    # Momentum Triggers (Loosened to RSI 40/60 instead of 30/70)
    bullish_trigger = (df['RSI_prev'] < 40) | (df['MACD_prev'] > df['MACD_Signal_prev'])
    bearish_trigger = (df['RSI_prev'] > 60) | (df['MACD_prev'] < df['MACD_Signal_prev'])

    # Buy: Must be in uptrend, and at least one bullish momentum trigger fires
    buy_condition = uptrend & bullish_trigger
    
    # Sell: Must be in downtrend, and at least one bearish momentum trigger fires
    sell_condition = downtrend & bearish_trigger

    # 3. Signal Generation
    df['signal'] = 0
    df.loc[buy_condition, 'signal'] = 1
    df.loc[sell_condition, 'signal'] = -1
    
    # To prevent spamming signals every single candle while conditions hold true, 
    # we only trigger when the signal flips from 0 or opposite
    df['signal_prev'] = df['signal'].shift(1).fillna(0)
    df.loc[df['signal'] == df['signal_prev'], 'signal'] = 0
    
    return df

def check_for_signals(df):
    """
    Adapter for LIVE mode.
    """
    df_signals = generate_signals(df)
    last_row = df_signals.iloc[-1]
    
    if last_row['signal'] == 1:
        print("Day Trading Engine: Multi-Factor Buy Signal Detected")
    elif last_row['signal'] == -1:
        print("Day Trading Engine: Multi-Factor Sell Signal Detected")
        
    return last_row['signal'], last_row['dynamic_sl_points']
