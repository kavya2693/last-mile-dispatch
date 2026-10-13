"""Distance and travel-time helpers.

Haversine is exact enough at city scale, and the road-distance factor stands in for a
routing engine: dispatch decisions only need relative travel times, not turn-by-turn paths.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from last_mile_dispatch.config import ROAD_CIRCUITY, SPEED_KMH

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: ArrayLike, lon1: ArrayLike, lat2: ArrayLike, lon2: ArrayLike) -> NDArray[np.float64]:
    la1, lo1, la2, lo2 = (np.radians(np.asarray(v, dtype=float)) for v in (lat1, lon1, lat2, lon2))
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return np.asarray(2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0))), dtype=float)


def road_km(straight_km: ArrayLike) -> NDArray[np.float64]:
    return np.asarray(straight_km, dtype=float) * ROAD_CIRCUITY


def traffic_factor(minute_of_day: float, rain: bool = False) -> float:
    """Speed multiplier. Morning and evening peaks slow every vehicle; rain is rare but severe."""
    hour = (minute_of_day / 60.0) % 24
    factor = 1.0
    if 7.5 <= hour < 9.5:
        factor = 0.72
    elif 17.0 <= hour < 20.5:
        factor = 0.68
    elif 12.5 <= hour < 14.0:
        factor = 0.88
    if rain:
        factor *= 0.6
    return factor


def travel_min(km: float, vehicle: str, minute_of_day: float, rain: bool = False) -> float:
    speed = SPEED_KMH[vehicle] * traffic_factor(minute_of_day, rain)
    return 60.0 * km / speed


def offset_latlon(lat: float, lon: float, dx_m: float, dy_m: float) -> tuple[float, float]:
    """Move a point by metres east (dx) and north (dy)."""
    dlat = dy_m / 111_320.0
    dlon = dx_m / (111_320.0 * np.cos(np.radians(lat)))
    return lat + dlat, lon + dlon
