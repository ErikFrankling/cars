# Plan: build it in the right order, and know the answer before running

From Erik: "Think from first principles. Read how real-to-life simulations are constructed. Lay out a plan that you know will have the desired effect before testing anything. You keep doing large tests, basically throwing shit at the wall to see what sticks." And: "Who cares about SUMO."

The reading is in `foundations/`: A how simulations are built, B what theory predicts, C why real traffic stays fluid, D from demand to lanes. Self-driving work stays paused (VALIDATION-GATE.md).

## The chain

A traffic simulation is a chain. Each link has its own measured truth, and each can be checked before the next exists.

Map and signals → capacity of each movement → routes that fit those capacities → queues → delay → routes again.

Tune from the far end and parameters absorb errors they didn't cause (FHWA 2004, pp. 7, 45, 54). We started at the far end: a whole city, then guessing from its jam.

## What we did wrong

1. **Routes from another model.** MATSim's routes answer "best path on MATSim's capacities". About 80% of the edges over 900 veh/lane/h are MATSim's own flow, at v/c 0.55 on its numbers. Its capacity on most main-road signal approaches is one constant, 845 veh/lane/h, whatever the signal or the turn. On our map's movements those routes overload 311-365 movements at 100%, 11-20 at 50%, none at 30%. That takes 2 seconds to compute and needs no simulation (D §2.4; `scripts/theory/screen.py`, rerun and confirmed). So a jam at 50% was never a surprise.
2. **The micro simulator as the first assignment tool.** In a jam, feedback means nothing. Report 23's "the fault left isn't route choice" isn't shown: no run has used routes assigned on this map's capacities.
3. **A driver that fails hand calculations, put on a city.** Give-way follow-up is 4.41 s against a real 3.0 s, which alone explains most of the give-way deficit (B §3).
4. **Waits that never end.** Root cars in saved runs are held a median 30-60 min. The longest wait measured at a real lane end is 79 s, and a median block fills behind a held car in 78-157 s (C §3.4). The lock happens at 2-4% of jam density, so it isn't a space problem.
5. **Copied trips.** Demand above 10% is copies of each trip, same route, within ±150 s. Variance over mean of 5-minute counts per movement: 0.82 at 10%, 2.97 at 50%, 5.63 at 100% (`scripts/theory/dispersion.py`). Random queue goes as I·x²/(2(1-x)). At x 0.85 that is 2.4 cars with independent trips and 13.5 with today's at 100%. The median signal approach holds 12 cars per lane. No report had tested this.
6. **No list of real jams.** Nobody builds a model without one (Gomes; FHWA). We only scored against it afterwards.
7. **SUMO and the old driver as reference.** "Healthy" was five times an old-driver run, and SUMO was used to split causes. Both go. The same target now comes from real speeds and Little's law (B §5.1), and the split comes from the macro layer below.

Not causes, tested: the district boundary (a wider cut has more cars inside, not fewer). Adding 141 OSM signals on the old driver and rigid routes gave no gain, so map coding is checked per movement, not assumed to be the fix.

## Rules

1. **No run without a written forecast.** A line in `foundations/forecasts.csv` before the run: the number, the formula or model it came from, the tolerance. No forecast, no run.
2. **A rung passes before the next rung runs.** No city run to see what happens.
3. **A result that misses its forecast gets explained first.** Either the code or the assumption is wrong, and we find out which before changing anything else.
4. **Reference is reality or theory.** No decision rests on SUMO or `--sumo-compat`. `scripts/golden.py` only guards that mode, and isn't a merge gate.
5. **One driver.** Physical motion with human decisions on top. Each human rule enters when a scene shows the gap it closes.
6. **One seed is no result** where the outcome is chaotic. Scenes and district runs quote a spread.
7. **Never scale demand to pass.** No vehicle removal. A driver giving up a turn and carrying on is behaviour, allowed and counted.

## The ladder

