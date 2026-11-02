# 20: What the simulator cannot do, and which limits matter

Checked 2026-11-02. No GPU. Nobody was contacted. Scripts are in [scripts-20/](scripts-20/), outputs in `/home/erikf/projects/personal/cars-data/truth/limits-20/`.

Erik: "What limitations of the simulation do we need to change so that it becomes more true to life, how cars actually move on the road and what they can do?"

## The answer

**Keep lanes. The largest missing things are not about how cars steer. They are the other things on the street that take road space and time away from cars: pedestrians and cyclists at crossings, buses at stops, parked and loading vehicles.** After those come give-way capacity, speeds, and how drivers change route while driving. None of these needs a redesign.

**Lane-based is good enough for what we need, with one condition.** It holds for Stockholm and Berlin car traffic, on what I could measure and read. Every tool I could read keeps cars lane-based in normal use. Trafikverket handles wide approaches as extra short lanes. Across 41 cities, four network facts (lane density, redundancy, signal spacing, bus production) explain about 90% of the variation in where networks reach capacity, and a lane model can hold all four. **The condition:** this breaks down where two-wheelers are a large share of traffic. In central Athens, 27% of the tracks I measured are motorcycles. If the reference city ends up being one like that, two-wheelers need lateral freedom. Cars still would not.

**Do not build any of this before demand and signals are fixed.** Report 16 found the Stockholm recipe carries 45% of measured traffic, with 66% hourly error against a 12% floor, and no real signal program. The limits below are worth from a few percent to over 50% on individual lanes and movements, depending on the site. Friction added to a network that already locks will lock it harder, and the result will say nothing.

**What is not known:** I found no study that measured, on a real city, how much network-level error any one of these removes. The numbers below are per lane or per movement. The ranking is my judgement from them. Only ablation on the benchmark can settle it, so each change ships with a switch.

## How to read the grades

**MEASURED**: real traffic, from a source I opened or data I processed. **DESIGN VALUE**: guideline figure, not a measurement checked here. **MODELLED**: simulation or analysis. **PROVIDER CLAIM**: vendor text. **UNVERIFIED**: search result only, page not opened. **OPINION**: mine. All costs are opinion.

## New measurements for this report

All of these are small samples. They are for sizing, not for targets.

**Where cars sit, from drone tracks, no lane labels.** Script: [lateral_drone.py](scripts-20/lateral_drone.py). Tracks are grouped into movements by start and end cell (at least 8 cars). The spread is a robust standard deviation across the movement's mean path, so a second lane in the same cell widens it less, but not never.

| Site | Tracks kept (cars, vans, trucks, buses) | Two-wheelers | Spread on straight movements, m | Spread in turns over 45°, m | Stopped pairs side by side |
|---|---:|---:|---|---|---|
| Helsinki, 17 Sep 2025, 15 files | 1,251 | 104 of 1,461 tracks | 0.22-0.30 per file, 19 movements, 294 cars | 0.21-0.39 per file, 27 movements, 478 cars | 12 pair-seconds in 6,320 stopped vehicle-seconds; 11 at 2.5 m or more, 1 is a tracking duplicate |
| Pully, Lausanne, one file | 168 | none | 0.15-0.19, 3 movements | none | 0 in 635 |
| Athens pNEUMA, one block, 30 min | 660 | 251 of 922 tracks | 0.56 median, 0.24-1.74, 6 movements | 1.23 median, 0.70-1.99, 7 movements | 1,265 pair-seconds; 0.08% under 1.9 m centre to centre, 17% under 2.5 m, median 2.94 m |

Reading, **MEASURED, thin**:
- In Nordic and Swiss traffic, cars hold a line tightly, about ±0.25 m, even through turns. Some of that is tracking noise.
- A car is about 1.8 m wide, so two cars within 1.9 m centre to centre would nearly touch. That almost never happens, even in Athens.
- The 17% under 2.5 m in Athens could be two abreast in a wide lane or two normal narrow lanes. Without lane geometry I cannot tell them apart. I give it as an upper bound.
- Parked cars have no direction of travel and are dropped, so the share of queueing cars with a neighbour is a lower bound.

**Turning cars held by pedestrians and cyclists, one real signal.** Script: [dlr_vru_block.py](scripts-20/dlr_vru_block.py). DLR Urban Traffic, Braunschweig, Sunday 24 Sep 2023, 12:00-15:00. A car counts as held by a person when it is under 1.5 m/s inside its turn with a moving pedestrian or cyclist 0-12 m ahead and within 4 m to the side.

