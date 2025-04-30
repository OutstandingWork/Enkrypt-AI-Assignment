import os
import json
import logging
import pandas as pd
from datetime import datetime, timedelta
from utils.date_utils import date_to_weekday, is_valid_date_format

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BookingDatabase:
    def __init__(self, bookings_file=None):
        # Set the correct path to the bookings file
        if bookings_file is None:
            # Use absolute path to ensure we're accessing the correct file
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.bookings_file = os.path.join(base_dir, 'data', 'bookings.csv')
        else:
            self.bookings_file = bookings_file
            
        logger.info(f"Database using bookings file: {self.bookings_file}")
        
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(self.bookings_file), exist_ok=True)
        
        # Create the bookings file if it doesn't exist
        if not os.path.exists(self.bookings_file):
            self._create_empty_bookings_file()
    
    def _create_empty_bookings_file(self):
        """Create an empty bookings CSV file with headers"""
        df = pd.DataFrame(columns=['user_name', 'date', 'time', 'booking_date', 'booking_id', 'day'])
        df.to_csv(self.bookings_file, index=False)
        logger.info(f"Created new empty bookings file at {self.bookings_file}")
    
    def _load_file(self, file_path, default_data=None):
        """Common function for loading CSV/JSON files with error handling"""
        try:
            if file_path.endswith('.csv'):
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    return pd.read_csv(file_path)
                return pd.DataFrame(default_data or [])
            elif file_path.endswith('.json'):
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    with open(file_path, 'r') as f:
                        return json.load(f)
                return default_data or {}
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {str(e)}")
            return pd.DataFrame([]) if file_path.endswith('.csv') else {}

    def _save_file(self, data, file_path):
        """Common function for saving CSV/JSON files with error handling"""
        try:
            # Create parent directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            if file_path.endswith('.csv'):
                data.to_csv(file_path, index=False)
            elif file_path.endswith('.json'):
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving file {file_path}: {str(e)}")
            return False
    
    def _load_bookings(self):
        """Load bookings using the common file loader"""
        return self._load_file(self.bookings_file, [])
        
    def _save_bookings(self, df):
        """Save bookings using the common file saver"""
        return self._save_file(df, self.bookings_file)
    
    def _migrate_day_to_date(self, df):
        """Migrate old schema using 'day' to new schema using 'date'"""
        # Create a copy of the day column as date
        df['date'] = df['day']
        
        # Try to convert day names to actual dates if possible
        current_date = datetime.now()
        for index, row in df.iterrows():
            try:
                # Map day name to a future date within the next 7 days
                day_name = row['day'].title()
                day_mapping = {
                    'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 
                    'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
                }
                
                if day_name in day_mapping:
                    current_weekday = current_date.weekday()
                    days_until = (day_mapping[day_name] - current_weekday) % 7
                    if days_until == 0:  # If today, use next week
                        days_until = 7
                    
                    target_date = current_date + timedelta(days=days_until)
                    df.at[index, 'date'] = target_date.strftime('%Y-%m-%d')
            except:
                # If conversion fails, keep the original day name
                continue
        
        # Save the updated dataframe
        self._save_bookings(df)
        return df
    
    def book_slot(self, user_name, date, time):
        """Book a slot"""
        logger.info(f"Attempting to book slot for {user_name} on {date} at {time}")
        
        # Load current bookings
        df = self._load_bookings()
        
        # Check for column schema
        date_column = 'date' if 'date' in df.columns else 'day'
        
        # Check if the slot is already booked
        try:
            matching_bookings = df[(df[date_column] == date) & (df['time'] == time)]
            if not matching_bookings.empty:
                logger.warning(f"Slot on {date} at {time} is already booked")
                return {'status': 'failure', 'message': 'Slot already booked'}
            
            # Add new booking
            booking_id = len(df) + 1
            
            # Calculate the weekday from the date
            try:
                # Convert date string to datetime object to get weekday name
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                weekday_name = date_obj.strftime("%A")  # %A gives full weekday name
                logger.info(f"Calculated weekday for {date}: {weekday_name}")
            except Exception as e:
                logger.error(f"Error calculating weekday for {date}: {e}")
                weekday_name = ""  # Default empty if calculation fails
                
            new_booking = pd.DataFrame([{
                'user_name': user_name,
                'date': date,
                'day': weekday_name,  # Store weekday name
                'time': time,
                'booking_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'booking_id': booking_id
            }])
            
            df = pd.concat([df, new_booking], ignore_index=True)
            
            # Save updated bookings
            if self._save_bookings(df):
                logger.info(f"Successfully booked slot for {user_name} on {date} at {time}")
                return {'status': 'success', 'message': f'Slot booked for {date} at {time}', 'booking_id': booking_id}
            else:
                logger.error("Failed to save bookings after booking")
                return {'status': 'failure', 'message': 'Error saving booking'}
        except Exception as e:
            logger.error(f"Error booking slot: {str(e)}")
            return {'status': 'failure', 'message': f'Error booking slot: {str(e)}'}
    
    def cancel_booking(self, user_name, date=None, time=None, booking_id=None):
        """Cancel a booking - can search by date/time or by booking_id for last booking"""
        logger.info(f"Attempting to cancel booking for {user_name}, date:{date}, time:{time}, id:{booking_id}")
        
        df = self._load_bookings()
        
        if df.empty:
            logger.warning(f"No bookings found in {self.bookings_file}")
            return {'status': 'failure', 'message': 'No bookings found'}
        
        # Check for column schema
        date_column = 'date' if 'date' in df.columns else 'day'
        logger.info(f"Using column '{date_column}' for date information")
        
        # Log the current bookings for debugging
        logger.info(f"Current bookings in database:\n{df}")

        # If booking_id is provided, use that for exact match
        if booking_id:
            mask = (df['user_name'] == user_name) & (df['booking_id'] == booking_id)
        # If "just now" or similar is detected, find the most recent booking
        elif date is None and time is None:
            # Get the most recent booking for this user
            user_bookings = df[df['user_name'] == user_name]
            if user_bookings.empty:
                logger.warning(f"No bookings found for user '{user_name}'")
                return {'status': 'failure', 'message': f'No bookings found for {user_name}'}
            
            # Sort by booking date (most recent first) and take the first one
            most_recent = user_bookings.sort_values('booking_date', ascending=False).iloc[0]
            mask = df['booking_id'] == most_recent['booking_id']
            
            # Update date and time for response clarity
            date = most_recent[date_column]
            time = most_recent['time']
        else:
            # Match by date and time
            mask = (df['user_name'] == user_name) & \
                   (df[date_column] == date) & \
                   (df['time'] == time)
               
        matching_bookings = df[mask]
        
        if matching_bookings.empty:
            logger.warning(f"No exact booking found for user '{user_name}' with the specified criteria")
            return {'status': 'failure', 'message': f'No booking found for {user_name} matching your criteria'}
            
        # Remove the booking(s) - should only be one with exact match logic
        df = df.drop(matching_bookings.index)
        
        # Save updated bookings
        if self._save_bookings(df):
            num_cancelled = len(matching_bookings) # Should be 1
            cancelled_booking = matching_bookings.iloc[0].to_dict()
            logger.info(f"Successfully cancelled booking: {cancelled_booking}")
            
            return {
                'status': 'success', 
                'message': f'Booking for {user_name} cancelled on {date} at {time}',
                'cancelled_date': date,
                'cancelled_time': time
            }
        else:
            logger.error(f"Failed to save bookings after cancellation")
            return {'status': 'failure', 'message': 'Error saving updated bookings'}

    def get_available_slots(self, start_date=None, end_date=None):
        """Get all available slots for a date range"""
        logger.info(f"Fetching available slots from {start_date} to {end_date}")
        df = self._load_bookings()
        
        # Check for column schema
        date_column = 'date' if 'date' in df.columns else 'day'
        
        # If no date range provided, use the next 7 days
        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%d")
        if not end_date:
            end_date_dt = datetime.now() + timedelta(days=7)
            end_date = end_date_dt.strftime("%Y-%m-%d")
            
        # Convert date strings to datetime objects for comparison
        start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Generate all possible slots for the date range
        date_range = [(start_date_dt + timedelta(days=i)).strftime("%Y-%m-%d") 
                      for i in range((end_date_dt - start_date_dt).days + 1)]
        hours = [f"{h:02d}:00" for h in range(9, 24)] # 9 AM to 11 PM (23:00)
        
        all_slots = []
        for date in date_range:
            for time in hours:
                all_slots.append({'date': date, 'time': time})
        
        all_slots_df = pd.DataFrame(all_slots)
        
        # Find which slots are already booked
        if not df.empty and 'time' in df.columns:
            # Ensure we're using the 'date' column for comparison
            # If we have a 'day' column but no 'date' column, migrate the data
            if date_column == 'day' and 'date' not in df.columns:
                df = self._migrate_day_to_date(df)
                
            # Now we can safely use the 'date' column for merging
            booked_slots = df[['date', 'time']].copy()
            
            # Merge to find available slots
            merged = pd.merge(
                all_slots_df, 
                booked_slots, 
                on=['date', 'time'], 
                how='left', 
                indicator=True
            )
            available_df = merged[merged['_merge'] == 'left_only'].drop('_merge', axis=1)
        else:
            # No bookings or empty/invalid dataframe, all slots are available
            available_df = all_slots_df
            
        logger.info(f"Found {len(available_df)} available slots.")
        return available_df
    
    def get_user_bookings(self, user_name):
        """Get all bookings for a user"""
        logger.info(f"Fetching bookings for user {user_name}")
        df = self._load_bookings()
        return df[df['user_name'] == user_name]
    
    def get_user_last_booking(self, user_name):
        """Get the most recent booking for a user"""
        logger.info(f"Fetching last booking for user {user_name}")
        df = self._load_bookings()
        user_bookings = df[df['user_name'] == user_name]
        
        if user_bookings.empty:
            return None
            
        # Sort by booking date (most recent first)
        most_recent = user_bookings.sort_values('booking_date', ascending=False).iloc[0]
        return most_recent.to_dict()
    
    def reset_all_bookings(self):
        """Reset all bookings"""
        logger.info("Resetting all bookings")
        try:
            self._create_empty_bookings_file()
            return True
        except Exception as e:
            logger.error(f"Error resetting bookings: {str(e)}")
            return False
