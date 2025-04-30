import requests
import logging
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cache directory for holiday data
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)

class HolidayResolver:
    def __init__(self):
        self.holiday_cache = {}
        self.cache_file = os.path.join(CACHE_DIR, 'holiday_cache.json')
        self.legacy_helper = None  # Add this to fix the AttributeError
        
        # Get Calendarific API key from environment
        self.api_key = os.environ.get("CALENDARIFIC_API_KEY")
        if not self.api_key:
            logger.warning("Calendarific API key not found. Holiday resolution may be limited.")
        
        # Base URL for Calendarific API
        self.base_url = "https://calendarific.com/api/v2"
        
        # Default to Indian holidays
        self.country_code = "IN"
        
        self.load_cache()
        
    def load_cache(self):
        """Load holiday cache from file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    self.holiday_cache = json.load(f)
                logger.info(f"Loaded holiday cache with {len(self.holiday_cache.keys())} years")
        except Exception as e:
            logger.error(f"Error loading holiday cache: {str(e)}")
            self.holiday_cache = {}
    
    def save_cache(self):
        """Save holiday cache to file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.holiday_cache, f)
            logger.info(f"Saved holiday cache to {self.cache_file}")
        except Exception as e:
            logger.error(f"Error saving holiday cache: {str(e)}")
            
    def get_holidays(self, year, country_code=None):
        """Get holidays for a specific year and country using Calendarific API"""
        if not country_code:
            country_code = self.country_code
            
        year_str = str(year)
        
        # Check if we have cached data for this year
        if year_str in self.holiday_cache:
            logger.info(f"Using cached holiday data for {year_str}")
            return self.holiday_cache[year_str]
        
        # If no API key, return empty dict
        if not self.api_key:
            logger.error("Calendarific API key not available")
            return {}
        
        # Fetch from Calendarific API
        try:
            url = f"{self.base_url}/holidays"
            params = {
                "api_key": self.api_key,
                "country": country_code,
                "year": year_str
            }
            
            logger.info(f"Fetching holidays from Calendarific API for {year_str} and country {country_code}")
            
            response = requests.get(url, params=params, timeout=10)
            
            response.raise_for_status()
            
            data = response.json()
            
            # Check if the API request was successful
            if data.get("meta", {}).get("code") != 200:
                error_message = data.get("meta", {}).get("error_message", "Unknown error")
                logger.error(f"Calendarific API error: {error_message}")
                return {}
                
            holidays = data.get("response", {}).get("holidays", [])
            
            # Format the holidays into a more usable structure
            formatted_holidays = {}
            for holiday in holidays:
                name = holiday.get('name', '').strip().lower()
                date_info = holiday.get('date', {})
                iso_date = date_info.get('iso', '')
                
                # Store the date for this holiday
                formatted_holidays[name] = iso_date
                
                # Add common name variations for major holidays
                if "diwali" in name or "deepavali" in name:
                    formatted_holidays["diwali"] = iso_date
                elif "christmas" in name and "eve" in name:
                    formatted_holidays["christmas eve"] = iso_date
                elif "christmas" in name:
                    formatted_holidays["christmas"] = iso_date
                elif "independence day" in name:
                    formatted_holidays["independence day"] = iso_date  # August 15th for India
                elif "republic day" in name:
                    formatted_holidays["republic day"] = iso_date  # January 26th for India
                elif "holi" in name:
                    formatted_holidays["holi"] = iso_date
                elif "janmashtami" in name or "krishna" in name:
                    formatted_holidays["janmashtami"] = iso_date
                    formatted_holidays["krishna janmashtami"] = iso_date
                elif "dussehra" in name or "dasara" in name or "vijayadashami" in name:
                    formatted_holidays["dussehra"] = iso_date
                    formatted_holidays["dasara"] = iso_date
                elif "makar sankranti" in name or "pongal" in name:
                    formatted_holidays["makar sankranti"] = iso_date
                    formatted_holidays["pongal"] = iso_date
                elif "gandhi jayanti" in name:
                    formatted_holidays["gandhi jayanti"] = iso_date
            
            # Cache the result
            self.holiday_cache[year_str] = formatted_holidays
            self.save_cache()
            
            return formatted_holidays
            
        except Exception as e:
            logger.error(f"Error fetching holidays for {year}: {str(e)}")
            return {}
            
    def get_festival_date(self, festival_name, year=None):
        """Get the date for a specific festival in YYYY-MM-DD format"""
        if not year:
            year = datetime.now().year
            
        year_str = str(year)
        festival_name = festival_name.lower()
        
        # First try to get it from our cached data
        result = self._get_festival_date_internal(festival_name, year)
        
        if result is None:
            # No need for legacy_helper check since we now handle it properly
            logger.warning(f"Could not find date for festival '{festival_name}' in year {year}")
            
        return result
        
    def _get_festival_date_internal(self, festival_name, year=None):
        """Internal method for getting festival date from our own cache"""
        if not year:
            year = datetime.now().year
            
        year_str = str(year)
        festival_name = festival_name.lower()
        
        # If we don't have data for this year yet, get it
        if year_str not in self.holiday_cache:
            self.get_holidays(year)
        
        # Check if festival is in our cache for this year
        if year_str in self.holiday_cache:
            holidays = self.holiday_cache[year_str]
            
            # Direct match
            if festival_name in holidays:
                return holidays[festival_name]
            
            # Try common aliases
            common_aliases = {
                "independence day of india": "independence day",
                "indian independence day": "independence day",
                "indian republic day": "republic day",
                "deepavali": "diwali",
                "coffee day": "international coffee day"
            }
            
            if festival_name in common_aliases and common_aliases[festival_name] in holidays:
                return holidays[common_aliases[festival_name]]
                
        return None

# Create a singleton instance
holiday_resolver = HolidayResolver()
