import itertools
import numpy as np
import MetaTrader5 as mt5

import config
from execution.orders import reset_ledger, get_open_positions, close_position, execute_trade
from execution.risk import calculate_position_size

class BacktestEngine:
    """
    The Backtest Engine runs your strategies over historical data without connecting to a live broker.
    It automatically performs a 'Grid Search' (testing all parameter combinations) and an 
    Out-Of-Sample validation to prevent overfitting.
    """
    def __init__(self, df, strategy_name):
        self.df = df
        self.strategy_name = strategy_name
        
        # Split the data into In-Sample (for finding parameters) and Out-Of-Sample (for testing them)
        self.train_split = int(len(df) * getattr(config, "TRAIN_SPLIT_RATIO", 0.7))
        self.df_train = df.iloc[:self.train_split].copy()
        self.df_test = df.iloc[self.train_split:].copy()
        
        # Load the selected strategy module and its corresponding parameter grid from config.py
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
            raise ValueError(f"Unknown strategy selected: {strategy_name}")
            
    def run_simulation(self, df_signals):
        """
        Simulates trading row-by-row based on the signals provided by the strategy.
        """
        reset_ledger() # Clear any fake trades from the previous iteration
        
        balance = getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0)
        peak_balance = balance
        max_drawdown = 0.0
        wins, losses = 0, 0
        trade_returns = []
        
        for i in range(len(df_signals)):
            row = df_signals.iloc[i]
            signal = row.get('signal', 0)
            sl_points = row.get('dynamic_sl_points', 0)
            if sl_points <= 0: 
                sl_points = getattr(config, "STOP_LOSS_POINTS", 150)
                
            price = row['close']
            
            # Check what trades we currently have open
            open_trades = get_open_positions(getattr(config, "SYMBOL", "XAUUSD"))
            has_long = any(t.type == mt5.ORDER_TYPE_BUY for t in open_trades)
            has_short = any(t.type == mt5.ORDER_TYPE_SELL for t in open_trades)
            
            # 1. Evaluate Exit Conditions First
            for trade in open_trades:
                # If we are LONG and the strategy signals a SELL (-1), close the LONG.
                if trade.type == mt5.ORDER_TYPE_BUY and signal == -1:
                    profit = (price - trade.price_open) * trade.volume * (100 if "XAU" in getattr(config, "SYMBOL", "XAUUSD") else 100000)
                    balance += profit
                    close_position(trade.ticket, current_price=price)
                    has_long = False
                    trade_returns.append(profit / getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0))
                    if profit > 0: wins += 1
                    else: losses += 1
                    
                # If we are SHORT and the strategy signals a BUY (1), close the SHORT.
                elif trade.type == mt5.ORDER_TYPE_SELL and signal == 1:
                    profit = (trade.price_open - price) * trade.volume * (100 if "XAU" in getattr(config, "SYMBOL", "XAUUSD") else 100000)
                    balance += profit
                    close_position(trade.ticket, current_price=price)
                    has_short = False
                    trade_returns.append(profit / getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0))
                    if profit > 0: wins += 1
                    else: losses += 1
                    
            # 2. Evaluate Entry Conditions
            if signal != 0:
                # Calculate safe lot size based on account balance and risk %
                lots = calculate_position_size(
                    getattr(config, "SYMBOL", "XAUUSD"), 
                    balance, 
                    getattr(config, "RISK_PERCENT", 1.0), 
                    sl_points, 
                    current_price=price
                )
                
                if lots > 0:
                    if signal == 1 and not has_long:
                        execute_trade(getattr(config, "SYMBOL", "XAUUSD"), mt5.ORDER_TYPE_BUY, lots, price, price - sl_points*0.01, price + sl_points*0.02, getattr(config, "MAGIC_NUMBER", 999111))
                    elif signal == -1 and not has_short:
                        execute_trade(getattr(config, "SYMBOL", "XAUUSD"), mt5.ORDER_TYPE_SELL, lots, price, price + sl_points*0.01, price - sl_points*0.02, getattr(config, "MAGIC_NUMBER", 999111))
                        
            # 3. Track Drawdown
            if balance > peak_balance:
                peak_balance = balance
            drawdown = (peak_balance - balance) / peak_balance
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                
        # 4. Close any lingering trades at the end of the simulation
        open_trades = get_open_positions(getattr(config, "SYMBOL", "XAUUSD"))
        for trade in open_trades:
            close_position(trade.ticket, current_price=price)
            
        # 5. Calculate final scores (Sharpe Ratio)
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
        """
        Runs the strategy on the training data across all possible parameter combinations.
        Returns the best performing parameters based on Win Rate * Sharpe.
        """
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
            
            # Custom Scoring Logic (Sharpe Ratio multiplied by Win Rate)
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
        """
        Runs the strategy one final time on completely unseen data using the best parameters.
        This proves whether the strategy actually works or if it was just overfit to the training data.
        """
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
    """
    Entry point for the backtester. Pulls cached data and kicks off the engine.
    """
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
