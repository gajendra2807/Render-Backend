import eventlet
eventlet.monkey_patch()

from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os
import logging

# =======================
# Configuration Settings
# =======================

# Initialize Flask app
app = Flask(__name__)

# Configure CORS to allow connections from specific origins
# For development purposes, you can allow all origins.
# In production, replace '*' with your frontend's domain.
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize SocketIO with Eventlet as the asynchronous mode
socketio = SocketIO(
    app,
    cors_allowed_origins="*",   # Adjust this in production
    async_mode='eventlet',     # Use 'eventlet' for asynchronous handling
    logger=True,               # Enable SocketIO's internal logger
    engineio_logger=True       # Enable EngineIO's internal logger
)

# =====================
# Logging Configuration
# =====================

# Set up logging to output to both console and a file
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for detailed logs; change to INFO or WARNING in production
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),                  # Log to console
        logging.FileHandler("server.log")         # Log to a file named 'server.log'
    ]
)
logger = logging.getLogger(__name__)

# =====================
# Server Routes
# =====================

@app.route('/')
def index():
    return "Flask-SocketIO server running for Android app audio processing.\\"

# =====================
# SocketIO Event Handlers
# =====================

@socketio.on('connect')
def handle_connect():
    """
    Handle a new client connection.
    """
    logger.info(f"Client connected: {request.sid}")
    # Optionally, emit an event to the client upon successful connection
    emit('connected', {'message': 'Successfully connected to the server.'})

@socketio.on('disconnect')
def handle_disconnect():
    """
    Handle client disconnection.
    """
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('upload_audio')
def handle_upload_audio(data):
    """
    Handle the 'upload_audio' event from the client.
    Expects data in the format:
    {
        'filename': 'example.mp3',
        'data': '<base64-encoded-audio>'
    }
    """
    filename = data.get('filename', 'unknown.mp3')
    base64_data = data.get('data')

    if not base64_data:
        logger.warning(f"No audio data received from {request.sid}")
        emit('error', {'message': 'No audio data received.'}, room=request.sid)
        return

    logger.info(f"Received 'upload_audio' from {request.sid}: {filename}")

    # TODO: Implement your audio processing logic here
    # For demonstration, we'll simply echo back the received data
    processed_base64 = process_audio(base64_data)

    # Emit the 'processing_complete' event back to the client with the processed data
    emit('processing_complete', {
        'processed_filename': f"processed_{filename}",
        'base64Audio': processed_base64
    }, room=request.sid)

@socketio.on('test_event')
def handle_test_event(data):
    """
    Handle a 'test_event' from the client.
    This is a simple event to test connectivity.
    """
    logger.info(f"Received 'test_event' from {request.sid}: {data}")
    emit('processing_complete', {'response': 'Hello Client!'}, room=request.sid)

# =====================
# Helper Functions
# =====================

def process_audio(base64_data):
    """
    Placeholder function to process audio data.
    Replace this with your actual audio processing logic.
    
    Args:
        base64_data (str): Base64-encoded audio data.
    
    Returns:
        str: Processed base64-encoded audio data.
    """
    # TODO: Implement actual processing (e.g., noise reduction, format conversion)
    logger.debug("Processing audio data (placeholder function).")
    return base64_data  # Echo back the data for testing

# =====================
# Server Execution
# =====================

if __name__ == '__main__':
    # Retrieve the port number from the environment variable (set by Render)
    port = int(os.getenv('PORT', 5000))
    
    logger.info(f"Starting Flask-SocketIO server on port {port}...")
    
    # Run the SocketIO server with Eventlet
    socketio.run(app, host='0.0.0.0', port=port)
