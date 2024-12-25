import eventlet
eventlet.monkey_patch()

from flask import Flask
from flask_socketio import SocketIO, emit
import os
import logging

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-default-secret-key')  # Replace with a secure secret key

# Initialize Socket.IO server with Eventlet for async support
socketio = SocketIO(
    app,
    cors_allowed_origins="*",  # Allow all origins; for production, specify your client's domain
    async_mode='eventlet'
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Define a simple route to verify the server is running
@app.route('/')
def index():
    return "Socket.IO server is running!"

# Event handler for client connection
@socketio.on('connect')
def handle_connect():
    logger.info(f"Client connected: {request.sid}")
    emit('message', {'data': 'Connected to server.'})

# Main entry point
if __name__ == '__main__':
    # Get the port from the environment or default to 5000
    port = int(os.environ.get('PORT', 5000))
    # Run the server and listen on all network interfaces
    socketio.run(app, host='0.0.0.0', port=port)
