"""
Polyline Encoder Service

This service handles the binary encoding of geographic coordinates into the compressed
polyline format used by LZM files. It implements varint encoding and delta compression
for efficient storage of coordinate sequences.
"""

import struct
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from lzm_builder import Coordinate

from lzm_utils import round_away_from_zero


class PolylineEncoder:
    """
    Service class for encoding coordinates into compressed polyline format.
    
    This encoder converts geographic coordinates into a binary format optimized
    for LZM files, using delta compression and varint encoding to minimize
    storage requirements while maintaining precision.
    """
    
    def __init__(self, buffer: bytearray, base: Optional['Coordinate'] = None):
        """
        Initialize the polyline encoder service.
        
        Args:
            buffer: Byte array buffer to write encoded data to
            base: Optional base coordinate for delta encoding
        """
        self.buf = buffer
        self.cur = 0
        self.lastLatInit = False
        self.lastLonInit = False
        self.lastLat = 0
        self.lastLon = 0
        
        if base is not None:
            self.lastLat = round_away_from_zero(base.lat * 1e5)
            self.lastLon = round_away_from_zero(base.lon * 1e5)
            self.lastLatInit = True
            self.lastLonInit = True

    def _add_part(self, ll: int):
        """
        Add a single coordinate part to the buffer using varint encoding.
        
        Implements variable-length integer encoding to compress coordinate deltas.
        The first two coordinates are stored as absolute 32-bit integers,
        subsequent coordinates are stored as varint-encoded deltas.
        
        Args:
            ll: Integer coordinate value to encode
        """
        if not self.lastLatInit:
            self.buf[self.cur:self.cur+4] = struct.pack("<i", ll)
            self.cur += 4
            self.lastLat = ll
            self.lastLatInit = True
            return
            
        if not self.lastLonInit:
            self.buf[self.cur:self.cur+4] = struct.pack("<i", ll)
            self.cur += 4
            self.lastLon = ll
            self.lastLonInit = True
            return
            
        # Varint encoding for delta values
        b = ll << 1
        if ll < 0:
            b = (~b) & 0xFFFFFFFFFFFFFFFF
            
        chunks = []
        while b > 0:
            chunks.append(b & 0x7F)
            b >>= 7
            
        if not chunks:
            self.buf[self.cur] = 0
            self.cur += 1
            return
            
        for i in range(len(chunks)-1):
            self.buf[self.cur] = (chunks[i] | 0x80)
            self.cur += 1
        self.buf[self.cur] = chunks[-1]
        self.cur += 1

    def add_coord_int(self, lon_i: int, lat_i: int):
        """
        Add coordinate using integer values (in 1e5 precision).
        
        The first coordinate of any polyline is stored as absolute 32-bit integers.
        Subsequent coordinates are stored as varint-encoded deltas from the previous point.
        
        Args:
            lon_i: Longitude as integer (degrees * 1e5)
            lat_i: Latitude as integer (degrees * 1e5)
        """
        # First coordinate of any polyline string is always absolute (32-bit integers)
        if not (self.lastLatInit and self.lastLonInit):
            # Write absolute lat and lon as 32-bit integers
            self.buf[self.cur:self.cur+4] = struct.pack("<i", lat_i)
            self.cur += 4
            self.buf[self.cur:self.cur+4] = struct.pack("<i", lon_i)
            self.cur += 4
            self.lastLat = lat_i
            self.lastLon = lon_i
            self.lastLatInit = True
            self.lastLonInit = True
            return
            
        # Subsequent coordinates are deltas (varint encoded)
        dlat = lat_i - self.lastLat
        dlon = lon_i - self.lastLon
        self._add_part(dlat)
        self._add_part(dlon)
        self.lastLat = lat_i
        self.lastLon = lon_i

    def add_coord_float(self, lon_f: float, lat_f: float):
        """
        Add coordinate using float values (degrees).
        
        Converts floating-point coordinates to the integer format
        and then encodes them using the integer method.
        
        Args:
            lon_f: Longitude in decimal degrees
            lat_f: Latitude in decimal degrees
        """
        lat_i = round_away_from_zero(lat_f * 1e5)
        lon_i = round_away_from_zero(lon_f * 1e5)
        self.add_coord_int(lon_i, lat_i)
    
    def get_encoded_size(self) -> int:
        """
        Get the current size of encoded data in bytes.
        
        Returns:
            Number of bytes written to the buffer
        """
        return self.cur
    
    def reset(self, base: Optional['Coordinate'] = None):
        """
        Reset the encoder state for encoding a new polyline.
        
        Args:
            base: Optional new base coordinate for delta encoding
        """
        self.cur = 0
        self.lastLatInit = False
        self.lastLonInit = False
        self.lastLat = 0
        self.lastLon = 0
        
        if base is not None:
            self.lastLat = round_away_from_zero(base.lat * 1e5)
            self.lastLon = round_away_from_zero(base.lon * 1e5)
            self.lastLatInit = True
            self.lastLonInit = True