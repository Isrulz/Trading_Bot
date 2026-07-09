import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from data.ingestion import get_historical_bars, get_latest_tick

# ---------------------------------------------------------
# Test 1: Verifying Data Formatting and Timezone Conversion
# ---------------------------------------------------------
@patch('data.ingestion.mt5.copy_rates_from_pos')
def test_get_historical_bars(mock_copy_rates):
    # 1. Define the fake data the Mock will return
    # This mimics the exact raw C-style tuple MT5 provides (time, open, high, low, close, tick_volume)
    import numpy as np
    mock_copy_rates.return_value = np.array(
        [(1717804800, 2300.50, 2305.00, 2299.00, 2304.20, 1000)],
        dtype=[('time', '<i8'), ('open', '<f8'), ('high', '<f8'), ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<i8')]
    )
    
    # 2. Execute the function
    # Because of the @patch decorator, this will NOT hit the real MT5 API.
    df = get_historical_bars("XAUUSD", 16385, 1)
    
    # 3. Assertions (The actual testing)
    assert df is not None, "DataFrame should not be None"
    assert 'time' in df.columns, "DataFrame must contain a 'time' column"
    assert df['close'].iloc[0] == 2304.20, "Close price did not map correctly"
    
    # Verify the timezone was successfully localized to Melbourne time
    timezone_str = str(df['time'].iloc[0].tzinfo)
    assert timezone_str == 'Australia/Melbourne', f"Expected Melbourne time, got {timezone_str}"

# ---------------------------------------------------------
# Test 2: Verifying Real-Time Tick Math
# ---------------------------------------------------------
@patch('data.ingestion.mt5.symbol_info_tick')
def test_get_latest_tick(mock_symbol_info_tick):
    # 1. Create a fake MT5 tick object with specific attributes
    fake_tick = MagicMock()
    fake_tick.ask = 2305.50
    fake_tick.bid = 2305.00
    
    # Assign the fake object to our mock
    mock_symbol_info_tick.return_value = fake_tick
    
    # 2. Execute the function
    result = get_latest_tick("XAUUSD")
    
    # 3. Assertions
    assert result is not None
    assert result['ask'] == 2305.50, "Ask price mapped incorrectly"
    assert result['bid'] == 2305.00, "Bid price mapped incorrectly"
    
    # Verify the spread calculation logic is accurate (Ask - Bid)
    assert result['spread'] == 0.50, "Spread calculation is mathematically incorrect"


@patch('data.ingestion.load_historical_data')
@patch('os.path.exists')
def test_get_auto_cached_historical_data_sorting(mock_exists, mock_load):
    mock_exists.return_value = True
    
    # Create a time-reversed dataframe
    reversed_df = pd.DataFrame({
        'time': [pd.Timestamp("2026-01-03"), pd.Timestamp("2026-01-02"), pd.Timestamp("2026-01-01")],
        'value': [3, 2, 1]
    })
    mock_load.return_value = reversed_df
    
    from data.ingestion import get_auto_cached_historical_data
    df = get_auto_cached_historical_data("XAUUSD", 15, 3, "dummy.csv")
    
    assert df is not None
    assert df['time'].iloc[0] == pd.Timestamp("2026-01-01")
    assert df['time'].iloc[1] == pd.Timestamp("2026-01-02")
    assert df['time'].iloc[2] == pd.Timestamp("2026-01-03")
    assert df['value'].iloc[0] == 1
    assert df['value'].iloc[1] == 2
    assert df['value'].iloc[2] == 3