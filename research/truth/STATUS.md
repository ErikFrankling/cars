# Status board

The orchestrator keeps this current. Work follows the ladder in `PLAN.md`. No run without a line in `foundations/forecasts.csv`. Reference is reality or theory; SUMO and `--sumo-compat` count for nothing here.

## Goal
Human-only traffic on the Berlin district (49 km²): no vehicle removal, full demand, report 15's Credible thresholds on held-out sites.

## Ladder
| Rung | State | Number that says so |
|---|---|---|
| 1. Reality table | Running | Targets with a number, spread and source |
| 2. Scenes and real tracks | Running | Scenes passing, of about 40 |
| 3. Movement table | Running | Site-hours outside the two-way capacity test |
| 4. Macro assignment | Next | RMSN, R², slope, GEH<5, class bias, rush-hour dip, jam list |
| 5. Vehicles and forecast | Waits | Var/mean, now 0.82 / 2.97 / 5.63 at 10 / 50 / 100% |
| 6. Corridor | Waits for 2, 5 | Real queue place, start, end, discharge |
| 7. Micro district | Waits for 6 | Real speeds and jam list; cars on road against forecast; hold p99 and max |
| 8. Score | Waits | Gate |

## What is known, measured or computed
| Fact | Value | Source |
|---|---|---|
| Movements over capacity on MATSim's routes, 100 / 50 / 30% | 311-365 / 11-20 / 0 | D §2.4 |
| Top jam roots at 50%, two old-driver runs: on or next to an overload; on a signal approach under 50 m | 6-27%; 40-54% (chance 4%, 10%) | PLAN, `scripts/theory/seeds_vs_*.py` |
| Major-road demand at peak against a regression on other cities | 245,200 against 262,000-318,000 veh-km/h, ±47% | B §5.4 |
| Cars on the road at 100%, from real speeds on model vehicle-km | 13,186 at 07-08 h, 15,114 at 08-09 h; recheck in rung 1 | B §5.1 |
| Longest wait at a real lane end | 79 s, 0 of 610 failed | Report 14 |
| Time for a held car to fill a median block | 78-157 s | C §3.4 |
| Physical driver follow-up at give-way | 4.41 s against 3.0 | B §3 |
| Human driver saturation | 1,500, now 1,800 after the launch fix B's formula points to | B §1, report 16 |
| Physical driver saturation and motorway | 1,929; 1,732-1,891 across three runs | Physics rounds |

## Open from the stopped runs
Not in main: the human driver, `t3/1b36c9cf` at 11afb41, conflicts with the physical driver in seven files, and gets merged by scene results. Its motorway flow is 1,220 per lane, and its final regression pass was cut short. Its no-jump fix for real I-80 tracks is in, but `merge_i80_real_vs_sim.mp4` was cut to 33 of 80 s by the watchdog and needs a full render, checked by eye, once the driver settles. `t3/c5547dcd` has the route agent's iteration files only. Rules committed but unproven: abreast (never fired), missed turns (15 m trigger misses 62% of lane-change root hours in older runs).

## Rules against rabbit holes
- Fix a cause only on the lowest rung that shows it.
- A miss against a forecast gets explained before anything else changes.
- Two rounds with no gain on a problem: stop, write down what was tried, take the next item.
- Merge to main often. At most 3 agents while one Claude account is at its weekly limit (it resets 4 November, 16:00).
