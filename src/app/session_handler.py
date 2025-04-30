import uuid
from datetime import datetime, timedelta
import json
import os

class SessionManager:
    """Manages conversation sessions for bookings"""
    
    def __init__(self, session_dir=None):
        if session_dir is None:
            # Use absolute path to ensure we're accessing the correct directory
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.session_dir = os.path.join(base_dir, 'data', 'sessions')
        else:
            self.session_dir = session_dir
            
        # Ensure the session directory exists
        os.makedirs(self.session_dir, exist_ok=True)
    
    def create_session(self, user_name):
        """Create a new conversation session"""
        session_id = str(uuid.uuid4())
        session_data = {
            'session_id': session_id,
            'user_name': user_name,
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'status': 'active',
            'context': {
                'intent': None,
                'date': None,
                'time': None,
                'ambiguous_time': None,
                'pending_clarification': False,
                'clarification_type': None,
                'last_booking': None,
                'last_booking_date': None,
                'last_booking_time': None,
                'last_booking_id': None,
                'reference_date': datetime.now().isoformat() # Important for relative date references
            },
            'messages': []
        }
        
        self._save_session(session_id, session_data)
        return session_id
    
    def get_session(self, session_id):
        """Get a session by ID"""
        session_file = os.path.join(self.session_dir, f"{session_id}.json")
        if not os.path.exists(session_file):
            return None
            
        try:
            with open(session_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None
    
    def update_session(self, session_id, updates):
        """Update a session with new data"""
        session = self.get_session(session_id)
        if not session:
            return False
            
        # Update the session data
        for key, value in updates.items():
            if key == 'context':
                # For context, update individual fields rather than replacing entire object
                for context_key, context_value in value.items():
                    session['context'][context_key] = context_value
            else:
                session[key] = value
                
        session['last_updated'] = datetime.now().isoformat()
        
        return self._save_session(session_id, session)
    
    def add_message(self, session_id, role, content):
        """Add a message to the session history"""
        session = self.get_session(session_id)
        if not session:
            return False
            
        session['messages'].append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        
        session['last_updated'] = datetime.now().isoformat()
        
        return self._save_session(session_id, session)
    
    def update_last_booking(self, session_id, booking_info):
        """Update the session with information about the last booking"""
        session = self.get_session(session_id)
        if not session:
            return False
            
        # Update the context with last booking information
        context_update = {
            'last_booking': booking_info,
            'last_booking_date': booking_info.get('date'),
            'last_booking_time': booking_info.get('time'),
            'last_booking_id': booking_info.get('booking_id')
        }
        
        self.update_session(session_id, {'context': context_update})
        return True
    
    def _save_session(self, session_id, session_data):
        """Save a session to disk"""
        session_file = os.path.join(self.session_dir, f"{session_id}.json")
        try:
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            return True
        except Exception:
            return False
    
    def cleanup_old_sessions(self, max_age_hours=24):
        """Remove sessions older than the specified age"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        for filename in os.listdir(self.session_dir):
            if not filename.endswith('.json'):
                continue
                
            file_path = os.path.join(self.session_dir, filename)
            try:
                with open(file_path, 'r') as f:
                    session = json.load(f)
                    
                last_updated = datetime.fromisoformat(session['last_updated'])
                if last_updated < cutoff_time:
                    os.remove(file_path)
            except Exception:
                # If we can't read the file, it might be corrupted - delete it
                try:
                    os.remove(file_path)
                except:
                    pass