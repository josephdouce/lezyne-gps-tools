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

### `osm-grid.html` — Interactive OSM Grid Downloader

File: `lzm_builder/tools/osm-grid.html`

Purpose: visually plan an area of interest (polygon) or load a GPX track and emit a resumable bash script to download OpenStreetMap highway data in fixed 0.20° × 0.20° tiles from the Overpass API.

Key behavior and notes:

- Tile size and indexing
    - Fixed cell size: 0.20° × 0.20° (latitude × longitude).
    - Computed using integer indices to avoid accumulation errors:
        - startLatIndex = floor(minLat / 0.20)
        - endLatIndex   = ceil(maxLat / 0.20)
        - startLngIndex = floor(minLng / 0.20)
        - endLngIndex   = ceil(maxLng / 0.20)

- Modes
    - Polygon Mode:
        - Creates an editable octagon (8 draggable points). The UI enforces convex polygons and warns if convexity is violated.
        - Emits a `.poly` block in longitude-latitude order (5 decimal places) with this layout:
            ```
            region
            1
            {lon} {lat}
            {lon} {lat}
            ...
            END
            END
            ```
    - GPX Mode:
        - Loads a GPX file and uses only the first `<trk>` element (falls back to `<wpt>` if no track). The track is drawn in red. GPX Mode hides the `.poly` output area.
        - Computes every 0.20° tile that intersects the track (point-in-square + segment intersection tests).

- Intersection selection
    - A tile is selected if any tile corner is inside the polygon/track, or any polygon vertex is inside the tile, or if any tile edge intersects any polygon/track segment.

- Safety and limits
    - Maximum selectable tiles: 100 (UI prevents exceeding this to avoid Overpass overload).
    - The UI shows warnings when polygon convexity fails or the tile limit is exceeded.

- Script and filenames
    - Generates a resumable Bash script that downloads a filtered Overpass result for each selected tile.
    - Filenames follow this convention:
        `osm_{minLat}_{minLng}_{maxLat}_{maxLng}_{index}_{total}_grid.osm`
        - Numeric coordinates in filenames and Overpass queries are rounded to 2 decimal places for readability and consistency.
    - Resume logic: the script checks file size with `stat -f%z` (macOS) or `stat -c%s` (Linux) and re-downloads only when the file is missing or ≤ 200 bytes.
    - Rate limiting: the generated script sleeps 30 seconds between downloads (the UI assumes ~10s per-download time when estimating totals).

- Overpass query
    - The script uses a highway filter for common tags (motorway, trunk, primary, secondary, tertiary, residential, cycleway, footway, service, etc.) and requests XML output with a 60s timeout.

- Area & time estimation
    - Polygon Mode: polygon area computed via a planar shoelace algorithm and converted to km² using ≈111 km/deg scaling.
    - GPX Mode: area approximated from the GPX bounding box using mean-latitude cosine scaling for longitude degrees.
    - Download time estimate: modeled as squares*10 + (squares-1)*30 seconds (10s assumed per-download + 30s enforced wait between tiles).

- Typical workflow
    1. Open `lzm_builder/tools/osm-grid.html` in a browser.
    2. Use Polygon Mode (🛑) to draw a region or GPX Mode (🧭) to load a track.
    3. Copy/save the generated bash script (e.g., `download_region.sh`), `chmod +x` and run it in a dedicated directory to download `.osm` tiles.
    4. Convert downloaded `.osm` files into LZM files with auto bbox extraction:
         ```bash
         for osm in *.osm; do python ../lzm_builder.py --osm "$osm" --bbox auto --verbose; done
         ```

Notes and caveats
    - 0.20° degree boxes are not equal-area — longitude degrees compress toward the poles. Use the tool for planning and convenience (equal-area grids require DGGS/S2/H3-style approaches).
    - The tool intentionally enforces conservative limits and waits to be a good Overpass citizen.