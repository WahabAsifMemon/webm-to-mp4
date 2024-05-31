from flask import Flask, render_template, request, jsonify, send_file
import os
import subprocess
import time
import shutil
from werkzeug.utils import secure_filename
import logging

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
CHUNK_FOLDER = 'chunks'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CHUNK_FOLDER'] = CHUNK_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(CHUNK_FOLDER):
    os.makedirs(CHUNK_FOLDER)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_chunk', methods=['POST'])
def upload_chunk():
    try:
        chunk = request.files['chunk']
        upload_id = request.form['uploadId']
        chunk_index = request.form['chunkIndex']
        filename = secure_filename(request.form['filename'])

        chunk_dir = os.path.join(app.config['CHUNK_FOLDER'], upload_id)
        if not os.path.exists(chunk_dir):
            os.makedirs(chunk_dir)

        chunk_path = os.path.join(chunk_dir, f'{chunk_index}_{filename}')
        chunk.save(chunk_path)

        return jsonify({"status": "Chunk uploaded"}), 200
    except Exception as e:
        logging.error(f"Error uploading chunk: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/convert', methods=['POST'])
def convert():
    try:
        data = request.get_json()
        upload_id = data['uploadId']
        filename = secure_filename(data['filename'])

        chunk_dir = os.path.join(app.config['CHUNK_FOLDER'], upload_id)
        webm_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Merge chunks
        with open(webm_file_path, 'wb') as webm_file:
            # Corrected sorting and joining of chunks
            chunks = sorted(os.listdir(chunk_dir), key=lambda x: int(x.split('_')[0]))
            for chunk in chunks:
                chunk_path = os.path.join(chunk_dir, chunk)
                with open(chunk_path, 'rb') as chunk_file:
                    shutil.copyfileobj(chunk_file, webm_file)

        # Remove chunk directory after merging
        shutil.rmtree(chunk_dir)

        start_time = time.time()

        mp4_filename = os.path.splitext(filename)[0] + '.mp4'
        mp4_file_path = os.path.join(app.config['UPLOAD_FOLDER'], mp4_filename)

        command = [
            'ffmpeg', '-i', webm_file_path, '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac', '-strict', 'experimental', mp4_file_path
        ]

        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            logging.error(f"FFmpeg error: {result.stderr.decode()}")
            raise subprocess.CalledProcessError(result.returncode, command, result.stdout, result.stderr)

        end_time = time.time()
        conversion_time = end_time - start_time

        os.remove(webm_file_path)  # Remove the original file after conversion

        mp4_file_url = request.url_root + 'download/' + mp4_filename

        return jsonify({"mp4_file_url": mp4_file_url, "conversion_time": conversion_time})

    except subprocess.CalledProcessError as e:
        logging.error(f"FFmpeg error during conversion: {e.stderr.decode()}")
        return jsonify({"error": f"FFmpeg error during conversion: {e.stderr.decode()}"}), 500
    except Exception as e:
        logging.error(f"Error during conversion: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    mp4_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if os.path.exists(mp4_file_path):
        return send_file(mp4_file_path, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)
