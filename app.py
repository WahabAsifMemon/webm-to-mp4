from flask import Flask, render_template, request, jsonify, send_file
import os
import subprocess
import time
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        try:
            webm_filename = secure_filename(file.filename)
            webm_file_path = os.path.join(app.config['UPLOAD_FOLDER'], webm_filename)
            file.save(webm_file_path)

            start_time = time.time()

            mp4_filename = os.path.splitext(webm_filename)[0] + '.mp4'
            mp4_file_path = os.path.join(app.config['UPLOAD_FOLDER'], mp4_filename)

            # Use 'ffmpeg' directly without specifying a full path
            command = [
                'ffmpeg', '-i', webm_file_path, '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac', '-strict', 'experimental', mp4_file_path
            ]

            subprocess.run(command, check=True)

            end_time = time.time()
            conversion_time = end_time - start_time

            mp4_file_url = request.url_root + 'download/' + mp4_filename

            return jsonify({"mp4_file_url": mp4_file_url, "conversion_time": conversion_time})

        except subprocess.CalledProcessError as e:
            return jsonify({"error": "FFmpeg error during conversion: " + str(e)}), 500
        except Exception as e:
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
