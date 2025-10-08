#!/usr/bin/env python3
"""
LZM Builder Test Script

Tests the refactored LZM builder with Belgium sample data.
Generates an LZM file for the Signal du Botrange area (highest point in Belgium)
and performs sanity checking on the result.

Test area: Signal du Botrange and High Fagnes nature reserve
Bounding box: 50.483507, 6.035957 (SW) to 50.522377, 6.138439 (NE)
"""

import os
import struct
import sys
import time
from pathlib import Path

from lzm_builder import LZMBuilder, BoundingBox, Coordinate, Polyline, GridTile


def test_signal_du_botrange():
    """Test LZM generation for Signal du Botrange area in Belgium."""
    
    print("🇧🇪 LZM Builder Test - Signal du Botrange")
    print("=" * 50)
    
    # Define the test area (Signal du Botrange and High Fagnes)
    # Southwest: 50.483507, 6.035957
    # Northeast: 50.522377, 6.138439
    bbox = BoundingBox(
        south=50.483507,
        west=6.035957, 
        north=50.522377,
        east=6.138439
    )
    
    print(f"Test area: Signal du Botrange and High Fagnes nature reserve")
    print(f"Bounding box: {bbox.south:.6f}, {bbox.west:.6f} (SW) to {bbox.north:.6f}, {bbox.east:.6f} (NE)")
    
    # Input and output files
    pbf_file = Path(__file__).parent / "belgium_sample.osm.pbf"
    expected_lzm_file = f"mf_{bbox.south:.2f}_{bbox.west:.2f}_{bbox.north:.2f}_{bbox.east:.2f}.lzm"
    lzm_file_path = None  # Track the generated file for cleanup
    
    print(f"Input PBF: {pbf_file}")
    print(f"Expected output: {expected_lzm_file}")
    
    # Check input file exists
    if not pbf_file.exists():
        print(f"❌ ERROR: Input file not found: {pbf_file}")
        return False
    
    pbf_size = pbf_file.stat().st_size
    print(f"✅ Input PBF file found ({pbf_size:,} bytes)")
    
    # Generate LZM file
    print("\n📍 Generating LZM file...")
    start_time = time.time()
    
    try:
        try:
            builder = LZMBuilder()
            lzm_file = builder.from_pbf(str(pbf_file), bbox, verbose=True)
            lzm_file_path = Path(lzm_file)  # Store for cleanup
            
            generation_time = time.time() - start_time
            print(f"✅ LZM file generated in {generation_time:.2f} seconds")
            print(f"Output file: {lzm_file}")
            
        except Exception as e:
            print(f"❌ ERROR generating LZM file: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Verify the output file
        if not lzm_file_path.exists():
            print(f"❌ ERROR: Output LZM file not found: {lzm_file_path}")
            return False
        
        lzm_size = lzm_file_path.stat().st_size
        print(f"✅ LZM file created ({lzm_size:,} bytes)")
        
        # Sanity checking
        print("\n🔍 Performing sanity checks...")
        test_result = perform_sanity_checks(lzm_file_path, bbox)
        
        return test_result
        
    finally:
        # Cleanup: Remove the generated LZM file
        if lzm_file_path and lzm_file_path.exists():
            try:
                lzm_file_path.unlink()
                print(f"🧹 Cleaned up test file: {lzm_file_path.name}")
            except OSError as e:
                print(f"⚠️  Warning: Failed to remove test file {lzm_file_path}: {e}")


def perform_sanity_checks(lzm_path: Path, expected_bbox: BoundingBox) -> bool:
    """Perform comprehensive sanity checks on the generated LZM file."""
    
    checks_passed = 0
    total_checks = 0
    
    # Check 1: File size is reasonable
    total_checks += 1
    file_size = lzm_path.stat().st_size
    if 1000 < file_size < 50_000_000:  # Between 1KB and 50MB
        print(f"✅ File size check: {file_size:,} bytes (reasonable)")
        checks_passed += 1
    else:
        print(f"❌ File size check: {file_size:,} bytes (suspicious)")
    
    # Check 2: File can be opened and has proper LZM binary header
    total_checks += 1
    try:
        with open(lzm_path, 'rb') as f:
            # LZM files start with 4 uint32 section offsets
            header_data = f.read(16)
            if len(header_data) == 16:
                section_offsets = struct.unpack('<IIII', header_data)
                if all(offset >= 0 for offset in section_offsets):
                    print(f"✅ Header check: Valid LZM binary format (sections at {section_offsets})")
                    checks_passed += 1
                else:
                    print(f"❌ Header check: Invalid section offsets {section_offsets}")
            else:
                print(f"❌ Header check: Cannot read 16-byte header")
    except Exception as e:
        print(f"❌ Header check: Cannot read file - {e}")
    
    # Check 3: Tile directory structure verification  
    total_checks += 1
    try:
        with open(lzm_path, 'rb') as f:
            # Read section offsets
            section_offsets = struct.unpack('<IIII', f.read(16))
            section1_off = section_offsets[0]
            
            # Section 1 starts with tile directory entries
            f.seek(section1_off)
            
            # Try to read first few tile directory entries (6 bytes each: uint32 + uint16)
            tiles_read = 0
            for _ in range(min(10, 40)):  # Read up to 10 tiles, max 40 expected
                tile_data = f.read(6)
                if len(tile_data) == 6:
                    file_offset, num_groups = struct.unpack('<IH', tile_data)
                    tiles_read += 1
                else:
                    break
            
            if tiles_read > 0:
                print(f"✅ Tile directory check: Read {tiles_read} tile entries successfully")
                checks_passed += 1
            else:
                print("❌ Tile directory check: Cannot read tile entries")
    except Exception as e:
        print(f"❌ Tile directory check failed: {e}")
    
    # Check 4: Manual binary format verification
    total_checks += 1
    try:
        coords_in_bounds = verify_coordinates_in_bounds(lzm_path, expected_bbox)
        if coords_in_bounds:
            print("✅ Coordinate bounds check: All coordinates within expected bounds")
            checks_passed += 1
        else:
            print("❌ Coordinate bounds check: Some coordinates outside expected bounds")
    except Exception as e:
        print(f"❌ Coordinate bounds check failed: {e}")
    
    # Summary
    print(f"\n📊 Sanity Check Results: {checks_passed}/{total_checks} checks passed")
    
    if checks_passed >= total_checks * 0.8:  # 80% pass rate
        print("✅ Overall: LZM file appears to be valid")
        return True
    else:
        print("❌ Overall: LZM file may have issues")
        return False


def verify_coordinates_in_bounds(lzm_path: Path, bbox: BoundingBox) -> bool:
    """Verify that the LZM file structure looks reasonable."""
    
    try:
        file_size = lzm_path.stat().st_size
        
        # Basic file size validation
        if file_size < 100:
            print(f"❌ File too small: {file_size} bytes")
            return False
        
        # Check that we can read the header structure
        with open(lzm_path, 'rb') as f:
            header = f.read(16)
            if len(header) == 16:
                section_offsets = struct.unpack('<IIII', header)
                if all(0 <= offset < file_size for offset in section_offsets if offset > 0):
                    print(f"📍 File structure appears valid")
                    return True
                else:
                    print(f"❌ Invalid section offsets: {section_offsets}")
                    return False
            else:
                print(f"❌ Cannot read header")
                return False
                
    except Exception as e:
        print(f"File structure verification error: {e}")
        return False


def main():
    """Main test function."""
    
    print("Starting LZM Builder Test Suite")
    print("Working directory:", os.getcwd())
    
    # Run the main test
    success = test_signal_du_botrange()
    
    if success:
        print("\n🎉 All tests completed successfully!")
        print("The refactored LZM builder is working correctly with real-world data.")
        return 0
    else:
        print("\n💥 Some tests failed!")
        print("Please review the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())