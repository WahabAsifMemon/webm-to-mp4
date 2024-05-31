from flask import Flask, render_template, request, jsonify, send_file
import os
import subprocess
import time
import traceback
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_chunk', methods=['POST'])
def upload_chunk():
    file_chunk = request.files['file']
    total_chunks = int(request.form['total_chunks'])
    current_chunk = int(request.form['current_chunk'])

    filename = secure_filename(file_chunk.filename)
    chunk_filename = f'{filename}.{current_chunk}'

    chunk_filepath = os.path.join(app.config['UPLOAD_FOLDER'], chunk_filename)
    file_chunk.save(chunk_filepath)

    if current_chunk == total_chunks - 1:
        # All chunks received, concatenate them
        with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'ab') as f:
            for i in range(total_chunks):
                chunk_filename = f'{filename}.{i}'
                chunk_filepath = os.path.join(app.config['UPLOAD_FOLDER'], chunk_filename)
                with open(chunk_filepath, 'rb') as chunk_file:
                    f.write(chunk_file.read())
                os.remove(chunk_filepath)

        # Now, start the conversion process
        try:
            start_time = time.time()

            mp4_filename = os.path.splitext(filename)[0] + '.mp4'
            webm_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            mp4_file_path = os.path.join(app.config['UPLOAD_FOLDER'], mp4_filename)

            command = [
                'ffmpeg', '-i', webm_file_path, '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac', '-strict', 'experimental', mp4_file_path
            ]

            process = subprocess.Popen(command, stderr=subprocess.PIPE)
            output, error = process.communicate()

            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, command, output=output, stderr=error)

            end_time = time.time()
            conversion_time = end_time - start_time

            mp4_file_url = request.url_root + 'download/' + mp4_filename

            return jsonify({"mp4_file_url": mp4_file_url, "conversion_time": conversion_time}), 200

        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    else:
        return jsonify({'message': 'Chunk uploaded successfully'}), 200

@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    mp4_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if os.path.exists(mp4_file_path):
        return send_file(mp4_file_path, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)
