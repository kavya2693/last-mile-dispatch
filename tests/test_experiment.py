import numpy as np
import pandas as pd
import pytest

from last_mile_dispatch.experiment import (
    bootstrap,
    hubs_needed,
    mde,
    paired_stratified_assignment,
    readout,
    rerandomisation_check,
    welch,
)


def test_assignment_balances_each_pair():
    rng = np.random.default_rng(0)
    hubs = list(range(26))
    pre = list(np.linspace(100, 900, 26))
    arm = paired_stratified_assignment(hubs, pre, rng)
    assert sorted(arm) == hubs
    assert sum(v == "treatment" for v in arm.values()) == 13
    # neighbours in the pre-period ordering always land in opposite arms
    for i in range(0, 26, 2):
        assert arm[i] != arm[i + 1]


def test_welch_matches_scipy():
    rng = np.random.default_rng(1)
    t, c = rng.normal(1, 1, 13), rng.normal(0, 2, 13)
    from scipy import stats

    ours = welch(t, c)
    ref = stats.ttest_ind(t, c, equal_var=False)
    assert ours.p_value == pytest.approx(ref.pvalue, rel=1e-9)
    assert ours.lo < ours.estimate < ours.hi


def test_bootstrap_centres_on_difference():
    rng = np.random.default_rng(2)
    t, c = rng.normal(5, 1, 40), rng.normal(3, 1, 40)
    b = bootstrap(t, c, rng)
    assert b.lo < 2 < b.hi or abs(b.estimate - 2) < 0.6
    assert b.lo < b.estimate < b.hi


def test_power_round_trip():
    effect = mde(sd=1.0, n_per_arm=13)
    assert hubs_needed(sd=1.0, effect=effect) == 13
    assert hubs_needed(sd=1.0, effect=effect / 2) > 40


def test_mde_falls_with_more_hubs():
    assert mde(1.0, 50) < mde(1.0, 13) < mde(1.0, 5)


def test_readout_signs_and_relative_change():
    rng = np.random.default_rng(3)
    df = pd.DataFrame({"hub_id": range(10), "cost": [10.0] * 5 + [8.0] * 5})
    arm = {h: ("control" if h < 5 else "treatment") for h in range(10)}
    out = readout(df, arm, ["cost"], rng, lower_is_better=["cost"]).iloc[0]
    assert out["diff"] == pytest.approx(-2.0)
    assert out["rel_diff"] == pytest.approx(-0.2)


def test_rerandomisation_recovers_a_known_effect():
    # The verifier for the whole readout: with a planted effect of +1 and hub noise sd 1,
    # 95% CIs should cover the truth about 95% of the time and A/A should rarely fire.
    rng = np.random.default_rng(4)
    hubs = pd.Index(range(26))
    base = pd.Series(rng.normal(10, 1, 26), index=hubs)
    treated = base + 1.0 + pd.Series(rng.normal(0, 0.3, 26), index=hubs)
    pre = base + pd.Series(rng.normal(0, 0.2, 26), index=hubs)
    res = rerandomisation_check(base, treated, pre, rng, n_draws=300, n_boot=400)
    assert res["true_effect"] == pytest.approx(1.0, abs=0.2)
    assert res["welch_coverage"] > 0.88
    assert res["aa_false_positive_welch"] < 0.1
