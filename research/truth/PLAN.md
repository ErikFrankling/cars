# Plan: good science first

Erik, 6 November: the north star is good science. That needs a baseline close to real-world data, so a lot of good real data to test against. Build the simulation from first principles and from what other projects got wrong, until it is true to life: a car you look at behaves like a real human, and at system scale it matches real data. Then build self-driving into it and see what it changes. Rethink every prior, ours included.

The earlier ladder (Berlin first, git history up to 1e4ecd7) is replaced. What it found still holds and is listed under "Kept".

## The priors we drop

| Prior | Why it fails | Instead |
|---|---|---|
| Berlin with MATSim demand is the main test | When demand comes from a model, a miss can come from demand, routes, map, signals or drivers, and the data can't tell which. We saw it: MATSim's routes overload 311-365 movements at full demand, which no driver can fix | Test behaviour first where demand, routes and signals are recorded. Berlin comes last, as a test of demand and routes once behaviour is settled |
| Theory scenes show the driver is right | They show the code does what its equations say. That is verification. Only recordings can show the equations are human. That is validation | Keep both and name them. A scene never sets a behaviour number |
| Parameters are plausible averages, adjusted until things look right | Fitted numbers absorb errors they didn't cause (Kennedy & O'Hagan 2001). Report 05's calibrated Krauss deceleration of 0.33 m/s² is one | Every behaviour number is measured as a distribution, from a recording of that behaviour alone, then frozen. Nothing higher up may move it |
| Matching a number means realistic | Many wrong models match one number (report 22). Counts can't tell free flow from a jam carrying the same flow | Indistinguishable from reality: the gap between simulation and recording is no larger than between two recordings, at every scale, on data never used to set anything |
| Behaviour is the car-following model | Most urban error sits in junctions, lane choice and lane changes, and the deadlocks are there | Every decision a driver makes gets its own recording-based test |

## The method: replay with recorded boundaries

A drone or overhead-camera recording sees every vehicle in an area. So we know when and where each one entered, at what speed and in which lane, where it left, and often what the signals showed. Put exactly that into the simulator at the edge of the recorded area and simulate only what happens inside. Demand and routes are then facts, not guesses. Signals are facts where the controller's states were recorded (DLR UT, SinD). In pNEUMA and Songdo they are read from stop-line crossings, which is circular if unchecked: a green read too short hides a discharge that is too slow. So that reading is first scored where the true states are known, and its error becomes a band on every result that uses it. What's left to differ is the driver and the map, and the map is checked separately against the recording.

One setting decides how much is simulated:

- **One vehicle simulated, the rest replayed.** Its leader and neighbours move exactly as recorded. Does this driver do what real drivers did in the same place?
- **One lane, approach or corridor simulated.** Do the queues, waves, discharge and capacity drop come out right?
- **Every vehicle in the area simulated.** Travel times, delay by approach, queue lengths, spillback, the area's flow-density curve.

Vehicles we don't model, such as motorcycles, bikes and buses, stay replayed at every setting. Self-driving uses the same harness: replace a share of recorded humans with automated vehicles and compare against the all-human replay of the same recording.

What replay doesn't control by itself, and the control for each:

| Confound | Control |
|---|---|
| Replayed vehicles don't react. A replayed follower never brakes for the simulated car | Overlaps are counted as a harness artefact, never as behaviour, and end that comparison. Passes are set at the second and third settings, where everyone reacts |
| Queues from outside the view set exit times | Replay the last recorded vehicle beyond each exit as a leader. Score T3 only on approaches whose exit runs free, or say otherwise |
| Map errors | Lane geometry checked against where recorded vehicles drive; map-matching residuals reported per lane |
| Tracker errors | Floor each metric by tracker against ground truth where a probe vehicle exists. No bumper gaps from DLR UT's short boxes or TGSIM's default lengths |
| Short recordings: the start state dominates 30 minutes | Start every vehicle from the recorded snapshot, discard a warm-up as long as the longest trip, and never re-initialise during a run. Per-cycle re-initialisation (Tsioutis 2026 on pNEUMA) hides the error growth we need to see |
| Motorcycles in Athens filter between lanes | Motorcycle share per lane and area. Prefer low-share areas and times, and run once with them removed to size their effect |
| One Sunday | DLR UT numbers are labelled Sunday until a weekday site (SinD, inD) agrees |
| No pedestrians in pNEUMA or Songdo | Turning capacity there lacks pedestrian yield delay; said wherever it matters |

