# 16: Input audit. What every scenario is really made of

Checked 2026-11-02. Read from the generating scripts, route files, net files and reports 01, 02, 03, 05, 06, 07, 11 and 15. No GPU. Nobody was contacted. New scripts and outputs are in [scripts-16/](scripts-16/).

## The answer

**No, the trips are not accurate, the signal timings are not accurate, and most of the other 500 things have never been checked.** Erik's doubt is right.

- **No Stockholm scenario has one real signal program, and nobody has found one in Berlin.** Every Stockholm program is netconvert's default: nominal 90 s, offset 0, apart from one nominal 256 s. Berlin's look generated too.
- **No Stockholm scenario has any real origin or destination.** Trips start and end on streets chosen by road length, and the count of trips is whatever a fit to 2016 estimated flows returned.
- **No city scenario here has trucks or pedestrians. None has cyclists, parked cars, weather or grades.** Those are not small approximations. They are zeros nobody chose on evidence.
- **The Stockholm run called "credible" misses measured traffic by far.** New test for this audit, with data its demand never saw: recipe day against measured Årstrafik counts at 860 site-directions. It carries **45% of measured traffic, with 66% hourly error, against a year-to-year floor of 12%. Only 6.7% of busy sites are within ±20%.** The site-by-site morning/evening pattern has correlation 0.04 with reality, so the commute tide is simply absent.
- **Part of why it doesn't lock up is that real signals were deleted.** The recipe net has 457 controllers across a 34×30 km clip. Stockholm municipality alone has 519 real installations.

