# Held-out recordings for the driver measurements

Fixed 6 November 2026, before any number in `research/truth/measure/` was computed. No script under `scripts/measure/` reads these unless called with `--holdout`, and none has been. They are for the later replay test of the driver built from these numbers.

| Part | Held out | Why this one |
|---|---|---|
| Tracker noise (1) | none | It describes the instrument, not drivers |
| Car following, band, lag (2, 4) | highD location 6 (recordings 58-60, a Wednesday in July 2018, 5 lanes per direction); DLR HT 14:00-16:00 UTC (never read by report 05); TGSIM I-90/94 moving (already the replay harness's test day) | A site, an hour block and a day no fit has seen |
| Persistence (3) | DLR HT 14:00-16:00 UTC; highD location 6 | Same |
| Gap acceptance (5) | inD location 3, Heckstrasse (recordings 30-32, a Thursday); rounD location 0 Wednesday (recordings 20-23) | A whole site, and a day at the busiest roundabout |
| Lane changes and merges (6) | exiD location 5 (recordings 73-77, a Friday); highD location 6 | A whole merge site |
| Launch and discharge (7) | SinD Xi'an | A whole city |
| Desired speed (8) | highD location 6; exiD location 5; inD location 3 | Same as above |

7 November 2026, lane changes (LANECHANGE.md): exiD location 5 and highD location 6 were **not** opened. Step 4 does not pass, so no held-out test was run.

7 November 2026, round 5 (MODEL.md, OPENGAP.md): **opened** for the round 5 law (j), after its fit was frozen (ship_jw.json, F837-F838) and its T0 realism rows passed (L1 1,874 veh/h at 50 km/h, S1 1.93 s): TGSIM I-90/94 moving, DLR HT 14:00-16:00 UTC and highD location 6 for the one-follower tests (F854-F860, round 1's windows and queries), and SinD Xi'an for the first time, for launches (F861, F862). Forecasts and margins were committed first (f09c603). The other held-out recordings stay closed.
