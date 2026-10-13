"""Rider assignment: FIFO baseline and min-cost matching.

FIFO is what most hubs run by hand: the rider who has waited longest takes the oldest bag.
Matching prices every rider-bag pair (km cost of that rider's vehicle, minutes late against
the promise, minutes the customers have already waited, a credit per order) and solves the
assignment with the Hungarian method. When bags outnumber free riders, the same costs decide
which bags leave now.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import linear_sum_assignment

from last_mile_dispatch.config import (
    COST_PER_KM,
    LATE_COST_PER_MIN,
    ORDER_DISPATCH_CREDIT,
    SERVICE_MIN_PER_STOP,
    SLA_MIN,
    SPEED_KMH,
    WAIT_COST_PER_MIN,
)
from last_mile_dispatch.geo import traffic_factor


@dataclass(frozen=True)
class BagPlan:
    orders: list[int]  # order indices in stop sequence
    legs_km: NDArray[np.float64]  # hub->s1, s1->s2, ..., sN->hub


def fifo(
    riders: Sequence[int], free_at: NDArray[np.float64], bags: Sequence[BagPlan], created: NDArray[np.float64]
) -> list[tuple[int, int]]:
    """Return (rider, bag index) pairs."""
    r_sorted = sorted(riders, key=lambda r: free_at[r])
    b_sorted = sorted(range(len(bags)), key=lambda b: min(created[i] for i in bags[b].orders))
    return list(zip(r_sorted, b_sorted, strict=False))


def pair_cost(bag: BagPlan, vehicle: str, now: float, created: NDArray[np.float64], rain: bool) -> float:
    speed = SPEED_KMH[vehicle] * traffic_factor(now, rain)
    cum_km = np.cumsum(bag.legs_km[:-1])
    eta = now + 60.0 * cum_km / speed + SERVICE_MIN_PER_STOP * np.arange(len(bag.orders))
    promised = created[bag.orders] + SLA_MIN
    late = np.maximum(0.0, eta - promised).sum()
    waited = (now - created[bag.orders]).sum()
    return float(
        bag.legs_km.sum() * COST_PER_KM[vehicle]
        + LATE_COST_PER_MIN * late
        - WAIT_COST_PER_MIN * waited
        - ORDER_DISPATCH_CREDIT * len(bag.orders)
    )


def min_cost(
    riders: Sequence[int],
    vehicles: Sequence[str],
    bags: Sequence[BagPlan],
    created: NDArray[np.float64],
    now: float,
    rain: bool,
) -> list[tuple[int, int]]:
    if not riders or not bags:
        return []
    # Riders differ only by vehicle, so price each bag once per vehicle type and broadcast.
    by_vehicle = {v: np.array([pair_cost(b, v, now, created, rain) for b in bags]) for v in set(vehicles)}
    cost = np.vstack([by_vehicle[vehicles[k]] for k in range(len(riders))])
    rows, cols = linear_sum_assignment(cost)
    return [(riders[r], int(c)) for r, c in zip(rows, cols, strict=True)]
