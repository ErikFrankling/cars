# 02: Jinan camera trajectories, audited and run on `cars`

Date 2026-11-02. Source: Yu et al. 2023, [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10582153/), which I read in full, including Figures 8, 12 and 13. [Data on figshare](https://doi.org/10.6084/m9.figshare.c.6676199.v1), [code](https://github.com/tsinghua-fib-lab/City-Camera-Trajectory-Data). Scripts are in `scripts/jinan/` on branch `t3/91f2bc65`. Data and runs are in `/home/erikf/projects/personal/cars-data/datasets/jinan-yu2023/`.

Grades: MEASURED (I computed it from the data or a run), PROVIDER CLAIM (the paper says so), MODELLED, UNVERIFIED.

## The answer

**This is not yet the first real all-vehicle validation. It is the best test bed we have found, and `cars` fails it on this net, mostly because of the map and generated signals, so the failure says little about the driver model.**

- **Useful:** whole-city camera timing for a full day. Camera-to-camera times give a real congestion curve that depends on neither our demand nor the paper's route model. Median leg speed is about 34 km/h at night and 22 km/h in both peaks. [MEASURED]
- **Not observed:** routes. The median trajectory has 2 camera records, its first and last. An estimated 6% of the points in between have a record, and the rest are inferred by a model trained on Amap GPS. Route choice is therefore mostly the model's. [MEASURED pattern, my inference of what it means]
- **Doubtful:** "almost all vehicles". 21.8% of same-vehicle trajectory pairs overlap in time, which one car can't do. Recorded driving is 4.3 km per "vehicle" per day. [MEASURED]
- **The result on `cars`:** at 1% and 10% it runs almost clean, but 2 to 2.5 times too fast, even at night when nothing is congested. At 30% it jams in pockets. At 100% in the morning it holds 28,037 cars at 10:00 and still climbing, against 14,925 in the data, with 11,691 teleports. [MEASURED]
- **Coincidence warning:** at 100% the overall trip speed matches, 21.2 against 21.3 km/h. Don't read that as success. The median simulated trip takes half the real time, a long tail jams, per-trip correlation is only 0.32, and 15% of eligible trips never finish.

Not done: 100% over a full day and the actuated-signal sensitivity. See [What did not run](#what-did-not-run).

## Ranked table

| Rank | Source | What it gives | Share of vehicles | Downloaded | Use |
|---|---|---|---|---|---|
| 1 | Jinan, 17 Oct 2022 | One day, whole city, camera timing, inferred routes | Claimed near-full, not established (below) | Yes, all 3 files, checksums match | Congestion truth, OD prior, waypoint test of route choice |
| 2 | Shenzhen, 3 days, 08:00 to 20:00 | Same method, 1 to 4 districts | 44% of the government's figure, PROVIDER CLAIM | No, listing only (2.07 GB of trajectories) | Untouched second city for holdout |

### Record for Jinan

| Field | Value |
|---|---|
| Measures | Vehicles matched across traffic cameras by appearance and plate features, paths between cameras inferred |
| Area and period | Jinan whole city, Mon 17 Oct 2022, 00:00 to 24:00 |
| Share of all vehicles | 963,125 "vehicles" against about 0.89 M average weekday from the traffic bureau, PROVIDER CLAIM. The definition isn't given and the number isn't a clean count, see below |
| Sampling | 1 frame per 2 s, about 19 M records, PROVIDER CLAIM |
| Level | Route-level in format, camera-level in evidence |
| Validation | Re-ID F1 0.863 on 423 GPS vehicles, **in Shenzhen only**. The paper says Jinan had no real trajectories. Jinan was checked by one case study and flows against the bureau on two road types |
| Access and licence | Open download. figshare says CC0, paper is CC BY 4.0, road data is OSM ODbL. Commercial use looks allowed; check ODbL for derived networks |
| Covers Sweden | No |
| Needs served | Demand (partly), routes (weakly), congestion truth (yes). Not maps or signals |
| Work to integrate | Done for a first pass, in `scripts/jinan/` |

## 1. Audit

All MEASURED unless marked.

**The paper's counts reproduce exactly:** 1,184,417 trajectories, 963,125 vehicles, 8,908 nodes, 23,312 edges. There are 1,651 camera nodes, 18.5% of all nodes, and 62 of them have no record all day. 1,838 is the paper's camera count; several cameras can share a node.

**The network is clean.** 99.73% of steps lie on a published edge, and the other 0.27% are a node repeating itself. All points are in the largest connected part of the graph. Length equals the sum of edge lengths and times never go backwards.

| Departures by hour | 00-05 | 06 | 07 | 08 | 09 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Thousands | 36 | 68 | 81 | 81 | 84 | 74 | 71 | 68 | 77 | 79 | 74 | 81 | 76 | 60 | 58 | 44 | 37 | 24 | 11 |

**Trip length:** median 2.0 km, mean 3.5 km, 29% under 1 km, and only 3.9% over 10 km. Median duration is 357 s and mean is 650 s. This matches the paper's Figure 8. These are not whole trips.

**Five things the paper doesn't tell you:**

1. **Most points are inferred.** Each interior timestamp ends in `.0` 10.03% of the time at non-camera nodes, which is pure chance, but 39.9% of the time at camera nodes and 97.5% of the time at first and last points. So whole-second times mark real records. That's 3.75 M observed points of 16.98 M. An estimated 11.6% of interior passes through a camera node have a record, and 5.6% of all interior points. This reading is mine, the paper doesn't document it.
2. **One "vehicle" is sometimes two cars.** Of 221,292 consecutive trajectory pairs on one ID, 21.8% overlap in time. That covers 44,724 of the 171,279 multi-trajectory IDs and 7.8% of all trajectories. The other direction also looks bad: mean 1.23 trajectories per ID, 82% with just one. The paper's Table 4 gives "expansion" 2.16. I didn't open the earlier paper that defines it, so what it means for vehicle counts is UNVERIFIED. If it means one real car splits into about 2 clusters, then 963,125 isn't a vehicle count, and its closeness to the bureau's 0.89 M proves little.
3. **A "trip" runs through any stop under 30 minutes.** Not one same-vehicle pair has a gap between 0 and 30 minutes, and 14.8% of camera gaps exceed 10 minutes. So durations contain parking. I also use a stop-free set: every camera leg between 5 and 130 km/h, 84% of trajectories.
4. **Long trajectories are mostly not trips.** Over 10 km they are 3.9% of trajectories but 27.8% of vehicle-km. 58% of those from 10 to 20 km revisit a node and their median length is 2.1 times the straight-line distance. Over 20 km it's 96% and 11.4 times. They are tours or false joins.
5. **The data changes character at 18:00.** Recorded points per 100 fall from 24 to 19 to 17, steps per camera leg rise from 5.8 to 7.9, and points per 15 minutes jump from about 240 k at 18:30 to 391 k at 19:00. Inferred edge speed jumps from 22.6 to 28.9 km/h, while camera leg speed moves far less, 22.7 to 24.6. Figure 13 also shows the data falling away from the bureau's counts at that time on trunk roads. The paper's speed check (Figure 12) stops at 19:00. **Use camera legs, not edge speeds.**

**Per-road counts.** 42.5% of edges have no traffic at all, and 73% of residential edges. This is the missing first and last mile, plainly.

| Class | km | Vehicle-km | Peak hour veh/h, median | 90th pct | Max |
|---|---:|---:|---:|---:|---:|
| Primary | 880 | 1.54 M | 133 | 428 | 1,191 |
| Secondary | 1,192 | 1.24 M | 66 | 316 | 2,063 |
| Trunk | 506 | 0.74 M | 85 | 458 | 1,001 |
| Tertiary | 1,794 | 0.42 M | 3 | 115 | 702 |
| Residential | 2,040 | 0.07 M | 0 | 12 | 510 |

These flows look low for main roads. At the 90th percentile a 3-lane primary carries about 140 veh/h per lane. My opinion is that the data misses a good part of real traffic, and I can't put a number on it. Figure 13 (bin and sites not stated) tracks the bureau's counts well off-peak, but at peaks the bureau is clearly higher: read off the figure, about 250 against 180 on trunk around 18:00, and about 175 against 125 on primary around 17:30.

**Speeds reproduce the paper once I use its method.** On the 10% sample, a robust speed per road gives trunk 33.5, primary 30.3, secondary 27.8 and tertiary 25.7 km/h for 08:00 to 19:00. Figure 12 (read off) has "ours" at about 38, 31, 27 and 22, and Amap at about 46, 36, 32 and 27. A true space-mean, with stops included, gives only 17 to 18 km/h. That gap is stops and false links.

## 2. Real behaviour against report 06

Sample: 193,825 trajectories at 500 m or more. Edge times per period come from the data itself. "Bound" uses observed cameras only: the shortest path forced through them, which is the part the route model can't have produced. It can only understate a route's excess.

| | Report 06, Minneapolis GPS | All | 0.5-2 km | 2-5 km | 5-10 km | Over 10 km | Over 5 km with 4+ cameras |
|---|---:|---:|---:|---:|---:|---:|---:|
| On the shortest-time path | 34% (commutes 13.5%) | 53% | 81% | 45% | 20% | 4% | 10% |
| Within 30 s | about 50% | 63% | 89% | 59% | 29% | 6% | 16% |
| Within 5 min | almost 90% | 91% | 99.7% | 96% | 77% | 24% | 54% |
| Bound: on the path | | 73% | 93% | 72% | 45% | 13% | 19% |
| Bound: within 5 min | | 93% | 99.9% | 97% | 84% | 32% | 62% |

- **The match with report 06 on "all trips" looks like a coincidence of fragment length.** 40% of these trajectories are under 2 km, where there's rarely a choice. Above 5 km real routes look much further from shortest than 06 assumes, but false joins and tours inflate that, so this doesn't refute 06's tolerance of about 30 s to a few percent. It can't confirm it either.
- **Share of cars by route can't be measured here.** Between the 4,973 camera pairs with at least 30 trajectories, the top inferred route holds 85% and the effective number of routes is 1.26. The observed camera sequences give 48% and 4.0, but they vary mainly because cameras record so few passes. The firm evidence: of the 52% of trajectories with an interior record, 21.7% have one off the pair's top route. With so few passes recorded, I read real route diversity as well above what the inferred routes show. The 5-route limit in 06 §8.3 stays untested.
- **Repeat routes day to day:** can't be tested, one day and few repeat IDs.
- **Day shape.** 06:00-18:00 holds 77%, 18:00-22:00 17% and 22:00-06:00 6%. It is flat: the busiest hour is 7.1% of the day, 1.11 times the 06:00-18:00 mean. That is flatter than the bureau's road counts in Figure 13, so some of the flatness probably comes from the data. Stockholm's uniform split inside bands is less wrong here than I expected, but don't take this as support for it.
- **Report 06's teleport warning holds on a real city.** See the 10% runs below.
- **Report 06's order, supply first, holds too.** See the hot spots below.

## 3. The scenario

- **Net.** Built from the paper's own graph, so every trajectory step is an edge and no map matching is needed. Lanes, speeds and signals come from a fresh OSM pull (November 2026, not 2022) matched by coordinates. 72% of edges matched. Lanes are tagged on 9.7% of edges (trunk 44%, primary 24%), and the rest use the class median from tagged Jinan edges. `maxspeed` is tagged on 2.4%, and the rest use netconvert's OSM typemap. 133,745 lanes in total.
- **Signals.** 999 nodes: 418 from OSM tags, plus 581 by a rule I set before any run (camera node, 3 or more arms, 3 or more main-road approaches). Programs are netconvert's generated 90 s fixed plans. The paper has no signal data.
- **Junction repair.** The paper moved merged junctions up to about 20 m off the road and ran each edge out and back. So a straight road shows a spike and netconvert calls it a U-turn. I cut those stubs on 7,840 edge ends at 2,682 nodes, which reduced missing movements from 2.14% to 0.45% of passes. I then added the remaining 527 observed movements. Afterwards 0.04% of movements are still broken, which splits 0.47% of routes.
- **First and last mile: left out, not invented.** A vehicle appears at the start of its first edge at the time of its first camera record, at maximum safe speed, and leaves at the end of its last edge. Any extension would be invented demand. The cost is that minor roads are empty and main-road merges miss traffic.
- **Dropped:** 12,189 trajectories (1.03%) above 130 km/h end to end, as false links. **Result:** 1,178,337 routes, sampled by vehicle and nested, 1% inside 10% inside 30%.
- **Nothing is fitted.** No parameter was set from a simulated result. The urban-speed run below is a labelled sensitivity.

## 4. Runs

CPU Vulkan only, default driver model, seed 1. The day runs used lavapipe on the homelab, and the 100% window used llvmpipe on the PC. Real trip speed is the stop-free set, by first-camera to last-camera time. Road-hour counts test almost nothing while cars keep moving, since the sim drives the same routes. They only show where it stops carrying traffic.

| Run | Trips | Arrived | Teleports | Collisions | Road-hour count sim/data, R² | Trip speed real / sim km/h | Median trip time sim/real | Per-trip r |
|---|---:|---:|---:|---:|---|---|---:|---:|
| 1%, day, teleports on | 11,703 | 11,702 | 0 | 0 | 0.99, 0.79 | 21.4 / 53.6 | 0.44 | 0.80 |
| 1%, day, teleports off | 11,703 | 11,702 | n/a | 0 | same as above, since no teleport happened | | | |
| 10%, day, on | 117,584 | 117,563 | 15 | 2 | 0.99, 0.97 | 21.4 / 53.1 | 0.44 | 0.79 |
| 10%, off, stopped at 17:23 | 89,856 so far | 87,663 | n/a | | | | | |
| 30%, day, on | 351,643 | 350,632 | 7,517 | 305 | 0.97, 0.94 | 21.4 / 24.2 | 0.46 | 0.18 |
| 100%, 06:00-10:00, on | 284,609 | 256,571 | 11,691 | 460 | 0.79, 0.75 | 21.3 / 21.2 | 0.50 | 0.32 |
| 100%, off, killed at 09:10 | 210,675 so far | 170,242 | n/a | | | | | |

**The 10% teleport test is the clearest result here.** With teleports on, the day shows 15 teleports and about 480 cars on the road. With them off, cars on the road climb steadily, 466, 708, 914, 1,374, 1,824, 2,179 at 08:00 to 17:20. So 15 teleports hide about 1,700 stuck cars at a tenth of the demand. These are deadlocks at a small number of places. I didn't work out whether the net or the kernel causes them.

**Cars on the road at 100%**, in the data and in the sim. The data figure includes parked cars inside a trajectory, so if anything it's too high:

| Time | Data | Sim, teleports on | Sim, teleports off |
|---|---:|---:|---:|
| 07:00 | 13,101 | 9,708 | 10,788 |
| 08:00 | 14,196 | 15,699 | 22,810 |
| 09:00 | 14,879 | 21,842 | 37,516 |
| 10:00 | 14,925 | 28,037 | not reached |

The real city stays flat from 07:00 on. The sim climbs without stopping. At 09:00 to 10:00 it passes only 70% of the data's road passes.

**Speed by hour** (trip start hour, km/h). Real camera legs and the sim's trip speed aren't the same measure, so compare the shape:

| Hour | Real camera leg, median | Real trip, stop-free | Sim 10% | Sim 30% | Sim 100% (arrived only) |
|---:|---:|---:|---:|---:|---:|
| 03 | 34.0 | 27.1 | 55.8 | 56.9 | |
| 07 | 22.2 | 19.6 | 53.6 | 30.1 | 16.7 |
| 08 | 21.8 | 20.0 | 53.8 | 26.1 | 21.7 |
| 12 | 27.2 | 23.0 | 53.0 | 20.8 | |
| 17 | 22.7 | 20.0 | 53.8 | 21.2 | |
| 19 | 27.7 | 20.3 | 52.7 | 26.4 | |
| 21 | 29.6 | 21.4 | 51.8 | 34.0 | |

Later hours at 100% look fast only because mostly short trips finish before the run ends.

Reading it:

- **Free-flow is wrong before congestion starts.** At 03:00 the sim runs about twice as fast as real trips. netconvert's typemap gives primary, secondary and trunk roads 100 km/h and tertiary 80, and hardly any edge overrides it. That was my poor default. As a sensitivity only, I used usual Chinese urban design speeds (80 km/h on trunk down to 30 on residential, from memory of CJJ 37, not opened). Night speed then falls from 57 to 37-40 km/h at full night demand, against 34 for real camera legs. That run stopped at 04:44, by my own time limit, so I have edge speeds only and no trip comparison.
- **The shape is wrong too.** Real speed drops by about a third from night to peak and recovers at midday. At 10% the sim barely drops. At 30% it keeps falling until 16:00 and recovers only late in the evening, because the jams don't clear. Real traffic doesn't show that.
- **The congestion is local and looks man-made.** At 30%, the top 10 edges hold 36% of excess hours and the top 50 hold 69%, while under 10 km/h covers just 1.5% of used road length. Median trips stay fast while a tail is catastrophic. 87% of the excess is on edges with guessed lanes. The worst edge, e21511, is a 3-lane primary where 90% of traffic continues along the corridor. netconvert calls that a right turn from one lane with 7% green. That's about 126 veh/h of capacity by my arithmetic, against a flow of 2,588 a day at 30%, so a queue that never clears is the expected result, not a finding about drivers. At 100% the top 500 edges hold 87%.

## 5. Plainly: is this the first real all-vehicle validation?

**Not yet, and not in the form we hoped.**

What it is: the first whole-city, full-day dataset we've tested with independent congestion timing, and a demand that wasn't fitted to counts. A simulator that can't reproduce a camera-leg speed curve with these trips has a real problem, and this is a fair place to show it.

What's weak:

1. **Routes are mostly inferred** from an Amap-trained prior, and timing inside a leg is too. Route-level validation isn't available, only waypoint checks.
2. **Road counts aren't independent.** The sim drives the same routes, so a 99% match means nothing. The bureau's counts would be independent, but only Figure 13 is public.
3. **Share of all vehicles is unknown.** Vehicle IDs are unreliable, and the peak flows and Figure 13's peaks suggest undercounting. If demand really is short, our sim's collapse at this demand looks worse still.
4. **Trips are fragments** with parked time in them and false joins among them. No first or last mile.
5. **No signals and few lane tags.** This dominates the current result. OSM is from 2026, the traffic from 2022.
6. **No vehicle classes,** one day only, one Monday. Re-ID accuracy was measured in another city. E-bikes and buses aren't there as separate traffic. [e-bikes: my knowledge of Chinese cities, UNVERIFIED for this dataset]
7. **The driver model is European-fitted.** Chinese junctions work differently: gap acceptance, right-turn-on-red and mid-block U-turns are common as far as I know [UNVERIFIED]. 0.31% of movement passes are U-turns at a node, which is modest but measured. This matters later. With this net we can't yet tell a driver error from a supply error, so **no conclusion about the driver model follows from these runs.**

## Top 3 recommendations

1. **Repair supply, then rerun at 100%.** Keep the net, and add the three changes in `build_net.py`: urban speed defaults stated in advance, green splits from the data's turning flows (Webster), and lanes per movement from the same flows. Turning flows come from inferred routes, but none of this looks at speeds. Pre-register the test now: camera-leg speed by hour, stop-free trip time by length band, and cars on the road. **Next step:** add those to `build_net.py`, then run a 100% day on the GPU, since CPU Vulkan can't hold it.
2. **Make camera legs our congestion truth, and Shenzhen the holdout.** Export a table of leg speed by hour and road class from observed points only. Never validate against edge speeds. **Next step:** run `hour_artifact.py` as the basis, then download Shenzhen's 2.07 GB and leave it untouched until the Jinan settings are frozen. Note that Shenzhen covers only 08:00 to 20:00.
3. **Use it as an OD prior and test route choice on waypoints.** Take only first and last cameras, drop IDs with overlaps and tours over 10 km, and run 06's assignment loop from these ODs. Then measure how often real interior camera records lie on simulated routes. That's the route-choice test we've never had and it doesn't depend on the paper's routes. **Next step:** after recommendation 1, because assignment over false bottlenecks would teach us nothing.

## What only Erik can do

- **Allow a GPU run** of the 100% day. This brief forbids the GPU.
- **Decide whether to write to the authors.** They have what would turn this into a much stronger test: a flag for recorded against inferred points, the bureau's counts behind Figure 13, and any signal plans. Corresponding author per the paper is Huan Yan, Tsinghua; I didn't look up an address. Draft for Erik to send himself:

> Hi, I'm using your Jinan camera trajectory data from the 2023 Scientific Data paper to test a traffic simulator. It's been really useful. I have a couple of questions. Is there a way to tell which points in a trajectory are real camera records and which are inferred? I'm guessing whole-second timestamps are the records, but I'd like to check that. Also, could you share the traffic bureau counts behind Figure 13, or say what sites and time bins they use? And do you know if signal timing for Jinan is available anywhere? Thanks a lot, Erik

## Dead ends, so nobody repeats them

- **100% over a full day on CPU Vulkan.** It crashes: `Buffer binding 15 range 229531320 exceeds max_*_buffer_binding_size limit 134217728`. The limit works out to about 620 k trips per run. Use a window or the GPU. Crash log: `runs/p100_t300/stderr.txt`.
- **Route shares or shortest-path tests on inferred routes alone.** They mostly measure the paper's prior and fragment length.
- **Edge speeds as truth after 18:00.** See the audit.
- **netconvert connection files.** Stating one movement for an edge stops netconvert guessing that edge's other movements. My first attempt raised broken movements from 298 k to 788 k. Restate them all, as `broken_moves.py` now does.
- **netconvert's OSM typemap for Chinese cities.** 100 km/h on urban primaries.
- **Long CPU jobs on the PC.** The lag guard killed my 100% run after 27 minutes, rightly. The homelab was at load 180 to 220 at the time, for reasons outside my jobs as far as I can see, with `cars` down to 2 steps/s.
- **Using `heavy sync` while a job runs.** It deletes worker-only outputs. Use `--no-sync` and pull first.

## What did not run

- **100% full day:** the buffer limit above. I ran 06:00 to 10:00 instead, so **no 100% evening peak**, and that run starts from an empty network at 06:00.
- **100% with teleports off:** killed by the lag guard at 09:10, so no trip comparison, only the counts of cars on the road.
- **10% with teleports off:** I stopped it at 17:23 when the homelab fell to 11 steps/s.
- **30% with teleports off:** never ran, because the worker stalled. Dropped.
- **Actuated signals at 30%:** it never got going on the stalled worker, and I stopped it. The net is built at `scenario_act/` with a route window ready.
- **Urban-speed runs:** night only, to 04:44. The 10% day-window route file is ready and unrun.

## New directions noticed

- Refs 23 and 24 in the paper are two more Scientific Data city datasets, one from holographic flow resampling and one synthetic. Both assume near-complete camera coverage. Not opened.
- The earlier KDD 2022 paper by the same group should define "expansion" and explain the recovery model. Not opened.
- The same camera approach should exist elsewhere in Chinese cities, and any city with plate-based enforcement cameras could produce this data, Stockholm's congestion charge among them. See report 06 for what that would need.
- Camera-leg speed by hour is cheap to compute and could be compared directly with Amap or other probe products, if any agent finds one for Jinan.
