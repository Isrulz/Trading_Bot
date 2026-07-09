import pandas as pd
import numpy as np
from utils.indicators import calculate_rsi, calculate_atr
from utils.calculations import get_point_size
from utils.time_sync import NEW_YORK_TZ
import config

VERSION = "1.0"

def generate_signals(df, **kwargs):
    """
    Opening Range Breakout (ORB) Strategy for NYSE Open.
    Calculates the high and low range of the first N minutes of the NYSE session (9:30 AM EST)
    and enters on a breakout confirmed by volatility, volume, and momentum filters.
    All positions are squared off before the NYSE market close.
    """
    # --- Strategy Parameters ---
    orb_lookback_minutes = kwargs.get('orb_lookback_minutes', 30)  # Duration of the opening range
    min_atr_mult = kwargs.get('min_atr_mult', 0.3)                  # Min opening range height relative to ATR
    max_atr_mult = kwargs.get('max_atr_mult', 2.5)                  # Max opening range height relative to ATR
    use_volume_filter = kwargs.get('use_volume_filter', True)       # Toggle volume filter
    use_rsi_filter = kwargs.get('use_rsi_filter', True)             # Toggle RSI momentum filter
    use_trend_filter = kwargs.get('use_trend_filter', False)        # Toggle trend filter
    trend_filter_period = kwargs.get('trend_filter_period', 200)    # Trend filter EMA period
    vol_ma_mult = kwargs.get('vol_ma_mult', 1.2)                    # Volume breakout multiplier
    rsi_period = kwargs.get('rsi_period', 14)                       # RSI indicator period
    rsi_low = kwargs.get('rsi_low', 30)                             # RSI oversold boundary for shorts
    rsi_high = kwargs.get('rsi_high', 70)                           # RSI overbought boundary for longs
    atr_sl_mult = kwargs.get('atr_sl_mult', 1.5)                    # ATR multiplier for SL if using ATR SL
    sl_type = kwargs.get('sl_type', 'range')                        # 'range' (opposite of ORB range) or 'atr'
    rr_ratio = kwargs.get('rr_ratio', 2.0)                          # Risk-to-reward ratio for Take Profit

    # Safe check for minimum historical data
    min_bars = max(rsi_period, 20) + 10
    if len(df) < min_bars:
        df['signal'] = 0
        df['dynamic_sl_points'] = 0
        df['dynamic_tp_points'] = 0
        df['exit_now'] = False
        return df

    # --- Time Synchronization ---
    # Convert timestamps to America/New_York
    if not pd.api.types.is_datetime64_any_dtype(df['time']):
        times = pd.to_datetime(df['time'])
    else:
        times = df['time']

    if times.dt.tz is None:
        times = times.dt.localize('UTC')
    times_ny = times.dt.tz_convert(NEW_YORK_TZ)
    
    df['date_ny'] = times_ny.dt.date
    df['minutes_ny'] = times_ny.dt.hour * 60 + times_ny.dt.minute

    # --- Technical Indicators ---
    df['ATR'] = calculate_atr(df, period=14)
    df['RSI'] = calculate_rsi(df['close'], period=rsi_period)
    df['vol_ma'] = df['tick_volume'].rolling(20).mean()
    df['ema_trend'] = df['close'].ewm(span=trend_filter_period, adjust=False).mean()

    # --- Calculate Opening Range High / Low ---
    # NYSE opens at 9:30 AM EST (570 minutes from midnight)
    nyse_open_m = 570
    orb_end_m = nyse_open_m + orb_lookback_minutes

    # Mask for the opening range period
    orb_mask = (df['minutes_ny'] >= nyse_open_m) & (df['minutes_ny'] < orb_end_m)

    # Find the high and low during the opening range for each day
    daily_highs = df[orb_mask].groupby('date_ny')['high'].max()
    daily_lows = df[orb_mask].groupby('date_ny')['low'].min()

    # Map the daily opening range high/low back to every row of that day
    df['orb_high'] = df['date_ny'].map(daily_highs)
    df['orb_low'] = df['date_ny'].map(daily_lows)

    # --- Setup for Breakout Signals ---
    # Shift variables to avoid look-ahead bias (making decisions on the last closed bar)
    df['close_prev'] = df['close'].shift(1)
    df['close_prev_prev'] = df['close'].shift(2)
    df['volume_prev'] = df['tick_volume'].shift(1)
    df['vol_ma_prev'] = df['vol_ma'].shift(1)
    df['RSI_prev'] = df['RSI'].shift(1)
    df['ATR_prev'] = df['ATR'].shift(1)
    df['ema_trend_prev'] = df['ema_trend'].shift(1)

    # Entry window: starts immediately after opening range ends, and ends at 12:00 PM (720 minutes)
    in_entry_window = (df['minutes_ny'] >= orb_end_m) & (df['minutes_ny'] < 720)

    # Filter 1: Range Volatility Filter
    orb_range = df['orb_high'] - df['orb_low']
    v_filter = (orb_range >= min_atr_mult * df['ATR_prev']) & (orb_range <= max_atr_mult * df['ATR_prev'])

    # Filter 2: Volume Confirmation Filter
    if use_volume_filter:
        vol_filter = df['volume_prev'] > (vol_ma_mult * df['vol_ma_prev'])
    else:
        vol_filter = True

    # Filter 3: Momentum Filter
    if use_rsi_filter:
        rsi_bull_filter = (df['RSI_prev'] > 50) & (df['RSI_prev'] < rsi_high)
        rsi_bear_filter = (df['RSI_prev'] < 50) & (df['RSI_prev'] > rsi_low)
    else:
        rsi_bull_filter = True
        rsi_bear_filter = True

    # Filter 4: Trend Filter
    if use_trend_filter:
        trend_bull = df['close_prev'] > df['ema_trend_prev']
        trend_bear = df['close_prev'] < df['ema_trend_prev']
    else:
        trend_bull = True
        trend_bear = True

    # Generate Breakout Conditions
    buy_trigger = (df['close_prev'] > df['orb_high']) & (df['close_prev_prev'] <= df['orb_high']) & in_entry_window & v_filter & vol_filter & rsi_bull_filter & trend_bull
    sell_trigger = (df['close_prev'] < df['orb_low']) & (df['close_prev_prev'] >= df['orb_low']) & in_entry_window & v_filter & vol_filter & rsi_bear_filter & trend_bear

    # Map triggers to raw signals
    df['raw_signal'] = 0
    df.loc[buy_trigger, 'raw_signal'] = 1
    df.loc[sell_trigger, 'raw_signal'] = -1


    # Keep only the FIRST signal of each day (prevent overtrading)
    df['has_signal'] = df['raw_signal'] != 0
    first_sig_idx = df[df['has_signal']].groupby('date_ny').head(1).index

    df['signal'] = 0
    df.loc[first_sig_idx, 'signal'] = df.loc[first_sig_idx, 'raw_signal']

    # --- End of Day Square-off Flag ---
    # Trigger a hard square-off at 3:45 PM NY time (945 minutes from midnight)
    df['exit_now'] = df['minutes_ny'] >= 945

    # --- Dynamic Stop Loss and Take Profit ---
    symbol = kwargs.get('symbol') or getattr(config, 'SYMBOL', 'GBPJPY')
    point_size = get_point_size(symbol)

    if sl_type == 'atr':
        # ATR-based Stop Loss
        df['dynamic_sl_points'] = (df['ATR'] * atr_sl_mult / point_size).fillna(150).astype(int)
    else:
        # Range-based Stop Loss (orb_high to orb_low)
        df['dynamic_sl_points'] = (orb_range / point_size).fillna(150).astype(int)

    # Safety bounds for Stop Loss (protect against micro ranges or giant gap ranges)
    df['dynamic_sl_points'] = df['dynamic_sl_points'].clip(lower=20, upper=350)
    
    # Calculate Take Profit based on Risk/Reward Ratio
    df['dynamic_tp_points'] = (df['dynamic_sl_points'] * rr_ratio).astype(int)

    # Clean temporary helper columns from DataFrame
    drop_cols = ['raw_signal', 'has_signal', 'close_prev', 'close_prev_prev', 'volume_prev', 'vol_ma_prev', 'RSI_prev', 'ATR_prev']
    df.drop(columns=[c for c in drop_cols if c in df.columns], inplace=True)

    return df

def check_for_signals(df):
    """
    Live trading adapter. This function is continuously called to check the newest data.
    """
    df_signals = generate_signals(df)
    last_row = df_signals.iloc[-1]

    if last_row['signal'] == 1:
        print("NYSE ORB Strategy: Bullish Breakout Entry Detected")
    elif last_row['signal'] == -1:
        print("NYSE ORB Strategy: Bearish Breakout Entry Detected")

    return last_row['signal'], last_row['dynamic_sl_points'], last_row['dynamic_tp_points']
