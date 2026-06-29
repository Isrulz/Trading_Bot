import pandas as pd
import numpy as np

def generate_signals(df, **kwargs):
    """
    Session Breakout Momentum Strategy.
    This strategy aims to capture explosive price moves that often occur when the
    London or New York trading sessions open, breaking out of the quiet Asian session range.
    """
    # --- Strategy Parameters ---
    asian_session_end = kwargs.get('asian_session_end', 8)       # Hour when Asian session ends (e.g., 8 AM)
    breakout_buffer = kwargs.get('breakout_buffer_points', 15)   # Extra points needed to confirm a true breakout
    volume_ma_period = kwargs.get('volume_ma_period', 20)        # Period for volume moving average
    volume_factor = kwargs.get('volume_factor', 1.2)             # Multiplier to detect an unusual surge in volume
    
    # Ensure we have enough data to calculate our volume moving average
    if len(df) < volume_ma_period:
        df['signal'] = 0
        df['dynamic_sl_points'] = 0
        return df

    # --- Time Processing ---
    # Extract the hour from the time column to know which trading session we are in
    df['hour'] = df['time'].dt.hour
    
    # Define the Asian session (e.g., from midnight to 8 AM)
    df['is_asian'] = df['hour'] < asian_session_end
    
    # Extract just the date so we can group data day by day
    df['date'] = df['time'].dt.date
    
    # Find the highest and lowest price reached during the Asian session for each day
    asian_highs = df[df['is_asian']].groupby('date')['high'].max().rename('Asian_High')
    asian_lows = df[df['is_asian']].groupby('date')['low'].min().rename('Asian_Low')
    
    # Attach these daily highs and lows back to our main dataset
    df = df.join(asian_highs, on='date')
    df = df.join(asian_lows, on='date')
    
    # Forward fill the values so that the rest of the day knows what the Asian High/Low was
    df['Asian_High'] = df['Asian_High'].fillna(method='ffill')
    df['Asian_Low'] = df['Asian_Low'].fillna(method='ffill')

    # --- Volume Processing ---
    # If the broker didn't provide volume data, generate some synthetic data for testing
    if 'tick_volume' not in df.columns:
        df['tick_volume'] = np.random.randint(100, 1000, size=len(df))
        
    # Calculate the average volume over the past N periods to establish a baseline
    df['Vol_MA'] = df['tick_volume'].rolling(window=volume_ma_period).mean()
    
    # --- Breakout Logic ---
    # We only want to trade during the active London/NY sessions (e.g., hours 8 to 16)
    is_active_session = (df['hour'] >= asian_session_end) & (df['hour'] < asian_session_end + 8)
    
    # Convert our breakout buffer points into a standardized price scale
    # This buffer ensures we don't buy on a fakeout (price barely crosses and falls back)
    buffer = breakout_buffer * 0.01 
    
    # Prepare previous candle data to track the exact moment of the breakout
    df['close_prev'] = df['close'].shift(1)
    df['high_prev'] = df['high'].shift(1)
    df['low_prev'] = df['low'].shift(1)
    
    # Determine if the current price broke out of the Asian session boundaries
    buy_breakout = df['close'] > (df['Asian_High'] + buffer)
    sell_breakout = df['close'] < (df['Asian_Low'] - buffer)
    
    # Check if the volume is exceptionally high (validating the breakout's strength)
    volume_surge = df['tick_volume'] > (df['Vol_MA'] * volume_factor)
    
    # Combine conditions: Active session + Price Breakout + High Volume
    buy_condition = is_active_session & buy_breakout & volume_surge
    sell_condition = is_active_session & sell_breakout & volume_surge
    
    # --- Signal Generation ---
    df['signal'] = 0
    df.loc[buy_condition, 'signal'] = 1
    df.loc[sell_condition, 'signal'] = -1
    
    # Filter out repeated signals to avoid opening duplicate trades
    df['signal_prev'] = df['signal'].shift(1).fillna(0)
    df.loc[df['signal'] == df['signal_prev'], 'signal'] = 0
    
    # Set a dynamic stop loss of 30 points (could be optimized later)
    df['dynamic_sl_points'] = 30
    
    return df

def check_for_signals(df):
    """
    Live trading adapter to check for the most recent breakout signals.
    """
    df_signals = generate_signals(df)
    last_row = df_signals.iloc[-1]
    
    # Output user-friendly messages when a breakout occurs
    if last_row['signal'] == 1:
        print("Session Breakout: Bullish Breakout Detected")
    elif last_row['signal'] == -1:
        print("Session Breakout: Bearish Breakout Detected")
        
    return last_row['signal'], last_row['dynamic_sl_points']
