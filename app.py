import eventlet
eventlet.monkey_patch()

from flask import Flask, request
from flask_socketio import SocketIO, emit
import os
import logging

# Initialize Flask app
app = Flask(__name__)

# Use a secure secret key for sessions
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-default-secret-key')  # Replace with secure key in production

# Initialize Socket.IO with Eventlet and enable CORS
socketio = SocketIO(
    app,
    cors_allowed_origins="*",  # Allow all origins for testing; restrict in production
    async_mode='eventlet',     # Use Eventlet for WebSocket support
    logger=True,               # Enable logs for debugging
    engineio_logger=True       # Enable detailed logs for Engine.IO
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Basic HTTP route for testing
@app.route('/')
def index():
    return "Socket.IO server is running and WebSocket is supported!"

# WebSocket event: Handle client connection
@socketio.on('connect')
def handle_connect():
    logger.info(f"Client connected: {request.sid}")
    emit('message', {'data': 'Connected to server.'})

# WebSocket event: Handle client disconnection
@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"Client disconnected: {request.sid}")

# WebSocket event: Handle custom events
@socketio.on('custom_event')
def handle_custom_event(data):
    logger.info(f"Received custom_event from {request.sid}: {data}")
    emit('response', {'data': 'Custom event received successfully.'})

# Entry point for running the server
if __name__ == '__main__':
    # Get port dynamically from Render.com or default to 5000 for local testing
    port = int(os.environ.get('PORT', 5000))

    # Run the app using Eventlet (supports WebSockets)
    socketio.run(app, host='0.0.0.0', port=port)
