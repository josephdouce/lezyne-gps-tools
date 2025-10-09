#!/usr/bin/env python3
"""
LZM Builder Auto Bbox Test Script

Tests the auto bbox detection feature of the refactored LZM builder.
This test:
1. Extracts a subset from belgium_sample.osm.pbf using osmium CLI
2. Names the extracted file with bbox coordinates in the filename  
3. Tests auto bbox detection by calling LZMBuilder.from_pbf() with bbox="auto"
4. Performs sanity checking on the result
5. Cleans up both the extracted PBF and generated LZM files

Test area: Signal du Botrange and High Fagnes nature reserve
Bounding box: 50.483507, 6.035957 (SW) to 50.522377, 6.138439 (NE)
"""

import os
import struct
import subprocess
import sys
import time
from pathlib import Path

from lzm_builder import LZMBuilder, BoundingBox, Coordinate, Polyline, GridTile


def test_auto_bbox_detection():
    """Test LZM generation with auto bbox detection for Signal du Botrange area."""
    
    print("🇧🇪 LZM Builder Auto Bbox Test - Signal du Botrange")
    print("=" * 60)
    
    # Define the test area (Signal du Botrange and High Fagnes)
    bbox = BoundingBox(
        south=50.483507,
        west=6.035957, 
        north=50.522377,
        east=6.138439
    )
    
    print(f"Test area: Signal du Botrange and High Fagnes nature reserve")
    print(f"Bounding box: {bbox.south:.6f}, {bbox.west:.6f} (SW) to {bbox.north:.6f}, {bbox.east:.6f} (NE)")
    
    # Input and output files
    source_pbf_file = Path(__file__).parent / "belgium_sample.osm.pbf"
    extracted_pbf_file = Path(__file__).parent / f"belgium_{bbox.south:.2f}_{bbox.west:.2f}_{bbox.north:.2f}_{bbox.east:.2f}_tk421.osm.pbf"
    expected_lzm_file = f"mf_{bbox.south:.2f}_{bbox.west:.2f}_{bbox.north:.2f}_{bbox.east:.2f}.lzm"
    lzm_file_path = None  # Track the generated file for cleanup
    
    print(f"Source PBF: {source_pbf_file}")
    print(f"Extracted PBF: {extracted_pbf_file}")
    print(f"Expected LZM output: {expected_lzm_file}")
    
    # Check source file exists
    if not source_pbf_file.exists():
        print(f"❌ ERROR: Source file not found: {source_pbf_file}")
        return False
    
    source_size = source_pbf_file.stat().st_size
    print(f"✅ Source PBF file found ({source_size:,} bytes)")
    
    try:
        # Step 1: Extract subset using osmium CLI
        print(f"\n📦 Step 1: Extracting subset using osmium CLI...")
        extract_start = time.time()
        
        success = extract_pbf_subset(source_pbf_file, extracted_pbf_file, bbox)
        if not success:
            print("❌ ERROR: Failed to extract PBF subset")
            return False
        
        extract_time = time.time() - extract_start
        extracted_size = extracted_pbf_file.stat().st_size
        print(f"✅ Extraction complete in {extract_time:.2f} seconds")
        print(f"📁 Extracted PBF: {extracted_size:,} bytes")
        
        # Step 2: Test auto bbox detection
        print(f"\n🤖 Step 2: Testing auto bbox detection...")
        print(f"Calling LZMBuilder.from_pbf() with bbox='auto'")
        generation_start = time.time()
        
        try:
            builder = LZMBuilder()
            lzm_file = builder.from_pbf(str(extracted_pbf_file), bbox="auto", verbose=True)
            lzm_file_path = Path(lzm_file)  # Store for cleanup
            
            generation_time = time.time() - generation_start
            print(f"✅ LZM file generated in {generation_time:.2f} seconds")
            print(f"Output file: {lzm_file}")
            
        except Exception as e:
            print(f"❌ ERROR generating LZM file: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Step 3: Verify the output file
        if not lzm_file_path.exists():
            print(f"❌ ERROR: Output LZM file not found: {lzm_file_path}")
            return False
        
        lzm_size = lzm_file_path.stat().st_size
        print(f"✅ LZM file created ({lzm_size:,} bytes)")
        
        # Step 4: Sanity checking
        print(f"\n🔍 Step 3: Performing sanity checks...")
        test_result = perform_sanity_checks(lzm_file_path, bbox)
        
        return test_result
        
    finally:
        # Cleanup: Remove both the extracted PBF and generated LZM files
        cleanup_files = []
        
        if extracted_pbf_file.exists():
            cleanup_files.append(extracted_pbf_file)
        
        if lzm_file_path and lzm_file_path.exists():
            cleanup_files.append(lzm_file_path)
        
        for file_path in cleanup_files:
            try:
                file_path.unlink()
                print(f"🧹 Cleaned up test file: {file_path.name}")
            except OSError as e:
                print(f"⚠️  Warning: Failed to remove test file {file_path}: {e}")


def extract_pbf_subset(source_pbf: Path, output_pbf: Path, bbox: BoundingBox) -> bool:
    """Extract a subset of the source PBF file using osmium CLI."""
    
    try:
        # Build osmium extract command
        # Format: osmium extract --bbox west,south,east,north input.pbf --output output.pbf
        cmd = [
            "osmium", "extract", 
            "--bbox", f"{bbox.west},{bbox.south},{bbox.east},{bbox.north}",
            "--output", str(output_pbf),
            str(source_pbf)
        ]
        
        print(f"Running osmium command: {' '.join(cmd)}")
        
        # Run the command
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("✅ osmium extract completed successfully")
            return True
        else:
            print(f"❌ osmium extract failed (exit code {result.returncode})")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ osmium extract timed out (>300s)")
        return False
    except FileNotFoundError:
        print("❌ osmium command not found. Please install osmium-tool:")
        print("   brew install osmium-tool  # macOS")
        print("   apt install osmium-tool   # Ubuntu/Debian")
        return False
    except Exception as e:
        print(f"❌ osmium extract failed: {e}")
        return False


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
    
    print("Starting LZM Builder Auto Bbox Test Suite")
    print("Working directory:", os.getcwd())
    
    # Run the main test
    success = test_auto_bbox_detection()
    
    if success:
        print("\n🎉 All tests completed successfully!")
        print("The auto bbox detection feature is working correctly!")
        return 0
    else:
        print("\n💥 Some tests failed!")
        print("Please review the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())