| Turn | Cars | Held by a person | Mean hold per turning car | Hold when it happens, median, p90 | Held by anything (mostly signal or queue) |
|---|---:|---:|---:|---|---:|
| Right | 1,012 | 6.5% | 0.26 s | 3.5 s, 8.0 s | 17.6% |
| Left | 1,019 | 2.2% | 0.07 s | 2.75 s, 5.45 s | 21.3% |

In those three hours: 4,815 vehicle tracks, 144 pedestrian and 798 cyclist tracks over all arms, so about 80 people per arm per hour. **MEASURED**, with these limits:
- One junction on one Sunday, and mostly cyclists.
- A person near a car is not proof the person is why it stopped, so this may overstate.
- Cars queued behind a held car are not counted, so this may understate.
- Track ids can repeat across 15 minute files.

Sizing: 0.26 s added to a 2.0 s queue headway is about −11% on a lane of only right turners (my arithmetic, an upper bound). Trafikverket's curve at 80 people per hour gives about −7% (interpolated, for pedestrians, and a different cycle). **So the size agrees roughly, and that is one comparison at low flow.** Weekday central Stockholm will be much busier, by an amount I do not know.

## Ranked: everything real traffic does that this design handles badly

"We" means main plus the physics and human branches (`t3/1c6fee50`, `t3/1b36c9cf`), which are not merged yet. Sorted by expected effect on a network-level match against cost. **Class:** Q quick fix (hours to days), M medium (days to weeks), R redesign (months), P pick the day or fix the data, no engine work, S skip for now.

