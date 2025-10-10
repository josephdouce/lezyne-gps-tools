"""
Grid Builder Service

Service for building spatial grids and assigning polylines to tiles.
"""

import math
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from models.data_classes import BoundingBox, GridTile, Coordinate

from utils.constants import GROUP_ORDER
from utils.geographic import angle_degrees_difference
from .progress_logger import ProgressLogger, PeriodicReporter
from .osm_parser import OSMParsingResult


class GridBuildingResult:
    """Data class to hold grid building results."""
    def __init__(self, grid: List[List['GridTile']], htiles: int, vtiles: int):
        self.grid = grid
        self.htiles = htiles
        self.vtiles = vtiles


class GridBuilder:
    """
    Service for building spatial grids from OSM data.
    
    Handles grid creation and polyline assignment with clean separation
    from progress reporting.
    """
    
    def __init__(self, logger: ProgressLogger):
        self._logger = logger
    
    def build(self, osm_data: OSMParsingResult, bbox: 'BoundingBox', opt_level: int = 2, epsilon: float = 0.00002) -> GridBuildingResult:
        """
        Build spatial grid from OSM parsing results.
        
        Args:
            osm_data: Results from OSM parsing
            bbox: Bounding box for the grid
            opt_level: Optimization level for polyline processing
            epsilon: Simplification epsilon for polylines
            
        Returns:
            GridBuildingResult containing the populated grid
        """
        # Phase 1: Create grid structure
        with self._logger.phase("Building tile grid"):
            grid_result = self._create_grid_structure(bbox)
        
        # Phase 2: Populate grid with ways
        with self._logger.phase("Populating grid with ways"):
            self._populate_grid_with_ways(grid_result, osm_data, bbox, opt_level, epsilon)
        
        return grid_result
    
    def _create_grid_structure(self, bbox: 'BoundingBox') -> GridBuildingResult:
        """Create the basic grid structure."""
        from models.data_classes import GridTile, BoundingBox
        
        south, west, north, east = bbox.south, bbox.west, bbox.north, bbox.east
        htiles = int(round((east - west) * 100.0))
        vtiles = int(round((north - south) * 100.0))

        self._logger.log(f"Grid dimensions: {htiles} × {vtiles} = {htiles * vtiles:,} tiles", "📐")

        grid: List[List[GridTile]] = []
        for y in range(vtiles):  # rows (south→north)
            row = []
            for x in range(htiles):  # columns (west→east)
                tbox = BoundingBox(
                    south + y * 0.01, 
                    west + x * 0.01, 
                    south + (y + 1) * 0.01, 
                    west + (x + 1) * 0.01
                )
                row.append(GridTile(tbox))
            grid.append(row)

        return GridBuildingResult(grid, htiles, vtiles)
    
    def _populate_grid_with_ways(self, grid_result: GridBuildingResult, osm_data: OSMParsingResult, 
                                bbox: 'BoundingBox', opt_level: int, epsilon: float):
        """Populate the grid with ways from OSM data."""
        # Import here to avoid circular imports
        from services.lzm_processing import add_way_to_polylines
        
        ways_reporter = PeriodicReporter(
            self._logger, 1000,
            "Assigned {count:,}/{total:,} ways to tiles"
        )
        
        south, west = bbox.south, bbox.west
        
        for (_, ptype, refs, _, bb) in osm_data.ways_to_include:
            south_i = max(0, int(math.floor(angle_degrees_difference(bb.south, south) * 100)) - 1)
            west_i = max(0, int(math.floor(angle_degrees_difference(bb.west, west) * 100)) - 1)
            height = int(math.ceil(angle_degrees_difference(bb.north, bb.south) * 100))
            width = int(math.ceil(angle_degrees_difference(bb.east, bb.west) * 100))
            north_i = min(grid_result.vtiles - 1, south_i + height + 1)
            east_i = min(grid_result.htiles - 1, west_i + width + 1)
            
            coords: List['Coordinate'] = []
            for r in refs:
                c = osm_data.nodes.get(r)
                if c is not None:
                    coords.append(c)
            
            if len(coords) < 2:
                continue
                
            for y in range(south_i, north_i + 1):
                for x in range(west_i, east_i + 1):
                    add_way_to_polylines(coords, ptype, grid_result.grid[y][x], opt_level, epsilon)
            
            ways_reporter.increment(total=len(osm_data.ways_to_include))