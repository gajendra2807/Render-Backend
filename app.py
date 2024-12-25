import eventlet
eventlet.monkey_patch()

from flask import Flask, request
from flask_socketio import SocketIO, emit
import os
import logging

# Initialize Flask app
app = Flask(__name__)

# Secure secret key for sessions
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-default-secret-key')  # Replace in production

# Initialize Socket.IO with Eventlet and enable CORS
socketio = SocketIO(
    app,
    cors_allowed_origins="*",  # Allow all origins for development; restrict in production
    async_mode='eventlet',
    logger=True,
    engineio_logger=True
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Store the uploaded audio file (Base64 encoded) and metadata
uploaded_audio = {
    "filename": None,
    "data": None
}

# HTTP Route: Server status check
@app.route('/')
def index():
    return "Socket.IO server is running and WebSocket is supported!"


# WebSocket Event: Client connected
@socketio.on('connect')
def handle_connect():
    logger.info(f"Client connected: {request.sid}")
    emit('message', {'data': 'Connected to server.'})


# WebSocket Event: Client disconnected
@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"Client disconnected: {request.sid}")


# WebSocket Event: Upload audio file
@socketio.on('upload_song')
def handle_upload_song(data):
    global uploaded_audio

    try:
        # Get filename and file data from the client
        filename = data.get('filename', 'audio.mp3')
        file_data = data.get('file')  # Base64 encoded data

        if not filename or not file_data:
            emit('error', {'message': 'Invalid data format'})
            return

        # Save the uploaded audio in memory (could be saved to disk if needed)
        uploaded_audio['filename'] = filename
        uploaded_audio['data'] = file_data  # Base64 encoded MP3 file

        logger.info(f"Received and stored file: {filename}")

        # Notify all clients about the uploaded song
        socketio.emit('song_uploaded', {'filename': filename})
        emit('message', {'data': f"File {filename} uploaded successfully!"})

    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        emit('error', {'message': str(e)})


# WebSocket Event: Request to play the uploaded song
@socketio.on('play_song')
def handle_play_song():
    global uploaded_audio

    try:
        if uploaded_audio['filename'] and uploaded_audio['data']:
            # Broadcast the song data (Base64) to all connected clients
            socketio.emit('play_song', {
                'filename': uploaded_audio['filename'],
                'file': uploaded_audio['data']  # Base64 encoded data
            })
            logger.info(f"Playing song: {uploaded_audio['filename']}")
        else:
            emit('error', {'message': 'No audio file uploaded yet!'})

    except Exception as e:
        logger.error(f"Error playing song: {str(e)}")
        emit('error', {'message': str(e)})


# Entry point for running the server
if __name__ == '__main__':
    # Get the port dynamically or default to 5000
    port = int(os.environ.get('PORT', 5000))
    # Run the server with Eventlet
    socketio.run(app, host='0.0.0.0', port=port)
