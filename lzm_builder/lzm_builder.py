"""
Lezyne LZM Map Builder

Generates Lezyne LZM offline map files from OpenStreetMap data.
Supports PBF as the base input map data.

Example usage:
    # Class interface
    builder = LZMBuilder()
    bbox = BoundingBox(50.92, 4.80, 50.97, 4.85)
    lzm_file = builder.from_pbf("map.osm.pbf", bbox, verbose=True)
    
    # Function interface
    lzm_file = build_lzm_from_pbf("map.osm.pbf", bbox, verbose=True)
    
    # Command line
    python lzm_builder.py --pbf map.osm.pbf --bbox 50.92,4.80,50.97,4.85 --verbose
"""

import argparse
import io
import math
import os
import struct
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import osmium

from lzm_utils import (
    angle_degrees_difference,
    bbox_contains,
    bbox_include,
    bbox_overlap,
    bbox_overlap_fast,
    get_way_bounds_fast,
    perpendicular_distance,
    point_in_bbox_fast,
    round_away_from_zero,
    simplify,
)
from lzm_constants import (
    GROUP_ORDER,
    PolylineType,
    WAY_KEY_TO_TYPE,
)
from lzm_processing import (
    add_way_to_polylines,
    build_lzm_from_extracted_pbf,
    build_lzm_from_pbf,
    compress_polylines,
)
from pbf_handler import PBFHandler


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Coordinate:
    """Represents a geographic coordinate (latitude, longitude)."""
    lat: float
    lon: float


@dataclass
class BoundingBox:
    """Represents a geographic bounding box."""
    south: float
    west: float
    north: float
    east: float


@dataclass
class Polyline:
    """Represents a polyline with a list of coordinates."""
    coordinates: List[Coordinate] = field(default_factory=list)


@dataclass
class GridTile:
    """Represents a single tile in the grid containing polyline data."""
    bbox: BoundingBox
    hasPolylineData: bool = False
    hasCompressedData: bool = False
    polys: Dict[int, List[Polyline]] = field(default_factory=lambda: {t: [] for t in GROUP_ORDER})
    counts: Dict[int, int] = field(default_factory=lambda: {t: 0 for t in GROUP_ORDER})
    compressed: Dict[int, bytes] = field(default_factory=dict)
    sizes: Dict[int, int] = field(default_factory=dict)


# =============================================================================
# PROCESSING CLASSES
# =============================================================================

class LZMBuilder:
    """
    LZM file generator for Lezyne GPS devices
    
    This class orchestrates generating LZM map files
    from OpenStreetMap PBF data.
    """
    
    def __init__(self):
        """Initialize LZM builder"""
        pass
        
    def from_pbf(self, pbf_path: str, bbox: BoundingBox, 
                 keep_service: bool = False, keep_sidewalks: bool = False,
                 extraction: bool = False, epsilon: float = 0.00002, opt_level: int = 2,
                 verbose: bool = False) -> str:
        """
        Generate LZM file from OSM PBF data
        
        Args:
            pbf_path: Path to OSM PBF file
            bbox: Geographic bounding box
            keep_service: Include service roads
            keep_sidewalks: Include sidewalks
            extraction: Use extraction method (faster, requires osmium cli tools)
            epsilon: RDP epsilon for simplification (0.00002 default)
            opt: Optimization level (0-3, default 2)
            verbose: Print progress information
            
        Returns:
            Path to generated LZM file
        """
        if extraction:
            return build_lzm_from_extracted_pbf(pbf_path, bbox, keep_service, keep_sidewalks,
                                                      epsilon, opt_level, verbose)
        else:
            return build_lzm_from_pbf(pbf_path, bbox, keep_service, keep_sidewalks,
                                 False, epsilon, opt_level, verbose)


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Command line interface for the LZM builder."""
    ap = argparse.ArgumentParser(description="Build LZM from PBF")

    ap.add_argument("--pbf", required=True, help="Path to input .pbf file")
    ap.add_argument("--bbox", required=True, help="south,west,north,east (decimal degrees)")
    ap.add_argument("--keep-service", action="store_true", help="Keep service roads")
    ap.add_argument("--keep-sidewalks", action="store_true", help="Keep sidewalks")
    ap.add_argument("--extraction", action="store_true", help="Use extraction method (faster, requires osmium cli tools)")
    ap.add_argument("--epsilon", type=float, default=0.00002, help="RDP epsilon")
    ap.add_argument("--opt", type=int, default=2, help="Optimization level")
    ap.add_argument("--verbose", action="store_true")
    
    args = ap.parse_args()

    s, w, n, e = map(float, args.bbox.split(","))
    bbox = BoundingBox(s, w, n, e)
    
    if args.pbf and args.bbox:
        if args.extraction:
            outname = build_lzm_from_extracted_pbf(args.pbf, bbox, args.keep_service, args.keep_sidewalks,
                                                        args.epsilon, args.opt, args.verbose)
        else:
            outname = build_lzm_from_pbf(args.pbf, bbox, args.keep_service, args.keep_sidewalks,
                                         False, args.epsilon, args.opt, args.verbose)
    else:
        if not args.pbf:
            print("Error: Specify --pbf input file")
        if not args.bbox:
            print("Error: Specify --bbox bounding box")
        return
        
    print(f"Generated: {outname}")


if __name__ == "__main__":
    main()