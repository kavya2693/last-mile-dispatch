"""Hub-level A/B experiment: randomisation, readout, power, and a check on the CIs themselves.

The unit of randomisation is the hub, because riders and orders inside a hub share one
dispatcher: a rider-level or order-level split would let treated and control orders compete
for the same riders and contaminate both arms. The price is a small sample (26 hubs), so the
analysis is done on one number per hub and the CI methods are checked by re-randomisation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy import stats


def paired_stratified_assignment(
    hub_ids: Sequence[int], pre_metric: Sequence[float], rng: np.random.Generator
) -> dict[int, str]:
    """Sort hubs by a pre-period metric, pair neighbours, and flip a coin inside each pair.
    Big hubs then cannot all land in one arm by chance. An odd hub out is randomised alone."""
    order = np.argsort(np.asarray(pre_metric, dtype=float))
    ids = np.asarray(hub_ids)[order]
    arm: dict[int, str] = {}
    for i in range(0, len(ids) - 1, 2):
        a, b = int(ids[i]), int(ids[i + 1])
        if rng.random() < 0.5:
            a, b = b, a
        arm[a], arm[b] = "treatment", "control"
    if len(ids) % 2:
        arm[int(ids[-1])] = "treatment" if rng.random() < 0.5 else "control"
    return arm


@dataclass(frozen=True)
class Interval:
    estimate: float
    lo: float
    hi: float
    p_value: float = float("nan")


def welch(treat: NDArray[np.float64], control: NDArray[np.float64], alpha: float = 0.05) -> Interval:
    t, c = np.asarray(treat, float), np.asarray(control, float)
    vt, vc = t.var(ddof=1) / len(t), c.var(ddof=1) / len(c)
    se = np.sqrt(vt + vc)
    diff = float(t.mean() - c.mean())
    if se == 0:
        return Interval(diff, diff, diff, 1.0 if diff == 0 else 0.0)
    dof = (vt + vc) ** 2 / (vt**2 / (len(t) - 1) + vc**2 / (len(c) - 1))
    q = stats.t.ppf(1 - alpha / 2, dof)
    p = 2 * stats.t.sf(abs(diff / se), dof)
    return Interval(diff, float(diff - q * se), float(diff + q * se), float(p))


def bootstrap(
    treat: NDArray[np.float64],
    control: NDArray[np.float64],
    rng: np.random.Generator,
    n_boot: int = 4000,
    alpha: float = 0.05,
) -> Interval:
    """Percentile bootstrap of the difference in hub means, resampling hubs within each arm."""
    t, c = np.asarray(treat, float), np.asarray(control, float)
    bt = t[rng.integers(0, len(t), size=(n_boot, len(t)))].mean(axis=1)
    bc = c[rng.integers(0, len(c), size=(n_boot, len(c)))].mean(axis=1)
    d = bt - bc
    diff = float(t.mean() - c.mean())
    lo, hi = np.quantile(d, [alpha / 2, 1 - alpha / 2])
    p = float(min(1.0, 2 * min((d <= 0).mean(), (d >= 0).mean())))
    return Interval(diff, float(lo), float(hi), p)


def mde(sd: float, n_per_arm: int, alpha: float = 0.05, power: float = 0.8) -> float:
    """Smallest true difference detectable with the given power, two-sided, equal arms.
    Uses t quantiles because with 13 hubs per arm the normal approximation is too generous."""
    dof = 2 * n_per_arm - 2
    q = stats.t.ppf(1 - alpha / 2, dof) + stats.t.ppf(power, dof)
    return float(q * sd * np.sqrt(2.0 / n_per_arm))


def hubs_needed(sd: float, effect: float, alpha: float = 0.05, power: float = 0.8) -> int:
    """Hubs per arm needed to detect ``effect``. Searches n because the t quantile depends on n."""
    for n in range(2, 10_000):
        if mde(sd, n, alpha, power) <= abs(effect):
            return n
    return 10_000


def readout(
    hub_metrics: pd.DataFrame,
    arm: dict[int, str],
    metrics: Sequence[str],
    rng: np.random.Generator,
    lower_is_better: Sequence[str] = (),
) -> pd.DataFrame:
    """One row per metric: arm means, absolute and relative difference, Welch and bootstrap CIs."""
    df = hub_metrics.assign(arm=hub_metrics["hub_id"].map(arm))
    rows = []
    for m in metrics:
        t = df.loc[df["arm"] == "treatment", m].to_numpy(float)
        c = df.loc[df["arm"] == "control", m].to_numpy(float)
        w = welch(t, c)
        b = bootstrap(t, c, rng)
        base = c.mean()
        rows.append(
            {
                "metric": m,
                "control": c.mean(),
                "treatment": t.mean(),
                "diff": w.estimate,
                "rel_diff": w.estimate / base if base else float("nan"),
                "welch_lo": w.lo,
                "welch_hi": w.hi,
                "welch_p": w.p_value,
                "boot_lo": b.lo,
                "boot_hi": b.hi,
                "direction": "lower is better" if m in lower_is_better else "higher is better",
            }
        )
    return pd.DataFrame(rows)


def rerandomisation_check(
    control_outcome: pd.Series,
    treatment_outcome: pd.Series,
    pre_metric: pd.Series,
    rng: np.random.Generator,
    n_draws: int = 500,
    n_boot: int = 1000,
) -> dict[str, float]:
    """Both potential outcomes of every hub are known in simulation, so the true effect is known.
    Re-draw the assignment many times and count how often each CI covers it, how often an
    A/A split (control outcomes on both sides) is called significant, and how often the real
    effect is detected."""
    hubs = control_outcome.index.to_numpy()
    true_effect = float((treatment_outcome - control_outcome).mean())
    cover_w = cover_b = aa_w = aa_b = detect_w = 0
    for _ in range(n_draws):
        arm = paired_stratified_assignment(list(hubs), list(pre_metric.loc[hubs].to_numpy()), rng)
        is_t = np.array([arm[h] == "treatment" for h in hubs])
        t = treatment_outcome.loc[hubs].to_numpy()[is_t]
        c = control_outcome.loc[hubs].to_numpy()[~is_t]
        w = welch(t, c)
        b = bootstrap(t, c, rng, n_boot=n_boot)
        cover_w += w.lo <= true_effect <= w.hi
        cover_b += b.lo <= true_effect <= b.hi
        detect_w += w.p_value < 0.05
        a = control_outcome.loc[hubs].to_numpy()
        wa = welch(a[is_t], a[~is_t])
        ba = bootstrap(a[is_t], a[~is_t], rng, n_boot=n_boot)
        aa_w += wa.p_value < 0.05
        aa_b += not (ba.lo <= 0 <= ba.hi)
    return {
        "true_effect": true_effect,
        "welch_coverage": cover_w / n_draws,
        "bootstrap_coverage": cover_b / n_draws,
        "welch_power": detect_w / n_draws,
        "aa_false_positive_welch": aa_w / n_draws,
        "aa_false_positive_bootstrap": aa_b / n_draws,
        "draws": n_draws,
    }
