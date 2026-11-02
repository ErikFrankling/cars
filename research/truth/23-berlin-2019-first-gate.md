# 23: Berlin, May 2019, first gate

Done 2026-11-02 on branch `t3/45597235`. Nobody was contacted. Scenario in `cars-data/berlin2019/`, scripts in `scripts/berlin2019/`, frozen files and logs in `research/truth/berlin2019/`. Each result names the step of [report 15's recipe](data-hunt/15-how-to-match-reality.md) it comes from. Grades: **MEASURED** (real data I computed), **MODELLED** (simulation or MATSim), **OPINION**.

## The answer

**It doesn't pass, and it is not yet a result.** The recipe stops at step 2. On the v6.4 net, the 49 km² district locked up with 10% of demand. After rounds of logged map fixes it runs the whole 10% day with teleports off: all 176,236 trip pieces finish, none are late, and no car is left at the end. At 50% it fails: by 08:00, 3.8 times as many cars are on the road as the 10% run implies. At 100% it was already 2.6 times by 06:30, and the PC's load guard killed that run at 06:41. Report 15's Credible column needs full demand, so no number here is a real result.

**The largest single cause is not the driver or the signals.** 29.3% of the district's vehicles had a U-turn in their MATSim route, 18,699 of them at signals, because MATSim's routes ignore turn rules. Removing them moved a lock-up from midday to a run that finishes.

**What's still open:** why 50% jams. SUMO on the same net and routes jams about as fast, and 25 iterations of route assignment barely help, so it isn't route choice or `cars` alone. See the hill climb below.

## Hill climb after the first report

Every round is a line in `research/truth/berlin2019/rounds.csv`. The count is cars on the road at 07:30 with teleports off, on step 2's test. A healthy day has 1,403 at 10% and 7,015 at 50%. One seed each except where noted, and lockup is chaotic, so differences under about 10% mean nothing.

| Round | Change | Driver, demand | Cars at 07:30 | At 08:00 | Reading |
|---|---|---|---:|---:|---|
| 0 | Map m10, netconvert's signals | Krauss, 50% | 19,825 | 31,527 | Start |
| 1 | One program per junction (report 10), m12 | Krauss, 50% | **14,792** | 25,258 | **Best signal change: −25%. Kept** |
| 1 | Static programs | Krauss, 50% | 20,936 | 31,687 | No gain |
| 1 | Give-way capacity in band, `impatience` 0.25 | Krauss, 50% | 17,709 | | −11% |
| 1 | Report 11's generator, adapted to Germany | Krauss, 50% | Over 16,800 by 07:00 | | Worse. 9,676 on m12 at 07:00 |
| 1 | Green split retimed to MATSim's flows | Krauss, 50% | 22,685 | | Worse |
| 1 | Report 10's 12 m join, across signals | Krauss, 50% | Over 11,700 by 07:00 | | Worse |
| 3 | Routes after 25 assignment iterations | Krauss, 50% | 13,691 | 23,196 | **−7%. Sensible routes don't hold it** |
| 2 | Physics, now main's default, on m12 | Physics, 10% | 2,947 | 4,964 | Locks at 10%, where Krauss finishes |
| 2 | Single rules off: arbiter, certificate, exit clear, zones, fleet of cars only, dt 0.5, faster lane changes, `lc_path` | Physics, 10% | 2,643–3,975 | 3,863–5,382 | **No rule alone frees it.** dt 0.5 reached only 07:00 before it stopped: 2,209, against 2,053 |
| 4 | Merge rule fix | Physics, 10% | 2,919 | 4,366 | Small |
| 4 | Fix of a car stopping itself half on a lane | Physics, 10% | 2,948 | 4,466 | Clears the night lock, not the morning |
| 4 | Both fixes, second seed | Physics, 10% | 2,782 | 4,053 | Still 2 × healthy |
| 4 | Both fixes | Physics, 50% | 31,955 | 43,034 | Was 37,728 and 47,641: −15% |
| 4 | Human driver, branch head | Human, 10%, dt 1 | 11,088 | 14,851 | Far from running on a city at dt 1 |

**Signals: two rounds and no gain, so I've stopped there (status board's rule).** The German generator (`german_tls.py`) gets closer to Hamburg's measured programs than netconvert does: cycle p10/p50/p90 70/76/110 s against 73/90/110, green share 0.16/0.43/0.77 against 0.15/0.31/0.60, where netconvert has 90/90/90 and 0.36/0.47/0.51. It still jams sooner. Retiming also shows signals aren't the limit at 50%: it leaves 2 of 2,050 loaded lanes over capacity, down from 16. So at 50% no signal is short of green for its flow.

