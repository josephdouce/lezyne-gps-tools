"""
Data classes for LZM Builder.

This module contains all the data structures used by the LZM Builder.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Coordinate:
    """Represents a geographic coordinate (latitude, longitude)."""
    lat: float
    lon: float


@dataclass
class BoundingBox:
    """Represents a geographic bounding box."""
    south: float
    west: float
    north: float
    east: float


@dataclass
class Polyline:
    """Represents a polyline with a list of coordinates."""
    coordinates: List[Coordinate] = field(default_factory=list)


@dataclass
class GridTile:
    """Represents a single tile in the grid containing polyline data."""
    bbox: BoundingBox
    hasPolylineData: bool = False
    hasCompressedData: bool = False
    polys: Dict[int, List[Polyline]] = field(default_factory=lambda: _default_polys())
    counts: Dict[int, int] = field(default_factory=lambda: _default_counts())
    compressed: Dict[int, bytes] = field(default_factory=dict)
    sizes: Dict[int, int] = field(default_factory=dict)


def _default_polys():
    """Default factory for polylines dict to avoid import issues."""
    # Import GROUP_ORDER here to avoid circular imports
    from utils.constants import GROUP_ORDER
    return {t: [] for t in GROUP_ORDER}


def _default_counts():
    """Default factory for counts dict to avoid import issues."""
    # Import GROUP_ORDER here to avoid circular imports
    from utils.constants import GROUP_ORDER
    return {t: 0 for t in GROUP_ORDER}