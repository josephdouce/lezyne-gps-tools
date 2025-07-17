from downloader import generate_tiles, request_tile
from flask import Flask, render_template, request, send_file, Response, jsonify, stream_with_context
from tcx2lzr import convert_file
from io import BytesIO
import zipfile
import requests
import time
import logging
import threading

app = Flask(__name__)

class ZipManager:
    def __init__(self):
        self.progress = {"total": 0, "completed": 0}
        self.zip_bytes = BytesIO()
        self.thread = None

    def build_zip(self, sw_lat, sw_lon, ne_lat, ne_lon):
        self.progress["completed"] = 0
        self.zip_bytes = BytesIO()
        tiles = generate_tiles(sw_lat, sw_lon, ne_lat, ne_lon)
        self.progress["total"] = len(tiles) + 2
        self.progress["completed"] += 1

        with zipfile.ZipFile(self.zip_bytes, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
            for sw, ne in tiles:
                url = request_tile(sw, ne)
                if url:
                    try:
                        response = requests.get(url)
                        if response.status_code == 200:
                            filename = f"mf_{sw['lat']}_{sw['lon']}_{ne['lat']}_{ne['lon']}.lzm"
                            zipf.writestr(filename, response.content)
                    except Exception as error:
                        logging.debug(f"Error downloading {url}: {error}")
                self.progress["completed"] += 1

        self.zip_bytes.seek(0)
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
        "trackpoints": [{"lat": lat, "lon": lon} for lat, lon in trackpoints],
        "coursepoints": [
            {"lat": lat, "lon": lon, "label": notes or name}
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
    def event_stream():
        last_sent = (-1, -1)
        while True:
            done = zm.progress["completed"]
            total = zm.progress["total"]
            thread_alive = int(zm.thread.is_alive()) if zm.thread else 0

            if (done, total, thread_alive) != last_sent:
                yield f"data: {done}/{total}/{thread_alive}\n\n"
                last_sent = (done, total, thread_alive)
            else:
                yield ": keep-alive\n\n"
            time.sleep(0.5)

    return Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream',
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )

@app.route('/download_zip')
def download_zip():
    zm = app.config['zip_manager']
    return send_file(
        zm.zip_bytes,
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