## Tiers

Each tier passes before the next counts. Tiers that don't depend on each other run side by side.

| Tier | Question | Recordings (on disk unless marked) | Compared | Status |
|---|---|---|---|---|
| **T0 Verification** | Does the code do what its equations say? | Theory scenes, `scripts/theory/scenes.py` | Hand-computed answers, forecasts F001-F049 | Running |
| **T1 One driver** | Does one simulated driver among recorded traffic act like the real one? | Car following: highD, TGSIM, DLR HT, HIGH-SIM, NGSIM. Launch and yellow: DLR UT (controller signal states), SinD. Gap acceptance: inD, rounD, Swiss roundabouts, OpenDD, DLR UT, Songdo. Lane changes and merges: exiD, highD, DLR HT, HIGH-SIM, DRaT, NGSIM I-80 | Distributions of gap, speed, acceleration, accepted gaps, timing, place. A classifier test, below | Next |
| **T2 Streams** | Given recorded inflow, do the right queues and waves appear? | HIGH-SIM (congested motorway), exiD, NGSIM I-80 and US-101, DLR UT (one German junction, 24 h, real signals), SinD, Lankershim. Songdo's 20 junctions, each its own scene: vehicle IDs are per file and junctions aren't stitched (downloading) | Wave speed, period and growth; capacity drop; queue length over time; discharge per cycle; lane use. Error against elapsed time on the long recordings (DLR UT 24 h; I-24 when it arrives) | Next |
| **T3 Areas, recorded demand** | Given every recorded entry, does the area behave like the recording? | pNEUMA, Athens: 10 drone areas over several mornings, every vehicle, heavy congestion (downloading; count the days on disk) | Per-vehicle travel time, delay by approach, queues, spillback, flow-density curve. Signals read from stop-line crossings, with their error band | After T1, T2 |
| **T3b Past saturation** | When demand exceeds capacity, does the driver jam, hold and recover like people do? | The most oversaturated pNEUMA areas and cycles; motorway breakdowns in HIGH-SIM and I-24 | Blocked junction boxes, holds and their length, give-ups, spillback, recovery time. A written forecast of behaviour past saturation first | Before any T4 run. T4 puts the driver in states no ordinary recording has: Berlin died there |
| **T4 Cities** | Partly recorded demand, then modelled demand | Xuancheng (plate reads and signal intervals, 1 h), Cambridge (camera journeys, 8 days), Jinan (reconstructed paths). Then Berlin, Stockholm, Madrid | Report 22's benchmark | Berlin parked |
| **T5 Self-driving** | What changes when some vehicles are automated? | Recorded automated vehicles: TGSIM I-294 L1 and L2 (adaptive cruise strings, humans behind), OpenACC (to fetch), CIRCLES on I-24 (100 unmarked vehicles in live traffic; account pending). Waymo only for marked vehicles | First the automated controller against its recordings, including adaptive cruise's known string instability. Then how humans respond to it. Then counterfactual replays on T2-T4 | After T3b. Humans react to an automated car they can recognise differently from one they can't (Zhao 2020; Wen 2022, behind marked Waymo cars), so the human model predicts reactions only to unmarked ones unless marked recordings test it |

## How a pass is decided

1. **Noise floor first, the right one per tier.** Replay asks how much the outcome varies given the same boundary, which reality never shows twice. Two days is too generous, since demand differs; two halves of one recording is too strict, since drivers and conditions are shared. So: in T1, the spread among different real followers behind similar leaders. In T2, the cycle-to-cycle spread under the same signal plan and similar arrivals. In T3, a bracket between the two-halves and the two-days floors, both reported.
2. **Indistinguishable, and better than a dumb model.** A metric passes when the simulation-to-recording gap has a confidence bound under the floor (an equivalence test with the margin written first, not a failure to reject), and the simulation beats a null model given the same inputs: a point queue with the measured discharge headway, a constant-time-gap follower, free-flow travel time plus signal delay. If a simple model does as well, the micro detail adds nothing there yet.
3. **Human-likeness: response, not context.** In the first setting a window is mostly the leader's motion, so comparing windows tests the scene, not the driver. Compare what the driver does given the same history: the next action scored with CRPS, and how far a rollout drifts from real followers behind matched leaders. For whole tracks, a classifier two-sample test (Lopez-Paz & Oquab 2017) and a kernel distance (MMD) with per-feature Wasserstein distances, which say what is wrong. Train and test splits and permutations go by vehicle and day, never by window, since windows of one vehicle aren't independent. The floor is measured per pairing (two drones, two days), and it will sit above 0.5. Both sides pass through the same instrument first: simulated tracks get the recording's sampling and smoothing, or the test just learns the tracker.
4. **Ensembles, not single runs.** Many seeds. Report where the recording falls in the simulated spread, with a proper score (CRPS), not only the mean.
5. **Duration counts.** Error is reported against elapsed time. A model good for 30 minutes and drifting after two hours fails, whatever its 30-minute score.
6. **Held out by design.** Set numbers on some days and sites, test on others, and on a contrasting place: set on Athens and the German sites, test on Songdo and Helsinki (the Nordic contrast; one sample on disk, the rest to fetch). A held-out set is opened once per change that already passes everything else.

