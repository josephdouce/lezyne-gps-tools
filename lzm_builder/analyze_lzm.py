#!/usr/bin/env python3
"""
LZM File Analyzer

Analyzes the binary structure of an LZM file to verify it matches expected format.
"""

import struct
import sys


def analyze_lzm_file(filename):
    """Analyze the structure of an LZM file."""
    
    print(f"🔍 Analyzing LZM file: {filename}")
    print("=" * 60)
    
    with open(filename, 'rb') as f:
        # Read header (4 section offsets)
        header = f.read(16)
        if len(header) != 16:
            print("❌ ERROR: Cannot read 16-byte header")
            return
        
        section1_off, section2_off, section3_off, section4_off = struct.unpack('<IIII', header)
        file_size = f.seek(0, 2)  # Seek to end to get file size
        f.seek(0)  # Return to start
        
        print(f"📊 File size: {file_size:,} bytes")
        print(f"📊 Header section offsets:")
        print(f"   Section 1 (Tile Directory): {section1_off}")
        print(f"   Section 2 (Tile→String IDs): {section2_off}")
        print(f"   Section 3 (String Index): {section3_off}")
        print(f"   Section 4 (Polyline Data): {section4_off}")
        print()
        
        # Analyze Section 1: Tile Directory
        print("📍 Section 1: Tile Directory")
        f.seek(section1_off)
        tile_count = 0
        while f.tell() < section2_off:
            data = f.read(6)
            if len(data) != 6:
                break
            file_offset, num_groups = struct.unpack('<IH', data)
            if tile_count < 10:  # Show first 10 tiles
                print(f"   Tile {tile_count}: offset={file_offset}, groups={num_groups}")
            tile_count += 1
        print(f"   Total tiles: {tile_count}")
        print()
        
        # Analyze Section 2: Tile→String IDs
        print("📍 Section 2: Tile→String IDs")
        f.seek(section2_off)
        string_count = 0
        while f.tell() < section3_off:
            data = f.read(5)
            if len(data) != 5:
                break
            file_offset, ptype = struct.unpack('<IB', data)
            if string_count < 10:  # Show first 10
                print(f"   String {string_count}: offset={file_offset}, type={ptype}")
            string_count += 1
        print(f"   Total strings: {string_count}")
        print()
        
        # Analyze Section 3: String Index
        print("📍 Section 3: String Index")
        f.seek(section3_off)
        index_count = 0
        while f.tell() < section4_off:
            data = f.read(6)
            if len(data) != 6:
                break
            file_offset, size = struct.unpack('<IH', data)
            if index_count < 10:  # Show first 10
                print(f"   Index {index_count}: offset={file_offset}, size={size}")
            index_count += 1
        print(f"   Total index entries: {index_count}")
        print()
        
        # Analyze Section 4: Polyline Data (first few bytes)
        print("📍 Section 4: Polyline Data")
        f.seek(section4_off)
        remaining = file_size - section4_off
        print(f"   Data size: {remaining:,} bytes")
        
        # Show first polyline data
        if remaining >= 2:
            num_polylines = struct.unpack('<H', f.read(2))[0]
            print(f"   First chunk has {num_polylines} polylines")
            
            if remaining >= 3:
                point_count = struct.unpack('<B', f.read(1))[0]
                print(f"   First polyline has {point_count} points")
                
                # Show first few coordinate bytes
                coord_data = f.read(min(20, remaining - 3))
                coord_hex = ' '.join(f'{b:02x}' for b in coord_data)
                print(f"   First coordinate bytes: {coord_hex}")
        print()
        
        print("✅ Analysis complete!")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyze_lzm.py <lzm_file>")
        sys.exit(1)
    
    analyze_lzm_file(sys.argv[1])