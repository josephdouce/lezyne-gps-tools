# LZM Builder

A clean, service-oriented tool for reverse-engineering and generating Lezyne LZM offline map files from OpenStreetMap data. This tool allows you to create custom maps for Lezyne GPS devices without relying on gpsroot.com.

## 🏗️ Architecture Overview

This codebase has been completely refactored from a monolithic script into a clean, maintainable service-oriented architecture following proper OOP principles. The structure is designed to be easily understood by both human developers and AI models.

```
lzm_builder/
├── lzm_builder.py      # 🎯 Main orchestrator (entry point)
├── run_tests.sh        # 🧪 Test runner script
├── models/             # 📊 Data structures and models
├── services/           # ⚙️ Core business logic services
├── utils/              # 🛠️ Utilities and constants
├── tests/              # ✅ Comprehensive test suite
└── tools/              # 🔧 Development and debugging tools
```

---

## 📊 Models (Data Structures)

### `models/data_classes.py`

Contains all the core data structures used throughout the system:

#### **`Coordinate`**
```python
@dataclass
class Coordinate:
    lat: float  # Latitude in decimal degrees
    lon: float  # Longitude in decimal degrees
```
- **Purpose**: Represents a single geographic point
- **Usage**: Building blocks for polylines and bounding boxes
- **Used by**: All services that handle geographic data

#### **`BoundingBox`** 
```python
@dataclass
class BoundingBox:
    south: float  # Southern latitude boundary
    west: float   # Western longitude boundary  
    north: float  # Northern latitude boundary
    east: float   # Eastern longitude boundary
```
- **Purpose**: Defines rectangular geographic areas
- **Usage**: Filtering OSM data, defining map extents, grid calculations
- **Used by**: OSMParser (filtering), GridBuilder (tile boundaries), CLI (user input)

#### **`Polyline`**
```python
@dataclass
class Polyline:
    coordinates: List[Coordinate] = field(default_factory=list)
```
- **Purpose**: Represents a connected sequence of geographic points (roads, paths, etc.)
- **Usage**: Storing road segments, trails, and other linear features
- **Used by**: GridBuilder (polyline assignment), LZMProcessing (compression)

#### **`GridTile`**
```python
@dataclass
class GridTile:
    bbox: BoundingBox                                    # Tile boundaries
    hasPolylineData: bool = False                        # Whether tile contains data
    hasCompressedData: bool = False                      # Whether data is compressed
    polys: Dict[int, List[Polyline]]                     # Polylines by type
    counts: Dict[int, int]                               # Count per polyline type
    compressed: Dict[int, bytes]                         # Compressed binary data
    sizes: Dict[int, int]                                # Size of compressed data
```
- **Purpose**: Represents a single tile in the spatial grid
- **Usage**: Organizing map data spatially for efficient access
- **Key Features**:
  - **Spatial Organization**: Each tile covers 0.01° × 0.01° (roughly 1km²)
  - **Type Separation**: Different polyline types stored separately
  - **Compression Ready**: Tracks both raw and compressed data
- **Used by**: GridBuilder (population), LZMWriter (serialization)

---

## ⚙️ Services (Business Logic)

### `services/progress_logger.py`

**Purpose**: Centralized progress reporting and logging system
**Responsibility**: All verbose output and progress tracking

#### **`ProgressLogger`**
```python
class ProgressLogger:
    def __init__(self, verbose: bool = False)
    def phase(self, phase_name: str) -> PhaseContext    # Context manager for phases
    def log(self, message: str, emoji: str = "📊")      # Log with emoji prefix
    def log_stats(self, stats: dict, prefix: str = "")  # Format statistics nicely
```

#### **`PhaseContext`** 
```python
class PhaseContext:
    # Context manager that automatically times and reports phases
    # Usage: with logger.phase("Phase name"): ...
```

#### **`PeriodicReporter`**
```python
class PeriodicReporter:
    def __init__(self, logger, interval, message_template)
    def increment(self, **kwargs)  # Report progress at regular intervals
```

**Benefits**: 
- Clean separation of logging from business logic
- Consistent progress reporting across all services
- Easy to disable verbose output for production use

### `services/osm_parser.py`

**Purpose**: Parse OpenStreetMap files and extract relevant geographic data
**Responsibility**: OSM file processing, filtering, and data extraction