**Route assignment, run by the route-choice agent on my scenario:** 25 iterations at 50%, relative gap 33% down to 11%, unfinished at 12:00 from 55% down to 38–44%. Still stalled at about 10:25 in 24 of 25 iterations. **The map doesn't hold under sensible routes, so the fault left is not route choice.**

**Two real bugs found with the tools.** Both are physics, and neither is in main yet:
1. **Merges asked for 12 s gaps, not 5 s.** Copied from SUMO, the waiter's impatience softens the foe's braking when it judges a merge, so a far foe counts as arriving fast. This is why isolated give-way capacity was low. Minor road capacity at major flows of 400, 800 and 1,200: 327, 194, 96 before and 474, 298, 159 now, against 736, 451, 277 from HBS. Still 57–66%.
2. **A car stopped itself half on a lane.** A long vehicle needing a lane change stopped for it with its rear on the junction, and physics refuses a change until the rear is clear. So it waited for ever. That locked Ernst-Reuter-Platz from 00:30 with almost no traffic. Stuck over 300 s at 02:00: 11 before, 0 now.

Also: my virtual loops wrote out of bounds for a vehicle with no lane, which stopped every car in trusted mode on the merged engine. That's fixed, and `scripts/bench/instrument/sensors-main.patch` now fits main's new edge counters. The gridlock report no longer crashes on a stale item. Physics at step 3 is now in band on saturation (1,870) and motorway (1,839), against 1,714 and 1,590 before. Its start wave, 28.6 km/h, is just over the 16–28 band, and capacity drop wasn't measurable in that scene. Step 3's exit still fails on give-way. The benchmark wasn't run on these rounds, because no driver finishes a day above 10%.

**What stops 50% now.** Not signal capacity, routes, fleet, or the kernel alone, since SUMO jams too, with 22,515 at 07:30. Roots of the jam on assigned routes with Krauss, by vehicle-hours held: **a car stopped waiting to change lane 722**, give-way 476, signal 299, exit full 95. The worst cluster sits at Karl-Liebknecht-Straße, close to the cut's east edge, and I haven't ruled out a boundary artefact there. So the leading explanation is cars blocked abreast on short roads, then spillback through blocks of tiny storage. This is an explanation of what the tools show, not yet a proven cause: no test has removed it.

**Next, in order:** a lane swap or giving-up rule for cars blocked abreast, tested at 50%; a larger cut, to test the boundary; then turn and bus lanes from OSM 2019, and the follow-up time at give-way (816 an hour with no major flow, against 1,200).

## Scorecard

All at tuning sites on tuning days. **Nothing here is held out**, so don't read it as validation. Floors use the same code as the simulation column, median over the other days, worst in brackets. The simulated column is the 10% day with flows ×10: it shows demand and map with no congestion, so it can't show a jam. It's a diagnostic from step 2, not a gate result. Medians over 8 real days.

