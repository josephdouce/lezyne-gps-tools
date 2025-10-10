# LZM Tools

This directory contains utility tools for working with LZM files.

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