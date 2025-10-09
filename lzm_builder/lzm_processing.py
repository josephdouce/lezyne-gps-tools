"""
LZM Processing Module

This module contains the core processing functions for generating LZM files.
These functions handle the main algorithmic work of converting OSM data into
the LZM format used by Lezyne GPS devices.
"""

import struct
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from lzm_builder import Coordinate, GridTile, Polyline

from lzm_constants import GROUP_ORDER

from lzm_utils import (
    angle_degrees_difference,   
    bbox_contains,
    simplify,
)


from polyline_encoder import PolylineEncoder


def add_way_to_polylines(way_coords: List['Coordinate'], ptype: int, tile: 'GridTile',
                         opt_level: int, epsilon: float):
    """Add a way to the appropriate polylines in a tile."""
    # Import here to avoid circular imports
    from lzm_builder import Polyline
    
    new_polylines: List[Polyline] = []
    new_poly = Polyline()
    last_added = False
    last_in = False
    last_coord = None
    added_this = 0
    for coord in way_coords:
        inside = bbox_contains(tile.bbox, coord)
        if inside and not last_added and last_coord is not None:
            new_poly.coordinates.append(last_coord)
            added_this += 1
        if inside or last_in:
            new_poly.coordinates.append(coord)
            last_added = True
            added_this += 1
            if added_this >= 254:
                added_this = 0
                new_polylines.append(new_poly)
                new_poly = Polyline()
                new_poly.coordinates.append(coord)
        else:
            last_added = False
            if len(new_poly.coordinates) > 0:
                new_polylines.append(new_poly)
                new_poly = Polyline()
        last_in = inside
        last_coord = coord
    if len(new_poly.coordinates) > 0:
        new_polylines.append(new_poly)

    if not new_polylines:
        return

    for poly in new_polylines:
        did_merge = False
        if opt_level > 0:
            for existing in tile.polys[ptype]:
                if (angle_degrees_difference(existing.coordinates[-1].lat, poly.coordinates[0].lat) <= 1e-5 and
                    angle_degrees_difference(existing.coordinates[-1].lon, poly.coordinates[0].lon) <= 1e-5):
                    for i in range(1, len(poly.coordinates)):
                        existing.coordinates.append(poly.coordinates[i])
                    did_merge = True
                    break
                if (angle_degrees_difference(existing.coordinates[0].lat, poly.coordinates[-1].lat) <= 1e-5 and
                    angle_degrees_difference(existing.coordinates[0].lon, poly.coordinates[-1].lon) <= 1e-5):
                    for i in range(len(poly.coordinates)-2, -1, -1):
                        existing.coordinates.insert(0, poly.coordinates[i])
                    did_merge = True
                    break
                if (angle_degrees_difference(existing.coordinates[-1].lat, poly.coordinates[-1].lat) <= 1e-5 and
                    angle_degrees_difference(existing.coordinates[-1].lon, poly.coordinates[-1].lon) <= 1e-5):
                    for i in range(len(poly.coordinates)-2, -1, -1):
                        existing.coordinates.append(poly.coordinates[i])
                    did_merge = True
                    break
                if (angle_degrees_difference(existing.coordinates[0].lat, poly.coordinates[0].lat) <= 1e-5 and
                    angle_degrees_difference(existing.coordinates[0].lon, poly.coordinates[0].lon) <= 1e-5):
                    for i in range(1, len(poly.coordinates)):
                        existing.coordinates.insert(0, poly.coordinates[i])
                    did_merge = True
                    break
        if not did_merge and len(poly.coordinates) > 0:
            poly.coordinates = simplify(poly.coordinates, epsilon, opt_level)
            tile.polys[ptype].append(poly)

    tile.hasPolylineData = True
    for t in GROUP_ORDER:
        tile.counts[t] = len(tile.polys[t])


def compress_polylines(polys: List['Polyline']) -> Tuple[bytes, int]:
    """Compress a list of polylines into binary format."""
    # Import here to avoid circular imports
    from lzm_builder import Polyline
    
    tmp = bytearray(8000)
    wpos = 0
    
    # Split any polylines that are too long
    split_polys = []
    for poly in polys:
        if len(poly.coordinates) > 255:
            # Split into chunks of 200 points with 5-point overlap
            chunk_size = 200
            overlap = 5
            for i in range(0, len(poly.coordinates), chunk_size - overlap):
                chunk_coords = poly.coordinates[i:i + chunk_size]
                if len(chunk_coords) >= 2:  # Only keep meaningful chunks
                    chunk_poly = Polyline()
                    chunk_poly.coordinates = chunk_coords
                    split_polys.append(chunk_poly)
        else:
            split_polys.append(poly)
    
    # Write uint16 number_of_polylines header as specified
    if len(split_polys) > 65535:
        raise ValueError("Too many polylines for uint16")
    tmp[wpos:wpos+2] = struct.pack("<H", len(split_polys))
    wpos += 2
    
    if not split_polys:
        return (bytes(tmp[:wpos]), wpos)
    
    # Shared base coordinate is first coordinate of first polyline
    base_coord = split_polys[0].coordinates[0] if split_polys[0].coordinates else None
    
    for i, poly in enumerate(split_polys):
        if len(poly.coordinates) > 255:
            raise ValueError(f"Split polyline still >255 points: {len(poly.coordinates)}")
        if wpos >= len(tmp):
            raise ValueError("Buffer overflow")
        
        # Write uint8 point_count for this polyline
        tmp[wpos] = len(poly.coordinates)
        wpos += 1
        
        if not poly.coordinates:
            continue
            
        # First polyline: no base (absolute coordinates for first point)
        # Subsequent polylines: use shared base coordinate
        if i == 0:
            enc = PolylineEncoder(tmp, base=None)
            enc.cur = wpos  # Set encoder position to current write position
        else:
            enc = PolylineEncoder(tmp, base=base_coord)
            enc.cur = wpos  # Set encoder position to current write position
        
        for c in poly.coordinates:
            enc.add_coord_float(c.lon, c.lat)
        
        wpos = enc.cur  # Update write position from encoder
    
    return (bytes(tmp[:wpos]), wpos)