| Check | Metric | Real floor | Credible | Sim: 10% ×10 | Verdict |
|---|---|---:|---:|---:|---|
| Nothing stuck | 100% demand, teleports off | n/a | ≤0.5% unfinished | 2.6 × the 10% level at 06:30, run not finished | **FAIL** (step 2) |
| | 50% | n/a | no persistent queue | 3.8 × the 10% level at 08:00 | **FAIL** (step 2) |
| | 10% | n/a | | 0 unfinished, 0 late, 0 teleports, 5 edges stopped over 1 h | Pass |
| Physically real | Report 19's distributions | | | The driver used here has no cornering rule (report 19) | **FAIL**, not re-measured |
| Day shape | Mean abs share, points | 0.09 (0.12) | ≤0.5 | 0.67 | Below Credible |
| | Peak hour AM, PM | same, ±1 | ±1 h | 07 vs 08, 16 vs 15 | Credible |
| | Night share 00–05 | 3.8% | | 1.9% | Too low |
| Volume | Hourly site RMSN, 07–18 | 0.09 (0.15) | ≤0.40 | 0.46 | Below Credible |
| | R² | 0.96 (0.89) | ≥0.75 | 0.23 | Below Credible |
| | Slope | 0.96 | 0.85–1.15 | 0.48 | Below Credible |
| | GEH<5 | 93% (86%) | ≥60% | 23% | Below Credible |
| | WAPE | 6.5% (9.1%) | ≤35% | 37% | Just below Credible |
| | Sites' total | 1.6% (2.9%) | ±10% | −9.4% | Credible; floor missed |
| | Vehicle-km, main roads, against SVZ 2019 | | ±10% | 4.18 vs 4.18 M km, static, step 4 | Credible, not blind in spirit |
| | Cordon, against SVZ 2019 | | ±10% | −14%, static | Below Credible |
| Speed, probes | Motorway, class × hour, mean abs | 11.5% (24%) | ±10% | 25.6%, flat all day | **FAIL** |
| | Arterial | 3.3% (7.9%) | ±20% | 17.6%, flat all day | Inside Credible, but for the wrong reason |
| | Lowest hour ÷ highest, motorway | 0.46 | | 0.96 | **No rush hour** |
| | Lowest hour ÷ highest, arterial | 0.69 | | 0.97 | **No rush hour** |
| Speed, detectors | Site median abs | 2 km/h | | 6 km/h | Floor missed |
| Travel time | Routes | | ≥70% | | **NOT TESTED**: no route data used here |
| Where and when | Jam hours caught, false alarms | 73%, 33% | ≥60%, ≤40% | 25%, 88% | **FAIL** |
| | Top-20 bottlenecks shared | 80% | ≥50% | 28% | **FAIL** |
| Network curve | Peak flow | 0.3% | ±20% | +10% (no congestion in it) | Not meaningful yet |
| Trips | Length, duration | | ±15% | | **NOT TESTED**: the cut makes pieces of trips; MATSim was fitted to the same survey |

Report 15's floor of RMSN 0.19 is for September 2024 with no faulty-day filter. On May 2019 with faulty site-days dropped, the same code gives 0.09, in line with report 22's WAPE floor of 7.3%. The sampling noise of ×10 adds about 11% at 800 vehicles an hour, so part of the 0.46 is that.

Real speeds, MeTS-10 method on the sim's own edges, mean of 8 days (MEASURED):

| Hour | 06 | 07 | 08 | 09 | 12 | 15 | 16 | 17 | 18 | 20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Motorway, km/h | 75 | 56 | 47 | 56 | 69 | 38 | 36 | 45 | 56 | 78 |
| Arterial, km/h | 37 | 32 | 28 | 28 | 29 | 26 | 25 | 27 | 28 | 34 |
| Local, km/h | 35 | 28 | 25 | 24 | 25 | 23 | 22 | 24 | 24 | 28 |

The simulated 10% day holds 68, 34 and 28 km/h all day. Even free flow is below the real 06:00 motorway and arterial speeds, by 9% and 7%.

## What's blind and what isn't