#### **`OSMParser`**
```python
class OSMParser:
    def __init__(self, logger: ProgressLogger)
    def parse(self, osm_path: str, bbox: BoundingBox, options: dict) -> OSMParsingResult
```

#### **`OSMParsingResult`**
```python
class OSMParsingResult:
    nodes: Dict[int, Coordinate]                                    # Node ID → Coordinate
    ways_to_include: List[Tuple[int, int, List[int], int, BoundingBox]]  # Way data
    stats: Dict[str, int]                                          # Processing statistics
```

**Key Features**:
- **Spatial Filtering**: Only processes nodes/ways within bounding box
- **Type Filtering**: Filters ways by highway type (roads, paths, etc.)
- **Optimization**: Early rejection of out-of-bounds nodes for performance
- **Progress Tracking**: Reports processing statistics via ProgressLogger

**Filtering Logic**:
- **Nodes**: Filtered by geographic bounding box with configurable buffer
- **Ways**: Filtered by highway tags, access restrictions, and spatial overlap
- **Service Roads**: Optional inclusion via `keep_service` flag
- **Sidewalks**: Optional inclusion via `keep_sidewalks` flag

### `services/grid_builder.py`

**Purpose**: Build spatial grids and assign polylines to tiles
**Responsibility**: Spatial organization of geographic data

#### **`GridBuilder`**
```python
class GridBuilder:
    def __init__(self, logger: ProgressLogger)
    def build(self, osm_data: OSMParsingResult, bbox: BoundingBox, 
              opt_level: int, epsilon: float) -> GridBuildingResult
```

#### **`GridBuildingResult`**
```python
class GridBuildingResult:
    grid: List[List[GridTile]]  # 2D array of tiles
    htiles: int                 # Horizontal tile count
    vtiles: int                 # Vertical tile count
```

**Grid System**:
- **Tile Size**: Each tile covers 0.01° × 0.01° (roughly 1km × 1km)
- **Calculation**: `htiles = (east - west) * 100`, `vtiles = (north - south) * 100`
- **Coordinate System**: Grid[y][x] where y=0 is south, x=0 is west

**Assignment Algorithm**:
1. Calculate way's bounding box
2. Determine which tiles the way might intersect
3. Add way to all potentially intersecting tiles
4. Apply optimization and simplification

### `services/lzm_processing.py`

**Purpose**: Core polyline processing algorithms
**Responsibility**: Polyline manipulation, optimization, and compression preparation

#### **Key Functions**:

**`add_way_to_polylines(way_coords, ptype, tile, opt_level, epsilon)`**
- **Purpose**: Add a way to a tile's polyline collection
- **Algorithm**:
  1. Clip way to tile boundaries
  2. Split into segments if too long (>254 points)
  3. Attempt to merge with existing polylines (if opt_level > 0)
  4. Apply simplification using Douglas-Peucker algorithm
  5. Add to tile's polyline collection

**`compress_polylines(polys) -> Tuple[bytes, int]`**
- **Purpose**: Compress polylines into LZM binary format
- **Format**:
  ```
  [uint16: number_of_polylines]
  For each polyline:
    [uint8: point_count]
    [encoded coordinates using PolylineEncoder]
  ```

**Optimization Levels**:
- **Level 0**: No optimization, keep all polylines separate
- **Level 1+**: Attempt to merge connecting polylines
- **Level 2+**: Apply Douglas-Peucker simplification

### `services/lzm_writer.py`

**Purpose**: Generate final LZM binary files
**Responsibility**: Binary file format generation and serialization

#### **`LZMWriter`**
```python
class LZMWriter:
    def __init__(self, logger: ProgressLogger)
    def write(self, grid_result: GridBuildingResult, bbox: BoundingBox) -> str
```

**LZM File Format**:
```
[Header: 4 × uint32 section offsets]

Section 1: Tile Directory
  For each tile: [uint32: file_offset, uint16: num_groups]

Section 2: Tile→String IDs  
  For each group: [uint32: file_offset, uint8: polyline_type]

Section 3: String Index
  For each group: [uint32: file_offset, uint16: size]

Section 4: Polyline Data
  Compressed polyline binary data
```

