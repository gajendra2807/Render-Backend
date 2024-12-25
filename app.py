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
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for Android app compatibility
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize Socket.IO with WebSocket and timeout configurations
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    ping_timeout=300,  # Longer timeout for mobile connections
    ping_interval=100,
    async_mode='eventlet'
)

# Dynamically set FFMPEG path based on OS
if platform.system() == "Windows":
    # Windows Development
    AudioSegment.converter = r"C:\path\to\ffmpeg\bin\ffmpeg.exe"  # Replace with your Windows ffmpeg.exe path
else:
    # Linux Deployment
    AudioSegment.converter = os.getenv('FFMPEG_PATH', '/usr/bin/ffmpeg')  # Linux default path for deployment

# Global variables for managing uploads
uploaded_files = []
clients_data = {}


@app.route('/')
def index():
    return "Flask-SocketIO server running for Android app audio processing."


@socketio.on('connect')
def handle_connect():
    logger.info(f"Client connected: {request.sid}")
    # Initialize session data
    clients_data[request.sid] = {"uploads": []}

    # Send existing files to the newly connected client
    emit('uploaded_files_list', uploaded_files, room=request.sid)


@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"Client disconnected: {request.sid}")
    # Optionally preserve session data
    if request.sid in clients_data:
        logger.info(f"Preserving data for {request.sid}")


@socketio.on('upload_start')
def handle_upload_start(data):
    filename = data.get('filename', 'unknown.mp3')
    logger.info(f"Upload started for file: {filename} from {request.sid}")

    # Add metadata
    uploaded_files.append({"filename": filename, "uploader": request.sid})

    # Prepare to receive data
    if request.sid in clients_data:
        clients_data[request.sid]["uploads"].append({"filename": filename, "file_data": io.BytesIO()})
    emit('upload_ready', room=request.sid)


@socketio.on('upload_chunk')
def handle_upload_chunk(data):
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
    try:
        if request.sid in clients_data and clients_data[request.sid]["uploads"]:
            logger.info(f"Upload complete for {request.sid}. Processing audio...")

            # Retrieve uploaded data
            file_data = clients_data[request.sid]["uploads"][-1]["file_data"]
            file_data.seek(0)
            mp3_data = file_data.read()

            emit('processing_start', room=request.sid)
            socketio.sleep(1)

            # Process the audio in chunks
            audio = AudioSegment.from_file(io.BytesIO(mp3_data), format="mp3")
            wav_io = io.BytesIO()
            chunk_size = 10 * 1000  # Process 10 seconds at a time
            processed_chunks = []

            for i in range(0, len(audio), chunk_size):
                chunk = audio[i:i + chunk_size]
                chunk.export(wav_io, format="wav")
                processed_chunks.append(wav_io.getvalue())

                # Send progress updates
                emit('processing_progress', {'progress': (i / len(audio)) * 100}, room=request.sid)
                socketio.sleep(0.5)

            # Combine processed chunks
            final_wav_data = b"".join(processed_chunks)
            processed_filename = f"processed_{request.sid}.wav"

            emit('processing_complete', {
                'processed_filename': processed_filename,
                'data': base64.b64encode(final_wav_data).decode('utf-8')  # Send data as Base64
            }, room=request.sid)
        else:
            emit('error', {'message': "No upload in progress"}, room=request.sid)
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        emit('error', {'message': f"Processing failed: {str(e)}"}, room=request.sid)


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
