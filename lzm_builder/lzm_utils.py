"""
LZM Utilities Module

This module contains utility functions used by the LZM builder for geographic
calculations, bounding box operations, and polyline simplification.
"""

import math
from typing import List, TYPE_CHECKING

# Avoid circular imports by using TYPE_CHECKING
if TYPE_CHECKING:
    from lzm_builder import Coordinate, BoundingBox


def round_away_from_zero(x: float) -> int:
    """Round a float away from zero to the nearest integer."""
    if x >= 0:
        return int(math.floor(x + 0.5))
    else:
        return int(math.ceil(x - 0.5))


def bbox_include(b: 'BoundingBox', c: 'Coordinate') -> None:
    """Expand bounding box to include coordinate."""
    if b.north < c.lat: b.north = c.lat
    if b.east  < c.lon: b.east  = c.lon
    if b.south > c.lat: b.south = c.lat
    if b.west  > c.lon: b.west  = c.lon


def bbox_contains(b: 'BoundingBox', c: 'Coordinate') -> bool:
    """Check if bounding box contains coordinate."""
    if b.south > c.lat: return False
    if b.west  > c.lon: return False
    if b.north < c.lat: return False
    if b.east  < c.lon: return False
    return True


def bbox_overlap(r1: 'BoundingBox', r2: 'BoundingBox') -> bool:
    """Check if two bounding boxes overlap."""
    no = (r1.west  > r2.east  or r2.west  > r1.east or
          r1.south > r2.north or r2.south > r1.north)
    return not no


def angle_degrees_difference(a1: float, a2: float) -> float:
    """Calculate the difference between two angles in degrees."""
    return 180.0 - abs(abs(a1 - a2) - 180.0)


def perpendicular_distance(p: 'Coordinate', a: 'Coordinate', b: 'Coordinate') -> float:
    """Calculate perpendicular distance from point p to line segment a-b."""
    A = p.lon - a.lon
    B = p.lat - a.lat
    C = b.lon - a.lon
    D = b.lat - a.lat
    dot = A*C + B*D
    len_sq = C*C + D*D
    if len_sq == 0.0:
        xx, yy = a.lon, a.lat
    else:
        param = dot / len_sq
        if param < 0 or (abs(a.lon-b.lon) <= 1e-6 and abs(a.lat-b.lat) <= 1e-6):
            xx, yy = a.lon, a.lat
        elif param > 1:
            xx, yy = b.lon, b.lat
        else:
            xx = a.lon + param*C
            yy = a.lat + param*D
    dx = p.lon - xx
    dy = p.lat - yy
    return math.sqrt(dx*dx + dy*dy)


def simplify(points: List['Coordinate'], epsilon: float, opt_level: int) -> List['Coordinate']:
    """Simplify a polyline using Douglas-Peucker algorithm."""
    if opt_level < 2 or len(points) <= 2:
        return points[:]
    dmax = 0.0
    index = 0
    for i in range(1, len(points)-1):
        d = perpendicular_distance(points[i], points[0], points[-1])
        if d > dmax:
            dmax = d
            index = i
    if dmax > epsilon:
        pre = simplify(points[:index+1], epsilon, opt_level)
        post = simplify(points[index:], epsilon, opt_level)
        return pre + post[1:]
    else:
        return [points[0], points[-1]]


def bbox_overlap_fast(bbox1: 'BoundingBox', bbox2: 'BoundingBox') -> bool:
    """Fast bounding box overlap check with early rejection."""
    return not (bbox1.east < bbox2.west or bbox1.west > bbox2.east or 
               bbox1.north < bbox2.south or bbox1.south > bbox2.north)


def point_in_bbox_fast(lat: float, lon: float, bbox: 'BoundingBox', buffer: float = 0.0) -> bool:
    """Fast point-in-bounding-box check with optional buffer."""
    return (bbox.south - buffer <= lat <= bbox.north + buffer and 
            bbox.west - buffer <= lon <= bbox.east + buffer)


def get_way_bounds_fast(node_refs: list, nodes: dict) -> tuple:
    """Quick way bounds calculation without creating full coordinate objects."""
    lats, lons = [], []
    for nid in node_refs:
        coord = nodes.get(nid)
        if coord:
            lats.append(coord.lat)
            lons.append(coord.lon)
    
    if not lats:
        return None
    
    return min(lats), min(lons), max(lats), max(lons)

def extract_smaller_pbf_from_larger_pbf(input_pbf: str, output_pbf: str, bbox: 'BoundingBox') -> bool:
    """Extract a smaller PBF file from a larger one using osmium."""
    import subprocess
    
    # osmium extract expects: LEFT,BOTTOM,RIGHT,TOP which is west,south,east,north
    bbox_str = f"{bbox.west},{bbox.south},{bbox.east},{bbox.north}"
    
    cmd = [
        "osmium", "extract",
        "--bbox", bbox_str,  # Use double dash
        "--output", output_pbf,  # Use double dash  
        input_pbf
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"osmium extract completed successfully")
        if result.stdout:
            print(f"stdout: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error during osmium extract: {e}")
        print(f"Command: {' '.join(cmd)}")
        print(f"Return code: {e.returncode}")
        if e.stdout:
            print(f"stdout: {e.stdout}")
        if e.stderr:
            print(f"stderr: {e.stderr}")
        return False

def pluck_bbox_from_filename(filename: str) -> 'BoundingBox':
    """Extract bounding box from filename formatted as '..._minlat_minlon_maxlat_maxlon...'.

    Example filenames: 
        'map_34.0_-118.5_34.5_-118.0.pbf'
        'map_34.0_-118.5_34.5_-118.0_grid_1_5.lzm'
        'map_34.0_-118.5_34.5_-118.0_full.osm'

    Must be decimal degrees with underscores as separators.
    Not Integers, No DMS, No other separators.

    Raises ValueError if pattern not found.
    Returns: BoundingBox object with extracted coordinates.
    """
    import re
    # Import here to avoid circular imports
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from lzm_builder import BoundingBox

    pattern = r'(\-?\d+\.\d+)_(-?\d+\.\d+)_(-?\d+\.\d+)_(-?\d+\.\d+)'
    match = re.search(pattern, filename)
    if not match:
        raise ValueError("Filename does not contain a valid bounding box pattern.")
    
    minlat, minlon, maxlat, maxlon = map(float, match.groups())
    
    # Create BoundingBox dynamically to avoid circular import
    import sys
    if 'lzm_builder' in sys.modules:
        BoundingBox = sys.modules['lzm_builder'].BoundingBox
    else:
        # Fallback: create a simple dataclass
        from dataclasses import dataclass
        @dataclass
        class BoundingBox:
            south: float
            west: float  
            north: float
            east: float
    
    return BoundingBox(north=maxlat, south=minlat, east=maxlon, west=minlon)