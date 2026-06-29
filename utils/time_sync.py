import pytz
from datetime import datetime

# Define standard timezones
MELBOURNE_TZ = pytz.timezone('Australia/Melbourne')
LONDON_TZ = pytz.timezone('Europe/London')
NEW_YORK_TZ = pytz.timezone('America/New_York')

def get_current_melbourne_time():
    """
    Returns the current time localized to Melbourne, Australia.
    Automatically accounts for AEST/AEDT daylight saving shifts.
    """
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    return utc_now.astimezone(MELBOURNE_TZ)

def get_active_sessions():
    """
    Checks the current time in major financial hubs to determine
    which markets are currently open and driving volume.
    Returns a dictionary of boolean flags.
    """
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    
    # Convert UTC to local times in major hubs
    london_time = utc_now.astimezone(LONDON_TZ)
    ny_time = utc_now.astimezone(NEW_YORK_TZ)
    
    # Define standard market hours (8:00 AM to 5:00 PM local time for each hub)
    sessions = {
        "London": 8 <= london_time.hour < 17,
        "New_York": 8 <= ny_time.hour < 17,
        "Overlap": (8 <= london_time.hour < 17) and (8 <= ny_time.hour < 17)
    }
    
    return sessions

def is_safe_to_trade():
    """
    A master switch to prevent the bot from trading during low-liquidity 
    periods, such as the broker's daily server rollover (Midnight broker time).
    """
    melbourne_now = get_current_melbourne_time()
    
    # 1. Prevent weekend trading (Saturday or Sunday local time)
    if melbourne_now.weekday() >= 5:
        return False
        
    # 2. Prevent trading during the "Witching Hour" (usually 7:00 AM or 8:00 AM Melbourne time)
    # This corresponds to 5:00 PM New York, when global banking rolls over.
    # Spreads widen massively during this hour, which can instantly trigger stop-losses.
    ny_time = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(NEW_YORK_TZ)
    if ny_time.hour == 17:  # 5:00 PM to 6:00 PM in New York
        return False
        
    return True