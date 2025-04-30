import os
import sys
import pandas as pd
from datetime import datetime, timedelta

# Fix the import to use relative import
from .date_utils import date_to_weekday, weekday_to_date

def fix_bookings_file(bookings_file=None):
    """Fix the bookings.csv file by adding missing weekday values"""
    if not bookings_file:
        # Default path to bookings file
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        bookings_file = os.path.join(curr_dir, '..', 'data', 'bookings.csv')
    
    # Create backup
    backup_file = create_backup(bookings_file)
    if backup_file:
        print(f"Created backup: {backup_file}")
    
    try:
        # Read the CSV file
        df = pd.read_csv(bookings_file)
        
        # Check if 'day' column exists
        if 'day' not in df.columns:
            print("The 'day' column does not exist in the bookings file.")
            return
        
        # Fill missing 'day' values based on 'date'
        if 'date' in df.columns:
            # For each row with missing 'day' but having 'date'
            for i, row in df.iterrows():
                if pd.isna(row['day']) and not pd.isna(row['date']):
                    weekday = date_to_weekday(row['date'])
                    if weekday:
                        df.at[i, 'day'] = weekday
                        print(f"Updated row {i}: date={row['date']} -> day={weekday}")
        
        # Save the updated CSV file
        df.to_csv(bookings_file, index=False)
        print(f"Updated bookings file saved to {bookings_file}")
        
    except Exception as e:
        print(f"Error fixing bookings file: {e}")
        
def migrate_database(bookings_file=None):
    """Migrate the database from day-based to date-based schema"""
    if not bookings_file:
        # Default path to bookings file
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        bookings_file = os.path.join(curr_dir, '..', 'data', 'bookings.csv')
    
    # Create backup
    backup_file = create_backup(bookings_file)
    if backup_file:
        print(f"Created backup: {backup_file}")
    
    try:
        # Read the CSV file
        df = pd.read_csv(bookings_file)
        
        # Check if we need to migrate
        if 'date' in df.columns:
            # Check if there are any rows with day but no date
            day_no_date = df[(~df['day'].isna()) & (df['date'].isna())]
            if day_no_date.empty:
                print("No migration needed: all rows already have dates.")
                return
            
        # Make sure 'day' column exists
        if 'day' not in df.columns:
            df['day'] = None
            
        # Make sure 'date' column exists
        if 'date' not in df.columns:
            df['date'] = None
            
        # Today's date for reference
        today = datetime.now().date()
        
        # For each row with day but no date
        for i, row in df.iterrows():
            if not pd.isna(row['day']) and pd.isna(row['date']):
                # Convert day to next date
                next_date = weekday_to_date(row['day'])
                if next_date:
                    df.at[i, 'date'] = next_date
                    print(f"Updated row {i}: day={row['day']} -> date={next_date}")
        
        # Save the updated CSV file
        df.to_csv(bookings_file, index=False)
        print(f"Migration complete. Updated file saved to {bookings_file}")
        
    except Exception as e:
        print(f"Error migrating database: {e}")

def create_backup(file_path):
    """Create a backup of the given file with timestamp"""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return None
        
    backup_file = f"{file_path}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
            df.to_csv(backup_file, index=False)
        else:
            with open(file_path, 'rb') as src, open(backup_file, 'wb') as dest:
                dest.write(src.read())
        return backup_file
    except Exception as e:
        print(f"Error creating backup: {e}")
        return None

if __name__ == "__main__":
    # Command-line interface for maintenance operations
    import argparse
    
    parser = argparse.ArgumentParser(description='Database maintenance utilities')
    parser.add_argument('--action', choices=['fix', 'migrate'], required=True,
                        help='Maintenance action to perform')
    parser.add_argument('--file', help='Path to bookings file (optional)')
    
    args = parser.parse_args()
    
    if args.action == 'fix':
        fix_bookings_file(args.file)
    elif args.action == 'migrate':
        migrate_database(args.file)