## The driver, from first principles

A human driver perceives, decides and acts, with delays and errors, inside a vehicle. Every part is a measured quantity. Nothing enters without a recording that shows it.

| Part | What it is | Measured as | First source |
|---|---|---|---|
| Perception | Gap and closing speed are judged with error, with a threshold below which change isn't noticed | Spread of response to small closing speeds | TGSIM, HIGH-SIM |
| Delay | Response to the leader comes late | Lag that best explains the follower | Report 05's free fit: 0.66 s. It chose 1.0 s because that gives realistic waves, so 1.0 s is provisional (rule 4) and the wave test must use other recordings than those chains |
| Attention | Drivers adjust in steps, not continuously | Acceleration noise and its correlation time | Report 05: small correlated noise |
| Following | Preferred time gap and standstill gap, different per driver | Distributions in steady following | TGSIM, DLR HT, HIGH-SIM, highD |
| Persistence | Whether a driver keeps their time gap and speed over a trip. Fresh draws match every distribution yet give no slow platoons or moving bottlenecks | Correlation of one driver's values along a long track | Long tracks: DLR HT (6 km), HIGH-SIM (2.4 km), I-24 (6.75 km, pending). Report 05's 30 s windows can't show it. Measured before any T3 pass counts |
| Free driving | Desired speed per road type and per driver | Speeds of unconstrained vehicles | DLR HT, pNEUMA off-peak, Berlin 05-06 h |
| Launch | Delay of the first car, headway of the rest | Crossing times after green | DLR UT: 2.7 s lost, 2.0 s per car, one Sunday. Report 05 tuned its gain `k2` to this, so DLR UT can't test it; Lankershim (1.9 s median, not used) and SinD can |
| Yellow | Stop or go | Share stopping by time to the line | DLR UT: half stop at 5.1 s; almost no one brakes over 2 m/s² |
| Gap acceptance | Accepted and rejected gaps, follow-up time, impatience over waiting | Gap choices per waiting time | Swiss roundabouts: critical gap about 2.95 s. Give-way junctions still to measure |
| Lane choice | Where drivers move into the lane they need | Distance before the junction | pNEUMA, Songdo |
| Lane change | Gaps accepted, duration, courtesy of the car behind | Accepted lead and lag gaps; 10-90% time | Report 05: 5.1-5.6 s; only 35% of congested US changes pass SUMO's safe-gap test |
| Vehicle | Power, braking, size | Manufacturer data and launches | Report 11 |

Emergent facts the whole must then reproduce with no retuning: wave speed, concave growth of oscillations along a platoon (Jiang et al. 2014), capacity drop at an active bottleneck, signal discharge, queue spillback, the flow-density curve of an area.

## What other projects got wrong, and what we do

| Mistake | Source | Here |
|---|---|---|
| Calibrated to counts that many parameter sets reach | MULTITUDE 2014: GEH targets "can be obtained with a multiplicity of parameter combinations" | Measured parts, emergent tests, no fit to aggregates |
| Demand and behaviour tuned together, going in circles | FHWA Toolbox III 2004 | Behaviour on recorded demand (T1-T3) before modelled demand (T4) |
| Failures hidden | SUMO teleports a car stuck 300 s by default | No teleports, no removal. Give-ups are behaviour and counted |
| Means of one run | MULTITUDE 2014 | Ensembles and proper scores |
| Car following fitted on trajectories, then waves vanish in the network | "Calibration Illusion", 2026: waves "degrade to non-existence" | Waves are a T2 test of their own |
| Learned simulators judged over 8 s | WOSAC 2023 | Horizons of hours, flows and queues |
| No held-out test | Report 15: no published city micro model passed on held-out data | Pass rule 6 |
| Re-initialising the replay every signal cycle, which hides error growth | Tsioutis 2026, pNEUMA | One start, no re-initialisation, error against elapsed time |
| Us: a city first, theory scenes taken as validation, big runs then guessing | This repo, October-November | This plan |

