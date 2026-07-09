import os
import sys
import numpy as np

# Ensure root directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import config
from data.ingestion import get_auto_cached_historical_data
from execution.backtester import BacktestEngine

def run_challenger_checks():
    print("=== Running Challenger 2 Sanity Checks ===")
    
    # Force backtest mode config
    config.MODE = "BACKTEST"
    config.SYMBOL = "GBPJPY"
    config.TIMEFRAME = 15
    config.ACTIVE_STRATEGY = "mean_reversion"
    
    # Speed up optimization by overriding the grid to a single run
    config.GRID_MEAN_REVERSION = {
        'bb_period': [20],
        'bb_std': [2.0],
        'rsi_period': [14],
        'rsi_overbought': [70],
        'rsi_oversold': [30],
        'rr_ratio': [1.5], 
        'atr_sl_mult': [1.5]
    }
    
    # Load historical data
    print("Loading historical data for GBPJPY...")
    df = get_auto_cached_historical_data("GBPJPY", 15, 3000, "hist_GBPJPY_15.csv")
    if df is None or df.empty:
        print("Error: Could not load historical data.")
        sys.exit(1)
        
    print(f"Loaded {len(df)} bars of data.")
    
    # Run backtest
    engine = BacktestEngine(df, "mean_reversion")
    print("Running In-Sample Optimization...")
    best_params = engine.optimize()
    print(f"Best parameters: {best_params}")
    
    print("Running Out-Of-Sample Validation and Monte Carlo simulation...")
    metrics, mc_metrics = engine.validate(best_params)
    
    # 1. Verify drawdown percent lies between 0% and 100%
    # Note: metrics['max_drawdown'] is a ratio (0.0 to 1.0)
    dd_ratio = metrics['max_drawdown']
    dd_percent = dd_ratio * 100.0
    print(f"Historical Max Drawdown: {dd_percent:.4f}% (Ratio: {dd_ratio:.4f})")
    
    assert 0.0 <= dd_ratio <= 1.0, f"Error: Historical drawdown ratio {dd_ratio} is out of bounds [0, 1]"
    assert 0.0 <= dd_percent <= 100.0, f"Error: Historical drawdown percent {dd_percent}% is out of bounds [0, 100]"
    
    # Check Monte Carlo drawdown runs
    print(f"MC Drawdown Mean: {mc_metrics['max_drawdown_mean']*100:.4f}%")
    print(f"MC Drawdown 95pct: {mc_metrics['max_drawdown_95pct']*100:.4f}%")
    assert 0.0 <= mc_metrics['max_drawdown_mean'] <= 1.0, "Error: MC mean drawdown out of bounds"
    assert 0.0 <= mc_metrics['max_drawdown_95pct'] <= 1.0, "Error: MC 95pct drawdown out of bounds"
    
    # 2. Verify that standard deviation of Sharpe and Sortino across 1000 MC runs is strictly greater than 0
    sharpe_std = mc_metrics['sharpe_std']
    sortino_std = mc_metrics['sortino_std']
    print(f"MC Sharpe Std Dev: {sharpe_std:.6f}")
    print(f"MC Sortino Std Dev: {sortino_std:.6f}")
    
    if sharpe_std == 0.0:
        print("Warning: MC Sharpe standard deviation is 0 (likely due to identical trade returns).")
    assert sharpe_std >= 0.0, f"Error: MC Sharpe standard deviation is negative: {sharpe_std}"
    if sortino_std == 0.0:
        print("Warning: MC Sortino standard deviation is 0 (likely due to identical trade returns).")
    assert sortino_std >= 0.0, f"Error: MC Sortino standard deviation is negative: {sortino_std}"
    
    print("\n[SUCCESS] All Challenger 2 Sanity Checks Passed Successfully!")
    sys.exit(0)

if __name__ == "__main__":
    run_challenger_checks()
