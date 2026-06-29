import time
from config import SYMBOL, TIMEFRAME
from data.ingestion import get_latest_data
from strategies.moving_avg import check_for_signals
from execution.risk import calculate_position_size
from execution.orders import execute_trade

def run_bot():
    print("Bot starting...")
    
    while True:
        # 1. Get the data
        market_data = get_latest_data(SYMBOL, TIMEFRAME)
        
        # 2. Check the strategy
        signal, stop_loss_price = check_for_signals(market_data)
        
        # 3. Execute if there is a signal
        if signal != 0:
            volume = calculate_position_size(stop_loss_price)
            execute_trade(SYMBOL, signal, volume, stop_loss_price)
            
        # Wait 60 seconds before checking again
        time.sleep(60)

if __name__ == "__main__":
    run_bot()