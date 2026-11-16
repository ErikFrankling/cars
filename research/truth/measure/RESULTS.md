# Driver measurements on recordings: results, F130-F147

6-7 November 2026. No simulator was run. Forecasts were committed before any number was computed (f05ec9a). The held-out recordings are listed in [HOLDOUT.md](HOLDOUT.md) and were never read. Scripts are in `scripts/measure/`; numbers are in the JSON files next to this one; big intermediates are in `cars-data/measure/`. The summary table is [DRIVER.md](DRIVER.md).

Intervals are 95% bootstrap intervals over vehicles (or drivers, or queues), never over samples. "n" counts vehicles or events, not drivers: no dataset here follows a driver across trips.

## Verdicts

| | Forecast | Result | Verdict |
|---|---|---|---|
| F130 tracker noise | 0.005-0.05 m about a 1 s quadratic | highD 1.0 cm along, 0.3 cm across; inD 0.3 cm; rounD 0.2 cm; exiD 0.05 cm | **partial miss**: rounD and exiD below the band. Their providers smooth harder than assumed, so this measures the smoother, not accuracy |
| F131 highD steady time gap | median 1.6, p5 0.8, p95 3.3 s | median **0.98 s** (0.97-0.99), p5 0.47, p95 2.22; 12,245 cars | **miss**: the forecast took report 05's broad definition (any car within 150 m) for steady following |
| F132 datasets agree | within 0.3 s (German), 0.4 s (US) | highD 0.95-0.97 against DLR HT 1.08-1.12 at 25-35 m/s; TGSIM within 0.05-0.29 s of highD at 10-20 m/s | **pass** |
| F133 standstill gap | median 2.5 m (1.5-4.0) | rounD **1.73 m** (1.63-1.85, 225 cars); inD 1.52 m (1.29-1.64, 70); highD 2.95 m (26 stops only) | **pass** at the low edge |
| F134 indifference band in gap | symmetric band, gain outside over 3x inside | **one-sided**: no response from 0.5 s too close to 1.75 s too far; braking only beyond 0.75 s too close. The symmetric hinge gives the reverse ratio (0.06-0.3) | **miss** as written; a one-sided band is real |
| F135 closing-speed dead zone | gain 0.2-0.6 /s outside a 0.2-0.6 m/s dead zone | **no dead zone** on any dataset; gain 0.11-0.2 /s on German motorways, 0.3-0.4 /s in US congestion, flattening above +1.5 m/s | **miss** |
| F136 time-gap persistence | r 0.3-0.6 at 1 km, floor 0.1-0.3, e-folding 0.5-2 km | all pairs: r 0.72 at 0.5-1 km, 0.39 at 3-5 km, e-folding 1.2 km. **Different leaders: r 0.29-0.43, flat to 5 km** | **pass** on the numbers; the decay is the shared leader, the driver's own part does not decay |
| F137 free-speed persistence | r 0.6-0.85 at 3 km, e-folding over 5 km | r 0.75 at 0.5-1 km, **0.48-0.55 at 3 km**, 0.26 at 5-6.5 km; e-folding 4.9 km | **partial**: below the band, inside its tolerance |
| F138 response lag, free fit | 0.5-1.0 s everywhere, spread under 0.3 s | first-order fit to the closing-speed kernel: dead time 0-0.3 s plus time constant 0.48-0.56 s on four datasets. Other estimators: 0.8-2.4 s | **partial**: the comparable estimator agrees with report 05's 0.66 s; no estimator isolates a pure delay |
| F139 inD give-way | minor left 5.5-7.0, straight 5.5-7.0, right 5.0-6.5, major left 4.0-5.5 s; follow-up 2.6-3.5 s | minor left **6.9 s** (6.4-7.5); minor straight 6.6 s (weak); right not measurable; major left **3.9 s** (3.3-4.6). Follow-up straight 2.7, right 3.2, **left 4.9 s** | **partial**: left and straight pass; major left just under; left follow-up over |
| F140 rounD | critical gap 3.0-4.2 s, follow-up 2.4-3.2 s | critical gap **3.0 s** (2.7-3.4) where the arrival is seen, but 2.1-5.0 s by subset and 1.5-3.4 s by day; follow-up **2.76 s** (2.68-2.84, 1,172) | follow-up **pass**; critical gap **pass at the edge, weak** |
| F141 impatience | 0.5-1.5 s shorter after 10 s waiting | within drivers: 2-4% ever take a gap shorter than one they refused; minor-left logit wait effect 0 (CI −0.05 to +0.03 per s) | **miss**: no impatience found |
| F142 merge gaps | lag p5/p50 0.5/1.5, lead 0.4/1.5 s ±50% | lag **0.45/1.81 s**, lead **0.39/1.66 s** (4,088 merges) | **pass** |
| F143 lane change duration | merges 3.5-5.5, mainline 4.5-6.0 s | merges 5.36 s; exiD mainline 5.04 s; highD 4.36 s (lower bounds, 5 s windows) | **pass** except highD, cut short by its 13 s tracks |
| F144 merge position | median 0.30-0.55 of the lane; under 10% in the last tenth | median **0.49** (0.48-0.50); **4.7%** in the last tenth; 109 m left | **pass** |
| F145 follower yields | 10-25% | **10.3%** (9.3-11.6) against a baseline of 6.3%: 4 points more | **pass** on the share; the excess is small |
| F146 SinD launch | start 1.0-2.5 s, saturation 1.8-2.5 s, peak 1.5-2.3 m/s² | start **2.0 s** (1.7-2.2); saturation **2.6 s** (2.45-3.2); peak **1.77 m/s²** (1.66-1.88) | start and peak **pass**; saturation **miss** (slower) |
| F147 desired speed | no limit 34-38, 120 km/h 30-34, 100 km/h 26-30, inD 11-14 m/s | highD no limit **34.5**, highD and exiD 120 km/h **32.2** and **30.7**, exiD 100 km/h **28.3** m/s; spread CV 0.14-0.20; inD not measurable | **pass** on motorways; inD **miss** (not measurable) |

