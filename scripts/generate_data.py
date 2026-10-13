"""Seeded generator for six weeks of quick-commerce orders across 26 dark-store hubs.

Writes data/hubs.csv, data/riders.csv, data/days.csv and data/orders.csv.gz. The patterns
that matter to dispatch are built in: lunch and evening peaks, a weekend lift, Ramadan
moving demand to the hours around iftar and late night, one rain day that slows traffic and
spikes demand, a few hub outages, high-rise districts where GPS is unreliable, and a small
share of riders who mark failed attempts without reaching the door.

Usage: python scripts/generate_data.py [--seed 7] [--out data]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from last_mile_dispatch.config import (
    EXPERIMENT_DAYS,
    GAMER_SHARE,
    N_HUBS,
    PRE_DAYS,
    SERVICE_RADIUS_KM,
    START_DATE,
)
from last_mile_dispatch.geo import offset_latlon

# A coastal city running south-west to north-east, about 45 km by 14 km.
CITY_ORIGIN = (25.02, 55.06)
COAST_BEARING_DEG = 40.0

RAMADAN_START = pd.Timestamp("2026-02-18")
RAIN_DAY = pd.Timestamp("2026-02-07")
HUB_OUTAGES = {(3, "2026-02-11"), (17, "2026-02-24")}  # (hub, date): hub closed from 15:00


def hourly_profile(ramadan: bool) -> np.ndarray:
    """Share of the day's orders created in each hour 0..23 (hub is open 08:00-24:00)."""
    h = np.arange(24)
    if not ramadan:
        w = 0.6 + 1.1 * np.exp(-0.5 * ((h - 13) / 1.3) ** 2) + 1.8 * np.exp(-0.5 * ((h - 20) / 1.8) ** 2)
    else:
        # Quiet fasting hours, a sharp run-up to iftar (about 18:15) and a long late-night tail.
        w = 0.35 + 1.6 * np.exp(-0.5 * ((h - 17) / 0.8) ** 2) + 2.2 * np.exp(-0.5 * ((h - 22) / 1.5) ** 2)
    w[:8] = 0.0
    return w / w.sum()


