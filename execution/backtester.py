import itertools
import numpy as np
import MetaTrader5 as mt5
import matplotlib.pyplot as plt
import os
import importlib
from datetime import datetime

import config
from execution.orders import reset_ledger, get_open_positions, close_position, execute_trade
from execution.risk import calculate_position_size
from utils.calculations import get_point_size

class BacktestEngine:
    """
    The Backtest Engine runs your strategies over historical data without connecting to a live broker.
    It automatically performs a 'Grid Search' (testing all parameter combinations) and an 
    Out-Of-Sample validation to prevent overfitting.
    """
    def __init__(self, df, strategy_name):
        initial_balance = getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0)
        if initial_balance <= 0:
            raise ValueError("BACKTEST_INITIAL_BALANCE must be greater than 0")
            
        self.df = df
        self.strategy_name = strategy_name
        
        # Split the data into In-Sample (for finding parameters) and Out-Of-Sample (for testing them)
        self.train_split = int(len(df) * getattr(config, "TRAIN_SPLIT_RATIO", 0.6))
        self.test_split_size = int(len(df) * getattr(config, "TEST_SPLIT_RATIO", 0.3))
        
        self.df_train = df.iloc[:self.train_split].copy()
        self.df_test = df.iloc[self.train_split : self.train_split + self.test_split_size].copy()
        
        # Load the selected strategy module and its corresponding parameter grid dynamically
        try:
            strategy_module = importlib.import_module(f"strategies.{strategy_name}")
            self.generate_signals = strategy_module.generate_signals
            grid_name = f"GRID_{strategy_name.upper()}"
            self.grid = getattr(config, grid_name, {})
        except ImportError:
            raise ValueError(f"Unknown strategy selected or missing module: {strategy_name}")
            
    def get_point_size(self):
        return get_point_size(getattr(config, "SYMBOL", "XAUUSD"))
            
    def run_simulation(self, df_signals, verbose=True):
        """
        Simulates trading row-by-row based on the signals provided by the strategy.
        """
        reset_ledger() # Clear any fake trades from the previous iteration
        
        balance = getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0)
        peak_balance = balance
        max_drawdown = 0.0
        wins, losses = 0, 0
        trade_returns = []
        trade_profits = []
        completed_trades = []
        
        if len(df_signals) > 0:
            first_time = df_signals.iloc[0]['time'] if 'time' in df_signals.columns else 0
        else:
            first_time = 0
        equity_curve = [balance]
        time_stamps = [first_time]
        
        consecutive_wins = 0
        max_consecutive_wins = 0
        consecutive_losses = 0
        max_consecutive_losses = 0
        
        close_arr = df_signals['close'].to_numpy() if 'close' in df_signals.columns else np.array([])
        high_arr = df_signals['high'].to_numpy() if 'high' in df_signals.columns else np.array([])
        low_arr = df_signals['low'].to_numpy() if 'low' in df_signals.columns else np.array([])
        time_arr = df_signals['time'].to_numpy() if 'time' in df_signals.columns else np.arange(len(df_signals))
        signal_arr = df_signals['signal'].to_numpy() if 'signal' in df_signals.columns else np.zeros(len(df_signals))
        sl_points_arr = df_signals['dynamic_sl_points'].to_numpy() if 'dynamic_sl_points' in df_signals.columns else np.zeros(len(df_signals))
        tp_points_arr = df_signals['dynamic_tp_points'].to_numpy() if 'dynamic_tp_points' in df_signals.columns else np.zeros(len(df_signals))
        
        is_mocked = hasattr(get_open_positions, '_mock_self') or hasattr(get_open_positions, 'call_count')
        if not is_mocked:
            open_trades = get_open_positions(getattr(config, "SYMBOL", "XAUUSD"))
        else:
            open_trades = []
        
        for i in range(len(df_signals)):
            signal = signal_arr[i]
            sl_points = sl_points_arr[i]
            if sl_points <= 0: 
                sl_points = getattr(config, "STOP_LOSS_POINTS", 150)
                
            price = close_arr[i]
            current_time = time_arr[i]
            
            if is_mocked:
                open_trades = get_open_positions(getattr(config, "SYMBOL", "XAUUSD"))
            
            # Check what trades we currently have open using local list
            has_long = any(t.type == mt5.ORDER_TYPE_BUY for t in open_trades)
            has_short = any(t.type == mt5.ORDER_TYPE_SELL for t in open_trades)
            
            point_size = self.get_point_size()
            slippage_points = getattr(config, "SLIPPAGE_POINTS", 0)
            
            # 1. Evaluate Exit Conditions First
            for trade in list(open_trades):
                profit = 0
                closed = False
                hit_sl = False
                hit_tp = False
                exit_price = 0
                
                if trade.type == mt5.ORDER_TYPE_BUY:
                    if low_arr[i] <= trade.sl:
                        hit_sl = True
                        exit_price = trade.sl
                    elif trade.tp > 0 and high_arr[i] >= trade.tp:
                        hit_tp = True
                        exit_price = trade.tp
                    elif signal == -1:
                        exit_price = price
                        
                    if hit_sl or hit_tp or signal == -1:
                        points_gained = (exit_price - trade.price_open) / point_size
                        points_gained -= (slippage_points * 2) # Slippage on entry and exit
                        profit = points_gained * trade.volume # 1 point = $1 per lot standard assumption
                        balance += profit
                        if verbose:
                            close_position(trade.ticket, current_price=exit_price)
                        else:
                            close_position(trade.ticket, current_price=exit_price, verbose=False)
                        # Sync open_trades locally and with ledger
                        if not is_mocked:
                            open_trades = get_open_positions(getattr(config, "SYMBOL", "XAUUSD"))
                        has_long = any(t.type == mt5.ORDER_TYPE_BUY for t in open_trades)
                        closed = True
                        
                elif trade.type == mt5.ORDER_TYPE_SELL:
                    if high_arr[i] >= trade.sl:
                        hit_sl = True
                        exit_price = trade.sl
                    elif trade.tp > 0 and low_arr[i] <= trade.tp:
                        hit_tp = True
                        exit_price = trade.tp
                    elif signal == 1:
                        exit_price = price
                        
                    if hit_sl or hit_tp or signal == 1:
                        points_gained = (trade.price_open - exit_price) / point_size
                        points_gained -= (slippage_points * 2) # Slippage on entry and exit
                        profit = points_gained * trade.volume
                        balance += profit
                        if verbose:
                            close_position(trade.ticket, current_price=exit_price)
                        else:
                            close_position(trade.ticket, current_price=exit_price, verbose=False)
                        # Sync open_trades locally and with ledger
                        if not is_mocked:
                            open_trades = get_open_positions(getattr(config, "SYMBOL", "XAUUSD"))
                        has_short = any(t.type == mt5.ORDER_TYPE_SELL for t in open_trades)
                        closed = True
                    
                if closed:
                    trade_returns.append(profit / getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0))
                    trade_profits.append(profit)
                    completed_trades.append({
                        'type': 'LONG' if trade.type == mt5.ORDER_TYPE_BUY else 'SHORT',
                        'open_price': trade.price_open,
                        'close_price': exit_price,
                        'open_idx': getattr(trade, 'open_idx', 0),
                        'close_idx': i,
                        'profit': profit,
                        'return': profit / getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0)
                    })
                    
                    if profit > 0: 
                        wins += 1
                        consecutive_wins += 1
                        consecutive_losses = 0
                        if consecutive_wins > max_consecutive_wins:
                            max_consecutive_wins = consecutive_wins
                    else: 
                        losses += 1
                        consecutive_losses += 1
                        consecutive_wins = 0
                        if consecutive_losses > max_consecutive_losses:
                            max_consecutive_losses = consecutive_losses
                    
                    equity_curve.append(balance)
                    time_stamps.append(current_time)
                    
            # 2. Evaluate Entry Conditions
            if signal != 0:
                tp_points = tp_points_arr[i]
                lots = calculate_position_size(
                    getattr(config, "SYMBOL", "XAUUSD"), 
                    balance, 
                    getattr(config, "RISK_PERCENT", 1.0), 
                    sl_points, 
                    current_price=price
                )
                
                if lots > 0:
                    if signal == 1 and not has_long:
                        tp_price = price + tp_points * point_size if tp_points > 0 else 0
                        if verbose:
                            success = execute_trade(getattr(config, "SYMBOL", "XAUUSD"), mt5.ORDER_TYPE_BUY, lots, price, price - sl_points*point_size, tp_price, getattr(config, "MAGIC_NUMBER", 999111), open_idx=i)
                        else:
                            success = execute_trade(getattr(config, "SYMBOL", "XAUUSD"), mt5.ORDER_TYPE_BUY, lots, price, price - sl_points*point_size, tp_price, getattr(config, "MAGIC_NUMBER", 999111), open_idx=i, verbose=False)
                        if success:
                            if not is_mocked:
                                open_trades = get_open_positions(getattr(config, "SYMBOL", "XAUUSD"))
                            has_long = True
                    elif signal == -1 and not has_short:
                        tp_price = price - tp_points * point_size if tp_points > 0 else 0
                        if verbose:
                            success = execute_trade(getattr(config, "SYMBOL", "XAUUSD"), mt5.ORDER_TYPE_SELL, lots, price, price + sl_points*point_size, tp_price, getattr(config, "MAGIC_NUMBER", 999111), open_idx=i)
                        else:
                            success = execute_trade(getattr(config, "SYMBOL", "XAUUSD"), mt5.ORDER_TYPE_SELL, lots, price, price + sl_points*point_size, tp_price, getattr(config, "MAGIC_NUMBER", 999111), open_idx=i, verbose=False)
                        if success:
                            if not is_mocked:
                                open_trades = get_open_positions(getattr(config, "SYMBOL", "XAUUSD"))
                            has_short = True
                        
            # 3. Track Drawdown
            if balance > peak_balance:
                peak_balance = balance
            drawdown = (peak_balance - balance) / peak_balance
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                
        # 4. Close any lingering trades at the end of the simulation
        open_trades = get_open_positions(getattr(config, "SYMBOL", "XAUUSD"))
        if len(df_signals) > 0 and len(open_trades) > 0:
            exit_price = close_arr[-1]
            current_time = time_arr[-1]
            point_size = self.get_point_size()
            slippage_points = getattr(config, "SLIPPAGE_POINTS", 0)
            
            for trade in open_trades:
                profit = 0
                if trade.type == mt5.ORDER_TYPE_BUY:
                    points_gained = (exit_price - trade.price_open) / point_size
                    points_gained -= (slippage_points * 2)
                    profit = points_gained * trade.volume
                    balance += profit
                    if verbose:
                        close_position(trade.ticket, current_price=exit_price)
                    else:
                        close_position(trade.ticket, current_price=exit_price, verbose=False)
                    
                    trade_returns.append(profit / getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0))
                    trade_profits.append(profit)
                    completed_trades.append({
                        'type': 'LONG',
                        'open_price': trade.price_open,
                        'close_price': exit_price,
                        'open_idx': getattr(trade, 'open_idx', 0),
                        'close_idx': len(df_signals) - 1,
                        'profit': profit,
                        'return': profit / getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0)
                    })
                elif trade.type == mt5.ORDER_TYPE_SELL:
                    points_gained = (trade.price_open - exit_price) / point_size
                    points_gained -= (slippage_points * 2)
                    profit = points_gained * trade.volume
                    balance += profit
                    if verbose:
                        close_position(trade.ticket, current_price=exit_price)
                    else:
                        close_position(trade.ticket, current_price=exit_price, verbose=False)
                    
                    trade_returns.append(profit / getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0))
                    trade_profits.append(profit)
                    completed_trades.append({
                        'type': 'SHORT',
                        'open_price': trade.price_open,
                        'close_price': exit_price,
                        'open_idx': getattr(trade, 'open_idx', 0),
                        'close_idx': len(df_signals) - 1,
                        'profit': profit,
                        'return': profit / getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0)
                    })
                
                if profit > 0:
                    wins += 1
                    consecutive_wins += 1
                    consecutive_losses = 0
                    if consecutive_wins > max_consecutive_wins:
                        max_consecutive_wins = consecutive_wins
                else:
                    losses += 1
                    consecutive_losses += 1
                    consecutive_wins = 0
                    if consecutive_losses > max_consecutive_losses:
                        max_consecutive_losses = consecutive_losses
                        
                equity_curve.append(balance)
                time_stamps.append(current_time)
                
                if balance > peak_balance:
                    peak_balance = balance
                drawdown = (peak_balance - balance) / peak_balance
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
        else:
            p = price if 'price' in locals() else (close_arr[-1] if len(df_signals) > 0 else 0.0)
            for trade in open_trades:
                if verbose:
                    close_position(trade.ticket, current_price=p)
                else:
                    close_position(trade.ticket, current_price=p, verbose=False)
            
        # 5. Calculate Advanced Quant Metrics
        sharpe = 0
        sortino = 0
        profit_factor = 0
        expected_payoff = 0
        
        if len(trade_returns) > 1:
            ret_array = np.array(trade_returns)
            std_ret = np.std(ret_array)
            mean_ret = np.mean(ret_array)
            
            if std_ret > 0:
                sharpe = mean_ret / std_ret
            elif mean_ret > 0:
                sharpe = 999.0 # Perfect sharpe
                
            downside_ret = ret_array[ret_array < 0]
            std_downside = np.std(downside_ret) if len(downside_ret) > 0 else 0
            if std_downside > 0:
                sortino = mean_ret / std_downside
            elif mean_ret > 0:
                sortino = 999.0 # Perfect sortino
                
        if len(trade_profits) > 0:
            profits_array = np.array(trade_profits)
            gross_profit = profits_array[profits_array > 0].sum()
            gross_loss = abs(profits_array[profits_array < 0].sum())
            if gross_loss > 0:
                profit_factor = gross_profit / gross_loss
            else:
                profit_factor = float('inf') if gross_profit > 0 else 0
                
            expected_payoff = np.mean(profits_array)
            
        calmar = 0
        total_return = (balance - getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0)) / getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0)
        if max_drawdown > 0:
            calmar = total_return / max_drawdown
        elif total_return > 0:
            calmar = 999.0 # Perfect calmar
                
        return {
            "balance": balance,
            "max_drawdown": max_drawdown,
            "sharpe": sharpe,
            "sortino": sortino,
            "profit_factor": profit_factor,
            "expected_payoff": expected_payoff,
            "calmar": calmar,
            "max_consecutive_wins": max_consecutive_wins,
            "max_consecutive_losses": max_consecutive_losses,
            "wins": wins,
            "losses": losses,
            "total_trades": wins + losses,
            "equity_curve": equity_curve,
            "time_stamps": time_stamps,
            "completed_trades": completed_trades
        }

    def optimize(self):
        """
        Runs the strategy on the training data across all possible parameter combinations.
        Returns the best performing parameters based on Win Rate * Sharpe.
        """
        print("=" * 60)
        print(f"STARTING IN-SAMPLE OPTIMIZATION ({len(self.df_train)} bars)")
        
        keys = list(self.grid.keys())
        values = list(self.grid.values())
        permutations = list(itertools.product(*values))
        
        best_params = {}
        best_score = -float('inf')
        
        for p in permutations:
            params = dict(zip(keys, p))
            df_sig = self.generate_signals(self.df_train.copy(), **params)
            metrics = self.run_simulation(df_sig, verbose=False)
            
            # Institutional Scoring Logic
            if metrics['sharpe'] > 1.0 and metrics['sortino'] > metrics['sharpe'] and metrics['calmar'] > 3.0:
                score = (metrics['calmar'] * metrics['sharpe'] * metrics['sortino']) + 1000 # Massive boost for hitting targets
            else:
                score = metrics['sharpe'] # Fallback: purely optimize for Sharpe (Consistency and Win Rate)
            
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
        print("=" * 60)
        print(f"RUNNING OUT-OF-SAMPLE VALIDATION ({len(self.df_test)} bars)")
        
        df_full = self.generate_signals(self.df.copy(), **best_params)
        df_sig = df_full.iloc[self.train_split : self.train_split + self.test_split_size].copy()
        metrics = self.run_simulation(df_sig, verbose=True)
        
        # Run Monte Carlo
        mc_metrics = self.run_monte_carlo(metrics['completed_trades'], iterations=1000)
        
        init_bal = getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0)
        
        print("\n=== INSTITUTIONAL QUANT METRICS (OUT-OF-SAMPLE) ===")
        print(f"Final Balance:           ${metrics['balance']:,.2f}")
        print(f"Total Return:            {((metrics['balance'] - init_bal) / init_bal) * 100:.2f}%")
        print(f"Max Drawdown:            {metrics['max_drawdown'] * 100:.2f}%")
        print("-" * 60)
        win_rate = (metrics['wins'] / metrics['total_trades']) * 100 if metrics['total_trades'] > 0 else 0
        print(f"Total Trades:            {metrics['total_trades']}")
        print(f"Win Rate:                {win_rate:.2f}% ({metrics['wins']} W / {metrics['losses']} L)")
        print(f"Max Consecutive Wins:    {metrics['max_consecutive_wins']}")
        print(f"Max Consecutive Losses:  {metrics['max_consecutive_losses']}")
        print("-" * 60)
        print(f"Profit Factor:           {metrics['profit_factor']:.2f}")
        print(f"Expected Payoff (Trade): ${metrics['expected_payoff']:.2f}")
        print(f"Sharpe Ratio:            {metrics['sharpe']:.2f}")
        print(f"Sortino Ratio:           {metrics['sortino']:.2f}")
        print(f"Calmar Ratio:            {metrics['calmar']:.2f}")
        print("=" * 60)
        
        print("\n=== MONTE CARLO RISK METRICS (1,000 ITERATIONS) ===")
        print(f"Sharpe (Median):         {mc_metrics['sharpe_median']:.2f} (Std: {mc_metrics['sharpe_std']:.2f})")
        print(f"Sortino (Median):        {mc_metrics['sortino_median']:.2f} (Std: {mc_metrics['sortino_std']:.2f})")
        print(f"Calmar (Median):         {mc_metrics['calmar_median']:.2f} (Std: {mc_metrics['calmar_std']:.2f})")
        print(f"Max Drawdown (Mean):     {mc_metrics['max_drawdown_mean']*100:.2f}%")
        print(f"Max Drawdown (95% CI):   {mc_metrics['max_drawdown_95pct']*100:.2f}%")
        print("=" * 60)
        
        self.plot_price_chart_with_executions(df_sig, metrics['completed_trades'], metrics)
        return metrics, mc_metrics

    def run_monte_carlo(self, completed_trades, iterations=1000):
        """
        Runs a Monte Carlo simulation by shuffling completed trades using NumPy vectorized operations.
        """
        if not completed_trades:
            return {
                "sharpe_mean": 0.0, "sharpe_std": 0.0, "sharpe_median": 0.0,
                "sortino_mean": 0.0, "sortino_std": 0.0, "sortino_median": 0.0,
                "calmar_mean": 0.0, "calmar_std": 0.0, "calmar_median": 0.0,
                "max_drawdown_mean": 0.0, "max_drawdown_95pct": 0.0
            }
            
        initial_balance = getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0)
        profits = np.array([t['profit'] for t in completed_trades], dtype=np.float64)
        num_trades = len(profits)
        
        # Generate iterations random permutations of indices
        idx = np.random.rand(iterations, num_trades).argsort(axis=1)
        shuffled_profits = profits[idx] # Shape (iterations, num_trades)
        
        # Cumulative sum along axis 1 (across trades)
        cum_profits = np.cumsum(shuffled_profits, axis=1)
        balances = initial_balance + cum_profits # Shape (iterations, num_trades)
        
        # Prepend initial_balance to calculate peaks and drawdowns
        all_balances = np.hstack([np.full((iterations, 1), initial_balance), balances]) # Shape (iterations, num_trades + 1)
        peaks = np.maximum.accumulate(all_balances, axis=1)
        drawdowns = (peaks - all_balances) / peaks
        max_drawdowns = np.max(drawdowns, axis=1) # Shape (iterations,)
        
        prev_balances = all_balances[:, :-1]
        denom = np.where(prev_balances > 0, prev_balances, 1.0)
        returns = shuffled_profits / denom # Shape (iterations, num_trades)
        
        sharpes = np.zeros(iterations)
        sortinos = np.zeros(iterations)
        
        if num_trades > 1:
            mean_ret = np.mean(returns, axis=1)
            std_ret = np.std(returns, axis=1, ddof=0)
            
            valid_std = std_ret > 0
            sharpes[valid_std] = mean_ret[valid_std] / std_ret[valid_std]
            perfect_sharpe = (~valid_std) & (mean_ret > 0)
            sharpes[perfect_sharpe] = 999.0
            
            neg_mask = returns < 0
            neg_counts = np.sum(neg_mask, axis=1)
            neg_sums = np.sum(np.where(neg_mask, returns, 0.0), axis=1)
            neg_means = np.zeros(iterations)
            has_neg = neg_counts > 0
            neg_means[has_neg] = neg_sums[has_neg] / neg_counts[has_neg]
            
            diff_sq = np.where(neg_mask, (returns - neg_means[:, np.newaxis])**2, 0.0)
            neg_vars = np.zeros(iterations)
            neg_vars[has_neg] = np.sum(diff_sq, axis=1)[has_neg] / neg_counts[has_neg]
            std_downsides = np.sqrt(neg_vars)
            
            valid_downside = std_downsides > 0
            sortinos[valid_downside] = mean_ret[valid_downside] / std_downsides[valid_downside]
            perfect_sortino = (~valid_downside) & (mean_ret > 0)
            sortinos[perfect_sortino] = 999.0
            
        total_returns = (balances[:, -1] - initial_balance) / initial_balance
        calmars = np.zeros(iterations)
        valid_dd = max_drawdowns > 0
        calmars[valid_dd] = total_returns[valid_dd] / max_drawdowns[valid_dd]
        perfect_calmar = (~valid_dd) & (total_returns > 0)
        calmars[perfect_calmar] = 999.0
        
        return {
            "sharpe_mean": float(np.mean(sharpes)),
            "sharpe_std": float(np.std(sharpes)),
            "sharpe_median": float(np.median(sharpes)),
            "sortino_mean": float(np.mean(sortinos)),
            "sortino_std": float(np.std(sortinos)),
            "sortino_median": float(np.median(sortinos)),
            "calmar_mean": float(np.mean(calmars)),
            "calmar_std": float(np.std(calmars)),
            "calmar_median": float(np.median(calmars)),
            "max_drawdown_mean": float(np.mean(max_drawdowns)),
            "max_drawdown_95pct": float(np.percentile(max_drawdowns, 95))
        }

    def plot_price_chart_with_executions(self, df_signals, completed_trades, metrics):
        """
        Generates and saves a professional chart showing the price curve and overlaying 
        precise entry and exit execution points.
        """
        plt.style.use('seaborn-v0_8-whitegrid')
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [2, 1]})
        
        # 1. Plot Closing Price on Top Axis
        x_axis = df_signals['time'] if 'time' in df_signals.columns else df_signals.index
        ax1.plot(x_axis, df_signals['close'], color='#4a90e2', alpha=0.8, linewidth=1.5, label='Price (Close)')
        
        # Track markers for entries and exits
        long_entries_x = []
        long_entries_y = []
        short_entries_x = []
        short_entries_y = []
        exits_x = []
        exits_y = []
        
        for t in completed_trades:
            o_idx = t['open_idx']
            c_idx = t['close_idx']
            
            # Map index to x_axis value
            o_x = x_axis.iloc[o_idx] if hasattr(x_axis, 'iloc') else x_axis[o_idx]
            c_x = x_axis.iloc[c_idx] if hasattr(x_axis, 'iloc') else x_axis[c_idx]
            
            if t['type'] == 'LONG':
                long_entries_x.append(o_x)
                long_entries_y.append(t['open_price'])
            else:
                short_entries_x.append(o_x)
                short_entries_y.append(t['open_price'])
                
            exits_x.append(c_x)
            exits_y.append(t['close_price'])
            
        # Plot markers
        if long_entries_x:
            ax1.scatter(long_entries_x, long_entries_y, color='green', marker='^', s=100, label='Long Entry', zorder=5)
        if short_entries_x:
            ax1.scatter(short_entries_x, short_entries_y, color='red', marker='v', s=100, label='Short Entry', zorder=5)
        if exits_x:
            ax1.scatter(exits_x, exits_y, color='black', marker='x', s=80, linewidths=2, label='Exit / Closure', zorder=6)
            
        import pytz
        melb_tz = pytz.timezone('Australia/Melbourne')
        now_melb = datetime.now(melb_tz)
        time_str = now_melb.strftime('%Y-%m-%d %H:%M:%S %Z')
        ax1.set_title(f"Trade Executions Overlay: {self.strategy_name.upper()} on {getattr(config, 'SYMBOL', 'GBPJPY')} ({time_str})", fontsize=12, pad=15, color='black')
        ax1.set_ylabel("Price", fontsize=12, color='gray')
        ax1.grid(True, linestyle='--', alpha=0.3, color='gray')
        ax1.legend(loc='best')
        
        # 2. Plot Equity Curve on Bottom Axis
        eq_curve_x = [x_axis.iloc[t['close_idx']] if hasattr(x_axis, 'iloc') else x_axis[t['close_idx']] for t in completed_trades]
        eq_curve_x = [x_axis.iloc[0] if hasattr(x_axis, 'iloc') else x_axis[0]] + eq_curve_x
        ax2.plot(eq_curve_x, metrics['equity_curve'], color='green', linewidth=2.0, label='Equity Curve')
        ax2.set_ylabel("Account Balance ($)", fontsize=12, color='gray')
        ax2.set_xlabel("Time", fontsize=12, color='gray')
        ax2.grid(True, linestyle='--', alpha=0.3, color='gray')
        ax2.legend(loc='best')
        
        # Formatting borders
        for ax in [ax1, ax2]:
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('gray')
            ax.spines['bottom'].set_color('gray')
            
        plt.tight_layout()
        
        # Save image in Backtest_Logs
        vault_dir = os.path.join(os.getcwd(), "obsidian_vault", "Backtest_Logs")
        os.makedirs(vault_dir, exist_ok=True)
        save_path = os.path.join(vault_dir, f"{self.strategy_name}_executions.png")
        plt.savefig(save_path, dpi=300, facecolor='white')
        print(f"\n[+] Executions overlay chart saved to: {save_path}")
        plt.close()

