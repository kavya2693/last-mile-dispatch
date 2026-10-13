import numpy as np
import pandas as pd

from last_mile_dispatch import assignment, bagging
from last_mile_dispatch.config import BAG_CAPACITY, BASELINE, TREATMENT, Policy
from last_mile_dispatch.geo import offset_latlon
from last_mile_dispatch.simulate import HubDay, simulate_hub_day

HUB = (25.2, 55.3)


def test_bagging_off_gives_singletons():
    xy = np.array([[1.0, 0.0], [1.1, 0.0]])
    assert bagging.make_bags([0, 1], np.zeros(2), xy, enabled=False) == [[0], [1]]


def test_bagging_groups_close_drops_and_respects_capacity():
    xy = np.array([[2.0, 0.0], [2.1, 0.1], [2.0, 0.2], [2.2, 0.0], [-3.0, 0.0]])
    created = np.array([0.0, 1.0, 2.0, 3.0, 0.5])
    bags = bagging.make_bags([0, 1, 2, 3, 4], created, xy, enabled=True)
    assert max(len(b) for b in bags) <= BAG_CAPACITY
    assert [4] in bags  # the drop on the other side of the hub is never bagged with the cluster
    assert sorted(i for b in bags for i in b) == [0, 1, 2, 3, 4]
    assert bags[0][0] == 0  # the oldest order seeds the first bag


def test_bagging_refuses_orders_far_apart_in_time():
    xy = np.array([[2.0, 0.0], [2.05, 0.0]])
    bags = bagging.make_bags([0, 1], np.array([0.0, 40.0]), xy, enabled=True)
    assert bags == [[0], [1]]


def test_route_visits_nearest_first():
    xy = np.array([[3.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
    assert bagging.route_order(xy) == [1, 2, 0]


def plan(km_out: float) -> assignment.BagPlan:
    return assignment.BagPlan([0], np.array([km_out, km_out]))


def test_fifo_gives_oldest_bag_to_longest_idle_rider():
    created = np.array([5.0, 1.0])
    bags = [assignment.BagPlan([0], np.array([1.0, 1.0])), assignment.BagPlan([1], np.array([1.0, 1.0]))]
    pairs = assignment.fifo([0, 1], np.array([30.0, 10.0]), bags, created)
    assert pairs[0] == (1, 1)


def test_matching_puts_the_car_on_the_short_trip():
    # cars cost more per km, so the min-cost matching hands the long trip to the bike
    created = np.array([100.0, 100.0])
    bags = [assignment.BagPlan([0], np.array([6.0, 6.0])), assignment.BagPlan([1], np.array([0.8, 0.8]))]
    pairs = dict(assignment.min_cost([0, 1], ["car", "bike"], bags, created, now=110.0, rain=False))
    assert pairs == {0: 1, 1: 0}


def test_matching_prefers_the_older_order_when_short_of_riders():
    created = np.array([60.0, 95.0])  # order 0 has waited 40 minutes, order 1 five
    bags = [assignment.BagPlan([0], np.array([2.0, 2.0])), assignment.BagPlan([1], np.array([2.0, 2.0]))]
    pairs = assignment.min_cost([0], ["bike"], bags, created, now=100.0, rain=False)
    assert pairs == [(0, 0)]


def tiny_hub_day(n_orders: int = 60, gamer: bool = True, seed: int = 0) -> HubDay:
    rng = np.random.default_rng(seed)
    ang = rng.uniform(0, 2 * np.pi, n_orders)
    r = rng.uniform(0.3, 3.0, n_orders)
    lat, lon = offset_latlon(*HUB, 1000 * r * np.cos(ang), 1000 * r * np.sin(ang))
    orders = pd.DataFrame(
        {
            "order_id": range(n_orders),
            "created_min": np.sort(rng.uniform(600, 900, n_orders)),
            "cust_lat": lat,
            "cust_lon": lon,
            "building": rng.choice(["highrise", "villa", "lowrise"], n_orders),
            "items": 3,
            "pick_min": 4.0,
            "customer_unavailable": rng.random(n_orders) < 0.05,
        }
    )
    riders = pd.DataFrame(
        {
            "rider_id": range(4),
            "hub_id": 0,
            "vehicle": ["bike", "bike", "car", "bike"],
            "shift": ["early", "early", "early", "late"],
            "remote_marker": [gamer, False, False, False],
        }
    )
    return HubDay(0, "2026-02-01", *HUB, rain=False, orders=orders, riders=riders)


def test_every_order_ends_in_exactly_one_terminal_state():
    for policy in (BASELINE, TREATMENT):
        m = simulate_hub_day(tiny_hub_day(), policy, seed=1).metrics
        assert m["delivered"] + m["cancelled"] + m["failed_genuine"] + m["fake_accepted"] == m["orders"]
        assert 0 < m["utilization"] < 1.5


def test_geofence_only_changes_outcomes_when_enforced():
    hd = tiny_hub_day(n_orders=80)
    off = simulate_hub_day(hd, Policy("x", True, True, False), seed=3)
    on = simulate_hub_day(hd, Policy("y", True, True, True), seed=3)
    assert off.metrics["fake_accepted"] > 0
    assert on.metrics["fake_accepted"] < off.metrics["fake_accepted"]
    # the same remote marks are logged in both runs because the per-order draws are shared
    assert sum(e["is_fake"] for e in off.events) >= off.metrics["fake_accepted"]


def test_honest_fleet_produces_no_fake_marks():
    res = simulate_hub_day(tiny_hub_day(gamer=False), BASELINE, seed=2)
    assert res.metrics["fake_accepted"] == 0
    assert not any(e["is_fake"] for e in res.events)


def test_same_seed_same_result():
    hd = tiny_hub_day()
    assert simulate_hub_day(hd, TREATMENT, 5).metrics == simulate_hub_day(hd, TREATMENT, 5).metrics
