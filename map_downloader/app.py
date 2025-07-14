from flask import Flask, render_template, request
from downloader import generate_tiles, request_tile, download_file
import os

app = Flask(__name__)
SAVE_DIR = "mapfiles"

@app.route('/')
def index():
    logs = []
    if os.path.exists("status.log"):
        with open("status.log", "r") as f:
            logs = f.readlines()
    return render_template("index.html", logs=logs)

@app.route('/download', methods=['POST'])
def download():
    sw_lat = float(request.form['sw_lat'])
    sw_lon = float(request.form['sw_lon'])
    ne_lat = float(request.form['ne_lat'])
    ne_lon = float(request.form['ne_lon'])

    tiles = generate_tiles(sw_lat, sw_lon, ne_lat, ne_lon)
    os.makedirs(SAVE_DIR, exist_ok=True)

    with open("status.log", "w") as log:
        for idx, (sw, ne) in enumerate(tiles, 1):
            url = request_tile(sw, ne)
            status = ""
            if url:
                try:
                    download_file(url, SAVE_DIR)
                    status = f"Downloaded tile {idx}/{len(tiles)}: {url}"
                except Exception as e:
                    status = f"Error downloading tile {idx}/{len(tiles)}: {e}"
            else:
                status = f"Failed to retrieve URL for tile {idx}/{len(tiles)}"
            log.write(status + "\n")

    logs = []
    if os.path.exists("status.log"):
        with open("status.log", "r") as f:
            logs = f.readlines()
    return render_template("index.html", logs=logs)

@app.route('/downloaded_tiles')
def downloaded_tiles():
    import glob
    tiles = []
    pattern = os.path.join(SAVE_DIR, "*.lzm")
    for path in glob.glob(pattern):
        fname = os.path.basename(path)
        parts = fname.replace(".lzm", "").replace("mf_", "").split("_")
        if len(parts) == 4:
            try:
                sw_lat, sw_lon, ne_lat, ne_lon = map(float, parts)
                tiles.append({
                    "sw": {"lat": sw_lat, "lon": sw_lon},
                    "ne": {"lat": ne_lat, "lon": ne_lon}
                })
            except ValueError:
                continue
    return {"tiles": tiles}

if __name__ == '__main__':
    app.run(debug=True)