## 1. Loaders and tracker noise (F130)

**Loaders.** `levelx.py` reads highD, inD, rounD and exiD straight from the provider's zips, one recording at a time, and caches columns per recording. `levelx_scene.py` writes the replay scene format of `research/truth/replay/README.md`: net, routes, `.rpl`, matched samples, `scene.json`. It refuses held-out recordings unless asked.

- highD: one edge per carriageway, lanes straight at the recording's lane markings, lane changes kept inside one track.
- inD, rounD, exiD: every vehicle lanelet of the site's Lanelet2 map becomes a one-lane edge, joined where one lanelet ends and the next begins. A track is cut where it moves to a lanelet that is not a successor (a lane change or a map gap). The pieces are separate replayed trips.

| Scene | Vehicles | Pieces per vehicle | Route links missing from the net | Distance of the recorded centre from its lane's centreline, p50 / p90 / p99 |
|---|---:|---:|---:|---|
| highD 01 | 1,047 | 1.0 | 0 | 0.26 / 0.64 / 1.56 m |
| exiD 00 | 1,409 | 1.39 | 0 | 0.32 / 0.89 / 1.73 m |
| inD 00 | 324 | 3.3 | 0 | 0.88 / 1.24 / 3.24 m (0.34 m p50 for moving cars; 40% of samples are parked cars) |
| rounD 01 | 263 | 5.3 | 0 | 0.48 / 1.70 / 3.04 m |

Not checked in the simulator, since this job runs none. The drone scenes need parallel lanelets merged into multi-lane edges before a simulated car can change lanes in them.

**Noise.** The recorded centre was compared with a 1 s local quadratic on 9,452 highD, 762 inD, 1,403 rounD and 5,384 exiD car tracks ([noise.json](noise.json)).

| | Along, SD | Across, SD | Speed about the same fit | Provider speed minus the derivative of its own positions, SD | Car length p5 / p50 / p95 |
|---|---:|---:|---:|---:|---|
| highD | 1.03 cm | 0.27 cm | 0.003 m/s (the 0.01 rounding) | 0.068 m/s | 3.94 / 4.85 / 6.27 m |
| inD | 0.31 cm | 0.17 cm | 0.004 m/s | 0.014 m/s | 3.64 / 4.48 / 5.25 m |
| rounD | 0.19 cm | 0.20 cm | 0.005 m/s | 0.016 m/s | 3.80 / 4.61 / 5.26 m |
| exiD | 0.05 cm | 0.05 cm | 0.0003 m/s | 0.053 m/s | 3.77 / 4.51 / 5.23 m |
| DLR HT spacing | 1.3 cm | | | | car box 4.43 m median |
| TGSIM I-90/94 spacing | 0.4 cm | | 0.056 m/s | | |

