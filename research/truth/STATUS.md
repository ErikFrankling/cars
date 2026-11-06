# Status board

The orchestrator keeps this current. Work follows the tiers in `PLAN.md`. No run without a line in `foundations/forecasts.csv`. Reference is recordings and theory; SUMO and `--sumo-compat` count for nothing here.

## Goal
Good science: a simulator whose every behaviour is tested against recordings where everything else was observed, so that a car you look at acts like a human and an area matches its recording, before any self-driving result counts.

## Tiers
| Tier | State | Number that says so |
|---|---|---|
| T0 Verification | Running: theory scenes, one driver, frozen time step | Scenes passing; baseline 74 pass, 98 fail (physical), 79, 99 (human) |
| T1 One driver | Next: replay harness | F101 spacing error; F102-F103 classifier |
| T2 Streams | Next, same harness | F104 discharge per cycle against a point queue |
| T3 Networks, recorded demand | Data downloading: pNEUMA, Songdo | |
| T4 Cities | Berlin macro parked on `t3/macro-assignment-rungs-3-5` | Reality table done |
| T5 Self-driving | Waits for T3 | |

## Recordings on disk
Car following and lane changes: TGSIM (5 sites), DLR HT (A39), HIGH-SIM sample, NGSIM (4 sites), DRaT, HDSVT. Junctions: DLR UT (24 h, controller signal states), SinD (4 cities, signal states), OpenDD, Swiss roundabouts, Songdo one junction-day. Whole areas: pNEUMA one file (full set downloading), Songdo (full set downloading). Cities: Xuancheng, Cambridge one day, Jinan. All under `/home/erikf/projects/personal/cars-data/truth/trajectories/` and `datasets/`.

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

## Erik
- I-24 MOTION and CIRCLES need a verified account in his name.
- highD, exiD, inD, rounD: pending review since 2 November, answer to erikfran@kth.se.

## Rules against rabbit holes
- Fix a cause only on the lowest tier that shows it.
- A miss against a forecast gets explained before anything else changes.
- Two rounds with no gain on a problem: stop, write down what was tried, take the next item.
- Merge to main often. At most 3 agents while one Claude account is at its weekly limit (account 2 until 9 November, 11:00).
