import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import config
from data.ingestion import get_auto_cached_historical_data
from execution.backtester import BacktestEngine

SYMBOLS = ["GBPJPY", "AUDJPY", "GBPAUD"]
STRATEGIES = ["mean_reversion", "zscore_momentum", "supertrend"]
TIMEFRAME = 15 # M15 Timeframe for higher frequency (1 trade/day minimum)

def run_mass_test():
    results = []
    
    for sym in SYMBOLS:
        print(f"\nFETCHING DATA FOR {sym}...")
        df = get_auto_cached_historical_data(
            sym, 
            TIMEFRAME, 
            3000, 
            f"hist_{sym}_{TIMEFRAME}.csv"
        )
        if df is None or df.empty:
            print(f"Skipping {sym} - Data failure")
            continue
            
        for strat in STRATEGIES:
            print(f"\n{'='*50}")
            print(f" TESTING: {strat.upper()} on {sym}")
            print(f"{'='*50}")
            
            config.SYMBOL = sym
            config.ACTIVE_STRATEGY = strat
            
            try:
                engine = BacktestEngine(df, strat)
                best_params = engine.optimize()
                
                # Get In-Sample metrics for Overfitting Analysis
                df_is_sig = engine.generate_signals(engine.df_train.copy(), **best_params)
                is_metrics = engine.run_simulation(df_is_sig)
                
                # Disable plotting for mass backtest
                engine.plot_price_chart_with_executions = lambda *args, **kwargs: None
                
                # Get Out-Of-Sample metrics
                oos_metrics, mc_metrics = engine.validate(best_params)
                
                results.append({
                    "Symbol": sym,
                    "Strategy": strat,
                    "Trades(IS)": is_metrics.get('total_trades', 0),
                    "Sharpe(IS)": round(is_metrics.get('sharpe', 0), 2),
                    "Trades(OOS)": oos_metrics.get('total_trades', 0),
                    "Sharpe(OOS)": round(oos_metrics.get('sharpe', 0), 2),
                    "WinRate(OOS)": round((oos_metrics.get('wins', 0) / max(1, oos_metrics.get('total_trades', 1)))*100, 1),
                    "DD(OOS)": round(oos_metrics.get('max_drawdown', 0)*100, 1),
                    "ProfFact(OOS)": round(oos_metrics.get('profit_factor', 0), 2)
                })
            except Exception as e:
                print(f"FAILED {strat} on {sym}: {e}")
                
    df_res = pd.DataFrame(results)
    df_res.to_csv("mass_backtest_reiterated.csv", index=False)
    print("\n\n=== MASS BACKTEST COMPLETE ===")
    print(df_res.to_string())

if __name__ == "__main__":
    run_mass_test()
