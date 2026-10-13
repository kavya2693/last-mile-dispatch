"""Run every hub-day under every policy, in parallel across hubs."""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import pandas as pd

from last_mile_dispatch.config import Policy
from last_mile_dispatch.simulate import HubDay, simulate_hub_day


def load(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    hubs = pd.read_csv(data_dir / "hubs.csv")
    riders = pd.read_csv(data_dir / "riders.csv")
    days = pd.read_csv(data_dir / "days.csv")
    orders = pd.read_csv(data_dir / "orders.csv.gz")
    return hubs, riders, days, orders


def _run_hub(
    args: tuple[pd.Series, pd.DataFrame, pd.DataFrame, pd.DataFrame, Sequence[Policy]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    hub, riders, days, orders, policies = args
    metrics: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    by_date = dict(tuple(orders.groupby("date")))
    for day_no, day in zip(days.index.to_numpy(dtype=int), days.itertuples(), strict=True):
        od = by_date.get(day.date, orders.iloc[:0])
        hd = HubDay(
            int(hub.hub_id), str(day.date), float(hub.lat), float(hub.lon), bool(day.rain), od, riders
        )
        # Same seed for every policy on a hub-day: differences come from the policy, not the dice.
        seed = int(hub.hub_id) * 10_000 + int(day_no)
        for p in policies:
            res = simulate_hub_day(hd, p, seed)
            metrics.append({**res.metrics, "period": day.period})
            for e in res.events:
                e["policy"] = p.name
            events.extend(res.events)
    return metrics, events


def run_all(
    hubs: pd.DataFrame,
    riders: pd.DataFrame,
    days: pd.DataFrame,
    orders: pd.DataFrame,
    policies: Sequence[Policy],
    workers: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    jobs = [
        (hub, riders[riders.hub_id == hub.hub_id], days, orders[orders.hub_id == hub.hub_id], policies)
        for _, hub in hubs.iterrows()
    ]
    metrics: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    if workers <= 1:
        results = map(_run_hub, jobs)
        for m, e in results:
            metrics.extend(m)
            events.extend(e)
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for m, e in ex.map(_run_hub, jobs):
                metrics.extend(m)
                events.extend(e)
    return pd.DataFrame(metrics), pd.DataFrame(events)
