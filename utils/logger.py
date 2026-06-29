import logging
import os

def setup_logger():
    # Create a logs folder if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    logging.basicConfig(
        filename='logs/bot_activity.log',
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Also print to the terminal
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)

    return logging.getLogger(__name__)

# Usage: log = setup_logger()
# log.info("Trade executed successfully.")
# log.error("Connection to broker lost.")