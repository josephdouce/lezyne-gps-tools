"""
Lezyne .lzr Route File Format (Custom Reverse-Engineered Structure)

STRUCTURE OVERVIEW:
──────────────────────────────────────────────────────────────────────────────
| Offset | Length | Field                          | Notes                    |
|--------|--------|---------------------------------|-------------------------|
| 0x00   | 4      | Destination Longitude (int32)   | Lezyne scaled coord     |
| 0x04   | 4      | Destination Latitude (int32)    | Lezyne scaled coord     |
| 0x08   | 1      | Device ID                       | Static, usually "H"     |
| 0x09   | 1      | Route Trimmed Flag              | 1 = yes, 0 = no         |
| 0x0A   | 2      | Encoded Polyline Length (uint16)| Bytes following         |
| 0x0C   | 2      | CoursePoint Count (uint16)      | Number of points        |
| 0x0E   | 1      | Re-Route Flag                   | 1 = reroute section     |
| ...    | var    | Encoded Polyline                | Binary polyline data    |
| ...    | var    | CoursePoints                    | See below               |
| ...    | 2      | Total File Length (uint16)      | Excludes CRC            |
| ...    | 2      | CRC-16                          | Lezyne-specific         |

OPTIONAL RE-ROUTE SECTION (Only if Re-Route Flag == 1):
──────────────────────────────────────────────────────────────────────────────
| Field                         | Length | Type   | Notes                       |
|------------------------------|--------|--------|------------------------------|
| Static Identifier Text       | 7      | bytes  | b"route  "                   |
| Distance After Trim          | 4      | int32  | Units unknown (placeholder)  |
| Linked Route Polyline Count  | 2      | uint16 | Placeholder for segment count|

COURSEPOINT STRUCTURE (Repeated N times):
──────────────────────────────────────────────────────────────────────────────
| Field               | Length | Type     | Notes                             |
|---------------------|--------|----------|-----------------------------------|
| Longitude           | 4      | int32    | Lezyne scaled                     |
| Latitude            | 4      | int32    | Lezyne scaled                     |
| Polyline Index      | 2      | uint16   | Ordinal number of point           |
| Type                | 1      | uint8    | Based on predefined TYPE_CODES     |
| Name Length         | 1      | uint8    | Length of Notes string (max 16)   |
| Name/Notes Text     | var    | bytes    | UTF-8 encoded Notes string        |

"""

import struct
import logging
import xml.etree.ElementTree as ET
from geopy.distance import geodesic


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.WARNING)

# Coordinate scaling constant specific to Lezyne format
LAT_LNG_SCALE = 1.1930464

TRACKPOINT_COURSEPOINT_THRESHOLD = 2

# CRC-16 lookup table
CRC_TABLE = [
    0x0000, 0xCC01, 0xD801, 0x1400,
    0xF001, 0x3C00, 0x2800, 0xE401,
    0xA001, 0x6C00, 0x7800, 0xB401,
    0x5000, 0x9C01, 0x8801, 0x4400
]

# Mapping of coursepoint types to numeric codes
TYPE_CODES = {
    'None': 0, 'Start': 1, 'StartRight': 2, 'StartLeft': 3, 'Destination': 4, 'DestinationRight': 5, 'DestinationLeft': 6,
    'Becomes': 7, 'Continue': 8, 'SlightRight': 9, 'Right': 10, 'SharpRight': 11, 'UturnRight': 12, 'UturnLeft': 13,
    'SharpLeft': 14, 'Left': 15, 'SlightLeft': 16, 'RampStraight': 17, 'RampRight': 18, 'RampLeft': 19, 'ExitRight': 20,
    'ExitLeft': 21, 'StayStraight': 22, 'StayRight': 23, 'StayLeft': 24, 'Merge': 25, 'RoundaboutEnter': 26,
    'RoundaboutExit': 27, 'FerryEnter': 28, 'FerryExit': 29, 'FullMap': 30, 'LinkRoute': 31, 'Generic': 50
}

