# last-mile-dispatch

[![ci](https://github.com/kavya2693/last-mile-dispatch/actions/workflows/ci.yml/badge.svg)](https://github.com/kavya2693/last-mile-dispatch/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.11-blue)
![license](https://img.shields.io/badge/license-MIT-green)

Quick-commerce dispatch for 26 dark-store hubs in a Gulf city: order bagging, rider matching,
a geofence on "customer unavailable" marks made away from the door, and a hub-level A/B test that says what it
can and cannot detect.

## The problem

A quick-commerce operator promises groceries in 30 minutes from 26 small hubs spread along a
coastal city. Each hub has 7 to 33 riders on two shifts. On an ordinary weekday the riders
keep up. On weekends, in the hour before iftar during Ramadan, and on the one day a year it
rains, orders pile up faster than riders come back, customers cancel after 45 minutes of
nothing leaving the hub, and every cancelled basket still cost a rider-hour that was paid for.

Most hubs dispatch by hand: the rider who has waited longest takes the oldest order, one order
per trip. Two orders going to the same tower block leave ten minutes apart with two riders.
On top of that, a small share of riders mark "customer unavailable" from the road instead of
walking to the door, which costs a refund and a customer.

## Why it is hard

The algorithms are not the hard part. The hard part is proving the change works before it is
rolled out to every hub. Riders inside a hub are shared, so orders cannot be split between
old and new logic without the arms competing for the same riders; the experiment has to
randomise whole hubs, and 26 hubs gives 13 per arm. The components also pull in opposite
directions: bagging lowers kilometres per order but makes the first customer in a bag wait,
and a geofence that catches fake marks also flags honest riders whose GPS bounces off a tower.

## The approach

Every two minutes the dispatcher takes picked orders and free riders, **bags** orders whose
drops are within 1 km and created within 12 minutes of each other (capped at three stops, and
only if the first customer waits at most 9 extra minutes), then **assigns** bags to riders
either by FIFO or by a min-cost matching solved with the Hungarian method
(`scipy.optimize.linear_sum_assignment`): each rider-bag pair is priced by that vehicle's
cost per km, minutes late against the promise, minutes the customers have already waited,
and a credit per order. A **geofence** flags a "customer unavailable" mark when fewer than
2 of the rider's last 6 GPS pings are within 150 m of the customer.

The key decision is in [ADR-0001](docs/adr/0001-randomise-hubs-and-measure-every-policy-on-every-hub-day.md):
randomise hubs (paired on pre-period volume) and analyse one number per hub, and, because this
is a simulator, run **every policy on every hub-day with the same per-order random draws**.
That gives the true effect for every hub, so the experiment's confidence intervals can be
checked against it rather than trusted.

## The result

Four experiment weeks, 26 hubs, 326,981 orders. Every number below is in
[`outputs/`](outputs/) and is produced by `make run`.

**A/B readout** (13 treated hubs vs 13 control hubs; treatment = bagging + matching + geofence;
95% Welch and hub-bootstrap CIs; "true" is the effect averaged over all 26 hubs, known only
because the simulator ran both arms everywhere):

| Metric | Control | Treatment | Difference | Welch 95% CI | Bootstrap 95% CI | True |
|---|---|---|---|---|---|---|
| Fleet cost per delivered order (AED) | 9.79 | 8.75 | **−1.04 (−10.6%)** | −1.47 to −0.62 | −1.41 to −0.65 | −1.04 |
| Delivered orders per rider-hour | 2.59 | 2.89 | +0.30 (+11.6%) | +0.18 to +0.42 | +0.19 to +0.41 | +0.28 |
| Rider utilisation (busy / paid time) | 0.667 | 0.650 | **−0.017 (−2.5%)** | −0.040 to +0.007 | −0.039 to +0.004 | −0.026 |
| Fake attempts accepted per 1,000 orders | 11.7 | 3.2 | −8.5 (−72%) | −15.0 to −2.0 | −14.4 to −2.9 | −12.2 |
| Orders delivered within 30 min (share of all orders) | 58.0% | 86.2% | +28.3 pts | +23.5 to +33.0 | +24.1 to +32.6 | +30.1 |
| Cancellation rate | 11.6% | 3.7% | −7.9 pts | −9.7 to −6.1 | −9.6 to −6.4 | −7.9 |
| P90 order-to-door minutes | 41.2 | 27.2 | −14.0 | −16.4 to −11.6 | −16.2 to −11.9 | −15.1 |

The metric that disagrees is **utilisation**. With the same paid roster, bagging means fewer
trips for the same orders, so riders spend a smaller share of their shift on the road. Every
other metric improves and utilisation goes down; the A/B cannot even tell that it moved
(p = 0.16), and the pre-period power calculation says 27 hubs per arm would be needed to see
an effect that size. Raising utilisation needs a smaller roster, which is a staffing decision
this experiment did not test.

**Where the cost saving comes from** (all hubs, all experiment days, baseline vs treatment):

| Day type | Orders | Cost per delivered order | Cancellation rate | Km per delivered order |
|---|---|---|---|---|
| Ordinary weekday | 125,715 | 9.71 → 9.36 (−3.7%) | 1.5% → 0.8% | 4.51 → 4.10 |
| Weekend or Ramadan | 184,449 | 9.65 → 8.30 (−14.0%) | 15.4% → 4.2% | 4.52 → 3.69 |
| Rain day | 16,817 | 10.42 → 6.84 (−34.4%) | 42.5% → 14.0% | 4.45 → 2.74 |

Most of the 10.6% comes from stressed days, when bagging turns a queue of cancellations into
delivered orders on a roster that is paid either way. On an ordinary weekday, when riders keep
up, the saving is under 4% and comes from kilometres. A pitch built on the blended number
would overpromise for a hub that rarely runs short.

**Ablation** (every policy on every hub-day):

| Policy | Cost / delivered | Orders per rider-hour | Utilisation | Cancel rate | On time (all orders) | Fake accepted /1k |
|---|---|---|---|---|---|---|
| FIFO, one order per trip (baseline) | 9.71 | 2.62 | 0.677 | 11.5% | 56.5% | 15.1 |
| + bagging | 8.95 | 2.83 | 0.650 | 4.5% | 78.1% | 16.0 |
| + matching | 9.31 | 2.71 | 0.665 | 8.6% | 68.9% | 16.0 |
| bagging + matching | 8.77 | 2.87 | 0.645 | 3.3% | 86.8% | 16.5 |
| bagging + matching + geofence | 8.65 | 2.91 | 0.649 | 3.4% | 87.8% | 2.7 |

Bagging carries most of the gain. Matching on its own adds about half as much, because
every rider starts from the hub and the riders differ only by vehicle; it helps most when
combined with bagging, where it decides which bags leave first when bags outnumber riders.

**Geofence** (judged on the baseline arm, where marks were not enforced; 11,566 marks,
4,938 of them fake by construction):

| Slice | Precision | Recall | Honest riders flagged |
|---|---|---|---|
| All marks, 150 m radius | 95.6% | 83.0% | 2.8% |
| Tower buildings | 89.5% | 82.0% | **5.3%** |
| Villas | 99.5% | 83.4% | 0.4% |
| Fake marked from more than 300 m | 100% | 100% | — |
| Fake marked from the kerb (under 300 m) | 100% | **68.1%** | — |

The rule catches every rider who marks from the road and misses a third of those who stop
outside the building and do not go up. Shrinking the radius to 50 m lifts recall to 97.9% but
flags 3.7% of honest riders, concentrated in towers where GPS multipath moves a whole trail
by 100 to 350 m ([`outputs/geofence_radius_sweep.csv`](outputs/geofence_radius_sweep.csv)).

**Are the intervals trustworthy at 13 hubs per arm?** The assignment was redrawn 500 times
([`outputs/rerandomisation.csv`](outputs/rerandomisation.csv)). Welch intervals covered the
true effect 97 to 99% of the time and an A/A split was called significant 2 to 7% of the time.
They are conservative, not optimistic, because pairing reduces variance that Welch does not
know about. The hub bootstrap was looser on one metric: its A/A false-positive rate on the
on-time share was 9%, nearly double the nominal 5%, which is the known small-sample weakness of
the percentile bootstrap. The readout reports both and leans on Welch.

## How it works

```
orders.csv.gz ─┐
riders.csv ────┼─► every 2 min per hub:  picked orders + free riders
hubs.csv ──────┘          │
                          ├─ bagging.make_bags        oldest order seeds a bag, close drops join
                          ├─ assignment.fifo | min_cost   Hungarian on km, lateness, wait, credit
                          └─ simulate: play each trip  traffic by hour, rain, handover, failed
                                │                       attempts, remote marks + GPS trail
                                ├─ geofence.flag_attempts   enforce (treatment) or just log
                                ▼
                     hub-day metrics × 5 policies
                                │
        ┌───────────────────────┼─────────────────────────────┐
   ablation (all hubs)   A/B: pair hubs on pre-period,   re-randomise 500× against
                         treat one per pair, Welch +      the known true effect:
                         bootstrap CIs, power from        coverage, power, A/A rate
                         pre-period spread
```

Stop conditions per hub-day: orders cancel 45 minutes after creation if nothing has left the
hub; the hub stops dispatching 45 minutes after it closes at midnight and anything left is
cancelled. A rider is free again when back at the hub; work past the shift end is paid as
overtime.

## Running it

```bash
uv sync
make data      # 26 hubs, 473 riders, 42 days, 477,868 orders into data/ (seed 7)
make run       # all policies, A/B readout, power, CI check, geofence -> outputs/ (about 3 min)
make check     # ruff, ruff format, mypy, pytest
uv run dispatch --quick   # 8 hubs, 7 experiment days, as CI runs it
docker build -t last-mile-dispatch . && docker run --rm last-mile-dispatch
```

`outputs/run_report.md` has every table; `outputs/run_log.txt` is the console output of the
run the README quotes.

## The data

The dataset is generated by the seeded script `scripts/generate_data.py` and sized to the
production problem (26 hubs, about 440 orders per hub-day, six weeks); production dispatch
data is proprietary.

It carries the patterns that change dispatch: lunch and evening peaks, a weekend lift,
Ramadan from 18 February moving demand to the hour before iftar and late night, one rain day
with 35% more orders and 40% slower traffic, two hub outages, a slow growth trend, bulk
baskets, 1.2% of addresses with no building type, 5% GPS ping dropout, and tower districts
where GPS is noisier and occasionally displaced as a block. Rosters are sized for an ordinary
weekday evening, so stressed days run short, as they do in practice. Travel is straight-line
distance times 1.35 at an hour-dependent speed, not a road graph. Fake marks are known by
construction, which is the only reason the geofence can be scored at all.

## Tests

`make check` runs 23 tests. The two that matter most:

- `test_rerandomisation_recovers_a_known_effect` plants an effect of +1 into 26 hubs and
  checks that the Welch intervals cover it about 95% of the time and an A/A split rarely
  fires. The experiment code was written and tested against this before the dispatcher existed.
- `test_geofence_only_changes_outcomes_when_enforced` runs the same hub-day with the geofence
  off and on using the same per-order draws, and checks the same remote marks occur in both
  while fewer are accepted when enforced. This is what makes the ablation a fair comparison.

## Known limitations

- **The biggest gap: the roster is fixed.** Every policy is paid for the same riders, so the
  cost saving is mostly cancelled orders turned into deliveries, and utilisation falls. A
  real rollout would cut or reshape shifts; the experiment says nothing about how riders and
  cancellations respond to a smaller roster.
- Riders do not react to the treatment. Riders who mark fake attempts keep the same habit
  when a geofence is enforced; in practice some stop and some learn to mark from the kerb,
  which is the slice the geofence already misses a third of.
- Travel times come from distance and hour, not a road network, and riders always return to
  the hub between trips. Matching would matter more with riders chained from drop to drop.
- The matching is myopic: it decides each two-minute wave on its own and never holds a bag
  for a rider about to return.
- The unit of analysis is the hub over four weeks. Hub-days are not used as independent
  observations, which is correct but leaves 13 units per arm; rarer metrics (fake attempts)
  have wide intervals and the pre-period says 21 hubs per arm would be needed for the
  observed fake-attempt effect at 80% power.
- Ramadan starts in the middle of the experiment. Randomising hubs handles that for the
  comparison, but the absolute numbers mix two demand regimes.

## Insights and learning

I picked this because dispatch changes are usually judged by a before-and-after chart, and
before-and-after in a city with Ramadan, weekends and the odd rain day mostly measures the
calendar. Randomising hubs fixes that, but 26 hubs is a small sample, so I wanted a way to
check the confidence intervals rather than assume them. Simulating every policy on every
hub-day gave the true effect to check against, and re-randomising the assignment 500 times
answered the question I could not answer from a textbook: at 13 hubs per arm, Welch held up
and the percentile bootstrap drifted.

What surprised me was how uneven the gain is. The blended 10.6% cost reduction is under 4% on
an ordinary weekday and over 30% on the rain day. The same change is a modest efficiency gain
for a well-staffed hub and a rescue for an under-staffed one, and those are different
business cases.

What I got wrong first: the matching weights priced lateness above waiting time. That made an
order that was already late look more expensive to send every time, so the matcher kept
choosing fresher orders and left the late one until the customer cancelled. On-time share
among delivered orders looked excellent while cancellations rose. Only the second metric,
on-time share of all orders, showed it. The waiting credit is now higher than the lateness
price and the config says why.

Next I would let the roster vary by policy (smallest roster that holds the on-time share),
chain riders from drop to drop instead of returning to the hub, and replace the fixed fake
habit with riders who respond to being flagged.

## License

MIT
