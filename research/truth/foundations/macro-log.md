# Macro log: rungs 3, 4, 5

**State on 6 November, when the owner changed direction.** Behaviour is now tested first on recordings where demand, routes and signals are all observed (drone and overhead camera). Berlin with MATSim demand becomes the last tier, a test of demand and routes once behaviour is settled. So this work stops here: rung 3 exited, rung 4 doesn't pass and hasn't hit the kill rule, rung 5 never started. Section "Pick it up cold" at the end says what exists, where, and what to do next.

| Rung | Verdict | Numbers |
|---|---|---|
| 3 | **Exits** on the upper test, cuts and audits; lower side has named causes only | upper .18% of site-hours at s 1,750, 1 named site (F072); jam heads median real/capacity .56 (F067 miss, named); cuts 0 of 58 and 0 of 84 |
| 4 blind | **Speeds pass, jams and motorways fail** | 06-20 h speed bias arterial −5.6%, local +1.6%, motorway +10.9%; arterial dip .66 (real .69), motorway .66 (real .46); jam list caught 0-17% against a real-day floor of 72-91% |
| 4 fitted | **Fails** | 07-18 h RMSN .426, R² .306, slope .552, GEH<5 32%; primary −22%, secondary +9%, tertiary +68% |
| 4 kill rule | **Not hit** | route choice alone reaches the 08 h site flows moving 4-8% of vehicle-km (F076): the fault is route cost, not demand |
| 5 | Not started | |

Nobody contacted. No microscopic simulation, no GPU. Data in `cars-data/berlin2019/macro/`, scripts in `scripts/macro/`. Tuning sites and May 2019 only; locked sites and months not read.

Inputs: lanes ESTIMATED (OSM 2019, m17); signals INVENTED (netconvert structure); saturation MEASURED elsewhere (report 25, 1,285-1,895, not Berlin); give-way gaps from HBS; demand MODELLED (who, where, when, class from MATSim v6.4).

## Rung 3

Base map **m17** with table repairs: same edges as m12, has the 141 OSM signals and OSM 2019 turn and bus lanes. m12 at s 1640 has the same .13% one-way result, so the map choice does not rest on this test; m17 is chosen because it holds the measured 2019 facts.

Table repairs, each a named cause (`mt.repair`, log in `macro/m17/repairs_r.csv`). They live in the table, not in the net: `step2_lanes.py` should take the same rules before rung 6.

| Cause | Where | Effect |
|---|---|---|
| Detector lane index read as a lane of the map; a closed bus lane shifts it | 7 sites | Test counts the n best lanes |
| Tag `none` read as serving nothing, though it means no arrow | Schöneberger Ufer `left\|through\|none\|none`, others | Lane also serves straight on |
| Turn tag names a target not on the map, lane left with no way on | 55 connections restored, Tunnel Tiergarten `left\|through\|right\|right` | |
| Ramp or carriageway joining straight on read as a gap search | Bundesallee TE264: capacity 691 against 1,438 real; A100 ramps | Daganzo's merge |

Results: cuts first.

| Test | Result | Forecast |
|---|---|---|
| Cluster cuts k 2-16, peak hour against capacity + storage | 0 of 58 over; max peak/capacity .30 | F052 hit |
| Band min cut (400 m), k 2, 4, 8, s 1285, 1640, 1895 | 0 of 84 over; max v/c .61, .53, .49 | F055 hit |
| Real flow over a cut | 0 (few sites on cut links) | F053 hit |
| One-way, s 1640 | 16 of 11,948 site-hours, 2 sites: TE562 needs g/C .43, TE509 .44; both inside Hamburg's range, map programs are invented | F050 |
| One-way, s 1285 | 299, 9 sites; TE184 needs .69, TE370 .68, over Hamburg's p90 of .60 | F051 |
| One-way, s 1895 | 4, 1 site | F051 |
| Two-way at own stop line, s 1640 | median .56 | F054 miss |
| Two-way to the first signal straight on, s 1640 | median .62, 40 of 46 under .85, 1 over 1.1 | F056 miss |

Cut caveats: capacity sums each link's best movement with no shared green, so a pass is weak and a fail would have been proof. Gates are MATSim's until the region runs.

