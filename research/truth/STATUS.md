# Status board

The orchestrator keeps this current. Work follows the tiers in `PLAN.md`. No run without a line in `foundations/forecasts.csv`. Reference is recordings and theory; SUMO and `--sumo-compat` count for nothing here.

## Goal
Good science: a simulator whose every behaviour is tested against recordings where everything else was observed, so that a car you look at acts like a human and an area matches its recording, before any self-driving result counts.

## Tiers
| Tier | State | Number that says so |
|---|---|---|
| T0 Verification | One driver, dt 0.25 s; junction faults fixed (`foundations/scenes-log.md` §5) | 142 pass, 60 fail of 202. Fixed: zipper (880/879 per arm, was 1,573/0), give-way gap rule (critical gap 7.9 -> 6.6 s), roundabout collapse, exit_comply. Open: give-way capacity still short by the start from rest (1.7 s to enter a gap); lane-change merges give one side 70%; lane drop at 100 km/h loses 18-28%; right-before-left grids lock at 0.2 kj as cycles around a block |
| T1 One driver | Measured driver round 2 merged, off by default (`measure/ROUND2.md`). Next: choose the following law's structure by testing candidates against every measured fact at once | Next-second response matches real drivers (round 1, held out). Lane capacity 1,104 veh/h against real 1,640-1,900: in the first 4 s of a queue launch followers fall 1.5-2 m behind real ones. Gaps at speed close slowly in reality too (28-41% in 30 s). Default driver: capacity right, response wrong |
| T2 Streams | DLR UT approach replays with its recorded signals; replayed cars now change lanes smoothly; highD and exiD scenes are multi-lane (`replay/RESULTS.md`) | DLR UT discharge per cycle within 0.14-0.32 cars (harness check). SinD has no queue of 4+ cars, so F120 can't be measured there; on Tianjin the driver crosses 3.6-4.1 s off against a point queue's 1.3 s, carried by a car running a yellow its real driver stopped for and by replayed motorcycles taking a whole lane |
| T3 Areas, recorded demand | pNEUMA drones 8 and 6 replay with boundary entry and read signals (70 of 95 links); noise floor measured (`replay/RESULTS.md`, `PNEUMA.md`) | Real mornings differ by 1.5-2.3 s in approach delay and 7.6-10.9 s in travel time. With every car simulated, both areas lock at junction clusters within 5 minutes: 39-45% of cars ever enter, travel time off by 106-188 s, 40-60 times the floor. Reality flows there (mean approach delay 5.5 s), so this is our fault to find |
| T4 Cities | Berlin macro merged, parked: `foundations/macro-log.md` ("Pick it up cold") | Movement table passes (0.18% of site-hours over). Whole day: arterial speed bias -5.6%, dip .66 against .69; motorways, jam list (0-17% caught) and counts (RMSN .43) fail. Route choice alone reaches RMSN .30, so next is route cost on unsignalled streets |
| T5 Self-driving | Waits for T3 | |

## Recordings on disk
Car following and lane changes: highD and exiD (`datasets/levelx/`), TGSIM (5 sites), DLR HT (A39), HIGH-SIM sample, NGSIM (4 sites), DRaT, HDSVT. Junctions: inD and rounD (`datasets/levelx/`), DLR UT (24 h, controller signal states), SinD (4 cities, signal states), OpenDD, Swiss roundabouts, Songdo one junction-day. Whole areas: pNEUMA (`datasets/pneuma-full`). Junction sets: Helsinki (`datasets/helsinki-drones-full`, Jätkäsaari 2024-2025, the Nordic contrast), LADDMS stage 1 (`datasets/laddms-stage1`, lidar at a Nashville corridor), Songdo (20 junctions, downloading to `datasets/songdo-full`). Cities: Xuancheng, Cambridge one day, Jinan. All under `/home/erikf/projects/personal/cars-data/truth/trajectories/` and `datasets/`.

## What is known, measured or computed
| Fact | Value | Source |
|---|---|---|
| Queue discharge with real signal states | 2.0 s per car, 2.7 s lost | Report 05, DLR UT |
| Lane change duration, 10-90% | 5.1-5.6 s on about 36,000 events | Report 05 |
| Congested US lane changes passing SUMO's safe-gap test | 35% (free German motorway 85%) | Report 05 |
| Yellow: half stop at | 5.1 s to the line; almost none brake over 2 m/s² | Report 05 |
| Roundabout critical gap | about 2.95 s, 7,131 decisions | Report 05 |
| Car following, held-out 30 s spacing error | lagged model 4.00 m, Krauss 5.43, IDM 5.54 | Report 05 |
| Longest wait at a real lane end | 79 s, 0 of 610 failed | Report 14 |
| Berlin: movements over capacity on MATSim's routes, 100 / 50 / 30% | 311-365 / 11-20 / 0 | D §2.4 |
| Berlin real saturation flow | 1,750, sweep 1,640-1,900 | R §2 |
| Real day against real day, Berlin jam places | caught 67%, false 33% | Report 22 |

## The driver as measured (`measure/DRIVER.md`)
| Part | Value | Today's driver |
|---|---|---|
| Time gap, steady following | falls with speed: 1.6 s at 3-10 m/s to 0.8 s over 35 m/s; median 0.98 s at 25-35 m/s | one value |
| Personal part of the time gap | log-SD 0.27, kept over at least 5 km | redrawn or none |
| Gap error response | one-sided: none from 0.5 s too close to 1.75 s too far, braking beyond 0.75 s too close | steers to its own gap |
| Closing-speed response | linear, no dead zone, 0.1-0.4 /s; 0.25-0.65 of the leader's acceleration shows within 1 s | |
| Response lag | time constant 0.5 s, dead time under 0.3 s; report 05's 1.0 s does not stand | |
| Standstill bumper gap | 1.7 m | 2.5-2.8 m |
| Desired speed spread | coefficient of variation 0.12-0.20, keeps r 0.5 over 3 km; fast drivers follow closer (r -0.41) | 0.1 |
| Give-way follow-up | straight 2.7, right 3.2, left 4.9 s; roundabout 2.76 s | 4.41 s (physical driver) |
| Critical gap | minor left 6.9 s, left off the priority road 3.9 s, roundabout about 3.0 s; no impatience found | |
| Lane change | gaps p5 0.45 s behind, 0.3-0.4 s ahead; duration 5.0-5.4 s; merges at 49% of the acceleration lane | |
| Launch at green, weekdays | first car 2.0 s after green, peak 1.77 m/s² | 2.6 m/s² |

## Data access
- highD, exiD, inD, rounD: downloaded 6 November, manifest with checksums and licence in `datasets/levelx/manifest.json`.
- I-24 MOTION and CIRCLES: account requested 6 November, pending approval; scheduled check 7 November 17:00.

## Rules against rabbit holes
- Fix a cause only on the lowest tier that shows it.
- A miss against a forecast gets explained before anything else changes.
- Two rounds with no gain on a problem: stop, write down what was tried, take the next item.
- Merge to main often. At most 3 agents while one Claude account is at its weekly limit (account 2 until 9 November, 11:00).
