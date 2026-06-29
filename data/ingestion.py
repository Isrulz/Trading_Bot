import MetaTrader5 as mt5
import pandas as pd
import pytz

def init_connection():
    """
    Establishes a connection to the MetaTrader 5 terminal.
    """
    if not mt5.initialize():
        print(f"Initialization failed. MT5 Error Code: {mt5.last_error()}")
        return False
    
    print("Successfully connected to the MT5 Terminal.")
    return True

def get_historical_bars(symbol, timeframe, num_bars):
    """
    Fetches historical candlestick data and formats it into a clean Pandas DataFrame.
    """
    # 1. Fetch the raw data array from the broker
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_bars)
    
    if rates is None:
        print(f"Failed to get {symbol} data. MT5 Error Code: {mt5.last_error()}")
        return None
        
    # 2. Convert the raw array into a structured DataFrame
    df = pd.DataFrame(rates)
    
    # 3. Format the UNIX timestamp into a readable date
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # 4. (Optional but recommended) Localize time to Australian Eastern Time
    melbourne_tz = pytz.timezone('Australia/Melbourne')
    df['time'] = df['time'].dt.tz_localize('UTC').dt.tz_convert(melbourne_tz)
    
    return df

def get_latest_tick(symbol):
    """
    Fetches the live, real-time Ask and Bid price of an asset.
    """
    tick = mt5.symbol_info_tick(symbol)
    
    if tick is None:
        print(f"Failed to get {symbol} tick. MT5 Error Code: {mt5.last_error()}")
        return None
        
    return {
        "ask": tick.ask,
        "bid": tick.bid,
        "spread": tick.ask - tick.bid
    }

def shutdown_connection():
    """
    Safely closes the connection to the terminal.
    """
    mt5.shutdown()
    print("MT5 connection closed.")

def download_and_save_historical_data(symbol, timeframe, num_bars, filename):
    """
    Fetches historical data and saves it to a local CSV file for backtesting.
    """
    print(f"Downloading {num_bars} bars for {symbol}...")
    df = get_historical_bars(symbol, timeframe, num_bars)
    
    if df is not None and not df.empty:
        df.to_csv(filename, index=False)
        print(f"Successfully saved {len(df)} rows to {filename}")
        return True
    
    print("Failed to download historical data.")
    return False

def load_historical_data(filename):
    """
    Loads historical data from a CSV file into a Pandas DataFrame.
    """
    try:
        df = pd.read_csv(filename)
        df['time'] = pd.to_datetime(df['time'])
        print(f"Loaded {len(df)} rows from {filename}")
        return df
    except Exception as e:
        print(f"Error loading historical data from {filename}: {e}")
        return None

def get_auto_cached_historical_data(symbol, timeframe, num_bars, filename):
    """
    Checks if a local CSV exists. If yes, loads it. 
    If no, connects to MT5, downloads the data, saves it, and then loads it.
    """
    import os
    if os.path.exists(filename):
        print(f"Auto-Cache Hit: Found local dataset '{filename}'. Bypassing MT5 API.")
        return load_historical_data(filename)
    else:
        print(f"Auto-Cache Miss: '{filename}' not found. Fetching from MT5...")
        # Ensure connection
        if not mt5.terminal_info():
            if not init_connection():
                return None
        
        success = download_and_save_historical_data(symbol, timeframe, num_bars, filename)
        if success:
            return load_historical_data(filename)
        return None