**What it bounds.**

- Jitter is no limit on any measurement here. A spacing jitter of 1.5 cm moves a time gap at 20 m/s by under 0.001 s.
- Speed is consistent with position to 0.01-0.07 m/s. That bounds closing speed and the 1 s acceleration at about 0.07 m/s².
- What this cannot see is slow error: a box length that is wrong, or a position biased over seconds. Only a probe vehicle can show that, and none exists for levelX. Car lengths look right (median 4.5-4.9 m), unlike DLR UT's 3.3 m.
- The smoothing itself matters more than the jitter. exiD and rounD are smoothed almost to a spline. That can spread a response in time, which bounds the lag measurement (part 4), and it may hide sharp thresholds (part 2).

## 2. Car following (F131-F135)

**Data.** Cars behind cars, same lane, same leader, at 5 Hz ([follow_steady.json](follow_steady.json), [follow_response.json](follow_response.json)):

- highD: 57 recordings, 85,508 followers. The bumper gap is exact (real box lengths).
- DLR HT: 06:00-14:00 UTC.
- TGSIM: I-90/94 stationary, I-294 L1 and I-395. These use centre spacing minus 5 m, report 05's convention.

**Steady following** means 10 s or more with |dv| under 1 m/s, gap under 100 m and speed over 15 m/s. One value per window (the median time gap).

| | Windows | Time gap p5 / p50 / p95, s | Median 95% CI |
|---|---:|---|---|
| highD | 12,245 | 0.47 / **0.98** / 2.22 | 0.97-0.99 |
| DLR HT | 10,113 | 0.54 / **1.09** / 2.48 | 1.07-1.11 |
| TGSIM I-90/94 stationary (15-20 m/s) | 302 | 0.64 / 1.23 / 2.65 | 1.17-1.34 |
| TGSIM I-294 | 429 | 0.45 / 1.00 / 2.65 | 0.93-1.09 |

- **The forecast's premise was the error.** Report 05's definition (any car within 150 m, 25-40 m/s) reproduces 1.62 s on DLR HT. Steady following selects coupled followers.
- **The value depends on how strict "steady" is.** On highD it runs from 1.08 s (3 s windows) to 0.98 s (10 s windows); on DLR HT from 1.23 to 1.09 s.
- **The time gap falls with speed, on every dataset.** highD medians by speed band:

| Speed band, m/s | 3-10 | 10-15 | 15-20 | 20-25 | 25-30 | 30-35 | 35-45 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Median time gap, s | 1.59 | 1.43 | 1.18 | 1.10 | 0.95 | 0.97 | 0.78 |

- TGSIM gives the same curve: 1.61-1.84 s at 3-10 m/s, 1.29-1.42 s at 10-20 m/s. A straight line fitted to highD steady states has a 10.9 m intercept and a 0.71 s slope. The stopped gap is about 2-3 m, so **spacing grows less than linearly with speed**, and a constant time gap cannot fit both ends.
- **Between sites and days the median moves less than the spread.** highD sites span 0.87-1.04 s. Location 1 gives 1.01, 0.97 and 0.98 s on Monday, Thursday and Wednesday.
- **Spread between windows: log-SD 0.46-0.54.** Only part of this belongs to the driver (part 3).

**Standstill bumper gap.**

- rounD queues: **1.73 m** (1.63-1.85; p10 1.02, p90 2.63; 225 cars).
- inD: **1.52 m** (1.29-1.64; 70 cars).
- highD: 2.95 m (26 stops; highD has almost no jams).
- TGSIM I-90/94: 2.92 m (centre minus 5 m, so not a bumper gap).
- Report 05's s0 of 2.8 m came from DLR UT's centre spacing and lengths assumed at 5 m. With real lengths, urban queues stand closer.

**Response in the next second** (F134, F135). The follower's mean acceleration over the next 1 s was taken against two inputs:

- gap error e: its time gap minus the median steady time gap at its speed (population reference), or minus its own median (own reference);
- closing speed dv.

The fit is a hinge model with the leader's current acceleration as a third term, plus conditional means.

| Mean next-second acceleration (m/s²) at small dv, by gap error (s, population reference) | −1.25 | −1.0 | −0.75 | −0.5 | −0.25 | 0 | +0.5 | +1.0 | +1.5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| highD | −0.29 | −0.12 | −0.06 | −0.02 | 0.00 | +0.02 | +0.02 | +0.03 | +0.04 |
| DLR HT | | −0.18 | −0.02 | −0.01 | 0.00 | +0.02 | +0.02 | +0.01 | 0.00 |
| TGSIM I-90/94 | −0.16 | −0.11 | −0.06 | −0.02 | +0.01 | +0.03 | +0.06 | +0.08 | +0.12 |

