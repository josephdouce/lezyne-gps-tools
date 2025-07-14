import math
import requests
import os

def generate_tiles(sw_lat, sw_lon, ne_lat, ne_lon):
    print(f"Generating tiles from SW=({sw_lat}, {sw_lon}) to NE=({ne_lat}, {ne_lon})")

    lat_step = 0.1
    lon_step = 0.2
    overlap = 0.01

    lat_start = math.floor(sw_lat / lat_step) * lat_step
    lat_end = math.ceil(ne_lat / lat_step) * lat_step
    lon_start = math.floor(sw_lon / lon_step) * lon_step
    lon_end = math.ceil(ne_lon / lon_step) * lon_step

    tiles = []
    lat = lat_start
    while lat < lat_end:
        lon = lon_start
        while lon < lon_end:
            tile_sw = {'lat': round(lat, 6), 'lon': round(lon, 6)}
            tile_ne = {
                'lat': round(lat + lat_step + overlap, 6),
                'lon': round(lon + lon_step + overlap, 6)
            }

            # Only include if tile intersects selected area
            if not (tile_ne['lat'] <= sw_lat or tile_sw['lat'] >= ne_lat or
                    tile_ne['lon'] <= sw_lon or tile_sw['lon'] >= ne_lon):
                tiles.append((tile_sw, tile_ne))
                print(f"Tile SW: {tile_sw}, NE: {tile_ne}")
            lon += lon_step
        lat += lat_step

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
    except Exception as e:
        print(f"❌ Error fetching tile {sw} to {ne}:", e)
    return None

def download_file(url, dest_folder):
    local_filename = url.split("/")[-1]
    dest_path = os.path.join(dest_folder, local_filename)
    print(f"⬇️ Downloading {url} to {dest_path}")
    r = requests.get(url, stream=True)
    with open(dest_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
