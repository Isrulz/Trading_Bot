import MetaTrader5 as mt5

def calculate_position_size(symbol, account_balance, risk_percentage, stop_loss_points):
    """
    Calculates the exact lot size to risk a fixed percentage of the account.
    Returns 0.0 if the trade is unsafe or too small.
    """
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Error: Symbol {symbol} not found.")
        return 0.0

    # 1. Determine how much money we are willing to lose (The Risk Amount)
    risk_amount = account_balance * (risk_percentage / 100)
    
    # 2. Fetch the monetary value of a single point movement from the broker
    tick_value = symbol_info.trade_tick_value
    tick_size = symbol_info.trade_tick_size
    
    # Calculate value per point (standardizing broker differences)
    point_value = tick_value / (tick_size / symbol_info.point)
    
    # 3. Calculate Raw Lot Size
    if point_value == 0 or stop_loss_points == 0:
        return 0.0
        
    raw_lot_size = risk_amount / (stop_loss_points * point_value)
    
    # 4. Round down to the broker's minimum allowed step (usually 0.01 lots)
    step = symbol_info.volume_step
    safe_lot_size = (raw_lot_size // step) * step
    
    # 5. Safety Checks against Broker and ASIC Minimums/Maximums
    if safe_lot_size < symbol_info.volume_min:
        print("Trade rejected: Lot size is below the broker's minimum.")
        return 0.0 
    if safe_lot_size > symbol_info.volume_max:
        safe_lot_size = symbol_info.volume_max
        
    return round(safe_lot_size, 2)