import pandas as pd
import numpy as np

def calculate_rsi(series, period=14):
    """
    Helper function to calculate the Relative Strength Index (RSI).
    RSI helps identify overbought (price went up too fast) or oversold (price dropped too fast) conditions.
    """
    # Find period-to-period price changes
    delta = series.diff()
    
    # Separate gains and losses
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    # Calculate Relative Strength (RS)
    rs = gain / loss.replace(0, np.nan)
    
    # Convert RS into an RSI index between 0 and 100
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50) # Neutral RSI is 50

def calculate_atr(df, period=14):
    """
    Helper function to calculate Average True Range (ATR).
    ATR measures market volatility by analyzing the entire range of an asset price for that period.
    """
    # 1. Current High minus Current Low
    high_low = df['high'] - df['low']
    # 2. Current High minus Previous Close (absolute value)
    high_close = np.abs(df['high'] - df['close'].shift())
    # 3. Current Low minus Previous Close (absolute value)
    low_close = np.abs(df['low'] - df['close'].shift())
    
    # Find the maximum of the 3 values above to get the True Range
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    
    # Average the True Range over the specified period
    atr = true_range.rolling(window=period).mean()
    return atr

def generate_signals(df):
    """
    High-winrate Day Trading Strategy.
    This strategy combines:
    1. Trend confirmation (EMA 50 and EMA 200)
    2. Mean Reversion / Pullbacks (RSI)
    3. Momentum (MACD)
    
    It waits for a broad trend, and then looks for short-term pullbacks and momentum shifts to enter trades.
    """
    # Ensure we have enough data (200 periods needed for the 200 EMA)
    if len(df) < 200:
        df['signal'] = 0
        df['dynamic_sl_points'] = 0
        return df

    # --- 1. Calculate Indicators ---
    
    # Trend Indicators (Exponential Moving Averages give more weight to recent prices)
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # Oscillator / Pullback Indicator
    df['RSI'] = calculate_rsi(df['close'], period=14)
    
    # Momentum Indicator (MACD)
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_12 - ema_26                                 # The MACD Line
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean() # The Signal Line
    
    # Volatility Indicator
    df['ATR'] = calculate_atr(df, period=14)

    # Day trading uses the default stop loss configured in the main bot settings
    df['dynamic_sl_points'] = 0

    # --- 2. Determine Market Context (Trend) ---
    # We are in an uptrend if the fast EMA (50) is above the slow EMA (200)
    uptrend = df['EMA_50'] > df['EMA_200']
    
    # We are in a downtrend if the fast EMA (50) is below the slow EMA (200)
    downtrend = df['EMA_50'] < df['EMA_200']

    # --- 3. Setup Triggers (Shift to avoid look-ahead bias) ---
    df['RSI_prev'] = df['RSI'].shift(1)
    df['MACD_prev'] = df['MACD'].shift(1)
    df['MACD_Signal_prev'] = df['MACD_Signal'].shift(1)
    
    # Bullish Trigger: 
    # RSI drops below 40 (minor pullback/oversold) OR MACD crosses above its Signal Line (bullish momentum)
    bullish_trigger = (df['RSI_prev'] < 40) | (df['MACD_prev'] > df['MACD_Signal_prev'])
    
    # Bearish Trigger:
    # RSI goes above 60 (minor rally/overbought) OR MACD crosses below its Signal Line (bearish momentum)
    bearish_trigger = (df['RSI_prev'] > 60) | (df['MACD_prev'] < df['MACD_Signal_prev'])

    # --- 4. Final Trade Conditions ---
    # BUY: The broader trend must be UP, and a bullish trigger must have fired
    buy_condition = uptrend & bullish_trigger
    
    # SELL: The broader trend must be DOWN, and a bearish trigger must have fired
    sell_condition = downtrend & bearish_trigger

    # --- 5. Signal Assignment and Cleanup ---
    df['signal'] = 0
    df.loc[buy_condition, 'signal'] = 1
    df.loc[sell_condition, 'signal'] = -1
    
    # Prevent the bot from spamming signals (e.g., repeatedly buying while condition holds true)
    # We only take the trade the moment the signal changes from 0 to 1, or 0 to -1.
    df['signal_prev'] = df['signal'].shift(1).fillna(0)
    df.loc[df['signal'] == df['signal_prev'], 'signal'] = 0
    
    return df

def check_for_signals(df):
    """
    Live trading adapter. Extracts the latest candle's signal.
    """
    df_signals = generate_signals(df)
    last_row = df_signals.iloc[-1]
    
    # Print clear terminal output for the user
    if last_row['signal'] == 1:
        print("Day Trading Engine: Multi-Factor Buy Signal Detected")
    elif last_row['signal'] == -1:
        print("Day Trading Engine: Multi-Factor Sell Signal Detected")
        
    return last_row['signal'], last_row['dynamic_sl_points']
