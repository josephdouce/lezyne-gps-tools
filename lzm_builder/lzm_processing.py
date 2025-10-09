"""
LZM Processing Module

This module contains the core processing functions for generating LZM files.
These functions handle the main algorithmic work of converting OSM data into
the LZM format used by Lezyne GPS devices.
"""

import math
import os
from pathlib import Path
import struct
import time
from typing import Dict, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from lzm_builder import BoundingBox, Coordinate, GridTile, Polyline

from lzm_constants import GROUP_ORDER

from lzm_utils import (
    angle_degrees_difference,
    extract_smaller_pbf_from_larger_pbf,
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

def build_lzm_from_extracted_pbf(pbf_path: str, bbox: 'BoundingBox',
                      keep_service: bool, keep_sidewalks: bool,
                      epsilon: float, opt_level: int, verbose: bool) -> str:
    """Generate a LZM by first extracting a smaller PBF from a larger one."""
    """Then build the LZM from that smaller PBF."""
    """This utilizes the cli utilities to extract the smaller PBF very quickly."""
    """Then it is just a matter of compressing everything in the small PBF to LZM."""
    """No bbox filtering is done in the LZM build step since the PBF is already filtered."""


    extracted_pbf_file = os.path.join(
        os.getcwd(),
        f"extracted_{bbox.south:.2f}_{bbox.west:.2f}_{bbox.north:.2f}_{bbox.east:.2f}.osm.pbf"
    )

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
        
    outname = build_lzm_from_pbf(extracted_pbf_file, bbox, keep_service, keep_sidewalks,
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




def build_lzm_from_pbf(pbf_path: str, bbox: 'BoundingBox',
                      keep_service: bool, keep_sidewalks: bool, bbox_filtering: bool,
                      epsilon: float, opt_level: int, verbose: bool) -> str:
    """Generate LZM file directly from PBF file"""
    # Import here to avoid circular imports
    from lzm_builder import BoundingBox, Coordinate, GridTile, PBFHandler
    
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

    outname = f"mf_{south:.2f}_{west:.2f}_{north:.2f}_{east:.2f}.lzm"
    
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


def build_lzm_from_pbf_with_auto_bbox(pbf_path: str, bbox: 'BoundingBox | str' = "auto", 
                                     keep_service: bool = False, keep_sidewalks: bool = False,
                                     extraction: bool = False, epsilon: float = 0.00002, opt_level: int = 2,
                                     verbose: bool = False) -> str:
    """
    Standalone function interface for building LZM files from PBF data with auto bbox detection.
    
    This is a convenience function that provides the same functionality as LZMBuilder.from_pbf()
    but as a standalone function. Supports auto-detection of bounding box from filename.
    
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
        
    Raises:
        ValueError: If bbox="auto" but filename doesn't contain bbox pattern
    """
    from lzm_builder import LZMBuilder
    builder = LZMBuilder()
    return builder.from_pbf(pbf_path, bbox, keep_service, keep_sidewalks,
                           extraction, epsilon, opt_level, verbose)