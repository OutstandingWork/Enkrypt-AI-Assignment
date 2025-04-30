from flask import Flask, render_template, request, jsonify
from app.db_handler import BookingDatabase  # Fixed: Use relative import
from app.session_handler import SessionManager  # Fixed: Use relative import
from llm.groq_handler import GroqHandler  # Fixed: Use relative import
from utils.date_utils import date_to_weekday, weekday_to_date, is_valid_date_format  # Fixed
from utils.holiday_resolver import holiday_resolver  # Added: Import holiday_resolver
import pandas as pd
import uuid
import json
import logging
import re
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create a simple date parser class to replace undefined date_parser
class DateParser:
    @staticmethod
    def extract_time(text):
        """Extract time from text using regex patterns"""
        # Look for patterns like 2pm, 14:00, etc.
        time_pattern = re.compile(r'(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?', re.IGNORECASE)
        match = time_pattern.search(text)
        
        if match:
            hour = int(match.group(1))
            minute = match.group(2)
            ampm = match.group(3)
            
            # Handle AM/PM
            if ampm and ampm.lower().startswith('p') and hour < 12:
                hour += 12
            elif ampm and ampm.lower().startswith('a') and hour == 12:
                hour = 0
                
            # Format as HH:MM
            return f"{hour:02d}:{minute if minute else '00'}"
        
        return None

# Create instances
db = BookingDatabase()
session_manager = SessionManager()
groq = GroqHandler()
date_parser = DateParser()  # Added: Create date_parser instance

# Define Booking class - was missing
class Booking:
    def __init__(self, user_name, date, time):
        self.user_name = user_name
        self.date = date
        self.time = time

def book_slot(booking):
    """Book a slot using the Booking object"""
    result = db.book_slot(booking.user_name, booking.date, booking.time)
    return result

def format_response(status, message, session_id=None, **additional_data):
    """Format a standardized API response"""
    response = {
        'status': status,
        'message': message
    }
    if session_id:
        response['session_id'] = session_id
        
    response.update(additional_data)
    return jsonify(response)

def perform_cancellation(user_name, date=None, time=None, booking_id=None, session_id=None):
    """Common cancellation function used by both direct API and NLP interface"""
    logger.info(f"Cancellation request: {user_name}, {date}, {time}, {booking_id}")
    
    # Check if time is valid (between 9:00 and 23:00)
    if time:
        try:
            hour = int(time.split(':')[0])
            if hour < 9 or hour >= 23:
                return {
                    'status': 'failure',
                    'message': f'Invalid cancellation time. Paradise Grill is only open from 9 AM to 11 PM'
                }
        except:
            return {
                'status': 'failure',
                'message': 'Invalid time format for cancellation. Please use HH:MM format.'
            }
    
    # Call the database cancellation function
    result = db.cancel_booking(user_name, date, time, booking_id)
    logger.info(f"Cancellation result: {result}")
    
    # Generate response
    nlp_response = groq.generate_cancellation_response(result)
    result['nlp_response'] = nlp_response
    
    # Add message to session if session_id is provided
    if session_id:
        session_manager.add_message(session_id, 'system', nlp_response)
        # If successful, mark the session as completed
        if result['status'] == 'success':
            session_manager.update_session(session_id, {'status': 'completed'})
    
    return result