- **There is a band, but it is one-sided and wide.** From 0.5 s too close to 1.75 s too far, the response is under 0.05 m/s² on the German motorways. Past about 0.75 s too close it brakes, at about 0.2-0.5 m/s² per s of extra closeness. Drivers who have fallen back barely close up within a second.
- The symmetric hinge in the forecast picks a narrow centre band (0.1-1.0 s) with a steeper slope inside than outside: a ratio of outside to inside of 0.06-0.3, the reverse of the forecast. That is the saturating far side showing through, not a Wiedemann band.
- **Closing speed: no dead zone.** At |e| under 0.3 s, the mean next-second acceleration runs straight through zero. On highD it is −0.04 m/s² for dv in −0.5 to 0, +0.06 for 0 to +0.5, −0.14 at −1, +0.19 at +1, and it flattens near +0.24 above +1.5 m/s.
- Slope: about 0.11 /s over ±4 m/s on highD and DLR HT, 0.2 /s near zero, 0.3-0.4 /s on the congested TGSIM sites.
- The leader's current acceleration carries most of the next second: a coefficient of 0.25-0.65.
- **Action points show no threshold.** The |dv| at which drivers flip the sign of their acceleration grows with spacing: on highD 0.48, 0.61, 0.78, 1.06 and 1.68 m/s from 5-15 m to 60-100 m. That looks like Wiedemann's perception thresholds. But |dv| at random moments in the same bands is 0.51, 0.63, 0.83, 1.18 and 1.72 m/s, so drivers act at whatever closing speed happens to be there. TGSIM shows the same.
- **Limit.** These tracks are smoothed (part 1). A dead zone of 0.2 m/s could be blurred, but one of 0.5 m/s would survive and is not there.

## 3. Persistence (F136, F137)

Method: 20 s windows on DLR HT car tracks (06:00-10:00 UTC; 7,070 tracks; 5,495 following windows and 12,643 free windows). Cell means (250 m of road × 20 min × lane) are removed, and pairs of windows are taken on the same track ([persist.json](persist.json)).

| Distance apart, km | 0.5-1 | 1-1.5 | 1.5-2 | 2-3 | 3-4 | 4-5 | 5-6.5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Log time gap, all pairs | 0.72 | 0.55 | 0.48 | 0.45 | 0.39 | 0.39 | 0.47 (36 pairs) |
| Log time gap, **different leaders** | 0.29 (65 pairs) | 0.36 | 0.43 | 0.31 | 0.30 | 0.31 | |
| Free speed | 0.75 | 0.68 | 0.70 | 0.55 | 0.48 | 0.40 | 0.26 |

- **Time gap.** Over all pairs the correlation decays from 0.72 to a floor of 0.36 (SE 0.05), with an e-folding length of 1.2 km (SE 0.3). But when the two windows have different leaders, the correlation is 0.29-0.43 at every distance from 0.5 to 5 km, with no decay (CIs about ±0.15).
- So a driver keeps a personal time gap over at least 5 km. It explains about a third of the between-window variance: a persistent log-SD of about 0.47 × √0.33 ≈ 0.27, the same as report 05's 0.25. The faster-decaying part belongs to the pair: the same leader, a platoon.
- HIGH-SIM agrees on that part (73 tracks, same leader throughout): r 0.82 under 300 m, 0.67 at 0.3-0.6 km, 0.38 at 0.6-1 km.
- highD (track ends 209 m apart): r 0.75 (0.67-0.83; 129 tracks).
- **Free speed** decays almost linearly, with an e-folding length of 4.9 km. It is a trait that drifts within a trip. On highD the two ends of a 270 m free track correlate at 0.85 (7,066 tracks).
- **The two traits are linked.** A driver who is fast when free follows closer: r = −0.41 between a track's mean log time gap and its free speed (770 tracks).

## 4. Response lag (F138)

Three free fits, none chosen for waves ([follow_lag.json](follow_lag.json), [follow_kernel.json](follow_kernel.json), [follow_kernel_leader.json](follow_kernel_leader.json)):

