# Plan: build it in the right order, and know the answer before running

From Erik: "Think from first principles. Read how real-to-life simulations are constructed. Lay out a plan that you know will have the desired effect before testing anything. You keep doing large tests, basically throwing shit at the wall to see what sticks." And: "Who cares about SUMO."

The reading is in `foundations/`: A how simulations are built, B what theory predicts, C why real traffic stays fluid, D from demand to lanes. Self-driving work stays paused (VALIDATION-GATE.md). This version includes a separate review of the first draft, and the test that review proposed.

## The chain

A traffic simulation is a chain. Each link has its own measured truth, and each can be checked before the next exists.

Map and signals → capacity of each movement → routes that fit those capacities → queues → delay → routes again.

Tune from the far end and parameters absorb errors they didn't cause (FHWA 2004, pp. 7, 45, 54). We started at the far end: a whole city, then guessing from its jam.

## What we did wrong

1. **Routes from another model.** MATSim's routes answer "best path on MATSim's capacities". About 80% of the edges over 900 veh/lane/h are MATSim's own flow, at v/c 0.55 on its numbers. Its capacity on most main-road signal approaches is one constant, 845 veh/lane/h, whatever the signal or the turn. On our map's movements those routes overload 311-365 movements at 100%, 11-20 at 50%, none at 30% (D §2.4; `scripts/theory/screen.py`, rerun and confirmed, 2 seconds). That rules those routes out at full demand. At 50% it explains only part of the jam; see the next section.
2. **The micro simulator as the first assignment tool.** In a jam, feedback means nothing. Report 23's "the fault left isn't route choice" isn't shown: no run has used routes assigned on this map's capacities.
3. **A driver that fails hand calculations, put on a city.** Give-way follow-up is 4.41 s against a real 3.0 s, which alone explains most of the give-way deficit (B §3).
4. **Waits that don't end.** Root cars in saved runs stay held from first to last 15-minute sample for a median of 30-60 min, which isn't proof of unbroken holding but is far outside reality. The longest wait measured at a real lane end is 79 s, and a median block fills behind a held car in 78-157 s (C §3.4). The lock happens at 2-4% of jam density, so it isn't a space problem.
5. **Copied trips.** Demand above 10% is copies of each trip, same route, within ±150 s. Variance over mean of 5-minute counts per movement: 0.82 at 10%, 2.97 at 50%, 5.63 at 100% (`scripts/theory/dispersion.py`). Random queue goes roughly as I·x²/(2(1-x)), so about 2.4 cars with independent trips and 13.5 with today's at x 0.85. That is an order of magnitude only: the count ignores signal filtering, contains the rising demand of 07-08 h, and copies spread over three 90 s cycles. It is second order next to items 1 and 3, and it gets a scene (X1) to size it.
6. **No list of real jams.** Nobody builds a model without one (Gomes; FHWA). We only scored against it afterwards.
7. **SUMO and the old driver as reference.** "Healthy" was five times an old-driver run, and SUMO was used to split causes. Both go. The same target now comes from real speeds (B §5.1), though the vehicle-km behind it still come from a model.

Not causes, tested: the district boundary (a wider cut has more cars inside, not fewer). Adding 141 OSM signals on the old driver and rigid routes gave no gain.

## Where the jam sources really sit

The review's falsifier: if the static screen explains the 50% jam, jam roots should sit on its overloaded approaches. `scripts/theory/seeds_vs_screen.py`, `seeds_vs_storage.py`. Share of top-15 root vehicle-hours, chance being that set's share of route flow. Saved runs, old driver, map m12, MATSim routes, so this is a clue about the map and the engine, and each row is one run:

| Where the root stands | Chance | `hunt_s5_s0` | `why5`, stopped early |
|---|---:|---:|---:|
| Approach over capacity, x > 1 | 1% | 5% | 27% |
| ... or next to one | 4% | 6% | 27% |
| Signal approach whose red-time queue doesn't fit | 3% | 25% | 21% |
| Signal approach under 50 m | 10% | 54% | 40% |
| Signal approach under 30 m | 5% | 39% | 32% |
| Inside a junction | | 20% | 0% |

The run on assigned routes, `whya1`, differs: 3% on short approaches, with 45% of root hours waiting for a lane change, 29% a yield and 29% inside a junction. Lane-change waits are 24% and 19% in the two runs above.

**So overload is real and predicted, but it isn't what starts most of the 50% jam.** My first draft said a jam at 50% was never a surprise. That was too strong. Most roots stand at approaches the table calls fine, and this leaves three local faults, each testable in a small scene:

- **Short links between signals.** A 17 m link can't hold one red's arrivals. I expected real signals to clear such links and ours not to. Hamburg doesn't confirm that: under 50 m, 77% of real through pairs are linked with a small offset, but only 46% clear on the report's test, and our invented programs clear as often (R §6). Ours are too uniform, not obviously worse. So why roots gather on short approaches is still open. Next checks: opposed pairs and turns into short links, lane choice and queueing on short links (scene N9), and how a real short link behaves when it fills.
- **Waits for a lane or a gap that don't end.** C's finding.
- **Stand-offs inside junctions.** The largest single root in `hunt_s5_s0`, 436 vehicle-hours, is a yield 2 m into a junction lane.

So rung 2 and the signal-pair check matter at least as much as the macro layer. Macro is still needed, for full demand and because no test has used routes fitted to this map.

## Rules

1. **No run without a written forecast.** A line in `foundations/forecasts.csv` before the run: the number, the formula or model it came from, the tolerance. No forecast, no run.
2. **A rung passes before anything that depends on it runs.** No city run to see what happens. Rungs that don't depend on each other run side by side.
3. **A result that misses its forecast gets explained first.** Either the code or the assumption is wrong, and we find out which before changing anything else.
4. **Reference is reality or theory.** No decision rests on SUMO or `--sumo-compat`. `scripts/golden.py` only guards that mode, and isn't a merge gate.
5. **One driver.** Physical motion with human decisions on top. Each human rule enters when a scene shows the gap it closes.
6. **One seed is no result** where the outcome is chaotic. Scenes and district runs quote a spread.
7. **Never scale demand to pass.** No vehicle removal. A driver giving up a turn and carrying on is behaviour, allowed, counted, and capped at 10 per 1,000 trips. That ceiling is a judgement, since no field measure exists. Going over it means lane planning is wrong.
8. **Nothing gets tuned to pass a fitted number.** Demand v6.4 was already fitted to these count sites, so agreeing with them proves little. Signals follow one rule fixed before scoring. Sweeps report sensitivity and are never a search for the best value.
9. **Agreement between our own layers is consistency, not truth.** Micro matching macro splits causes. Only real data passes a rung that claims realism.

## The ladder

Dependencies: 1 → 3 → 4 → 5 → 6 → 7 → 8, and 2 → 6. Rung 2 runs alongside 3 and 4.

| Rung | What | Runs | Cost | Exit test | If it fails |
|---|---|---|---|---|---|
| **1. Reality table, done** | `foundations/R-reality-table.md`. 97 credible real jam places in the district. Saturation 1,750, sweep 1,640-1,900; Berlin can't settle it. Main-road green 0.47-0.76, cycle 75-110 s. Free speed from 05-06 h. Cars on the road at 100%: 12,800-16,100 at 07-08 h, 15,700-18,500 at 08-09 h, 18,500-21,800 at 16-17 h, the real peak. MATSim's morning runs about an hour early: real over model 0.77 at 06 h, 0.86 at 07 h, 0.98 at 08 h, 1.11-1.18 at 09-11 h | Data only | Done | Every target has a number, a spread and a source | |
| **2. Scenes and real tracks** | About 40 small scenes from B and C with computed answers, including two signals 20 m apart and stand-offs inside a junction. Most run in seconds; the closed grid is hours of simulated time on CPU. Then the benchmark's trajectory levels on held-out real tracks, since norm formulas alone are bands. Time step frozen here | CPU | Days of driver work | All pass on one driver at one time step, within tolerance | Fix the driver. A city run proves nothing until this passes |
| **3. Movement table** | Every movement: capacity, storage, free time, from lanes, signals and the German manual. Connections with no green. Main roads with capacity under 50 veh/h. **Through signal pairs under 50 m follow the rule from R §6, fixed before any Berlin score:** same cycle, downstream green +2 s, overlap 0.65. `cuts.rs` on this table: if 100% exceeds a cut, no routing can fix it | No simulation, seconds | Hours | **Upper:** real flow ≤ 1.1 × table capacity at every site-hour, or a named cause. **Lower:** hourly loops can't test capacity from below, since real queue-hour flow is a median 619 per lane at any saturation, so a table too high is caught by jams: every real jam head on the list must have a table capacity near its real flow, or a named cause. Scenes agree with the table within 10% per class | Fix the table or the map, one named cause at a time |
| **4. Macro assignment** | 100% demand, whole region, movement delay, real free speeds, road hierarchy. Only who, where, when, class comes from MATSim | One CPU, minutes | Days to build | **First the blind checks:** speed by class and hour, rush-hour dip ±0.10, the 24 clean cross-sections, and the real jam list, scored against what one real day gets on the other seven: caught 72-81%, false 22-40% at a third of free speed; 80-91%, 7-11% at half. Then fitted sites: RMSN ≤ 0.40, R² ≥ 0.75, slope 0.85-1.15, GEH<5 ≥ 60%, class bias ±15% | Macro understates delay, so speeds alone don't condemn it. If flows by site and class can't be reached with capacities inside measured ranges, the demand is the problem: stop micro work on Berlin, say so, and go to data or Madrid |
| **5. Vehicles and forecast** | Macro's paths to whole vehicles. Same-route clusters gone, peak shape kept. Kinematic-wave pass for spillback. Boundary: metered entries, time-varying exit capacity. Writes the forecast for rungs 6 and 7 | No simulation, minutes | Days | Peak profile within 5%. Bunching as scene X1 says it must be. Movements within 5% of macro. Lane-feasible routes | Fix before any micro run |
| **6. Corridors** | No single corridor has both known timing and known discharge. Leipziger Straße-Gertraudenstraße eastbound: jam on 8 of 8 days from 15:30, four loops in a line, discharge about 750 per lane, signals by rule. B1/B5: jam on 8 of 8 days, published cycles, no loops. Small simulated area around each | GPU, short | Hours | Leipziger: real jam place, start, end and discharge. B1/B5: real place and time | Back to the lowest rung that shows the cause |
| **7. Micro district** | In order: near-empty, flat reduced, 50% peak, 100%. Small to big | GPU, short | Hours each | **Real data:** speed by class and hour, jam list, flows on tuning sites. **Own forecast:** cars on road within 15%, discharge per movement within 10%. Holds: p99 under spill time, none over 5 min. Give-ups under 10 per 1,000 trips | Macro has no queue and micro does: engine or lane fault. Both have it: map or routes. Fix there, on the lowest rung that shows it |
| **8. Score** | Benchmark with one configuration. Open locked sites once. Then Madrid | | | Gate thresholds | Report exactly what fails |