def process_booking_request():
    """Process a natural language booking or cancellation request"""
    if request.method == 'POST':
        data = request.json
        user_name = data.get('user_name')
        user_input = data.get('booking_request')
        session_id = data.get('session_id')
        
        if not user_name or not user_input:
            return format_response(
                'failure',
                'Missing user_name or booking_request',
                session_id
            )
        
        # Log the incoming request
        logger.info(f"Received request from {user_name}: '{user_input}'")
        
        # Get or create session
        active_session = None
        if session_id:
            active_session = session_manager.get_session(session_id)
            
        if not active_session:
            # Create a new session
            session_id = session_manager.create_session(user_name)
            active_session = session_manager.get_session(session_id)
            logger.info(f"Created new session {session_id} for {user_name}")
        
        # Add the user message to the session
        session_manager.add_message(session_id, 'user', user_input)
        
        # Check if we're waiting for clarification
        context = active_session['context']
        if context.get('pending_clarification'):
            # Handle the clarification response
            clarification_type = context.get('clarification_type')
            
            if clarification_type == 'ambiguous_time':
                # Parse the clarification response
                ambiguity_info = context.get('ambiguous_time', {})
                clarified_time = groq.parse_clarification_response(user_input, ambiguity_info)
                
                if clarified_time == 'unknown':
                    # Still couldn't understand the time
                    response = format_response(
                        'pending',
                        "I'm sorry, I still couldn't understand the time. Please specify a time between 9 AM and 11 PM in a clear format, like '2 PM' or '14:00'.",
                        session_id
                    )
                    session_manager.add_message(session_id, 'system', response['message'])
                    return response
                
                # Convert to hourly format (round to nearest hour)
                try:
                    hour = int(clarified_time.split(':')[0])
                    minute = int(clarified_time.split(':')[1])
                    
                    # Round to nearest hour
                    if minute >= 30:
                        hour += 1
                    
                    hourly_time = f"{hour:02d}:00"
                    
                    # Validate business hours
                    if hour < 9 or hour >= 24:
                        response = format_response(
                            'failure',
                            "I'm sorry, but the hotel is only open from 9 AM to 12 midnight. Please choose a time within our operating hours.",
                            session_id
                        )
                        session_manager.add_message(session_id, 'system', response['message'])
                        return response
                    
                    clarified_time = hourly_time
                    
                except:
                    response = format_response(
                        'failure',
                        'Invalid time format. Please specify a clear hourly time like 2 PM or 14:00.',
                        session_id
                    )
                    session_manager.add_message(session_id, 'system', response['message'])
                    return response
                
                # Update the context with the clarified time
                updates = {
                    'context': {
                        'time': clarified_time,
                        'pending_clarification': False,
                        'clarification_type': None,
                        'ambiguous_time': None
                    }
                }
                session_manager.update_session(session_id, updates)
                
                # Now proceed with booking using the clarified time
                date = context.get('date')
                
                # Create a booking object
                booking = Booking(user_name=user_name, date=date, time=clarified_time)
                
                # Try to book the slot
                result = book_slot(booking)
                
                # Generate a natural language response
                nlp_response = groq.generate_booking_response(result)
                
                # Add the response to the session
                session_manager.add_message(session_id, 'system', nlp_response)
                
                # If booking was successful, mark the session as complete
                if result['status'] == 'success':
                    session_manager.update_session(session_id, {'status': 'completed'})
                
                # Add the NLP response to the result
                result['nlp_response'] = nlp_response
                result['session_id'] = session_id
                
                return jsonify(result)
            
            elif clarification_type == 'hourly_time':
                # Handle hourly time clarification
                date = context.get('date')  # Make sure we preserve the date
                original_time = context.get('original_time')
                suggested_time = context.get('suggested_time')
                
                # Check if user agreed to the suggested time
                if any(word in user_input.lower() for word in ['yes', 'yeah', 'ok', 'sure', 'fine']):
                    # User agreed to suggested time
                    time = suggested_time
                else:
                    # User wants a different time - try to extract an hourly time
                    parsed_time = groq.parse_booking_request(user_input)
                    new_time = parsed_time.get('time', 'unknown')
                    
                    if new_time != 'unknown' and ':' in new_time:
                        # Check if it's an hourly time
                        try:
                            hour, minute = map(int, new_time.split(':'))
                            if minute == 0 and 9 <= hour < 24:
                                time = new_time
                            else:
                                # Not a valid hourly time
                                response = format_response(
                                    'pending',
                                    "I can only book on the hour. Please choose a time between 9:00 and 23:00.",
                                    session_id
                                )
                                session_manager.add_message(session_id, 'system', response['message'])
                                return response
                        except:
                            # Couldn't parse the time
                            response = format_response(
                                'pending',
                                "I couldn't understand the time. Please specify an hourly time (e.g., 6:00 PM).",
                                session_id
                            )
                            session_manager.add_message(session_id, 'system', response['message'])
                            return response
                    else:
                        # Extract a simple hour
                        hour_match = None
                        for word in user_input.lower().split():
                            if word.isdigit() and 1 <= int(word) <= 23:
                                hour_match = int(word)
                                break
                        
                        if hour_match:
                            # Determine if AM or PM based on context
                            if "pm" in user_input.lower() or "evening" in user_input.lower():
                                if hour_match < 12:
                                    hour_match += 12
                            
                            # Ensure it's within opening hours
                            if 9 <= hour_match < 24:
                                time = f"{hour_match:02d}:00"
                            else:
                                response = format_response(
                                    'pending',
                                    "The hotel is open from 9 AM to 12 midnight. Please choose a time within these hours.",
                                    session_id
                                )
                                session_manager.add_message(session_id, 'system', response['message'])
                                return response
                        else:
                            # Failed to extract a time
                            response = format_response(
                                'pending',
                                "I couldn't understand the time. Please specify an hourly time like 6 PM or 18:00.",
                                session_id
                            )
                            session_manager.add_message(session_id, 'system', response['message'])
                            return response
                
                # Clear the pending clarification but preserve the date
                updates = {
                    'context': {
                        'time': time,
                        'date': date,  # Make sure we keep the date!
                        'pending_clarification': False,
                        'clarification_type': None
                    }
                }
                session_manager.update_session(session_id, updates)
                
                # Create a booking object
                booking = Booking(user_name=user_name, date=date, time=time)
                
                # Try to book the slot
                result = book_slot(booking)
                
                # Generate a natural language response
                nlp_response = groq.generate_booking_response(result)
                
                # Add the response to the session
                session_manager.add_message(session_id, 'system', nlp_response)
                
                # If booking was successful, mark the session as complete
                if result['status'] == 'success':
                    session_manager.update_session(session_id, {'status': 'completed'})
                
                # Add the NLP response to the result
                result['nlp_response'] = nlp_response
                result['session_id'] = session_id
                
                return jsonify(result)

        # Not waiting for clarification, process as normal request
        
        # First determine if this is a follow-up or new request
        is_follow_up = False
        previous_context = {}
        
        # Check if this is an active session with previous context
        if active_session and active_session.get('context'):
            prev_context = active_session.get('context', {})
            prev_date = prev_context.get('date')
            prev_intent = prev_context.get('intent')
            
            # Simple heuristics to detect follow-up questions
            follow_up_phrases = ["instead", "how about", "what about", "can it be", 
                               "is it available", "try", "another", "different", "for"]
            
            has_follow_up_phrase = any(phrase in user_input.lower() for phrase in follow_up_phrases)
            is_short_query = len(user_input.split()) <= 7  # Short queries are often follow-ups
            
            # Detect if this is likely a follow-up request
            if (prev_intent == 'booking' and (has_follow_up_phrase or is_short_query)):
                is_follow_up = True
                previous_context = prev_context
                logger.info(f"Detected follow-up question. Previous context: {previous_context}")
        
        # First determine what the user wants to do
        intent_info = groq.parse_user_intent(user_input, active_session['context'] if active_session else None)
        intent = intent_info.get('intent')
        
        # For follow-up questions related to time changes, force booking intent
        if is_follow_up and re.search(r'\b\d+\s*(?:am|pm|a\.m|p\.m|o\'clock)\b', user_input.lower(), re.IGNORECASE):
            intent = 'booking'
            logger.info(f"Forcing booking intent due to detected time in follow-up")
        
        # Log the intent detection results
        logger.info(f"Detected intent: {intent}, details: {intent_info}")
        
        # For follow-up questions, preserve the previous intent if new one is uncertain
        if is_follow_up and intent == 'unknown':
            intent = previous_context.get('intent', 'unknown')
            logger.info(f"Using previous intent for follow-up: {intent}")
        
        # Update the session context with the intent
        session_manager.update_session(session_id, {'context': {'intent': intent}})
        
        if intent == 'booking':
            # First try our direct parsing approach for common date references
            parsed_request = groq.parse_booking_request(user_input, active_session['context'] if active_session else None)
            
            # Log the full parsed request for debugging
            logger.info(f"Parsed booking request: {parsed_request}")
            
            # Extract the festival reference if present
            festival_referenced = parsed_request.get('festival_referenced')
            
            date = parsed_request.get('date')
            time = parsed_request.get('time')
            
            # Special handling for festival references - try our holiday resolver as a backup
            if (not date or date == "unknown") and festival_referenced:
                festival_date = holiday_resolver.get_festival_date(festival_referenced)
                if festival_date:
                    date = festival_date
                    logger.info(f"Resolved festival {festival_referenced} to date {festival_date}")
            
            # Special handling for common holiday references
            if not date or date == "unknown":
                # Try direct parsing for common holiday references like "Christmas Eve"
                date_ref = None
                for holiday in ["christmas eve", "christmas", "new year", "diwali", "holi"]:
                    if holiday in user_input.lower():
                        date_ref = holiday
                        break
                        
                if date_ref:
                    # Try to get the date from our holiday resolver
                    holiday_date = holiday_resolver.get_festival_date(date_ref)
                    if holiday_date:
                        date = holiday_date
                        logger.info(f"Resolved holiday reference {date_ref} to date {holiday_date}")
            
            # Try to extract time if not already found
            if not time or time == "unknown":
                time = date_parser.extract_time(user_input)
                logger.info(f"Time parser found: {time}")
            
            # For follow-up questions, use the previous date if none specified
            if is_follow_up and (not date) and previous_context.get('date'):
                date = previous_context.get('date')
                logger.info(f"Using date from previous context: {date}")
            
            # Update the session context with what we know so far
            session_manager.update_session(session_id, {'context': {'date': date, 'time': time}})
            
            # Handle missing date
            if not date:
                return format_response(
                    'pending',
                    'Could you please specify which date you would like to make a reservation at Paradise Grill?',
                    session_id
                )
            
            # Handle missing time
            if not time:
                return format_response(
                    'pending',
                    'Could you please specify what time you would like to reserve at Paradise Grill? We accept reservations on the hour between 9 AM and 11 PM.',
                    session_id
                )
                
            # Process time information - check if on the hour
            logger.info(f"About to process time information: {time}")
            
            try:
                hour, minute = map(int, time.split(':'))
                if minute != 0:
                    # Round to the nearest hour
                    original_hour = hour
                    if minute >= 30:
                        hour += 1
                    hourly_time = f"{hour:02d}:00"
                    
                    # Generate a message about hourly booking policy
                    clarification_q = (
                        f"I noticed you requested a reservation for {time} on {date}. "
                        f"Paradise Grill only accepts reservations on the hour. "
                        f"Would you like me to book {hourly_time} instead? "
                        f"We're open from 9 AM to 12 midnight."
                    )
                    
                    # Update session for hourly time clarification
                    updates = {
                        'context': {
                            'pending_clarification': True,
                            'clarification_type': 'hourly_time',
                            'original_time': time,
                            'date': date,
                            'suggested_time': hourly_time
                        }
                    }
                    session_manager.update_session(session_id, updates)
                    
                    # Add the clarification question to the session
                    session_manager.add_message(session_id, 'system', clarification_q)
                    
                    return format_response(
                        'pending',
                        clarification_q,
                        session_id
                    )
                
                # Check if time is valid (between 9:00 and 23:00)
                if hour < 9 or hour >= 24:
                    return format_response(
                        'failure',
                        f'Paradise Grill is only open from 9 AM to 12 midnight. You requested {time}.',
                        session_id
                    )
                
            except Exception as e:
                logger.error(f"Error processing time {time}: {e}")
                return format_response(
                    'failure',
                    'Invalid time format. Please use HH:MM format or specify the time clearly.',
                    session_id
                )
            
            # Create a booking object
            booking = Booking(user_name=user_name, date=date, time=time)
            
            # Try to book the slot
            result = book_slot(booking)
            
            # Generate a natural language response
            nlp_response = groq.generate_booking_response(result, festival_referenced)
            
            # Add the response to the session
            session_manager.add_message(session_id, 'system', nlp_response)
            
            # If booking was successful, mark the session as complete and store booking info
            if result['status'] == 'success':
                # Store the last booking information
                last_booking = {
                    'date': date,
                    'time': time,
                    'booking_id': result.get('booking_id')
                }
                session_manager.update_last_booking(session_id, last_booking)
                session_manager.update_session(session_id, {'status': 'completed'})
            
            # Add the NLP response and session_id to the result
            result['nlp_response'] = nlp_response
            result['session_id'] = session_id
            
            return jsonify(result)
            
        elif intent == 'cancellation':
            # Handle cancellation request
            date = intent_info.get('date')
            time = intent_info.get('time')
            is_recent_reference = intent_info.get('is_recent_reference', False)
            
            # Update the session context with what we know
            session_manager.update_session(session_id, {'context': {'date': date, 'time': time}})
            
            # If user is referring to their most recent booking
            if is_recent_reference:
                # Try to cancel the most recent booking
                result = perform_cancellation(user_name, session_id=session_id)
                return jsonify(result)
            
            # Handle missing information
            if not date:
                return format_response(
                    'pending',
                    'Could you please let me know which date your reservation is on that you wish to cancel?',
                    session_id
                )
                
            if not time:
                return format_response(
                    'pending',
                    'Could you please let me know what time your reservation is that you wish to cancel?',
                    session_id
                )
            
            # Now we have all the information to proceed with cancellation
            result = perform_cancellation(user_name, date, time, None, session_id)
            return jsonify(result)
            
        elif intent == 'availability':
            # Handle availability check request
            date_info = groq.parse_booking_request(user_input)
            date = date_info.get('date')
            
            if not date:
                # Ask for the date
                return format_response(
                    'pending',
                    'Which date would you like to check for available slots at Paradise Grill?',
                    session_id
                )
            
            # Get available slots for the requested date
            all_slots = db.get_available_slots(date, date)
            available_slots = all_slots.to_dict(orient='records')
            
            # Generate a response with the available times
            nlp_response = groq.generate_available_slots_response(available_slots, date)
            session_manager.add_message(session_id, 'system', nlp_response)
            
            # Return the response
            return jsonify({
                'status': 'success',
                'message': 'Available slots retrieved',
                'date': date,
                'available_slots': available_slots,
                'nlp_response': nlp_response,
                'session_id': session_id
            })
        
        else:
            # Handle unknown intent
            return format_response(
                'failure',
                "I couldn't understand your request. Could you please specify if you'd like to make a reservation, cancel a reservation, or check availability at Paradise Grill?",
                session_id
            )
    
    return render_template('booking.html')

