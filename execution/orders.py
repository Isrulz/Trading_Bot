import MetaTrader5 as mt5
import config
from config import MAGIC_NUMBER

# Simulated Ledger for Backtesting
_simulated_ledger = []
_simulated_ticket_counter = 1

def reset_ledger():
    global _simulated_ledger, _simulated_ticket_counter
    _simulated_ledger = []
    _simulated_ticket_counter = 1

class SimulatedPosition:
    def __init__(self, ticket, symbol, type, volume, price_open, magic, sl=0.0, tp=0.0, open_idx=None):
        self.ticket = ticket
        self.symbol = symbol
        self.type = type
        self.volume = volume
        self.price_open = price_open
        self.magic = magic
        self.sl = sl
        self.tp = tp
        self.open_idx = open_idx

def get_open_positions(symbol):
    if config.MODE == "BACKTEST":
        return [p for p in _simulated_ledger if p.symbol == symbol and p.magic == MAGIC_NUMBER]
        
    positions = mt5.positions_get(symbol=symbol)
    if positions is None or len(positions) == 0:
        return []
    return [p for p in positions if p.magic == MAGIC_NUMBER]

def close_position(position_ticket, current_price=None, verbose=True):
    if config.MODE == "BACKTEST":
        global _simulated_ledger
        for p in _simulated_ledger:
            if p.ticket == position_ticket:
                _simulated_ledger.remove(p)
                if verbose:
                    print(f"BACKTEST: Closed position {position_ticket} at price {current_price}")
                return True
        if verbose:
            print(f"Error: Position ticket {position_ticket} not found in backtest ledger.")
        return False

    position = mt5.positions_get(ticket=position_ticket)
    if position is None or len(position) == 0:
        print(f"Error: Position ticket {position_ticket} not found.")
        return False
        
    pos_detail = position[0]
    symbol = pos_detail.symbol
    lot_size = pos_detail.volume
    
    if pos_detail.type == mt5.POSITION_TYPE_BUY:
        order_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).bid
    elif pos_detail.type == mt5.POSITION_TYPE_SELL:
        order_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).ask
    else:
        return False

    close_request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": order_type,
        "position": position_ticket,
        "price": price,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": "Bot Exit Signal Triggered",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(close_request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to close position {position_ticket}. Error: {result.retcode}")
        return False
        
    print(f"SUCCESS: Closed position {position_ticket} at price {result.price}")
    return True

def execute_trade(symbol, order_type, lot_size, price, sl, tp, magic_number, open_idx=None, verbose=True):
    if config.MODE == "BACKTEST":
        global _simulated_ticket_counter
        pos = SimulatedPosition(
            ticket=_simulated_ticket_counter,
            symbol=symbol,
            type=order_type,
            volume=lot_size,
            price_open=price,
            magic=magic_number,
            sl=sl,
            tp=tp,
            open_idx=open_idx
        )
        _simulated_ledger.append(pos)
        _simulated_ticket_counter += 1
        if verbose:
            print(f"BACKTEST: Opened {'LONG' if order_type == mt5.ORDER_TYPE_BUY else 'SHORT'} {lot_size} lots at {price}")
        return True
        
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": magic_number,
        "comment": "Bot Entry Signal",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to execute trade. Error: {result.retcode}")
        return False
        
    print(f"SUCCESS: Trade executed at price {result.price}")
    return True