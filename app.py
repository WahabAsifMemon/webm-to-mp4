# from flask import Flask, render_template, request, jsonify, send_file
# import os
# import subprocess
# import time
# import traceback  # Import traceback module
# from werkzeug.utils import secure_filename
#
# app = Flask(__name__)
#
# UPLOAD_FOLDER = 'uploads'
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
#
# if not os.path.exists(UPLOAD_FOLDER):
#     os.makedirs(UPLOAD_FOLDER)
#
# @app.route('/')
# def index():
#     return render_template('index.html')
#
# @app.route('/convert', methods=['POST'])
# def convert():
#     if 'file' not in request.files:
#         return jsonify({"error": "No file part"}), 400
#
#     file = request.files['file']
#
#     if file.filename == '':
#         return jsonify({"error": "No selected file"}), 400
#
#     if file:
#         try:
#             webm_filename = secure_filename(file.filename)
#             webm_file_path = os.path.join(app.config['UPLOAD_FOLDER'], webm_filename)
#             file.save(webm_file_path)
#
#             start_time = time.time()
#
#             mp4_filename = os.path.splitext(webm_filename)[0] + '.mp4'
#             mp4_file_path = os.path.join(app.config['UPLOAD_FOLDER'], mp4_filename)
#
#             # Use 'ffmpeg' directly without specifying a full path
#             command = [
#                 'ffmpeg', '-i', webm_file_path, '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac', '-strict', 'experimental', mp4_file_path
#             ]
#
#             # Use subprocess.Popen instead of subprocess.run to capture error output
#             process = subprocess.Popen(command, stderr=subprocess.PIPE)
#             output, error = process.communicate()
#
#             if process.returncode != 0:
#                 raise subprocess.CalledProcessError(process.returncode, command, output=output, stderr=error)
#
#             end_time = time.time()
#             conversion_time = end_time - start_time
#
#             mp4_file_url = request.url_root + 'download/' + mp4_filename
#
#             return jsonify({"mp4_file_url": mp4_file_url, "conversion_time": conversion_time})
#
#         except subprocess.CalledProcessError as e:
#             # Print full error message to console
#             traceback.print_exception(type(e), e, e.__traceback__)
#             return jsonify({"error": "FFmpeg error during conversion: " + str(e)}), 500
#         except Exception as e:
#             # Print full error message to console
#             traceback.print_exc()
#             return jsonify({"error": str(e)}), 500
#
# @app.route('/download/<filename>', methods=['GET'])
# def download(filename):
#     mp4_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#
#     if os.path.exists(mp4_file_path):
#         return send_file(mp4_file_path, as_attachment=True)
#     else:
#         return jsonify({"error": "File not found"}), 404
#
# if __name__ == '__main__':
#     app.run(debug=True)

from celery import Celery
from flask import Flask, render_template, request, jsonify, send_file
import os
import subprocess
import traceback  # Import traceback module
from werkzeug.utils import secure_filename

# Initialize Celery
celery = Celery(__name__, broker=os.environ.get('REDIS_URL'))
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

@celery.task
def convert_file(webm_file_path, mp4_file_path, base_url):
    try:
        command = [
            'ffmpeg', '-i', webm_file_path, '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac', '-strict', 'experimental', mp4_file_path
        ]
        subprocess.run(command, check=True)
        return {"mp4_file_url": base_url + 'download/' + os.path.basename(mp4_file_path)}
    except Exception as e:
        # Handle the exception
        return {"error": str(e)}

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

            mp4_filename = os.path.splitext(webm_filename)[0] + '.mp4'
            mp4_file_path = os.path.join(app.config['UPLOAD_FOLDER'], mp4_filename)

            # Enqueue the conversion task
            task = convert_file.delay(webm_file_path, mp4_file_path, request.url_root)

            return jsonify({"task_id": task.id})

        except Exception as e:
            return jsonify({"error": str(e)}), 500

# Add a route to check the status of the conversion task
@app.route('/status/<task_id>')
def get_status(task_id):
    task = convert_file.AsyncResult(task_id)
    if task.state == 'PENDING':
        return jsonify({"status": "pending"})
    elif task.state == 'STARTED':
        return jsonify({"status": "started"})
    elif task.state == 'SUCCESS':
        return jsonify({"status": "success", "result": task.result})
    elif task.state in ['RETRY', 'FAILURE']:
        return jsonify({"status": "error", "message": task.info})
    return jsonify({"status": "unknown"})

@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    mp4_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if os.path.exists(mp4_file_path):
        return send_file(mp4_file_path, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)