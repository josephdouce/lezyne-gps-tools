"""
PBF Handler Service

This service handles parsing of OpenStreetMap PBF files specifically for LZM generation.
It filters and extracts relevant geographic data (nodes and ways) within specified 
bounding boxes, optimizing for the LZM file format requirements.

Optionally you can instruct the handleer to not filter on a bounding box, but keep all nodes and ways.
"""

import time
from typing import Dict, List, Tuple, TYPE_CHECKING

import osmium

if TYPE_CHECKING:
    from lzm_builder import BoundingBox, Coordinate

from lzm_constants import PolylineType, WAY_KEY_TO_TYPE
from lzm_utils import bbox_overlap_fast, get_way_bounds_fast


class PBFHandler(osmium.SimpleHandler):
    """
    Service class for parsing PBF files and extracting LZM-relevant data.
    
    This handler processes OpenStreetMap PBF files, filtering nodes and ways
    that are relevant for generating LZM offline map files. It implements
    spatial filtering, progress tracking, and road type classification.
    """
    
    def __init__(self, bbox: 'BoundingBox', bbox_buffer: float, nodes: dict, 
                 ways_to_include: list, bbox_filter: bool, keep_service: bool, keep_sidewalks: bool, verbose: bool):
        """
        Initialize the PBF handler service.
        
        Args:
            bbox: Geographic bounding box for filtering
            bbox_buffer: Buffer distance around bounding box  
            nodes: Dictionary to store processed nodes
            ways_to_include: List to store processed ways
            keep_service: Whether to include service roads
            keep_sidewalks: Whether to include sidewalks
            verbose: Whether to print progress information
        """
        osmium.SimpleHandler.__init__(self)
        self.bbox = bbox
        self.bbox_buffer = bbox_buffer
        self.nodes = nodes
        self.ways_to_include = ways_to_include
        self.bbox_filter = bbox_filter
        self.keep_service = keep_service
        self.keep_sidewalks = keep_sidewalks
        self.verbose = verbose
        
        # Progress tracking
        self.nodes_processed = 0
        self.ways_processed = 0
        self.ways_included = 0
        self.nodes_rejected_early = 0
        self.last_progress_time = time.time()
            
    def node(self, n):
        """
        Process a node from the PBF file.
        
        Filters nodes based on geographic bounding box and stores
        relevant nodes for later way processing.
        
        Args:
            n: OSM node object from osmium
        """
        # Import here to avoid circular imports
        from lzm_builder import Coordinate
        
        self.nodes_processed += 1
        
        lat, lon = float(n.location.lat), float(n.location.lon)

        """Bounding box filtering with early rejection."""
        """Only filter if bbox_filter is True."""
        if self.bbox_filter:
            # Quick rejection for obviously out-of-bounds nodes
            if lat < self.bbox.south - self.bbox_buffer or lat > self.bbox.north + self.bbox_buffer:
                self.nodes_rejected_early += 1
                return

            if lon < self.bbox.west - self.bbox_buffer or lon > self.bbox.east + self.bbox_buffer:
                self.nodes_rejected_early += 1
                return
        
        # Keep nodes in expanded bounding box (includes buffer for ways)
        self.nodes[n.id] = Coordinate(lat, lon)
            
        # Progress reporting every 100k nodes
        if self.verbose and self.nodes_processed % 100000 == 0:
            current_time = time.time()
            elapsed = current_time - self.last_progress_time
            rate = 100000 / elapsed if elapsed > 0 else 0
            efficiency = (1 - self.nodes_rejected_early / self.nodes_processed) * 100 if self.nodes_processed > 0 else 0
            print(f"📊 Processed {self.nodes_processed:,} nodes ({len(self.nodes):,} in area, {efficiency:.1f}% efficiency) - {rate:.0f} nodes/sec")
            self.last_progress_time = current_time
            
    def way(self, w):
        """
        Process a way from the PBF file.
        
        Filters ways based on road type, geographic location, and other criteria.
        Classifies roads according to LZM polyline types.
        
        Args:
            w: OSM way object from osmium
        """
        # Import here to avoid circular imports
        from lzm_builder import BoundingBox
        
        self.ways_processed += 1
        
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
        
        if not self.keep_service and (is_parking or is_driveway or is_private):
            return
        if not self.keep_sidewalks and (is_sidewalk or is_crosswalk):
            return
            
        # Get node refs
        node_refs = [ref.ref for ref in w.nodes]
        if len(node_refs) < 2:
            return

        # Get way bounds quickly
        way_bounds = get_way_bounds_fast(node_refs, self.nodes)
        if not way_bounds:
            return
    
        min_lat, min_lon, max_lat, max_lon = way_bounds

        way_bbox = BoundingBox(min_lat, min_lon, max_lat, max_lon)

        # Determine polyline type using constants mapping
        way_type = WAY_KEY_TO_TYPE.get(tags.get("highway"), PolylineType.ROAD_NORMAL)

        # Yes we filter on bbox
        if self.bbox_filter:
            
            # Quick rejection if way is completely outside target area
            if (max_lat < self.bbox.south or min_lat > self.bbox.north or 
                max_lon < self.bbox.west or min_lon > self.bbox.east):
                return
                
            # Only create full coordinate objects if way might intersect
            way_nodes = [self.nodes.get(nid) for nid in node_refs if nid in self.nodes]
            if len(way_nodes) < 2:
                return
                
            # Final intersection check with target bbox using utility function
            if bbox_overlap_fast(self.bbox, way_bbox):
                self.ways_to_include.append((w.id, way_type, node_refs, way_type, way_bbox))
                self.ways_included += 1
        else:
            # No bbox filtering, include all ways that pass previous checks
            self.ways_to_include.append((w.id, way_type, node_refs, way_type, way_bbox))
            self.ways_included += 1

        # Progress reporting every 10k ways
        if self.verbose and self.ways_processed % 10000 == 0:
            efficiency = (self.ways_included / self.ways_processed) * 100 if self.ways_processed > 0 else 0
            print(f"🛣️  Processed {self.ways_processed:,} ways ({self.ways_included:,} included, {efficiency:.1f}% efficiency)")
    
    def get_processing_stats(self) -> Dict[str, int]:
        """
        Get processing statistics from the handler.
        
        Returns:
            Dictionary containing processing statistics
        """
        return {
            'nodes_processed': self.nodes_processed,
            'ways_processed': self.ways_processed,
            'ways_included': self.ways_included,
            'nodes_rejected_early': self.nodes_rejected_early,
            'nodes_kept': len(self.nodes)
        }