import time
import sys
import MetaTrader5 as mt5

# Import global configurations
import config

# Import structural modules
from data.ingestion import init_connection, get_historical_bars, get_latest_tick, shutdown_connection
from execution.risk import calculate_position_size
from execution.orders import get_open_positions, execute_trade, close_position
from utils.time_sync import is_safe_to_trade, get_current_melbourne_time

# If we are in backtest mode, we can just import the runner and bypass the live stuff
if config.MODE == "BACKTEST":
    from execution.backtester import run_backtest

# ==============================================================================
# 1. INITIALIZATION SEQUENCE
# ==============================================================================
def initialize_system():
    """
    Connects to the MT5 Terminal and logs into the broker using credentials from .env.
    """
    if config.MODE == "BACKTEST":
        print("=" * 50)
        print("INITIALIZING ALGORITHMIC TRADING SYSTEM - OFFLINE BACKTEST MODE")
        print("=" * 50)
        return True
        
    print("=" * 50)
    print("INITIALIZING ALGORITHMIC TRADING SYSTEM")
    print("=" * 50)
    
    if not init_connection():
        print("CRITICAL: Could not connect to MT5 Terminal. Exiting system.")
        sys.exit(1)
        
    login_success = mt5.login(
        login=config.MT5_LOGIN,
        password=config.MT5_PASSWORD,
        server=config.MT5_SERVER
    )
    
    if not login_success:
        print(f"CRITICAL: Broker login failed. MT5 Error: {mt5.last_error()}")
        shutdown_connection()
        sys.exit(1)
        
    print(f"Logged into Account: {config.MT5_LOGIN} ({config.ENVIRONMENT} Mode)")
    print(f"Target Asset: {config.SYMBOL}")
    print("System status: ONLINE & RUNNING\n")
    return True

# ==============================================================================
# 2. LIVE TRADING LOOP
# ==============================================================================
def run_trading_loop():
    """
    The infinite loop that scans the live market, checks the strategy for signals,
    and executes trades accordingly.
    """
    print(f"Starting LIVE Execution with Strategy: {config.ACTIVE_STRATEGY}")
    
    # Load the requested strategy dynamically based on config.py
    import importlib
    try:
        strategy_module = importlib.import_module(f"strategies.{config.ACTIVE_STRATEGY}")
        check_for_signals = strategy_module.check_for_signals
    except (ImportError, AttributeError) as e:
        print(f"CRITICAL: Failed to load strategy module/function for '{config.ACTIVE_STRATEGY}': {e}")
        return

    # Infinite Loop
    while True:
        try:
            current_time = get_current_melbourne_time()
            print(f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')} AEST] Scanning market...")

            # 1. Safety Check (Is the market open?)
            if not is_safe_to_trade():
                print("Market Status: CLOSED or LOW LIQUIDITY WINDOW. Pausing execution.")
                time.sleep(60)
                continue

            # 1b. End of Day Square-off for NYSE ORB Strategy (at or after 3:45 PM America/New_York)
            if config.ACTIVE_STRATEGY == "nyse_orb":
                from utils.time_sync import NEW_YORK_TZ
                import pytz
                from datetime import datetime
                ny_now = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(NEW_YORK_TZ)
                if (ny_now.hour == 15 and ny_now.minute >= 45) or (ny_now.hour > 15):
                    print("NYSE ORB Strategy: End-of-day square-off window active. Closing all positions and pausing.")
                    open_trades = get_open_positions(config.SYMBOL)
                    for trade in open_trades:
                        print(f"EOD Closure: Closing position {trade.ticket}")
                        close_position(trade.ticket)
                    time.sleep(60)
                    continue

            # 2. Fetch recent historical data
            required_bars = getattr(config, 'STRATEGY_SLOW_PERIOD', 200) + 10
            df = get_historical_bars(config.SYMBOL, config.TIMEFRAME, required_bars)
            
            if df is None or df.empty:
                print("Warning: Data stream interrupted. Retrying next cycle.")
                time.sleep(10)
                continue

            # 3. Check what positions we currently hold
            open_trades = get_open_positions(config.SYMBOL)
            has_long = any(t.type == mt5.POSITION_TYPE_BUY for t in open_trades)
            has_short = any(t.type == mt5.POSITION_TYPE_SELL for t in open_trades)

            # 4. Ask the strategy if we should enter or exit
            signal, strategy_sl_points, strategy_tp_points = check_for_signals(df)

            # 5. Handle Exits
            for trade in open_trades:
                if trade.type == mt5.POSITION_TYPE_BUY and signal == -1:
                    print(f"Exit Signal Detected! Closing Long Position: {trade.ticket}")
                    close_position(trade.ticket)
                    has_long = False
                elif trade.type == mt5.POSITION_TYPE_SELL and signal == 1:
                    print(f"Exit Signal Detected! Closing Short Position: {trade.ticket}")
                    close_position(trade.ticket)
                    has_short = False

            # 6. Handle Entries
            if signal != 0:
                tick = get_latest_tick(config.SYMBOL)
                account_info = mt5.account_info()
                
                if tick and account_info:
                    sl_points = strategy_sl_points if strategy_sl_points > 0 else config.STOP_LOSS_POINTS
                    tp_points = strategy_tp_points if strategy_tp_points > 0 else (sl_points * 2)
                    
                    # Risk engine calculates the exact lot size we need to hit our RISK_PERCENT
                    calculated_lots = calculate_position_size(
                        symbol=config.SYMBOL,
                        account_balance=account_info.balance,
                        risk_percentage=config.RISK_PERCENT,
                        stop_loss_points=sl_points,
                        current_price=tick['ask'] if signal == 1 else tick['bid']
                    )
                    
                    if signal == 1 and not has_long:
                        print(f"Execution Strategy: Triggering LONG Trade. Lots: {calculated_lots}")
                        sl_price = tick['ask'] - (sl_points * mt5.symbol_info(config.SYMBOL).point)
                        tp_price = tick['ask'] + (tp_points * mt5.symbol_info(config.SYMBOL).point)
                        execute_trade(config.SYMBOL, mt5.ORDER_TYPE_BUY, calculated_lots, tick['ask'], sl_price, tp_price, config.MAGIC_NUMBER)
                        
                    elif signal == -1 and not has_short:
                        print(f"Execution Strategy: Triggering SHORT Trade. Lots: {calculated_lots}")
                        sl_price = tick['bid'] + (sl_points * mt5.symbol_info(config.SYMBOL).point)
                        tp_price = tick['bid'] - (tp_points * mt5.symbol_info(config.SYMBOL).point)
                        execute_trade(config.SYMBOL, mt5.ORDER_TYPE_SELL, calculated_lots, tick['bid'], sl_price, tp_price, config.MAGIC_NUMBER)
            
            # 7. Sleep before scanning again
            time.sleep(10)
            
        except KeyboardInterrupt:
            print("\nShutdown command acknowledged by operator.")
            break
        except Exception as e:
            print(f"Unexpected Runtime System Exception Error: {e}")
            time.sleep(15)


# ==============================================================================
# 3. MAIN ROUTER
# ==============================================================================
if __name__ == "__main__":
    if initialize_system():
        # Depending on config.py, either launch a fast offline backtest or trade live.
        if getattr(config, "MODE", "BACKTEST") == "BACKTEST":
            run_backtest()
        else:
            run_trading_loop()
        
        # Cleanup
        if getattr(config, "MODE", "BACKTEST") != "BACKTEST":
            shutdown_connection()
            
        print("=" * 50)
        print("SYSTEM DEACTIVATED - GRACEFUL SHUTDOWN COMPLETE")
        print("=" * 50)
