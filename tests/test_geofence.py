import numpy as np
import pandas as pd

from last_mile_dispatch.geo import offset_latlon
from last_mile_dispatch.geofence import confusion, evaluate, flag_attempts, ping_distances_m

CUST = (25.2, 55.3)


def trail(offsets_m):
    pts = [offset_latlon(*CUST, dx, dy) for dx, dy in offsets_m]
    return np.array([[p[0] for p in pts]]), np.array([[p[1] for p in pts]])


def test_rider_at_the_door_is_not_flagged():
    lat, lon = trail([(5, -10), (12, 3), (-8, 8), (0, 0), (20, 15), (-15, -5)])
    d = ping_distances_m(lat, lon, np.array([CUST[0]]), np.array([CUST[1]]))
    assert d.max() < 30
    assert not flag_attempts(d)[0]


def test_rider_on_the_highway_is_flagged():
    lat, lon = trail([(1500, 900), (1350, 820), (1200, 700), (1050, 600), (900, 500), (800, 450)])
    d = ping_distances_m(lat, lon, np.array([CUST[0]]), np.array([CUST[1]]))
    assert flag_attempts(d)[0]


def test_dropouts_count_as_outside_and_an_empty_trail_is_flagged():
    near = np.array([[10.0, np.nan, np.nan, np.nan, np.nan, np.nan]])
    assert flag_attempts(near)[0]  # one ping inside is not enough
    assert flag_attempts(np.full((1, 6), np.nan))[0]
    two = np.array([[10.0, 12.0, np.nan, np.nan, np.nan, np.nan]])
    assert not flag_attempts(two)[0]


def test_confusion_counts():
    c = confusion(np.array([1, 1, 0, 0], bool), np.array([1, 0, 1, 0], bool))
    assert (c["precision"], c["recall"], c["false_flag_rate"]) == (0.5, 0.5, 0.5)


def test_evaluate_splits_hard_cases():
    events = pd.DataFrame(
        {
            "d0": [20.0, 400.0, 1500.0, 120.0],
            "d1": [25.0, 380.0, 1400.0, 110.0],
            "is_fake": [False, False, True, True],
            "building": ["villa", "highrise", "lowrise", None],
            "true_mark_dist_m": [15.0, 10.0, 1450.0, 115.0],
        }
    )
    out = evaluate(events, ["d0", "d1"]).set_index("slice")
    # the genuine tower rider with multipath is a false flag; the close fake is missed
    assert out.loc["building=highrise", "false_flag_rate"] == 1.0
    assert out.loc["fake marked <300 m", "recall"] == 0.0
    assert out.loc["fake marked >1 km", "recall"] == 1.0