**Process**:
1. Compress all polylines in all tiles
2. Calculate file layout and offsets
3. Write header with section pointers
4. Write tile directory
5. Write type mappings
6. Write size index
7. Write compressed polyline data
8. Update header with final offsets

### `services/polyline_encoder.py`

**Purpose**: Encode coordinates into compressed binary format
**Responsibility**: Low-level coordinate compression using varint encoding

#### **`PolylineEncoder`**
```python
class PolylineEncoder:
    def __init__(self, buffer: bytearray, base: Optional[Coordinate] = None)
    def add_coord_float(self, lon_f: float, lat_f: float)
    def add_coord_int(self, lon_i: int, lat_i: int)
```

**Encoding Algorithm**:
1. **First coordinate**: Stored as absolute 32-bit integers (lat, lon)
2. **Subsequent coordinates**: Stored as varint-encoded deltas
3. **Precision**: Coordinates multiplied by 1e5 for integer representation
4. **Compression**: Variable-length integer encoding for space efficiency

**Varint Encoding**:
- Small deltas use fewer bytes
- Large deltas use more bytes as needed
- Most coordinate changes are small, so this is very efficient

---

## 🛠️ Utils (Utilities and Constants)

### `utils/constants.py`

**Purpose**: All constants, enums, and configuration mappings

#### **`PolylineType`** (Constants)
```python
class PolylineType:
    SERVICE      = 0   # Service roads, driveways
    ROAD_MAJOR   = 1   # Major roads (trunk, primary, secondary)  
    ROAD_HIGHWAY = 2   # Highways and motorways
    ROAD_TERTIARY= 3   # Tertiary roads and links
    ROAD_NORMAL  = 4   # Residential, unclassified roads
    TRAIL_FOOT   = 90  # Footpaths, pedestrian areas
    TRAIL_BIKE   = 99  # Bike paths, tracks
```

#### **`WAY_KEY_TO_TYPE`** (Mapping)
Maps OpenStreetMap highway tags to LZM polyline types:
```python
WAY_KEY_TO_TYPE = {
    "motorway": PolylineType.ROAD_HIGHWAY,
    "trunk": PolylineType.ROAD_MAJOR,
    "primary": PolylineType.ROAD_MAJOR,
    "residential": PolylineType.ROAD_NORMAL,
    "cycleway": PolylineType.TRAIL_BIKE,
    "footway": PolylineType.TRAIL_FOOT,
    # ... complete mapping
}
```

#### **`GROUP_ORDER`** (Processing Priority)
Defines rendering order (highways rendered first, service roads last):
```python
GROUP_ORDER = [
    PolylineType.ROAD_HIGHWAY,    # Rendered first (on top)
    PolylineType.ROAD_MAJOR,
    PolylineType.ROAD_NORMAL,
    PolylineType.ROAD_TERTIARY,
    PolylineType.TRAIL_BIKE,
    PolylineType.TRAIL_FOOT,
    PolylineType.SERVICE,         # Rendered last (on bottom)
]
```

### `utils/geographic.py`

**Purpose**: Geographic calculations and utility functions

#### **Core Functions**:

**Bounding Box Operations**:
```python
def bbox_contains(b: BoundingBox, c: Coordinate) -> bool
def bbox_overlap(r1: BoundingBox, r2: BoundingBox) -> bool  
def bbox_include(b: BoundingBox, c: Coordinate) -> None  # Expand bbox
```

**Coordinate Utilities**:
```python
def angle_degrees_difference(a1: float, a2: float) -> float
def round_away_from_zero(x: float) -> int
```

**Douglas-Peucker Simplification**:
```python
def simplify(coords: List[Coordinate], epsilon: float, opt_level: int) -> List[Coordinate]
def rdp_simplify(coords: List[Coordinate], epsilon: float) -> List[Coordinate]
def point_to_line_distance(point: Coordinate, line_start: Coordinate, line_end: Coordinate) -> float
```

**File and Path Operations**:
```python
def filename_from_bbox(bbox: BoundingBox, prefix="mf", suffix=".lzm") -> str
def pluck_bbox_from_filename(filename: str) -> BoundingBox
def script_dir() -> str
def extract_smaller_osm_from_larger_osm(input_osm: str, output_osm: str, bbox: BoundingBox) -> bool
```

---

## 🎯 Main Orchestrator

