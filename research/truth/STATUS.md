# Status board

The orchestrator keeps this current. Work follows the tiers in `PLAN.md`. No run without a line in `foundations/forecasts.csv`. Reference is recordings and theory; SUMO and `--sumo-compat` count for nothing here.

## Goal
Good science: a simulator whose every behaviour is tested against recordings where everything else was observed, so that a car you look at acts like a human and an area matches its recording, before any self-driving result counts.

## Tiers
| Tier | State | Number that says so |
|---|---|---|
| T0 Verification | Running: theory scenes, one driver, frozen time step | Scenes passing; baseline 74 pass, 98 fail (physical), 79, 99 (human) |
| T1 One driver | Harness merged (`replay/RESULTS.md`). Measuring the driver's parts from highD, inD, rounD, exiD, SinD | Main's driver fails: 30 s spacing error 6.30 m; classifier 0.89 against a real floor of 0.64-0.68; next-second response 0.68 m/s, worse than constant speed (0.37). It steers to its own 1 s gap; real followers keep 2.3 s and let it drift |
| T2 Streams | DLR UT approach replays with its recorded signals | Discharge per cycle off by 0.14-0.32 cars of 7.3 (harness check, not independent). Cars cross the stop line 2.1-2.4 s early: launch at 2.6 m/s² against 1.8 measured. F120 on SinD needs stop lines inferred first |
| T3 Areas, recorded demand | pNEUMA on disk (15 GB); Songdo downloading | |
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

## Data access
- highD, exiD, inD, rounD: downloaded 6 November, manifest with checksums and licence in `datasets/levelx/manifest.json`.
- I-24 MOTION and CIRCLES: account requested 6 November, pending approval; scheduled check 7 November 17:00.

## Rules against rabbit holes
- Fix a cause only on the lowest tier that shows it.
- A miss against a forecast gets explained before anything else changes.
- Two rounds with no gain on a problem: stop, write down what was tried, take the next item.
- Merge to main often. At most 3 agents while one Claude account is at its weekly limit (account 2 until 9 November, 11:00).
