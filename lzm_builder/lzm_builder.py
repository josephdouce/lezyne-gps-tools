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
    lzm_file = build_lzm_from_pbf_with_auto_bbox("map.osm.pbf", bbox, verbose=True)
    
    # Command line
    python lzm_builder.py --pbf map.osm.pbf --bbox 50.92,4.80,50.97,4.85 --verbose
"""

import argparse
import math
import os
import struct
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


from lzm_utils import (
    angle_degrees_difference,
    pluck_bbox_from_filename,
)
from lzm_constants import (
    GROUP_ORDER,
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



class LZMBuilder:
    """
    LZM file generator for Lezyne GPS devices
    
    This class orchestrates generating LZM map files
    from OpenStreetMap PBF data.
    """
    
    def __init__(self):
        """Initialize LZM builder"""
        pass
        
    def from_pbf(self, pbf_path: str, bbox: BoundingBox | str = "auto", 
                 keep_service: bool = False, keep_sidewalks: bool = False,
                 extraction: bool = False, epsilon: float = 0.00002, opt_level: int = 2,
                 verbose: bool = False) -> str:
        """
        Generate LZM file from OSM PBF data - Main public interface
        
        Args:
            pbf_path: Path to OSM PBF file
            bbox: Geographic bounding box or "auto" to extract from filename
            keep_service: Include service roads
            keep_sidewalks: Include sidewalks
            extraction: Use extraction method (faster, requires osmium cli tools)
            epsilon: RDP epsilon for simplification (0.00002 default)
            opt_level: Optimization level (0-3, default 2)
            verbose: Print progress information
            
        Returns:
            Path to generated LZM file
        """
        # Handle auto bbox detection
        if isinstance(bbox, str) and bbox == "auto":
            return self._from_pbf_with_auto_bbox(pbf_path, keep_service, keep_sidewalks,
                                               extraction, epsilon, opt_level, verbose)
        
        # Handle extraction method
        if extraction:
            return self._build_lzm_from_extracted_pbf(pbf_path, bbox, keep_service, keep_sidewalks,
                                                     epsilon, opt_level, verbose)
        
        # Direct build
        return self._build_lzm_from_pbf(pbf_path, bbox, keep_service, keep_sidewalks,
                                       bbox_filtering=True, epsilon=epsilon, 
                                       opt_level=opt_level, verbose=verbose)
    
    def _from_pbf_with_auto_bbox(self, pbf_path: str,
                                keep_service: bool, keep_sidewalks: bool,
                                extraction: bool, epsilon: float, opt_level: int, verbose: bool) -> str:
        """
        Convenience method that handles auto bbox detection from filename
        """
        if extraction:
            raise ValueError("Cannot use extraction method with bbox='auto'. Auto mode processes the whole PBF file, making extraction redundant.")
        
        try:
            bbox = pluck_bbox_from_filename(pbf_path)
            if verbose:
                print(f"Auto-detected bbox from filename: {bbox}")
        except ValueError as e:
            raise ValueError(f"Cannot auto-detect bounding box from filename '{pbf_path}': {e}")
        
        # Call the core build method with no bbox filtering (process whole PBF)
        return self._build_lzm_from_pbf(pbf_path, bbox, keep_service, keep_sidewalks,
                                       bbox_filtering=False, epsilon=epsilon,
                                       opt_level=opt_level, verbose=verbose)

    def _build_lzm_from_extracted_pbf(self, pbf_path: str, bbox: BoundingBox,
                                     keep_service: bool, keep_sidewalks: bool,
                                     epsilon: float, opt_level: int, verbose: bool) -> str:
        """
        Convenience method that extracts a smaller PBF then calls the core build method
        """
        from lzm_utils import extract_smaller_pbf_from_larger_pbf

        from lzm_utils import filename_from_bbox
        
        extracted_pbf_file = filename_from_bbox(bbox, prefix="extracted", suffix=".osm.pbf", include_path=True)

        if verbose:
            print(f"⏱️  Extracting smaller PBF to {extracted_pbf_file}...")
            extract_start = time.time()
        
        success = extract_smaller_pbf_from_larger_pbf(pbf_path, extracted_pbf_file, bbox)
        if not success:
            raise RuntimeError("Failed to extract smaller PBF")
        
        if verbose:
            extract_time = time.time() - extract_start
            print(f"✅ Extraction complete ({extract_time:.1f}s)")
            print()
            print(f"⏱️  Building LZM from extracted PBF...")
            
        # Call the core build method with no bbox filtering (extracted PBF is already filtered)
        outname = self._build_lzm_from_pbf(extracted_pbf_file, bbox, keep_service, keep_sidewalks,
                                         bbox_filtering=False, epsilon=epsilon,
                                         opt_level=opt_level, verbose=verbose)
        
        # Clean up temporary file
        try:
            os.remove(extracted_pbf_file)
            if verbose:
                print(f"🧹 Removed temporary file {extracted_pbf_file}")
        except OSError as e:
            print(f"⚠️  Warning: Failed to remove temporary file {extracted_pbf_file}: {e}")
        
        return outname

    def _build_lzm_from_pbf(self, pbf_path: str, bbox: BoundingBox,
                          keep_service: bool, keep_sidewalks: bool, bbox_filtering: bool,
                          epsilon: float, opt_level: int, verbose: bool) -> str:
        """Generate LZM file directly from PBF file"""
        # Import here to avoid circular imports
        from lzm_processing import add_way_to_polylines, compress_polylines
        
        start_time = time.time()
        
        nodes: Dict[int, Coordinate] = {}
        ways_to_include: List[Tuple[int, int, List[int], int, BoundingBox]] = []
        
        # Spatial optimization: expand bbox slightly for edge cases
        bbox_buffer = 0.01  # ~1km buffer
        
        # Phase 1: Parse PBF file
        if verbose: 
            print(f"⏱️  Phase 1: Parsing PBF file...")
            phase1_start = time.time()

        handler = PBFHandler(bbox, bbox_buffer, nodes, ways_to_include, bbox_filtering,
                            keep_service, keep_sidewalks, verbose)
        handler.apply_file(pbf_path)
        
        if verbose:
            phase1_time = time.time() - phase1_start
            print(f"✅ Phase 1 complete ({phase1_time:.1f}s)")
            node_efficiency = (1 - handler.nodes_rejected_early / handler.nodes_processed) * 100 if handler.nodes_processed > 0 else 0
            way_efficiency = (len(ways_to_include) / handler.ways_processed) * 100 if handler.ways_processed > 0 else 0
            print(f"📊 Final stats: {handler.nodes_processed:,} nodes processed, {len(nodes):,} kept ({node_efficiency:.1f}% efficiency)")
            print(f"📊 Final stats: {handler.ways_processed:,} ways processed, {len(ways_to_include):,} included ({way_efficiency:.1f}% efficiency)")
            print(f"🚀 Optimization: {handler.nodes_rejected_early:,} nodes rejected early (fast path)")
            print()
        
        # Phase 2: Build grid
        if verbose:
            print(f"⏱️  Phase 2: Building tile grid...")
            phase2_start = time.time()
        
        south, west, north, east = bbox.south, bbox.west, bbox.north, bbox.east
        htiles = int(round((east - west)*100.0))
        vtiles = int(round((north - south)*100.0))

        if verbose:
            total_tiles = htiles * vtiles
            print(f"📐 Grid dimensions: {htiles} × {vtiles} = {total_tiles:,} tiles")

        grid: List[List[GridTile]] = []
        for y in range(vtiles):  # rows (south→north)
            row = []
            for x in range(htiles):  # columns (west→east)
                tbox = BoundingBox(south + y*0.01, west + x*0.01, south + (y+1)*0.01, west + (x+1)*0.01)
                row.append(GridTile(tbox))
            grid.append(row)

        # Phase 3: Populate grid with ways
        if verbose:
            phase2_time = time.time() - phase2_start
            print(f"✅ Phase 2 complete ({phase2_time:.1f}s)")
            print(f"⏱️  Phase 3: Populating grid with ways...")
            phase3_start = time.time()
            ways_assigned = 0

        for (_, ptype, refs, _, bb) in ways_to_include:
            south_i = max(0, int(math.floor(angle_degrees_difference(bb.south, south)*100))-1)
            west_i  = max(0, int(math.floor(angle_degrees_difference(bb.west, west)*100))-1)
            height  = int(math.ceil(angle_degrees_difference(bb.north, bb.south)*100))
            width   = int(math.ceil(angle_degrees_difference(bb.east, bb.west)*100))
            north_i = min(vtiles-1, south_i + height + 1)
            east_i  = min(htiles-1, west_i  + width  + 1)
            coords: List[Coordinate] = []
            for r in refs:
                c = nodes.get(r)
                if c is not None:
                    coords.append(c)
            if len(coords) < 2:
                continue
            for y in range(south_i, north_i+1):
                for x in range(west_i, east_i+1):
                    add_way_to_polylines(coords, ptype, grid[y][x], opt_level, epsilon)
            
            if verbose:
                ways_assigned += 1
                if ways_assigned % 1000 == 0:
                    print(f"🗺️  Assigned {ways_assigned:,}/{len(ways_to_include):,} ways to tiles")

        # Phase 4: Compress polylines
        if verbose:
            phase3_time = time.time() - phase3_start
            print(f"✅ Phase 3 complete ({phase3_time:.1f}s)")
            print(f"⏱️  Phase 4: Compressing polylines...")
            phase4_start = time.time()
            tiles_compressed = 0

        for y in range(vtiles):
            for x in range(htiles):
                for t in GROUP_ORDER:
                    if len(grid[y][x].polys[t]) > 0:
                        data, size = compress_polylines(grid[y][x].polys[t])
                        grid[y][x].compressed[t] = data
                        grid[y][x].sizes[t] = size
                        grid[y][x].counts[t] = len(grid[y][x].polys[t])
                
                if verbose:
                    tiles_compressed += 1
                    if tiles_compressed % 1000 == 0:
                        total_tiles = htiles * vtiles
                        print(f"🗜️  Compressed {tiles_compressed:,}/{total_tiles:,} tiles")

        # Phase 5: Write LZM file
        if verbose:
            phase4_time = time.time() - phase4_start
            print(f"✅ Phase 4 complete ({phase4_time:.1f}s)")
            print(f"⏱️  Phase 5: Writing LZM file...")
            phase5_start = time.time()

        from lzm_utils import filename_from_bbox
        outname = filename_from_bbox(bbox)
        
        with open(outname, "wb") as out:
            # Write using same format as working files
            section1_off = 16
            section2_off = 0
            section3_off = 0
            section4_off = 0
            out.write(struct.pack("<IIII", section1_off, section2_off, section3_off, section4_off))

            # Section 1: Tile Directory
            file_offset = 0
            for y in range(vtiles):
                for x in range(htiles):
                    tile = grid[y][x]
                    num_groups = len([t for t in GROUP_ORDER if len(tile.polys[t]) > 0])
                    out.write(struct.pack("<IH", file_offset, num_groups))
                    file_offset += num_groups * 5

            # Section 2: Tile→String IDs
            section2_off = out.tell()
            file_offset = 0
            for y in range(vtiles):
                for x in range(htiles):
                    tile = grid[y][x]
                    for t in GROUP_ORDER:
                        if len(tile.polys[t]) > 0:
                            out.write(struct.pack("<IB", file_offset, t))
                            file_offset += 1

            # Section 3: String Index
            section3_off = out.tell()
            file_offset = 0
            for y in range(vtiles):
                for x in range(htiles):
                    tile = grid[y][x]
                    for t in GROUP_ORDER:
                        if len(tile.polys[t]) > 0:
                            size = tile.sizes[t]
                            out.write(struct.pack("<IH", file_offset, size))
                            file_offset += size

            # Section 4: Polyline Data
            section4_off = out.tell()
            for y in range(vtiles):
                for x in range(htiles):
                    tile = grid[y][x]
                    for t in GROUP_ORDER:
                        if len(tile.polys[t]) > 0:
                            out.write(tile.compressed[t])

            # Update header with actual offsets
            out.seek(0)
            out.write(struct.pack("<IIII", section1_off, section2_off, section3_off, section4_off))

        # Final timing summary
        if verbose:
            phase5_time = time.time() - phase5_start
            total_time = time.time() - start_time
            print(f"✅ Phase 5 complete ({phase5_time:.1f}s)")
            print()
            print(f"📋 GENERATION COMPLETE!")
            print(f"📁 Output: {outname}")
            print(f"⏱️ Total time: {total_time:.1f}s")
            
            # File size info
            file_size = os.path.getsize(outname)
            print(f"📦 File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
            print(f"🗺️ Coverage: {htiles}×{vtiles} tiles ({htiles*vtiles:,} total)")
            
        return outname


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Command line interface for the LZM builder."""
    ap = argparse.ArgumentParser(description="Build LZM from PBF")

    ap.add_argument("--pbf", required=True, help="Path to input .pbf file")
    ap.add_argument("--bbox", required=True, help="south,west,north,east (decimal degrees) OR 'auto' to extract from pbf filename")
    ap.add_argument("--keep-service", action="store_true", help="Keep service roads")
    ap.add_argument("--keep-sidewalks", action="store_true", help="Keep sidewalks")
    ap.add_argument("--extraction", action="store_true", help="Use extraction method (faster, requires osmium cli tools)")
    ap.add_argument("--epsilon", type=float, default=0.00002, help="RDP epsilon")
    ap.add_argument("--opt", type=int, default=2, help="Optimization level")
    ap.add_argument("--verbose", action="store_true")
    
    args = ap.parse_args()

    # Parse bbox argument
    if args.bbox == "auto":
        bbox = "auto"
    else:
        s, w, n, e = map(float, args.bbox.split(","))
        bbox = BoundingBox(s, w, n, e)
    
    if args.pbf:
        builder = LZMBuilder()
        outname = builder.from_pbf(args.pbf, bbox, args.keep_service, args.keep_sidewalks,
                                  args.extraction, args.epsilon, args.opt, args.verbose)
        print(f"Generated: {outname}")


if __name__ == "__main__":
    main()