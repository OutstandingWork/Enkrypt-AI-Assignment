import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def date_to_weekday(date_string):
    """Convert date string to weekday name"""
    try:
        date_obj = datetime.strptime(str(date_string), "%Y-%m-%d")
        return date_obj.strftime("%A")  # Full weekday name
    except Exception as e:
        logger.error(f"Error converting date to weekday: {e}")
        return None

def weekday_to_date(day_name, reference_date=None):
    """Convert weekday name to next date with that weekday"""
    if reference_date is None:
        reference_date = datetime.now()
        
    day_mapping = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6
    }
    
    target_day = day_name.lower()
    if target_day not in day_mapping:
        return None
        
    current_weekday = reference_date.weekday()
    days_to_add = (day_mapping[target_day] - current_weekday) % 7
    if days_to_add == 0:  # Same day of week, go to next week
        days_to_add = 7
        
    target_date = reference_date + timedelta(days=days_to_add)
    return target_date.strftime("%Y-%m-%d")

def is_valid_date_format(date_str):
    """Check if a string is a valid date format (YYYY-MM-DD)"""
    try:
        datetime.strptime(str(date_str), "%Y-%m-%d")
        return True
    except ValueError:
        return False
