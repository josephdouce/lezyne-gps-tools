from pathlib import Path
import struct
import codecs

# Load the binary file
file_path = Path("./test.lzr")
data = file_path.read_bytes()

# Constants
record_length = 4 + 4 + 4  # lon(4) + lat(4) + unknown(4)
entries = []

typecodes = [{'Value':1,'Name':'Start'},
{'Value':8,'Name':'Continue'},
{'Value':9,'Name':'Slight Right'},
{'Value':10,'Name':'Right'},
{'Value':11,'Name':'Sharp Right'},
{'Value':14,'Name':'Sharp Left'},
{'Value':15,'Name':'Left'},
{'Value':16,'Name':'Slight Left'},
{'Value':18,'Name':'Ramp Right'},
{'Value':19,'Name':'Ramp Left'},
{'Value':25,'Name':'Merge'},
{'Value':26,'Name':'Roundabout Enter'},
{'Value':27,'Name':'Roundabout Exit'},
{'Value':28,'Name':'Ferry Enter'},
{'Value':29,'Name':'Ferry Exit'},
{'Value':4,'Name':'Destination'},
{'Value':50,'Name':'Ride Note'}]

def slashescape(err):
    """ codecs error handler. err is UnicodeDecode instance. return
    a tuple with a replacement for the unencodable part of the input
    and a position where encoding should continue"""
    #print err, dir(err), err.start, err.end, err.object[:err.start]
    thebyte = err.object[err.start:err.end]
    repl = u'\\x'+hex(ord(thebyte))[2:]
    return (repl, err.end)

codecs.register_error('slashescape', slashescape)

def lezyneHexToLatLon(hex):
    _b = hex
    _signedNumber = round(int.from_bytes(_b, byteorder='little', signed=True)/10000000/1.19304653471,5)
    return _signedNumber

i = 0
while i < len(data) - record_length:
    try:
        # Read 4 bytes each for lon and lat (little-endian, signed int)
        lon_bytes = data[i:i+4]
        lat_bytes = data[i+4:i+8]
        unknown_byte1 = data[i+8]
        unknown_byte2 = data[i+9]
        unknown_byte3 = data[i+10]
        unknown_byte4 = data[i+11]
        
        lon = lezyneHexToLatLon(lon_bytes)
        lat = lezyneHexToLatLon(lat_bytes)
        
        # Scan for ASCII string right after the 12-byte block
        ascii_phrase = []
        j = i + 12
        while j < len(data) and 32 <= data[j] <= 122 and 50 <= lat <= 60 and -5 <= lon <= 0:
            ascii_phrase.append(chr(data[j]))
            j += 1
        phrase = ''.join(ascii_phrase)

        # Only consider as valid if there's a non-empty phrase
        if len(phrase) > 4:
            entries.append({
                "Latitude": round(lat, 6),
                "Longitude": round(lon, 6),
                "Type": next((item for item in typecodes if item.get("Name") and item["Value"] == unknown_byte3), None)['Name'],
                "Phrase": phrase,
                "End": i
            })
            i = j  # Move past the ASCII string
        else:
            i += 1  # Move one byte forward and try again
    except Exception:
        i += 1  # Skip malformed record

for item in entries:
    print(item)# Show first 5 entries for review

i=6
start_lon = lezyneHexToLatLon(data[0:4])
start_lat = lezyneHexToLatLon(data[4:8])
new_lon = start_lon
new_lat = start_lat
print("startLonLat:",start_lon, start_lat)
while i < 124:
    offset_lon = -int.from_bytes(data[i:i+1], byteorder='little', signed=True)
    offset_lat = -int.from_bytes(data[i+1:i+2], byteorder='little', signed=True)
    new_lon = start_lon  + offset_lon
    new_lat = start_lat  + offset_lat
    #print("newLonLat:",round(new_lon,4),round(new_lat,4),"lonLatOffset:",offset_lon,offset_lat)
    print(f'{offset_lon:.8f}',f'{offset_lat:.8f}') 
    i += 2
    