| Estimator | highD | DLR HT | I-90/94 stat. | I-294 | I-395 |
|---|---|---|---|---|---|
| a) Lag of the best linear fit of acceleration at t+τ on gap, speed and dv at t | 2.2 s (2.2-2.4) | 1.8 s | 0.8 s | 1.2 s | 2.4 s (0.6-2.4) |
| b) Kernel to dv over 0-3 s, first-order fit: dead time + time constant | 0.15 + **0.48** s | 0.14 + **0.56** s | 0.0 + **0.52** s | 0.08 + **0.54** s | 0.30 + 0.05 s (degenerate) |
| c) Kernel to the leader's acceleration alone: centroid | 1.36 s | 1.91 s | 0.67 s | 0.47 s | 1.71 s |

- (a) measures where the slow, smoothed response is strongest, not a delay. It tracks report 05's cross-correlation lags (1.0-2.0 s).
- (b) has report 05's structure: a first-order filter of 0.66 s. It gives 0.48-0.56 s plus a dead time under 0.3 s on four datasets, so **0.5-0.8 s in all**. But below 0.5 s it shares the follower's own 1 s speed smoother, which leaks into the lag-0 weight. So it bounds the time constant from above; it does not separate a dead time.
- (c) avoids that leak, but its weights swing sign between neighbouring lags, which is what an input this smooth does. Only I-395 gives a smooth kernel (peak 2.0 s).
- **Two rounds without a clean pure delay, so stopped (rule 9).** What stands: report 05's 0.66 s filter is inside (b). **1.0 s is not supported by any free fit.**

## 5. Gap acceptance (F139-F141)

**Setup.** Who gives way comes from each site's Lanelet2 right-of-way elements. Each element is one of three kinds:

- minor road;
- left turn off the priority road across oncoming traffic;
- right-before-left. Frankenburg's four approaches form a cycle in its map.

**Definitions.**

- Decision: the front 3 m past the yield line. Minor cars often stand with the front up to 2 m past the mapped line, and the first version of the script, with the decision at the line, was wrong for that reason.
- Arrival: 10 m before the line. It is carried back at constant speed when the car is first seen inside that zone (8% of inD decisions, 52% of rounD).
- Conflicts: priority vehicles whose path comes within 2.5 m of the minor car's path, timed when they first reach it.
- A refused interval counts only if no other road user (pedestrian, cyclist, the car ahead, another minor stream) was on the first 25 m of the car's path during it. On inD 54% of decisions had someone there at some point, and 347 refused intervals were dropped as blocked.
- Critical gap: lognormal censored likelihood, as report 05 §4.5, with Raff as a cross-check ([gaps_inD.json](gaps_inD.json), [gaps_rounD.json](gaps_rounD.json)).

| inD (Aachen, weekdays) | Decisions | With a refusal | Critical gap, s (95% CI) | Raff, s | Follow-up, s (n) |
|---|---:|---:|---|---:|---|
| Bendplatz, minor road, left | 279 | 73 | **6.90** (6.36-7.46) | 7.04 | **4.96** (44) |
| Bendplatz, minor road, straight | 58 | 11 | 6.57 (4.85-7.93) | 6.49 | |
| Bendplatz, left off the priority road | 137 | 38 | **3.90** (3.28-4.64) | 3.56 | 2.12 (23, all sites) |
| Frankenburg, right-before-left, straight | 345 | 15 | 3.90 (3.07-4.85) | 4.44 | 3.04 (91) |
| Minor roads, all sites | 1,807 | 104 | 2.69 (2.46-2.91) | 3.60 | **2.88** (508); straight 2.68, right 3.16, left 4.88 |
| Bendplatz, Monday / Tuesday | 168 / 330 | | 4.83 / 5.37 | | |

| rounD (3 roundabouts) | Decisions | With a refusal | Critical gap, s | Follow-up, s |
|---|---:|---:|---|---|
| Arrival seen | 1,144 | 96 | **3.01** (2.74-3.35) | |
| All, including carried-back arrivals | 2,517 | 169 | 2.11 (1.89-2.39) | **2.76** (2.68-2.84, 1,172) |
| Drivers who stopped | 398 | 73 | 4.97 (4.40-5.60) | |
| Location 0, Tuesday / Thursday | 978 / 1,351 | 89 / 70 | 3.42 / 1.54 | 2.80 (location 0) |

