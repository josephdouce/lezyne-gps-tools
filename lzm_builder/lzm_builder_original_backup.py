
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

from typing import List, Tuple, Dict, Optional, Any
import struct, math, argparse, sys, io, os

def round_away_from_zero(x: float) -> int:
    if x >= 0:
        return int(math.floor(x + 0.5))
    else:
        return int(math.ceil(x - 0.5))

class Coordinate:
    __slots__ = ("lat","lon")
    def __init__(self, lat: float, lon: float):
        self.lat = lat
        self.lon = lon

class BoundingBox:
    __slots__ = ("north","east","south","west")
    def __init__(self, south: float, west: float, north: float, east: float):
        self.north = north
        self.east  = east
        self.south = south
        self.west  = west

def bbox_include(b: 'BoundingBox', c: 'Coordinate') -> None:
    if b.north < c.lat: b.north = c.lat
    if b.east  < c.lon: b.east  = c.lon
    if b.south > c.lat: b.south = c.lat
    if b.west  > c.lon: b.west  = c.lon

def bbox_contains(b: 'BoundingBox', c: 'Coordinate') -> bool:
    if b.south > c.lat: return False
    if b.west  > c.lon: return False
    if b.north < c.lat: return False
    if b.east  < c.lon: return False
    return True

def bbox_overlap(r1: 'BoundingBox', r2: 'BoundingBox') -> bool:
    no = (r1.west  > r2.east  or r2.west  > r1.east or
          r1.south > r2.north or r2.south > r1.north)
    return not no

def angle_degrees_difference(a1: float, a2: float) -> float:
    return 180.0 - abs(abs(a1 - a2) - 180.0)

class PolylineEncoder:
    def __init__(self, buffer: bytearray, base: Optional[Coordinate]=None):
        self.buf = buffer
        self.cur = 0
        self.lastLatInit = False
        self.lastLonInit = False
        self.lastLat = 0
        self.lastLon = 0
        if base is not None:
            self.lastLat = round_away_from_zero(base.lat*1e5)
            self.lastLon = round_away_from_zero(base.lon*1e5)
            self.lastLatInit = True
            self.lastLonInit = True

    def _add_part(self, ll: int):
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
        lat_i = round_away_from_zero(lat_f*1e5)
        lon_i = round_away_from_zero(lon_f*1e5)
        self.add_coord_int(lon_i, lat_i)

def perpendicular_distance(p: Coordinate, a: Coordinate, b: Coordinate) -> float:
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

def simplify(points: List[Coordinate], epsilon: float, opt_level: int) -> List[Coordinate]:
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

class PolylineType:
    service     = 0
    RoadMajor   = 1
    RoadHighway = 2
    RoadTertiary= 3
    RoadNormal  = 4
    TrailFoot   = 90
    TrailBike   = 99

WAY_KEY_TO_TYPE = {
    "motorway":   PolylineType.RoadHighway,
    "motorway_link": PolylineType.RoadHighway,
    "trunk":      PolylineType.RoadMajor,
    "primary":    PolylineType.RoadMajor,
    "secondary":  PolylineType.RoadMajor,
    "tertiary":   PolylineType.RoadTertiary,
    "trunk_link": PolylineType.RoadTertiary,
    "tertiary_link": PolylineType.RoadTertiary,
    "unclassified": PolylineType.RoadNormal,
    "residential": PolylineType.RoadNormal,
    "living_street": PolylineType.RoadNormal,
    "bus_guideway": PolylineType.RoadNormal,
    "escape": PolylineType.RoadNormal,
    "raceway": PolylineType.RoadNormal,
    "road": PolylineType.RoadNormal,
    "busway": PolylineType.RoadNormal,
    "corridor": PolylineType.RoadNormal,
    "rest_area": PolylineType.RoadNormal,
    "path": PolylineType.TrailBike,
    "track": PolylineType.TrailBike,
    "cycleway": PolylineType.TrailBike,
    "pedestrian": PolylineType.TrailFoot,
    "footway": PolylineType.TrailFoot,
    "bridleway": PolylineType.TrailBike,
    "steps": PolylineType.TrailFoot,
    "service": PolylineType.service,
    "turning_circle": PolylineType.service,
    "turning_loop": PolylineType.service,
}

GROUP_ORDER = [
    PolylineType.RoadHighway,
    PolylineType.RoadMajor,
    PolylineType.RoadNormal,
    PolylineType.RoadTertiary,
    PolylineType.TrailBike,
    PolylineType.TrailFoot,
    PolylineType.service,
]

class Polyline:
    __slots__=("coordinates",)
    def __init__(self): self.coordinates: List[Coordinate] = []

