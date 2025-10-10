"""
OSM Parser Service

Clean, focused service for parsing OSM files.
Progress reporting is handled separately via ProgressLogger.
"""

import time
from typing import Dict, List, Tuple, TYPE_CHECKING

import osmium

if TYPE_CHECKING:
    from models.data_classes import BoundingBox, Coordinate

from utils.constants import PolylineType, WAY_KEY_TO_TYPE
from utils.geographic import bbox_overlap_fast, get_way_bounds_fast
from .progress_logger import ProgressLogger, PeriodicReporter


class OSMParsingResult:
    """Data class to hold OSM parsing results."""
    def __init__(self):
        self.nodes: Dict[int, 'Coordinate'] = {}
        self.ways_to_include: List[Tuple[int, int, List[int], int, 'BoundingBox']] = []
        self.stats = {
            'nodes_processed': 0,
            'ways_processed': 0,
            'ways_included': 0,
            'nodes_rejected_early': 0,
            'nodes_kept': 0
        }


class OSMParser:
    """
    Service for parsing OSM files and extracting LZM-relevant data.
    
    Focused solely on parsing logic - progress reporting is handled
    by the injected ProgressLogger.
    """
    
    def __init__(self, logger: ProgressLogger):
        self._logger = logger
        
    def parse(self, osm_path: str, bbox: 'BoundingBox', options: dict) -> OSMParsingResult:
        """
        Parse OSM file and extract relevant data for LZM generation.
        
        Args:
            osm_path: Path to OSM file
            bbox: Bounding box for filtering
            options: Parsing options (keep_service, keep_sidewalks, etc.)
            
        Returns:
            OSMParsingResult containing nodes and ways
        """
        result = OSMParsingResult()
        
        bbox_filter = options.get('bbox_filtering', True)
        bbox_buffer = options.get('bbox_buffer', 0.01)
        
        handler = _OSMHandler(
            bbox=bbox,
            bbox_buffer=bbox_buffer,
            bbox_filter=bbox_filter,
            keep_service=options.get('keep_service', False),
            keep_sidewalks=options.get('keep_sidewalks', False),
            logger=self._logger,
            result=result
        )
        
        with self._logger.phase("Parsing OSM file"):
            handler.apply_file(osm_path)
        
        # Update final stats
        result.stats['nodes_kept'] = len(result.nodes)
        
        self._logger.log_stats(result.stats, "Final parsing stats - ")
        
        return result


class _OSMHandler(osmium.SimpleHandler):
    """
    Internal OSM handler - implementation detail of OSMParser.
    Progress reporting delegated to ProgressLogger.
    """
    
    def __init__(self, bbox: 'BoundingBox', bbox_buffer: float, bbox_filter: bool,
                 keep_service: bool, keep_sidewalks: bool, 
                 logger: ProgressLogger, result: OSMParsingResult):
        osmium.SimpleHandler.__init__(self)
        self.bbox = bbox
        self.bbox_buffer = bbox_buffer
        self.bbox_filter = bbox_filter
        self.keep_service = keep_service
        self.keep_sidewalks = keep_sidewalks
        self._logger = logger
        self.result = result
        
        # Set up periodic reporting
        self.node_reporter = PeriodicReporter(
            logger, 100000, 
            "Processed {count:,} nodes ({nodes_kept:,} in area, {efficiency:.1f}% efficiency) - {rate:.0f} nodes/sec"
        )
        self.way_reporter = PeriodicReporter(
            logger, 10000,
            "Processed {count:,} ways ({ways_included:,} included, {efficiency:.1f}% efficiency)"
        )
            
    def node(self, n):
        """Process a node from the OSM file."""
        from models.data_classes import Coordinate
        
        self.result.stats['nodes_processed'] += 1
        
        lat, lon = float(n.location.lat), float(n.location.lon)

        # Bounding box filtering with early rejection
        if self.bbox_filter:
            if (lat < self.bbox.south - self.bbox_buffer or 
                lat > self.bbox.north + self.bbox_buffer or
                lon < self.bbox.west - self.bbox_buffer or 
                lon > self.bbox.east + self.bbox_buffer):
                self.result.stats['nodes_rejected_early'] += 1
                return
        
        # Keep nodes in expanded bounding box
        self.result.nodes[n.id] = Coordinate(lat, lon)
        
        # Report progress
        efficiency = (1 - self.result.stats['nodes_rejected_early'] / self.result.stats['nodes_processed']) * 100 if self.result.stats['nodes_processed'] > 0 else 0
        self.node_reporter.increment(
            nodes_kept=len(self.result.nodes),
            efficiency=efficiency
        )
            
    def way(self, w):
        """Process a way from the OSM file."""
        from models.data_classes import BoundingBox
        
        self.result.stats['ways_processed'] += 1
        
        tags = dict(w.tags)
        
        # Only process highways
        if 'highway' not in tags:
            return
            
        # Filter way types
        if not self._should_include_way(tags):
            return
            
        # Get node refs
        node_refs = [ref.ref for ref in w.nodes]
        if len(node_refs) < 2:
            return

        # Get way bounds
        way_bounds = get_way_bounds_fast(node_refs, self.result.nodes)
        if not way_bounds:
            return
    
        min_lat, min_lon, max_lat, max_lon = way_bounds
        way_bbox = BoundingBox(min_lat, min_lon, max_lat, max_lon)

        # Determine polyline type
        way_type = WAY_KEY_TO_TYPE.get(tags.get("highway"), PolylineType.ROAD_NORMAL)

        # Apply bbox filtering if enabled
        if self.bbox_filter:
            if not self._way_intersects_bbox(way_bbox, node_refs):
                return
                
        # Include the way
        self.result.ways_to_include.append((w.id, way_type, node_refs, way_type, way_bbox))
        self.result.stats['ways_included'] += 1

        # Report progress
        efficiency = (self.result.stats['ways_included'] / self.result.stats['ways_processed']) * 100 if self.result.stats['ways_processed'] > 0 else 0
        self.way_reporter.increment(
            ways_included=self.result.stats['ways_included'],
            efficiency=efficiency
        )
    
    def _should_include_way(self, tags: dict) -> bool:
        """Determine if a way should be included based on its tags."""
        is_area = tags.get("area") == "yes"
        if is_area:
            return False
            
        is_parking = (tags.get("service") == "parking_aisle")
        is_driveway = (tags.get("service") == "driveway")
        is_private = (tags.get("access") == "private")
        is_sidewalk = (tags.get("footway") == "sidewalk")
        is_crosswalk = (tags.get("footway") == "crossing")
        
        if not self.keep_service and (is_parking or is_driveway or is_private):
            return False
        if not self.keep_sidewalks and (is_sidewalk or is_crosswalk):
            return False
            
        return True
    
    def _way_intersects_bbox(self, way_bbox: 'BoundingBox', node_refs: List[int]) -> bool:
        """Check if way intersects with target bbox."""
        # Quick rejection if way is completely outside target area
        if (way_bbox.north < self.bbox.south or way_bbox.south > self.bbox.north or 
            way_bbox.east < self.bbox.west or way_bbox.west > self.bbox.east):
            return False
            
        # Only create full coordinate objects if way might intersect
        way_nodes = [self.result.nodes.get(nid) for nid in node_refs if nid in self.result.nodes]
        if len(way_nodes) < 2:
            return False
            
        # Final intersection check
        return bbox_overlap_fast(self.bbox, way_bbox)