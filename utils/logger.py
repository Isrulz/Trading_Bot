import logging
import os

def setup_logger():
    """
    Creates a dual-output logging system.
    """
    os.makedirs('logs', exist_ok=True)
    logger = logging.getLogger("TradingBot")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        # 1. File Handler (Saves detailed records to logs/bot.log)
        file_handler = logging.FileHandler("logs/bot.log")
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # 2. Console Handler (Prints a cleaner version to your terminal screen)
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger

# Initialize it once so other files can just import 'log'
log = setup_logger()