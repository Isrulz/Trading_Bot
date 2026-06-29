import pandas as pd
import numpy as np

def calculate_rsi(series, period=14):
    """
    Calculates the Relative Strength Index (RSI).
    RSI is a momentum oscillator that measures the speed and change of price movements.
    
    Parameters:
    series (pd.Series): The price data (usually closing prices).
    period (int): The number of periods to use (default is 14).
    
    Returns:
    pd.Series: The RSI values (ranging from 0 to 100).
    """
    # Calculate the difference in price from the previous period
    delta = series.diff()
    
    # Isolate the positive price changes (gains) and calculate their rolling average
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    
    # Isolate the negative price changes (losses), make them positive, and calculate their rolling average
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    # Relative Strength (RS) is the ratio of average gain to average loss
    rs = gain / loss.replace(0, np.nan)
    
    # Calculate the RSI formula and fill any missing values with 50 (neutral)
    return (100 - (100 / (1 + rs))).fillna(50)

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

    # Ensure we have enough historical data to calculate our indicators
    if len(df) < max(bb_period, rsi_period):
        df['signal'] = 0
        df['dynamic_sl_points'] = 0
        return df

    # --- Indicator Calculation ---
    # Calculate Bollinger Bands
    df['SMA'] = df['close'].rolling(window=bb_period).mean()         # Middle band (Simple Moving Average)
    df['STD'] = df['close'].rolling(window=bb_period).std()          # Price volatility
    df['Upper_BB'] = df['SMA'] + (df['STD'] * bb_std)                # Upper band (Overvalued area)
    df['Lower_BB'] = df['SMA'] - (df['STD'] * bb_std)                # Lower band (Undervalued area)

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
    df['RSI_prev'] = df['RSI'].shift(1)

    # --- Trading Logic ---
    # BUY: If the previous close was below the lower Bollinger Band AND RSI is oversold (< 30)
    buy_condition = (df['close_prev'] < df['Lower_BB_prev']) & (df['RSI_prev'] < rsi_oversold)
    
    # SELL: If the previous close was above the upper Bollinger Band AND RSI is overbought (> 70)
    sell_condition = (df['close_prev'] > df['Upper_BB_prev']) & (df['RSI_prev'] > rsi_overbought)

    # Initialize the signal column with 0 (no signal)
    df['signal'] = 0
    # Assign 1 for a Buy signal
    df.loc[buy_condition, 'signal'] = 1
    # Assign -1 for a Sell signal
    df.loc[sell_condition, 'signal'] = -1
    
    # --- Clean up Signals ---
    # Prevent the bot from opening multiple trades in the same direction consecutively
    df['signal_prev'] = df['signal'].shift(1).fillna(0)
    df.loc[df['signal'] == df['signal_prev'], 'signal'] = 0
    
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
        
    # Return the latest signal and the dynamic stop loss for the risk manager
    return last_row['signal'], last_row['dynamic_sl_points']