| Rung | What | Runs | Cost | Exit test | If it fails |
|---|---|---|---|---|---|
| **1. Reality table** | Real jams: place, start, end, extent, across the 8 days, from probes and loops. Highest flow per site with a queue present. Free speed by class, closing probes against detectors. Saturation flow: report 25's 1,640 against the 1,800-2,100 band. Cars on the road by hour from real speeds | Data only | Hours | Every target below has a number, a spread and a source | Say what can't be known, and drop that check |
| **2. Scenes** | About 40 small scenes from B and C, each with a computed answer: lane, ring, signal, give-way, lane change, lane drop, spillback, closed grid, clone bursts. One command. Time step frozen here | Seconds each, CPU | Days of driver work | All pass on one driver at one time step, within tolerance | Fix the driver. A city run proves nothing until this passes |
| **3. Movement table** | Every movement in the map: capacity, storage, free time, from lanes, signals and HBS. Connections with no green. Main roads with capacity under 50 veh/h | No simulation, seconds | Hours | Real flow ≤ 1.1 × table capacity at every site and hour, or a named cause. Scenes agree with the table within 10% per class | Fix the table or the map, one named cause at a time |
| **4. Macro assignment** | 100% demand, whole region, movement delay, real free speeds, road hierarchy. Only who, where, when, class comes from MATSim | One CPU, minutes | Days to build | Tuning sites: RMSN ≤ 0.40, R² ≥ 0.75, slope 0.85-1.15, GEH<5 ≥ 60%. Class bias ±15%. Rush-hour dip ±0.10. Jam list ≥ 60% caught, ≤ 40% false | **Stop.** No micro can beat it. Sweep capacity inside measured ranges and signals inside Hamburg's. If it still fails, Berlin's inputs can't pass: say so and move to Madrid or to data |
| **5. Vehicles and forecast** | Macro's paths to whole vehicles with independent draws. Kinematic-wave pass for spillback. Writes the forecast for rung 6: cars on the road by hour, queue places and times | No simulation, minutes | Days | Var/mean near 1 at every demand. Movements within 5% of macro. Lane-feasible routes | Fix before any micro run |
| **6. Micro district** | In order: near-empty, flat reduced, 50% peak, 100%. Small to big | GPU, short | Hours each | Cars on road per hour within 10% of forecast. Discharge per movement within 10%. Holds: p99 under spill time, none over 5 min | Macro has no queue and micro does: engine or lane fault. Both have it: map or routes. Fix there, on the lowest rung that shows it |
| **7. Score** | Benchmark on tuning sites with one configuration. Open locked sites once. Then Madrid | | | Gate thresholds | Report exactly what fails |

## What we can already calculate

These are forecasts, written before any code changes.

| Change | Today | Calculated after |
|---|---|---|
| Give-way follow-up 4.41 → 3.0 s | 816 / 474 / 279 / 162 veh/h at major 0 / 400 / 800 / 1,200 | 1,200 / 696 / 404 / 234. HBS 1,200 / 736 / 451 / 277 |
| Independent trips instead of copies | 13.5 cars of random queue at x 0.85, 100% demand | 2.4 cars |
| A wrong-lane head gives up after 60 s, 10% of a lane's cars | 0 veh/h through that lane | 450 veh/h (S3) |
| Holds end in about 90 s instead of 30 min | Active seeds N = λD | About 20 times fewer at the same seed rate |
| Lane planning | 36% complete a change on a 97 m block at 900 veh/h, Δv 3 m/s | 95% needs 660 m of planning, or 190 m after slowing to Δv 6 |
| Full demand on major roads | | 230,500-245,200 veh-km/h, inside the real network's 262,000-318,000 (Loder). So no network-level reason to lock |

## What isn't known

- Whether macro reaches the bars on Berlin's invented signals. Rung 4 answers that in minutes of computing, which is why it comes before any more micro work.
- How much each give-up or forcing behaviour moves a real network. No field study measures it. Scenes prove each rule works, not its size in a city.
- The match between the screen's limit (first overloads at 30% with our give-way) and the stepped run's freeze at 30% is one match, and that run re-routed between steps.
- Hamburg's detector feed is signal requests, not counts. It gives real cycles and greens, not saturation flow.

## Parked

Stockholm, self-driving tiers, signal-free junctions, the learned driver, the report rewrite. The benchmark stays as the final scoreboard, used at rung 7, not as a hill to climb before then.
