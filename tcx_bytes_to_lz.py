import struct
import xml.etree.ElementTree as ET
from io import BytesIO

latLngScale = 1.1930464

CRC_TABLE = [
    0x0000, 0xCC01, 0xD801, 0x1400,
    0xF001, 0x3C00, 0x2800, 0xE401,
    0xA001, 0x6C00, 0x7800, 0xB401,
    0x5000, 0x9C01, 0x8801, 0x4400
]

typecodes = {
    'None': 0, 'Start': 1, 'StartRight': 2, 'StartLeft': 3, 'Destination': 4, 'DestinationRight': 5, 'DestinationLeft': 6,
    'Becomes': 7, 'Continue': 8, 'SlightRight': 9, 'Right': 10, 'SharpRight': 11, 'UturnRight': 12, 'UturnLeft': 13,
    'SharpLeft': 14, 'Left': 15, 'SlightLeft': 16, 'RampStraight': 17, 'RampRight': 18, 'RampLeft': 19, 'ExitRight': 20,
    'ExitLeft': 21, 'StayStraight': 22, 'StayRight': 23, 'StayLeft': 24, 'Merge': 25, 'RoundaboutEnter': 26,
    'RoundaboutExit': 27, 'FerryEnter': 28, 'FerryExit': 29, 'FullMap': 30, 'LinkRoute': 31, 'Generic': 50
}

def zigzag_encode(n):
    return (n << 1) ^ (n >> 31)

def write_varint(value):
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
    scaled = int(coord * 1e7 * latLngScale)
    return scaled.to_bytes(4, byteorder="little", signed=True)

def extract_trackpoints(xml):
    root = ET.fromstring(xml)
    ns = {"ns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}
    points = []
    for tp in root.findall(".//ns:Trackpoint", ns):
        lat = tp.find("ns:Position/ns:LatitudeDegrees", ns)
        lon = tp.find("ns:Position/ns:LongitudeDegrees", ns)
        if lat is not None and lon is not None:
            points.append((float(lat.text), float(lon.text)))
    return points

def extract_coursepoints(xml):
    root = ET.fromstring(xml)
    ns = {"ns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}
    points = []
    for cp in root.findall(".//ns:CoursePoint", ns):
        name = cp.find("ns:Name", ns)
        lat = cp.find("ns:Position/ns:LatitudeDegrees", ns)
        lon = cp.find("ns:Position/ns:LongitudeDegrees", ns)
        typ = cp.find("ns:PointType", ns)
        notes = cp.find("ns:Notes", ns)
        if lat is not None and lon is not None:
            points.append((
                name.text if name is not None else "",
                float(lat.text),
                float(lon.text),
                typ.text if typ is not None else "None",
                notes.text if notes is not None else ""
            ))
    return points

def encode_polyline(points):
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
    xml = bytes(input_bytes).decode("utf-8")
    trackpoints = extract_trackpoints(xml)
    coursepoints = extract_coursepoints(xml)
    polyline = encode_polyline(trackpoints)

    byte_array = bytearray()
    byte_array += lezyne_lat_lon_to_bytes(trackpoints[0][1])  # dest lon
    byte_array += lezyne_lat_lon_to_bytes(trackpoints[0][0])  # dest lat
    byte_array += b"H"  # device id
    byte_array += (1).to_bytes(1, 'little')  # trimmed route
    byte_array += len(polyline).to_bytes(2, 'little')  # polyline length
    byte_array += len(coursepoints).to_bytes(2, 'little')  # coursepoint count
    byte_array += (0).to_bytes(1, 'little')  # reroute
    byte_array += polyline

    for i, (name, lat, lon, typ, notes) in enumerate(coursepoints, start=1):
        byte_array += lezyne_lat_lon_to_bytes(lon)
        byte_array += lezyne_lat_lon_to_bytes(lat)
        byte_array += i.to_bytes(2, 'little')
        byte_array += typecodes.get(typ, 0).to_bytes(1, 'little')
        name_bytes = notes.encode("utf-8")[:16]
        byte_array += len(name_bytes).to_bytes(1, 'little')
        byte_array += name_bytes

    data_for_crc = byte_array[:]
    byte_array += len(byte_array).to_bytes(2, 'little')  # file length
    checksum = get_crc16(data_for_crc)
    byte_array += checksum.to_bytes(2, 'little')

    return byte_array
