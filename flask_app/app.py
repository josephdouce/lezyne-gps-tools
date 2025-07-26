from downloader import generate_tiles, request_tile
from flask import Flask, render_template, request, send_file, Response, jsonify, stream_with_context, after_this_request  
from tcx2lzr import convert_file
from io import BytesIO
import zipfile
import requests
import time
import logging
import threading
import os
import json

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))  # Points to flask_app/
TEMP_DIR = os.path.join(BASE_DIR, "temp")

os.makedirs(BASE_DIR, exist_ok=True)

class ZipManager:
    def __init__(self):
        self.progress = {"total": 0, "completed": 0}
        self.thread = None

    def build_zip(self, sw_lat, sw_lon, ne_lat, ne_lon):
        sw_lat = round(sw_lat,2)
        sw_lon = round(sw_lon,2)
        ne_lat = round(ne_lat,2)
        ne_lon = round(ne_lon,2)
        self.progress["completed"] = 0
        tiles = generate_tiles(sw_lat, sw_lon, ne_lat, ne_lon)
        self.progress["total"] = len(tiles) + 2
        self.progress["completed"] += 1

        # Use stable path based on coordinates
        filename = f"tiles_{sw_lat}_{sw_lon}_{ne_lat}_{ne_lon}.zip"
        zip_path = os.path.join(TEMP_DIR, filename)

        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
            for sw, ne in tiles:
                url = request_tile(sw, ne)
                if url:
                    try:
                        response = requests.get(url)
                        if response.status_code == 200:
                            fname = f"mf_{sw['lat']}_{sw['lon']}_{ne['lat']}_{ne['lon']}.lzm"
                            zipf.writestr(fname, response.content)
                    except Exception as error:
                        logging.debug(f"Error downloading {url}: {error}")
                self.progress["completed"] += 1
        self.progress["completed"] += 1

# Attach to app config
app.config['zip_manager'] = ZipManager()

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/get_track', methods=['POST'])
def get_track():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    input_bytes = file.read()
    _, trackpoints, coursepoints = convert_file(input_bytes)

    return jsonify({
        "trackpoints": [{"lat": lat, "lon": lon, "alt": alt, "distance": dist, "climb":climb} for lat, lon, alt, dist, climb in trackpoints],
        "coursepoints": [
            {"lat": lat, "lon": lon, "label": notes or name, "type": typ}
            for name, lat, lon, typ, notes, _ in coursepoints
        ],
    })

@app.route('/download', methods=['POST'])
def download():
    sw_lat = float(request.form['sw_lat'])
    sw_lon = float(request.form['sw_lon'])
    ne_lat = float(request.form['ne_lat'])
    ne_lon = float(request.form['ne_lon'])

    zm = app.config['zip_manager']
    zm.progress = {"total": 0, "completed": 0}
    zm.zip_path = None

    zm.thread = threading.Thread(
        target=zm.build_zip,
        args=(sw_lat, sw_lon, ne_lat, ne_lon),
        daemon=True
    )
    zm.thread.start()

    return "", 202


@app.route('/progress')
def progress():
    zm = app.config['zip_manager']

    # Recompute the same filename used in build_zip
    sw_lat = request.args.get('sw_lat', type=float)
    sw_lon = request.args.get('sw_lon', type=float)
    ne_lat = request.args.get('ne_lat', type=float)
    ne_lon = request.args.get('ne_lon', type=float)
    filename = f"tiles_{sw_lat}_{sw_lon}_{ne_lat}_{ne_lon}.zip"
    zip_path = os.path.join(TEMP_DIR, filename)

    def event_stream():
        last_sent = (-1, -1, False, -1)
        while True:
            done = zm.progress["completed"]
            total = zm.progress["total"]
            ready = os.path.exists(zip_path) and (not zm.thread or not zm.thread.is_alive())
            zip_size = os.path.getsize(zip_path) if os.path.exists(zip_path) else 0

            current = (done, total, ready, zip_size)
            if current != last_sent:
                yield f"data: {json.dumps({'completed': done, 'total': total, 'ready': ready, 'size': zip_size})}\n\n"
                last_sent = current
            else:
                yield ": keep-alive\n\n"

            time.sleep(0.5)

    response = Response(stream_with_context(event_stream()), mimetype='text/event-stream')
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response

@app.route('/download_zip')
def download_zip():
    sw_lat = request.args.get('sw_lat', type=float)
    sw_lon = request.args.get('sw_lon', type=float)
    ne_lat = request.args.get('ne_lat', type=float)
    ne_lon = request.args.get('ne_lon', type=float)
    filename = f"tiles_{sw_lat}_{sw_lon}_{ne_lat}_{ne_lon}.zip"
    zip_path = os.path.join(TEMP_DIR, filename)

    if not os.path.exists(zip_path):
        return "ZIP file not ready or missing", 404

    # Optional: delay cleanup, or keep files permanently and clean them later
    return send_file(
        zip_path,
        mimetype='application/zip',
        as_attachment=True,
        download_name='downloaded_tiles.zip'
    )

@app.route('/get_lzr', methods=['POST'])
def get_lzr():
    if 'file' not in request.files:
        return "No file uploaded", 400

    file = request.files['file']
    if not file.filename.endswith('.tcx'):
        return "Invalid file type", 400

    input_bytes = file.read()
    lzr_bytes, _, _ = convert_file(input_bytes)

    return send_file(
        BytesIO(lzr_bytes),
        as_attachment=True,
        download_name=file.filename.replace(".tcx", ".lzr"),
        mimetype="application/octet-stream"
    )

if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    app.run(debug=True)
else:
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.WARNING)