| # | What real traffic does | What we do | Evidence of size | Others | GPU cost, no local arrays | Class |
|---:|---|---|---|---|---|---|
| 1 | **Pedestrians and cyclists block turning cars at crossings.** | Nothing. Persons are dropped, crossings removed, no phase has a walk call (report 16). | Trafikverket: all-turning lane, two-phase signal: 1,700 with no pedestrians, about 1,340 at 250/h, 1,060 at 500/h, 770 at 1,000/h. Lane with 30% turning: about 1,830, 1,690, 1,540, 1,310. Read by eye from [figure 9](#sources), ±30. **DESIGN VALUE.** "Yielding behaviour is decisive for saturation flow" ([Handbok, my translation][tvh]). HCM has right-turn factors for this; a 1998 FHWA report says the procedures of the day "underestimate the effect of pedestrians on right turns in many cases" ([FHWA 98-106][hcmped]). Measured here: see above. | Vissim, Aimsun, TransModeler, SimMobility all have it. NCDOT: "a substantial effect on the operation of the model" ([TransModeler guide][nc]) | One buffer of crossings, one kernel. Each crossing keeps an "occupied until" time, drawn from a flow and the walk phase. A turning link checks it like a foe. **No walking agents needed.** | M |
| 2 | **Buses stop in the lane. Vans load. Cars park and leave. Trips start and end at the kerb.** | Buses absent in Stockholm. `<stop>` is parsed and ignored (`demand.rs:536`, report 16). Cars appear and vanish on the lane with no manoeuvre. Service roads removed. | HCM: 14.4 s per bus, 18 s per parking manoeuvre, a parking lane costs 0.1 lane ([NPTEL summary][hcm], secondary). My arithmetic: 30 buses/h on one lane is ×0.88. 20 manoeuvres/h with kerb parking, two lanes, ×0.90. 41 cities: −6.64 vehicle-km of capacity per bus-km, t = −5.19 ([Loder 2019][loder], **MEASURED, correlation**; I read the table from flattened XML and matched columns by t-values). At their mean bus production that is −16% with critical accumulation held, −2.5% if it moves too (my arithmetic). Treating buses as cars in Zurich's MFD "results in poor accordance" ([Paipuri 2020][pai], abstract). Manhattan double parking −6 to −12% ([ITS record][man], **UNVERIFIED**, 403). 4,513 bus stops and 2,856 ways with parking tags in the Stockholm clip. | Vissim (bay, in-lane and kerb-extension stops, [Handbok][tvh]), Aimsun, SimMobility (dwell model), Paramics (**UNVERIFIED**) | Cheap in concept: a dwelling bus or a loading van **is** a stopped vehicle in the sorted lane, so car following, lane change and queues work unchanged. Per-trip stop list, a dwell timer in `Veh`, a table of timed blockers. Needs row 15 on one-lane streets or blockages get too strong. | M |
| 3 | **Give-way and right-before-left junctions run at real capacity.** | Gap model, fails: at 600 and 900 veh/h on the major road, minor flow 468 and 243 against Siegloch 626 and 455, −25 to −47% (report 16). Roundabout gap spread log-SD 0.57-0.65 against 0.23-0.25 measured. Jam and yield classes dominate stuck cars, on demand that locks. | The Stockholm net has 22,194 priority, 10,674 right-before-left and 1,922 signal junctions, so 5.5% are signals by count, not by flow. Targets are **DESIGN VALUE** only. No Swedish measured gaps found. | All have gap acceptance. Aimsun's required gap falls with waiting ([am]) | Kernel logic exists. Needs fitting to SinD, inD and the Swiss sites, and a smaller spread. No new structure. | M |
| 4 | **People drive below the limit, more so in dense streets.** | Limit × N(1, 0.1). | All-day mean 10-15% below limit in Stockholm (report 16, **MEASURED**). HCM6 loses 0.078 mph per access point per mile per through lane ([NCHRP 900][acc], **UNVERIFIED**). Speed by hour is a gate check on its own. | TfL sets desired speed per link. Vissim has reduced-speed areas; the chosen speed has a large effect on saturation flow ([Handbok][tvh]) | A per-edge speed factor from probe data. Data work, no kernel change. | Q |
| 5 | **Drivers change route on the way when they see a jam.** | Assignment between runs, plus reroute for lost cars. Nobody leaves a route because of traffic ahead. | Adaptive drivers raise a network's critical density "considerably", in simulation ([Daganzo 2011][dag]). Three rounds of feedback cut Stockholm teleports 89% at 60% demand, and raised them inside a full jam (report 02, **MODELLED**), so route response is a large lever with a wrong way to pull it. Real apps are smaller: Google moved under 2% of trips (report 06, **MEASURED**). No field proof of the critical-density effect: its authors say so. | Not checked per tool in what I opened | The lost-car reroute already goes to a Rust router. A share of cars asks at intervals, on current edge times. Rate limited. | M |
| 6 | **Saturation depends on the time step only in the simulator.** | Cities run at dt 1. | Human model, dt 1 against 0.1: through 1,782 against 1,858 (−4%), lost time 0.99 against 2.68 s (fail against pass), double turn 1,548 against 1,199. Krauss: discharge 15% apart (report 04). Vissim poor at 1 s (Hidas, report 15). | Aimsun allows 0.1-1.5 s | Twice the steps at dt 0.5, nothing else. Lost time passes there. Standing spacing does not yet. | Q |
| 7 | **Turning paths are smooth and turn speed is real.** | netconvert shapes: 3,864 lateral samples over 8 m/s² on 2,372 Stockholm lanes. Invented corner floor of 8 m/s (`turn_min`). Right 1,449, left 1,569 against 1,700. | "Speed in turning movements has great importance for saturation flow" ([Handbok, my translation][tvh]). Fixed paths themselves look fine: ±0.2-0.4 m in Helsinki turns, measured above. | **Everyone uses fixed paths.** | Smooth the shapes at build time, then fit turn speed to data. | Q |
| 8 | **Turn bays and flares store and block.** Left-turners wait inside the junction. | Bays only if `--osm.turn-lanes` is set and the map has them. | Bays: "often a critical component" ([NCDOT][nc]). Usable length differs from the drawing because of bus stops and parked cars ([Handbok][tvh]). Spillback lowers arterial capacity, shown in a model, no field figure ([Haddad 2012][had]). TRVMB: flares that hold two abreast are coded as short lanes. | TransModeler: lane additions must be coded as lanes, tapers are "aesthetic" and hold one vehicle | Map recipe, v5 already does part. Check storage inside the junction. | Q |
| 9 | **Trucks are slower and longer.** | None in Stockholm. Berlin one car type. Human driver not fitted on them. | Real heavy share 3.8% Stockholm, 8.3% Berlin (report 16). TRVMB: ×0.97-0.98 at 5%, ×0.93-0.97 at 10% (**DESIGN VALUE**). 10% 40 t trucks in Python: 1,861 to 1,507, worst case (report 11). | All | vTypes exist. Fit truck following on DLR HT and TGSIM. | Q |
| 10 | **Weather changes capacity.** | Dry, always. `--surface` on the physics branch sets friction only. | Freeways: rain −10 to −11%, snow −12 to −20%, jam density unchanged ([Hranac 2006][hr], **MEASURED**). Signals, Vermont: wet 2-3%, slush 11-21%, sticky snow 19-24%, start-up lost time mostly unaffected ([Sadek 2004][sad], **MEASURED**). Winnipeg headways up to +38.7% ([Manitoba][man2]). Japan about −20% in winter ([ISHC 1994][jap]). | Practice: exclude bad days ([Handbok][tvh]) | Pick dry test days now (**P**). Later a per-run factor on T and desired speed, from the same day's weather. | P, then Q |
| 11 | **Incidents, road works, events.** | None. | Real days have them; FHWA lists them among seven sources, without shares on the page I opened ([FHWA][fh]). Trafikverket says to check calibration data is free of them ([Handbok][tvh]). Aerial shows works at 3 sites (report 16). | TfL lists incidents and parking as microsimulation uses; NCDOT's TransModeler guide takes an incident file | **Pick clean days and date the network.** Later, timed lane closures, the same table as row 2. | P |
| 12 | **Capacity drop at bottlenecks.** | Not produced: discharge 7-13% above pre-breakdown flow; free single lane tops out near 1,640 veh/h (report 16). | Relaxation passes against I-395, so the missing piece is short headways at high speed, not relaxation. Matters for Essingeleden and the motorway ring. | Vissim's slow recovery option | Car-following change, bounded. Report 16 tried T and courtesy without luck. | M |
| 13 | **Each lane's width matters a little.** | Width ignored for capacity. Only 2,353 lanes in the Stockholm net have any explicit width. | TRVMB: 2.75 m ×0.94, 3.00 m ×0.97, 3.25 m ×0.99, 3.50 m ×1, 4.00 m ×1.01 (**DESIGN VALUE**). HCM summary: two narrow lanes carry more than one wide lane, the limit given is 4.8 m. | HCM, TRVMB | A per-lane factor on T, width from NVDB. | Q |
| 14 | **Day-to-day variation.** | Seeds only. Same demand every run. | Real days differ by 6.3% per site, 8.7% per lane-hour in Berlin (report 04). That is the gate's bar. A simulation with no day noise cannot be compared to it fairly. | FHWA uses envelopes across days | Draw demand per run. Rust only. | Q |
| 15 | **Passing a stopped bus or van over the centre line, narrow two-way streets where one car waits.** | "Opposite driving" omitted (`lc.wgsl:3`). Two opposing lanes under 1.4 m apart hold no zone, and narrow streets can stand off. | Local, no size found. Stockholm's OSM has lanes of 1.6 m, physics-provenance. Needed for row 2 on one-lane streets. | SUMO has opposite overtaking; Aimsun a two-way overtaking model | A bounded rule through the existing lane-change kernels. Fiddly. | M |
| 16 | **Network boundaries.** Queues build outside the model; exits can be blocked. | Insertion waits off-network, exits are free sinks. | "External section ought to be long enough to contain all traffic" and junctions that queue should be inside ([TfL][tfl]). No through traffic in Stockholm (report 16). No size found. | Guideline practice | Report insertion backlog per entry. Meter exits from real counts. | Q |
| 17 | **Lane use across parallel lanes.** | LC2013 strategic stage. | Trafikverket: varies by site, matters for capacity. Report 18's job. | Vissim, Aimsun | No structure. | see 18 |
| 18 | **Cyclists sharing the car lane.** | None. | TRVMB counts a cyclist as 0.3 car (**DESIGN VALUE**). Separate cycle paths are common in Stockholm: 15,143 `cycleway` ways in the clip. Strongly seasonal. | Vissim, Aimsun lateral | Use the 0.3 at first, as an added vehicle or a speed factor. | Q |
| 19 | **Driver differences and hesitation.** | Per-vehicle T, s0, start delay. Kurtc and Treiber's inter-to-intra-driver ratio on reconstructed I-80: about 0.6% for speed, 4.7-5.9% for gap (report 15). Lost time passes at dt 0.1-0.5. Phone use +0.41 to +0.59 s on headway, simulator, 53 people ([2020 study][phone]), no prevalence known here. | Vissim, Aimsun per vehicle; SimTraffic 10 driver types | Already covered by T's spread. Fix the spread only where a test fails. | S |
| 20 | **Same driver, same route, day after day.** | Not represented. | Matters for route learning, not for a single-day flow match. | Route logit and memory in assignment | Skip until multi-day tests exist. | S |
| 21 | **Perception: line of sight, seeing past a truck.** | Perfect knowledge within a set distance. `see` 30 m at give-way. No occlusion. | `see` 15 or 60 m lowers minor flow from 354 to 324 and 318 veh/h, both ways down (report 16). No network evidence found on occlusion. | Vissim visibility per conflict area. Aimsun 100 m at give-way; only its lateral mode discards hidden leaders. | Occlusion needs ray tests per car. Keep a per-junction visibility from geometry instead. | S |
| 22 | **Reaction delays and looking several cars ahead.** | One leader, 1 s response lag on the human driver. | Multi-anticipation offsets delay and errors, which "in many cases" justifies simple models ([Treiber 2006][tr], **MODELLED**, IDM only). Our chains already pass: wave speed 34.4 km/h, SD growth 1.04 (report 16). | Vissim observes several vehicles | Skip. No test fails for this reason. | S |
| 23 | **Right turn on arrival.** | Red means stop. Free slip lanes only as the map has them. | I read this as right on red, green arrows and slips. TRVMB and the Handbok do not mention turning on red. I believe it is not a general Swedish rule (**UNVERIFIED**). Berlin has some green arrows (**UNVERIFIED**). | Aimsun has RTOR signs | Per-link flag at a few sites, from the map. | S in Sweden |
| 24 | **Darkness.** | Nothing. | Conflicting: 13% and 11% lower capacity in Indonesia and Malaysia; lighting +2.5% on a Dutch motorway. All **UNVERIFIED**. | | Skip until a day needs it. | S |
| 25 | **Position within a lane, straddling, wide-lane overtaking, two abreast in queues.** | One line per lane. Finite lane change on the branches. | Measured above: ±0.25 m Nordic, two-abreast almost absent. Vissim's page says vehicles use the full width by default, and warns that observing adjacent lanes "can reduce the simulation speed significantly". | Vissim yes, Aimsun for two-wheelers, SUMO sublane, TransModeler no | Rewrite: see below. | R, not now |
| 26 | **Filtering.** | None. | Motorcycles 27% of tracks in Athens, 7% in Helsinki. Stockholm share and season unknown. | Aimsun, Vissim, SUMO | Same rewrite as 25. | R, only if the reference city needs it |
| 27 | **Junction space used freely.** | Fixed internal lanes with conflict zones computed from swept paths. | Report 09: foes missed 12%, spurious 18%, fixed by zones. Helsinki ±0.2-0.4 m in turns; Athens 0.7-2 m in the same measure, mixed lanes included. I found no study of network impact. | **No tool I could read does this for cars.** | Free paths need 2D conflict search per pair. No evidence to justify it. | S |
| 28 | **Continuous lateral motion in a lane change.** | **Done** on branches: finite time, shadow lane, quintic. 10-90 time 5.09 s against 4.8-6.0. | Report 05, report 16. | SimMobility constant lateral speed; SUMO optional | Merge it. | Done |

### What is odd about the table

- **Lateral freedom is near the bottom, and that is not because it is hard.** It is because the evidence for cars says it is small, and every tool I could read leaves cars in lanes by choice.
- **Rows 1 and 2 are two faces of one thing.** Trafikverket's city-centre note names both: saturation flow is lower in central areas because of higher side friction from pedestrians and cyclists, vehicle stopping and so on (TRVMB 4.7.5, my translation). HCM's area factor is 0.90 for a central district ([Vistro][vis], provider text of HCM). TRL found the RR67 formula over-predicts London's saturation flows by 15% on average, and TfL names heavy pedestrian movement, poor visibility and parked vehicles ([TfL][tfl], **MEASURED**). That 10-15% sits above the 6-9% day-to-day floor.
- **Our Swedish fit may hide this.** `--region sweden` sets T × 0.55 to hit TRVMB's 1,900 per green hour, and report 16 says replay does not support T that low. TRVMB's 1,900 is a base value before any correction. Once friction exists, the fit needs redoing, and real streets should come in lower. This should be tested against DLR-type real discharge, 2.0 s per car (report 05).

## How other simulators compare

Read from documentation, unless marked. Blank means I could not establish it. Paramics and SimTraffic manuals could not be opened, the same as in report 15.

| | Cars move in lanes? | Car following | Pedestrians block cars | Bus stops | Other |
|---|---|---|---|---|---|
| **Vissim** | Lanes, with lateral position inside them: full width by default, overtaking in a lane optional, 0.2 m at a stand, 1.0 m at 50 km/h, diamond queues ([lateral page][vl]) | Wiedemann psycho-physical, observed vehicles and look-ahead settings ([following][vf]) | Yes, conflict areas, signal heads for walkers ([Handbok][tvh]) | Bay, in-lane and kerb-extension stops ([Handbok][tvh]) | TfL: "Lane-Based network layout" with "lateral behaviour within lanes" |
| **Aimsun** | Lanes. A non-lane-based mode replaces lane changing per vehicle type; the page gives bikes and motorbikes in it with cars, trucks and buses left lane-based as an option ([mixed traffic][am2]). TfL: it "focuses on large-scale performance and aggregated outputs rather than realistic vehicle trajectories" ([TfL][tfl]) | Gipps, with reaction time at stop as a calibration lever ([am]) | Yes, integrated ([TfL][tfl]) | Yes ([TfL][tfl]) | RTOR signs, visibility at give-way, two-way overtaking |
| **Paramics** | Lanes, as far as I can tell | Fritzsche, aggression and awareness (**UNVERIFIED**) | | Yes (**UNVERIFIED**, [FORUM8][p], 403) | |
| **TransModeler** | Lanes. Tapers are "aesthetic in nature" and "only one vehicle can occupy a position laterally along its length" ([NCDOT][nc], guideline) | Not read | Yes, volume file, "substantial effect" | | Incident, detour and pedestrian input files |
| **SimTraffic** | Not read | 10 driver types, drawn at random ([TxDOT][sim]) | Not read | Not read | Junction-level use |
| **SimMobility** | Lanes, constant lateral speed in a change | Reaction time and perception delays per person | Pedestrian layer and crossing choice | Stops, dwell model | Calibrated on 360 sensors ([sm]) |
| **MITSIM** | Lanes | Estimated stimulus-response, reaction-time and headway-threshold distributions (report 15) | None found | Transit movement (**UNVERIFIED**) | The forced and courtesy merging line |
| **SUMO** | "At most one vehicle per lane" by default; on the sublane option, smaller strips mean "the higher the running time" ([sublane][sl]) | Krauss and others; driver state device with perception errors, off by default ([driver state][ds]) | Yes, optional | Yes | Opposite overtaking |
| **cars** | One line per lane; finite lane change on branches | Fitted human model, lowest spacing error in replay against W99 and Gipps on five frozen windows (report 16) | **No** | **No** | Conflict zones from swept paths; order-independent claims |

**So:** we are ahead on following, replay testing and conflict geometry, and behind the main commercial tools on rows 1, 2 and 11. Those are what they have and we lack. Lateral freedom for cars is not the gap.

## Is lane-based good enough?

**Yes for Stockholm, Berlin and AV comparisons in lane-disciplined traffic. No for fully mixed traffic.** My reasons, weakest stated:

1. **Measured lateral spread is small against a lane.** About ±0.25 m in Helsinki and Lausanne, on small samples.
2. **Capacity barely depends on the extra room.** TRVMB's width factor runs 0.94 to 1.01 over 2.75 to 4 m. These are design values. Flares that hold two abreast go in as short lanes.
3. **Network capacity is explained well without it.** [Loder 2019][loder]: adjusted R² 0.91 for capacity over 107 networks in 41 cities, on lane density, redundancy, signal spacing and bus production. This is not a test of a lane simulator, only a sign that lateral detail is not what separates cities. Its authors do not model signal control, and it uses detectors in cities with detectors.
4. **Practice agrees.** TfL describes Aimsun's lateral model as for two-wheelers and Vissim's as making cyclists and overtaking possible. SUMO's own list of uses starts with two-wheelers.
5. **Against:** Athens spreads are 2 to 4 times larger, and motorcycles fill gaps there. Real cyclists matter at Stockholm junctions in summer. I found no direct study comparing a lane-based and lateral model of European car traffic against real network data. Absence is not proof.

**A cheap test before anyone reconsiders.** SUMO has the sublane model. Run one real corridor with and without `--lateral-resolution` on the same demand, against held-out counts and travel times. If the difference is under the day-to-day floor, the question is closed for cars. CPU only, days.

**What a redesign would cost, if it is ever needed.** `Veh` gets a lateral offset. A lane's order is no longer one leader, so `seg`, `plan`, `exec`, `is_leader`, `lc_neighbors`, `collide`, `detect` and the zones all change. Strips can be a bitmask in a `u32`, so no local arrays are needed. Leader search becomes a bounded scan, with a cost that grows with the scan length. SUMO warns of the same cost. Aimsun caps it by limiting forward view. Months, and every replay and acceptance test reruns. A narrower version can stop at two-wheelers: bikes and motorcycles in a side list per lane, cars untouched. **Not now.**

## Top 5, with next steps

1. **Crossings as occupied-until times.** Add a `Crossing` buffer, a kernel, and a check on turning links. Inputs: 1,917 `crossing=traffic_signals` nodes in the clip (my count), 3,861 push buttons (report 16), flows from city counts. Test: reproduce Trafikverket's figure 9 first, then real DLR turns. Switch `--human-off crossings`.
2. **Kerb events as stopped vehicles.** Honour `<stop>`, load SL's buses and Berlin's 26,143 bus trips, read bay or kerb from OSM. Add timed blockers for loading, and a short manoeuvre at trip ends. Check against HCM's formula on one lane, then ablate on the benchmark. Row 15 follows if one-lane streets jam too hard.
3. **Give-way capacity.** Fit the gap model against the Swiss sites, SinD and inD, with spread as a target, and on Siegloch at high major flows. This is where the current build fails hardest, and where stuck cars sit.
4. **Speed and time step.** Per-edge free-speed factors from probe data, smooth turn shapes, dt 0.5 for every counted run. Hours to days. Refit `--region sweden` afterwards.
5. **En-route rerouting.** A capped share of cars re-asks the route worker on current edge times. Reach it only once demand is real, then compare with day-to-day stability, not just fewer jams.

**Order:** merge physics and human first. 4, then 1 and 2, then 3, then 5. Pick dry, incident-free test days now (rows 10, 11), which costs nothing.

## What only Erik can do

- **Nothing here needs anyone contacted yet.** Pedestrian and cycle counts are report 16's list.
- **Library access:** Milazzo et al. TRR 1578 on pedestrians and right turns; Castrillon & Laval 2018 on buses; HCM 7th edition chapters 19 and 31 for primary formulas. Each would firm up a value I only have second hand.
- **Optional Vissim or Aimsun licence** to run one corridor through a tool with these features. Not required for the ranking.

## Dead ends

- FHWA's often-quoted congestion shares (bottlenecks 40%, incidents 25%, and so on). `ops.fhwa.dot.gov/aboutus/opstory.htm` is gone and the report chapter I opened has no percentages. I did not use them.
- PMC is behind a browser check; EuropePMC's REST full text works. `fullTextXML` gave Loder 2019.
- Paramics and SimTraffic user guides: not open anywhere I tried, as report 15 also found. TxDOT has only a paragraph on SimTraffic.
- Trafikverket's curves are drawn, not tabulated. Render the PDF page: `tv-capacity/raw`, page 122.
- `osmium` on the clip under load timed out for `highway=service`, so I give no count of service roads.
- Pully's sample is a single road link. Use Helsinki or pNEUMA for lateral questions.

## New directions I could not cover

- **Real saturation at many sites.** Hamburg, Perth and Glasgow signal and detector data (reports 11, 13) could give friction by district, with no drone.
- **Lane geometry in pNEUMA.** Athens lanes from OSM would split the 17% into narrow lanes and true two-abreast.
- **All three days of Helsinki**, 170,000 tracks and 2.2 GB, would make the spread and turn measures solid and add queues on multi-lane approaches. Worth it for the benchmark's microscopic level.
- **`SLOTS` 8 and `MAX_ITEMS` 8 in `common.wgsl`.** Caps on approaching cars per link and on items per car are design artefacts, not traffic. No test here shows them binding; a busy major road at a give-way could. Add a counter.

## Sources

Opened in this session unless marked. Local copies from report 15 are under `cars-data/truth/practice/opus-20261101/`.

- **Trafikverket:** [TRVMB Kapacitet][trv], chapter 4, sections 4.7.4, 4.7.5, figure 9 at PDF page 122. [Handbok för kapacitetsanalys med simulering][tvh].
- **Guidelines:** [TfL][tfl]. [NCDOT TransModeler guide][nc], local copy `ncdot-sim`.
- **Vendors:** [Vissim lateral][vl], [Vissim following][vf], [Aimsun micro][am], [Aimsun mixed traffic][am2], [SUMO sublane][sl], [SUMO driver state][ds], [TxDOT on SimTraffic][sim], [HCM in PTV Vistro][vis].
- **Network:** [Loder et al. 2019][loder], full text through EuropePMC. [Paipuri et al. 2020][pai], abstract. [Daganzo, Gayah & Gonzales 2011][dag], abstract. [Taillanter et al.][tai], abstract, buses named, no figure.
- **Friction:** [HCM factors, NPTEL][hcm], secondary. [FHWA 98-106, chapter 5][hcmped] and chapter 4; what I could read of them is model comparison, not field data. [DTU Copenhagen][dtu], landing page, no numbers.
- **Weather:** [Hranac 2006][hr]. [Sadek 2004][sad]. [Manitoba thesis][man2], abstract. [ISHC 1994 record][jap].
- **Models:** [Treiber, Kesting & Helbing 2006][tr]. [Haddad & Geroliminis 2012][had], local PDF; capacity effects shown as curves from its model, with no field values. [2020 simulator study of phone use][phone].
- **Earlier reports:** 02, 03, 04, 05, 06, 07, 09, 11, 15, and data-hunt 15 and 16. `t3-1b36c9cf/research/truth/16-human-build.md`, `t3-1b36c9cf/.../shaders/HUMAN.md`, `t3-1c6fee50/research/physics-provenance.md`.
- **Unverified, search result only:** [NCHRP 900, access density][acc]; [Manhattan double parking][man]; [FORUM8 on S-Paramics][p]; Saifuzzaman on hand-held calls; the Indonesian, Malaysian and Dutch darkness papers; Castrillon on bus short-block effects.

[trv]: https://bransch.trafikverket.se/globalassets/dokument/trvmb_kapacitet_och_framkomlighetseffekter.pdf
[tvh]: https://bransch.trafikverket.se/contentassets/32ce05ecc3ac458bb8ecb802e8e2da54/handbok_for_kapacitetsanalys_med_hjalp_av_simulering.pdf
[tfl]: https://content.tfl.gov.uk/traffic-modelling-guidelines.pdf
[nc]: https://connect.ncdot.gov/resources/safety/Teppl/TEPPL%20All%20Documents%20Library/NCDOT%20CONGESTION%20MANAGEMENT%20SIMULATION%20GUIDELINES%20-%20Effective%2010-01-2016.pdf
[vl]: https://cgi.ptvgroup.com/vision-help/VISSIM_2022_ENG/Content/4_BasisdatenSim/FahrverhaltensparameterQuerverhalten.htm
[vf]: https://cgi.ptvgroup.com/vision-help/VISSIM_2025_ENG/Content/4_BasisdatenSim/FahrverhaltensparameterFolgeverh_Wied99.htm
[am]: https://docs.aimsun.com/next/latest/UsersManual/MicrosimulationModellingVehicleMovement.html
[am2]: https://docs.aimsun.com/next/latest/UsersManual/MixedTraffic.html
[sl]: https://sumo.dlr.de/docs/Simulation/SublaneModel.html
[ds]: https://sumo.dlr.de/docs/Driver_State.html
[sim]: https://www.txdot.gov/manuals/des/tsp/chapter-4-traffic-analysis-methodology--tools--and/4-3-analysis-tool-description-and-selection-method/4-3-10-simtraffic.html
[sm]: https://web.mit.edu/cami/Public/CLA_SimMobilityST_TRB_2017.pdf
[vis]: https://cgi.ptvgroup.com/vision-help/VISTRO_2021_ENG/Content/PTV_Vistro_UserManual_EN/HCM_2000_for_Signalized_Intersections.htm
[loder]: https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6841661/fullTextXML
[pai]: https://www.frontiersin.org/articles/10.3389/ffutr.2020.00001/pdf
[dag]: https://its.berkeley.edu/node/4628
[tai]: https://arxiv.org/abs/2310.06531
[hcm]: https://archive.nptel.ac.in/content/storage2/courses/105101008/574_SignalLos/point5/point.html
[hcmped]: https://www.fhwa.dot.gov/publications/research/safety/pedbike/98106/chapter5.cfm
[dtu]: https://orbit.dtu.dk/en/publications/pedestriansand-cyclistseffect-on-capacity-of-right-turn-movement-/
[hr]: https://ops.fhwa.dot.gov/publications/weatherempirical/sect0.htm
[sad]: https://onlinepubs.trb.org/onlinepubs/trispdfs/00983592.pdf
[man2]: https://mspace.lib.umanitoba.ca/items/5fbe2a86-a1ab-4042-8e25-e00300c9db6a/full
[jap]: https://trid.trb.org/View/415229
[tr]: https://ar5iv.arxiv.org/html/cond-mat/0404736
[had]: https://www.strc.ch/2012/Haddad_Geroliminis.pdf
[phone]: https://pmc.ncbi.nlm.nih.gov/articles/PMC7068547/
[fh]: https://ops.fhwa.dot.gov/congestion_report/chapter2.htm
[acc]: https://www.nationalacademies.org/read/25342/chapter/9
[man]: https://www.itskrs.its.dot.gov/node/209178
[p]: https://www.forum8.co.jp/topic/up99-seihin12-e.htm
