import time
import sys
import MetaTrader5 as mt5

# Import global configurations
import config

# Import structural modules
from data.ingestion import init_connection, get_historical_bars, get_latest_tick, shutdown_connection, load_historical_data
from execution.risk import calculate_position_size
from execution.orders import get_open_positions, execute_trade, close_position
from utils.time_sync import is_safe_to_trade, get_current_melbourne_time

def initialize_system():
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

def run_trading_loop():
    print(f"Starting LIVE Execution with Strategy: {config.ACTIVE_STRATEGY}")
    if config.ACTIVE_STRATEGY == "moving_avg":
        from strategies.moving_avg import check_for_signals
    elif config.ACTIVE_STRATEGY == "day_trading":
        from strategies.day_trading import check_for_signals
    else:
        print("Invalid strategy selected.")
        return

    while True:
        try:
            current_time = get_current_melbourne_time()
            print(f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')} AEST] Scanning market...")

            if not is_safe_to_trade():
                print("Market Status: CLOSED or LOW LIQUIDITY WINDOW. Pausing execution.")
                time.sleep(60)
                continue

            required_bars = getattr(config, 'STRATEGY_SLOW_PERIOD', 200) + 10
            df = get_historical_bars(config.SYMBOL, config.TIMEFRAME, required_bars)
            
            if df is None or df.empty:
                print("Warning: Data stream interrupted. Retrying next cycle.")
                time.sleep(10)
                continue

            open_trades = get_open_positions(config.SYMBOL)
            signal, strategy_sl_points = check_for_signals(df)
            
            has_long = any(t.type == mt5.POSITION_TYPE_BUY for t in open_trades)
            has_short = any(t.type == mt5.POSITION_TYPE_SELL for t in open_trades)

            for trade in open_trades:
                if trade.type == mt5.POSITION_TYPE_BUY and signal == -1:
                    print(f"Exit Signal Detected! Closing Long Position: {trade.ticket}")
                    close_position(trade.ticket)
                    has_long = False
                elif trade.type == mt5.POSITION_TYPE_SELL and signal == 1:
                    print(f"Exit Signal Detected! Closing Short Position: {trade.ticket}")
                    close_position(trade.ticket)
                    has_short = False

            if signal != 0:
                tick = get_latest_tick(config.SYMBOL)
                account_info = mt5.account_info()
                
                if tick and account_info:
                    sl_points = strategy_sl_points if strategy_sl_points > 0 else config.STOP_LOSS_POINTS
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
                        tp_price = tick['ask'] + (sl_points * 2 * mt5.symbol_info(config.SYMBOL).point)
                        execute_trade(config.SYMBOL, mt5.ORDER_TYPE_BUY, calculated_lots, tick['ask'], sl_price, tp_price, config.MAGIC_NUMBER)
                    elif signal == -1 and not has_short:
                        print(f"Execution Strategy: Triggering SHORT Trade. Lots: {calculated_lots}")
                        sl_price = tick['bid'] + (sl_points * mt5.symbol_info(config.SYMBOL).point)
                        tp_price = tick['bid'] - (sl_points * 2 * mt5.symbol_info(config.SYMBOL).point)
                        execute_trade(config.SYMBOL, mt5.ORDER_TYPE_SELL, calculated_lots, tick['bid'], sl_price, tp_price, config.MAGIC_NUMBER)
            
            time.sleep(10)
        except KeyboardInterrupt:
            print("\nShutdown command acknowledged by operator.")
            break
        except Exception as e:
            print(f"Unexpected Runtime System Exception Error: {e}")
            time.sleep(15)


import itertools
import numpy as np
from execution.orders import reset_ledger

class BacktestEngine:
    def __init__(self, df, strategy_name):
        self.df = df
        self.strategy_name = strategy_name
        self.train_split = int(len(df) * getattr(config, "TRAIN_SPLIT_RATIO", 0.7))
        self.df_train = df.iloc[:self.train_split].copy()
        self.df_test = df.iloc[self.train_split:].copy()
        
        if strategy_name == "mean_reversion":
            from strategies.mean_reversion import generate_signals
            self.generate_signals = generate_signals
            self.grid = getattr(config, "GRID_MEAN_REVERSION", {})
        elif strategy_name == "session_breakout":
            try:
                from strategies.session_breakout import generate_signals
                self.generate_signals = generate_signals
                self.grid = getattr(config, "GRID_SESSION_BREAKOUT", {})
            except ImportError:
                pass
        elif strategy_name == "volatility_trend":
            try:
                from strategies.volatility_trend import generate_signals
                self.generate_signals = generate_signals
                self.grid = getattr(config, "GRID_VOLATILITY_TREND", {})
            except ImportError:
                pass
        else:
            raise ValueError("Unknown strategy.")
            
    def run_simulation(self, df_signals):
        reset_ledger()
        balance = getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0)
        peak_balance = balance
        max_drawdown = 0.0
        wins, losses = 0, 0
        trade_returns = []
        
        for i in range(len(df_signals)):
            row = df_signals.iloc[i]
            signal = row.get('signal', 0)
            sl_points = row.get('dynamic_sl_points', 0)
            if sl_points <= 0: sl_points = getattr(config, "STOP_LOSS_POINTS", 150)
            price = row['close']
            
            open_trades = get_open_positions(getattr(config, "SYMBOL", "XAUUSD"))
            has_long = any(t.type == mt5.ORDER_TYPE_BUY for t in open_trades)
            has_short = any(t.type == mt5.ORDER_TYPE_SELL for t in open_trades)
            
            for trade in open_trades:
                if trade.type == mt5.ORDER_TYPE_BUY and signal == -1:
                    profit = (price - trade.price_open) * trade.volume * (100 if "XAU" in getattr(config, "SYMBOL", "XAUUSD") else 100000)
                    balance += profit
                    close_position(trade.ticket, current_price=price)
                    has_long = False
                    trade_returns.append(profit / getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0))
                    if profit > 0: wins += 1
                    else: losses += 1
                elif trade.type == mt5.ORDER_TYPE_SELL and signal == 1:
                    profit = (trade.price_open - price) * trade.volume * (100 if "XAU" in getattr(config, "SYMBOL", "XAUUSD") else 100000)
                    balance += profit
                    close_position(trade.ticket, current_price=price)
                    has_short = False
                    trade_returns.append(profit / getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0))
                    if profit > 0: wins += 1
                    else: losses += 1
                    
            if signal != 0:
                lots = calculate_position_size(getattr(config, "SYMBOL", "XAUUSD"), balance, getattr(config, "RISK_PERCENT", 1.0), sl_points, current_price=price)
                if lots > 0:
                    if signal == 1 and not has_long:
                        execute_trade(getattr(config, "SYMBOL", "XAUUSD"), mt5.ORDER_TYPE_BUY, lots, price, price - sl_points*0.01, price + sl_points*0.02, getattr(config, "MAGIC_NUMBER", 999111))
                    elif signal == -1 and not has_short:
                        execute_trade(getattr(config, "SYMBOL", "XAUUSD"), mt5.ORDER_TYPE_SELL, lots, price, price + sl_points*0.01, price - sl_points*0.02, getattr(config, "MAGIC_NUMBER", 999111))
                        
            if balance > peak_balance:
                peak_balance = balance
            drawdown = (peak_balance - balance) / peak_balance
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                
        open_trades = get_open_positions(getattr(config, "SYMBOL", "XAUUSD"))
        for trade in open_trades:
            close_position(trade.ticket, current_price=price)
            
        sharpe = 0
        if len(trade_returns) > 1:
            std_ret = np.std(trade_returns)
            if std_ret > 0:
                sharpe = np.mean(trade_returns) / std_ret
                
        return {
            "balance": balance,
            "max_drawdown": max_drawdown,
            "sharpe": sharpe,
            "wins": wins,
            "losses": losses,
            "total_trades": wins + losses
        }

    def optimize(self):
        print("=" * 50)
        print(f"STARTING IN-SAMPLE OPTIMIZATION ({len(self.df_train)} bars)")
        
        keys = list(self.grid.keys())
        values = list(self.grid.values())
        permutations = list(itertools.product(*values))
        
        best_params = {}
        best_score = -float('inf')
        
        for p in permutations:
            params = dict(zip(keys, p))
            df_sig = self.generate_signals(self.df_train.copy(), **params)
            metrics = self.run_simulation(df_sig)
            
            win_rate = (metrics['wins'] / metrics['total_trades']) if metrics['total_trades'] > 0 else 0
            score = metrics['sharpe'] * win_rate
            
            if score > best_score and metrics['total_trades'] > 0:
                best_score = score
                best_params = params
                
        if not best_params and permutations:
            best_params = dict(zip(keys, permutations[0]))
            
        print(f"BEST IS PARAMS: {best_params}")
        return best_params
        
    def validate(self, best_params):
        print("=" * 50)
        print(f"RUNNING OUT-OF-SAMPLE VALIDATION ({len(self.df_test)} bars)")
        
        df_sig = self.generate_signals(self.df_test.copy(), **best_params)
        metrics = self.run_simulation(df_sig)
        
        init_bal = getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0)
        
        print("OOS METRICS:")
        print(f"Final Balance:   {metrics['balance']:.2f}")
        print(f"Total Return:    {((metrics['balance'] - init_bal) / init_bal) * 100:.2f}%")
        
        win_rate = (metrics['wins'] / metrics['total_trades']) * 100 if metrics['total_trades'] > 0 else 0
        print(f"Total Trades:    {metrics['total_trades']} (Wins: {metrics['wins']}, Losses: {metrics['losses']})")
        print(f"Win Rate:        {win_rate:.2f}%")
        print(f"Max Drawdown:    {metrics['max_drawdown'] * 100:.2f}%")
        print(f"Sharpe Ratio:    {metrics['sharpe']:.2f} (Trade Basis)")
        print("=" * 50)
        return metrics

def run_backtest():
    from data.ingestion import get_auto_cached_historical_data
    df = get_auto_cached_historical_data(
        getattr(config, "SYMBOL", "XAUUSD"), 
        getattr(config, "TIMEFRAME", 16385), 
        3000, 
        getattr(config, "BACKTEST_DATA_FILE", "historical_data.csv")
    )
    if df is None or df.empty:
        print("CRITICAL: Failed to load backtest data.")
        return
        
    engine = BacktestEngine(df, getattr(config, "ACTIVE_STRATEGY", "mean_reversion"))
    best_params = engine.optimize()
    engine.validate(best_params)

if __name__ == "__main__":
    if initialize_system():
        if getattr(config, "MODE", "BACKTEST") == "BACKTEST":
            run_backtest()
        else:
            run_trading_loop()
        
        if getattr(config, "MODE", "BACKTEST") != "BACKTEST":
            shutdown_connection()
            
        print("=" * 50)
        print("SYSTEM DEACTIVATED - GRACEFUL SHUTDOWN COMPLETE")
        print("=" * 50)