### `lzm_builder.py`

**Purpose**: High-level orchestration and public API
**Responsibility**: Coordinating services and providing clean public interface

#### **`LZMBuilder`**
```python
class LZMBuilder:
    def __init__(self, verbose: bool = False)
    def from_osm(self, osm_path: str, bbox: Union[BoundingBox, str] = "auto", 
                 keep_service: bool = False, keep_sidewalks: bool = False,
                 extraction: bool = False, epsilon: float = 0.00002, 
                 opt_level: int = 2, verbose: bool = False) -> str
```

**Service Architecture**:
```python
def __init__(self, verbose: bool = False):
    self._logger = ProgressLogger(verbose)
    self._osm_parser = OSMParser(self._logger)      # Inject logger
    self._grid_builder = GridBuilder(self._logger)  # Inject logger  
    self._lzm_writer = LZMWriter(self._logger)      # Inject logger
```

**Processing Modes**:

1. **Auto Bbox Mode** (`bbox="auto"`):
   - Extracts bounding box from filename
   - Processes entire OSM file (no spatial filtering)
   - Best for pre-extracted regional files

2. **Extraction Mode** (`extraction=True`):
   - Uses osmium CLI to extract subset first
   - Then processes extracted file
   - Best for large continental/world files

3. **Direct Mode** (default):
   - Processes OSM file with spatial filtering
   - Most memory efficient for moderate files

**Clean Orchestration**:
```python
def _build_lzm_from_osm(self, osm_path, bbox, ...):
    # Phase 1: Parse OSM file
    osm_data = self._osm_parser.parse(osm_path, bbox, parsing_options)
    
    # Phase 2 & 3: Build and populate grid
    grid_result = self._grid_builder.build(osm_data, bbox, opt_level, epsilon)
    
    # Phase 4 & 5: Compress and write LZM file
    return self._lzm_writer.write(grid_result, bbox)
```

---

## ✅ Testing

### `tests/` Directory Structure

```
tests/
├── __init__.py
├── lzm_builder_test.py              # Basic functionality test
├── lzm_builder_bbox_auto_test.py    # Auto bbox detection test  
└── lzm_builder_extraction_test.py   # Extraction method test
```

### `run_tests.sh` - Test Runner

**Features**:
- Automatically discovers all test files
- Provides progress reporting and summary statistics
- Returns proper exit codes for CI/CD integration
- Skips non-test files (`__init__.py`)

**Usage**:
```bash
./run_tests.sh
```

**Sample Output**:
```
🧪 LZM Builder Test Suite
=========================

🔬 Running lzm_builder_test...
✅ PASSED: lzm_builder_test

📊 TEST SUMMARY
===============
Total tests:  3
Passed:       3
Failed:       0

```



### Test Coverage

Each test validates different aspects:

1. **Basic Test**: Standard LZM generation workflow
2. **Auto Bbox Test**: Filename-based bbox extraction
3. **Extraction Test**: Osmium CLI integration

All tests include comprehensive sanity checking:
- File size validation
- Binary format verification
- Tile directory structure validation
- Coordinate bounds checking

---

## 🔧 Tools

### `tools/analyze_lzm.py`

**Purpose**: Debug and analyze LZM file structure
**Usage**: `python tools/analyze_lzm.py <lzm_file>`

**Features**:
- Parses LZM binary format
- Shows section offsets and sizes
- Displays tile directory structure  
- Analyzes polyline data
- Validates file integrity

### `tools/osm-grid.html` — Interactive OSM Grid Downloader

Purpose: visually plan an area (polygon) or load a GPX track and emit a resumable Bash script to download OpenStreetMap highway data in grid tiles. The tool now supports a configurable cell size (0.05°–0.30°, default 0.20°) so you can pick the degree-size of each tile.

Key features:

- Tile size and indexing
    - Configurable cell size: 0.05°–0.30° (latitude × longitude). Default is 0.20°.
    - Indexing uses integer grid indices to avoid floating point accumulation:
        - startLatIndex = floor(minLat / 0.20)
        - endLatIndex   = ceil(maxLat  / 0.20)
        - startLngIndex = floor(minLng / 0.20)
        - endLngIndex   = ceil(maxLng  / 0.20)