- **15 May isn't blind.** Report 22 says so: it has been read. May 2019 is tuning data here. I didn't download or read any other 2019 month. The HERE archive holds January to June, and only May was unpacked.
- **Locked and unread:** 31 of the district's 94 sites are locked by report 22's split, `sha256(site + "cars-bench-v1")` per road class, plus sites over 200 m from a v6.4 calibration link. Of those, 4 are in the district. Berlin has 91 locked sites. Their real-against-real floors exist because that doesn't reveal a model. The simulated output includes them, in `site_hour.csv`, and my code doesn't read them. So the benchmark can reveal them.
- **v6.4 demand was fitted to these sensors.** Report 12: 222 of 266 cross-sections sit within 50 m of a station it was fitted to, in 2018 data. I couldn't get the clean plans, and `plans-initial` is post-fit. So the volume check is in-sample even at tuning sites, and only the 4 locked clean sites would be blind.
- **I fitted nothing to the test days.** No scaling, no OD change. Map fixes come from OSM 2019, loops and rule-based lane checks, and I judged them on whether traffic got stuck, not on flows or speeds at sites.
- **Blind in substance:** probe speeds. No fit has used them. v6.4's free speeds came from routing services, and I didn't take them: limits here are OSM's.

## Step 0: the district

**Picked by data.** Among 25, 36 and 49 km² windows on a 1 km grid, the most trusted sites are in this 7 × 7 km box around Tiergarten, Kreuzberg and Schöneberg: 98 sites, then 94 after quality control. No Berlin window has real signal plans, so signals don't separate them. There are almost no motorway sensors anywhere: none here, so the A100's check rests on probes.

**Exit, inputs labelled** (rule 3):

| Input | Label | Source and what's wrong |
|---|---|---|
| Demand | MODELLED, partly fitted | v6.4 10%, experienced plans. 540,377 vehicle legs against 540,373 vehicle trips in the trips file, so all were kept. ×10 gives 5.40 M trips, 104 M km region-wide. Report 03's 4.42 M and about 42.9 M km are the part touching Berlin, against 41.3 M official |
| 100% from 10% | INVENTED | Ten copies with departures ±150 s. Not independent trips |
| Vehicle classes | MODELLED | MATSim's per-agent types: 80% cars, 12% vans, 8% trucks. Lengths estimated, as MATSim's are road-space units |
| Buses, bicycles, people | **Missing** | Report 20's largest gap. Buses run in reality here |
| Network | MODELLED | v6.4's own `sumo.net.xml`, OSM of Jan 2023, patched to Jan 2019 below |
| Lanes | ESTIMATED | OSM of Jan 2019, loops for 5 edges. Bus lanes unmarked. Turn lanes guessed by netconvert |
| Signals | **INVENTED** | 487 controllers from netconvert, actuated, offset 0. Report 11 hasn't landed with a spec. The only real figure I found: one corridor, B1/B5, runs 90, 110 and 100 s cycles by time of day, coordinated ([Senate answer S19-12905](https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-12905.pdf)) |
| Counts, speeds | MEASURED | Detectors, May 2019, hourly. Probes, HERE Traffic4cast, May 2019 |
| Weather | MEASURED | 15 May: 0.1 mm, 13 °C. 16 May had 12.7 mm, and it's still in the floor ([Open-Meteo](https://archive-api.open-meteo.com/v1/archive?latitude=52.52&longitude=13.40&start_date=2019-05-13&end_date=2019-05-17&daily=precipitation_sum,temperature_2m_max&timezone=Europe/Berlin)) |
| Roadworks, events on the day | **Not checked** | I found no source |

## Step 1: frozen before any score

