# ADR-0001: Randomise hubs, not orders, and run every policy on every hub-day as a check

## Status
Accepted

## Context
The dispatch change has three parts (order bagging, min-cost rider matching, a geofence on
"customer unavailable" marks) and the business wants one decision: roll it out to all hubs
or not. The decision rests on an A/B test. Three things make that test easy to get wrong:

1. Orders inside a hub share one rider pool. If half the orders in a hub were dispatched by
   the new logic and half by FIFO, the two halves would compete for the same riders, and
   whichever arm grabbed riders first would look better for a reason that disappears at
   rollout.
2. The city has 26 hubs. With hub-level randomisation the experiment has 13 units per arm,
   and textbook large-sample intervals are not trustworthy at that size.
3. Each component can move a metric in opposite directions. Bagging lowers kilometres per
   order but delays the first customer in the bag; the geofence stops fake attempts but
   sends some honest riders back to the door.

## Decision
- **Unit of randomisation is the hub.** Hubs are paired on pre-period order volume and one
  of each pair is treated, so the arms cannot differ in size by chance.
- **Analysis is one number per hub over the experiment window**, compared with Welch's t
  interval and a hub-resampling bootstrap. Daily hub numbers are not treated as independent
  observations: they share riders, customers and the hub's own quirks.
- **The simulator runs every policy on every hub-day with the same per-order random draws.**
  This gives both potential outcomes for every hub, so the true effect of the rollout is
  known. That is used twice: an ablation table that isolates each component, and a
  re-randomisation check that redraws the hub assignment hundreds of times and measures how
  often each interval covers the true effect and how often an A/A split is declared
  significant.
- **Power is computed from the pre-period before reading the result**, from the between-hub
  spread of each metric, using t quantiles for 13 hubs per arm.
- **The geofence is a two-parameter rule** (radius, minimum pings inside) that an operations
  lead can explain to a rider, evaluated against ground truth on the baseline arm where no
  mark was enforced.

## Alternatives rejected
- **Order-level or rider-level randomisation.** More units and tighter intervals, but the
  arms interfere through the shared rider pool, so the estimate is biased in an unknown
  direction.
- **Switchback (time-sliced) randomisation within a hub.** Handles interference better than
  an order split, but riders dispatched in one slice are still out on the road in the next,
  and the city has strong time-of-day and Ramadan patterns that a short switchback would
  have to model. Worth doing with real traffic; not the first design.
- **Vehicle-routing solver (OR-Tools) for bagging.** Better routes for large bags, but bags
  are capped at three stops and recomputed every two minutes; a greedy bagger is exact
  enough at that size and is explainable to hub staff.
- **A learned fake-attempt classifier.** Labels for fake attempts are scarce and disputed in
  practice; a rule with a radius the business can tune is easier to defend to riders.

## Consequences
- The A/B readout is honest about what 26 hubs can detect: some metrics are underpowered
  and the readout says so instead of reporting a point estimate as a win.
- The ablation numbers come from the simulator, not from the experiment, and are labelled
  that way.
