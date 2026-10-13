"""Wave-based dispatch simulator for one hub-day under one policy.

Every two minutes the dispatcher looks at orders that are picked and waiting and riders who
are back at the hub, forms bags, assigns them, and plays each trip out: travel under the
hour's traffic, a two-minute handover per stop, a real failed attempt where the customer is
not in, and a remote "customer unavailable" mark when a rider who games the system decides
to skip a stop. Random draws are made per order before the loop, so two policies run on the
same hub-day see the same customers, the same GPS noise and the same temptations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from last_mile_dispatch import assignment, bagging
from last_mile_dispatch.config import (
    CANCEL_AFTER_MIN,
    CLOSE_MIN,
    COST_PER_KM,
    FORCED_COMPLETION_PENALTY_MIN,
    GAMER_FAKE_RATE,
    GENUINE_ATTEMPT_WAIT_MIN,
    HOURLY_PAY,
    OPEN_MIN,
    PING_DROPOUT,
    PING_INTERVAL_S,
    PINGS_PER_EVENT,
    SERVICE_MIN_PER_STOP,
    SHIFT_HOURS,
    SLA_MIN,
    SPEED_KMH,
    WAVE_MIN,
    Policy,
)
from last_mile_dispatch.geo import traffic_factor, travel_min
from last_mile_dispatch.geofence import flag_attempts

KM_PER_DEG_LAT = 111.32

# GPS error per ping (m, each axis) and the chance a whole trail is displaced by multipath.
GPS_SD_M = {"highrise": 25.0, "lowrise": 10.0, "villa": 6.0, "unknown": 15.0}
MULTIPATH_P = {"highrise": 0.07, "lowrise": 0.015, "villa": 0.005, "unknown": 0.02}

STATUS_PENDING, STATUS_DELIVERED, STATUS_FAILED_GENUINE, STATUS_FAKE_ACCEPTED, STATUS_CANCELLED = range(5)


@dataclass
class HubDay:
    hub_id: int
    date: str
    hub_lat: float
    hub_lon: float
    rain: bool
    orders: pd.DataFrame  # one hub-day of orders
    riders: pd.DataFrame  # the hub's roster


@dataclass
class Draws:
    """Per-order randomness fixed before the simulation (common random numbers)."""

    fake_u: NDArray[np.float64]
    close_mark: NDArray[np.bool_]
    mark_frac: NDArray[np.float64]
    close_dist_m: NDArray[np.float64]
    noise: NDArray[np.float64]  # (n, pings, 2) standard normal
    dropout: NDArray[np.bool_]  # (n, pings)
    multipath: NDArray[np.bool_]
    multipath_off: NDArray[np.float64]  # (n, 2) metres

    @classmethod
    def make(cls, n: int, building: NDArray[Any], seed: int) -> Draws:
        rng = np.random.default_rng(seed)
        mp_p = np.array([MULTIPATH_P[b] for b in building])
        ang = rng.uniform(0, 2 * np.pi, n)
        mag = rng.uniform(100, 350, n)
        return cls(
            fake_u=rng.random(n),
            close_mark=rng.random(n) < 0.25,
            mark_frac=rng.uniform(0.3, 0.97, n),
            close_dist_m=rng.uniform(40, 220, n),
            noise=rng.standard_normal((n, PINGS_PER_EVENT, 2)),
            dropout=rng.random((n, PINGS_PER_EVENT)) < PING_DROPOUT,
            multipath=rng.random(n) < mp_p,
            multipath_off=np.c_[mag * np.cos(ang), mag * np.sin(ang)],
        )


@dataclass
class Result:
    metrics: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)


def _to_xy_km(
    lat: NDArray[np.float64], lon: NDArray[np.float64], lat0: float, lon0: float
) -> NDArray[np.float64]:
    kx = KM_PER_DEG_LAT * np.cos(np.radians(lat0))
    return np.c_[(lon - lon0) * kx, (lat - lat0) * KM_PER_DEG_LAT]


def _ping_distances(
    i: int,
    mark_xy: NDArray[np.float64],
    back_dir: NDArray[np.float64],
    moving_kmh: float,
    cust_xy: NDArray[np.float64],
    building: str,
    d: Draws,
) -> NDArray[np.float64]:
    """Distances (m) to the customer of the last few pings before a mark. A moving rider's
    trail stretches back along the road; a rider at the door has a stationary trail."""
    step_km = moving_kmh / 60.0 * PING_INTERVAL_S / 60.0
    k = np.arange(PINGS_PER_EVENT)[:, None]
    true_pts = mark_xy[None, :] + back_dir[None, :] * step_km * k
    err_m = d.noise[i] * GPS_SD_M[building]
    if d.multipath[i]:
        err_m = err_m + d.multipath_off[i][None, :]
    pts_m = true_pts * 1000.0 + err_m
    dist = np.hypot(*(pts_m - cust_xy[None, :] * 1000.0).T)
    dist[d.dropout[i]] = np.nan
    return np.asarray(dist, dtype=float)


def simulate_hub_day(hd: HubDay, policy: Policy, seed: int) -> Result:
    o = hd.orders.reset_index(drop=True)
    n = len(o)
    created = o["created_min"].to_numpy(float)
    ready = created + o["pick_min"].to_numpy(float)
    xy = _to_xy_km(o["cust_lat"].to_numpy(float), o["cust_lon"].to_numpy(float), hd.hub_lat, hd.hub_lon)
    building = o["building"].fillna("unknown").to_numpy()
    unavailable = o["customer_unavailable"].to_numpy(bool)
    draws = Draws.make(n, building, seed)

    vehicles = hd.riders["vehicle"].to_numpy()
    remote = hd.riders["remote_marker"].to_numpy(bool)
    shift_start = np.where(
        hd.riders["shift"].to_numpy() == "early", OPEN_MIN, OPEN_MIN + SHIFT_HOURS * 60
    ).astype(float)
    shift_end = shift_start + SHIFT_HOURS * 60
    n_r = len(vehicles)
    free_at = shift_start.copy()
    busy = np.zeros(n_r)
    overtime = np.zeros(n_r)
    km_by_rider = np.zeros(n_r)

    status = np.full(n, STATUS_PENDING)
    delivered_at = np.full(n, np.nan)
    events: list[dict[str, Any]] = []
    false_flags = flagged_fakes = 0

    by_ready = np.argsort(ready, kind="stable")
    ptr = 0
    pending: list[int] = []
    t = float(OPEN_MIN)
    while t <= CLOSE_MIN + CANCEL_AFTER_MIN:
        while ptr < n and ready[by_ready[ptr]] <= t:
            pending.append(int(by_ready[ptr]))
            ptr += 1
        still = []
        for i in pending:
            if t - created[i] > CANCEL_AFTER_MIN:
                status[i] = STATUS_CANCELLED
            else:
                still.append(i)
        pending = still
        avail = [r for r in range(n_r) if shift_start[r] <= t < shift_end[r] and free_at[r] <= t]
        if pending and avail:
            groups = bagging.make_bags(pending, created, xy, policy.bagging)
            plans = []
            for g in groups:
                seq = bagging.route_order(xy[g])
                ordered = [g[s] for s in seq]
                plans.append(
                    assignment.BagPlan(ordered, bagging.route_legs_km(xy[ordered], list(range(len(ordered)))))
                )
            if policy.matching:
                pairs = assignment.min_cost(
                    avail, [str(vehicles[r]) for r in avail], plans, created, t, hd.rain
                )
            else:
                pairs = assignment.fifo(avail, free_at, plans, created)
            dispatched: set[int] = set()
            for r, b in pairs:
                plan = plans[b]
                dispatched.update(plan.orders)
                clock = t
                pos = np.zeros(2)
                km = 0.0
                veh = str(vehicles[r])
                for i in plan.orders:
                    leg_vec = xy[i] - pos
                    leg_km = float(np.hypot(*leg_vec)) * 1.35
                    heading = leg_vec / max(float(np.hypot(*leg_vec)), 1e-9)
                    speed = SPEED_KMH[veh] * traffic_factor(clock, hd.rain)
                    fake = remote[r] and not unavailable[i] and draws.fake_u[i] < GAMER_FAKE_RATE
                    if fake:
                        if draws.close_mark[i]:
                            mark_xy = xy[i] - heading * draws.close_dist_m[i] / 1000.0
                        else:
                            mark_xy = pos + leg_vec * draws.mark_frac[i]
                        part_km = float(np.hypot(*(mark_xy - pos))) * 1.35
                        clock += travel_min(part_km, veh, clock, hd.rain)
                        km += part_km
                        # A rider who stops at the building and marks from the kerb stands still;
                        # one who marks from the road is still moving.
                        mark_speed = 0.0 if draws.close_mark[i] else speed
                        dist = _ping_distances(i, mark_xy, -heading, mark_speed, xy[i], building[i], draws)
                        flagged = bool(flag_attempts(dist[None, :])[0])
                        events.append(
                            _event(hd, o, i, True, float(np.hypot(*(mark_xy - xy[i]))) * 1000, dist, flagged)
                        )
                        if policy.geofence and flagged:
                            flagged_fakes += 1
                            rest_km = float(np.hypot(*(xy[i] - mark_xy))) * 1.35
                            clock += travel_min(rest_km, veh, clock, hd.rain) + FORCED_COMPLETION_PENALTY_MIN
                            km += rest_km
                            status[i] = STATUS_DELIVERED
                            delivered_at[i] = clock
                            clock += SERVICE_MIN_PER_STOP
                            pos = xy[i]
                        else:
                            status[i] = STATUS_FAKE_ACCEPTED
                            pos = mark_xy
                        continue
                    clock += travel_min(leg_km, veh, clock, hd.rain)
                    km += leg_km
                    pos = xy[i]
                    if unavailable[i]:
                        clock += GENUINE_ATTEMPT_WAIT_MIN
                        dist = _ping_distances(i, xy[i], np.zeros(2), 0.0, xy[i], building[i], draws)
                        flagged = bool(flag_attempts(dist[None, :])[0])
                        events.append(_event(hd, o, i, False, 0.0, dist, flagged))
                        if policy.geofence and flagged:
                            false_flags += 1
                            clock += FORCED_COMPLETION_PENALTY_MIN  # rider has to call in and re-verify
                        status[i] = STATUS_FAILED_GENUINE
                    else:
                        status[i] = STATUS_DELIVERED
                        delivered_at[i] = clock
                        clock += SERVICE_MIN_PER_STOP
                back_km = float(np.hypot(*pos)) * 1.35
                clock += travel_min(back_km, veh, clock, hd.rain)
                km += back_km
                busy[r] += clock - t
                overtime[r] += max(0.0, clock - max(t, shift_end[r]))
                km_by_rider[r] += km
                free_at[r] = clock
            pending = [i for i in pending if i not in dispatched]
        t += WAVE_MIN
    for i in pending:
        status[i] = STATUS_CANCELLED

    shift_min = SHIFT_HOURS * 60.0 * n_r
    pay = sum(HOURLY_PAY[str(v)] for v in vehicles) * SHIFT_HOURS + sum(
        overtime[r] / 60.0 * HOURLY_PAY[str(vehicles[r])] for r in range(n_r)
    )
    km_cost = sum(km_by_rider[r] * COST_PER_KM[str(vehicles[r])] for r in range(n_r))
    delivered = status == STATUS_DELIVERED
    lead = delivered_at[delivered] - created[delivered]
    n_del = int(delivered.sum())
    cost = pay + km_cost
    metrics = {
        "hub_id": hd.hub_id,
        "date": hd.date,
        "policy": policy.name,
        "orders": n,
        "delivered": n_del,
        "cancelled": int((status == STATUS_CANCELLED).sum()),
        "failed_genuine": int((status == STATUS_FAILED_GENUINE).sum()),
        "fake_accepted": int((status == STATUS_FAKE_ACCEPTED).sum()),
        "fake_flagged": flagged_fakes,
        "false_flags": false_flags,
        "fleet_cost": cost,
        "km": float(km_by_rider.sum()),
        "busy_min": float(busy.sum()),
        "shift_min": shift_min,
        "riders": n_r,
        "on_time": int((lead <= SLA_MIN).sum()),
        "lead_mean": float(lead.mean()) if n_del else float("nan"),
        "lead_p90": float(np.quantile(lead, 0.9)) if n_del else float("nan"),
        "cost_per_delivered": cost / n_del if n_del else float("nan"),
        "utilization": float(busy.sum()) / shift_min,
    }
    return Result(metrics, events)


def _event(
    hd: HubDay,
    o: pd.DataFrame,
    i: int,
    is_fake: bool,
    true_d_m: float,
    dist: NDArray[np.float64],
    flagged: bool,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "order_id": int(o["order_id"].to_numpy()[i]),
        "hub_id": hd.hub_id,
        "date": hd.date,
        "building": o.at[i, "building"],
        "is_fake": is_fake,
        "true_mark_dist_m": true_d_m,
        "flagged": flagged,
    }
    row.update({f"d{k}": float(v) for k, v in enumerate(dist)})
    return row
