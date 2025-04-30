from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class DateParser:
    """Utility class for parsing dates from natural language"""
    
    def __init__(self):
        self.current_year = datetime.now().year
        
        # Common fixed holiday dates
        self.fixed_holidays = {
            "christmas eve": f"{self.current_year}-12-24",
            "christmas": f"{self.current_year}-12-25",
            "new year's eve": f"{self.current_year}-12-31",
            "new years eve": f"{self.current_year}-12-31",
            "new year's day": f"{self.current_year}-01-01",
            "valentine's day": f"{self.current_year}-02-14",
            "halloween": f"{self.current_year}-10-31",
            "independence day": f"{self.current_year}-08-15",  # India
            "republic day": f"{self.current_year}-01-26",      # India
            "gandhi jayanti": f"{self.current_year}-10-02"     # India
        }
        
    def parse_date_reference(self, text):
        """Parse date references from text"""
        text = text.lower()
        
        # Check direct holiday references
        for holiday, date in self.fixed_holidays.items():
            if holiday in text:
                logger.info(f"Found holiday reference: {holiday} -> {date}")
                return date
        
        # Handle relative dates
        if "tomorrow" in text:
            tomorrow = datetime.now() + timedelta(days=1)
            return tomorrow.strftime("%Y-%m-%d")
        
        if "today" in text:
            return datetime.now().strftime("%Y-%m-%d")
        
        if "next" in text:
            # Handle "next Monday", "next Tuesday", etc.
            for i, day in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
                if day in text:
                    # Calculate days until next occurrence
                    current_weekday = datetime.now().weekday()
                    target_weekday = i
                    days_ahead = target_weekday - current_weekday
                    if days_ahead <= 0:  # Target day already happened this week
                        days_ahead += 7
                    next_date = datetime.now() + timedelta(days=days_ahead)
                    return next_date.strftime("%Y-%m-%d")
        
        return None
    
    def extract_time(self, text):
        """Extract time from text"""
        text = text.lower()
        
        # Look for patterns like "9PM", "9 PM", etc.
        hours = list(range(1, 13))
        for hour in hours:
            # Check various formats
            patterns = [
                f"{hour}pm", f"{hour} pm", f"{hour}p.m.", f"{hour} p.m.",
                f"{hour}am", f"{hour} am", f"{hour}a.m.", f"{hour} a.m."
            ]
            
            for pattern in patterns:
                if pattern in text:
                    # Convert to 24-hour format
                    if "p" in pattern:
                        return f"{(hour % 12) + 12:02d}:00"
                    else:
                        return f"{hour % 12:02d}:00"
        
        return None
