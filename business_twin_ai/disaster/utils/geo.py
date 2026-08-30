"""Geospatial helpers for the disaster validation layer."""

from __future__ import annotations

import math
from typing import Tuple

from business_twin_ai.disaster.config import ValidationConfig

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two WGS84 points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def is_valid_gps(lat: float | None, lon: float | None, cfg: ValidationConfig) -> bool:
    """True when lat/lon exist and fall inside the allowed GPS ranges."""
    if lat is None or lon is None:
        return False
    return (
        cfg.GPS_LAT_MIN <= lat <= cfg.GPS_LAT_MAX
        and cfg.GPS_LON_MIN <= lon <= cfg.GPS_LON_MAX
    )


def is_origin(lat: float, lon: float, cfg: ValidationConfig) -> bool:
    """True when the coordinates are effectively (0, 0)."""
    return abs(lat) <= cfg.ORIGIN_TOLERANCE and abs(lon) <= cfg.ORIGIN_TOLERANCE


def decimal_places(value: float) -> int:
    """Count significant decimal places of a float, e.g. 28.6125 -> 4."""
    text = repr(value)
    if "e" in text.lower():
        return 6  # scientific notation → high precision
    if "." not in text:
        return 0
    return len(text.split(".")[1].rstrip("0"))


def precision_score(lat: float, lon: float, cfg: ValidationConfig) -> float:
    """Score (0-100) for GPS precision based on decimal places of both coords."""
    decimals = min(decimal_places(lat), decimal_places(lon))
    table = cfg.PRECISION_SCORE_BY_DECIMALS
    idx = min(decimals, len(table) - 1)
    return float(table[idx])


def bounding_box(
    lat: float, lon: float, radius_km: float
) -> Tuple[float, float, float, float]:
    """Return (min_lat, max_lat, min_lon, max_lon) for a radius around a point."""
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon


def movement_speed_kmh(lat1: float, lon1: float, lat2: float, lon2: float, hours: float) -> float:
    """Average speed between two GPS fixes (km/h). 0 when time delta is ~0."""
    if hours <= 0:
        return 0.0
    return haversine_km(lat1, lon1, lat2, lon2) / hours
