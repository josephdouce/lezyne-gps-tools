# LZM Tools

This directory contains utility tools for working with LZM files and generating large-scale map datasets.

## Tools

### `analyze_lzm.py`
A debugging tool for analyzing the internal structure of LZM files.

**Usage:**
```bash
python analyze_lzm.py <lzm_file>
```

**Features:**
- Parses LZM binary format
- Shows section offsets and sizes
- Displays tile directory structure
- Analyzes polyline data
- Validates file integrity

**Example:**
```bash
python tools/analyze_lzm.py test_map.lzm
```

This tool is useful for:
- Debugging LZM generation issues
- Understanding LZM file structure
- Validating generated maps
- Research and development

---

### `osm-grid.html`
An interactive web-based tool for generating batch download scripts to create comprehensive offline map sets for large regions.

**Purpose:** Generate a grid of OSM data downloads that can be converted into a complete set of LZM files covering an entire country or large region.

#### **What It Does:**

**Visual Grid Planning:**
- Interactive map interface using Leaflet.js
- Draw custom polygons to define your area of interest
 - Automatically calculates 0.20° × 0.20° degree grid boxes
- Real-time feedback on total area and number of downloads
- Convex polygon validation to ensure proper coverage
- Load GPX tracks (GPX Mode) and compute 0.20° boxes that intersect the track (first <trk> only)

**Smart Download Management:**
- Generates bash scripts with resume capability
- Skips existing files > 200 bytes (prevents re-downloading)
- Includes 30-second delays between downloads (Overpass API rate limiting)
- Filters for highway data only (roads, paths, trails)
- Proper file naming with coordinates and grid position

**Safety Features:**
 - Limits to maximum 100 grid boxes (prevents server overload)
- Warns about non-convex polygons
- Shows total download count and estimated coverage area

#### **How to Use for Large Region LZM Generation:**

**Step 1: Plan Your Region**
1. Open `osm-grid.html` in your web browser
2. Navigate to your target region (e.g., Belgium, Netherlands, etc.)
3. Click the red stop button (🛑) to enter polygon mode
4. Drag the octagon vertices to cover your desired area
5. Ensure the polygon remains convex (tool will warn if not)
6. Review the grid information panel:
   - Total area in km²
    - Number of 0.20° boxes
   - Any warnings about limits
    - To use GPX Mode instead of polygon mode, click the compass button (🧭) and choose a .gpx file. The first
      <trk> will be used and the map will zoom to the track. The .poly output is hidden in GPX Mode; the generated
      bash script is produced as usual.

**Step 2: Generate Download Script**
1. The tool automatically generates a bash script in the text area
2. Click "Copy Script to Clipboard" 
3. Save the script to a file (e.g., `download_belgium.sh`)
4. Make it executable: `chmod +x download_belgium.sh`

**Step 3: Download OSM Data**
```bash
# Create download directory
mkdir belgium_osm_data
cd belgium_osm_data

# Run the download script
../download_belgium.sh
```

**Expected Downloads:**
- Each file covers a 0.20° × 0.20° degree bounding box (lat × lon)
- Filenames like: `osm_50.92_4.80_51.14_5.02_1_73_grid.osm`
- Format: `osm_{minLat}_{minLng}_{maxLat}_{maxLng}_{index}_{total}_grid.osm`
- Resume capability: Re-run script to continue interrupted downloads

**Step 4: Convert to LZM Files**
```bash
# Process each OSM file into LZM format
for osm_file in *.osm; do
    echo "Processing $osm_file..."
    
    # Extract coordinates from filename
    coords=$(echo "$osm_file" | grep -o '[0-9.-]*_[0-9.-]*_[0-9.-]*_[0-9.-]*' | head -1)
    
    # Convert to LZM using auto bbox detection
    python ../lzm_builder.py --osm "$osm_file" --bbox auto --verbose
    
    echo "Generated LZM for $osm_file"
done
```

**Step 5: Deploy to Lezyne Device**
```bash
# Copy all LZM files to your Lezyne GPS device
cp *.lzm /Volumes/LEZYNE/Maps/
```

#### **Real-World Example: Belgium Coverage**

**Planning Phase:**
- Total area: ~30,500 km²
- Grid boxes: 73 files (0.20° × 0.20° each)
- Download time: ~40 minutes (with rate limiting)
- Processing time: ~17 minutes for LZM conversion

**Benefits:**
- Complete offline coverage of entire country
- Seamless map experience on device
- Custom data (no reliance on gpsroot.com)
- Perfect for bikepacking across regions

**File Management:**
```
belgium_project/
├── download_belgium.sh       # Generated download script
├── osm_data/                 # Downloaded OSM files
│   ├── osm_50.48_4.24_50.70_4.46_1_73_grid.osm
│   ├── osm_50.48_4.46_50.70_4.68_2_73_grid.osm
│   └── ... (71 more files)
└── lzm_maps/                 # Generated LZM files
    ├── mf_50.48_4.24_50.70_4.46.lzm
    ├── mf_50.48_4.46_50.70_4.68.lzm
    └── ... (73 total LZM files)
```

#### **Advanced Usage Tips:**

**Large Countries/Regions:**
- Split very large areas into multiple polygons
- Process regions separately to manage download times
- Consider using extraction method for faster processing

**Data Quality:**
- OSM highway filter includes all road types: motorways, residential streets, bike paths, footpaths
- 0.20° boxes provide consistent degree-based tiling (longitude degree width varies with latitude)
- Overpass API provides up-to-date road data

**Automation:**
```bash
# Complete automation pipeline
./download_region.sh          # Download OSM data
./convert_to_lzm.sh           # Convert all to LZM
./deploy_to_device.sh         # Copy to GPS device
```

**Rate Limiting Compliance:**
- Built-in 30-second delays between downloads
- Respects Overpass API usage guidelines
- Resume capability prevents duplicate requests

#### **Technical Details:**

**Grid System:**
- 0.20° × 0.20° degree boxes (lat × lon). Note: degrees are used directly and longitude degrees correspond to different ground distances depending on latitude.
- Intersection detection ensures complete coverage
- No gaps or overlaps in final map set

**Overpass API Query:**
```
[out:xml][timeout:60];
(way[highway~"^(motorway|trunk|primary|...)$"](bbox);>;);
out;
```

**File Size Expectations:**
- Rural areas: 50-200 KB per OSM file
- Urban areas: 500KB-2MB per OSM file
- Final LZM files: 5-50 KB each

This tool transforms the process of creating comprehensive regional offline maps from a manual, tedious task into an automated, visual workflow perfect for planning multi-day bikepacking adventures or complete regional coverage.