- **The critical gap is weak wherever refusals are few.** At roundabouts and on the busy minor approaches most drivers never refuse a gap, so the estimate rests on the lower tail of accepted gaps and moves with the subset and the day. The minor-left estimate at Bendplatz (73 refusals) and the follow-up times are the strong numbers.
- **Follow-up time is the number our driver gets wrong most.** It is 2.7 s straight, 3.2 s right and 4.9 s left on inD, and 2.8 s at roundabouts, against the physical driver's 4.41 s.
- Two inD groups are unexplained and left out:
  - Frankenburg's other minor elements: 1,497 decisions, 11 refusals, 1.7 s.
  - Aseag's element 1173, a priority lanelet that also yields, read as a major left: 1.24 s.
- **No impatience.** Drivers almost never take a gap shorter than one they refused on a clear path: 3.8% on inD (8.5% after waits over 15 s, n = 59) and 2.4% on rounD.
- A logistic model over all offered intervals says acceptance *falls* with waiting (−0.11 to −0.16 per s). That is driver mix: cautious drivers stay in the sample longer. Within one movement (minor left) the waiting effect is zero (−0.05 to +0.03 per s).

## 6. Lane changes and merges (F142-F145)

exiD has 23,482 events over 57 recordings; highD has 12,234 car lane changes ([lanechange_exiD.json](lanechange_exiD.json), [lanechange_highD.json](lanechange_highD.json)). Time gaps are measured at the moment the centre crosses the marking. Each cell shows p5 / p50 in s, with the 95% CI in parentheses.

| | n | Lag time gap | Lead time gap | 10-90% duration, s | Peak lateral speed |
|---|---:|---|---|---|---|
| exiD on-ramp merge | 4,088 | **0.45** (0.42-0.48) / **1.81** (1.74-1.91) | **0.39** / **1.66** | **5.36** (5.32-5.44) | 1.25 m/s |
| exiD mainline | 12,633 | 0.49 / 1.67 | 0.38 / 1.71 | 5.04 | 1.25 m/s |
| exiD to an exit lane | 3,425 | 0.46 / 1.18 (n = 130) | 0.62 / 2.21 | 4.44 | 1.25 m/s |
| highD mainline | 12,234 | 0.45 / 1.21 | 0.30 / 1.54 | 4.36 | 1.0 m/s |
| highD to the left / right | 5,475 / 6,759 | 0.54 / 1.82 and 0.43 / 1.03 | 0.25 / 0.90 and 0.60 / 2.28 | 4.32 / 4.36 | |

- Durations need 5 s on each side, since these recordings are short. They are lower bounds: report 05's 5.6 s on DLR HT used 8 s.
- **Where drivers merge.** The median is 0.49 (0.48-0.50) of the acceleration lane, with 109 m left (lanes 183-262 m long). By site the median runs from 0.35 to 0.59, and 4.7% merge in the last tenth.
- **The car behind.**
  - It slows 0.3 m/s² or more beyond followers at the same speed with no merger in 10.3% (9.3-11.6) of merges, against 6.3% of baseline windows: an excess of 4 points.
  - Its mean relative acceleration is +0.01 m/s².
  - For mainline changes: 12.4%, an excess of 6 points.
  - Most courtesy is not braking, as report 14 found.
- **German motorway drivers take tighter gaps than report 05's DLR HT set showed:**
  - lag p5 0.45 s against 0.70;
  - lead p5 0.30-0.39 s against 0.61.
  - highD is the busier traffic.

## 7. Launch and discharge, SinD weekdays (F146)

Three Chinese recordings were used: Tianjin (Monday 09-10 h), Changchun and Chongqing. Xi'an is held out. Data: [sind.json](sind.json).

- **Light codes**, read from the sequences: 1 green, 3 yellow (3.0 s everywhere), 0 red. Tianjin has a 1 s all-red; there is no red-yellow.
- **Which light governs each approach**: inferred from when standing cars start.
- **Changchun's light log looks several seconds off.**
  - On its light-2 approaches, cars keep crossing at full flow for 4 s after the logged red.
  - Every queue head starts 4-7.5 s after the logged green. On light 1 they may be waiting for light 2's late traffic to clear, since Changchun has no all-red.
  - In Tianjin and Chongqing, crossings stop at the logged red and heads start 1.5-2.9 s after green.
- So numbers that need the green onset use Tianjin and Chongqing only. Headways from position 2 on, and launch acceleration, need no clock and use all three.