def get_available_slots_route():
    """Get all available slots"""
    logger.info("'/slots' endpoint called")
    
    # Get date range from query parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Default to a week if not specified
    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")
    if not end_date:
        end_date_dt = datetime.now() + timedelta(days=7)
        end_date = end_date_dt.strftime("%Y-%m-%d")
    
    available_slots = db.get_available_slots(start_date, end_date)
    return jsonify({
        'status': 'success',
        'available_slots': available_slots.to_dict(orient='records'),
        'start_date': start_date,
        'end_date': end_date
    })

def get_user_bookings(user_name):
    """Get all bookings for a user"""
    user_bookings = db.get_user_bookings(user_name)
    return jsonify({
        'status': 'success',
        'bookings': user_bookings.to_dict(orient='records')
    })

def cancel_booking():
    """Cancel a booking"""
    data = request.json
    user_name = data.get('user_name')
    date = data.get('date')
    time = data.get('time')
    booking_id = data.get('booking_id')
    
    logger.info(f"Direct cancellation API call: {user_name}, {date}, {time}, {booking_id}")
    
    if not user_name:
        return format_response('failure', 'Missing user_name for cancellation')
    
    result = perform_cancellation(user_name, date, time, booking_id)
    return jsonify(result)

def reset_bookings():
    """Reset all bookings"""
    result = db.reset_all_bookings()
    
    return format_response(
        'success' if result else 'failure',
        'All bookings have been reset' if result else 'Failed to reset bookings'
    )

def register_routes(app):
    @app.route('/')
    def index():
        return render_template('booking.html')
    
    @app.route('/booking', methods=['GET', 'POST'])
    def booking():
        return process_booking_request()
    
    @app.route('/slots', methods=['GET'])
    def slots_route():
        return get_available_slots_route()
    
    @app.route('/user-bookings/<user_name>', methods=['GET'])
    def user_bookings_route(user_name):
        return get_user_bookings(user_name)
    
    @app.route('/cancel-booking', methods=['POST'])
    def cancel_booking_route():
        return cancel_booking()
    
    @app.route('/reset-bookings', methods=['POST'])
    def reset_bookings_route():
        return reset_bookings()