- Modes
    - Polygon Mode:
        - Editable octagon (8 draggable vertices). The UI enforces convex polygons and warns on non-convex shapes.
        - Emits a `.poly` block (longitude latitude order, 5 decimal places) when a valid polygon is present.
    - GPX Mode:
        - Loads a GPX file and uses only the first `<trk>` element (falls back to `<wpt>` if no track). The track is drawn in red and the `.poly` output is hidden.
    - Computes all grid tiles (at the selected size) that intersect the track using point-in-square and segment-intersection tests.

- Selection & safety
    - A tile is selected if any tile corner lies inside the polygon/track, or any polygon vertex lies inside the tile, or any tile edge intersects any polygon/track segment.
    - Maximum selectable tiles: 100 (UI prevents generating larger batches to avoid Overpass abuse).

- Generated Bash script
    - Filenames: `osm_{minLat}_{minLng}_{maxLat}_{maxLng}_{index}_{total}_grid.osm` (coordinates rounded to 2 decimal places for filenames and Overpass bboxes).
    - Resume logic: the script skips existing files larger than 200 bytes using `stat -f%z` (macOS) or `stat -c%s` (Linux) with a safe fallback.
    - Rate-limiting: the script enforces a 30s sleep between downloads; the UI estimates total time assuming ~10s download + 30s wait per tile.
    - Overpass filter: the query filters common highway tags (motorway, trunk, primary, secondary, tertiary, residential, cycleway, footway, service, etc.).

- `.poly` output (Polygon Mode)
    - Format (longitude latitude order):
        ```
        region
        1
        {lon} {lat}
        {lon} {lat}
        ...
        END
        END
        ```

- Area & time estimates
    - Polygon area uses a planar shoelace approximation converted to km² (~111 km/deg).
    - GPX area uses the GPX bounding box with mean-latitude cosine scaling for longitude km conversion.
    - Download time estimate = squares*10 + (squares-1)*30 seconds.

Quick workflow:

1. Open `lzm_builder/tools/osm-grid.html` in a browser.
2. Use Polygon Mode (🛑) to draw/adjust the octagon or GPX Mode (🧭) to load a track.
3. Copy/save the generated script (e.g. `download_region.sh`), `chmod +x` and run it in a fresh directory to download `.osm` tiles.
4. Convert `.osm` files to LZM using auto-bbox mode:
     ```bash
     for osm in *.osm; do python ../lzm_builder.py --osm "$osm" --bbox auto --verbose; done
     ```

Notes:

- Grid tiles are degree-based (default 0.20°) and not equal-area — longitudinal distance varies with latitude.
- The tool enforces conservative limits and waits to be a good Overpass citizen; adjust your workflow accordingly.


---

## 🚀 Usage Guide

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install osmium CLI tools (for extraction method)
brew install osmium-tool  # macOS
```

### Basic Usage

```bash
# Generate LZM from PBF with explicit bbox
python lzm_builder.py --osm map.osm.pbf --bbox 50.92,4.80,50.97,4.85 --verbose

# Use auto bbox detection from filename
python lzm_builder.py --osm belgium_50.48_6.04_50.52_6.14.osm.pbf --bbox auto --verbose

# Use extraction method for large files
python lzm_builder.py --osm europe.osm.pbf --bbox 50.92,4.80,50.97,4.85 --extraction --verbose
```

### Python API

```python
from lzm_builder import LZMBuilder, BoundingBox

# Create builder
builder = LZMBuilder(verbose=True)

# Generate LZM file
bbox = BoundingBox(south=50.92, west=4.80, north=50.97, east=4.85)
lzm_file = builder.from_osm("map.osm.pbf", bbox)

print(f"Generated: {lzm_file}")
```

### Advanced Options

```python
# Custom settings
lzm_file = builder.from_osm(
    osm_path="map.osm.pbf",
    bbox=bbox,
    keep_service=True,      # Include service roads
    keep_sidewalks=True,    # Include sidewalks  
    extraction=True,        # Use extraction method
    epsilon=0.00005,        # More aggressive simplification
    opt_level=3,            # Maximum optimization
    verbose=True
)
```

---

## 🏗️ Architecture Benefits

### For Developers

1. **Single Responsibility**: Each service has one clear job
2. **Dependency Injection**: Clean service composition with injected logger
3. **Testability**: Each component can be tested in isolation
4. **Maintainability**: Changes are localized to specific services
5. **Extensibility**: Easy to add new services or modify existing ones

### For AI Models

1. **Clear Boundaries**: Obvious where to make specific types of changes
2. **Consistent Patterns**: All services follow same structure
3. **Comprehensive Documentation**: Every component and responsibility documented
4. **Type Safety**: Full type hints for better code understanding
5. **Separation of Concerns**: Business logic separate from I/O, logging, etc.

### Service Interaction Pattern

```
User Input → LZMBuilder → Services → Data Models → Binary Output
     ↓           ↓           ↓            ↓            ↓
