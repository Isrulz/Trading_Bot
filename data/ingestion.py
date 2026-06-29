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