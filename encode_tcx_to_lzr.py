# Lezyne schema
# Trackpoint 
# ??????
#
# CoursePoint 12 byte string plus description
# 0xFFFF lon 32bit littlendian signed char scaled by 19.3%
# 0xFFFF lat 32bit littlendian signed char scaled by 19.3%
# 0xFFFF type?
# 0xFFFF... string containing description

import struct
import codecs
import xml.etree.ElementTree as ET
import os
filePath = 'test1.tcx'
latLngScale = 1.1930464
byteArray = []
CRC_TABLE = [
    0x0000, 0xCC01, 0xD801, 0x1400,
    0xF001, 0x3C00, 0x2800, 0xE401,
    0xA001, 0x6C00, 0x7800, 0xB401,
    0x5000, 0x9C01, 0x8801, 0x4400
]

def zigzag_encode(n):
    return (n << 1) ^ (n >> 31)

def vlq_encode(value):
    """VLQ encode a ZigZag-encoded int."""
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

def encode_trackpoints(trackpoints):
    """Encode a list of (lat, lon) pairs into LZR binary format."""
    output = bytearray()

    # First point: full 8 bytes
    lat0 = int(trackpoints[0][0] * 100000)
    lon0 = int(trackpoints[0][1] * 100000)
    output += struct.pack("<i", lat0)
    output += struct.pack("<i", lon0)

    # Encode deltas
    last_lat = lat0
    last_lon = lon0
    for lat, lon in trackpoints[1:]:
        lat_i = int(lat * 100000)
        lon_i = int(lon * 100000)
        dlat = lat_i - last_lat
        dlon = lon_i - last_lon
        output += vlq_encode(zigzag_encode(dlat))
        output += vlq_encode(zigzag_encode(dlon))
        last_lat = lat_i
        last_lon = lon_i

    return output