`metrics.py` and the freeze were committed before the first simulated score, and the metric code hasn't changed since (its hash is in `freeze.json`). Bars for real against real are in the scorecard and `floor.md`. The freeze changed twice before any simulated site score: when report 22 arrived, and to apply the existing "nearly empty" rule, after a static route count showed one site with 88 vehicles a day. That second version was on disk before the first score, but was only committed with this report. The floor at the 94 district sites matches `reference-days/berlin-2019` exactly at tuning sites on 15 May: 1,509 site-hours, flow and speed identical. `reference_day.py` itself wasn't run on these outputs, because `metrics.py` measures at the real sensor position, which is what report 22 asks for.

**Virtual detectors:** `cars run --sensors`, on this branch, counts a vehicle's front crossing a point per lane, with spot speed, on the loop's real position, and only the lanes the loops cover. Output is the same hour and definition as the real files.

## Step 2: the map, 10% then 50%, teleports off

Every issue is in `research/truth/berlin2019/` (`map_issues_summary.csv`, `map_fixes_m10.csv`, `step2_map_variants.csv`).

Audit of the cut (MEASURED against OSM): 371 edges with a different speed limit, 172 with a different lane count, 540 under a car's length, 278 lanes with no way on, 96 edges with a bus lane in 2019, 2,112 edges whose OSM way isn't in the 2019 file and so went unchecked. Of the lane differences, 114 have fewer lanes on the 2023 map and 58 more; Kantstraße is the longest case, and Hardenbergstraße has 3 loops on 2 mapped lanes. Of the limit differences, 232 are 30 on the 2023 map against 50 in 2019.

Cars running at the end of each hour, 10% demand. A healthy day peaks near 1,600 and falls to 0:

| Map | 07 | 10 | 13 | 16 | 19 | 23 | Note |
|---|---:|---:|---:|---:|---:|---:|---|
| v6.4 as cut | 1,823 | 2,910 | 6,551 | | | | Locks from 05:00, with 125 cars in the net |
| + 2019 lanes and speeds, chains | 1,515 | 1,749 | 5,968 | | | | |
| + lane feeds | 1,515 | 1,292 | 3,032 | 11,585 | 20,000 | | |
| + **no U-turns** | 1,514 | 974 | 1,171 | 1,912 | 2,717 | 3,210 | Stuck at 13:00 on a 0 m edge |
| + join edges under 7.5 m, not at signals (**m10**) | 1,608 | 1,020 | 1,191 | 1,472 | 867 | 78 | **Finishes** |
| m10, static programs | 1,857 | 1,175 | 1,383 | 1,739 | 1,011 | 91 | Finishes |
| Report 10's 12 m join, per-junction programs | 2,906 | 7,998 | | | | | Worse: broke the Ernst-Reuter-Platz ring |
| Report 19's junction radii and smoothing | 2,167 | 8,000 | | | | | Worse: road pieces shrink to 0 m without its joins |

**Causes, in the order `cars jam` and `cars why` showed them:**

1. **Chains of pieces.** At Potsdamer Brücke, edges of 1–13 m with lane counts 4→2→3 into a signal, left when bike edges were removed. Merged, with 540 edges under a car falling to 56.
2. **U-turns.** 29.3% of vehicles, 55,622 U-turn movements. 34,060 are out-and-backs at a trip's ends, MATSim's link-based activity spot, so those were trimmed. Elsewhere there's a detour or, if there's no path, the trip splits.
3. **Two cars abreast, each wanting the other's lane, on a short road.** Worst seed at 10%: 16 m Rahel-Hirsch-Straße, 580 cars held and 806 vehicle-hours, from a U-turn route. This is an engine gap: `cars` has no swap. Removing U-turns and giving short roads an extra lane feed only make it rarer.
4. **Routes that lanes can't serve.** `cars lanes`: at 3 s per lane change, 14.3% of trips can't be driven lane by lane, 2% after the feeds. At 5 s it's still 21%. Routes through connections closed to their class were being dropped silently, 2.2%: now they use per-class graphs.

**Exit test at 10%:** passed, with 5 edges stopped for over an hour, all at signals. The worst is Reichpietschufer, 7.5 h, on a joined multi-node controller where cars lose 118 s a pass. Coding left: those 5, bus lanes and turn lanes.

