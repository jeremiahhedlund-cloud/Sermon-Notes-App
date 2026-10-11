"""Private sermon notes web app. Deploy behind HTTPS with APP_PASSWORD and OPENAI_API_KEY."""
import hmac
import os
import tempfile
from pathlib import Path
from functools import wraps
from flask import Flask, request, jsonify, send_file, Response
from openai import OpenAI

ROOT = Path(__file__).resolve().parent
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024

@app.before_request
def require_login():
    if request.path == '/health':
        return None
    password = os.getenv('APP_PASSWORD', '')
    if len(password) < 16:
        return jsonify(error='APP_PASSWORD must be set to at least 16 characters.'), 503
    auth = request.authorization
    if not auth or not hmac.compare_digest(auth.password or '', password):
        return Response('Login required', 401, {'WWW-Authenticate': 'Basic realm="Sermon Notes"'})

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Frame-Options'] = 'DENY'
    return response

@app.get('/health')
def health():
    return jsonify(status='ok')

@app.get('/')
def home():
    return send_file(ROOT / 'index.html')

@app.post('/api/transcribe')
def transcribe():
    if not os.getenv('OPENAI_API_KEY'):
        return jsonify(error='OPENAI_API_KEY is not configured on the server.'), 503
    audio = request.files.get('audio')
    if not audio or not audio.filename:
        return jsonify(error='Choose a recording first.'), 400
    extension = Path(audio.filename).suffix.lower()
    if extension not in ('.webm', '.mp4', '.m4a', '.mp3', '.wav', '.ogg'):
        return jsonify(error='Unsupported audio format.'), 400
    try:
        with tempfile.NamedTemporaryFile(suffix=extension) as tmp:
            audio.save(tmp.name)
            with open(tmp.name, 'rb') as handle:
                result = OpenAI().audio.transcriptions.create(model='whisper-1', file=handle)
        return jsonify(text=result.text)
    except Exception:
        app.logger.exception('Transcription failed')
        return jsonify(error='Transcription failed. Check server logs, audio size, and API billing.'), 502

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', '5000')))
