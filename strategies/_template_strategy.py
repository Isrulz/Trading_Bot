import pandas as pd
import numpy as np

# ==============================================================================
# HOW TO BUILD YOUR OWN STRATEGY
# ==============================================================================
# 1. Copy this file and rename it (e.g., "my_super_strategy.py")
# 2. Add your new file to the ACTIVE_STRATEGY options in config.py
# 3. Add a new GRID dictionary in config.py (e.g., GRID_MY_SUPER_STRATEGY)
# 4. Update execution/backtester.py and main.py to recognize your new strategy name.

def generate_signals(df, **kwargs):
    """
    This is the core mathematical engine for your strategy.
    
    Inputs:
    - df: A Pandas DataFrame containing historical price data.
          Columns include: ['time', 'open', 'high', 'low', 'close', 'tick_volume']
    - **kwargs: The parameter combinations passed by the BacktestEngine from config.py.
    
    Outputs:
    - df: The exact same Pandas DataFrame, but you MUST add two new columns:
          1. 'signal': +1 for BUY, -1 for SELL, 0 for HOLD.
          2. 'dynamic_sl_points': Your calculated Stop Loss distance in points (e.g., 150).
    """
    
    # --------------------------------------------------------------------------
    # STEP 1: UNPACK YOUR PARAMETERS
    # --------------------------------------------------------------------------
    # Use kwargs.get() to grab your parameters. Provide a default value just in case.
    # For example, if you added 'ema_length' to config.py, you grab it like this:
    ema_length = kwargs.get('ema_length', 20) 
    
    
    # --------------------------------------------------------------------------
    # STEP 2: CALCULATE YOUR INDICATORS
    # --------------------------------------------------------------------------
    # DO NOT use loops (for/while) here. Pandas is built for Vectorization.
    # Calculate everything across the entire dataframe at once.
    # Example: df['EMA'] = df['close'].ewm(span=ema_length).mean()
    pass 
    
    
    # --------------------------------------------------------------------------
    # STEP 3: DEFINE YOUR ENTRY RULES
    # --------------------------------------------------------------------------
    # Create boolean (True/False) conditions based on your indicators.
    # Example: buy_condition = df['close'] > df['EMA']
    # Example: sell_condition = df['close'] < df['EMA']
    buy_condition = False
    sell_condition = False
    
    
    # --------------------------------------------------------------------------
    # STEP 4: APPLY THE SIGNALS
    # --------------------------------------------------------------------------
    # Start by setting all signals to 0 (Do nothing)
    df['signal'] = 0
    
    # Where your buy condition is True, set the signal to 1
    df.loc[buy_condition, 'signal'] = 1
    
    # Where your sell condition is True, set the signal to -1
    df.loc[sell_condition, 'signal'] = -1
    
    
    # --------------------------------------------------------------------------
    # STEP 5: FILTER REPEATED SIGNALS (CRITICAL)
    # --------------------------------------------------------------------------
    # If the price stays above the EMA for 10 bars, you don't want to send 
    # 10 buy signals in a row. You only want the first one (the crossover).
    # This block wipes out consecutive identical signals.
    df['signal_prev'] = df['signal'].shift(1).fillna(0)
    df.loc[df['signal'] == df['signal_prev'], 'signal'] = 0
    
    
    # --------------------------------------------------------------------------
    # STEP 6: DEFINE YOUR STOP LOSS
    # --------------------------------------------------------------------------
    # You can set a fixed stop loss for the backtester here, or calculate it dynamically
    # (e.g., using ATR). If you set it to 0, the engine will use STOP_LOSS_POINTS from config.py.
    df['dynamic_sl_points'] = 150 
    
    return df


def check_for_signals(df):
    """
    This function is used ONLY for Live Trading.
    It runs the `generate_signals` function above, but instead of returning the 
    whole dataframe, it just returns the very last row (the current moment).
    """
    df_signals = generate_signals(df)
    last_row = df_signals.iloc[-1]
    
    if last_row['signal'] == 1:
        print("My Strategy: Bullish Signal Detected!")
    elif last_row['signal'] == -1:
        print("My Strategy: Bearish Signal Detected!")
        
    return last_row['signal'], last_row['dynamic_sl_points']
