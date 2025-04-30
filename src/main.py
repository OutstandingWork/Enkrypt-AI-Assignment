from flask import Flask
from app.routes import register_routes  # Local import without src prefix
import os

# Create data directory if it doesn't exist
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# Create sessions directory if it doesn't exist
sessions_dir = os.path.join(data_dir, 'sessions')
if not os.path.exists(sessions_dir):
    os.makedirs(sessions_dir)

app = Flask(__name__, 
           static_folder='static',
           template_folder='templates')

# Register all routes
register_routes(app)

if __name__ == '__main__':
    app.run(debug=True, port=5000)