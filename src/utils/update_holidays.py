#!/usr/bin/env python3
"""
Utility to update the holiday cache for the current and next year
"""

import os
import sys
import argparse
from datetime import datetime

# Fix the import to use relative import
from .holiday_resolver import holiday_resolver

def update_holiday_cache(years=None, country_code="IN"):
    """Update the holiday cache for the specified years"""
    if years is None:
        # Default to current year and next year
        current_year = datetime.now().year
        years = [current_year, current_year + 1]
    
    print(f"Updating holiday cache for years: {years}")
    
    for year in years:
        print(f"Fetching holidays for {year}...")
        holidays = holiday_resolver.get_holidays(year, country_code)
        print(f"Found {len(holidays)} holiday entries for {year}")
        
        # Print some example holidays
        print("\nExample holidays:")
        count = 0
        for name, date in holidays.items():
            print(f"- {name}: {date}")
            count += 1
            if count >= 5:
                break
    
    print("\nHoliday cache update complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update the holiday cache for Paradise Grill booking system")
    parser.add_argument("--years", type=int, nargs="+", help="Years to update (defaults to current and next year)")
    parser.add_argument("--country", type=str, default="IN", help="Country code (default: IN)")
    
    args = parser.parse_args()
    update_holiday_cache(args.years, args.country)