def extract_trackpoints_from_tcx(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    ns = {"ns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}

    trackpoints = []
    for tp in root.findall(".//ns:Trackpoint", ns):
        lat = tp.find("ns:Position/ns:LatitudeDegrees", ns).text
        lon = tp.find("ns:Position/ns:LongitudeDegrees", ns).text
        if lat is not None and lon is not None:
            trackpoints.append((float(lat), float(lon)))
    return trackpoints

def extract_coursepoints_from_tcx(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    ns = {"ns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}

    coursepoints = []
    for tp in root.findall(".//ns:CoursePoint", ns):
        name = tp.find("ns:Name", ns).text or ""
        lat = float(tp.find("ns:Position/ns:LatitudeDegrees", ns).text)
        lon = float(tp.find("ns:Position/ns:LongitudeDegrees", ns).text)
        pointType = tp.find("ns:PointType", ns).text or ""
        notes = tp.find("ns:Notes", ns).text or ""
        if lat is not None and lon is not None:
            coursepoints.append((name,lat,lon,pointType,notes))
    return coursepoints

def get_crc16(data: bytes) -> int:
    crc = 0  # Start with CRC = 0

    for b in data:
        # Process lower nibble of byte
        tmp = CRC_TABLE[crc & 0xF]        # Lookup table using lower 4 bits of current CRC
        crc = (crc >> 4) & 0x0FFF          # Shift right by 4, mask to 12 bits
        crc ^= tmp ^ CRC_TABLE[b & 0x0F]   # XOR with CRC_TABLE[low nibble of data byte]

        # Process upper nibble of byte
        tmp = CRC_TABLE[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc ^= tmp ^ CRC_TABLE[(b >> 4) & 0x0F]  # CRC_TABLE[high nibble of data byte]

    return crc

# Test data (your byte array)
def lezyneLatLonToHex(lat):
    _n = int(float(lat)*10000000*latLngScale)
    _b = _n.to_bytes(4, byteorder='little', signed=True)
    _h = _b
    return _h

def zigzag_encode(n):
    return (n << 1) ^ (n >> 31)

def write_varint(value):
    """Encodes an integer into varint format (LEB128)"""
    output = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            output.append(byte | 0x80)
        else:
            output.append(byte)
            break
    return output

def encode_polyline(points):
    """
    Encodes a list of (lat, lon) tuples into binary format
    using ZigZag and Varint (similar to BinaryPolylineEncoder).
    """
    encoded = bytearray()

    # Scale factor
    scale = 100000

    # First point (absolute, little-endian 4-byte ints)
    first_lat = int(points[0][0] * scale)
    first_lon = int(points[0][1] * scale)
    print("Track Start:",first_lat/100000,first_lon/10000)
    encoded.extend(struct.pack('<i', first_lat))
    encoded.extend(struct.pack('<i', first_lon))

    prev_lat, prev_lon = first_lat, first_lon

    for lat, lon in points[1:]:
        curr_lat = int(lat * scale)
        curr_lon = int(lon * scale)
        d_lat = curr_lat - prev_lat
        d_lon = curr_lon - prev_lon
        encoded.extend(write_varint(zigzag_encode(d_lat)))
        encoded.extend(write_varint(zigzag_encode(d_lon)))
        prev_lat, prev_lon = curr_lat, curr_lon
        print("Track Point:",curr_lat/100000,curr_lon/100000)

    return encoded

typecodes = [
{'Value':0,'Name':'None'},
{'Value':1,'Name':'Start'},
{'Value':2,'Name':'StartRight'},
{'Value':3,'Name':'StartLeft'},
{'Value':4,'Name':'Destination'},
{'Value':5,'Name':'DestinationRight'},
{'Value':6,'Name':'DestinationLeft'},
{'Value':7,'Name':'Becomes'},
{'Value':8,'Name':'Continue'},
{'Value':9,'Name':'SlightRight'},
{'Value':10,'Name':'Right'},
{'Value':11,'Name':'SharpRight'},
{'Value':12,'Name':'UturnRight'},
{'Value':13,'Name':'UturnLeft'},
{'Value':14,'Name':'SharpLeft'},
{'Value':15,'Name':'Left'},
{'Value':16,'Name':'SlightLeft'},
{'Value':17,'Name':'RampStraight'},
{'Value':18,'Name':'RampRight'},
{'Value':19,'Name':'RampLeft'},
{'Value':20,'Name':'ExitRight'},
{'Value':21,'Name':'ExitLeft'},
{'Value':22,'Name':'StayStraight'},
{'Value':23,'Name':'StayRight'},
{'Value':24,'Name':'StayLeft'},
{'Value':25,'Name':'Merge'},
{'Value':26,'Name':'RoundaboutEnter'},
{'Value':27,'Name':'RoundaboutExit'},
{'Value':28,'Name':'FerryEnter'},
{'Value':29,'Name':'FerryExit'},
{'Value':30,'Name':'FullMap'},
{'Value':31,'Name':'LinkRoute'},
{'Value':50,'Name':'Generic'}]

coursepoints = extract_coursepoints_from_tcx(filePath)
trackpoints = extract_trackpoints_from_tcx(filePath)
polyline_path = encode_trackpoints(trackpoints)

print("Dest Lon:", trackpoints[0][1])
byteArray.append(lezyneLatLonToHex(trackpoints[0][1])) #dest lon
print("Dest Lat:", trackpoints[0][0])
byteArray.append(lezyneLatLonToHex(trackpoints[0][0]))  #dest lat
print("Device ID:","H")
byteArray.append(bytes("H",'utf-8'))   #deviceid
print("Route Trimmed:",int(1))
byteArray.append(int(1).to_bytes(1,'little'))   #trimmedroute????
print("Polyline Bytes Length:",int(len(polyline_path)/2))
byteArray.append(len(polyline_path).to_bytes(2,'little'))   #encoded polylines length
print("Course Points:",len(coursepoints))
byteArray.append(len(coursepoints).to_bytes(2,'little'))    #coursepoints length
print("Re Route:",int(0))
byteArray.append(int(0).to_bytes(1,'little'))   #re route????
byteArray.append(polyline_path) #encoded polyline

for trackpoint in trackpoints:
    print("Trackpoint",trackpoint[0],trackpoint[1])


i=1
for coursepoint in coursepoints:
    #each cours points contains 12 bytes followed by the name, lon(4) lat(4) polyline(2) type(1) namelength(1, max 16 chars) name(variable)
    _name = coursepoint[0]
    _lat = coursepoint[1]
    _lon = coursepoint[2]
    _type = coursepoint[3]
    _notes = coursepoint[4]
    print("CoursePoint",_lat,_lon,_type,_name,_notes)
    byteArray.append(lezyneLatLonToHex(_lon)) #lon
    byteArray.append(lezyneLatLonToHex(_lat)) #lat
    byteArray.append(int(i).to_bytes(2,'little')) # which polyline
    i+=1
    byteArray.append(int(next((item for item in typecodes if item.get("Value") and item["Name"] == _type), None)['Value']).to_bytes(1,'little')) #type code
    byteArray.append(int(len(_notes)).to_bytes(1,'little')) #name length
    byteArray.append(bytes(_notes,"utf-8")) #name

byteArray = b''.join(bytes(item) for item in byteArray)
byteArrayForChecksum = bytearray(byteArray)

lengthOfFile = len(byteArray)
print("File Length:",lengthOfFile)
byteArray += lengthOfFile.to_bytes(2,'little') # file length

checksum = get_crc16(bytes(bytearray(byteArrayForChecksum)))
print("Checksum:",checksum)
byteArray += checksum.to_bytes(2,'little') # checksum

with open("route.lzr", "wb") as outFile:
        outFile.write(byteArray)
outFile.close()


