import MetaTrader5 as mt5
from config import MAGIC_NUMBER

def get_open_positions(symbol):
    """
    Fetches all active live positions opened by THIS bot's magic number.
    Returns a list of active position objects.
    """
    # Get all open positions for the specific symbol
    positions = mt5.positions_get(symbol=symbol)
    
    if positions is None or len(positions) == 0:
        return []
        
    # Filter positions so the bot ONLY modifies trades containing its unique Magic Number
    bot_positions = [p for p in positions if p.magic == MAGIC_NUMBER]
    
    return bot_positions

def close_position(position_ticket):
    """
    Closes a specific active trade using its unique database ticket ID.
    Automatically detects if it's a Long or Short and sends the correct counter-order.
    """
    # 1. Fetch the exact live details of the position we want to close
    position = mt5.positions_get(ticket=position_ticket)
    if position is None or len(position) == 0:
        print(f"Error: Position ticket {position_ticket} not found.")
        return False
        
    pos_detail = position[0]
    symbol = pos_detail.symbol
    lot_size = pos_detail.volume
    
    # 2. Determine the opposite order type required to cancel out the position
    # If we are currently LONG (BUY), we must SELL to close.
    # If we are currently SHORT (SELL), we must BUY to close.
    if pos_detail.type == mt5.POSITION_TYPE_BUY:
        order_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).bid
    elif pos_detail.type == mt5.POSITION_TYPE_SELL:
        order_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).ask
    else:
        return False

    # 3. Construct the close payload
    close_request = {
        "action": mt5.TRADE_ACTION_DEAL,      # Execute immediately
        "symbol": symbol,
        "volume": lot_size,                   # Must match the exact open volume
        "type": order_type,
        "position": position_ticket,          # CRITICAL: Tells MT5 WHICH position to close
        "price": price,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": "Bot Exit Signal Triggered",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    # 4. Transmit the close request to the broker
    result = mt5.order_send(close_request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to close position {position_ticket}. Error: {result.retcode}")
        return False
        
    print(f"SUCCESS: Closed position {position_ticket} at price {result.price}")
    return True