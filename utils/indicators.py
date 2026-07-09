import pandas as pd
import numpy as np

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculates the Relative Strength Index (RSI).
    """
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculates the Average True Range (ATR).
    """
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def calculate_bollinger_bands(series: pd.Series, period: int = 20, std_dev_mult: float = 2.0):
    """
    Calculates the Bollinger Bands.
    Returns:
        upper_band, middle_band, lower_band
    """
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = middle + (std * std_dev_mult)
    lower = middle - (std * std_dev_mult)
    return upper, middle, lower

def calculate_zscore(series: pd.Series, period: int = 20) -> pd.Series:
    """
    Calculates the rolling Z-Score.
    """
    mean = series.rolling(period).mean()
    std = series.rolling(period).std()
    std = std.replace(0, np.nan)
    return (series - mean) / std
