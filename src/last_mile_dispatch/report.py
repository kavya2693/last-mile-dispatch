"""Turn hub-day results into the tables the README quotes."""

from __future__ import annotations

import pandas as pd

# Metrics read out in the experiment, and which way is good.
AB_METRICS = [
    "cost_per_delivered",
    "orders_per_rider_hour",
    "utilization",
    "fake_accepted_per_1k",
    "on_time_share_of_orders",
    "cancel_rate",
    "lead_p90",
]
LOWER_IS_BETTER = ["cost_per_delivered", "fake_accepted_per_1k", "cancel_rate", "lead_p90"]


SUM_COLS = [
    "orders",
    "delivered",
    "cancelled",
    "fake_accepted",
    "false_flags",
    "fleet_cost",
    "km",
    "busy_min",
    "shift_min",
    "on_time",
]


def _ratios(sums: pd.Series) -> dict[str, float]:
    g = {k: float(sums[k]) for k in SUM_COLS}
    return {
        "orders": g["orders"],
        "delivered": g["delivered"],
        "cost_per_delivered": g["fleet_cost"] / g["delivered"],
        "orders_per_rider_hour": g["delivered"] / (g["shift_min"] / 60.0),
        "utilization": g["busy_min"] / g["shift_min"],
        "fake_accepted_per_1k": 1000.0 * g["fake_accepted"] / g["orders"],
        "on_time_share_of_orders": g["on_time"] / g["orders"],
        "on_time_share_of_delivered": g["on_time"] / g["delivered"],
        "cancel_rate": g["cancelled"] / g["orders"],
        "false_flags_per_1k": 1000.0 * g["false_flags"] / g["orders"],
        "km_per_delivered": g["km"] / g["delivered"],
    }


def pooled_by_policy(hub_days: pd.DataFrame) -> pd.DataFrame:
    """Every hub and every experiment day pooled: the ablation table."""
    sums = hub_days.groupby("policy", sort=False)[SUM_COLS].sum()
    out = pd.DataFrame({p: _ratios(sums.loc[p]) for p in sums.index}).T
    out["lead_p90"] = hub_days.groupby("policy", sort=False)["lead_p90"].mean()
    return out


def per_hub(hub_days: pd.DataFrame, policy: str) -> pd.DataFrame:
    """One row per hub over the period: the unit the experiment analyses."""
    d = hub_days[hub_days["policy"] == policy]
    sums = d.groupby("hub_id")[SUM_COLS].sum()
    out = pd.DataFrame({h: _ratios(sums.loc[h]) for h in sums.index}).T
    out["lead_p90"] = d.groupby("hub_id")["lead_p90"].mean()
    out.index.name = "hub_id"
    return out.reset_index()


def stress_split(hub_days: pd.DataFrame, days: pd.DataFrame) -> pd.DataFrame:
    """Same pooled metrics on ordinary days and on stressed days (weekend, Ramadan, rain).
    A blended number hides that the policies only differ much when riders are short."""
    d = hub_days.merge(days[["date", "weekend", "ramadan", "rain"]], on="date")
    d["day_type"] = "ordinary weekday"
    d.loc[d["weekend"] | d["ramadan"], "day_type"] = "weekend or Ramadan"
    d.loc[d["rain"], "day_type"] = "rain day"
    rows = []
    for (dt, pol), g in d.groupby(["day_type", "policy"], sort=False):
        rows.append({"day_type": dt, "policy": pol, **_ratios(g[SUM_COLS].sum())})
    return pd.DataFrame(rows)


def fmt_table(df: pd.DataFrame, floatfmt: str = ".3f") -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for _, row in df.iterrows():
        cells = [format(v, floatfmt) if isinstance(v, float) else str(v) for v in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
