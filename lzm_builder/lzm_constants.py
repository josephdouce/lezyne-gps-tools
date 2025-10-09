"""
LZM Constants Module

This module contains all constants, enums, and configuration mappings used by the LZM builder.
These include polyline type definitions, OpenStreetMap highway mappings, and processing order.
"""


class PolylineType:
    """Constants for different polyline types used in LZM files."""
    SERVICE      = 0
    ROAD_MAJOR   = 1
    ROAD_HIGHWAY = 2
    ROAD_TERTIARY= 3
    ROAD_NORMAL  = 4
    TRAIL_FOOT   = 90
    TRAIL_BIKE   = 99


# Mapping from OpenStreetMap highway tags to LZM polyline types
WAY_KEY_TO_TYPE = {
    "motorway":   PolylineType.ROAD_HIGHWAY,
    "motorway_link": PolylineType.ROAD_HIGHWAY,
    "trunk":      PolylineType.ROAD_MAJOR,
    "primary":    PolylineType.ROAD_MAJOR,
    "secondary":  PolylineType.ROAD_MAJOR,
    "tertiary":   PolylineType.ROAD_TERTIARY,
    "trunk_link": PolylineType.ROAD_TERTIARY,
    "tertiary_link": PolylineType.ROAD_TERTIARY,
    "unclassified": PolylineType.ROAD_NORMAL,
    "residential": PolylineType.ROAD_NORMAL,
    "living_street": PolylineType.ROAD_NORMAL,
    "bus_guideway": PolylineType.ROAD_NORMAL,
    "escape": PolylineType.ROAD_NORMAL,
    "raceway": PolylineType.ROAD_NORMAL,
    "road": PolylineType.ROAD_NORMAL,
    "busway": PolylineType.ROAD_NORMAL,
    "corridor": PolylineType.ROAD_NORMAL,
    "rest_area": PolylineType.ROAD_NORMAL,
    "path": PolylineType.TRAIL_BIKE,
    "track": PolylineType.TRAIL_BIKE,
    "cycleway": PolylineType.TRAIL_BIKE,
    "pedestrian": PolylineType.TRAIL_FOOT,
    "footway": PolylineType.TRAIL_FOOT,
    "bridleway": PolylineType.TRAIL_BIKE,
    "steps": PolylineType.TRAIL_FOOT,
    "service": PolylineType.SERVICE,
    "turning_circle": PolylineType.SERVICE,
    "turning_loop": PolylineType.SERVICE,
}


# Processing order for polyline types (determines rendering priority)
GROUP_ORDER = [
    PolylineType.ROAD_HIGHWAY,
    PolylineType.ROAD_MAJOR,
    PolylineType.ROAD_NORMAL,
    PolylineType.ROAD_TERTIARY,
    PolylineType.TRAIL_BIKE,
    PolylineType.TRAIL_FOOT,
    PolylineType.SERVICE,
]