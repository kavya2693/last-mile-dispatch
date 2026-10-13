"""Operating constants shared by the generator, the dispatcher and the experiment.

Money is in AED. Time inside the simulator is minutes from local midnight.
"""

from __future__ import annotations

from dataclasses import dataclass

# City and network
N_HUBS = 26
SERVICE_RADIUS_KM = 4.0
ROAD_CIRCUITY = 1.35  # road km per straight-line km, typical for a grid with interchanges

# Calendar: two pre-period weeks used for stratification and power, then four experiment weeks.
START_DATE = "2026-01-19"
PRE_DAYS = 14
EXPERIMENT_DAYS = 28

# Hub hours
OPEN_MIN = 8 * 60
CLOSE_MIN = 24 * 60
WAVE_MIN = 2  # dispatcher wakes every two minutes
SHIFT_HOURS = 8

# Service promise
SLA_MIN = 30  # promised delivery window from order creation
CANCEL_AFTER_MIN = 45  # customer cancels if nothing has left the hub by then
SERVICE_MIN_PER_STOP = 2.0
GENUINE_ATTEMPT_WAIT_MIN = 4.0  # rider waits at the door before marking a real failed attempt
FORCED_COMPLETION_PENALTY_MIN = 3.0  # extra time when a flagged rider is sent back to the door

# Fleet economics
HOURLY_PAY = {"bike": 22.0, "car": 26.0}
COST_PER_KM = {"bike": 0.18, "car": 0.45}
SPEED_KMH = {"bike": 24.0, "car": 22.0}
BAG_CAPACITY = 3
FAILED_ORDER_COST = 12.0  # refund handling and a lost basket margin on a fake or cancelled order

# Fake attempts
GAMER_SHARE = 0.08  # riders who sometimes mark "customer unavailable" without reaching the door
GAMER_FAKE_RATE = 0.22  # per stop, for those riders
PING_INTERVAL_S = 30
PINGS_PER_EVENT = 6
PING_DROPOUT = 0.05


@dataclass(frozen=True)
class Policy:
    """One dispatch configuration. The A/B experiment compares two of these."""

    name: str
    bagging: bool
    matching: bool  # min-cost matching instead of FIFO
    geofence: bool


BASELINE = Policy("baseline", bagging=False, matching=False, geofence=False)
BAG_ONLY = Policy("bagging", bagging=True, matching=False, geofence=False)
MATCH_ONLY = Policy("matching", bagging=False, matching=True, geofence=False)
BAG_MATCH = Policy("bagging+matching", bagging=True, matching=True, geofence=False)
TREATMENT = Policy("bagging+matching+geofence", bagging=True, matching=True, geofence=True)
ALL_POLICIES = (BASELINE, BAG_ONLY, MATCH_ONLY, BAG_MATCH, TREATMENT)

# Bagging limits
BAG_MAX_DROP_GAP_KM = 1.0  # straight-line distance between two drops in one bag
BAG_MAX_CREATED_GAP_MIN = 12.0
BAG_MAX_EXTRA_MIN = 9.0  # extra minutes the first customer may wait because of the bag

# Matching weights (AED). Lateness is priced so the matcher protects the promise,
# and each dispatched order earns a credit so larger bags are not starved by their km.
LATE_COST_PER_MIN = 1.0
WAIT_COST_PER_MIN = 0.4
ORDER_DISPATCH_CREDIT = 9.0

# Geofence rule
GEOFENCE_RADIUS_M = 150.0
GEOFENCE_MIN_PINGS_INSIDE = 2
