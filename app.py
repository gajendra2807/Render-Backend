import eventlet
eventlet.monkey_patch()

import os
import io
import logging
import platform
import base64

from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from pydub import AudioSegment
from dotenv import load_dotenv

# Load environment variables from .env file (if using)
load_dotenv()

# Configuration
FFMPEG_PATH = os.getenv('FFMPEG_PATH', '/usr/bin/ffmpeg')  # Default for Linux
PORT = int(os.getenv('PORT', 5000))
DEBUG = os.getenv('DEBUG', 'False').lower() in ['true', '1', 't']

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,  # Detailed logs if DEBUG is True
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("server.log")  # Log to file (optional)
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for all routes and origins (adjust for production)
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize Socket.IO with WebSocket and polling transports
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    ping_timeout=300,       # Longer timeout for mobile connections
    ping_interval=100,      # Ping interval in seconds
    async_mode='eventlet',
    transports=['websocket', 'polling']  # Allow both transports
)

# Dynamically set FFMPEG path based on OS
if platform.system() == "Windows":
    # Windows development example (ensure the path is correct)
    AudioSegment.converter = os.getenv('FFMPEG_WINDOWS_PATH', r"C:\ffmpeg\bin\ffmpeg.exe")
    AudioSegment.ffmpeg = AudioSegment.converter
else:
    # Linux/macOS deployment example
    AudioSegment.converter = FFMPEG_PATH
    AudioSegment.ffmpeg = FFMPEG_PATH

# Global variables for managing uploads
uploaded_files = []       # For metadata (optional)
clients_data = {}         # To store chunked uploads per client

@app.route('/')
def index():
    return "Flask-SocketIO server running for Android app audio processing."

@socketio.on('connect')
def handle_connect():
    """ Handle a new client connection """
    logger.info(f"Client connected: {request.sid}")
    # Initialize data structure for this client's uploads
    clients_data[request.sid] = {"uploads": []}

    # Send existing file metadata to the newly connected client (if desired)
    emit('uploaded_files_list', uploaded_files, room=request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    """ Handle client disconnect """
    logger.info(f"Client disconnected: {request.sid}")
    # Optionally preserve client data if needed
    if request.sid in clients_data:
        logger.info(f"Preserving data for {request.sid}")
        # You can implement data preservation logic here if needed

@socketio.on('upload_start')
def handle_upload_start(data):
    """
    Client signals start of upload.
    data = {
      "filename": "audio.mp3"  # for example
    }
    """
    filename = data.get('filename', 'unknown.mp3')
    logger.info(f"Upload started for file: {filename} from {request.sid}")

    # Keep track of this file in a global list (optional)
    uploaded_files.append({"filename": filename, "uploader": request.sid})

    # Prepare to receive data in clients_data
    if request.sid in clients_data:
        clients_data[request.sid]["uploads"].append({
            "filename": filename,
            "file_data": io.BytesIO()
        })
    else:
        # Initialize if not present
        clients_data[request.sid] = {
            "uploads": [{
                "filename": filename,
                "file_data": io.BytesIO()
            }]
        }

    # Notify the client that the server is ready to receive chunks
    emit('upload_ready', room=request.sid)

@socketio.on('upload_chunk')
def handle_upload_chunk(data):
    """
    Client sends a chunk of base64-encoded data.
    We append it to the current file's BytesIO buffer.
    """
    try:
        # Decode Base64 chunk if it's a string
        if isinstance(data, str):
            chunk = base64.b64decode(data)
        elif isinstance(data, bytes):
            chunk = data
        else:
            logger.warning(f"Received unsupported data type from {request.sid}")
            emit('error', {'message': "Unsupported data type for chunk"}, room=request.sid)
            return

        if request.sid in clients_data and clients_data[request.sid]["uploads"]:
            file_data = clients_data[request.sid]["uploads"][-1]["file_data"]
            file_data.write(chunk)
            logger.debug(f"Received chunk from {request.sid}, size: {len(chunk)} bytes")
        else:
            logger.warning(f"No upload in progress for {request.sid}")
            emit('error', {'message': "No upload in progress"}, room=request.sid)
    except Exception as e:
        logger.error(f"Error processing chunk from {request.sid}: {e}")
        emit('error', {'message': f"Chunk processing failed: {str(e)}"}, room=request.sid)

@socketio.on('upload_complete')
def handle_upload_complete():
    """
    Client signals that the upload is complete.
    We then process the received audio file.
    """
    try:
        if request.sid in clients_data and clients_data[request.sid]["uploads"]:
            logger.info(f"Upload complete for {request.sid}. Processing audio...")

            # Retrieve uploaded data
            file_entry = clients_data[request.sid]["uploads"][-1]
            file_data = file_entry["file_data"]
            filename = file_entry["filename"]
            file_data.seek(0)
            mp3_data = file_data.read()

            # Notify the uploader that we're starting processing
            emit('processing_start', room=request.sid)
            socketio.sleep(1)  # Short pause for demonstration

            # Process the audio (e.g., converting to WAV)
            audio = AudioSegment.from_file(io.BytesIO(mp3_data), format="mp3")
            processed_chunks = []
            chunk_size_ms = 10 * 1000  # 10-second chunks in milliseconds

            total_length = len(audio)
            logger.debug(f"Total audio length: {total_length} ms")

            for i in range(0, total_length, chunk_size_ms):
                chunk = audio[i:i + chunk_size_ms]
                wav_io = io.BytesIO()
                chunk.export(wav_io, format="wav")
                processed_chunks.append(wav_io.getvalue())

                # Calculate progress percentage
                progress = min((i + chunk_size_ms) / total_length * 100, 100)
                emit('processing_progress', {'progress': int(progress)}, room=request.sid)
                logger.debug(f"Processing progress for {request.sid}: {int(progress)}%")
                socketio.sleep(0.5)  # Simulate processing time

            # Combine processed chunks into one final WAV
            # Note: Simply concatenating WAV byte data may not produce a valid WAV file.
            # Proper WAV concatenation requires handling headers and metadata correctly.
            # For demonstration purposes, we'll assume processing is chunk-based.

            # Here, we'll save each chunk as separate files or handle accordingly
            # For simplicity, we'll concatenate bytes (not recommended for actual WAV files)
            final_wav_data = b"".join(processed_chunks)
            processed_filename = f"processed_{request.sid}.wav"

            # Broadcast the processed audio to ALL clients
            emit('processing_complete', {
                'processed_filename': processed_filename,
                'uploader': request.sid,
                'data': base64.b64encode(final_wav_data).decode('utf-8')
            }, broadcast=True)

            logger.info(f"Processing complete for {request.sid}. Broadcasted to all clients.")

        else:
            logger.warning(f"No upload in progress for {request.sid}")
            emit('error', {'message': "No upload in progress"}, room=request.sid)
    except Exception as e:
        logger.error(f"Error processing audio for {request.sid}: {e}")
        emit('error', {'message': f"Processing failed: {str(e)}"}, room=request.sid)

if __name__ == '__main__':
    # Enable detailed Socket.IO and Engine.IO logs if DEBUG is True
    if DEBUG:
        logging.getLogger('socketio').setLevel(logging.DEBUG)
        logging.getLogger('engineio').setLevel(logging.DEBUG)

    # Run the server on 0.0.0.0:PORT so it can be accessed externally
    logger.info(f"Starting Flask-SocketIO server on port {PORT}...")
    socketio.run(app, host='0.0.0.0', port=PORT)