| | Value | n |
|---|---|---:|
| First car passes 1.5 m/s after green | **2.0 s** (1.7-2.2); p10-p90 1.0-3.9 | 57 queue heads |
| First car crosses the line after green | 2.8 s (2.2-3.1) | 57 |
| Headway at position 2, 3, 4, 5 | 3.7, 2.9, 2.6, 2.7 s | 74, 31, 16, 8 |
| Saturation headway, position 4 and on | **2.6 s** (2.45-3.2) | 30 (Changchun) |
| First car's peak acceleration | **1.77 m/s²** (1.66-1.88); p5-p95 0.54-3.01 | 154 |

- Against DLR UT's Sunday (report 05):
  - The peak acceleration agrees: 1.80 m/s².
  - The start is later by 0.4 s, which is about what a German red-yellow gives in warning.
  - Discharge is slower: 2.6 against 2.0 s per car.
- SinD is mixed traffic with motorcycles, bicycles and tricycles between the cars, so its slower discharge is not a test of German drivers.
- **No weekday German site with signal states is on disk.** DLR UT's 2.0 s stays labelled Sunday.
- **LADDMS is not usable here.** It has no signal states, and its one sample day (2 September 2024) is a US public holiday (Labor Day).

## 8. Desired speed (F147)

One value per car: the median speed over samples with no leader within 150 m (motorway), at least 2 s free ([freespeed.json](freespeed.json)).

| Road | n | Median, m/s (km/h) | 95% CI | SD | CV | p5-p95 |
|---|---:|---|---|---:|---:|---|
| highD, no limit (3 sites) | 7,485 | **34.5** (124) | 34.4-34.7 | 5.7 | 0.17 | 25.4-44.9 |
| highD, 130 km/h | 1,922 | 34.5 (124) | 34.3-34.7 | 4.8 | 0.14 | 25.3-41.4 |
| highD, 120 km/h | 30,195 | **32.2** (116) | 32.2-32.3 | 6.1 | 0.20 | 19.9-38.5 |
| exiD, 120 km/h | 5,664 | **30.7** (110) | 30.5-30.9 | 5.8 | 0.19 | 20.0-37.4 |
| exiD, 100 km/h | 7,229 | **28.3** (102) | 28.2-28.4 | 3.5 | 0.12 | 23.4-34.8 |
| exiD, no limit, main carriageway (sites 2, 3, 6) | 12,783 | 33.2-34.8 by site | | 5.3-6.1 | 0.15-0.18 | |
| DLR HT (Monday) | 10,461 | 34.2 (123) | 34.1-34.3 | 6.3 | 0.18 | 24.2-45.3 |

- Drivers sit near the limit where there is one. The spread between drivers is a CV of 0.12-0.20, so **SUMO's speedDev of 0.1 is too narrow**.
- exiD's "no limit" lanelets at sites 0 and 1 are connector roads (20-22 m/s), not free motorway, and are left out.
- **Urban desired speed is not measurable from inD.** Inside the drone's view every car is approaching or leaving the junction. Free cars on priority roads go 4.1 m/s at Frankenburg (right-before-left), and too few qualify at the other sites. A mid-block urban recording is needed (pNEUMA off-peak, Helsinki).

## Rerun

```sh
source /home/erikf/projects/personal/cars-data/dev-env.sh; export OMP_NUM_THREADS=1   # one job at a time: the agent slice's guard kills more
python3 -I scripts/measure/levelx.py cache highD inD rounD exiD     # about 5 min, held-out recordings skipped
python3 -I scripts/measure/levelx_scene.py highD 1                  # a replay scene; inD 0, rounD 1, exiD 0 likewise
python3 -I scripts/measure/noise.py
python3 -I scripts/measure/dlrht.py 0 12                            # DLR HT 06-10 UTC blocks
python3 -I scripts/measure/follow.py table && python3 -I scripts/measure/follow.py steady
python3 -I scripts/measure/follow.py response; python3 -I scripts/measure/follow.py lag
python3 -I scripts/measure/follow.py kernel; python3 -I scripts/measure/follow.py kernel_leader
python3 -I scripts/measure/persist.py && python3 -I scripts/measure/persist.py highsim
python3 -I scripts/measure/gaps.py inD; python3 -I scripts/measure/gaps.py rounD
python3 -I scripts/measure/lanechange.py exiD; python3 -I scripts/measure/lanechange.py highD
python3 -I scripts/measure/sind.py; python3 -I scripts/measure/freespeed.py
```
