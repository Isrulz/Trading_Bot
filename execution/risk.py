import MetaTrader5 as mt5
import config
from utils.calculations import get_point_size

class MockSymbolInfo:
    def __init__(self, symbol):
        self.trade_tick_value = 1.0
        pt = get_point_size(symbol)
        self.trade_tick_size = pt
        self.point = pt
        self.volume_step = 0.01
        self.volume_min = 0.01
        self.volume_max = 100.0

_mock_symbol_info_cache = {}

def get_mock_symbol_info(symbol):
    if symbol not in _mock_symbol_info_cache:
        _mock_symbol_info_cache[symbol] = MockSymbolInfo(symbol)
    return _mock_symbol_info_cache[symbol]

def calculate_position_size(symbol, account_balance, risk_percentage, stop_loss_points, current_price=None):
    """
    Calculates the exact lot size to risk a fixed percentage of the account.
    Enforces ASIC leverage limits.
    Returns 0.0 if the trade is unsafe or too small.
    """
    symbol_info = None
    if config.MODE != "BACKTEST":
        symbol_info = mt5.symbol_info(symbol)
        
    if symbol_info is None:
        if config.MODE == "BACKTEST":
            symbol_info = get_mock_symbol_info(symbol)
        else:
            print(f"Error: Symbol {symbol} not found.")
            return 0.0

    # 1. Risk Amount
    risk_amount = account_balance * (risk_percentage / 100)
    
    # 2. Point Value
    tick_value = symbol_info.trade_tick_value
    tick_size = symbol_info.trade_tick_size
    point_value = tick_value / (tick_size / symbol_info.point)
    
    # 3. Raw Lot Size
    if point_value == 0:
        return 0.0
        
    # Enforce a minimum stop loss to prevent infinite sizing or divide-by-zero on tight intraday signals
    min_sl_points = 10
    safe_stop_loss = max(stop_loss_points, min_sl_points)
        
    raw_lot_size = risk_amount / (safe_stop_loss * point_value)
    
    # 4. ASIC Leverage Constraints
    leverage = config.ASIC_LEVERAGE_GOLD if "XAU" in symbol or "XAG" in symbol else config.ASIC_LEVERAGE_FOREX
    # Contract size approximations: 100000 for Forex, 100 for Gold
    contract_size = 100 if "XAU" in symbol or "XAG" in symbol else 100000
    
    if current_price:
        max_notional = account_balance * leverage
        # Contract size is 100k of base currency. Roughly equivalent to 100k USD for sizing limits.
        # Do not multiply by JPY price (e.g. 215) because it drastically overestimates margin in USD accounts.
        # For XAU, current_price is in USD so we multiply.
        margin_price = current_price if "XAU" in symbol else 1.0 
        max_lots_by_leverage = max_notional / (contract_size * margin_price)
        if raw_lot_size > max_lots_by_leverage:
            raw_lot_size = max_lots_by_leverage

    # 5. Round down
    step = symbol_info.volume_step
    safe_lot_size = (raw_lot_size // step) * step
    
    if safe_lot_size < symbol_info.volume_min:
        print(f"Trade rejected: Lot size is below the broker's minimum. (SL: {stop_loss_points}, Raw Lot: {raw_lot_size}, Point Value: {point_value})")
        return 0.0 
    if safe_lot_size > symbol_info.volume_max:
        safe_lot_size = symbol_info.volume_max
        
    return round(safe_lot_size, 2)