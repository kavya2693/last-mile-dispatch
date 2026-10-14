"""Export the numbers drawn on slides 02, 06 and 10 from the repo's own data and outputs.

- daily: cancellation rate per experiment day, all 26 hubs pooled, FIFO baseline vs the
  treatment (bagging + matching + geofence), from outputs/hub_day_metrics.csv.
- stress: cost per delivered order and cancellation rate by day type, from
  outputs/stress_split.csv (the README's "where the cost saving comes from" table).
- totals: orders, cancelled and delivered over the four experiment weeks, per policy.
- hubs: hub positions in km from the city's centroid, from data/hubs.csv.

Run:  cd <repo> && python3 <this file> <out.json>
"""

import json
import sys

import numpy as np
import pandas as pd

KM_PER_DEG_LAT = 111.32
BASE, TREAT = "baseline", "bagging+matching+geofence"

m = pd.read_csv("outputs/hub_day_metrics.csv")
days = pd.read_csv("data/days.csv")
g = m.groupby(["date", "policy"])[["orders", "cancelled"]].sum()
g["rate"] = g["cancelled"] / g["orders"]
exp = days[days["period"] == "experiment"]
daily = [
    {
        "date": d.date,
        "dow": int(d.dow),
        "weekend": bool(d.weekend),
        "ramadan": bool(d.ramadan),
        "rain": bool(d.rain),
        "base": round(float(g.at[(d.date, BASE), "rate"]), 4),
        "treat": round(float(g.at[(d.date, TREAT), "rate"]), 4),
    }
    for d in exp.itertuples()
]

s = pd.read_csv("outputs/stress_split.csv").set_index(["day_type", "policy"])
stress = [
    {
        "day_type": t,
        "orders": int(s.at[(t, BASE), "orders"]),
        "cost_base": round(float(s.at[(t, BASE), "cost_per_delivered"]), 2),
        "cost_treat": round(float(s.at[(t, TREAT), "cost_per_delivered"]), 2),
        "cost_chg_pct": round(
            float(s.at[(t, TREAT), "cost_per_delivered"] / s.at[(t, BASE), "cost_per_delivered"] - 1) * 100, 1
        ),
        "cancel_base": round(float(s.at[(t, BASE), "cancel_rate"]), 4),
        "cancel_treat": round(float(s.at[(t, TREAT), "cancel_rate"]), 4),
    }
    for t in ("ordinary weekday", "weekend or Ramadan", "rain day")
]

h = pd.read_csv("data/hubs.csv")
lat0, lon0 = h["lat"].mean(), h["lon"].mean()
kx = KM_PER_DEG_LAT * np.cos(np.radians(lat0))
hubs = [
    {"hub": int(r.hub_id), "x": round((r.lon - lon0) * kx, 2), "y": round((r.lat - lat0) * KM_PER_DEG_LAT, 2)}
    for r in h.itertuples()
]

tot = m.groupby("policy")[["orders", "cancelled", "delivered"]].sum()
totals = {k: {c: int(tot.at[p, c]) for c in tot.columns} for k, p in (("base", BASE), ("treat", TREAT))}

out = {"daily": daily, "stress": stress, "hubs": hubs, "totals": totals}
with open(sys.argv[1], "w") as fh:
    json.dump(out, fh, indent=1)
print(len(daily), "days;", [(x["day_type"], x["cost_base"], x["cost_treat"]) for x in stress])
