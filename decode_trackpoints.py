import struct

def zigzag_decode(n):
    return (n >> 1) ^ -(n & 1)

def decode_vlq(data):
    """Decode bytes using VLQ+ZigZag."""
    results = []
    value = 0
    shift = 0
    for b in data:
        value |= (b & 0x7F) << shift
        if b & 0x80:
            shift += 7
        else:
            results.append(zigzag_decode(value))
            value = 0
            shift = 0
    return results

def decode_trackpoints(filepath):
    with open(filepath, "rb") as f:
        content = f.read()

    # Extract start lat/lon from first 8 bytes
    start_lat = struct.unpack("<i", content[0:4])[0] / 100000.0
    start_lon = struct.unpack("<i", content[4:8])[0] / 100000.0

    print(f"Start Point: lat = {start_lat}, lon = {start_lon}")

    # Decode the remaining bytes as VLQ+ZigZag deltas
    deltas = decode_vlq(content[8:])

    # Apply deltas cumulatively
    lat = int(start_lat * 100000)
    lon = int(start_lon * 100000)
    track = [(start_lat, start_lon)]

    for i in range(0, len(deltas), 2):
        lat += deltas[i]
        lon += deltas[i + 1]
        track.append((lat / 100000.0, lon / 100000.0))

    return track

if __name__ == "__main__":
    import sys
    import os

    if len(sys.argv) != 2:
        print("Usage: python decode_lzr.py <path_to_lzr_file>")
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.isfile(path):
        print("File not found:", path)
        sys.exit(1)

    decoded_points = decode_lzr(path)
    for i, (lat, lon) in enumerate(decoded_points):
        print(f"{i+1}: {lat:.5f}, {lon:.5f}")
