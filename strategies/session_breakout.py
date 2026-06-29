import pandas as pd
import numpy as np

def generate_signals(df, **kwargs):
    """
    Session Breakout Momentum Strategy (London/NY)
    """
    asian_session_end = kwargs.get('asian_session_end', 8)
    breakout_buffer = kwargs.get('breakout_buffer_points', 15)
    volume_ma_period = kwargs.get('volume_ma_period', 20)
    volume_factor = kwargs.get('volume_factor', 1.2)
    
    if len(df) < volume_ma_period:
        df['signal'] = 0
        df['dynamic_sl_points'] = 0
        return df

    # Note: `df['time']` is expected to be a datetime column.
    # In live data, MT5 provides UTC time if properly converted, or broker local time.
    # Our data ingestion convert it to Australia/Melbourne or standard. 
    # Let's assume hour is accessible.
    
    df['hour'] = df['time'].dt.hour
    
    # Calculate the Asian session high/low for the current day
    # We define the Asian session roughly as 00:00 to asian_session_end
    # The breakout happens during the London session.
    df['is_asian'] = df['hour'] < asian_session_end
    
    # We need to find the High and Low of the Asian session for each day.
    df['date'] = df['time'].dt.date
    
    asian_highs = df[df['is_asian']].groupby('date')['high'].max().rename('Asian_High')
    asian_lows = df[df['is_asian']].groupby('date')['low'].min().rename('Asian_Low')
    
    df = df.join(asian_highs, on='date')
    df = df.join(asian_lows, on='date')
    
    # Forward fill just in case, though it should be populated per date.
    df['Asian_High'] = df['Asian_High'].fillna(method='ffill')
    df['Asian_Low'] = df['Asian_Low'].fillna(method='ffill')

    # Calculate typical volume using 'tick_volume' if available. 
    # But our synthetic backtest data does not have volume. We will mock it if missing.
    if 'tick_volume' not in df.columns:
        df['tick_volume'] = np.random.randint(100, 1000, size=len(df))
        
    df['Vol_MA'] = df['tick_volume'].rolling(window=volume_ma_period).mean()
    
    # Breakout Conditions
    # Only trade during the active London/NY session (e.g. hours 8 to 16)
    is_active_session = (df['hour'] >= asian_session_end) & (df['hour'] < asian_session_end + 8)
    
    # Price breaks the Asian High/Low with a buffer
    # Note: breakout_buffer is in points. For synthetic data, we use small raw values.
    # But usually 15 points = 0.00015 in Forex or 0.15 in Gold. We will just use the raw value.
    # To keep it generic, we assume price is roughly normalized or buffer is scaled.
    # We will assume breakout_buffer is a raw price addition since we don't have symbol info here.
    # So if breakout_buffer = 15, we add 15. If price is 2000, 15 is fine. If price is 1.1000, 15 is huge.
    # For now, we'll divide by 100 to simulate a standardized scale, or just add the raw value since it's synthetic.
    buffer = breakout_buffer * 0.01 
    
    df['close_prev'] = df['close'].shift(1)
    df['high_prev'] = df['high'].shift(1)
    df['low_prev'] = df['low'].shift(1)
    
    buy_breakout = df['close'] > (df['Asian_High'] + buffer)
    sell_breakout = df['close'] < (df['Asian_Low'] - buffer)
    
    volume_surge = df['tick_volume'] > (df['Vol_MA'] * volume_factor)
    
    buy_condition = is_active_session & buy_breakout & volume_surge
    sell_condition = is_active_session & sell_breakout & volume_surge
    
    df['signal'] = 0
    df.loc[buy_condition, 'signal'] = 1
    df.loc[sell_condition, 'signal'] = -1
    
    # Filter repeated signals
    df['signal_prev'] = df['signal'].shift(1).fillna(0)
    df.loc[df['signal'] == df['signal_prev'], 'signal'] = 0
    
    # Dynamic SL: SL placed at the opposite side of the breakout range or midway
    df['dynamic_sl_points'] = 30 # Fixed default for now
    
    return df

def check_for_signals(df):
    df_signals = generate_signals(df)
    last_row = df_signals.iloc[-1]
    
    if last_row['signal'] == 1:
        print("Session Breakout: Bullish Breakout Detected")
    elif last_row['signal'] == -1:
        print("Session Breakout: Bearish Breakout Detected")
        
    return last_row['signal'], last_row['dynamic_sl_points']