Two-way reading: real flow with a queue present is about 530 veh/lane/h at signal-bound sites. At s 1640 that is g/C .33. Hamburg's median is .31, the map's .46. So the map's invented greens are the leading cause, not proven: an hour flagged as queued may not discharge at saturation all hour, and a queue can be set further down. It gets re-tested on the rule below.

Audits: no signal connection without green, none under 5 s. Three main-road movements under 50 veh/h on screen foe flows, all permissive rights across heavy flow with almost no demand. Priority-coded through movements on main roads: 10 urban, one look each (`audit_prio_look.csv`), none has an OSM 2019 signal at the junction after m16; 7 are carriageways joining, 3 links crossing a road. Earlier suspects (Straße des 17. Juni, Hardenbergstraße, Karl-Liebknecht-Straße) are signals since m16.

Signal pairs under 50 m: 208 (`signal_pairs.csv`), 163 under 30 m, 166 on main roads, none on one controller, median storage 3.9 cars. Each gets one coordinated rule from Hamburg when the reality agent has measured it, fixed before any Berlin score.

Clean cross-sections: all 24 stations over 200 m from a calibration link are in the locked set (report 22's rule), 4 of them in the district. They are not read here. Macro writes their flows for the reveal.

### Rung 3 on the reality table's corrections (6 November)

| Test | Result | Forecast |
|---|---|---|
| Upper, s 1,640 / 1,750 / 1,900, committed rule greens | .33% / .18% / .12% of 11,948 site-hours; 1 site at 1,750, TE562 Potsdamer Straße needs g/C .40 | F072 hit after the rule change below |
| Jam heads tier A at a third, real flow over table capacity (`jam_heads.csv`) | 18 heads with a loop within two edges: median .56, p25-p75 .44-.94; 4 of 33 over 1.1 | F067 .8 ± .15: miss |
| Short links under 50 m between signals, saturated feed over storage, map programs (`short_links.csv`) | through: 75 of 166 links overfed, 2,574 excess cars a cycle; R 6's rule on the 74 opposed through connections: 74 links, 1,655 (−36%). Turns: 118 of 151 links, 2,815, unchanged | F068: through −36% against half; turns now the larger source |
| Cuts | unchanged: 0 of 58, 0 of 84 at s 1,640 and up | F052, F055 |

**The jam-head miss, named.** Hourly flow at a head is a floor on capacity, since a queue rarely fills the hour (R 2: queue-present flow equals flow without one). The invented greens give main roads about .46, while Berlin's queue-hour flows imply an effective .33. And macro carries .65-.8 of real flow at those heads, at x .66 median; only 11-23% of heads are over x .9 in macro at 08 and 16 h. A loop can't prove the table generous; rung 4's jam list can, and this predicts it will catch few.

**Short links.** R 6's rule takes a third off the through feed, but at saturated feed it clears almost none of these links, as Hamburg clears only 46%. Turns into short links, which the rule doesn't touch, are the larger source. That points to rung 2's scene N9 and to turn feeds, not to through offsets.

**Rung 3 exits** on the upper test, the cuts and the audits. The lower side has named causes and no proof either way, and goes to rung 4's jam list.

## Rule fixed before any macro score (rule 8)

Revised 6 November from the reality table, before any score on it. Scores F058-F064 ran on an uncommitted mix of this and the first rule, so they count as development runs; the scores from F072 on are the first on this rule.

Signals, all controllers, no site-level change, counts not used:
- Cycle 90 s **05:00-20:59**, 75 s otherwise. R 5: Hamburg's 90 s runs 05-20 h, not 07-20 h as report 26 said. Cycle sweep 75-110 s (`--cycle`), sensitivity only.
- Which movements share a stage: the map's program.
- Stage greens: **the map's stage shares, stretched to the cycle** (`--split map`), each stage .11-.76 of the cycle (R 5). Transitions keep their map length; effective green is green minus 1 s per start (3 s amber counted, 4 s lost, B 5.2). Changed after looking, at rung 3; see below.
- Saturation **1,750** through (R 2: 1,285 is rejected by Berlin's flows), sweep 1,640-1,900.
- Through signal pairs under 50 m, R 6: same cycle, downstream green +2 s, overlap .65 of the upstream green. In the engine: a through movement into a short link between two signals passes `s · .65 · g/C` plus what the link stores per cycle; a through movement out of a short link gets .35 of Webster's uniform delay, as linked. Turns into short links stay as the map's program has them.

### Why the greens don't follow macro's flows (rung 3, 6 November)

The upper test (F072) was run on the greens each rule gives on region model A at 08 h and 16 h, before any macro score. Share of 11,948 tuning site-hours over 1.1 × table capacity at s 1,640 / 1,750 / 1,900:

| Stage split | Over | Sites at 1,750 | What goes wrong |
|---|---|---|---|
| Map's program as is, its own cycle | .13% / .06% / .03% | 1 | |
| Equal degree of saturation on macro's flows, most loaded stage ≥ .47 | 3.16% / 2.64% / 2.25% | 7 | Gertraudenstraße gets g/C .18 at 16 h: macro carries 942 there against 2,338 real, so the cross street looks busier and takes the green |
| Same, the floor on the stage of the highest road class | 1.47% / 1.20% / 0.92% | 6 | Secondaries crossing a primary: Lietzenburger Straße .24, Kochstraße .20 |
| Highest class's stage fixed at .62, the rest by saturation | 3.02% / 2.62% / 2.37% | 5 | Secondaries carrying the main flow starve: Schöneberger Ufer .14, Tiergartenstraße .11 |
| **Map's stage shares, cycle 90 s 05-21 h and 75 s otherwise** | **.33% / .18% / .12%** | **1** | TE562 Potsdamer Straße needs g/C .40, has .31 protected: inside Hamburg's main-phase range, a named invented-program cause |

Greens set on assigned flows feed back: a road macro under-loads loses green, so it costs more and loses more flow. Smith (1979) showed equisaturation policies can cut a network's capacity this way. Class doesn't say which road carries the flow. So the rule takes no flow and no class: the map's stage shares, on the measured cycle. This was chosen with real counts at rung 3's exit test, as the ladder says to fix a failing table, by one named cause, and it is fixed now, before any rung 4 score. `--split sat` and `--split main` stay as sensitivity runs.

Route cost: free time from probes as above; `β` residential and living street +.30, unclassified and tertiary +.10, other 0; perception noise σ .15 per edge and draw (D step 3, order of 10-20%). PCE car 1, van 1.2, trucks 2. Free time per edge from probes at 05-06 h (R 3), `scripts/macro/free_time.py`: L over v_hm, on every edge with 40 or more probes and 30 m or more, else the median probe ratio of its class, apart for edges ending at a signal. The signal's low-flow delay is then in the free time, so the engine adds only Webster's uniform delay above the through movement's zero-flow value, plus overflow. Changed after looking (F077): the first version used probes only on edges not ending at a signal, and Webster with random arrivals put 17.5 s at each of 4.2 signal passes a km on arterials, where real 05 h speeds imply about 5 s, HCM's arrival type 5. That makes 05 h a consistency check, not a blind one; it still misses by 16% (F078).

## Rung 4 (6 November)

Region model A, 100% demand, movement detail in the district, on the committed rule. Runs in `cars-data/berlin2019/macro/runs6/`, scores in `cars-data/berlin2019/runs/macro_*`. Scored with the frozen `metrics.py` on tuning sites and days.

**First scores** (F073 08 h, F066 16 h), before the free-time change:

| | 08 h | 16 h |
|---|---|---|
| Arterial / local km/h, model against v_hm | 20.0 / 18.9 against 23.7 / 20.4 | 17.3 / 14.7 against 21.8 / 18.4 |
| RMSN, R², slope, GEH<5 | .49, .20, .38, 38% | .42, .30, .56, 31% |
| Class bias primary, secondary, tertiary | −40%, +2%, +42% | −17%, +15%, +69% |

**Free speed hour** (F077): at 05 h arterials ran 23.7 km/h against 35.6 real. Webster with random arrivals gave 17.5 s at each of 4.2 signal passes a km; real speeds imply about 5 s, HCM's arrival type 5 (PF .43 at g/C .46). The brief's "free speed from 05-06 h per edge" had been applied only to edges not ending at a signal. Now on all (F078):

| | 05 h | 08 h | 16 h |
|---|---|---|---|
| Arterial km/h, model against v_hm | 29.9 / 35.6 | 23.4 / 23.7 | 19.9 / 21.8 |
| Local | 26.8 / 32.8 | 22.1 / 20.4 | 16.0 / 18.4 |
| Motorway | 74.1 / 80.4 | 54.1 / 43.6 | 47.2 / 32.0 |
| RMSN, R², slope | | .454, .243, .434 | .409, .331, .603 |
| Class bias primary, tertiary | | −31%, +42% | −10%, +76% |

**Route choice alone can reach the counts** (F076, `route_bound.py`, a diagnostic whose splits are thrown away): on macro's kept paths at 08 h, moving 3.9% of vehicle-km brings RMSN .50 to .30 and R² .21 to .65; 5.8% gives R² .78, slope .79, GEH<5 64%. So the kill rule doesn't fire at 08 h: the demand can produce the counts with small route changes, and the fault is in route cost.

**Where flow goes wrong, read by D's flow-and-speed table.** Primary under-load sits on the central east-west corridors: Leipziger Straße .29-.66 of real, Potsdamer Straße .45-.77. Their own edges run at free speed in macro, so it isn't capacity there: "flow low, speed high: traffic goes elsewhere". It goes to parallel streets with no signal arc on the map and no flow-dependent delay: Französische Straße, one lane, 2.2-2.7× real at free speed 35 km/h, where probes show 24 km/h at 08 h on 490 real cars. Lindenstraße 1.4-1.7×, Lennéstraße 3×. Macro has no mid-block friction on urban streets, and the map may be missing signals or priority rules on them. Motorways run 25-47% too fast: no spillback, no merge queue in a static model, as D expected.

**The whole day** (F079, F075, F059). Model A hour by hour, 06-20 h, each hour its own static assignment (`runs6/aday`, merged from `runs6/ah/h*`, `f08`, `f16`):

| Hour | 06 | 07 | 08 | 10 | 12 | 14 | 16 | 17 | 18 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|
| Arterial model / v_hm, km/h | 19.8 / 31.7 | 19.5 / 27.2 | 23.4 / 23.7 | 25.9 / 24.9 | 24.8 / 25.1 | 22.3 / 24.3 | 19.9 / 21.8 | 22.1 / 23.0 | 24.2 / 23.6 | 29.4 / 29.2 |
| Local | 17.4 / 29.4 | 17.6 / 23.4 | 22.1 / 20.4 | 23.8 / 20.1 | 20.8 / 20.0 | 21.1 / 20.5 | 16.0 / 18.4 | 21.0 / 19.6 | 22.7 / 20.1 | 25.9 / 23.2 |
| Motorway | 53.6 / 71.1 | 49.2 / 51.5 | 54.1 / 43.6 | 64.4 / 57.4 | 58.7 / 62.4 | 51.5 / 48.3 | 47.2 / 32.0 | 51.8 / 40.3 | 60.3 / 50.8 | 72.9 / 73.4 |
| Real over model, arterial sites | .71 | .92 | 1.16 | 1.19 | 1.12 | | .96 | 1.00 | 1.09 | |

- **Passes:** arterial and local speed by hour from 08 h on, within 10% at almost every hour. Arterial dip .66 against .69. Over 24 h, real over model is primary 1.27, secondary .90, tertiary .58, the same direction as MATSim's own (R 4: arterials 1.08, tertiary .78) but stronger.
- **06-07 h overload, a demand-by-hour cause.** Macro's slowest hour is 06 h, when the real network is nearly free: arterials 19.8 against 31.7. Demand at 06 h is 112,390 vehicles against 145,410 at 08 h, but they drive 3.71 M vehicle-km against 2.31 M (33 km a vehicle against 16): long trips into the city leave early in MATSim's plans. Real over model at arterial sites is .71 at 06 h and .92 at 07 h, the same early morning R 4 found in MATSim's own runs (.77, .86). The static model piles that hour's overload into that hour. Timing correction is the smallest OD change there is and is allowed only after routes and capacity are done (PLAN, rule 7), so it wasn't applied.
- **Motorways:** too fast in every peak (16 h 47.2 against 32.0) and dip .66 against .46. A static model has no merge queue and no spillback, as D said it would understate delay. AVUS/A100 at 15-18 h, the longest real jam, doesn't appear.
- **Jam list,** probe tier A, no parallel-road rows, edges matched by `real_jam_edges.csv`: at a third, AM 0 of 35 caught (4 model places), PM 3 of 56 (9 places, 67% false); at half 11% and 17% caught, 65-67% false. The real-day floor is 72-81% caught at a third and 80-91% at half. Static macro with point capacity barely jams, as the jam-head test predicted: heads sit at x .66 median.
- **Fitted sites,** 07-18 h, 8 days, median: RMSN .426, R² .306, slope .552, GEH<5 32%, WAPE .33, bias −3.5%. Every bar fails except RMSN, which misses .40 by .03.

### What would come next on Berlin, in order

1. **Route cost on urban streets without signals.** Add mid-block friction or the map's missing control on streets like Französische Straße (one lane, kind 0 arcs, no delay at any flow); check the map's control there against OSM 2019 first, one named cause at a time. Then rerun F076: if the kept-path bound stays at 4-8% of vehicle-km and the class bias falls, routes were the cause.
2. **The sweep that never ran** (F074, `scripts/macro/sweep.sh`, 15 runs, about 3 min each locally on 2 threads): s, cycle, split, σ, β. Sensitivity only.
3. **Model B** (`scripts/macro/bday.sh`): needs heavy's big slot (it ran out of 3 GB; each rayon fold holds a full period-by-arc array, so fewer threads or a chunked fold would cut memory). It gives queues that carry over, which the jam list and motorway dip need.
4. **Timing of MATSim's morning,** only after 1-3, by one time-profile factor (PLAN rule 7).

## Pick it up cold

- **Branch** `t3/d09c4919`. Code: `crates/cars-macro` (engine; `macro DIR OUT --model a|b --hours H --split map|sat|main --cycle 90 --s 1750 ...`), `scripts/macro/`.
- **Tables:** `.macro-data/prep_region/` (region with district movement detail, built by `prep_region.py m17 m16 OUT`) and `.macro-data/prep_ft/` (same, free times from `free_time.py`; **use this one**). Both untracked in the worktree; copies of `prep_region` also at `cars-data/berlin2019/macro/prep_region/`. Build `prep_ft` again with `python3 -I scripts/macro/free_time.py PREP_REGION PREP_FT`.
- **Runs:** `cars-data/berlin2019/macro/runs6/`: `a05 a08 a16` (before free times), `a08p` (saved paths, for `route_bound.py`), `f05 f08 f16` (committed rule), `ah/h6..h20` (hourly), `aday` (merged day), `greens_rule.csv` (rule greens for `rung3.py --greens`). Scores: `cars-data/berlin2019/runs/macro_r4a08, r4a16, r4f08, r4f16, r4aday` (`score.json`, `blind.json`, `site_hour.csv`).
- **Rung 3 outputs:** `cars-data/berlin2019/macro/m17/no_model_rule.csv` (upper test), `jam_heads.csv`, `short_links.csv`; `cars-data/berlin2019/macro/real_jam_edges.csv` (member edges of each real jam place, from `jam_edges.py`; kept out of the repo as per-edge probe output).
- **Rerun:** `source cars-data/dev-env.sh`; one hour `target/release/macro .macro-data/prep_ft OUT --model a --hours 8 --iters 45 --threads 3 --reroute 3` (90-180 s); `python3 -I scripts/macro/score.py .macro-data/prep_ft OUT NAME --hours 8`; speeds for any hour `class_speed.py PREP RUN H...`; a day: `ahours.sh PREP OUT H...` then `merge_hours.py OUT H=RUN...` then `score.py` without `--hours`. Upper test: `greens_for_rung3.py m17 RUN_AM RUN_PM greens.csv`, then `rung3.py m17 --repair m16 --tag _rule --greens greens.csv`.
- **Machines:** the homelab node sat at load 31 on 8 threads all afternoon; `heavy` jobs at idle priority didn't finish a 2-minute run in 15 minutes. Local single-hour runs on 2-3 threads are fine.
- **Forecasts:** every line F040-F079 that belongs to rungs 3-4 has a result and a verdict in `forecasts.csv`; F065, F069-F071 and F074 say "not run".
