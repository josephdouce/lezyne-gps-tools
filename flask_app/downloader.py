import os
import requests

LAT_STEP = 0.1
LON_STEP = 0.2
OVERLAP = 0.01

def generate_tiles(sw_lat, sw_lon, ne_lat, ne_lon):
    print(f"Generating tiles from SW=({sw_lat}, {sw_lon}) to NE=({ne_lat}, {ne_lon})")

    tiles = []
    lat = sw_lat
    while lat < ne_lat:
        lon = sw_lon
        while lon < ne_lon:
            tile_sw = {'lat': round(lat, 6), 'lon': round(lon, 6)}
            tile_ne = {
                'lat': round(lat + LAT_STEP + OVERLAP, 6),
                'lon': round(lon + LON_STEP + OVERLAP, 6)
            }

            if not (
                tile_ne['lat'] <= sw_lat or tile_sw['lat'] >= ne_lat or
                tile_ne['lon'] <= sw_lon or tile_sw['lon'] >= ne_lon
            ):
                tiles.append((tile_sw, tile_ne))
                print(f"Tile SW: {tile_sw}, NE: {tile_ne}")

            lon += LON_STEP
        lat += LAT_STEP

    print(f"Total tiles generated: {len(tiles)}")
    return tiles


def request_tile(sw, ne):
    url = "https://www.gpsroot.com/generate_lzm/get/"
    payload = {
        "sw_gps_lat": f"{sw['lat']:.2f}",
        "sw_gps_lon": f"{sw['lon']:.2f}",
        "ne_gps_lat": f"{ne['lat']:.2f}",
        "ne_gps_lon": f"{ne['lon']:.2f}"
    }

    print(f"Requesting tile: {payload}")
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        if data.get("APIResultMessage") == "Success":
            print(f"✅ Success: {data.get('mf_url')}")
            return data.get("mf_url")
        else:
            print("❌ API failed:", data)
    except Exception as error:
        print(f"❌ Error fetching tile {sw} to {ne}:", error)
    return None


def download_file(url, dest_folder):
    local_filename = url.split("/")[-1]
    dest_path = os.path.join(dest_folder, local_filename)
    print(f"⬇️ Downloading {url} to {dest_path}")
    response = requests.get(url, stream=True)
    with open(dest_path, 'wb') as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)