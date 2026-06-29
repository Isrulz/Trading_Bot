import MetaTrader5 as mt5

def execute_trade(symbol, order_type, lot_size, price, sl, tp, magic_number=999111):
    """
    Constructs the order payload and sends it to the broker.
    """
    # Create the standardized MT5 request dictionary
    request = {
        "action": mt5.TRADE_ACTION_DEAL,      # Immediate market execution
        "symbol": symbol,
        "volume": lot_size,                   # The safe lot size from risk.py
        "type": order_type,                   # mt5.ORDER_TYPE_BUY or mt5.ORDER_TYPE_SELL
        "price": price,                       # The current Ask or Bid price
        "sl": sl,                             # Stop Loss price
        "tp": tp,                             # Take Profit price
        "deviation": 20,                      # Acceptable slippage in points
        "magic": magic_number,                # A unique ID tag for your bot
        "comment": "Bot Execution",
        "type_time": mt5.ORDER_TIME_GTC,      # Good Till Cancelled
        "type_filling": mt5.ORDER_FILLING_IOC,# Immediate Or Cancel
    }

    # Transmit to the broker
    result = mt5.order_send(request)
    
    # Error Handling
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed. MT5 Error Code: {result.retcode}")
        # You would look up this error code in the MQL5 documentation
        return False
        
    print(f"SUCCESS: Order {result.order} filled at {result.price}")
    return True