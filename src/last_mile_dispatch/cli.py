"""One command: simulate both periods, read out the experiment, evaluate the geofence.

dispatch                      full run (26 hubs, 14 pre-period days, 28 experiment days)
dispatch --quick              8 hubs and 7 experiment days, for CI
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from last_mile_dispatch import experiment, report
from last_mile_dispatch.config import ALL_POLICIES, BASELINE, PINGS_PER_EVENT, TREATMENT
from last_mile_dispatch.geofence import evaluate, radius_sweep
from last_mile_dispatch.runner import load, run_all

ASSIGNMENT_SEED = 2026


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--out", type=Path, default=Path("outputs"))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--draws", type=int, default=500, help="re-randomisation draws for the CI check")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    started = time.time()

    hubs, riders, days, orders = load(args.data)
    if args.quick:
        hubs = hubs.head(8)
        pre_days = days[days.period == "pre"].head(5)
        exp_days = days[days.period == "experiment"].head(7)
        days = pd.concat([pre_days, exp_days])
        args.draws = min(args.draws, 100)
    pre, exp = days[days.period == "pre"], days[days.period == "experiment"]
    n_riders = int(riders.hub_id.isin(hubs.hub_id).sum())
    print(f"hubs={len(hubs)} riders={n_riders} pre_days={len(pre)} exp_days={len(exp)}")

    pre_m, _ = run_all(hubs, riders, pre, orders, [BASELINE], args.workers)
    exp_m, events = run_all(hubs, riders, exp, orders, ALL_POLICIES, args.workers)
    print(f"simulated {len(pre_m) + len(exp_m):,} hub-day-policy runs in {time.time() - started:.0f}s")
    exp_m.to_csv(args.out / "hub_day_metrics.csv", index=False)

    # Ablation: every policy on every hub-day, so the effect of each component is exact.
    ablation = report.pooled_by_policy(exp_m)
    ablation.to_csv(args.out / "ablation.csv")
    stress = report.stress_split(exp_m, days)
    stress.to_csv(args.out / "stress_split.csv", index=False)

    # Experiment: half the hubs see the treatment, half the baseline. Only that is observed.
    pre_hub = report.per_hub(pre_m, BASELINE.name).set_index("hub_id")
    rng = np.random.default_rng(ASSIGNMENT_SEED)
    arm = experiment.paired_stratified_assignment(
        list(pre_hub.index), list(pre_hub["orders"] / len(pre)), rng
    )
    base_hub = report.per_hub(exp_m, BASELINE.name).set_index("hub_id")
    treat_hub = report.per_hub(exp_m, TREATMENT.name).set_index("hub_id")
    observed = pd.concat(
        [
            treat_hub.loc[[h for h, a in arm.items() if a == "treatment"]],
            base_hub.loc[[h for h, a in arm.items() if a == "control"]],
        ]
    ).reset_index()
    observed["arm"] = observed["hub_id"].map(arm)
    observed.to_csv(args.out / "ab_hub_outcomes.csv", index=False)
    ab = experiment.readout(observed, arm, report.AB_METRICS, rng, report.LOWER_IS_BETTER)
    ab["true_effect_all_hubs"] = [float((treat_hub[m] - base_hub[m]).mean()) for m in report.AB_METRICS]
    ab.to_csv(args.out / "ab_readout.csv", index=False)

    # Power from the pre-period: what this design can and cannot detect.
    n_arm = len(hubs) // 2
    true_eff = dict(zip(ab["metric"], ab["true_effect_all_hubs"], strict=True))
    power_rows = []
    for m in report.AB_METRICS:
        sd = float(pre_hub[m].std(ddof=1))
        mde = experiment.mde(sd, n_arm)
        eff = float(true_eff[m])
        power_rows.append(
            {
                "metric": m,
                "pre_mean": float(pre_hub[m].mean()),
                "between_hub_sd": sd,
                "mde_80pct_power": mde,
                "mde_rel": mde / float(pre_hub[m].mean()) if pre_hub[m].mean() else float("nan"),
                "true_effect": eff,
                "hubs_per_arm_needed": experiment.hubs_needed(sd, eff) if eff else None,
            }
        )
    power = pd.DataFrame(power_rows)
    power.to_csv(args.out / "power.csv", index=False)

    # Check the CIs themselves: both potential outcomes are known, so coverage is measurable.
    rr_rows = []
    rr_rng = np.random.default_rng(ASSIGNMENT_SEED + 1)
    for m in report.AB_METRICS:
        res = experiment.rerandomisation_check(
            base_hub[m], treat_hub[m], pre_hub["orders"], rr_rng, n_draws=args.draws, n_boot=1000
        )
        rr_rows.append({"metric": m, **res})
    rr = pd.DataFrame(rr_rows)
    rr.to_csv(args.out / "rerandomisation.csv", index=False)

    # Geofence, judged on the baseline arm where no mark was enforced, so riders' behaviour
    # is the same whether or not a mark would have been flagged.
    dist_cols = [f"d{k}" for k in range(PINGS_PER_EVENT)]
    ev = events[events["policy"] == BASELINE.name]
    geo = evaluate(ev, dist_cols)
    geo.to_csv(args.out / "geofence_eval.csv", index=False)
    sweep = radius_sweep(ev, dist_cols, [50, 75, 100, 150, 200, 300, 500])
    sweep.to_csv(args.out / "geofence_radius_sweep.csv", index=False)

    summary = {
        "hubs": len(hubs),
        "experiment_days": len(exp),
        "orders_in_experiment": int(exp_m.loc[exp_m.policy == BASELINE.name, "orders"].sum()),
        "arms": {a: sorted(h for h, x in arm.items() if x == a) for a in ("treatment", "control")},
        "runtime_s": round(time.time() - started, 1),
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))

    md = [
        "# Run report",
        "",
        f"{summary['hubs']} hubs, {summary['experiment_days']} experiment days, "
        f"{summary['orders_in_experiment']:,} orders. Runtime {summary['runtime_s']} s.",
        "",
        "## Ablation (every policy on every hub-day)",
        "",
        report.fmt_table(ablation.reset_index(names="policy")),
        "",
        "## Stressed vs ordinary days",
        "",
        report.fmt_table(stress),
        "",
        "## A/B readout (hub-level randomisation)",
        "",
        report.fmt_table(ab, ".4f"),
        "",
        "## Power (from the pre-period)",
        "",
        report.fmt_table(power, ".4f"),
        "",
        "## Re-randomisation check of the CIs",
        "",
        report.fmt_table(rr, ".3f"),
        "",
        "## Geofence",
        "",
        report.fmt_table(geo, ".3f"),
        "",
        report.fmt_table(sweep, ".3f"),
        "",
    ]
    (args.out / "run_report.md").write_text("\n".join(md))
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    print("\nAblation\n", ablation.round(3).to_string())
    print("\nA/B readout\n", ab.round(4).to_string())
    print("\nPower\n", power.round(4).to_string())
    print("\nRe-randomisation\n", rr.round(3).to_string())
    print("\nGeofence\n", geo.round(3).to_string())
    print("\nRadius sweep\n", sweep.round(3).to_string())
    print(f"\nwrote {args.out}/ in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
