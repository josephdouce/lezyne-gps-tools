"""
LZM Writer Service

Service for writing LZM binary files from grid data.
"""

import os
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.data_classes import BoundingBox

from utils.constants import GROUP_ORDER
from utils.geographic import filename_from_bbox
from .progress_logger import ProgressLogger, PeriodicReporter
from .grid_builder import GridBuildingResult
from .lzm_processing import compress_polylines


class LZMWriter:
    """
    Service for writing LZM files from grid data.
    
    Handles compression and binary file generation with clean separation
    from progress reporting.
    """
    
    def __init__(self, logger: ProgressLogger):
        self._logger = logger
    
    def write(self, grid_result: GridBuildingResult, bbox: 'BoundingBox') -> str:
        """
        Write LZM file from grid data.
        
        Args:
            grid_result: Grid building results containing populated tiles
            bbox: Bounding box for filename generation
            
        Returns:
            Path to the generated LZM file
        """
        # Phase 1: Compress polylines
        with self._logger.phase("Compressing polylines"):
            self._compress_grid_polylines(grid_result)
        
        # Phase 2: Write binary file
        outname = filename_from_bbox(bbox)
        with self._logger.phase("Writing LZM file"):
            self._write_binary_file(grid_result, outname)
        
        # Log file information
        file_size = os.path.getsize(outname)
        self._logger.log(f"Output: {outname}", "📁")
        self._logger.log(f"File size: {file_size:,} bytes ({file_size/1024:.1f} KB)", "📦")
        self._logger.log(f"Coverage: {grid_result.htiles}×{grid_result.vtiles} tiles ({grid_result.htiles*grid_result.vtiles:,} total)", "🗺️")
        
        return outname
    
    def _compress_grid_polylines(self, grid_result: GridBuildingResult):
        """Compress polylines in all grid tiles."""
        tiles_compressed = 0
        total_tiles = grid_result.htiles * grid_result.vtiles
        
        compression_reporter = PeriodicReporter(
            self._logger, 1000,
            "Compressed {count:,}/{total:,} tiles"
        )
        
        for y in range(grid_result.vtiles):
            for x in range(grid_result.htiles):
                tile = grid_result.grid[y][x]
                for t in GROUP_ORDER:
                    if len(tile.polys[t]) > 0:
                        data, size = compress_polylines(tile.polys[t])
                        tile.compressed[t] = data
                        tile.sizes[t] = size
                        tile.counts[t] = len(tile.polys[t])
                
                tiles_compressed += 1
                compression_reporter.increment(total=total_tiles)
    
    def _write_binary_file(self, grid_result: GridBuildingResult, outname: str):
        """Write the binary LZM file."""
        with open(outname, "wb") as out:
            # Write header with placeholder offsets
            section1_off = 16
            section2_off = 0
            section3_off = 0
            section4_off = 0
            out.write(struct.pack("<IIII", section1_off, section2_off, section3_off, section4_off))

            # Section 1: Tile Directory
            file_offset = 0
            for y in range(grid_result.vtiles):
                for x in range(grid_result.htiles):
                    tile = grid_result.grid[y][x]
                    num_groups = len([t for t in GROUP_ORDER if len(tile.polys[t]) > 0])
                    out.write(struct.pack("<IH", file_offset, num_groups))
                    file_offset += num_groups * 5

            # Section 2: Tile→String IDs
            section2_off = out.tell()
            file_offset = 0
            for y in range(grid_result.vtiles):
                for x in range(grid_result.htiles):
                    tile = grid_result.grid[y][x]
                    for t in GROUP_ORDER:
                        if len(tile.polys[t]) > 0:
                            out.write(struct.pack("<IB", file_offset, t))
                            file_offset += 1

            # Section 3: String Index
            section3_off = out.tell()
            file_offset = 0
            for y in range(grid_result.vtiles):
                for x in range(grid_result.htiles):
                    tile = grid_result.grid[y][x]
                    for t in GROUP_ORDER:
                        if len(tile.polys[t]) > 0:
                            size = tile.sizes[t]
                            out.write(struct.pack("<IH", file_offset, size))
                            file_offset += size

            # Section 4: Polyline Data
            section4_off = out.tell()
            for y in range(grid_result.vtiles):
                for x in range(grid_result.htiles):
                    tile = grid_result.grid[y][x]
                    for t in GROUP_ORDER:
                        if len(tile.polys[t]) > 0:
                            out.write(tile.compressed[t])

            # Update header with actual offsets
            out.seek(0)
            out.write(struct.pack("<IIII", section1_off, section2_off, section3_off, section4_off))