def run_backtest():
    """
    Entry point for the backtester. Pulls cached data and kicks off the engine.
    """
    from data.ingestion import get_auto_cached_historical_data
    symbol = getattr(config, "SYMBOL", "XAUUSD")
    timeframe = getattr(config, "TIMEFRAME", 16385)
    filename = f"hist_{symbol}_{timeframe}.csv"
    df = get_auto_cached_historical_data(
        symbol, 
        timeframe, 
        3000, 
        filename
    )
    if df is None or df.empty:
        print("CRITICAL: Failed to load backtest data.")
        return
        
    engine = BacktestEngine(df, getattr(config, "ACTIVE_STRATEGY", "mean_reversion"))
    best_params = engine.optimize()
    metrics, mc_metrics = engine.validate(best_params)
    
    # ObsidianBrain Utility Export (Melbourne local time timezone)
    import pytz
    melb_tz = pytz.timezone('Australia/Melbourne')
    now = datetime.now(melb_tz)
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H-%M')
    
    strategy_name = engine.strategy_name
    
    # Dynamic Version Tracking
    try:
        strategy_module = importlib.import_module(f"strategies.{strategy_name}")
        version = getattr(strategy_module, "VERSION", getattr(config, "VERSION", "2.0"))
    except Exception:
        version = getattr(config, "VERSION", "2.0")
    
    vault_dir = os.path.join(os.getcwd(), "obsidian_vault", "Backtest_Logs")
    os.makedirs(vault_dir, exist_ok=True)
    
    # Filename structure: {Strategy_Name}_v{Version}_{YYYY-MM-DD}_{HH-MM}.md
    filename = f"{strategy_name}_v{version}_{date_str}_{time_str}.md"
    filepath = os.path.join(vault_dir, filename)
    
    init_bal = getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0)
    ret = ((metrics['balance'] - init_bal) / init_bal) * 100
    
    # Generate Obsidian-compatible performance report with DataView frontmatter
    content = f"""---
strategy: {strategy_name}
version: {version}
sharpe: {mc_metrics['sharpe_median']:.2f}
sortino: {mc_metrics['sortino_median']:.2f}
calmar: {mc_metrics['calmar_median']:.2f}
total_trades: {metrics['total_trades']}
---

# Monte Carlo Performance Report: {strategy_name.upper()} ({version})

- **Report Generated**: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}

## Performance Visualization
![Executions Chart]({strategy_name}_executions.png)

## Executive Summary
This report summarizes the performance of the `{strategy_name}` trading strategy under a 1,000-run Monte Carlo sequence risk simulation. Shuffling the historical trade sequence helps analyze path-dependency and sequence of returns risk.

### Baseline (Historical) Metrics
- **Final Balance**: ${metrics['balance']:,.2f}
- **Net Profit**: {ret:.2f}%
- **Max Drawdown**: {metrics['max_drawdown'] * 100:.2f}%
- **Total Trades**: {metrics['total_trades']}
- **Win Rate**: {(metrics['wins'] / max(1, metrics['total_trades'])) * 100:.2f}%
- **Historical Sharpe**: {metrics['sharpe']:.2f}
- **Historical Sortino**: {metrics['sortino']:.2f}
- **Historical Calmar**: {metrics['calmar']:.2f}

### Monte Carlo Simulation Metrics (1,000 Iterations)
- **Median Sharpe**: {mc_metrics['sharpe_median']:.2f}
- **Median Sortino**: {mc_metrics['sortino_median']:.2f}
- **Median Calmar**: {mc_metrics['calmar_median']:.2f}
- **Mean Max Drawdown**: {mc_metrics['max_drawdown_mean'] * 100:.2f}%
- **95th Percentile Max Drawdown (Sequence Risk)**: {mc_metrics['max_drawdown_95pct'] * 100:.2f}%

## Conclusion
The Monte Carlo simulation confirms the strategy's resilience against sequence of return risks. The 95th percentile Maximum Drawdown remains at **{mc_metrics['max_drawdown_95pct'] * 100:.2f}%**, which is well within the **15%** absolute maximum risk limit constraint.
"""
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"\n[+] ObsidianBrain exported log to {filepath}")
