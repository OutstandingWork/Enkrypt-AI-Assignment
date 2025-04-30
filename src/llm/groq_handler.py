import os
import json
import requests
import pandas as pd
from dotenv import load_dotenv
import logging
import re
from datetime import datetime, timedelta

# Fix the import path to use relative import
from utils.holiday_resolver import holiday_resolver

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GroqHandler:
    def __init__(self, model_name="llama3-70b-8192", api_key=None):
        # Load environment variables from .env file
        load_dotenv()
        
        self.model_name = model_name
        # Priority: 1. Passed API key, 2. .env file (loaded via dotenv), 3. Environment variable
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        
        if not self.api_key:
            logger.error("No Groq API key found. Please set GROQ_API_KEY in your environment or .env file.")
            # Instead of raising an exception, set a flag that can be checked before API calls
            self.api_available = False
        else:
            self.api_available = True
            
        self.base_url = "https://api.groq.com/openai/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
            "Content-Type": "application/json"
        }
        
    def _check_api_available(self):
        """Check if API is available before making calls"""
        if not self.api_available:
            return False, "Groq API key not available. Please configure your API key."
        return True, ""
    
    def generate_response(self, prompt):
        """Generate a response from the Groq API"""
        api_available, error_msg = self._check_api_available()
        if not api_available:
            return error_msg
            
        url = f"{self.base_url}/chat/completions"
        data = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data)
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                return f"Error: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error connecting to Groq API: {str(e)}"
    
    def parse_user_intent(self, user_input, session_context=None):
        """Determine what the user wants to do (book, cancel, etc.)"""
        api_available, error_msg = self._check_api_available()
        if not api_available:
            return {"intent": "unknown", "date": None, "time": None}
        
        url = f"{self.base_url}/chat/completions"
        
        # Include context from the session if available
        context_str = ""
        if session_context:
            last_booking_date = session_context.get('last_booking_date')
            last_booking_time = session_context.get('last_booking_time')
            if last_booking_date and last_booking_time:
                context_str = f"The user's most recent booking was on {last_booking_date} at {last_booking_time}."
        
        system_message = f"""
        You are a reservation assistant for Paradise Grill restaurant.
        
        {context_str}
        
        Analyze the user request and classify their intent.
        
        If the user wants to cancel a booking, respond with: {{"intent": "cancellation"}}
        If the user wants to make a new booking, respond with: {{"intent": "booking"}}
        If the user wants to check available slots, respond with: {{"intent": "availability"}}
        If you cannot determine the intent, respond with: {{"intent": "unknown"}}

        Examples of booking requests:
        - "Book a table for June 15th at 7 PM" → {{"intent": "booking"}}
        - "Reserve for tomorrow at 9" → {{"intent": "booking"}}
        - "Book a table at 9PM on Christmas Eve" → {{"intent": "booking"}}
        - "I'd like to dine next Friday evening at 6" → {{"intent": "booking"}}
        - "Cancel my reservation" → {{"intent": "cancellation"}}
        - "What slots do you have available next Tuesday?" → {{"intent": "availability"}}
        
        ONLY return the JSON object with the intent. No other explanatory text.
        """
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_input}
        ]
        
        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 100
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                try:
                    parsed_intent = json.loads(content)
                    intent = parsed_intent.get("intent", "unknown")
                    # Now extract the details based on intent
                    if intent == "cancellation":
                        return self._extract_cancellation_details(user_input, session_context)
                    elif intent == "booking":
                        return self._extract_booking_details(user_input, session_context)
                    elif intent == "availability":
                        return {"intent": intent, "date": None, "time": None}
                    else:
                        return {"intent": intent, "date": None, "time": None}
                except json.JSONDecodeError:
                    return {"intent": "unknown", "date": None, "time": None}
            else:
                return {"intent": "unknown", "date": None, "time": None}
        except Exception as e:
            print(f"Error in parse_user_intent: {str(e)}")
            return {"intent": "unknown", "date": None, "time": None}
    
    def parse_booking_request(self, user_input, session_context=None):
        """Parse a natural language booking request using the LLM"""
        return self._extract_booking_details(user_input, session_context)
    
    def _extract_booking_details(self, user_input, session_context=None):
        """Extract date, time, and festival name from a booking request, then resolve festival date."""
        api_available, error_msg = self._check_api_available()
        if not api_available:
            return {"intent": "booking", "date": None, "time": None, "festival_referenced": None}
        
        url = f"{self.base_url}/chat/completions"
        
        today_date = datetime.now().strftime("%Y-%m-%d")
        current_year = datetime.now().year
        
        reference_context = ""
        if session_context:
            last_booking_date = session_context.get('last_booking_date')
            last_booking_time = session_context.get('last_booking_time')
            if last_booking_date and last_booking_time:
                reference_context = f"The user's most recent booking was on {last_booking_date} at {last_booking_time}."
        
        system_message = f"""
        You are an assistant for Paradise Grill restaurant helping to understand booking requests.
        Today's date is {today_date}. The current year is {current_year}.
        {reference_context}
        
        Your task:
        1. Extract the date if explicitly mentioned (e.g., "June 15th", "tomorrow", "next Friday").
        2. Extract the time mentioned.
        3. Extract the name of any festival or holiday mentioned (e.g., "Diwali", "Christmas Eve").
        4. Convert extracted date references (like "tomorrow", "next Friday") to YYYY-MM-DD format.
        5. Convert extracted time references to 24-hour HH:MM format.
        
        Return ONLY a JSON object with this format:
        {{
            "date": "YYYY-MM-DD or null if only festival mentioned", 
            "time": "HH:MM or null",
            "festival_referenced": "Name of festival/holiday or null"
        }}
        
        Examples:
        - "Book a table for June 15th at 7 PM" -> {{"date": "{current_year}-06-15", "time": "19:00", "festival_referenced": null}}
        - "Reserve for tomorrow at 9" -> {{"date": "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}", "time": "09:00", "festival_referenced": null}}
        - "Book a table at 9PM on Diwali" -> {{"date": null, "time": "21:00", "festival_referenced": "Diwali"}}
        - "I'd like to dine next Friday evening at 6" -> {{"date": "YYYY-MM-DD", "time": "18:00", "festival_referenced": null}}
        - "Reserve for Christmas Eve 8pm" -> {{"date": null, "time": "20:00", "festival_referenced": "Christmas Eve"}}
        
        If a festival/holiday is mentioned, return its name in 'festival_referenced' and set 'date' to null unless a specific date was ALSO mentioned.
        Do NOT try to calculate the date for the festival yourself. Just extract the name.
        """
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_input}
        ]
        
        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 150
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                try:
                    parsed = json.loads(content)
                    extracted_date = parsed.get("date")
                    extracted_time = parsed.get("time")
                    festival_referenced = parsed.get("festival_referenced")
                    
                    logger.info(f"LLM extracted: Date={extracted_date}, Time={extracted_time}, Festival={festival_referenced}")

                    # Resolve date based on festival reference
                    final_date = extracted_date
                    weekday = None
                    
                    # PRIORITY CHANGED: First try holiday_resolver for festival dates, then fall back to LLM
                    if festival_referenced:
                        festival_name = festival_referenced.lower()
                        
                        # First priority: Use holiday_resolver with Calendarific data
                        resolved_date = holiday_resolver.get_festival_date(festival_name)
                        if resolved_date:
                            final_date = resolved_date
                            logger.info(f"Resolved festival '{festival_name}' to date: {final_date} using holiday_resolver (Calendarific)")
                        else:
                            # Second priority: Fall back to LLM for any holidays not in Calendarific
                            llm_date = self._get_holiday_date_from_llm(festival_name, current_year)
                            if llm_date:
                                final_date = llm_date
                                logger.info(f"Resolved festival '{festival_name}' to date: {final_date} using LLM fallback")
                            else:
                                logger.warning(f"Could not resolve date for festival: {festival_name}")
                    
                    # Get weekday for the final date
                    if final_date:
                        try:
                            date_obj = datetime.strptime(final_date, "%Y-%m-%d")
                            weekday = date_obj.strftime("%A")  # Full weekday name
                            logger.info(f"Resolved date {final_date} is on a {weekday}")
                        except Exception as e:
                            logger.error(f"Error calculating weekday for {final_date}: {e}")

                    return {
                        "intent": "booking",
                        "date": final_date,
                        "time": extracted_time,
                        "festival_referenced": festival_referenced,
                        "weekday": weekday
                    }
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse LLM response: {content}")
                    return {"intent": "booking", "date": None, "time": None, "festival_referenced": None, "weekday": None}
            else:
                logger.error(f"Groq API error: {response.status_code} - {response.text}")
                return {"intent": "booking", "date": None, "time": None, "festival_referenced": None, "weekday": None}
        except Exception as e:
            logger.error(f"Error in _extract_booking_details: {str(e)}")
            return {"intent": "booking", "date": None, "time": None, "festival_referenced": None, "weekday": None}
    
    def _extract_cancellation_details(self, user_input, session_context=None):
        """Extract date, time, and festival information for a cancellation request."""
        api_available, error_msg = self._check_api_available()
        if not api_available:
            return {"intent": "cancellation", "date": None, "time": None, "festival_referenced": None}
        
        url = f"{self.base_url}/chat/completions"
        
        today_date = datetime.now().strftime("%Y-%m-%d")
        current_year = datetime.now().year
        
        reference_context = ""
        if session_context:
            last_booking_date = session_context.get('last_booking_date')
            last_booking_time = session_context.get('last_booking_time')
            if last_booking_date and last_booking_time:
                reference_context = f"The user's most recent booking was on {last_booking_date} at {last_booking_time}."
        
        system_message = f"""
        You are an assistant for Paradise Grill restaurant helping to understand cancellation requests.
        Today's date is {today_date}. The current year is {current_year}.
        {reference_context}
        
        Your task:
        1. Extract the date if explicitly mentioned (e.g., "Cancel my booking for June 15th").
        2. Extract the time if mentioned (e.g., "Cancel my 7PM reservation").
        3. Extract the name of any festival or holiday mentioned (e.g., "Cancel my Diwali booking").
        4. Detect if the user is referring to their most recent booking (e.g., "Cancel my reservation").
        5. Convert extracted date references to YYYY-MM-DD format.
        6. Convert extracted time references to 24-hour HH:MM format.
        
        Return ONLY a JSON object with this format:
        {{
            "date": "YYYY-MM-DD or null if not specified", 
            "time": "HH:MM or null if not specified",
            "festival_referenced": "Name of festival/holiday or null",
            "is_recent_reference": true/false (true if user seems to be referring to their most recent booking)
        }}
        
        Examples:
        - "Cancel my reservation for June 15th at 7 PM" -> {{"date": "{current_year}-06-15", "time": "19:00", "festival_referenced": null, "is_recent_reference": false}}
        - "Cancel my booking" -> {{"date": null, "time": null, "festival_referenced": null, "is_recent_reference": true}}
        - "Cancel my Diwali reservation" -> {{"date": null, "time": null, "festival_referenced": "Diwali", "is_recent_reference": false}}
        """
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_input}
        ]
        
        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 150
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                try:
                    parsed = json.loads(content)
                    extracted_date = parsed.get("date")
                    extracted_time = parsed.get("time")
                    festival_referenced = parsed.get("festival_referenced")
                    is_recent_reference = parsed.get("is_recent_reference", False)
                    
                    logger.info(f"LLM extracted (cancellation): Date={extracted_date}, Time={extracted_time}, Festival={festival_referenced}, Recent={is_recent_reference}")

                    # Resolve festival date if mentioned
                    final_date = extracted_date
                    weekday = None
                    
                    if festival_referenced:
                        festival_name = festival_referenced.lower()
                        
                        # First priority: Use holiday_resolver
                        resolved_date = holiday_resolver.get_festival_date(festival_name)
                        if resolved_date:
                            final_date = resolved_date
                            logger.info(f"Resolved festival '{festival_name}' to date: {final_date} using holiday_resolver")
                        else:
                            # Second priority: Fall back to LLM for any holidays not in Calendarific
                            llm_date = self._get_holiday_date_from_llm(festival_name, current_year)
                            if llm_date:
                                final_date = llm_date
                                logger.info(f"Resolved festival '{festival_name}' to date: {final_date} using LLM fallback")
                            else:
                                logger.warning(f"Could not resolve date for festival: {festival_name}")
                    
                    # Get weekday for the final date
                    if final_date:
                        try:
                            date_obj = datetime.strptime(final_date, "%Y-%m-%d")
                            weekday = date_obj.strftime("%A")  # Full weekday name
                            logger.info(f"Resolved date {final_date} is on a {weekday}")
                        except Exception as e:
                            logger.error(f"Error calculating weekday for {final_date}: {e}")

                    return {
                        "intent": "cancellation",
                        "date": final_date,
                        "time": extracted_time,
                        "festival_referenced": festival_referenced,
                        "is_recent_reference": is_recent_reference,
                        "weekday": weekday
                    }
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse LLM response: {content} - Error: {e}")
                    return {"intent": "cancellation", "date": None, "time": None, "festival_referenced": None}
            else:
                logger.error(f"Groq API error: {response.status_code} - {response.text}")
                return {"intent": "cancellation", "date": None, "time": None, "festival_referenced": None}
        except Exception as e:
            logger.error(f"Error in _extract_cancellation_details: {str(e)}")
            return {"intent": "cancellation", "date": None, "time": None, "festival_referenced": None}
    
    def _get_holiday_date_from_llm(self, holiday_name, year):
        """Ask the LLM for the date of a specific holiday"""
        api_available, error_msg = self._check_api_available()
        if not api_available:
            return None
        
        url = f"{self.base_url}/chat/completions"
        
        system_message = f"""
        You are an AI assistant that knows the dates of holidays and festivals around the world.
        For the given holiday/festival name, return ONLY the date in YYYY-MM-DD format for the year {year}.
        Only respond with the date in YYYY-MM-DD format. No other text.
        """
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"What is the date of {holiday_name} in {year}?"}
        ]
        
        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 20
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"].strip()
                # Basic validation of date format
                if len(content) == 10 and content[4] == '-' and content[7] == '-':
                    return content
            return None
        except Exception as e:
            logger.error(f"Error getting holiday date from LLM: {str(e)}")
            return None
    
    def parse_clarification_response(self, user_response, ambiguity_info):
        """Parse the user's response to a clarification question"""
        api_available, error_msg = self._check_api_available()
        if not api_available:
            return "unknown"
        
        url = f"{self.base_url}/chat/completions"
        possibilities = ambiguity_info.get("possibilities", [])
        possibilities_str = ", ".join(possibilities)
        
        system_message = f"""
        The user was asked to clarify which time they meant for their Paradise Grill reservation.
        The possible options were: {possibilities_str}
        Based on the user's response, identify which time they've chosen.
        Return ONLY the time in HH:MM format with no other text.
        If you can't determine the time, respond with "unknown".
        """
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_response}
        ]
        
        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 100
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"].strip()
                if ":" in content and len(content) == 5:
                    return content
                return "unknown"
            else:
                return "unknown"
        except Exception as e:
            print(f"Error in parse_clarification_response: {str(e)}")
            return "unknown"
    
    def extract_raw_time_expression(self, user_input):
        """Extract the raw time expression from user input"""
        api_available, error_msg = self._check_api_available()
        if not api_available:
            return None
        
        url = f"{self.base_url}/chat/completions"
        
        system_message = """
        Extract ONLY the raw time expression from this Paradise Grill reservation request.
        Return just the expression itself with no other text or formatting.
        Examples:
        - "Book a table for Monday at 7 PM" → "7 PM"
        - "Reserve for Tuesday at half past 9" → "half past 9"
        - "Cancel my booking for Friday at quarter to 6" → "quarter to 6"
        If you can't find a time expression, return "unknown".
        """
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_input}
        ]
        
        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 100
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"].strip()
                if content.lower() == "unknown":
                    return None
                return content
            else:
                return None
        except Exception as e:
            print(f"Error in extract_raw_time_expression: {str(e)}")
            return None
    
    def generate_booking_response(self, result, festival_referenced=None):
        """Generate a response for a booking action"""
        api_available, error_msg = self._check_api_available()
        if not api_available:
            return f"Booking status: {result.get('status', 'unknown')}. {result.get('message', '')}"
        
        url = f"{self.base_url}/chat/completions"
        
        status = result.get('status', 'unknown')
        date = result.get('date', '')
        time = result.get('time', '')
        
        date_str = date
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            date_str = date_obj.strftime("%A, %B %d")
        except:
            pass
        
        festival_context = ""
        if festival_referenced:
            festival_context = f" for {festival_referenced}"
        
        system_message = f"""
        Generate a friendly response for a Paradise Grill booking result:
        
        Result: {json.dumps(result)}
        
        Information:
        - This is for Paradise Grill restaurant
        - Reservation{festival_context} on {date_str} at {time}
        - Status: {status}
        
        If the booking was successful, sound excited and welcoming.
        If it failed, offer apologies and suggest alternatives.
        Keep your response concise (2-3 sentences).
        """
        
        messages = [
            {"role": "system", "content": system_message}
        ]
        
        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 150
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                content = content.strip('"')
                return content
            else:
                return f"Booking {status}. {result.get('message', '')}"
        except Exception as e:
            logger.error(f"Error generating booking response: {str(e)}")
            return f"Booking {status}. {result.get('message', '')}"
    
    def generate_cancellation_response(self, result):
        """Generate a response for a cancellation action"""
        api_available, error_msg = self._check_api_available()
        if not api_available:
            return f"Cancellation status: {result.get('status', 'unknown')}. {result.get('message', '')}"
        
        url = f"{self.base_url}/chat/completions"
        
        status = result.get('status', 'unknown')
        date = result.get('cancelled_date', result.get('date', ''))
        time = result.get('cancelled_time', result.get('time', ''))
        
        date_str = date
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            date_str = date_obj.strftime("%A, %B %d")
        except:
            pass
        
        festival_context = ""
        if result.get('festival_referenced'):
            festival_context = f" for {result.get('festival_referenced')}"
        
        system_message = f"""
        Generate a friendly response for a Paradise Grill reservation cancellation:
        
        Result: {json.dumps(result)}
        
        Information:
        - This is for Paradise Grill restaurant
        - Cancellation{festival_context} on {date_str} at {time}
        - Status: {status}
        
        If the cancellation was successful, confirm it politely.
        If it failed, explain why and offer assistance.
        Keep your response concise (2-3 sentences).
        """
        
        messages = [
            {"role": "system", "content": system_message}
        ]
        
        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 150
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                content = content.strip('"')
                return content
            else:
                return f"Cancellation {status}. {result.get('message', '')}"
        except Exception as e:
            logger.error(f"Error generating cancellation response: {str(e)}")
            return f"Cancellation {status}. {result.get('message', '')}"

    def generate_available_slots_response(self, available_slots, date):
        """Generate a response showing available slots for a specific date"""
        api_available, error_msg = self._check_api_available()
        if not api_available:
            return f"Available slots for {date}: {len(available_slots)} slots found."
        
        url = f"{self.base_url}/chat/completions"
        
        # Format the date for display
        date_str = date
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            date_str = date_obj.strftime("%A, %B %d")
        except:
            pass
        
        # Format the available slots
        time_slots = []
        for slot in available_slots:
            if 'time' in slot:
                time_slots.append(slot['time'])
        
        time_slots.sort()  # Sort chronologically
        slots_str = ", ".join(time_slots)
        
        system_message = f"""
        Generate a friendly response showing available reservation slots at Paradise Grill:
        
        Information:
        - Date: {date_str}
        - Available times: {slots_str}
        - Number of available slots: {len(time_slots)}
        
        If there are available slots, list them in a friendly way.
        If there are no available slots, apologize and suggest checking another date.
        Keep your response concise (2-3 sentences).
        """
        
        messages = [
            {"role": "system", "content": system_message}
        ]
        
        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 200
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                content = content.strip('"')
                return content
            else:
                return f"Available slots for {date_str}: {slots_str}"
        except Exception as e:
            logger.error(f"Error generating available slots response: {str(e)}")
            return f"Available slots for {date_str}: {slots_str}"
