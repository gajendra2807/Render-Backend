import eventlet
eventlet.monkey_patch()

from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from pydub import AudioSegment
import io
import logging
import os
import base64
import platform

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for detailed logs
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for all routes and origins
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize Socket.IO with WebSocket only
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    ping_timeout=300,       # Longer timeout for mobile connections
    ping_interval=100,      # Ping interval
    async_mode='eventlet',
    transports=['websocket']  # Force only WebSocket, skip polling
)

# Dynamically set FFMPEG path based on OS
if platform.system() == "Windows":
    # Windows development example (replace with your local ffmpeg.exe path)
    AudioSegment.converter = r"C:\path\to\ffmpeg\bin\ffmpeg.exe"
else:
    # Linux deployment example
    AudioSegment.converter = os.getenv('FFMPEG_PATH', '/usr/bin/ffmpeg')

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
    # Notify the client that the server is ready to receive chunks
    emit('upload_ready', room=request.sid)

@socketio.on('upload_chunk')
def handle_upload_chunk(data):
    """
    Client sends a chunk of base64-encoded data.
    We append it to the current file's BytesIO buffer.
    """
    try:
        # Decode Base64 chunk
        chunk = base64.b64decode(data) if isinstance(data, str) else data

        if request.sid in clients_data and clients_data[request.sid]["uploads"]:
            file_data = clients_data[request.sid]["uploads"][-1]["file_data"]
            file_data.write(chunk)
            logger.info(f"Received chunk from {request.sid}, size: {len(chunk)} bytes")
        else:
            logger.warning(f"No upload in progress for {request.sid}")
    except Exception as e:
        logger.error(f"Error processing chunk: {e}")
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
            file_data = clients_data[request.sid]["uploads"][-1]["file_data"]
            file_data.seek(0)
            mp3_data = file_data.read()

            # Notify the uploader that we're starting processing
            emit('processing_start', room=request.sid)
            socketio.sleep(1)  # Just a short pause for demonstration

            # Process the audio in chunks (example: converting to WAV)
            audio = AudioSegment.from_file(io.BytesIO(mp3_data), format="mp3")
            wav_io = io.BytesIO()
            chunk_size = 10 * 1000  # 10-second chunks
            processed_chunks = []

            for i in range(0, len(audio), chunk_size):
                chunk = audio[i:i + chunk_size]
                chunk.export(wav_io, format="wav")
                processed_chunks.append(wav_io.getvalue())

                # Send progress updates back to the uploader
                progress = min((i / len(audio)) * 100, 100)
                emit('processing_progress', {'progress': progress}, room=request.sid)
                socketio.sleep(0.5)

            # Combine processed chunks into one final WAV
            final_wav_data = b"".join(processed_chunks)
            processed_filename = f"processed_{request.sid}.wav"

            # Broadcast the processed audio to ALL clients
            emit('processing_complete', {
                'processed_filename': processed_filename,
                'uploader': request.sid,
                'data': base64.b64encode(final_wav_data).decode('utf-8')
            }, broadcast=True)

        else:
            emit('error', {'message': "No upload in progress"}, room=request.sid)
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        emit('error', {'message': f"Processing failed: {str(e)}"}, room=request.sid)

if __name__ == '__main__':
    # Enable detailed Socket.IO and Engine.IO logs
    logging.getLogger('socketio').setLevel(logging.DEBUG)
    logging.getLogger('engineio').setLevel(logging.DEBUG)

    # Run the server on 0.0.0.0:5000 so it can be accessed externally
    socketio.run(app, host='0.0.0.0', port=5000)