**Exit test at 50%: FAILED.** Running at 08:00: 31,527, against 8,240 from 5 × the 10% run. It leaves the 10% curve around 06:00, near Alexanderplatz, Karl-Liebknecht-Straße and Ebertstraße. At this load there are far fewer cars than the roads hold, so it's seeds spreading, not a full city. The recipe says fix this before going on. I report the rest anyway as diagnostics.

## Step 3: capacity without a city

Isolated scenes at dt 1, one seed, `step3_capacity.py`. Bands from report 04. **Exit: FAILED for every driver.**

| Driver | Saturation 50 km/h, 1,800–2,100 | 30 km/h, no band | Motorway per lane, 1,800–2,300 | Jam spacing, 6.5–8 m | Start wave, 16–28 km/h | Drop, 0–18% |
|---|---:|---:|---:|---:|---:|---:|
| main (Krauss) | **1,895** | 1,469 | **2,001** | **7.1** | **20.9** | **14.5%** |
| human, t3/1b36c9cf at f69d694 | 1,500 | 1,200 | 1,503 | **7.9** | **22.8** | −19% |
| human, dt 0.5 | 1,469 | 1,200 | 1,650 | 8.7 | **22.5** | −6% |
| physical default, same build | 1,714 | 1,440 | 1,590 | **7.1** | **17.9** | −26% |

A negative drop means the jam started in the first minutes of the scene, so there was no flow before it to compare with. Those aren't measurements of a drop.

**Give-way, minor road's right turn with random major flow, main:** 436, 261 and 152 vehicles an hour at major flows of 400, 800 and 1,200, against 736, 451 and 277 from Siegloch with HBS's 5.9 s and 3.0 s. **About 57% of the reference.** I didn't get a clean figure for the human driver: its run used even major gaps, which aren't comparable, and the physical default's rerun timed out. With even gaps its minor road took 1,196 vehicles an hour whatever the major flow, which looks like it ignores priority. That needs checking.

**Decision:** dt 1 with main for the map work, because it's the only one with capacity in band, though report 19's point stands that it isn't physical. **At 10%, the human driver has 7,700–8,000 cars running at 08:00 on both m2 and m10, and the physics branch (883f923) 6,200 on m2**, against 1,600 for a healthy day. They can't be judged here until their capacity is in band: 18–25% low on saturation and motorway.

## Step 4: demand, static checks only

Nothing fitted. District cut: 176,236 pieces at 10%.

| Check | Result | Exit |
|---|---|---|
| Vehicle-km on main road classes, in the box, against SVZ 2019 count network | 4.18 vs 4.18 M km. This compares road classes, not the same links | Pass, ≤15% |
| Cordon of the box, against SVZ | 1.32 vs 1.54 M vehicles a day, −14% | Pass, just |
| Sites' total at 63 tuning sites | −6% against real | |
| Sites, one by one | Median ratio 0.96, 37% within ±20%, 6% under half, 5% over double, daily R² 0.31 | Poor, and this is on fitted sites |
| Trip length | Fitted to the same survey | Not tested |
| Peak | MATSim's shape, 07 and 16 against 08 and 15 | Inside ±1 h |

So the amount is right and where it goes isn't. **At full demand, 268–317 of about 8,300 edges carry over 900 vehicles per lane per hour in peak hours**, and 27–37 carry over 1,500, including single-lane tertiary roads at 2,447. No signal can pass that. MATSim's queue model has its own capacities, and these routes never met this map's lanes.

## Steps 5 to 10: not started

The recipe forbids them until step 2 passes. Step 9 was not opened. Demand was never scaled to pass: 10% and 50% are map tests only.

## Where it fails first, and why

Controlled tests at 50% on m10, running cars at 07:30 (5 × the 10% run: 7,015):

