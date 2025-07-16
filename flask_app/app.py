from downloader import generate_tiles, request_tile
from flask import Flask, render_template, request, send_file, Response, jsonify, stream_with_context
from tcx2lzr import convert_file
from io import BytesIO
import io
import zipfile
import requests
import time
import logging
import threading

app = Flask(__name__)
progress_data = {"total": 0, "completed": 0}
zip_bytes = BytesIO()
zip_thread = threading.Thread()

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
    global zip_thread
    def build_zip(sw_lat, sw_lon, ne_lat, ne_lon):
        global zip_bytes, progress_data
        progress_data["completed"] = 0
        zip_bytes = BytesIO()
        tiles = generate_tiles(sw_lat, sw_lon, ne_lat, ne_lon)
        progress_data["total"] = len(tiles)+2
        progress_data["completed"] += 1

        with zipfile.ZipFile(zip_bytes, mode="w",
                             compression=zipfile.ZIP_DEFLATED) as zipf:
            for sw, ne in tiles:
                url = request_tile(sw, ne)
                if url:
                    try:
                        response = requests.get(url)
                        if response.status_code == 200:
                            filename = (
                                f"mf_{sw['lat']}_{sw['lon']}_"
                                f"{ne['lat']}_{ne['lon']}.lzm"
                            )
                            zipf.writestr(filename, response.content)
                    except Exception as error:
                        logging.debug(f"Error downloading {url}: {error}")
                progress_data["completed"] += 1

        zip_bytes.seek(0) 
        time.sleep(3) 
        progress_data["completed"] += 1

    sw_lat = float(request.form['sw_lat'])
    sw_lon = float(request.form['sw_lon'])
    ne_lat = float(request.form['ne_lat'])
    ne_lon = float(request.form['ne_lon'])

    zip_thread = threading.Thread(
        target=build_zip,
        args=(sw_lat, sw_lon, ne_lat, ne_lon),
        daemon=True
    )
    zip_thread.start()

    return "", 202


@app.route('/progress')
def progress():
    def event_stream():
        global progress_data, zip_thread

        last_sent = (-1, -1)
        while True:
            done = progress_data["completed"]
            total = progress_data["total"]
            thread = int(zip_thread.is_alive())

            # Send only when progress changes
            if (done, total, thread) != last_sent:
                yield f"data: {done}/{total}/{thread}\n\n"
                last_sent = (done, total, thread)
            else:
                # Send keep-alive to keep connection open
                yield ": keep-alive\n\n"

            time.sleep(0.5)

    response = Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream'
    )
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@app.route('/download_zip')
def download_zip():
    global zip_bytes
    bytesToSend = zip_bytes
    return send_file(
        bytesToSend,
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

    # Return the binary file
    return send_file(
        io.BytesIO(lzr_bytes),
        as_attachment=True,
        download_name=file.filename.replace(".tcx", ".lzr"),
        mimetype="application/octet-stream"
    )


if __name__ == '__main__':
    app.run(debug=True)
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
else: 
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.WARNING)
