"""Geofence check on "customer unavailable" marks.

A rider who really waited at the door leaves a short trail of GPS pings near the drop.
A rider who marked the attempt from the road does not. The rule is deliberately simple
so an operations lead can explain a flag to the rider: fewer than ``min_inside`` of the
last few pings within ``radius_m`` of the customer means the mark is flagged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from last_mile_dispatch.config import GEOFENCE_MIN_PINGS_INSIDE, GEOFENCE_RADIUS_M
from last_mile_dispatch.geo import haversine_km


def ping_distances_m(
    ping_lat: NDArray[np.float64],
    ping_lon: NDArray[np.float64],
    cust_lat: NDArray[np.float64],
    cust_lon: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Distances (m) from each ping to its event's customer. Pings are (events, k); NaN = dropout."""
    return 1000.0 * haversine_km(ping_lat, ping_lon, np.asarray(cust_lat)[:, None], np.asarray(cust_lon)[:, None])


def flag_attempts(
    dist_m: NDArray[np.float64],
    radius_m: float = GEOFENCE_RADIUS_M,
    min_inside: int = GEOFENCE_MIN_PINGS_INSIDE,
) -> NDArray[np.bool_]:
    """True where the mark looks remote. A trail with every ping missing is flagged too:
    an attempt that cannot be located cannot be accepted without a call to the customer."""
    inside = np.nan_to_num(dist_m, nan=np.inf) <= radius_m
    return np.asarray(inside.sum(axis=1) < min_inside)


def confusion(flagged: NDArray[np.bool_], is_fake: NDArray[np.bool_]) -> dict[str, float]:
    flagged = np.asarray(flagged, dtype=bool)
    is_fake = np.asarray(is_fake, dtype=bool)
    tp = int((flagged & is_fake).sum())
    fp = int((flagged & ~is_fake).sum())
    fn = int((~flagged & is_fake).sum())
    tn = int((~flagged & ~is_fake).sum())
    return {
        "events": tp + fp + fn + tn,
        "fake": tp + fn,
        "genuine": fp + tn,
        "flagged": tp + fp,
        "precision": tp / (tp + fp) if tp + fp else float("nan"),
        "recall": tp / (tp + fn) if tp + fn else float("nan"),
        "false_flag_rate": fp / (fp + tn) if fp + tn else float("nan"),
    }


def evaluate(events: pd.DataFrame, dist_cols: list[str], radius_m: float = GEOFENCE_RADIUS_M) -> pd.DataFrame:
    """Precision/recall overall and split by the cases that are hard for different reasons:
    tower buildings (GPS multipath makes genuine riders look remote) and fakes marked close
    to the door (the rider stopped at the building but did not go up)."""
    dist = events[dist_cols].to_numpy(dtype=float)
    flagged = flag_attempts(dist, radius_m)
    fake = events["is_fake"].to_numpy(dtype=bool)
    rows = [{"slice": "all", **confusion(flagged, fake)}]
    building = events["building"].fillna("unknown").to_numpy()
    for b in ("highrise", "lowrise", "villa", "unknown"):
        m = building == b
        if m.any():
            rows.append({"slice": f"building={b}", **confusion(flagged[m], fake[m])})
    true_d = events["true_mark_dist_m"].to_numpy(dtype=float)
    for lo, hi, label in ((0, 300, "fake marked <300 m"), (300, 1000, "fake marked 300-1000 m"), (1000, 1e9, "fake marked >1 km")):
        m = fake & (true_d >= lo) & (true_d < hi)
        if m.any():
            rows.append({"slice": label, **confusion(flagged[m], fake[m])})
    return pd.DataFrame(rows)


def radius_sweep(events: pd.DataFrame, dist_cols: list[str], radii: list[float]) -> pd.DataFrame:
    dist = events[dist_cols].to_numpy(dtype=float)
    fake = events["is_fake"].to_numpy(dtype=bool)
    return pd.DataFrame([{"radius_m": r, **confusion(flag_attempts(dist, r), fake)} for r in radii])
