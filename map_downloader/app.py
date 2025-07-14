
from flask import Flask, render_template, request, send_file, Response
from downloader import generate_tiles, request_tile
from io import BytesIO
import zipfile
import requests
import threading
import time

app = Flask(__name__)
progress_data = {"total": 0, "completed": 0}
zip_bytes = BytesIO()

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/download', methods=['POST'])
def download():
    def build_zip(sw_lat, sw_lon, ne_lat, ne_lon):
        global zip_bytes, progress_data
        zip_bytes = BytesIO()
        tiles = generate_tiles(sw_lat, sw_lon, ne_lat, ne_lon)
        progress_data["total"] = len(tiles)
        progress_data["completed"] = 0
        with zipfile.ZipFile(zip_bytes, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
            for idx, (sw, ne) in enumerate(tiles):
                url = request_tile(sw, ne)
                if url:
                    try:
                        r = requests.get(url)
                        if r.status_code == 200:
                            filename = f"mf_{sw['lat']}_{sw['lon']}_{ne['lat']}_{ne['lon']}.lzm"
                            zipf.writestr(filename, r.content)
                    except Exception as e:
                        print(f"Error downloading {url}: {e}")
                progress_data["completed"] += 1
        zip_bytes.seek(0)

    sw_lat = float(request.form['sw_lat'])
    sw_lon = float(request.form['sw_lon'])
    ne_lat = float(request.form['ne_lat'])
    ne_lon = float(request.form['ne_lon'])

    threading.Thread(target=build_zip, args=(sw_lat, sw_lon, ne_lat, ne_lon)).start()
    return "started"

@app.route('/progress')
def progress():
    def event_stream():
        while True:
            yield f"data: {progress_data['completed']}/{progress_data['total']}\n\n"
            if progress_data["completed"] >= progress_data["total"]:
                break
            time.sleep(0.5)
    return Response(event_stream(), mimetype="text/event-stream")

@app.route('/download_zip')
def download_zip():
    global zip_bytes
    return send_file(zip_bytes, mimetype='application/zip',
                     as_attachment=True, download_name='downloaded_tiles.zip')
