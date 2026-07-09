import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
import config
from execution.backtester import BacktestEngine

# A dummy strategy generator
def mock_generate_signals(df, **kwargs):
    df = df.copy()
    # Generate alternating signals
    df['signal'] = 0
    df.loc[df.index % 4 == 0, 'signal'] = 1
    df.loc[df.index % 4 == 2, 'signal'] = -1
    df['dynamic_sl_points'] = 50
    df['dynamic_tp_points'] = 100
    return df

def test_monte_carlo_non_zero_std():
    # Create dummy price data (rising trend so we have some wins/losses)
    dates = pd.date_range(start="2026-01-01", periods=100, freq="h")
    prices = [100.0 + i * 0.1 for i in range(100)]
    df = pd.DataFrame({
        'time': dates,
        'open': prices,
        'high': [p + 0.5 for p in prices],
        'low': [p - 0.5 for p in prices],
        'close': prices,
        'tick_volume': [100] * 100
    })
    
    # Instantiate backtest engine using mean_reversion as the strategy template
    engine = BacktestEngine(df, "mean_reversion")
    engine.generate_signals = mock_generate_signals
    
    # Set mock MT5 positions to return empty
    with patch('execution.backtester.get_open_positions') as mock_get_positions, \
         patch('execution.backtester.execute_trade') as mock_exec, \
         patch('execution.backtester.close_position') as mock_close:
        
        mock_get_positions.return_value = []
        
        # We need to simulate completed trades
        # Create some mock trades with different profits
        completed_trades = [
            {'profit': 100.0, 'return': 0.01, 'type': 'LONG', 'open_price': 100, 'close_price': 101, 'open_idx': 1, 'close_idx': 5},
            {'profit': -50.0, 'return': -0.005, 'type': 'SHORT', 'open_price': 101, 'close_price': 101.5, 'open_idx': 6, 'close_idx': 10},
            {'profit': 200.0, 'return': 0.02, 'type': 'LONG', 'open_price': 100, 'close_price': 102, 'open_idx': 11, 'close_idx': 15},
            {'profit': -100.0, 'return': -0.01, 'type': 'SHORT', 'open_price': 102, 'close_price': 103, 'open_idx': 16, 'close_idx': 20},
        ]
        
        mc_metrics = engine.run_monte_carlo(completed_trades, iterations=50)
        
        # Verify standard deviation of Sharpe and Sortino across runs is non-zero
        assert mc_metrics['sharpe_std'] > 0.0, f"Expected non-zero Sharpe std, got {mc_metrics['sharpe_std']}"
        assert mc_metrics['sortino_std'] > 0.0, f"Expected non-zero Sortino std, got {mc_metrics['sortino_std']}"

def test_lingering_positions_simulation():
    dates = pd.date_range(start="2026-01-01", periods=10, freq="h")
    prices = [100.0] * 10
    df = pd.DataFrame({
        'time': dates,
        'open': prices,
        'high': prices,
        'low': prices,
        'close': prices,
        'tick_volume': [100] * 10
    })
    
    engine = BacktestEngine(df, "mean_reversion")
    engine.generate_signals = mock_generate_signals
    
    # We want to mock get_open_positions such that at the end of the loop, there is still an open trade
    fake_trade = MagicMock()
    fake_trade.ticket = 12345
    fake_trade.type = 0 # ORDER_TYPE_BUY
    fake_trade.price_open = 95.0
    fake_trade.volume = 1.0
    fake_trade.sl = 90.0
    fake_trade.tp = 110.0
    fake_trade.open_idx = 0
    
    # Track actions
    closed_tickets = []
    def mock_close(ticket, current_price):
        closed_tickets.append(ticket)
        return True
        
    with patch('execution.backtester.get_open_positions') as mock_get_positions, \
         patch('execution.backtester.close_position', side_effect=mock_close), \
         patch('execution.backtester.execute_trade'):
        
        # First call inside loop: returns empty
        # Second call at end of loop (lingering positions check): returns the fake trade
        mock_get_positions.side_effect = [
            [], [], [], [], [], [], [], [], [], [], # 10 iterations of the loop
            [fake_trade] # end of loop lingering positions
        ]
        
        # Run simulation
        metrics = engine.run_simulation(df)
        
        # The lingering position should have been closed
        assert 12345 in closed_tickets
        # The metrics should record the completed trade
        assert len(metrics['completed_trades']) == 1
        assert metrics['completed_trades'][0]['profit'] == (100.0 - 95.0) / engine.get_point_size() - (getattr(config, "SLIPPAGE_POINTS", 0) * 2)


def test_backtest_engine_invalid_initial_balance():
    # Save the current config balance
    old_balance = getattr(config, "BACKTEST_INITIAL_BALANCE", 10000.0)
    
    # Create a dummy DataFrame
    df = pd.DataFrame({'time': [pd.Timestamp("2026-01-01")]})
    
    try:
        # Set balance <= 0
        config.BACKTEST_INITIAL_BALANCE = 0
        with pytest.raises(ValueError, match="BACKTEST_INITIAL_BALANCE must be greater than 0"):
            BacktestEngine(df, "mean_reversion")
            
        config.BACKTEST_INITIAL_BALANCE = -500
        with pytest.raises(ValueError, match="BACKTEST_INITIAL_BALANCE must be greater than 0"):
            BacktestEngine(df, "mean_reversion")
    finally:
        # Restore old balance
        config.BACKTEST_INITIAL_BALANCE = old_balance