## What we can already calculate

These are forecasts, written before any code changes.

| Change | Today | Calculated after |
|---|---|---|
| Give-way follow-up 4.41 → 3.0 s | 816 / 474 / 279 / 162 veh/h at major 0 / 400 / 800 / 1,200 | 1,200 / 696 / 404 / 234. German manual 1,200 / 736 / 451 / 277 |
| A wrong-lane head gives up after 60 s, 10% of a lane's cars | 0 veh/h through that lane | 450 veh/h (S3) |
| Holds end in about 90 s instead of 30 min | Active seeds N = λD | About 20 times fewer at the same seed rate |
| Lane planning | 36% complete a change on a 97 m block at 900 veh/h, Δv 3 m/s (a floor; real drivers do better) | 95% needs 660 m of planning, or 190 m after slowing to Δv 6 |
| Independent trips instead of copies, order of magnitude | About 13.5 cars of random queue at x 0.85, 100% demand | About 2.4 cars |
| Full demand on major roads | 230,500-245,200 veh-km/h | 262,000-318,000 by a regression on other cities, ±47%, so only a rough sign the network fits. Real per-lane flow is 6-15% under this demand |

## What isn't known

- Whether macro reaches the bars on Berlin's invented signals. Rung 4 answers that cheaply, which is why it comes before any more district micro work.
- How much each give-up or forcing behaviour moves a real network. No field study measures it. Scenes prove each rule works, not its size in a city.
- Why jam roots gather on short signal approaches. It's two old-driver runs, top 15 roots each, sampled every 15 minutes, on an invented signal program, and Hamburg didn't confirm the first explanation.
- The match between the screen's limit (first overloads at 30% with our give-way) and the stepped run's freeze at 30% is one match, and that run re-routed between steps.
- Berlin's saturation flow, green splits, motorway capacity, residential traffic and queue lengths. R "What can't be known" says why. One Berlin queue count with a stopwatch, or real weekday headways anywhere in Germany, would settle saturation.
- There is no real reference for bunching at 5-minute level, since Berlin's detectors are hourly.
- Whether to correct MATSim's early morning. A time-profile factor is the smallest OD change there is, and it is only allowed after route and capacity work, within rule 7.

## How it could pass and still be wrong

- Signals tuned against sites demand was already fitted to. Rule 8 forbids it, and blind checks come first.
- A table too generous everywhere passes the upper test. Real jams on the list must come out as jams, in macro and in micro, which a too-generous table can't do.
- Micro agreeing with a macro built on the same inputs. Rule 9, and rungs 6 and 7 exit on real data.
- Scenes pass on norm values that aren't Berlin's. Rung 1 settles what can be settled, and held-out sites at rung 8 are the final word.

## Parked

Stockholm, self-driving tiers, signal-free junctions, the learned driver, the report rewrite. The benchmark stays as the final scoreboard, used at rung 8, apart from its trajectory levels at rung 2.