**Of 94 inputs in the Stockholm recipe, 76 are invented, 18 estimated and 0 measured.** The full count is in [the tally](#tally).

**Scenarios that can currently pass the validation gate: none.** Most can't even be tested, because they have no dated real day. What's measured is mostly the checking data (Årstrafik, toll totals, Berlin detectors, SVZ) and not the inputs. Scenario verdicts are [below](#verdict-per-scenario), then [the top 20](#top-20-inputs-most-likely-to-make-network-results-wrong), [what's indefensible](#what-is-indefensible) and [every input](#every-input-stockholm).

## How to read the labels

- **MEASURED:** observed on real roads, with a source, date and sample.
- **ESTIMATED:** derived from real data through a model or by people, like OSM tags, an authority's estimated flows, or a fit.
- **INVENTED:** a default, a guess, a value picked because the run looked better, or left out. **INVENTED (zero)** means the thing exists on real streets and we simulate none of it.

"Network effect" quotes a controlled test only if one exists. "None" means nobody has tested it, and any size given is a bound or my opinion. Most tests measure teleports, not agreement with reality, because the Stockholm tests were asking "does it lock up". A change that reduces teleports can make the scenario less true, and that's what happened with signals.

## New measurements in this audit

| What | Result | Grade | File |
|---|---|---|---|
| Recipe day `v2_day2` against Årstrafik, all non-blind rows: 860 site-directions, 20,640 site-hours. The `test` rows stay untouched. | Simulated/measured **0.453**. WAPE **65.7%**. Hourly GEH<5 on 41.9%. Median busy-site ratio 0.44, 10th to 90th percentile 0.16–0.79. **Only 6.7% of 493 busy sites within ±20%.** | Measured against modelled | [json](scripts-16/recipe_vs_arstrafik.json) |
| Same, by road class | Motorway 0.345, secondary 0.377, primary 0.439, unclassified 0.456, residential 0.477, tertiary 0.523, trunk 0.653 | Same | Same |
| Same, share of day by hour | 08:00: 9.7% simulated, 7.2% real. 17:00: 10.1% against 7.2%. 15:00: 5.2% against 7.7%. | Same | Same |
| Morning peak over evening peak, per site | Real 0.51 / 0.89 / 1.52 at 10/50/90th percentile. Simulated 0.87 / 0.96 / 1.07. **Site-level correlation 0.04.** | Same | Same |
| Heavy vehicles in Årstrafik 2023–25, 2,961 directional records with at least 5 measurement days | **3.83% of flow.** Site median 4.0%, 90th percentile 8.0%. Scenarios have 0%. | Measured | [json](scripts-16/arstrafik.json) |
| Mean speed against the net's limit, 1,456 records joined by site to edge | Limit 30: 27.4 km/h. 40: 35.2. 50: 42.3. 60: 52.4. 80: 67.7. The 85th percentile sits near the limit (32.7, 42.0, 48.7, 60.8). All-day figures that include some congestion, and Essingeleden has no speeds. | Measured | Same |
| Signals per net, whole clip | Old 1,922 controllers (report 07). **Recipe n7: 457.** v5: 903. One n7 program has a nominal 256 s cycle. All others are 90 s. | File census | [json](scripts-16/census_nets_big.json) |
| v2_c4 route file | 790,967 vehicles, one vType, 4,009 origin edges, 1,000 routes hold 52%, top 100 origin edges 22%, 10.6% of vehicles still have an immediate `edge,-edge` reversal | File census | [json](scripts-16/census_routes.json) |
| Charlottenburg and Mitte cut-outs | 155,430 of 330,358 trips (47%) and 180,360 of 357,934 (50%) carry `departLane=best departSpeed=max`, which the uncut BeST trips don't. I read these as trips cut at the boundary; I didn't trace them one by one. | File census, reading is my opinion | Same |
| I-80 demand by hour | 2,770 / 5,200 / 8,302 / 5,200 / 2,770. **Exactly symmetric.** That's a designed curve, not a recorded afternoon. | File census | Same |
| `cars` and bus stops | `demand.rs:536-538` and `:638` count `<stop>` and ignore it. **LuST's 2,240 buses never stop at their 37,376 scheduled stops.** Persons are dropped the same way. | Code read | `crates/cars-core/src/demand.rs` |
| SUMO on LuST, local partial run (1.28 assumed, config not traced) | 18,011 teleports at 17:00. At 19:21, when the file ends: 60,901 running, 36,143 teleports. | Modelled | `truth/assign/runs/lust_sumo_summary.xml` |
| Bologna's origin, from the authors' slides | 636 loops, 5-minute flows, 11–13 Nov 2008, about 90 faulty, no vehicle classes, one hour, manual corrections. Signal plans from the city, adaptation switched off. Authors' stated limits: one hour, too small for rerouting, needs warm-up. | Provider claim, slides only | [slides](https://eclipse.dev/sumo/documents/2014/Presentation_open_scenarios_LauraBieker.pdf) |

**Correction to report 02:** `cars` ignoring connection `allow` and `disallow` is fixed, commit `76719b4`, 2026-11-01 18:32. But the recipe's final day finished at 17:25, so it ran on the older code. Its routes were built legal, and teleports or wrong-lane moves could still differ. Not rerun.

## Verdict per scenario

"Gate" is the eight checks in [VALIDATION-GATE.md](../VALIDATION-GATE.md). None of these has been compared on a real dated day, and most can't be.

| Scenario | Inputs in plain words | Gate today | Verdict |
|---|---|---|---|
| **Stockholm old demand** (`stockholm60` on `stockholm.net`) | Random walks fitted to 2016 estimates, wrong by construction, 40% of real cordon traffic, 290,352 teleports. WAPE 79% on the blind rows, measured by the assign run. | Fails stuck, volume, day shape, speed | **Drop.** Keep only the file as a gridlock regression test, labelled "synthetic stress case". No results from it count for anything. |
| **Stockholm recipe** (`n7_ramps` + `v2_c4`) | Invented trips, invented signals, a net tuned until teleports fell, 60% demand. 2,449 teleports. | Passes nothing it was compared on: **volume fail (0.453), day shape fail, trips untested, speed untested but flat 42–44 km/h all day is implausible against 42.8% TomTom congestion.** At 100% it's `network_suspect`: 855,186 teleports, 149,127 collisions, not converged. | **Keep as "synthetic Stockholm-shaped engine benchmark at 60% load, generated signals".** Speed and regression only. **Not a Stockholm result, and not a human baseline.** Report 09e's Stockholm comparison must carry this label. |
| **Stockholm v5_inventory** | Best net we have: real signal positions (register), turn lanes, bus lanes closed. Programs still invented. No completed assign run: `stockholm_v5s` has only checks and init. Teleports far higher: 631,888 on a day. | Fails stuck | **Keep as the base net for a future real scenario. No results count until real plans go in at the key sites.** Don't choose against it because it locks up: that lock-up is at least partly honest capacity. |
| **Berlin BeST** | MATSim-derived trips, half of observed traffic, generated signals, hand-edited where SUMO jammed, OSM from 2020. | Volume fail (0.50–0.62), day shape fail, stuck: 23,715 teleports in cars vs 2,090 SUMO | **Keep as SUMO parity and throughput benchmark only**, as report 03 decided. Label: "synthetic Berlin benchmark, about half of observed traffic". |
| **Charlottenburg, Mitte** | Cut-outs of BeST, with about half their trips starting at the cut at full speed. | Same as Berlin, plus boundary artefacts | **Keep as small SUMO parity cases only.** Nothing else. Drop if a smaller parity case does the job. |
| **LuST** | Synthetic 2015 scenario, valid on SUMO 0.26 by its authors' own statement. Gridlocks in modern SUMO too. In `cars`, buses don't stop. | Fails stuck: 208,074 of 288,250 unfinished with teleports off | **Benchmark only, and only after bus stops work or the buses are labelled as non-stopping.** Don't calibrate anything on it. Otherwise drop. |
| **Bologna joined** | The most measured scenario here: real 2008 loops and city signal plans. But one hour, cars only, adaptation off, offset 0 everywhere, 18 years old, no held-out data at hand. | Can't be tested: no independent real data held locally | **Keep as a small benchmark and rehearsal case, labelled "2008 peak hour reconstruction, not validated by us".** The thesis's word "validated" is not supported by anything I could open. |
| **I-80 Davis** | Real corridor shape, demand "based on PeMS" with no dates stated, a symmetric made-up looking curve, trucks removed by us. **Not the NGSIM I-80 in Emeryville.** | Not tested | **Keep as benchmark. Best candidate here to become a real test:** no signals, and PeMS has dated flow and speed. Rebuild from one dated PeMS day with trucks back. |
| **Ring** | Invented 4 km loop at 120 km/h and 50 veh/km after a published simulation setup. | Not applicable | **Keep as a stability unit test.** No claim about real traffic. |
| **Two-signal grid and test junctions** | Hand-written or generated, for comparing with SUMO. | Not applicable | **Keep as unit tests.** No claim about real traffic. |

**The honest overall state:** `cars` matches SUMO fairly well on identical inputs, and that's the only validated claim. Nothing shows either of them matches a real city on these inputs.

## Top 20 inputs most likely to make network results wrong

Ranking is my opinion, based on the evidence column. "Test" means a controlled run exists. Most tests are of teleports, so they rank how much the simulator reacts, not how far from truth it is.

| # | Input | Status now | Evidence of size | Real data that replaces it |
|---:|---|---|---|---|
| 1 | **Origins and destinations** | INVENTED in Stockholm, modelled in Berlin | Same counts, different pools: 2.9 M or 1.32 M trips. Toy with known truth: a uniform prior fits counts to 41% with pair correlation 0.25 (report 06 E5). Berlin median link off ×2.0. | Toll passages by postcode, Telia OD, Sampers, SCB commuting (report 05 drafts 2, 7, 11, 12). MATSim v6.4 for Berlin. |
| 2 | **Total demand level, and scaling it to get a run** | INVENTED 60% in Stockholm; 50% of real in Berlin | 100/80/60/40% gives 70,595 / 28,078 / 10,131 / 3,058 teleports by 10:00. Measured: 0.453 of real at sites. | Årstrafik and toll totals fix the level. No scaling allowed (report 15, #4). |
| 3 | **Signal programs, cycles, offsets, actuation** | INVENTED in Stockholm, Berlin, LuST | 51 of 103 stuck heads wait on red on v5, against 5 of 116 on base (report 02). No test against real plans exists anywhere. Practice: every project claiming realism used real plans for at least part of the net (report 15). | Trafikkontoret plans (report 05 draft 3), starting at 2 junctions. Melbourne sheets. |
| 4 | **Signal positions and grouping** | ESTIMATED OSM; n7 deletes them; v5 MEASURED register | Day teleports 9,558 on n7-like against 631,888 on v5. 457 controllers against 519 real in the city alone. **Low teleports here are partly the absence of signals.** | City register, already open, plus NVDB and state-road sources. |
| 5 | **Route choice** | INVENTED method, not converged | Pool to shortest paths −94%. Feedback −89%, measured at 60%. At 100%: gap 18–20%, 42% unseen. No real route ever compared. | INRIX trips (report 05 draft 5), other GPS sources (reports 03, 04). |
| 6 | **Departure times, and who peaks when** | INVENTED | Site AM/PM correlation 0.04. Simulated flow at 08:00 is 9.7% of day against 7.2%. Flat profile −18% in an older run. Same profile for every route, so no tide. | Årstrafik per site for flow shape. Toll passages per minute for timing. RVU for trip starts. |
| 7 | **Count targets the demand was fitted to** | ESTIMATED, 2016 | Measured over estimated: median 0.97, IQR 0.75–1.19, 39% off by more than 30%, sum 0.873 (report 01). | Årstrafik, measured and already downloaded, keeping a held-out share. |
| 8 | **Junction capacity from model and step** | INVENTED defaults | Krauss saturation changes 15% between dt 1 and 0.1 (report 04). Overstates motorway capacity by at least 19%. Accel −20% teleports (report 02). Queue wave unstable at dt 1. | Saturation flows at real sites. TRVMB design values as a first bound. |
| 9 | **Trucks, vans, buses** | INVENTED (zero) in Stockholm; all one type in Berlin; buses without stops in LuST | Real heavy share 3.8% Stockholm, 8.3% Berlin. Python only: 10% 40 t trucks drops saturation 1,861 to 1,507, a worst case (report 11). **No city test.** | Årstrafik heavy share by hour and site. SL GTFS. Vans have no source yet. |
| 10 | **Short links and junction joining** | ESTIMATED OSM through netconvert | 94% of night teleports at junctions touching a link under 7.5 m. Join flags −40% to −71%. 745 signal approaches on stubs. | Junction-level hand fixes where real plans go in. NVDB `Korsning`. |
| 11 | **Through traffic, commuters and the map edge** | INVENTED shares | Berlin motorway ratio falls from 0.56 to 0.06 toward the edge. Stockholm's portal volume is whatever the fit returns. Nothing queues outside the map. | Toll passages, Telia, Sampers or Dynameq sub-area. |
| 12 | **Turn lanes and lane-to-movement connections** | INVENTED in recipe, ESTIMATED in v5 | `--osm.turn-lanes` 1,721 to 4,202 teleports. Only 1,161 of 435,105 ways are tagged. | NVDB `AntalKörfält2` lane codes. |
| 13 | **Bus lanes** | Recipe open to cars, wrong; v5 closed | 1,721 to 2,692, and 849 to 1,934. Fit still loads those lanes. | NVDB `Kollektivkörfält`, OSM already honoured with `--osm.lane-access`. |
| 14 | **Pedestrians at crossings** | INVENTED (zero) | **No test.** 12,674 crossing nodes in the OSM clip, 3,861 positioned push buttons in the city register. No turning car ever yields to anyone. No phase has a walk call. | City pedestrian counts if any. Push-button positions show where. |
| 15 | **Cyclists, parked and stopping vehicles, deliveries** | INVENTED (zero) | **No test.** OSM parking tags exist on thousands of ways. Service roads removed, so every trip starts on a through street at full speed. | OSM parking tags for a first bound, city cycle counts. |
| 16 | **Motorway merges, ramps and managed lanes** | INVENTED flags, MCS not modelled | Ramp fix −14%, and it was chosen on outcome. Real Essingeleden about 72% matched in full fit by my arithmetic. | MCS radar, NVDB ramp lengths. |
| 17 | **Free-flow speed** | Limit × N(1, 0.1) | Real all-day means 10–15% below limit (new, above). Default 100 km/h where `maxspeed` is missing on secondary (57 urban edges at 75+). **No test.** | NVDB speed limits, Årstrafik speeds, KoDa off-peak bus runs. |
| 18 | **Right of way** | ESTIMATED from road class | 1,877 give-way and stop signs not read. 119 at `right_before_left`. 62 right-before-left junctions with a secondary-or-higher approach. **No test.** | NVDB `Väjningsplikt`, `Stopplikt` (needs key). |
| 19 | **Turn speeds and gap acceptance** | INVENTED defaults | Python: turn at 6.13 m/s gives 1,619 veh/h, at 4.66 m/s 1,380. Netconvert's 5.5 m/s² against 3.1–3.6 measured in the US. Roundabout gap 2.95 s measured; SUMO `jmTimegapMinor` 1 s. **No city test.** | rounD, inD fits; TRVMB. |
| 20 | **Teleport and collision settings** | INVENTED 120 s and 20 s, copied from BeST | They hide what we're measuring: 17,910 stuck trips become 0 in a toy (report 06). With teleports off the human driver has 114,298 of 167,295 stuck. | Not data. Gate rule: teleports off. |

Just below the line: lane counts, map-versus-traffic dates, weather, grades, seeds.

## What is indefensible

Said plainly.

1. **Calling any of this Stockholm.** Trips start where road length says, at a distance a kernel says, in hours somebody typed into `retime.py`.
2. **Choosing net flags because teleports fell.** `--tls.discard-simple`, `--tls.join`, `junctions.join-dist 15` and `ramps.min-highway-speed` were picked by outcome. So was `accel` 2.6. Report 02 says so, but the recipe then got used as "the corrected demand". BeST did the same: its net was hand-edited on a teleport list.
3. **60% demand.** It's a stated cost in report 02 and a violation of "never scale demand or capacity to pass" in report 15. A run at 60% that doesn't lock up says nothing about a city at 100%.
4. **Comparing AV control to generated signals on Stockholm and reporting the gain or loss** (report 09e, "worse than signals does not hold"). The baseline is invented, and the gate now says no AV result counts. Report 09e does disclose the generated timing. The disclosure doesn't rescue the comparison.
5. **The 97% cordon figure as validation.** A hand-drawn polygon, full-scale planned demand, no station data. The demand actually run gets 59%. Report 02 warns about this, and people will still quote it.
6. **"Lane counts hold against OSM."** That's the net against its own source. No official comparison has ever been made.
7. **Thesis wording, as far as these scenarios go.** Bologna "validated" and "heterogeneous demand": I could only find street-network checks against aerial images in the slides, and our route file has one vehicle type and no buses. I-80 "realistic demand profile": the curve is exactly symmetric, the dates are unstated, and we removed the trucks. Bologna also ran with no warm-up, against its authors' own warning. Reading the paper itself could soften the first point; I only opened the slides. Report 10 already covers the thesis's other problems.
8. **The human driver as a baseline.** Fitted on US and German trajectories only, with trucks and buses excluded, and it isn't merged. On Stockholm and Berlin mornings with teleports off, 68–72% of cars are stuck at 2.5 m/s. Those runs can't tell driver errors from input errors, because the inputs are this bad.
9. **Annual-average data as "a day".** Årstrafik and Trafikflöde are annual weekday means. The gate requires a real measured day. Stockholm has no dated source locally, so the gate can't even be attempted there yet.

## Every input: Stockholm

Columns apply to the recipe (`n7_ramps` + `v2_c4`). Differences for the old scenario and `v5_inventory` are in the text. `v5_inventory` demand is the same method rebuilt on that net.

### Who drives, from where to where

| # | Input | Label | What it is: source, date, sample | How checked | How wrong | Network effect, test | Replace with |
|---|---|---|---|---|---|---|---|
| S1 | Origins | INVENTED | 6,000 origin edges drawn by road length on residential, living street, unclassified, tertiary (`sthlm_assign.py:47-52`). Old: ends of random walks. No population, jobs or schools. | Never against OD. | Unknown. Road length isn't activity: a suburb's street and a city block weigh the same per metre. | Toy: bad prior with fit correlation 0.25 (06 E5). No real test. | SCB BEF301/302, RVU, toll postcode data |
| S2 | Destinations | INVENTED | Same draw, `exp(-d/6 km)`, over 800 m. 10 per origin. | Kernels 3, 6, 12 km give 1.21–1.37 M trips. Not against OD. | Unknown. Kernel value is a choice. | Trip total only. Not on congestion. | Same |
| S3 | Trip count | ESTIMATED | 1,318,869 full, output of a fit. Old 2,919,242 from the same counts. | Municipal vkm by division, cordon. | Factor 2.2 between pools proves it isn't identified. | See S6. | Toll totals plus driver OD |
| S4 | Trip lengths | INVENTED | Mean 8.04 km, median 6.86 km, p95 17.8 km. Old mean 2.43. | RVU only says half of work journeys are 5–20 km, all modes. Not checked on car drivers. | Unknown. | Pool shape: thinning to equal vkm −79%, route shape a further −71% (02). | RVU driver tables, Telia, INRIX |
| S5 | Fit target flows | ESTIMATED | `Trafikflöde_Motorfordon`: 16,698 features, all `Skattad`, 99.55% updated 2016, ÅMVD. | Against measured 2024–25, 509 site-years (01). | Median 0.97, IQR 0.75–1.19, 39% off by >30%. | None directly. | Årstrafik, measured, 2023–25 |
| S6 | Demand scale | INVENTED | 0.6 × fit, chosen so the run survives. | Cordon 59%. Årstrafik 0.453 (new). | At least 40% low at the checked level. | 100/80/60/40%: 70,595 / 28,078 / 10,131 / 3,058 (02). Assign at 100%: 855,186 teleports. | No scaling. Fix net and signals instead |
| S7 | Count-to-road matching | ESTIMATED | Nearest edge within 60 m and 35°, 50/50 direction split, 856 features with one matched direction get all the flow. Recipe keeps same-name, 1,275 edges dropped, 839 uncovered. | Name audit (02). | Old: 4,117 of 31,654 matches join a different street name. | Motorways 55% of target in old fit. | Årstrafik has direction and NVDB key. Join on that |
| S8 | Fit method | INVENTED | Multiplicative update, 300 iterations, no prior. | Algebra: equal totals are built in (02). | Toy: makes OD worse as fit improves, correlation 0.70 to 0.57. | 06 E5 toy only. | Fit with prior pull, held-out sites |
| S9 | Vehicle count check at cordon | MEASURED target, INVENTED polygon | 8,420,500 passages, 21 charged days, Sep 2024. Polygon drawn by hand, 139 edges. | Kernels 92–106%. | "About right" for full fit. Essingeleden 58,833 in charged hours against about 80,000 from Årstrafik by my arithmetic (54,000 per direction × 2 × 0.76). | Not an input. | Station coordinates from Lastkajen, per-station toll data |
| S10 | Route set, old | INVENTED | Speed-weighted random walks. 46.45% of vehicles have an immediate reversal. | Census (02). | Shortest paths with same ends 39% shorter. | −94% teleports (02). | Drop |
| S11 | Route set, recipe | INVENTED | 62,089 duarouter-like paths on free-flow cost, 16,725 used, 1,000 hold 52%. 10.6% of vehicles still reverse. | Never against a real route. | Real: 13.5% of commutes follow exact shortest path, about half lose under 30 s (06). | Not tested against reality. | GPS routes |
| S12 | Route feedback | INVENTED | 1/2, 1/3, 1/4 of vehicles moved to current best on 06–10 times, then 1/4 on 06–21. | Assign at 100%: gap 18–20%, not converged. | Crude and not an equilibrium, as report 02 says. | −89% at 60%. In a jam it raised teleports (02). | Report 06 loop, on real demand |
| S13 | Congestion tax in route choice | INVENTED (zero) | Cost has no toll. Real tax cut cordon traffic about 20% in 2006 (04). | Not checked. | Moves traffic across the cordon and to Essingeleden. Size unknown. | None. | Tax as cost in routing |
| S14 | Departure hour within a day | INVENTED | 12-hour weights typed in `retime.py`, same in `sthlm_pool.py`. | Against Årstrafik, new. | 08:00 flow 9.7% vs 7.2%, 17:00 10.1% vs 7.2%, 15:00 5.2% vs 7.7%. | Flat −18%, older routes, not rerun (02). | Toll per minute, Årstrafik |
| S15 | Band totals (06–18, 18–22, 22–06) | ESTIMATED | From target layer; 76/18/6 if missing. | New: real 76.2/15.9/7.9 on 1,377 busy records. | Close, and it's the one thing that matches. | None. | Årstrafik |
| S16 | Direction tide | INVENTED | Same hourly weights for every route. Bands fitted separately. | New: site AM/PM correlation 0.04. | Real spread 0.51–1.52, simulated 0.87–1.07. **No inbound morning or outbound evening exists.** | None. | Toll passages by direction and time |
| S17 | Tours, return trips | INVENTED (zero) | Every trip is independent, nobody goes home. | Not checked. | Morning and evening OD have no link. | None. | Activity model |
| S18 | Exact departure second | INVENTED | Uniform within an hour, which gives visible steps (02). | Seen in running curve. | Small, except jumps: 05→06 demand ×6.2, real flow ×3. | None. | Real profile by 5–15 min |
| S19 | Weekday and season | ESTIMATED | ÅMVD, annual non-holiday Mon–Fri mean. | Definition read. | No season. Daily variance unknown, year-to-year 12.4% floor. | None. | One dated day |
| S20 | Depart lane and speed | INVENTED | `departLane=best departSpeed=max`. Cars appear on the street at full speed. | No. | Hides start-up and pull-out. | None. | Driveway model, or start at low speed as LuST does |
| S21 | Arrival | INVENTED | Trip ends on an edge. No parking search, no pull-in. | No. | Unknown. | None. | Parking model only if a test says it matters |
| S22 | Trip start location class | INVENTED | `highway.service` removed from the net, so car parks and many garages have no link. | Build flags read. | Unknown. | None. | Keep service roads where they connect |

### Who is missing

| # | Input | Label | What it is | How checked | How wrong | Network effect, test | Replace with |
|---|---|---|---|---|---|---|---|
| S23 | Vehicle mix | INVENTED | One vType, `passenger`, 5 m. | New census. | Årstrafik heavy 3.83%, up to 8%+ at sites. | Python: 10% 40 t trucks −19% saturation (11). No city test. | Årstrafik heavy share |
| S24 | Trucks | INVENTED (zero) | None. | As above. | Physics fitted only for cars; trucks excluded (05). | Same. | Types from report 11, tested |
| S25 | Vans, deliveries, service | INVENTED (zero) | None. Årstrafik's "tunga" doesn't include vans. | No. | Unknown. Berlin's MATSim authors name commercial data as weak. | None. | No source yet |
| S26 | Buses | INVENTED (zero) | None loaded. Even if loaded, stops are ignored. | Code read. | SL volume not extracted. Berlin: +1 point in site ratio, 277,000 km/day (03). | None in Stockholm. | SL GTFS through Trafiklab key, plus stop support in engine |
| S27 | Taxis | INVENTED (zero) | None. | No. | Unknown. | None. | KTH iMobility (report 05) |
| S28 | Through traffic | INVENTED | Portal candidates: `src`×5, 20% chance of a sink per origin. Fit sets volume. | Not checked. | Unknown. Berlin's lost cross-boundary trips are half its motorway problem. | None in Stockholm. | Toll, Telia, Sampers |
| S29 | Commuters from outside | INVENTED | Same portals. No portal has measured inflow. | Not checked. | Unknown. | None. | Portal counts from Årstrafik and TMS |
| S30 | Pedestrians | INVENTED (zero) | `cars` drops persons. Net removes crossings. OSM tag lines: 12,674 `highway=crossing`, and `crossing=` 4,486 uncontrolled, 3,328 marked, 2,514 signal. | Tag count, new. | Turning capacity downtown could fall a lot. Size unknown. | **None.** | Pedestrian flows, or a yield probability tested as a bound |
| S31 | Cyclists | INVENTED (zero) | Removed. OSM has 2,124 `cycleway` tags and 7,695 `cycleway:*`. | Tag count. | Strongly seasonal in Stockholm. Unknown. | **None.** | City cycle counts |
| S32 | Parking and stopping on street | INVENTED (zero) | None. OSM `parking:left/right/both` lines: 4,910 / 7,120 / 5,701. | Tag count. | Lanes blocked by double parking, loading, pull-outs. Unknown. | **None.** | OSM tags as a first test; field checks |
| S33 | Bus stop blocking | INVENTED (zero) | 4,513 OSM bus stops, none modelled. | Tag count. | Curbside bus stops block a lane. Unknown. | **None.** | GTFS plus stop support |
| S34 | Trams, level crossings | INVENTED (zero) | `keep-edges.by-vclass passenger` removes rail. | Build flags. | Local. | None. | OSM |
| S35 | Emergency vehicles, incidents, breakdowns | INVENTED (zero) | None. | No. | Real days have them. Gate needs an incident-free day. | None. | Pick clean day |

### The map

| # | Input | Label | What it is | How checked | How wrong | Network effect, test | Replace with |
|---|---|---|---|---|---|---|---|
| S36 | Road network | ESTIMATED | OSM clip, newest edit 2026-10-23, 435,105 ways. Volunteer-made. | 20 sites by 0.5 m aerial, by eye (07). | Layout mostly right at those sites. Lane level not checked. | None. | NVDB |
| S37 | Map date against traffic date | INVENTED pairing | Map Oct 2026. Fit flows 2016. Toll 2024. Årstrafik 2023–25. Aerial June 2025. | Dates read. | A decade of change, Slussen and Norrtull under rebuild. | None. | Freeze one date |
| S38 | Lane counts | ESTIMATED | OSM `lanes`: motorway 99.7%, primary 87%, secondary 79%, tertiary 54%, residential 3%. Rest default. | Only against its own source (07). | 188 major edges with false drop, 16.8 km. | None. | NVDB `AntalKörfält2` |
| S39 | Turn lanes | INVENTED (v5 ESTIMATED) | Recipe doesn't read arrows, so all lanes guess. v5 reads 1,157 ways. | Tags against net (07). | 205 vs 406 approaches with turn-only lane. | 1,721 to 4,202 (02), which is a sign of bad data handling, not proof of truth. | NVDB lane codes |
| S40 | Lane-to-turn connections | INVENTED | Netconvert's guess. 478 stranded lanes. | Census. | Local bottlenecks. | None apart from S39. | NVDB, hand fixes |
| S41 | Turn bans | ESTIMATED | OSM relations. NVDB 504; 163 match a movement; 116–122 remain open. | Sampled 8 (07). | No exemptions known. | None. | NVDB with exemptions |
| S42 | Bus lanes | INVENTED (v5 ESTIMATED) | Recipe opens 293 tagged edges to cars. v5 honours them. | Sanity script, aerial at one site. | Adds capacity that doesn't exist. | 1,721 to 2,692; 849 to 1,934 by 10:00. One day run before the last round goes the other way, 9,558 to 8,411 (02). | NVDB `Kollektivkörfält` |
| S43 | Speed limits | ESTIMATED | OSM `maxspeed` on 33,071 ways. Missing gets 100 km/h secondary, 80 tertiary. | 57 urban edges at 75+ (07). | No official comparison. | None. | NVDB `Hastighetsgräns`: city says NVDB layers go away autumn 2026, so download now |
| S44 | Free-flow speed | INVENTED | Limit × normal(1, 0.1), SUMO default. | New: mean 10–15% below limit, all-day. | Likely too fast in cities. Size unknown. | None. | Årstrafik, off-peak bus runs |
| S45 | Junction type | ESTIMATED | Class and speed rule. 22,321 priority, 10,545 right-before-left, 485 signal nodes in n7. | Census. | `right_before_left` is the Swedish default, but class rule is a guess. | None. | NVDB |
| S46 | Give way and stop signs | INVENTED | 1,770 + 107 nodes not read. | Report 07. | 119 at right-before-left junctions. | None. | Read the tags; NVDB |
| S47 | Roundabouts | ESTIMATED | `--roundabouts.guess`. | By eye. | Looked right. Priority rule default. | None. | NVDB `Cirkulationsplats` |
| S48 | Junction geometry | ESTIMATED | Netconvert from centrelines. 15 shapes over 60 m. | By eye, 0.5 m. | Internal paths not measured. | None. | Lane-level sources if any |
| S49 | Short links | ESTIMATED artefact | n7 4,559 under 7.5 m, base 5,136–5,388, 745 signal approaches. | Census. | Not real road pieces. | 94% of night teleports (02). | Merge by hand at key sites |
| S50 | Junction join distance | INVENTED | 15 m chosen by outcome. | Teleports. | Unknown. | −11% at noise limit (02). | Plans |
| S51 | On-ramps | INVENTED | `min-highway-speed 16.6`, `ramp-length 200`. | Yielding ramps 34 to 9. | No ramp checked on the street. | −14% (02). | NVDB, aerial |
| S52 | Managed motorways | INVENTED (zero) | MCS variable limits, lane control not modelled. | Not checked. | Changes breakdown. | None. | MCS archive |
| S53 | Grades | INVENTED (zero) | No z in any net file (new census). | Surface model: 52% of km over 3% as an upper bound (11). | Not flat. | Python: −3% at +3%, with trucks another −20% (11). No city test. | National height model |
| S54 | Tunnels, levels | ESTIMATED | OSM layers. | By eye at 7 sites. | Looked right. | None. | NVDB |
| S55 | Road works | INVENTED (zero) | None. | Aerial shows work sites at 3. | Local, large. | None. | Dated network |
| S56 | Removed roads | INVENTED | `highway.service`, `pedestrian` and small components removed. | Flags. | Removes alternatives and arrows' targets (07). | None. | Keep and test |
| S57 | Map edge | INVENTED | Rectangle 34.4 × 30.5 km. 50 sources, 48 sinks, not all real portals. | Census (02). | No queues outside. No alternative outside. | None. | Parent model, wider net |

### Signals

| # | Input | Label | What it is | How checked | How wrong | Network effect, test | Replace with |
|---|---|---|---|---|---|---|---|
| S58 | Positions | INVENTED by deletion (old ESTIMATED, v5 MEASURED) | n7 457 controllers. Old 1,922, 95% of nodes real. v5 register: 10,301 lanterns, 519 ids, undated, city only. | Register match (07). | n7 misses real signals. How many in n7 specifically wasn't counted; a close variant left 238 installations without a controller. | 498 vs 13,444 on same demand (02). | Register plus state-road data |
| S59 | Grouping | INVENTED (v5 MEASURED) | Base 2.5 controllers per installation. v5 0.95. | Sanity script. | Independent fragments at one junction. | Most of the damage comes from joining under generated programs (02). | Same |
| S60 | Phases | INVENTED | Netconvert. Top patterns 42-3-42-3 (201), 38-3-6-3-37-3 (52). | Census. | No relation to real stages. | No real comparison. | Plans |
| S61 | Cycle | INVENTED | 90 s nominal, one at 256 s. Real corridor 85 and 100 s, handbook 70–85–100. | One corridor document. | Near in number, wrong in meaning. | None. | Plans |
| S62 | Greens | INVENTED | Generated, limits 5–50 s mostly. | Census. | On the base net, 82-3-5 on 1,146 controllers means up to 50 s green with no walk call (07). | None. | Plans |
| S63 | Offsets | INVENTED | All 0. | Census. | No coordination exists. Real corridors have it. | **None.** | Plans |
| S64 | Actuation | INVENTED | SUMO's logic, loops placed by rule. Real: LHOVRA at isolated signals (handbook). | Code read. | Different behaviour. | Fixed vs actuated +3%, between two invented things (02). | Plans plus detector layout |
| S65 | Time-of-day plans | INVENTED (zero) | None. Real clock switching at one corridor. | Document. | Peak capacity wrong. | None. | Plans |
| S66 | Yellow, all-red | INVENTED | 3–4 s generated. Driver response untuned: real stop threshold 5.1 s from line (05). | No. | Small per cycle. | None. | Plans, report 05 |
| S67 | Walk phases, push buttons | INVENTED (zero) | None. Register has the buttons. | Register. | Cuts green on real calls. | **None.** | Plans |
| S68 | Bus priority | INVENTED (zero) | None. Whether Stockholm's signals use it wasn't checked. | No. | Unknown. | None. | Plans |
| S69 | State-road signals | ESTIMATED | OSM only. Register is city only. Roslagstull: OSM and NVDB yes, register nothing. | By eye (07). | Unknown who runs them. | None. | Trafikverket |
| S70 | Missing signals | ESTIMATED | 41 register installations with no OSM signal, for example Norrbro. | List (07). | Unsettled. | None. | Street check |

### Drivers

| # | Input | Label | What it is | How checked | How wrong | Network effect, test | Replace with |
|---|---|---|---|---|---|---|---|
| S71 | Car-following model | INVENTED for humans | Krauss, SUMO port. | Replay: 5.43–6.16 m spacing RMSE vs 4.00 best (05). | Wave speed 31–59 km/h at these defaults, real 33.7. | Not at city level. | Human model after gate tests |
| S72 | accel | INVENTED | 2.6 (old 1.5). SUMO default. Picked after it reduced teleports. | Against trajectories: most real driving far gentler (05). | Both may be wrong. | −20% and −8% (02). | Report 05, 11 |
| S73 | decel | INVENTED | 4.5. | Real yield rarely above 2 m/s² at yellow (05). | Large for comfort. | None. | Report 05 |
| S74 | sigma | INVENTED | 0.5. | Saturation changes with step because of it (04, 11). | 15%. | Python and small nets. | Replace model |
| S75 | tau | INVENTED | 1 s. | Real time gap median about 2 s, p5 0.8–1 (05). | Capacity likely high. | Motorway overstated at least 19% (04). | Report 05 |
| S76 | Length and minGap | INVENTED, happens to match | 5 + 2 m. Real jam spacing 6.96 m Braunschweig, 7.43 m TRVMB. | 04. | Good, for cars only. | None needed. | Keep |
| S77 | Saturation headway outcome | INVENTED | Result of the above. | Real about 2.0 s, 2.7 s lost (05). Design 1,900 veh/h. | Model range 1.62–2.60 s. | Python only at city scale. | Fit |
| S78 | Heterogeneity | INVENTED | speedDev only. | No. | Spread matters for capacity. | None. | Per-vehicle gaps (05) |
| S79 | Lane changes | INVENTED | LC2013 port, instant. Real 5.1–5.6 s; 35% of US congested changes pass SUMO's safe gap. | 05. | Merge and weave capacity. | 55% of recipe teleports are wrong-lane. | Report 05 gates |
| S80 | Gap acceptance | INVENTED | `jmTimegapMinor` 1 s. Real roundabout 2.95 s. | 05. | Side-road capacity too high. | None at city scale. | rounD, TRVMB |
| S81 | Turn speed | INVENTED | netconvert 5.5 m/s² average. 38% of internal lanes above 5.5 at lane speed. Real peaks 3.1–3.6 m/s², US. | 07, 11. | Turn capacity 15% in Python. | No A/B yet. | `--junctions.limit-turn-speed 3` test |
| S82 | Human model | ESTIMATED | US and German trajectories, cars only, lag seen on held-out data. Not merged. No Swedish data. | Replay (05). | Good in replay. City run: 68% stuck. | City tables in the report page. | Chalmers cars (05 draft 9), blind test |

### Run settings

| # | Input | Label | What it is | How checked | How wrong | Network effect, test | Replace with |
|---|---|---|---|---|---|---|---|
| S83 | Weather | INVENTED (zero) | Dry, always. | No. | Rain headway +12–15%, snow capacity −12 to −20% (04). | None. | Pick a dry day; `μ` later |
| S84 | Light and winter | INVENTED (zero) | None. | No. | Stockholm's winter is its own traffic. | None. | Pick season |
| S85 | Step size | INVENTED | dt 1 s. | 04, 11. | Saturation 15%, queue wave unstable, Euler stopping. | Small nets (04), Python (11). | 0.1–0.5 s with ballistic, tested on GPU |
| S86 | Teleport time | INVENTED | 120 s. Code default 300, Berlin config copied. | 06 E3, 15. | Hides gridlock. | Toy 17,910 to 0. | Off, with missed-turn rule |
| S87 | Junction blocker | INVENTED | 20 s, copied from BeST. | No. | Lets jams clear by ignoring them. | None. | Remove and test |
| S88 | Collisions | INVENTED | Engine action. 51 recipe, 149,127 at full demand. SUMO has fewer. | 02. | Each is a broken ledger or a move through a car. | Not investigated. | Fix first |
| S89 | Warm-up | INVENTED, harmless | Starts at 00:00 from empty, low demand. First teleport at 00:05 is a coding fault, not warm-up. | Summary. | Small. | None. | Keep |
| S90 | Network empty at start | INVENTED | No overnight traffic left. | No. | Small. | None. | Keep |
| S91 | End of day | INVENTED | 2,235 still running at midnight, not counted. | Summary. | Small here. | None. | Horizon past midnight, as assign does |
| S92 | Seeds | INVENTED | One seed per run usually. Route file drawn once: seeds 42, 7, 6. | 2–8% between engine seeds (02). | Route-draw noise never measured. | Small vs other errors. | Repeat with new draws |
| S93 | Engine against SUMO | ESTIMATED, modelled | 35–64% more teleports than SUMO on same input. | 02. | Bug lead. | Yes (02). | Fix |
| S94 | District cut for 09e | INVENTED | 1 km box. Trip entry time `d + 1.3 × free-flow time`, 1.3 picked by hand. `stockholm2.py`. Warm-up 300 s. Two seeds. | No. | Arrival pattern invented twice over. | Results depend on it. | Label as synthetic |

### The checking data itself

| # | Input | Label | What it is | Caveat |
|---|---|---|---|---|
| S95 | Årstrafik | MEASURED | 63,047 records, 4,053 sites, since 1991. | Median site-year 5 days. No dated days. One record 91,600 on 3 days needs screening. No speeds on Essingeleden. Terms not confirmed as a standard licence. |
| S96 | Toll totals | MEASURED | Monthly. Sep 2024 and Sep 2026 seen. | No station, direction or hour publicly. Exemptions unknown. |
| S97 | Municipal vehicle-km | ESTIMATED | 3.3 bn/year, read from a figure. | Not the clip. |
| S98 | TomTom index | ESTIMATED | 42.8% metro congestion, opaque. | Sanity only. |
| S99 | RVU | MEASURED survey | 11,985 responses, 21%. | Car includes passengers. Report 404s at the cited URL. |
| S100 | Year-to-year floor | MEASURED | WAPE 12.4% on 146 pairs. | Annual means, so true day-to-day is not known here. Berlin lane-hour median 8.7%. |

## Every input: Berlin BeST

| # | Input | Label | What it is: source, date, sample | How checked | How wrong | Network effect | Replace with |
|---|---|---|---|---|---|---|---|
| B1 | Origins, destinations | ESTIMATED | MATSim v5.5.x ×10 synthetic agents, inferred by report 03 from r=0.9992. Unpublished filter. | SrV, MATSim, cells. | Keeps about 80% of inside trips, drops crossing. | Link r 0.74; median link ×2.0. | v6.4 ×10 |
| B2 | Trip count | ESTIMATED | 2,248,884. | SrV 2.21 M. | "Berliners inside Berlin". | 0.50–0.62 of real. | v6.4 4.42 M, untested |
| B3 | Departure times | ESTIMATED | MATSim 5-minute shape, agents shift within 2 h. | Detectors, 93 sites, Sep 2024. | 08:00 flow 0.51 of real. Night nearly empty. Cliff −39% in 25 min at 20:00. | Evening load. | Detector shape |
| B4 | Weekday, season | ESTIMATED | Synthetic weekday. Detectors Sep 2024, SVZ 2019. | Year effect about 2 points. | Small next to demand. | Small. | One dated day, detectors have them |
| B5 | Routes | ESTIMATED | DUA iteration 103, Gawron, 900 s, routed at half load. | Report 03. | Too concentrated: 88.7% vs 69.5% on count net. | Not equilibrium at real load. | Re-iterate |
| B6 | Vehicle mix | INVENTED | One vType: 5 m, accel 1.5, sigma 0.5, tau 1, maxSpeed 50 m/s. Lkw 8.33% of crossings real. | Detectors. | Up to 12% of site gap. | Not simulated. | v6.4 classes |
| B7 | Buses | ESTIMATED, off in cars | 26,143 trips, 277,000 km, 5,468 stops. `cars` run doesn't load them; stops would be ignored. | Report 03. | +1 point of volume. Blocking unknown. | Published with-bus SUMO 2,332 teleports vs 2,090. | Load plus stops |
| B8 | Through and outside traffic | INVENTED (near zero) | 0.06% of trips start on dead ends. | Radial ratios. | A10 0.02, A115 0.18 of official. | Half the gap with others. | Re-extract |
| B9 | Pedestrians, cyclists, parking, deliveries | INVENTED (zero) | Filtered from net use. | No. | Unknown. | None. | Same as Stockholm |
| B10 | Network | ESTIMATED | OSM Nov 2020, edited with netedit 1.21 on 2025-03-26 using a teleport list. | 6 sites against today's OSM. | Way 138614363 is now a construction site. **Tuned to SUMO's own failures.** | Unknown, by design favours SUMO. | Fresh build with audit |
| B11 | Map date against traffic | INVENTED pairing | 2020 map, 2025 edits, 2024 detectors, 2019 SVZ, MATSim about 2019 base. A100 extension opened Aug 2025. | Dates. | Real road network changed. | None. | Frozen date |
| B12 | Lanes, turn lanes | ESTIMATED | OSM. 2,352 turn-only approaches, 756 unconnected lanes. | TE324 suspect. | Not checked officially. | None. | City data |
| B13 | Speed limits, free flow | ESTIMATED / INVENTED | OSM, factor default. | No. | Unknown. | None. | Detector speeds |
| B14 | Junction types | ESTIMATED | Rules, and yields hand-removed. | Bus paper. | Hand changes raise capacity. | Unknown. | Audit |
| B15 | Signal positions | ESTIMATED | 2,344 controllers on 2,875 nodes. LSA WFS 2,305 records not joined. | Count. | Unknown. | None. | Run the fragment check |
| B16 | Programs, cycles, offsets, actuation | INVENTED | Generated. 95.8% nominal 90 s, all offset 0, all actuated. | Census. | No real plan. | None. | City plans |
| B17 | Driver parameters | INVENTED | accel 1.5, Krauss. | Report 05. | Same as S71–S81. | Same. | Same |
| B18 | Grades, weather | INVENTED (zero) | None. | Census. | Berlin is flatter. | None. | Dated day |
| B19 | Step, teleport, flags | INVENTED | dt 1, 120 s, 20 s, from shipped config. Local SUMO adds `time-to-teleport.highways 0`. | Report 03. | cars 23,715 vs SUMO 2,090. | Yes (03). | Teleports off |
| B20 | Boundary | INVENTED | Inside trips only, so no boundary load. | Report 03. | See B8. | Same. | Include crossing trips |
| B21 | Warm-up, seeds | INVENTED | From empty at midnight, seed default, SUMO seed 251920. | No. | Small. | SUMO three seeds in paper. | Repeat |
| B22 | Checking data | MEASURED | Detectors Sep 2024, with dated hours. SVZ is count-based and partly extrapolated. | They disagree by 16–24%. | Cause not found. | Not an input. | Also Traffic4cast (report 04) |

## Every input: Charlottenburg and Mitte

Everything in Berlin applies. These are only the differences.

| # | Input | Label | What it is | How wrong | Network effect |
|---|---|---|---|---|---|
| C1 | Trips | ESTIMATED | `cutRoutes.py` on BeST, May 2025. 330,358 and 357,934. | BeST's half of real traffic, cut again. | Same |
| C2 | Boundary | INVENTED | 47% and 50% of trips appear to start at the polygon cut, `best` lane, `max` speed. | No upstream queue, no upstream signal. Arrival platoons are lost. Traffic that couldn't leave vanishes at the edge. | **No test.** Large by design |
| C3 | Route choice | ESTIMATED | Inherited fragments, not re-routed. A trip can't avoid the map edge. | Rerouting inside a cut is meaningless. | None |
| C4 | Signals | INVENTED | 212 and 265 controllers from the same generated set. 203 and 240 at 90 s. | Same as B16. | None |
| C5 | Buses | ESTIMATED, off | Cut files exist, `cars` runs without them. | Same as B7. | None |
| C6 | Reinickendorf | ESTIMATED | Third cut exists, unused. | Same. | None |

## Every input: LuST

| # | Input | Label | What it is | How checked | How wrong | Network effect | Replace with |
|---|---|---|---|---|---|---|---|
| L1 | Trips | ESTIMATED | 215,526 local plus 70,484 transit plus 2,240 bus. README: validated on SUMO 0.26; CHANGELOG says tested on 0.27. | Authors' papers not opened. | Their README: on newer SUMO "cannot be considered validated". | SUMO 1.28 gridlocks too. | MoST, or nothing |
| L2 | Origins, destinations | ESTIMATED, source not opened | Scenario from 2015. No raw observed OD recovered (01). | No. | Unknown. | None. | Luxembourg data |
| L3 | Departure times | ESTIMATED | Three rush peaks by design. | No real comparison here. | Unknown. | None. | Counts |
| L4 | Routes | ESTIMATED | DUE on SUMO 0.27. Equilibrium for a different engine. | No. | Stale for any newer engine. | Stalls with 77% due. | Re-assign, but see verdict |
| L5 | Vehicle mix | INVENTED | Six passenger types with weights .40/.20/.20/.10/.05/.05, plus bus. No trucks. | File. | Mix isn't from data I saw. | None. | Data |
| L6 | Buses | ESTIMATED schedule, broken in `cars` | 2,240 buses. **37,376 stops ignored.** | Code read, new. | Buses run nonstop, so parity with SUMO can't hold. | None. | Support stops |
| L7 | Through traffic | INVENTED | Author: external mobility "not representative of the traffic on the highways". 4 origin edges. | CHANGELOG. | Their own warning. | None. | Counts |
| L8 | Pedestrians, cyclists, parking | INVENTED (zero) | None in the DUE runs. | File. | Unknown. | None. | None available |
| L9 | Network | ESTIMATED | OSM, about 2015 going by the paper date, fixed by hand, some speeds lowered. 5,779 edges. | Authors. | 11 years old. | None. | Fresh |
| L10 | Speeds | ESTIMATED | Mostly 50, motorway 130. `maxSpeed` 30–70 m/s by type. | No. | Unknown. | None. | Data |
| L11 | Signal programs | INVENTED | 201 actuated. 30-4-10-4-30-4 on 115, cycle 82 on 117. Not established as real (01). | Census. | Regular pattern. | Static vs actuated exists as a route set only. | Plans |
| L12 | Offsets, actuation | INVENTED | Generated. Labelled actuated, but no phase has different min and max durations in the file, so they may run as fixed time. I didn't trace this. | Census. | Unknown. | None. | Plans |
| L13 | Detectors | INVENTED | 3,155 loops are simulator definitions, not field data. | Docs. | Don't confuse them with measurements. | None. | None |
| L14 | Driver parameters | INVENTED | sigma .5, decel 4.5, minGap 1–2.5, accel 2.3–3. | File. | Same as Stockholm. | Same. | Same |
| L15 | Step, teleport | INVENTED | Assign runs vary: teleports off, 120 s, 600 s, valve. | Verdicts. | `lust_counted`: 208,074 of 288,250 unfinished. `lust_valve`: 0 unfinished, 866 teleports, still `network_suspect`. | Yes, local runs. | Teleports off |
| L16 | Weather, grades, boundary, warm-up, seeds | INVENTED | Dry, flat, midnight start. | Census. | Luxembourg isn't flat. | None. | None |
| L17 | Real truth to compare | INVENTED (zero) | None local. | 01. | No gate is possible. | n/a | Drop this as a validation case |

## Every input: Bologna joined

| # | Input | Label | What it is | How checked | How wrong | Network effect | Replace with |
|---|---|---|---|---|---|---|---|
| O1 | Trips | ESTIMATED | 10,069 cars, 0–3,598 s. Built from 636 loops, 5-min, 11–13 Nov 2008, Tue–Thu, about 90 faulty, with manual corrections. | Slides only. | 18 years old. Method not read. | Not compared here. | Bologna open data if any |
| O2 | Origins, destinations | ESTIMATED | From VISSIM scenario plus counts. | No. | Unknown. | None. | None |
| O3 | Time window | MEASURED source, one hour | 8–9 am. | Slides. | Authors: "traffic demand is only for one hour". | No day shape possible. | None |
| O4 | Vehicle mix | INVENTED | Thesis: all `human`. Loops had no classes. | File. | Trucks unknown. | None. | None |
| O5 | Buses | ESTIMATED, off | Exist in the SUMO scenario, `bologna_cars.rou.xml` doesn't load them. Net has 34 lanes closed to cars. | Config. | Thesis says "without structural modification". | None. | Load, needs stops |
| O6 | Pedestrians, parking | INVENTED (zero) | None. | File. | Dense Italian city. Unknown. | None. | None |
| O7 | Network | ESTIMATED | VISSIM import, checked on Google images, hand-fixed connections. 267 edges. | Slides. | Better lane work than OSM probably. Not verified. | None. | Fresh audit |
| O8 | Signal plans | MEASURED source, city Excel | 13 `utopia` programs, for example cycle 117 s. | Slides, file. | Real greens but static. | None. | Dated logs |
| O9 | Actuation | INVENTED (zero) | UTOPIA adaptive off, per authors. | Slides. | Real signals adapted. | None. | None |
| O10 | Offsets | INVENTED | All 13 are 0. | File. | Whether real plans were synchronised: unknown. | None. | Plans |
| O11 | Driver parameters | INVENTED | IDM, decel 2, tau 1, minGap 2.5, not calibrated. Report 05: calibrated IDM saturation 3.0 s. | 05. | Capacity may be low. | Thesis results depend on it. | Report 05 |
| O12 | Warm-up | INVENTED (zero) | None, 5,400 s from empty. Authors warn. | Config. | First part underloaded. | None. | Pre-load |
| O13 | Step, flags | ESTIMATED | dt 0.1, default teleport. | 10. | Fine for this size. | Report 10. | Keep |
| O14 | Boundary, routes | INVENTED | 38 dead ends. Authors: too small for rerouting. | Slides. | Routes are fixed by design. | None. | None |
| O15 | Grades, weather, seeds | INVENTED | Flat, dry. November data. 3 seeds. | File. | Small here. | None. | None |

## Every input: I-80 Davis

| # | Input | Label | What it is | How checked | How wrong | Network effect | Replace with |
|---|---|---|---|---|---|---|---|
| I1 | Trips | ESTIMATED | 24,242 over 5 h, OD pairs "based on PeMS", 3 demand sets. Dates not given on Dryad; which set we use is unstated. | Dryad page. | Unknown. | None. | PeMS dated day |
| I2 | Time shape | INVENTED | Symmetric by hour. Not a real afternoon. | New census. | Real peaks aren't mirror images. | Shapes all breakdown timing. | PeMS 5-min |
| I3 | Vehicle mix | INVENTED by us | Thesis removed heavy vehicles. Real share not checked. | Thesis text. | Directly raises capacity. | Report 11: −16 to −38% for 40 t rows, worst case. | PeMS, truck data |
| I4 | Routes | ESTIMATED | Shortest paths, a corridor with few alternatives. 7 origins. | Dryad. | Small risk. | Small. | Keep |
| I5 | Network | ESTIMATED | Authors' netedit file 2019, 38 edges. | Not checked. | Unknown. | None. | Caltrans, aerial |
| I6 | Speed limit | INVENTED until checked | 121 km/h on 105 of 118 lanes. I remember 65 mph there, not verified. | Census. | Possibly 15% high. | Free-flow travel time. | Check |
| I7 | Lane rules | ESTIMATED | 25 `closingLaneReroute` for `trailer`. Inert once trucks are removed. | File. | Truck lane logic gone. | Unknown. | Restore |
| I8 | Depart | INVENTED | 25, 20, 15 m/s at source. | File. | Small. | Small. | Keep |
| I9 | Driver | INVENTED | IDM as Bologna. | 10. | No calibration. | Yes, in report 10. | Fit to PeMS |
| I10 | Step | INVENTED | dt 1 unlike others, CACC collides. | 10. | 32,088–33,217 collisions per CACC run. | Yes (10). | 0.1–0.5 s |
| I11 | Weather, grades, warm-up, seeds | INVENTED | Dry, flat, starts empty at low demand, 3 seeds. | File. | Warm-up fine. | None. | Dated day |
| I12 | Name | Warning | **This isn't NGSIM I-80 in Emeryville**, used in reports 05 and 14. The clips "courtesy on the I-80 shape" need checking on which they are. | Files. | Confusion risk. | n/a | Rename to `i80_davis` |

## Every input: ring and test junctions

| # | Input | Label | What it is | Use |
|---|---|---|---|---|
| R1 | Ring geometry | INVENTED | 4 km, one lane, 80 edges at 33.3 m/s. After Porfyri et al.'s simulation setup. Not Sugiyama's real 230 m ring. | Stability test |
| R2 | Density | INVENTED | 200 cars, 50 veh/km. | Same |
| R3 | Disturbance | INVENTED | One car slowed 60 s after 2,000 s warm-up. | Same |
| R4 | Driver | INVENTED | Same vehicle types, dt 0.1. | Same |
| R5 | Comparison | Measured data exists elsewhere | Sugiyama and Stern rings are real and not used in these sweeps. | Could become a real test |
| T1 | Two-signal grid | INVENTED | 60 km/h, 27-3-27-3 static 60 s, flows 650/420/90/90/90/90. | GLOSA and parity |
| T2 | `junction_tests.py` | INVENTED | 400 m arms, generated by netconvert, Krauss sigma 0, IDM. | SUMO parity |
| T3 | `golden.py` | INVENTED | Against SUMO only. | Regression |
| T4 | D8 district, junction nets | INVENTED | Generated in `scripts/d8/`. | AV tests. Blocked by the gate |

## Tally

Counted from the label column above. A row counts once, even when it bundles several inputs. Checking data isn't counted as input.

| Scenario | Input rows | MEASURED | ESTIMATED | INVENTED |
|---|---:|---:|---:|---:|
| Stockholm recipe | 94 | **0** | 18 | **76** |
| Stockholm old | 94 | 0 | 19 | 75 |
| Stockholm v5_inventory | 94 | 2 (signal positions, grouping) | 20 | 72 |
| Berlin BeST | 21 | 0 | 10 | 11 |
| LuST | 17 | 0 | 7 | 10 |
| Bologna | 15 | 2 (one-hour count source, city plans; both 2008 and through others' processing) | 5 | 8 |
| I-80 Davis | 11 | 0 | 4 | 7 |
| Charlottenburg, Mitte | Berlin plus 6 | 0 | 4 more | 2 more |
| Ring, test junctions | 8 | 0 | 0 | 8, as they should be for unit tests |

## Inputs with no controlled test at all

These need a test before anyone can say they don't matter: pedestrians, cyclists, parking and stopping, bus dwell, trucks in a city run, offsets and coordination, walk phases, right-of-way signs, free-flow speed, turn speed in a city run, congestion tax in routing, tide direction, map-edge inflow, cut-out boundaries, weather, grades in a city run.

## Top 3 recommendations

**1. Relabel now.** Apply the verdict table everywhere results appear: the report page, 09d, 09e, and AGENTS.md. Next step: an editor pass by whoever owns the page. Stockholm gets "synthetic, generated signals, 60% load, carries 45% of measured traffic". Rename I-80 to `i80_davis`.

**2. Attempt the gate first on a corridor, not a city.** No signals needed, so the biggest invented input disappears. Candidates: I-80 Davis with PeMS (free account, report 01), the A10 (report 01), E4/Essingeleden with Trafikverket data. Next step: Erik creates the PeMS account. Then build one dated weekday with trucks, from 5-minute detectors, and hold out sites and speeds.

**3. For Stockholm, replace in this order, measuring after each step against the held-out Årstrafik sites, and stop tuning on teleports.** (a) NVDB lanes, limits and turn bans, downloading the open layers before the city removes them. (b) Refit to Årstrafik with a prior instead of 2016 estimates. (c) Add trucks from Årstrafik shares. (d) Real toll passages and signal plans (report 05 drafts 1–3). (e) One GPU sensitivity sweep for the untested list above, using bounded values, so the ranking above stops being opinion. Only then return to 100% demand on `v5_inventory`.

## What only Erik can do

All drafts are already in [report 05](05-sweden-kth.md), so I haven't repeated them.

- Send drafts 1, 2 and 3 for toll data and signal plans.
- Create a PeMS account. Register for Trafikverket's API and Lastkajen for NVDB lane codes.
- Decide whether the relabelling also applies to thesis wording, for example in a corrected version.
- Tell me or whoever follows up which I-80 demand set was used and why heavy vehicles were removed, if he or Adam remembers.

## Dead ends and limits

- **I did not read** the Bieker chapter, the LuST papers or the Gao report, only slides, README and Dryad. A few labels could move toward ESTIMATED or MEASURED if those show more.
- **OSM tag counts stopped early** when the PC overloaded: restrictions, `construction`, conditional limits and ramp meters weren't counted. Nothing here depends on them.
- **Old demand and Berlin route files weren't rescanned.** I relied on counts in reports 02 and 03, which were rechecked there.
- **Comparison limits:** recipe flows use `entered` on the matched edge. Årstrafik is an annual mean, and it's at 60% scale by design. So 0.453 mixes the 60% choice with real error. Scaled up linearly it would be about 0.75, but that run locks up, so that number doesn't exist in simulation.
- **Blind rows stayed blind:** I excluded `role=test`. An earlier assign run on the old demand did use them, giving 0.79 WAPE.
- **Speed join:** only about half of records have speed, and those skew to smaller streets.

## New directions

- **A Stockholm-free first pass:** Melbourne (report 01) has real signal sheets, which removes the worst input without needing any request. The engine needs left-hand traffic first.
- **Sugiyama and Stern rings** could be real tests at almost no cost. They're measured, and they just aren't in the sweep.
- **Årstrafik's per-site hourly profiles** can replace `retime.py` tomorrow, at least per road class. They give no OD, but they'd stop the worst shape errors.
- **Report 02's recipe can be re-scored** in this form every time something changes. The script is [recipe_vs_arstrafik.py](scripts-16/recipe_vs_arstrafik.py). Teleports shouldn't be the score any more.
