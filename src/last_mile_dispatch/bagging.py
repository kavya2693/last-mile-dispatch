"""Order bagging: put orders whose drops are close in space and time into one rider trip.

Greedy by age. The oldest waiting order seeds a bag, and nearby orders join it only if the
seed customer's delivery is delayed by no more than ``BAG_MAX_EXTRA_MIN``. Seeding by age
keeps the bagger from starving an old, isolated order in favour of a dense cluster.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from last_mile_dispatch.config import (
    BAG_CAPACITY,
    BAG_MAX_CREATED_GAP_MIN,
    BAG_MAX_DROP_GAP_KM,
    BAG_MAX_EXTRA_MIN,
    ROAD_CIRCUITY,
    SERVICE_MIN_PER_STOP,
    SPEED_KMH,
)


def route_order(xy: NDArray[np.float64]) -> list[int]:
    """Nearest-neighbour stop order starting at the hub (origin). Exact for bags of up to
    three stops in the cases that matter here, and cheap enough to run every wave."""
    remaining = list(range(len(xy)))
    pos = np.zeros(2)
    seq: list[int] = []
    while remaining:
        d = np.hypot(*(xy[remaining] - pos).T)
        k = remaining.pop(int(np.argmin(d)))
        seq.append(k)
        pos = xy[k]
    return seq


def route_legs_km(xy: NDArray[np.float64], seq: list[int]) -> NDArray[np.float64]:
    """Road km of each leg: hub to first stop, between stops, last stop back to hub."""
    pts = np.vstack([np.zeros(2), xy[seq], np.zeros(2)])
    return np.asarray(np.hypot(*np.diff(pts, axis=0).T) * ROAD_CIRCUITY, dtype=float)


def _minutes_to_stop(xy: NDArray[np.float64], seq: list[int], target: int) -> float:
    legs = route_legs_km(xy, seq)
    pos = seq.index(target)
    km = legs[: pos + 1].sum()
    return 60.0 * km / SPEED_KMH["bike"] + SERVICE_MIN_PER_STOP * pos


def make_bags(
    pending: list[int],
    created: NDArray[np.float64],
    xy: NDArray[np.float64],
    enabled: bool,
) -> list[list[int]]:
    """Split pending order indices into bags. With bagging off, every order is its own bag."""
    if not enabled:
        return [[i] for i in pending]
    order = sorted(pending, key=lambda i: created[i])
    used: set[int] = set()
    bags: list[list[int]] = []
    for seed in order:
        if seed in used:
            continue
        used.add(seed)
        bag = [seed]
        cands = [
            j
            for j in order
            if j not in used
            and abs(created[j] - created[seed]) <= BAG_MAX_CREATED_GAP_MIN
            and np.hypot(*(xy[j] - xy[seed])) <= BAG_MAX_DROP_GAP_KM
        ]
        cands.sort(key=lambda j: float(np.hypot(*(xy[j] - xy[seed]))))
        direct = _minutes_to_stop(xy[[seed]], [0], 0)
        for j in cands:
            if len(bag) >= BAG_CAPACITY:
                break
            trial = [*bag, j]
            local = xy[trial]
            seq = route_order(local)
            if _minutes_to_stop(local, seq, 0) - direct <= BAG_MAX_EXTRA_MIN:
                bag = trial
                used.add(j)
        bags.append(bag)
    return bags