def make_hubs(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    theta = np.radians(COAST_BEARING_DEG)
    for i in range(N_HUBS):
        along = rng.uniform(2, 43)  # km along the coast
        inland = rng.uniform(1, 13) ** 1.15 / 1.3  # hubs crowd towards the coast
        dx = 1000 * (along * np.sin(theta) - inland * np.cos(theta))
        dy = 1000 * (along * np.cos(theta) + inland * np.sin(theta))
        lat, lon = offset_latlon(*CITY_ORIGIN, dx, dy)
        base = float(np.clip(rng.lognormal(np.log(380), 0.42), 140, 1100))
        # Coastal hubs serve tower districts; inland hubs serve villas and low-rise.
        highrise_share = float(np.clip(0.75 - 0.06 * inland + rng.normal(0, 0.08), 0.05, 0.9))
        rows.append(
            {
                "hub_id": i,
                "lat": lat,
                "lon": lon,
                "base_daily_orders": round(base, 1),
                "highrise_share": round(highrise_share, 3),
            }
        )
    return pd.DataFrame(rows)


def make_riders(hubs: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    rid = 0
    for hub in hubs.itertuples():
        # Rostered for an ordinary weekday evening peak, so weekends, iftar and rain run tight.
        n = int(np.ceil(hub.base_daily_orders * 0.105 / 2.3 * rng.uniform(0.9, 1.1)))
        n = max(n, 5)
        for k in range(n):
            rows.append(
                {
                    "rider_id": rid,
                    "hub_id": hub.hub_id,
                    "vehicle": "car" if rng.random() < 0.15 else "bike",
                    "shift": "early" if k < round(0.4 * n) else "late",
                    "remote_marker": bool(rng.random() < GAMER_SHARE),
                }
            )
            rid += 1
    return pd.DataFrame(rows)


def make_days() -> pd.DataFrame:
    dates = pd.date_range(START_DATE, periods=PRE_DAYS + EXPERIMENT_DAYS, freq="D")
    df = pd.DataFrame({"date": dates})
    df["dow"] = df["date"].dt.dayofweek
    df["weekend"] = df["dow"].isin([5, 6])
    df["ramadan"] = df["date"] >= RAMADAN_START
    df["rain"] = df["date"] == RAIN_DAY
    df["period"] = np.where(np.arange(len(df)) < PRE_DAYS, "pre", "experiment")
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    return df


def make_orders(hubs: pd.DataFrame, days: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    frames = []
    trend = np.linspace(1.0, 1.06, len(days))  # a growing business
    for d_idx, day in enumerate(days.itertuples()):
        day_mult = trend[d_idx] * (1.18 if day.weekend else 1.0)
        if day.ramadan:
            day_mult *= 1.08
        if day.rain:
            day_mult *= 1.35
        profile = hourly_profile(bool(day.ramadan))
        for hub in hubs.itertuples():
            hub_noise = rng.lognormal(0, 0.08)  # day-to-day noise per hub
            n = rng.poisson(hub.base_daily_orders * day_mult * hub_noise)
            hours = rng.choice(24, size=n, p=profile)
            minute = hours * 60 + rng.uniform(0, 60, size=n)
            if (hub.hub_id, day.date) in HUB_OUTAGES:
                minute = minute[minute < 15 * 60]
                n = len(minute)
            # Drops: most within 2.5 km, a long tail out to the service edge.
            r_km = np.minimum(rng.gamma(2.2, 0.75, size=n), SERVICE_RADIUS_KM)
            ang = rng.uniform(0, 2 * np.pi, size=n)
            lat, lon = offset_latlon(hub.lat, hub.lon, 1000 * r_km * np.cos(ang), 1000 * r_km * np.sin(ang))
            btype = np.where(
                rng.random(n) < hub.highrise_share,
                "highrise",
                np.where(rng.random(n) < 0.55, "villa", "lowrise"),
            ).astype(object)
            btype[rng.random(n) < 0.012] = None  # address parser could not classify the building
            items = 1 + rng.poisson(3.2, size=n)
            items[rng.random(n) < 0.004] = rng.integers(30, 70)  # bulk baskets
            pick = 2.5 + 0.35 * items + rng.gamma(2.0, 0.6, size=n)
            # Genuine "customer unavailable" is more common in towers (lobby access, no answer).
            p_unavail = np.where(btype == "highrise", 0.032, 0.018)
            frames.append(
                pd.DataFrame(
                    {
                        "hub_id": hub.hub_id,
                        "date": day.date,
                        "created_min": np.round(minute, 2),
                        "cust_lat": np.round(lat, 6),
                        "cust_lon": np.round(lon, 6),
                        "building": btype,
                        "items": items,
                        "pick_min": np.round(pick, 2),
                        "customer_unavailable": rng.random(n) < p_unavail,
                    }
                )
            )
    orders = pd.concat(frames, ignore_index=True).sort_values(["date", "hub_id", "created_min"])
    orders.insert(0, "order_id", np.arange(len(orders)))
    return orders.reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=Path("data"))
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)

    hubs = make_hubs(rng)
    riders = make_riders(hubs, rng)
    days = make_days()
    orders = make_orders(hubs, days, rng)

    hubs.to_csv(args.out / "hubs.csv", index=False)
    riders.to_csv(args.out / "riders.csv", index=False)
    days.to_csv(args.out / "days.csv", index=False)
    orders.to_csv(args.out / "orders.csv.gz", index=False, compression="gzip")
    print(
        f"hubs={len(hubs)} riders={len(riders)} days={len(days)} orders={len(orders):,} "
        f"(mean {len(orders) / len(days) / len(hubs):.0f} per hub-day)"
    )


if __name__ == "__main__":
    main()
