# Lezyne schema
# Trackpoint 
# ??????
#
# CoursePoint 12 byte string plus description
# 0xFFFF lon 32bit littlendian signed char scaled by 19.3%
# 0xFFFF lat 32bit littlendian signed char scaled by 19.3%
# 0xFFFF type?
# 0xFFFF... string containing description 

import codecs
import xml.etree.ElementTree as ET

def lezyneLatLonToHex(lat):
    _n = int(float(lat)*10000000*1.193)
    _b = _n.to_bytes(4, byteorder='little', signed=True)
    _h = codecs.encode(_b, 'hex')
    return _h

def lezyneHexToLatLon(hex):
    _b = bytes.fromhex(hex.decode())
    _signedNumber = round(int.from_bytes(_b, byteorder='little', signed=True)/10000000/1.19304653471,5)
    return _signedNumber

tree=ET.parse('test.tcx')
root=tree.getroot()
ns = {'garmin':'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'}

for coursepoint in root.findall('./garmin:Courses/garmin:Course/garmin:CoursePoint', ns):
    _notes = coursepoint.find('garmin:Notes', ns).text
    _position = coursepoint.find('garmin:Position', ns)
    _lat = _position.find('garmin:LatitudeDegrees', ns).text
    _lon = _position.find('garmin:LongitudeDegrees', ns).text
    _type = coursepoint.find('garmin:PointType', ns).text
    print("CoursePoint", _lat,_lon, _type,_notes)
    print("CoursePoint", lezyneLatLonToHex(_lon).decode(),lezyneLatLonToHex(_lat).decode(),"ffff",_notes.encode("utf-8").hex())
    #print(lezyneHexToLatLon(lezyneLatLonToHex(_lon)),lezyneHexToLatLon(lezyneLatLonToHex(_lat)))

for trackpoint in root.findall('./garmin:Courses/garmin:Course/garmin:Track/garmin:Trackpoint', ns):
    _position = trackpoint.find('garmin:Position', ns)
    _lat = _position.find('garmin:LatitudeDegrees', ns).text
    _lon = _position.find('garmin:LongitudeDegrees', ns).text
    print("Trackpoint", _lat,_lon)
    print("Trackpoint",lezyneLatLonToHex(_lon).decode(),lezyneLatLonToHex(_lat).decode())