| Change | Cars at 07:30 | Reading |
|---|---:|---|
| Base | 19,825 | |
| Static programs instead of actuated | 20,936 | **Not the actuated logic** |
| One program per junction, report 10 | 14,792 | **The largest of these, −25%. Still 2.1 × the 10% level** |
| Give-way capacity moved into band (`impatience` 0.25) | 17,709 | **About 10%. Not the main cause alone** |
| SUMO 1.28, same net and routes, teleports off | 22,515 | **The jam isn't specific to `cars`.** At 07:00 SUMO has 13,116 running with 9,125 halted; `cars` has 11,826 |

I didn't test real signal timing, because none exists for Berlin. Matching SUMO isn't evidence of accuracy (see AGENTS.md); here it only splits inputs from engine.

By road class at 10%: free-flow speeds are slightly below real early morning, and there's no rush hour anywhere. By class on volume at 15 May: primary sites run −22%, secondary +13%, tertiary +26%. That's traffic on smaller roads than in reality, which agrees with reports 03 and 15.

| Rank | Cause | Evidence | Kind |
|---:|---|---|---|
| 1 | Routes ignore lanes and turn rules | 29% of vehicles with a U-turn; took a jam from midday to a finish | Demand and map |
| 2 | Short stubs in the map | 540 under a car; first seed; report 15's Beijing case | Map |
| 3 | No lane swap in the engine | Largest seeds at 10% | Engine |
| 4 | Routes overload lanes; traffic on small roads | Static counts; volume by class; SUMO jams on the same inputs | Demand, step 5 |
| 5 | Give-way capacity 57% of reference | Isolated test; small city effect alone | Driver, step 3 |
| 6 | Human and physics capacity 18–25% low | Isolated tests; lock at 10% | Driver, step 3 |
| 7 | Signal programs invented | No real data. One program per junction gave −25% at 50%; a joined controller lost 118 s a pass | Signals |
| 8 | Buses, people, turn lanes, bus lanes | Not modelled | Reports 16, 20 |

## Next fixes

1. **Lane swap in the engine, then re-run 50%.** It's the only remaining stuck class at 10%.
2. **Take one program per junction into the base map, then fix the seed junctions at 50% with the tools,** starting at `cars jam --trace runs/why5/f.trace`.
3. **Mark bus lanes and turn lanes from OSM 2019,** then re-run `cars lanes`.
4. **Bring the human or physics driver into step 3's bands, including give-way,** before it's tried on a city again.
5. **Step 5 once 50% passes:** re-route on this map's lanes with a main-road preference. That's where the 900+ edges should go.
6. **Get signal evidence:** Hamburg's real cycles and greens, as report 12 proposes, and the Senate's corridor figures.

## For the benchmark

`cars-data/berlin2019/scenario.json` names net, route files, sensors, the freeze and the output format. After a run, `scripts/berlin2019/read_run.py NAME` writes `runs/NAME/site_hour.csv` (site, hour, flow, speed, long, lanes, all sites) and `exit.json`. `step6_probes.py` scores speeds. Probe files stay outside the repo, since the licence doesn't allow sharing.

## Limits and what went wrong

- The GPU lock was held by other batch jobs throughout, so every run was on CPU Vulkan, one seed, dt 1. The load guard killed the 100% morning at 06:41. **No full 100% day was run.**
- MeTS-10's pipeline ran out of memory on the homelab, then the homelab's SSH dropped. I used its join, median and trust filter for the district on the PC, with one change: free flow is each edge's 90th percentile, not its speed clusters. Citywide speeds aren't done.
- Probe speed and sim space-mean speed aren't quite the same measure, and I didn't check them against detectors first (report 22's cross-tracker closure). Motorway probes are thin: 143 edges.
- Results vary between runs of the same map: m2 locked at 14:00 once, and earlier in a rerun on a later engine build. Seeds of this kind are chaotic. One run proves little.
- `trips.csv` pieces mean the cut trips can't be compared with the survey.
