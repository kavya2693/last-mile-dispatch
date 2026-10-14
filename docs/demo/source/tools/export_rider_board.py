"""Re-run the repo's own dispatcher for ONE hub-day and export one wave's rider board.

Same data, policy (bagging + matching + geofence), seed rule (hub_id * 10_000 + day index) and
config as `make run`, for hub 18 on Saturday 2026-02-14, a treatment hub on a weekend. The
dispatcher's min-cost matcher is wrapped (not changed) so every wave's free riders, bags and
chosen pairs are recorded; the hub-day metrics it returns are checked against
outputs/hub_day_metrics.csv before anything is written.

Drop ETAs replay the simulator's own clock for each trip (repo `geo.travel_min` per leg, plus
the 2-minute handover per stop). The exported riders are honest riders and their customers
are home, so these are exactly the simulator's delivery times.

Run:  cd <repo> && PYTHONPATH=src .venv/bin/python <this file> <out.json> [hub] [date] [HH:MM]
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from last_mile_dispatch import simulate
from last_mile_dispatch.config import SERVICE_MIN_PER_STOP, SLA_MIN, TREATMENT
from last_mile_dispatch.geo import travel_min
from last_mile_dispatch.runner import load

out_path = Path(sys.argv[1])
hub_id = int(sys.argv[2]) if len(sys.argv) > 2 else 18
date = sys.argv[3] if len(sys.argv) > 3 else "2026-02-14"
wave_at = sys.argv[4] if len(sys.argv) > 4 else "21:46"

hubs, riders, days, orders = load(Path("data"))
hub = hubs.set_index("hub_id").loc[hub_id]
day_no = int(days.index[days["date"] == date][0])
rain = bool(days.loc[day_no, "rain"])
od = orders[(orders["hub_id"] == hub_id) & (orders["date"] == date)]
rd = riders[riders["hub_id"] == hub_id].reset_index(drop=True)
hd = simulate.HubDay(hub_id, date, float(hub["lat"]), float(hub["lon"]), rain, od, rd)

waves = []
_min_cost = simulate.assignment.min_cost


def recording_min_cost(avail, vehicles, plans, created, now, rain_):  # type: ignore[no-untyped-def]
    pairs = _min_cost(avail, vehicles, plans, created, now, rain_)
    waves.append({"now": now, "avail": list(avail), "plans": plans, "pairs": pairs})
    return pairs


simulate.assignment.min_cost = recording_min_cost
res = simulate.simulate_hub_day(hd, TREATMENT, hub_id * 10_000 + day_no)
simulate.assignment.min_cost = _min_cost

# The re-run must reproduce the published hub-day exactly.
pub = pd.read_csv("outputs/hub_day_metrics.csv")
pub = pub[(pub["hub_id"] == hub_id) & (pub["date"] == date)].set_index("policy")
for k in ("orders", "delivered", "cancelled", "on_time"):
    assert int(pub.at[TREATMENT.name, k]) == int(res.metrics[k]), k


def hhmm(m: float) -> str:
    return f"{int(m) // 60:02d}:{int(m) % 60:02d}"


o = od.reset_index(drop=True)
created = o["created_min"].to_numpy(float)
xy = simulate._to_xy_km(o["cust_lat"].to_numpy(float), o["cust_lon"].to_numpy(float), hd.hub_lat, hd.hub_lon)
w = next(x for x in waves if hhmm(x["now"]) == wave_at)
now = float(w["now"])
rows = []
for k, (r, b) in enumerate(sorted(w["pairs"], key=lambda p: p[0])):
    plan = w["plans"][b]
    veh = str(rd.at[r, "vehicle"])
    assert not bool(rd.at[r, "remote_marker"]), "pick a wave with honest riders"
    assert not o.loc[plan.orders, "customer_unavailable"].any(), "pick a wave with customers at home"
    clock, stops = now, []
    for leg, i in zip(plan.legs_km[:-1], plan.orders, strict=True):
        clock += travel_min(float(leg), veh, clock, rain)
        stops.append(
            {
                "order_id": int(o.at[i, "order_id"]),
                "x": round(float(xy[i, 0]), 3),
                "y": round(float(xy[i, 1]), 3),
                "eta": hhmm(clock),
                "due": hhmm(created[i] + SLA_MIN),
                "on_time": bool(clock - created[i] <= SLA_MIN),
            }
        )
        clock += SERVICE_MIN_PER_STOP
    clock += travel_min(float(plan.legs_km[-1]), veh, clock, rain)
    rows.append(
        {
            "rider": f"Rider {k + 1:02d}",
            "vehicle": veh,
            "orders": len(plan.orders),
            "km": round(float(plan.legs_km.sum()), 1),
            "leaves": hhmm(now),
            "waited_min": round(float(now - created[plan.orders].min()), 1),
            "first_eta": stops[0]["eta"],
            "last_eta": stops[-1]["eta"],
            "due": min(s["due"] for s in stops),
            "back": hhmm(clock),
            "stops": stops,
        }
    )
chosen = {b for _, b in w["pairs"]}
waiting = [
    {"x": round(float(xy[i, 0]), 3), "y": round(float(xy[i, 1]), 3)}
    for b, p in enumerate(w["plans"])
    if b not in chosen
    for i in p.orders
]
out = {
    "hub": hub_id,
    "date": date,
    "weekday": pd.Timestamp(date).day_name(),
    "rain": rain,
    "wave": wave_at,
    "free_riders": len(w["avail"]),
    "bags_waiting_before": len(w["plans"]),
    "bags_held": len(w["plans"]) - len(w["pairs"]),
    "orders_dispatched": int(sum(r_["orders"] for r_ in rows)),
    "orders_held": len(waiting),
    "roster": len(rd),
    "day": {
        p: {k: int(pub.at[p, k]) for k in ("orders", "delivered", "cancelled", "on_time")}
        for p in ("baseline", TREATMENT.name)
    },
    "rows": rows,
    "waiting_drops": waiting,
    "max_drop_km": round(float(np.hypot(*xy.T).max()), 2),
}
out_path.write_text(json.dumps(out, indent=1))
print({k: v for k, v in out.items() if k not in ("rows", "waiting_drops")})
