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
        
        # Indian festivals with accurate dates for specific years
        # These festivals follow lunar calendar, so dates vary each year
        self.indian_festivals = {
            2023: {
                "diwali": "2023-11-12",
                "holi": "2023-03-08",
                "navratri": "2023-10-15"
            },
            2024: {
                "diwali": "2024-11-01",
                "holi": "2024-03-25",
                "navratri": "2024-10-03"
            },
            2025: {
                "diwali": "2025-10-20",  # Corrected date for 2025
                "holi": "2025-03-14",
                "navratri": "2025-09-23"
            },
            2026: {
                "diwali": "2026-11-08",
                "holi": "2026-03-03",
                "navratri": "2026-10-12"
            }
        }
        
    def parse_date_reference(self, text):
        """Parse date references from text"""
        if not text:
            return None
            
        text = text.lower()
        
        # Check for Indian festivals first with exact dates
        for festival in ["diwali", "holi", "navratri"]:
            if festival in text:
                # Get the correct year's date
                year = self.current_year
                # Check if the festival exists for the current year in our database
                if year in self.indian_festivals and festival in self.indian_festivals[year]:
                    festival_date = self.indian_festivals[year][festival]
                    logger.info(f"Found Indian festival: {festival} -> {festival_date}")
                    return festival_date
        
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
        if not text:
            return None
            
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