# GPS route providers
ROUTE_PROVIDERS = [
    ('gpsRoot_providerA', 1, 'A'),
    ('gpsRoot_providerB', 2, 'B'),
    ('gpsRoot_providerC', 3, 'C'),
    ('gpsRoot_providerD', 4, 'D'),
    ('MountainBike', 5, 'E'),
    ('RoadBike', 6, 'F'),
    ('EazyRide', 7, 'G'),
    ('Shortest', 8, 'H'),
    ('Hiking', 9, 'I'),
    ('Commuter', 10, 'J'),
    ('Custom', 11, 'K')
]


def zigzag_encode(n):
    return (n << 1) ^ (n >> 31)


def write_varint(value):
    # Encode integer using protobuf-style varint
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            break
    return out


def lezyne_lat_lon_to_bytes(coord):
    # Convert latitude or longitude to 4-byte Lezyne-specific scaled format
    scaled = int(coord * 1e7 * LAT_LNG_SCALE)
    return scaled.to_bytes(4, byteorder="little", signed=True)


def extract_trackpoints_coursepoints(xml):
    # Parse and extract all GPS trackpoints from TCX
    root = ET.fromstring(xml)
    ns = {"ns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}
    trackpoints = []

    for tp in root.findall(".//ns:Trackpoint", ns):
        lat = tp.find("ns:Position/ns:LatitudeDegrees",
                      ns)  # Find latitude element
        lon = tp.find("ns:Position/ns:LongitudeDegrees",
                      ns)  # Find longitude element

        if lat is not None and lon is not None:
            lat_val = float(lat.text)
            lon_val = float(lon.text)
            # Add tuple (lat, lon) to list
            trackpoints.append((lat_val, lon_val))
            logging.debug(f"[Trackpoint] Lat: {lat.text}, Lon: {lon.text}")

    logging.debug(
        # Summary
        f"[Trackpoint] Total: {len(trackpoints)} trackpoints extracted.")

    # Parse and extract coursepoints (turn instructions, waypoints, etc.)
    coursepoints = []

    last_trackpoint = 0
    for cp in root.findall(".//ns:CoursePoint", ns):

        trackpoint = 0
        name = cp.find("ns:Name", ns)
        lat = cp.find("ns:Position/ns:LatitudeDegrees", ns)
        lon = cp.find("ns:Position/ns:LongitudeDegrees", ns)
        typ = cp.find("ns:PointType", ns)
        notes = cp.find("ns:Notes", ns)

        # Use empty string if the tag is missing or the text is None
        name_text = name.text.strip() if name is not None and name.text else ""
        typ_text = typ.text.strip() if typ is not None and typ.text else ""
        notes_text = notes.text.strip() if notes is not None and notes.text else ""
        lat_val = float(lat.text)
        lon_val = float(lon.text)

        for idx, tp in enumerate(trackpoints[last_trackpoint:]):
            dist = geodesic((lat_val, lon_val), tp).meters
            if dist <= TRACKPOINT_COURSEPOINT_THRESHOLD:
                logging.debug(
                    f"[Matched Trackpoint] [{last_trackpoint + idx}] Dist: {dist}")
                last_trackpoint += idx
                trackpoint = last_trackpoint
                break

        if lat is not None and lon is not None:
            point_data = (
                name_text,
                lat_val,
                lon_val,
                typ_text,
                notes_text,
                trackpoint
            )
            coursepoints.append(point_data)

    return trackpoints, coursepoints


def encode_polyline(points):
    # Encode trackpoints as compressed polyline (protobuf-style)
    encoded = bytearray()
    scale = 100000
    lat0 = int(points[0][0] * scale)
    lon0 = int(points[0][1] * scale)
    encoded.extend(struct.pack('<i', lat0))
    encoded.extend(struct.pack('<i', lon0))
    last_lat, last_lon = lat0, lon0

    for lat, lon in points[1:]:
        ilat = int(lat * scale)
        ilon = int(lon * scale)
        dlat = ilat - last_lat
        dlon = ilon - last_lon
        encoded.extend(write_varint(zigzag_encode(dlat)))
        encoded.extend(write_varint(zigzag_encode(dlon)))
        last_lat, last_lon = ilat, ilon

    return encoded


def get_crc16(data: bytes) -> int:
    # Compute CRC-16 checksum using Lezyne-specific table
    crc = 0
    for b in data:
        tmp = CRC_TABLE[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc ^= tmp ^ CRC_TABLE[b & 0x0F]
        tmp = CRC_TABLE[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc ^= tmp ^ CRC_TABLE[(b >> 4) & 0x0F]
    return crc


def convert_file(input_bytes):
    # Decode and parse the input TCX XML, then convert to .lzr format
    xml = bytes(input_bytes).decode("utf-8")
    trackpoints, coursepoints = extract_trackpoints_coursepoints(xml)
    polyline = encode_polyline(trackpoints)  # Encode trackpoints
    byte_array = bytearray()

    # Add route header (destination coords, flags)
    # Convert destination longitude to bytes
    dest_lon_bytes = lezyne_lat_lon_to_bytes(trackpoints[0][1])
    logging.debug(f"[Header] Destination Longitude: {trackpoints[0][1]}")
    byte_array += dest_lon_bytes  # Add destination longitude

    # Convert destination latitude to bytes
    dest_lat_bytes = lezyne_lat_lon_to_bytes(trackpoints[0][0])
    logging.debug(f"[Header] Destination Latitude: {trackpoints[0][0]}")
    byte_array += dest_lat_bytes  # Add destination latitude

    route_provider = ROUTE_PROVIDERS[5][2]  # Route provider
    logging.debug(f"[Header] Device ID: {route_provider}")
    byte_array += bytes(route_provider, 'utf-8')  # Route provider

    trimmed_flag = (1).to_bytes(1, 'little')  # Route trimmed flag (1 = yes)
    logging.debug(f"[Header] Trimmed Route Flag: 1")
    byte_array += trimmed_flag  # Add trimmed flag

    polyline_len_bytes = len(polyline).to_bytes(
        2, 'little')  # Length of encoded polyline
    logging.debug(f"[Header] Polyline Byte Length: {len(polyline)}")
    byte_array += polyline_len_bytes  # Add polyline length

    coursepoint_count_bytes = len(coursepoints).to_bytes(
        2, 'little')  # Total number of coursepoints
    logging.debug(f"[Header] Number of Coursepoints: {len(coursepoints)}")
    byte_array += coursepoint_count_bytes  # Add coursepoint count

    reroute_flag = (0).to_bytes(1, 'little')  # Reroute flag (0 = no)
    logging.debug(f"[Header] Reroute Flag: 0")
    byte_array += reroute_flag  # Add reroute flag

    byte_array += polyline  # Append encoded polyline data

    # Append each coursepoint as a structured binary block
    for (name, lat, lon, typ, notes, trackpoint) in coursepoints:
        byte_array += lezyne_lat_lon_to_bytes(lon)  # Coursepoint longitude
        byte_array += lezyne_lat_lon_to_bytes(lat)  # Coursepoint latitude
        byte_array += int(trackpoint).to_bytes(2,
                                               'little')  # Coursepoint index
        byte_array += TYPE_CODES.get(typ, 0).to_bytes(1, 'little')  # Turn type
        notes_bytes = bytes(notes, "utf-8")
        notes_len = len(notes_bytes)
        byte_array += notes_len.to_bytes(1, 'little')  # Length of notes
        byte_array += notes_bytes  # Notes (used as label)
        logging.debug(f"[Coursepoint] Name: {name}, Lat: {lat}, Lon: {lon}, "
                      f"Type: {typ}, Notes: {notes} Trackpoint: {trackpoint} Length: {notes_len}")

    # Compute CRC and total file length
    data_for_crc = byte_array[:]
    byte_array += len(byte_array).to_bytes(2, 'little')  # Total file length
    checksum = get_crc16(data_for_crc)
    byte_array += checksum.to_bytes(2, 'little')  # CRC16 checksum

    return byte_array, trackpoints, coursepoints