## Rules

1. **No run without a written forecast** in `foundations/forecasts.csv`: the number, where it comes from, the tolerance. Replay-tier forecasts use F100 onwards.
2. **A miss gets explained before anything else changes.** Code or assumption, find out which.
3. **Fix a cause on the lowest tier that shows it.** A T3 miss caused by lane changes goes back to T1 lane changes.
4. **A behaviour number comes from a recording of that behaviour**, with its source written next to it. A value set because a scene passes with it is marked provisional.
5. **Reference is recordings and theory.** No decision rests on SUMO or `--sumo-compat`. SUMO's netconvert may still convert map formats.
6. **One seed is no result.**
7. **No vehicle removal, no demand scaling.**
8. **Agreement between our own layers is consistency, not truth.**
9. **Two rounds with no gain on a problem: stop, write down what was tried, take the next.**

## Kept from the earlier ladder

- The theory scene suite and forecasts F001-F049, now T0.
- The reality table, `foundations/R-reality-table.md`: 97 real Berlin jam places, saturation 1,750 (1,640-1,900), green splits, cars on the road by hour, Hamburg signal pairs. It serves T4.
- The macro assignment on branch `t3/macro-assignment-rungs-3-5`, parked with its log. Berlin needs it in T4.
- The static checks in `scripts/theory/`.
- Report 22's benchmark and noise floors, the scoreboard for T4.

## First experiments and their forecasts

Written before any run, F100-F104 in `forecasts.csv`.

1. **Harness check (T0).** Replay every vehicle of a recording: the simulator's output equals the recording within map-matching error.
2. **One follower (T1).** TGSIM I-90/94, report 05's held-out day, one simulated vehicle behind its recorded leader. 30 s spacing error between 4.0 and 5.5 m. Under 4.4 m only if the driver has report 05's 1 s response lag. Report 05: its lagged model 4.00 m, calibrated Krauss 5.43 m, calibrated IDM 5.54 m.
3. **Classifier, as a test of the test (T1).** Splits by vehicle and day. Two halves of one recording near 0.5 accuracy; two drones or two days above it, measured as the floor for that pairing. Today's driver against real well above the floor, since a driver with no noise in acceleration is easy to spot. If it isn't spotted, the test has no power.
4. **One approach (T2).** DLR UT, one signal approach, recorded arrivals and controller states, every car on it simulated. Discharge per saturated cycle at least as close to the recording as a point queue with 2.0 s headway and 2.7 s lost time. This checks the harness on real signals; it isn't independent, since report 05 tuned discharge on DLR UT. The independent test is F120, the same on SinD, whose signal states are recorded and which no fit has used.

A separate review (Fable, 6 November) found the holes fixed above: overload untested, persistence unmeasured, duration ignored, one noise floor for all tiers, inferred signals called recorded, the lag and discharge already tuned on the data meant to test them. Prior work it found: Tsioutis 2026 replayed one pNEUMA junction in SUMO, re-initialised every cycle and had no held-out data; Montanino & Punzo 2015 found NGSIM I-80's raw tracks give wrong macroscopic patterns until reconstructed, mainly through lane changes; Hickert 2026 on I-24 found waves vanish with scale and duration, and that a time step of 0.55 s against 0.5 s changed the result.

## Data access

- **highD, exiD, inD, rounD** (German motorways, motorway exits and entries, junctions in Aachen, roundabouts): granted 2 November, downloaded 6 November to `datasets/levelx/`. Non-commercial use, no redistribution, cite the papers.
- **I-24 MOTION and CIRCLES** (Nashville motorway, every vehicle, and the 100-vehicle automated test of November 2022): account requested 6 November, waiting for the site's approval. A scheduled check reads the KTH inbox on 7 November and downloads when approved.
