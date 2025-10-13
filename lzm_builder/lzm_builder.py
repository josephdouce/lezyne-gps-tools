"""
Refactored LZM Builder

Clean, service-oriented LZM file generator for Lezyne GPS devices.
This orchestrates generating LZM map files from OpenStreetMap data using
a proper service layer architecture.
"""

import argparse
import os
import time
from typing import Union

# Import data models
from models.data_classes import BoundingBox

# Import services
from services.progress_logger import ProgressLogger
from services.osm_parser import OSMParser
from services.grid_builder import GridBuilder
from services.lzm_writer import LZMWriter

# Import utilities
from utils.geographic import pluck_bbox_from_filename, filename_from_bbox, extract_smaller_osm_from_larger_osm


class LZMBuilder:
    """
    LZM file generator for Lezyne GPS devices
    
    This class orchestrates generating LZM map files from OpenStreetMap data
    using a clean service layer architecture with proper separation of concerns.
    """
    
    def __init__(self, verbose: bool = False):
        """
        Initialize LZM builder with services.
        
        Args:
            verbose: Enable progress reporting
        """
        self._logger = ProgressLogger(verbose)
        self._osm_parser = OSMParser(self._logger)
        self._grid_builder = GridBuilder(self._logger)
        self._lzm_writer = LZMWriter(self._logger)
        
    def from_osm(self, osm_path: str, bbox: Union[BoundingBox, str] = "auto", 
                 keep_service: bool = False, keep_sidewalks: bool = False,
                 extraction: bool = False, epsilon: float = 0.00002, opt_level: int = 2,
                 verbose: bool = False) -> str:
        """
        Generate LZM file from OSM data - Main public interface
        
        Args:
            osm_path: Path to OSM file (.pbf or .osm)
            bbox: Geographic bounding box or "auto" to extract from filename
            keep_service: Include service roads
            keep_sidewalks: Include sidewalks
            extraction: Use extraction method (faster, requires osmium cli tools)
            epsilon: RDP epsilon for simplification (0.00002 default)
            opt_level: Optimization level (0-3, default 2)
            verbose: Print progress information (overrides constructor setting)
            
        Returns:
            Path to generated LZM file
        """
        # Update logger verbosity if explicitly set
        if verbose and not self._logger.verbose:
            self._logger.verbose = verbose
        
        start_time = time.time()
        
        try:
            # Handle auto bbox detection
            if isinstance(bbox, str) and bbox == "auto":
                return self._build_lzm_from_osm_with_auto_bbox(osm_path, keep_service, keep_sidewalks,
                                                   extraction, epsilon, opt_level)
            
            # Handle extraction method
            if extraction:
                return self._build_lzm_from_osm_with_extraction(osm_path, bbox, keep_service, keep_sidewalks,
                                                         epsilon, opt_level)
            
            # Direct build
            return self._build_lzm_from_osm(osm_path, bbox, keep_service, keep_sidewalks,
                                           bbox_filtering=True, epsilon=epsilon, 
                                           opt_level=opt_level)
        
        finally:
            total_time = time.time() - start_time
            self._logger.log(f"GENERATION COMPLETE! Total time: {total_time:.1f}s", "📋")
    
    def _build_lzm_from_osm_with_auto_bbox(self, osm_path: str,
                                keep_service: bool, keep_sidewalks: bool,
                                extraction: bool, epsilon: float, opt_level: int) -> str:
        """
        Convenience method that handles auto bbox detection from filename
        """
        if extraction:
            raise ValueError("Cannot use extraction method with bbox='auto'. Auto mode processes the whole OSM file, making extraction redundant.")
        
        try:
            bbox = pluck_bbox_from_filename(osm_path)
            self._logger.log(f"Auto-detected bbox from filename: {bbox}")
        except ValueError as e:
            raise ValueError(f"Cannot auto-detect bounding box from filename '{osm_path}': {e}")
        
        # Call the core build method with no bbox filtering (process whole OSM file)
        return self._build_lzm_from_osm(osm_path, bbox, keep_service, keep_sidewalks,
                                       bbox_filtering=False, epsilon=epsilon,
                                       opt_level=opt_level)

    def _build_lzm_from_osm_with_extraction(self, osm_path: str, bbox: BoundingBox,
                                     keep_service: bool, keep_sidewalks: bool,
                                     epsilon: float, opt_level: int) -> str:
        """
        Convenience method that extracts a smaller PBF then calls the core build method
        """
        extracted_pbf_file = filename_from_bbox(bbox, prefix="extracted", suffix=".osm.pbf", include_path=True)

        with self._logger.phase(f"Extracting smaller OSM/PBF to {extracted_pbf_file}"):
            success = extract_smaller_osm_from_larger_osm(osm_path, extracted_pbf_file, bbox)
            if not success:
                raise RuntimeError("Failed to extract smaller PBF")
            
        # Call the core build method with no bbox filtering (extracted PBF is already filtered)
        try:
            outname = self._build_lzm_from_osm(extracted_pbf_file, bbox, keep_service, keep_sidewalks,
                                             bbox_filtering=False, epsilon=epsilon,
                                             opt_level=opt_level)
        finally:
            # Clean up temporary file
            try:
                os.remove(extracted_pbf_file)
                self._logger.log(f"Removed temporary file {extracted_pbf_file}", "🧹")
            except OSError as e:
                self._logger.log(f"Warning: Failed to remove temporary file {extracted_pbf_file}: {e}", "⚠️")
        
        return outname

    def _build_lzm_from_osm(self, osm_path: str, bbox: BoundingBox,
                          keep_service: bool, keep_sidewalks: bool, bbox_filtering: bool,
                          epsilon: float, opt_level: int) -> str:
        """
        Generate LZM file directly from OSM file using service layer architecture.
        
        This method is now clean and focused on orchestration only.
        """
        # Prepare parsing options
        parsing_options = {
            'keep_service': keep_service,
            'keep_sidewalks': keep_sidewalks,
            'bbox_filtering': bbox_filtering,
            'bbox_buffer': 0.01  # ~1km buffer for edge cases
        }
        
        # Phase 1: Parse OSM file
        osm_data = self._osm_parser.parse(osm_path, bbox, parsing_options)
        
        # Phase 2 & 3: Build and populate grid
        grid_result = self._grid_builder.build(osm_data, bbox, opt_level, epsilon)
        
        # Phase 4 & 5: Compress and write LZM file
        return self._lzm_writer.write(grid_result, bbox)


# Backward compatibility - keep the old data classes available at module level
from models.data_classes import Coordinate, BoundingBox, Polyline, GridTile

__all__ = ['LZMBuilder', 'Coordinate', 'BoundingBox', 'Polyline', 'GridTile']


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Command line interface for the LZM builder."""
    ap = argparse.ArgumentParser(description="Build LZM from PBF")

    ap.add_argument("--osm", required=True, help="Path to input OSM file (.pbf or .osm)")
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
    
    if args.osm:
        builder = LZMBuilder(verbose=args.verbose)
        outname = builder.from_osm(args.osm, bbox, args.keep_service, args.keep_sidewalks,
                                  args.extraction, args.epsilon, args.opt, args.verbose)
        print(f"Generated: {outname}")


if __name__ == "__main__":
    main()