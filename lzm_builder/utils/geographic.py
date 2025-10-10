"""
Geographic Utilities Module

This module contains utility functions used by the LZM builder for geographic
calculations, bounding box operations, and polyline simplification.
"""

import math
import os
import re
import subprocess
from typing import List, Optional, Tuple, TYPE_CHECKING

# Avoid circular imports by using TYPE_CHECKING
if TYPE_CHECKING:
    from ..models.data_classes import Coordinate, BoundingBox


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


def bbox_overlap_fast(r1: 'BoundingBox', r2: 'BoundingBox') -> bool:
    """Fast bounding box overlap check - same as bbox_overlap but optimized."""
    return not (r1.west > r2.east or r2.west > r1.east or
                r1.south > r2.north or r2.south > r1.north)


def angle_degrees_difference(a1: float, a2: float) -> float:
    """Calculate the difference between two angles in degrees."""
    return 180.0 - abs(abs(a1 - a2) - 180.0)


def get_way_bounds_fast(node_refs: List[int], nodes: dict) -> Optional[Tuple[float, float, float, float]]:
    """Get bounding box of a way quickly without creating Coordinate objects."""
    if not node_refs:
        return None
    
    min_lat = min_lon = float('inf')
    max_lat = max_lon = float('-inf')
    
    for node_ref in node_refs:
        coord = nodes.get(node_ref)
        if coord:
            if coord.lat < min_lat: min_lat = coord.lat
            if coord.lat > max_lat: max_lat = coord.lat
            if coord.lon < min_lon: min_lon = coord.lon
            if coord.lon > max_lon: max_lon = coord.lon
    
    if min_lat == float('inf'):
        return None
        
    return min_lat, min_lon, max_lat, max_lon


def simplify(coords: List['Coordinate'], epsilon: float, opt_level: int) -> List['Coordinate']:
    """Simplify a list of coordinates using Douglas-Peucker algorithm."""
    if opt_level < 2 or len(coords) <= 2:
        return coords
    
    return rdp_simplify(coords, epsilon)


def rdp_simplify(coords: List['Coordinate'], epsilon: float) -> List['Coordinate']:
    """Douglas-Peucker line simplification algorithm."""
    if len(coords) <= 2:
        return coords
    
    # Find the point with maximum distance from the line between first and last
    max_dist = 0
    max_index = 0
    
    for i in range(1, len(coords) - 1):
        dist = point_to_line_distance(coords[i], coords[0], coords[-1])
        if dist > max_dist:
            max_dist = dist
            max_index = i
    
    # If max distance is greater than epsilon, recursively simplify
    if max_dist > epsilon:
        # Recursive call
        left_part = rdp_simplify(coords[:max_index + 1], epsilon)
        right_part = rdp_simplify(coords[max_index:], epsilon)
        
        # Combine results (remove duplicate middle point)
        return left_part[:-1] + right_part
    else:
        # All points between first and last can be removed
        return [coords[0], coords[-1]]


def point_to_line_distance(point: 'Coordinate', line_start: 'Coordinate', line_end: 'Coordinate') -> float:
    """Calculate perpendicular distance from point to line segment."""
    # Vector from line_start to line_end
    line_vec_x = line_end.lon - line_start.lon
    line_vec_y = line_end.lat - line_start.lat
    
    # Vector from line_start to point
    point_vec_x = point.lon - line_start.lon
    point_vec_y = point.lat - line_start.lat
    
    # Calculate line length squared
    line_len_sq = line_vec_x * line_vec_x + line_vec_y * line_vec_y
    
    if line_len_sq == 0:
        # Line start and end are the same point
        return math.sqrt(point_vec_x * point_vec_x + point_vec_y * point_vec_y)
    
    # Calculate the parameter t that represents position along line
    t = (point_vec_x * line_vec_x + point_vec_y * line_vec_y) / line_len_sq
    
    if t < 0:
        # Point is beyond line_start
        return math.sqrt(point_vec_x * point_vec_x + point_vec_y * point_vec_y)
    elif t > 1:
        # Point is beyond line_end
        end_vec_x = point.lon - line_end.lon
        end_vec_y = point.lat - line_end.lat
        return math.sqrt(end_vec_x * end_vec_x + end_vec_y * end_vec_y)
    else:
        # Point projects onto line segment
        proj_x = line_start.lon + t * line_vec_x
        proj_y = line_start.lat + t * line_vec_y
        dist_x = point.lon - proj_x
        dist_y = point.lat - proj_y
        return math.sqrt(dist_x * dist_x + dist_y * dist_y)


def script_dir() -> str:
    """Get the directory containing the lzm_builder package (parent of utils)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def filename_from_bbox(bbox: 'BoundingBox', prefix: str = "mf", suffix: str = ".lzm", include_path: bool = False) -> str:
    """Generate filename from bounding box coordinates."""
    filename = f"{prefix}_{bbox.south:.6f}_{bbox.west:.6f}_{bbox.north:.6f}_{bbox.east:.6f}{suffix}"
    
    if include_path:
        return os.path.join(script_dir(), filename)
    else:
        return filename


def pluck_bbox_from_filename(filename: str) -> 'BoundingBox':
    """Extract bounding box from filename containing coordinates."""
    from models.data_classes import BoundingBox
    
    # Pattern to match: prefix_south_west_north_east.extension or prefix_south_west_north_east_suffix.extension
    pattern = r'[^_]+_(-?\d+\.?\d*)_(-?\d+\.?\d*)_(-?\d+\.?\d*)_(-?\d+\.?\d*)(?:_[^.]*)?\..*'
    match = re.search(pattern, os.path.basename(filename))
    
    if not match:
        raise ValueError(f"Cannot extract bounding box from filename: {filename}")
    
    south, west, north, east = map(float, match.groups())
    return BoundingBox(south, west, north, east)


def extract_smaller_pbf_from_larger_pbf(input_pbf: str, output_pbf: str, bbox: 'BoundingBox') -> bool:
    """Extract a smaller PBF file from a larger one using osmium."""
    try:
        bbox_str = f"{bbox.west},{bbox.south},{bbox.east},{bbox.north}"
        cmd = [
            "osmium", "extract",
            "--bbox", bbox_str,
            "--output", output_pbf,
            input_pbf
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False