class GridTile:
    __slots__=(
        "bbox","hasPolylineData","hasCompressedData",
        "polys","counts","compressed","sizes"
    )
    def __init__(self, bbox: BoundingBox):
        self.bbox = bbox
        self.hasPolylineData = False
        self.hasCompressedData = False
        self.polys: Dict[int,List[Polyline]] = {t:[] for t in GROUP_ORDER}
        self.counts: Dict[int,int] = {t:0 for t in GROUP_ORDER}
        self.compressed: Dict[int,bytes] = {}
        self.sizes: Dict[int,int] = {}

def add_way_to_polylines(way_coords: List[Coordinate], ptype: int, tile: GridTile,
                         opt_level: int, epsilon: float):
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

def compress_polylines(polys: List[Polyline]) -> Tuple[bytes, int]:
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

def build_lzm_from_pbf(pbf_path: str, bbox: BoundingBox,
                      keep_service: bool, keep_sidewalks: bool,
                      epsilon: float, opt_level: int, verbose: bool) -> str:
    """Generate LZM file directly from PBF file"""
    import time
    import osmium
    start_time = time.time()
    
    nodes: Dict[int, Coordinate] = {}
    ways_to_include: List[Tuple[int,int,List[int],int,BoundingBox]] = []
    
    # Progress tracking variables
    nodes_processed = 0
    ways_processed = 0
    ways_included = 0
    nodes_rejected_early = 0
    last_progress_time = time.time()
    
    # Spatial optimization: expand bbox slightly for edge cases
    bbox_buffer = 0.01  # ~1km buffer
    bbox_expanded = BoundingBox(
        bbox.south - bbox_buffer, bbox.west - bbox_buffer,
        bbox.north + bbox_buffer, bbox.east + bbox_buffer
    )
    
    class PBFHandler(osmium.SimpleHandler):
        def __init__(self):
            osmium.SimpleHandler.__init__(self)
            
        def node(self, n):
            nonlocal nodes_processed, nodes_rejected_early, last_progress_time
            nodes_processed += 1
            
            lat, lon = float(n.location.lat), float(n.location.lon)
            
            # Quick rejection for obviously out-of-bounds nodes
            if lat < bbox.south - bbox_buffer or lat > bbox.north + bbox_buffer:
                nodes_rejected_early += 1
                return
            
            if lon < bbox.west - bbox_buffer or lon > bbox.east + bbox_buffer:
                nodes_rejected_early += 1
                return
            
            # Keep nodes in expanded bounding box (includes buffer for ways)
            nodes[n.id] = Coordinate(lat, lon)
                
            # Progress reporting every 100k nodes
            if verbose and nodes_processed % 100000 == 0:
                current_time = time.time()
                elapsed = current_time - last_progress_time
                rate = 100000 / elapsed if elapsed > 0 else 0
                efficiency = (1 - nodes_rejected_early / nodes_processed) * 100 if nodes_processed > 0 else 0
                print(f"📊 Processed {nodes_processed:,} nodes ({len(nodes):,} in area, {efficiency:.1f}% efficiency) - {rate:.0f} nodes/sec")
                last_progress_time = current_time
                
        def way(self, w):
            nonlocal ways_processed, ways_included
            ways_processed += 1
            
            tags = dict(w.tags)
            
            # Only process highways
            if 'highway' not in tags:
                return
                
            # Filter way types for appropriate road categories
            is_area = tags.get("area") == "yes"
            if is_area:
                return
                
            is_parking = (tags.get("service") == "parking_aisle")
            is_driveway = (tags.get("service") == "driveway")
            is_private = (tags.get("access") == "private")
            is_sidewalk = (tags.get("footway") == "sidewalk")
            is_crosswalk = (tags.get("footway") == "crossing")
            
            if not keep_service and (is_parking or is_driveway or is_private):
                return
            if not keep_sidewalks and (is_sidewalk or is_crosswalk):
                return
                
            # Get node refs
            node_refs = [ref.ref for ref in w.nodes]
            if len(node_refs) < 2:
                return
                
            # Fast way bounds pre-check using static method
            way_bounds = LZMBuilder._get_way_bounds_fast(node_refs, nodes)
            if not way_bounds:
                return
            
            min_lat, min_lon, max_lat, max_lon = way_bounds
            
            # Quick rejection if way is completely outside target area
            if (max_lat < bbox.south or min_lat > bbox.north or 
                max_lon < bbox.west or min_lon > bbox.east):
                return
                
            # Only create full coordinate objects if way might intersect
            way_nodes = [nodes.get(nid) for nid in node_refs if nid in nodes]
            if len(way_nodes) < 2:
                return
                
            # Determine polyline type
            way_type = WAY_KEY_TO_TYPE.get(tags.get("highway"), PolylineType.RoadNormal)
            
            # Create precise bounding box for final check
            way_bbox = BoundingBox(min_lat, min_lon, max_lat, max_lon)
            
            # Final intersection check with target bbox using fast method
            if LZMBuilder._bbox_overlap_fast(bbox, way_bbox):
                ways_to_include.append((w.id, way_type, node_refs, way_type, way_bbox))
                ways_included += 1
                
            # Progress reporting every 10k ways
            if verbose and ways_processed % 10000 == 0:
                efficiency = (ways_included / ways_processed) * 100 if ways_processed > 0 else 0
                print(f"🛣️  Processed {ways_processed:,} ways ({ways_included:,} included, {efficiency:.1f}% efficiency)")
    
    # Phase 1: Parse PBF file
    if verbose: 
        print(f"⏱️  Phase 1: Parsing PBF file...")
        phase1_start = time.time()
    
    handler = PBFHandler()
    handler.apply_file(pbf_path)
    
    if verbose:
        phase1_time = time.time() - phase1_start
        print(f"✅ Phase 1 complete ({phase1_time:.1f}s)")
        node_efficiency = (1 - nodes_rejected_early / nodes_processed) * 100 if nodes_processed > 0 else 0
        way_efficiency = (len(ways_to_include) / ways_processed) * 100 if ways_processed > 0 else 0
        print(f"📊 Final stats: {nodes_processed:,} nodes processed, {len(nodes):,} kept ({node_efficiency:.1f}% efficiency)")
        print(f"📊 Final stats: {ways_processed:,} ways processed, {len(ways_to_include):,} included ({way_efficiency:.1f}% efficiency)")
        print(f"🚀 Optimization: {nodes_rejected_early:,} nodes rejected early (fast path)")
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
        print(f"⏱️  Total time: {total_time:.1f}s")
        
        # File size info
        import os
        file_size = os.path.getsize(outname)
        print(f"📦 File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
        print(f"🗺️  Coverage: {htiles}×{vtiles} tiles ({htiles*vtiles:,} total)")
        
    return outname


class LZMBuilder:
    """
    LZM file generator for Lezyne GPS devices
    
    This class provides a clean interface for generating LZM map files
    from OpenStreetMap PBF data.
    """
    
    def __init__(self):
        """Initialize LZM builder"""
        pass
    
    @staticmethod
    def _bbox_overlap_fast(bbox1: BoundingBox, bbox2: BoundingBox) -> bool:
        """Fast bounding box overlap check with early rejection"""
        return not (bbox1.east < bbox2.west or bbox1.west > bbox2.east or 
                   bbox1.north < bbox2.south or bbox1.south > bbox2.north)
    
    @staticmethod
    def _point_in_bbox_fast(lat: float, lon: float, bbox: BoundingBox, buffer: float = 0.0) -> bool:
        """Fast point-in-bounding-box check with optional buffer"""
        return (bbox.south - buffer <= lat <= bbox.north + buffer and 
                bbox.west - buffer <= lon <= bbox.east + buffer)
    
    @staticmethod
    def _get_way_bounds_fast(node_refs: list, nodes: dict) -> tuple:
        """Quick way bounds calculation without creating full coordinate objects"""
        lats, lons = [], []
        for nid in node_refs:
            coord = nodes.get(nid)
            if coord:
                lats.append(coord.lat)
                lons.append(coord.lon)
        
        if not lats:
            return None
        
        return min(lats), min(lons), max(lats), max(lons)
        
    def from_pbf(self, pbf_path: str, bbox: BoundingBox, 
                 keep_service: bool = False, keep_sidewalks: bool = False,
                 verbose: bool = False) -> str:
        """
        Generate LZM file from OSM PBF data
        
        Args:
            pbf_path: Path to OSM PBF file
            bbox: Geographic bounding box
            keep_service: Include service roads
            keep_sidewalks: Include sidewalks
            verbose: Print progress information
            
        Returns:
            Path to generated LZM file
        """
        return build_lzm_from_pbf(pbf_path, bbox, keep_service, keep_sidewalks, 
                                 0.00002, 2, verbose)
    
    
    

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Build LZM from PBF")
    ap.add_argument("--pbf", help="Path to input .pbf file")
    ap.add_argument("--bbox", required=True, help="south,west,north,east (decimal degrees)")
    ap.add_argument("--keep-service", action="store_true", help="Keep service roads")
    ap.add_argument("--keep-sidewalks", action="store_true", help="Keep sidewalks")
    ap.add_argument("--epsilon", type=float, default=0.00002, help="RDP epsilon")
    ap.add_argument("--opt", type=int, default=2, help="Optimization level")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    s,w,n,e = map(float, args.bbox.split(","))
    bbox = BoundingBox(s,w,n,e)
    
    if args.pbf:
        outname = build_lzm_from_pbf(args.pbf, bbox, args.keep_service, args.keep_sidewalks,
                                    args.epsilon, args.opt, args.verbose)
    else:
        print("Error: Specify either --pbf input file")
        return
        
    print(f"Generated: {outname}")

if __name__ == "__main__":
    main()