Command Line  Orchestration  Processing   Storage    LZM File
```

All services report progress through the same ProgressLogger, ensuring consistent user experience and making it easy to track processing stages.

---

## 🎛️ Configuration and Tuning

### Performance Tuning

**Memory Usage**:
- Use `extraction=True` for large continental files
- Smaller epsilon values = more detail but larger files
- Higher opt_level = more processing time but better compression

**Quality vs Speed**:
```python
# Fast, lower quality
builder.from_osm(pbf, bbox, epsilon=0.0001, opt_level=0)

# Slower, higher quality  
builder.from_osm(pbf, bbox, epsilon=0.00001, opt_level=3)
```

### Road Type Filtering

```python
# Include all road types
builder.from_osm(pbf, bbox, keep_service=True, keep_sidewalks=True)

# Only major roads (faster processing)
builder.from_osm(pbf, bbox, keep_service=False, keep_sidewalks=False)
```

---

## 📋 Requirements

### System Requirements

- **Python**: 3.8+
- **Memory**: 2GB+ recommended for large areas
- **Storage**: Space for temporary extracted files if using extraction method

### Python Dependencies

```
osmium>=3.2.0      # OSM file parsing
```

### Optional Dependencies

```bash
# For extraction method
brew install osmium-tool    # macOS
apt install osmium-tool     # Ubuntu/Debian
```

### Input Data

- **OSM Files**: `.pbf` or `.osm` format
- **Sources**: 
  - [Geofabrik](https://download.geofabrik.de/) - Regional extracts
  - [BBBike](https://extract.bbbike.org/) - Custom extracts
  - [Geo2Day](https://geo2day.com/) - Premium extracts

---

## 🔮 Future Development

### Planned Features

1. **POI Support**: Add Points of Interest to generated maps
2. **Routing Data**: Include turn restrictions and routing information  
3. **Metadata**: Add proper file metadata and versioning
4. **Batch Processing**: Generate multiple LZM files for large areas
5. **GPX Integration**: Generate maps for specific routes with buffers

### Extension Points

The architecture makes it easy to add:

1. **New Services**: Add to `services/` directory
2. **New Data Types**: Extend `models/data_classes.py`
3. **New Output Formats**: Create alternative writers
4. **New Input Sources**: Create alternative parsers
5. **New Optimization Algorithms**: Extend `lzm_processing.py`

### Contributing

When adding new features:

1. Follow the service-oriented pattern
2. Inject ProgressLogger for consistent reporting
3. Add comprehensive type hints
4. Create corresponding tests
5. Update this documentation

---

## 🏆 Credits and History

This tool was created through reverse engineering of Lezyne's LZM format using:

- **Manual Analysis**: Hex dump analysis of known simple maps
- **Pattern Recognition**: Identifying binary format structure
- **Iterative Development**: AI-assisted coding and testing
- **Validation**: Testing on actual Lezyne GPS devices

The breakthrough came from analyzing a minimal LZM file containing just one north-south street, which revealed the coordinate encoding scheme and tile organization.

### Architecture Evolution

- **V1**: Single monolithic script (~400 lines)
- **V2**: Service-oriented architecture with proper separation of concerns
- **V3**: (Current) Comprehensive documentation and tooling

The refactoring transformed chaotic procedural code into a maintainable, testable, and extensible system while preserving 100% functionality.

---

## 📄 License and Disclaimer

This is a reverse-engineered implementation. The LZM format belongs to Lezyne. This tool is for educational and personal use. The generated files work on Lezyne devices but there's no guarantee they match Lezyne's official format exactly.

Use at your own risk. Always backup your device before loading custom maps.