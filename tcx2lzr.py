import struct
import xml.etree.ElementTree as ET

latLngScale = 1.1930464
CRC_TABLE = [
  0x0000, 0xCC01, 0xD801, 0x1400,
  0xF001, 0x3C00, 0x2800, 0xE401,
  0xA001, 0x6C00, 0x7800, 0xB401,
  0x5000, 0x9C01, 0x8801, 0x4400
]

typecodes = [{"Value":i,"Name":n} for i,n in enumerate([
  'None','Start','StartRight','StartLeft','Destination','DestinationRight','DestinationLeft',
  'Becomes','Continue','SlightRight','Right','SharpRight','UturnRight','UturnLeft',
  'SharpLeft','Left','SlightLeft','RampStraight','RampRight','RampLeft','ExitRight',
  'ExitLeft','StayStraight','StayRight','StayLeft','Merge','RoundaboutEnter',
  'RoundaboutExit','FerryEnter','FerryExit','FullMap','LinkRoute'])] + [{"Value":50,"Name":"Generic"}]

def zigzag_encode(n): return (n << 1) ^ (n >> 31)

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

def lezyneLatLonToHex(lat):
    _n = int(float(lat)*10000000*latLngScale)
    return _n.to_bytes(4, byteorder='little', signed=True)

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

def encode_trackpoints(trackpoints):
    output = bytearray()
    lat0 = int(trackpoints[0][0] * 100000)
    lon0 = int(trackpoints[0][1] * 100000)
    output += struct.pack("<i", lat0)
    output += struct.pack("<i", lon0)
    last_lat, last_lon = lat0, lon0
    for lat, lon in trackpoints[1:]:
        lat_i = int(lat * 100000)
        lon_i = int(lon * 100000)
        output += write_varint(zigzag_encode(lat_i - last_lat))
        output += write_varint(zigzag_encode(lon_i - last_lon))
        last_lat, last_lon = lat_i, lon_i
    return output

def parse_tcx(xml_str):
    ns = {"ns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}
    root = ET.fromstring(xml_str)
    trackpoints = []
    for tp in root.findall(".//ns:Trackpoint", ns):
        lat = tp.find("ns:Position/ns:LatitudeDegrees", ns)
        lon = tp.find("ns:Position/ns:LongitudeDegrees", ns)
        if lat is not None and lon is not None:
            trackpoints.append((float(lat.text), float(lon.text)))
    coursepoints = []
    for cp in root.findall(".//ns:CoursePoint", ns):
        name = cp.find("ns:Name", ns).text or ""
        lat = float(cp.find("ns:Position/ns:LatitudeDegrees", ns).text)
        lon = float(cp.find("ns:Position/ns:LongitudeDegrees", ns).text)
        pointType = cp.find("ns:PointType", ns).text or ""
        notes = cp.find("ns:Notes", ns).text or ""
        coursepoints.append((name, lat, lon, pointType, notes))
    return trackpoints, coursepoints

def convert_file(input_bytes):
    xml = input_bytes.decode("utf-8")
    trackpoints, coursepoints = parse_tcx(xml)
    polyline = encode_trackpoints(trackpoints)
    byteArray = []
    byteArray.append(lezyneLatLonToHex(trackpoints[0][1]))
    byteArray.append(lezyneLatLonToHex(trackpoints[0][0]))
    byteArray.append(b"H")
    byteArray.append((1).to_bytes(1,'little'))
    byteArray.append(len(polyline).to_bytes(2,'little'))
    byteArray.append(len(coursepoints).to_bytes(2,'little'))
    byteArray.append((0).to_bytes(1,'little'))
    byteArray.append(polyline)
    i = 1
    for name, lat, lon, pointType, notes in coursepoints:
        byteArray.append(lezyneLatLonToHex(lon))
        byteArray.append(lezyneLatLonToHex(lat))
        byteArray.append((i).to_bytes(2, 'little'))
        i += 1
        typeval = next((t["Value"] for t in typecodes if t["Name"] == pointType), 50)
        byteArray.append((typeval).to_bytes(1, 'little'))
        byteArray.append((len(notes)).to_bytes(1, 'little'))
        byteArray.append(notes.encode("utf-8"))
    data = b''.join(byteArray)
    data += len(data).to_bytes(2, 'little')
    data += get_crc16(data).to_bytes(2, 'little')
    return data