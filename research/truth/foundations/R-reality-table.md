# R: The reality table (rung 1)

Done 2026-11-02. Real data only: no simulation, no GPU, no locked site opened, nobody contacted. Tables are in `research/truth/berlin2019/real_*.csv`, code in `scripts/reality/`. Definitions were committed before computing (below, and 74ffe81). Changes made after seeing data are listed under "Changed after looking".

Grades: **MEASURED** from data I opened, **ESTIMATED** a formula on measured inputs, **MODELLED** MATSim, **INVENTED** no source.

## The answer

- **Real jams are common and repeat, but which edge jams differs a lot between days.** The district has 97 trusted jam places on main roads at a third of free speed, and 115 at half. A real day catches 72-81% of the list built from the other seven days, and 22-40% of that day's places aren't on the list. So rung 4's bar of "≥ 60% caught, ≤ 40% false" is about what one real day scores. The false side has no margin.
- **The morning isn't the peak.** Cars on the road peak at 16-17 h: 18,500-21,800 at 100% over the cut, against 15,700-18,500 at 08-09 h. Rung 7 and any "healthy" number must use the afternoon too.
- **The measured Berlin flows can't settle 1,640 against 1,900.** Queue-present flow is a median 619 veh/lane/h, far below what either implies at Hamburg's main-road green. They do rule out one end: 1,285 fails the upper test at 17% of sites. Use **1,750, sweep 1,640-1,900**. Nothing measured supports 2,100.
- **Close-spaced signals in Hamburg are linked but don't always clear.** Under 50 m, 77% of through pairs are linked against 29% at 50-150 m. The offset is small, a median +2 s. But only 46% clear on my test, and our invented programs score as well or better. So invented offsets alone are not shown to be the cause of the jam roots on short approaches.
- **B1/B5 has a real jam and known cycles but no loop on it,** so it can't test discharge. Use **Leipziger Straße-Gertraudenstraße eastbound** for discharge, and B1/B5 only for place and time.

## 1. `real_jams.csv`: the real bottlenecks

**Definition.** Edge's 15-minute median probe speed under a third of its free speed (`threshold=third`; also `half`), at least 5 probes, for 30 minutes or more. Free speed is the edge's 90th percentile. Joined across adjacent edges that overlap in time, by AM (05-11 h) and PM (12-21 h). A row needs 2 of 8 days. Loop rows use the same fractions on hourly speed. `tier` A: main road, at least 4 days, at least 200 m on a median day, at least 10 probes. B: other main-road rows. C: local roads, unverified.

**Sample check, as written beforehand.** 960 tuning site-hours have loop speed under half of free, on 72 sites. The one-third rule on the same edge fires in at least one interval on 67%, and in a full 30-minute episode on 56%. It misses 44%, under the written limit of 50%, so one third stays primary. The other way, of 903 site-hours with an episode, 86% have the loop under 0.7 of free and 60% under half. At the half rule those are 60% and 30%: half catches more and is wrong more often.

**What it shows** (tier A, one third):

| Scope | Places | Repeat on 8 of 8 days, median | |
|---|---:|---:|---|
| District | 97 | yes | 69 arterial, 22 tertiary and local, 6 motorway |
| Other Berlin main roads | 467 | 7 of 8 | |

Longest in the district: AVUS and the A100 15:22-17:45, about 19 km on a median day. That's joined stretches, so an upper limit, and probably several bottlenecks. Then Zossener Straße-Gitschiner Straße-Mehringdamm 08:00-10:00 (2.0 km), Mehringdamm-Gneisenaustraße 13:15-16:15 (2.0 km), Kurfürstenstraße-Potsdamer Straße 16:30-18:15 (1.65 km), Klingelhöferstraße-Reichpietschufer 13:00-19:00 (1.35 km), Tempelhofer Damm 08:30-09:00, Martin-Luther-Straße 07:45-10:00. Loops agree at Klingelhöferstraße (TE223 under a third on 7 of 8 days, 16-19 h) and Gertraudenstraße (TE367, 5 of 8, 17-19 h).

Cause is filled on 25 of the 564 tier A rows: 13 motorway merge or diverge, 12 lane drop. Everything else is blank. A head junction type is there, but a signal at the head is not a named cause. 39 rows carry `flag_parallel_road`: free speed over 1.4 times the limit, such as Detmolder Straße beside the A100, so they probably read motorway probes. Don't test against those.

**Noise** (`real_jams_noise.csv`), main roads in the district, median of 28 day pairs:

| | Jaccard of jam edges | Day A's jam edge-intervals also jam on day B | Top 20 shared |
|---|---:|---:|---:|
| Third, AM | 0.25 | 0.19 | 0.30 |
| Third, PM | 0.36 | 0.35 | 0.40 |
| Half, AM | 0.46 | 0.33 | 0.38 |
| Half, PM | 0.59 | 0.40 | 0.55 |

Lists built on 4 days against the other 4: 75-78% of places found at a third, 91-92% at half; Jaccard of edges 0.53 and 0.66. One real day against the other 7: **caught 72-81%, false 22-40% at a third; caught 80-91%, false 7-11% at half.** Half is the steadier list. I'd score rung 4 on both and quote this floor beside it.

**Measured:** speeds, days, places. **Not measured:** real queue length. Extent is km of slow edges, with probes on a 100 m grid. Local roads have no loops to check against, and their rows include speeds under 1 km/h that look like stationary probes, so tier C isn't a target.

**Jam recovery** (`real_jam_clusters.csv`). Main roads in the box, space-time clusters at a third: median duration 15 min, p90 30, p99 105, longest 690. 2.3% last over an hour, 0.3% over 3 hours. Tail exponents: size 2.30 (2.24-2.37 across days), duration 4.44 (4.21-4.98). Zhang's 2.34 for size looks close, but his bins are 1 minute and these 15, and his duration exponent of 3.13 isn't comparable here for that reason. Use these numbers for simulated runs on the same bins.

## 2. `real_capacity.csv`: highest real flow

**Definition.** Flow per lane per hour on 8 days, 155 stations (63 in the district, 92 elsewhere) and one apart. Queue-present hours (loop under 0.7 of site free) are kept apart from others. Each has a certainty grade: **A** loop under half and probes low for at least 2 of 4 intervals; **B** loop under 0.7 and probes low at least once; **C** loop alone; `none`. `measures_capacity` is `yes` with at least 3 A or B hours on at least 2 days: 75 stations.

**What it shows.**

| Stations with `yes` (75) | veh/lane/h |
|---|---:|
| Highest flow, queue present, median site | 619 |
| The same, p90 of sites | 859 |
| Highest with no queue, median site | 620 |
| Highest single lane at any time, median site | 736 |
| Highest single lane at any station | 1,259 (Saatwinkler Damm, one of two lanes measured) |

At the median site, flow with a queue equals flow without one (ratio 0.97). A hourly queue-present flow is mostly not a full hour of saturation, since the queue may fill only part of the hour. **So for the "reach 0.85 of table capacity" test, grade A or B flow is a lower bound on capacity, and failing it doesn't by itself prove the table wrong.** Only 5 of the 75 have an A grade at their highest hour, and 57 have B.

**Motorways.** All trusted motorway stations are locked. The one unlocked station, TE002 on the A115, is weak by map match and is kept apart as `unsplit`: 1,652 per lane with no queue, top lane 1,961, 1,476 with a queue. One station. Motorway capacity on tuning data is otherwise unknown.

**Saturation: can Berlin settle it? No, only one end of it.** Berlin has hourly loops and no signal plans, so `s` can't be measured here. Only the product `s·g/C` shows. Report 25's 17 sites are not in Berlin: Athens 7 (median 1,636), Los Angeles and Atlanta 8 (1,735), Braunschweig 1 (1,800, 53 headways, on a Sunday), Changchun 1 (1,284, mixed traffic). The band of 1,800-2,100 came from report 04, not from a measurement here.

Share of stations at each table capacity, `s·g/C`, with Hamburg's longest-green connection per light (p10 0.47, p50 0.62, p90 0.76) and its median connection (0.30):

| s | g/C 0.30 | 0.47 | 0.62 | 0.76 |
|---:|---|---|---|---|
| 1,285 | over 95%, reach 93% | over 61%, reach 75% | **over 17%, reach 33%** | over 3%, reach 12% |
| 1,640 | over 85%, reach 88% | over 21%, reach 40% | over 3%, reach 11% | 0%, reach 1% |
| 1,750 | over 78%, reach 88% | over 10%, reach 31% | over 1%, reach 5% | 0%, reach 1% |
| 1,900 | over 69%, reach 81% | over 6%, reach 17% | 0%, reach 3% | 0%, reach 0% |

"Over" is top lane above 1.1 × capacity (F040). "Reach" is queue-present flow at least 0.85 × capacity on `yes` stations (F045).

- **Upper test.** At main-road green, 1,285 fails at 17% of stations. 1,640 and up pass. Over-limit stations at green 0.30 mean those lanes get more green than Hamburg's median connection, which is expected for a main road.
- **Lower test.** At main-road green no `s` reaches: 11% at 1,640, 3% at 1,900. Real queue-hour flows imply effective `s·g/C` of about 620 per lane, which is g/C 0.33-0.38. So the difference isn't `s`. It's green, partial queues, lanes averaged with turn lanes, and buses. F045 at 0.85 **will fail on most sites with any s on Hamburg's main-road green.** Rung 3 should expect that and name these causes, or use the grade A and B stations with an approach-specific green, or it will reject a sound table.

**What the movement table should use: s = 1,750 through, sweep 1,640-1,900.** My reasons, an opinion on measured inputs: the western signalised sites, weighted by site, are 1,756 (9 sites: US and Braunschweig). 1,636 is pulled down by Athens, with motorcycles and narrow lanes, and by one Chinese site. The only German value is 1,800 on a Sunday. Report 25 also takes 3,600 over a median headway, which probably runs slightly above real flow, since headways skew long. 1,285 comes from one site unlike Berlin, and Berlin's flows reject it. 2,100 has no measured site. This changes step 3's verdict: **Krauss at 1,895 and the physical driver at 1,714 are both in band, not just Krauss. The human driver at 1,500 is out.** **What would settle it:** one Berlin queue count with a stop watch, or any real headway data in Germany on a weekday.

## 3. `real_free_speed.csv`: free speed by class, probes closed against loops

**Definition.** Probe volume-weighted speed, `v_med` (median over the edge's cells, as earlier work) and `v_hm` (harmonic over cells, closer to what a crossing car averages). Night 01-05 h, early 05-06 h, and 06-07 h. Closure is loop against probes on the same edge and hour at tuning sites.

| Class, district | 01-05 h `v_med` | **05-06 h `v_med`** | 05-06 h `v_hm` | 06-07 h `v_med` | 06-07 h `v_hm` | Map limit median | Sim 10% day |
|---|---:|---:|---:|---:|---:|---:|---:|
| Motorway | 78.5 | **84.1** | 79.8 | 75.1 | 70.5 | 80 and 60 on links | 68 |
| Arterial | 36.4 | **40.1** | 35.8 | 36.6 | 31.8 | 50 | 34 |
| Local | 30.8 | **38.7** | 34.7 | 35.0 | 30.9 | 30-50 | 28 |

The 8-day range is ±1-3 km/h. Earlier numbers reproduce: 75, 37, 35 at 06 h. The hourly export matches this extract to 0.03 km/h.

**Night isn't free speed in the probes.** Deep-night probes run slower than 05-06 h (arterial 36.4 against 40.1) while loops don't move at all (48.6 against 48.9). So that dip is who is in the fleet at night, not traffic. **Use 05-06 h as free speed.** It's also clear 06-07 h isn't free: 11% below on motorways, and 9-10% on the others.

**Closure, loop over probes** (median site, 86 secondary, 59 primary, 8 tertiary; p10-p90 about 0.88-1.3):

| | 01-05 h | 05-06 h | 06-07 h | Peak hours |
|---|---:|---:|---:|---:|
| Primary, over `v_med` | 1.05 | 1.06 | 1.09 | 1.19 |
| Secondary, over `v_med` | 1.04 | 1.06 | 1.05 | 1.15 |
| Tertiary, over `v_med` | 1.25 | 1.11 | 1.20 | 1.31 |
| Primary, over `v_hm` | 1.13 | 1.11 | 1.22 | 1.37 |

So loops read 5-6% above probes when empty and 15-30% above in the peak. That is expected: a mid-block loop misses delay at the signal. Arterial mid-block free speed is 48-49 km/h by loop. Free travel along the edge, with signals, is 36-40. **Motorway closure doesn't exist:** the one A115 loop reads 15-23% under probes, and one trunk station 3-8% under.

**Does the gap survive?** It depends on the class. The simulated speed is a space mean with stops in it, so `v_hm` is the fair match.
- **Motorway: survives.** 68 against 80 (−15%) at 05 h, against 70.5 (−4%) at 06 h. A real reason shows: links have limit 60 on the map and run 85, and motorways limit 80 and run 88. But the only loop on a motorway reads lower than probes, so the size is ±10%.
- **Arterial: gone.** 34 is inside 32-36. The earlier −8% compared a space mean with stops with a median over cells.
- **Local: smaller, still there.** 28 against 31-35, −9 to −19%. Unweighted over edges, it's 31-33. Much of this class has limit 30.

**Not known:** whether the probe fleet drives like everyone else. HERE's fleet mix isn't published here, and the night dip says it changes.

## 4. `real_accumulation.csv`: cars on the road

**Definition.** Edie and Little on links: `N(h) = Σ q(e,h) L(e) / v(e,h)`. Route vehicle-km is MODELLED, stepped through the day at real speeds. Speed is measured.

**F043, on model vehicle-km, whole cut, 100%:**

| Variant | 06-07 | **07-08** | **08-09** | 09-10 | 12-13 | 15-16 | **16-17** | 17-18 | 18-19 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Forecast | | 13,186 | 15,114 | | | | | | |
| (a) class speeds, the hand method | 8,276 | 13,079 | 15,159 | 13,177 | 10,867 | 17,185 | 18,586 | 16,713 | 13,933 |
| (b) edge `v_med` | 9,047 | 13,685 | 15,689 | 13,666 | 11,462 | 17,036 | 18,470 | 16,919 | 14,362 |
| (c) edge `v_hm` | 10,586 | 16,079 | 18,488 | 16,255 | 13,646 | 20,076 | 21,782 | 19,956 | 16,887 |
| (d) as (c), scaled to real counts | 7,498 | 12,783 | 17,231 | 16,528 | 13,302 | 18,252 | 18,817 | 17,509 | 15,622 |

The 8 days move each by ±3-5%. In (b) and (c) that's 13,185-14,124 and 15,799-16,516 at 07-08 h.

- **The hand figure is right as arithmetic:** within 1%. Its input choice is the larger question. Measure of speed moves the answer 17%, three to five times the day-to-day noise.
- **The target to use is a band:** 07-08 h 12,800-16,100; 08-09 h 15,700-18,500; 16-17 h 18,500-21,800. Old "healthy" 07:30 of 14,030 (7,015 at 50%) sits inside its band, so it stands on real speeds, as a range. The verdict on F043 is in `forecasts.csv`.
- **The model's morning is an hour early.** Real counts over route counts at arterial tuning sites run 0.77 at 06 h, 0.86 at 07 h, 0.98 at 08 h and 1.11-1.18 at 09-11 h. That's why (d) falls at 07-08 h and holds up at 09-10 h. This is a real fault in demand timing, on fitted sites.
- **Class check.** Over 24 h, real over model is 1.08 on arterials and 0.78 on tertiary roads (5 sites): real traffic favours bigger roads, as report 23 found.

**F046, real counts and real speeds only, no MATSim.** No count exists on residential streets, so this can only cover main roads, and only in the box. Compared on the same roads:

| Box, 100% | 07-08 | 08-09 | 16-17 | Against model on the same roads |
|---|---:|---:|---:|---|
| Main roads: (e) SVZ 2019 veh-km × loop hourly share, `v_med` to `v_hm` | 6,543-7,667 | 8,431-9,927 | 10,057-11,801 | **−6%, +7%, +5%** |
| Model (b) to (c), same roads | 6,990-8,190 | 7,881-9,268 | 9,607-11,285 | |
| Arterials: (f) loop q/v × road-km, `v_med` to `v_hm` | 5,798-7,067 | 7,886-9,554 | 8,821-10,689 | **+3 to +6%, +24 to +26%, +16 to +18%** |
| Model (b) to (c), same roads | 5,650-6,679 | 6,383-7,585 | 7,609-9,031 | |

**How they differ.** On main roads the official count network and the model agree within 7%, with the model early in the morning, which is the same timing error. (f) is higher, as expected, since count stations sit on busier streets than the average road of their class, so treat it as an upper limit. **F046 can't give a whole-network number.** Tertiary and residential traffic, 3,600-4,400 cars of the box's 10,600-12,500 at 07-08 h, has almost no count (5 tertiary sites, no residential) and stays MODELLED.

## 5. `real_signals.csv`: cycles and greens

**Definition.** Hamburg `primary_signal`, 49 lights live of 50, 1,100 connections, weekdays 26-28 Oct 2026 and Sunday 25 Oct (the day clocks changed). Dedupe on stream and time. The recorder is running, still catching up. `detector_car` isn't used.

| Weekday, local hour | Cycle p10 / p50 / p90, s | Green share p10 / p50 / p90 | Longest green per light p10 / p50 / p90 |
|---|---|---|---|
| 21-04 | 60 / 75 / 75-86 | 0.12 / 0.28 / 0.53-0.57 | 0.46 / 0.61-0.72 / 0.83-0.86 |
| 05-20 | 60 / 90 / 93-95 | 0.11-0.12 / 0.29-0.30 / 0.60 | 0.44-0.48 / 0.61-0.69 / 0.74-0.82 |

- **This overturns two lines of report 26 and foundation D.** The 90 s cycle runs **05:00 to 20:59**, not 07-20. Sunday also runs 90 s from 08-19, not 75 s. One Sunday, 49 lights.
- **Fixed, mostly.** In a median connection the within-hour spread of the cycle is 0 s, and 32-41% of connections go over 5 s. Report 26's "11-31 s" came mostly from one light on one Monday.
- **Longest green per light** is what a main road gets: median 0.62 by day. That and not 0.30 is the number for a main-road approach. Earlier work used 0.31 as "typical" (foundation A §3b).
- **Sweep range for macro:** cycle 75-110 s (Hamburg's 75-95 plus Berlin's published 110). Main-phase g/C 0.47-0.76. Any connection 0.11-0.60.

**Berlin's published figures:** B1/B5 from Blumberger Damm to the east city limit, 60 km/h green wave, 110 s in the morning peak, 100 s in the afternoon peak, 90 s otherwise (the answer gives the three values and the two peaks; off-peak is my reading). Heavy load 07-09 and 15-18 h. It's from August 2022. No greens, no offsets. The answer also says the cycles sit at the top of the RiLSA range. It says all coordinated lights must share one cycle.

**How well can Hamburg stand for Berlin?** Cycles: fairly well. German guidelines are shared, and Berlin's 90 s off-peak is Hamburg's. But Berlin's outer corridor goes to 110 s and Hamburg's inner-city median doesn't move in the peak, so Berlin's peak cycle may be longer. Greens: for shape only. These are 50 lights packed in 1.27 km of central Hamburg in 2026, with cycles and greens not chosen for anything in Berlin in 2019, and pedestrian and bus loads differ. **No Berlin green split has been measured. Berlin's signals stay INVENTED, and Hamburg only sets their range.**

## 6. `real_signal_pairs.csv`: close-spaced signals (F048)

**Definition** in item 7 below. Unit: signal-group pair, day 07-19 h, weekdays 26-29 Oct (29 Oct partial). "Through" means the turn between the two is 30 degrees or less. A pair stays `inside_junction` when the second stop line is passed before the egress starts.

| Through pairs, day | Under 30 m | 30-50 m | Control 50-150 m |
|---|---:|---:|---:|
| Group pairs (light pairs) | 21 (13) | 14 (11) | 41 (35) |
| One controller | 57% | 7% | 5% |
| Linked (one controller, or same cycle and stable offset) | 76% | 79% | 29% |
| Offset of `d` after `c`, p25 / p50 / p75, s | −2 / +4 / +9 | 0 / +2 / +18 | −7 / −1 / +7 |
| Offset spread over a day, s | 1 | 1 | 15 |
| Overlap of greens, p25 / p50 / p75 | 0.46 / 0.70 / 0.93 | 0.35 / 0.64 / 0.69 | 0.40 / 0.64 / 0.81 |
| `d` green after `c` ends, median, s | 4 | 0 | 7 |
| Red feed, median and p90, s per cycle | 10, 37 | 18.5, 38 | 14, 36 |
| Clears on at least 80% of cycles | 62% | 21% | 71% |

Linking is a daytime thing: at night only 8% of through pairs at 30-50 m hold it, about the share on one controller. Turning into a short link is different: under 30 m, 73% of turn pairs run opposed (their green while `d` is red), with a median feed of 11.5 s.

**Are close pairs one controller or linked?** Mostly linked by day. **Offset?** Small and stable, median +2 to +4 s, with a wide spread between sites. **Overlap?** About two thirds. **Does the upstream green end early enough?** Only sometimes. 46% of through pairs under 50 m clear on my test at saturated feed. The real feed is probably smaller, since upstream traffic isn't always saturated and not all goes straight. Hamburg can't show that, since it has no counts. So this is a floor on real clearing.

**Rule for Berlin's map, through movement to through movement, link under 50 m:**
1. Same cycle always, by day. 77% of Hamburg pairs (22 light pairs).
2. Downstream green starts **+2 s** after upstream. Spread p25-p75 −2 to +10 s, p10-p90 −17 to +19 s.
3. Overlap **0.65** of the upstream green, p25-p75 0.44-0.75.
4. Downstream green ends **4 s** after upstream, p25-p75 0-11 s. That's under the time to drive 30 m (7.6 s needed at 8.3 m/s). A rule that always clears would be stricter than Hamburg.

**Stand-in:** medium for "they are linked with a small offset", low for the numbers. It's 22 light pairs in one city centre in 2026. Berlin in 2019 may run differently.

**The same measures on our invented programs (m12, `signal_pairs_map.py`, no run), 75 through pairs under 50 m:** same cycle 100%, offset 0, overlap 1.0 on 75-79% of pairs, opposed on 12-16%, clears 76-79%. So the invented programs clear as often as or more often than Hamburg's under 30 m, and far more at 30-50 m. **They differ in being too uniform, not in failing to clear.** The worst cases are the opposed ones, with 37-41 s of feed into 3-5 cars of storage, and Hamburg has fewer of those under 30 m (5% against 16%) though similar at 30-50 m (21% against 12%). The m12 figures take listed phase durations as fixed. With these sample sizes, the plan's idea that real offsets clear short links and ours don't isn't confirmed. A next test: replace those opposed cases by the rule and rerun the screen. That also checks whether turns into short links, which aren't in the m12 figures, are the bigger difference.

## 7. Corridor for the corridor rung

**B1/B5 as published (Blumberger Damm to the east limit): a real jam, but it can't test discharge.**
- **Jam:** Alt-Biesdorf-Alt-Kaulsdorf 05:52-08:45, 1.76 km, 8 of 8 days. Alt-Biesdorf-Alt-Friedrichsfelde 15:38-16:38, 1.39 km, 8 of 8. Alt-Mahlsdorf 16:30-17:00, 6 of 8. The Senate names junctions on the same three streets. The morning head starts earlier than the Senate's 07-09 heavy load, which is worth a look.
- **Probes:** enough, 94-154 per interval.
- **Loops: none on the section**, on any quality or split. Only TE208 is nearby, on Blumberger Damm, and it's locked. So place, start and end can be tested, discharge can't.
- **Also:** outside the district, so it needs its own cut.

**Better for discharge: Leipziger Straße-Gertraudenstraße, eastbound (Leipziger Platz to Breite Straße, about 1.8 km).**
- **Jam:** head at Breite Straße 15:30-18:45, 1.0 km, 8 of 8; Leipziger Straße 15:30-18:08, 8 of 8.
- **Loops:** four tuning stations in a line: TE560, TE353, TE370, TE367. Under half: TE367 15-19 h on 8 of 8, TE370 16-18 h on 5 of 8.
- **Discharge:** 758 per lane at TE367 (31 grade A hours, 11 B), 735 at TE370, 743 at TE560, all grade B at their highest hour.
- **Cost:** signals unknown. Timing has to come by rule, which is a limit. Head sits 57 m outside the box, so the simulated area must include it.

**So:** run Leipziger-Gertrauden for place, start, end and discharge, with rule-set signals. Run B1/B5 for place and time with published cycles. Together they cover known timing and known discharge, but no single corridor has both.

## What's measured, estimated or invented

| Item | Grade |
|---|---|
| Probe speeds, loop flows and speeds, Hamburg cycles and greens | MEASURED |
| Jam list, queue grades, cars on the road from real speeds | ESTIMATED, on measured inputs. Thresholds are choices |
| `s·g/C` bound and `s` = 1,750 | ESTIMATED, then OPINION |
| Route vehicle-km, residential traffic | MODELLED |
| Berlin green splits and offsets | INVENTED. Range from Hamburg |

## What can't be known from this data

- **Berlin's saturation flow.** No queue counts, no plans. Hourly loops give only `s·g/C`.
- **Motorway capacity and motorway closure on tuning data:** the stations are locked or one weak.
- **Real queue length,** anywhere. Only slow edges.
- **Traffic on residential streets:** no counts, and probes there don't reach the trust bar.
- **Within-hour peaks at loops:** the data is hourly. Bunching stays unmeasured.
- **Causes of jams,** beyond a plain lane drop or merge. Roadworks and incidents in May 2019 weren't checked.
- **Signals in Berlin in 2019.**

## Changed after looking

1. **Main and local roads kept apart, and motorways apart from arterials,** in joining. The first list had a 54 km place on tertiary and residential streets and a 34 km chain from a parallel road, with heads at under 1 km/h on thin edges.
2. **Tier added** so a test can use only the credible rows. Its thresholds (4 days, 200 m, 10 probes) are mine and come after looking. All rows stay in the file.
3. **`flag_parallel_road` and `pattern`** added, plus head-edge start and end, since a place's start often sits on the period's edge.
4. **`real_signal_pairs.csv` split into through and turn,** after the first cut showed two kinds of pair. The definition had neither. The rule above is for through movements.
5. **Hamburg days:** the rule for a full day was loosened to at least 2.5 M rows, so Sunday 25 Oct counts. 29 Oct, partial, is used for pairs only.

## Rerun

`source cars-data/dev-env.sh`. `probes15.py` needs h5py, shapely and geographiclib: build `berlin2019/t4c_job/env.nix` and use its python. It writes `probes/edge_15min.npz` outside the repo in about 5 minutes. Then `python3 -I` on `jams.py`, `signals.py`, `capacity.py`, `free_speed.py`, `accumulation.py`, `signal_pairs.py`, `signal_pairs_map.py` from a scratch directory `/tmp/rung1`. `accumulation.py` caches route counts in `/tmp/rung1/qeh.npy`. All in minutes.

---

## Definitions, written before computing

**Days.** The 8 frozen tuning days in `step1/freeze.json`, all May 2019. No other month is opened.

**Sites.** Loop stations with quality `trusted` that aren't in `locked_sites_all_berlin`. Scope `district` is the 63 `tuning_sites`. Scope `berlin` is the unlocked trusted stations outside the box, needed because the district has no motorway loop. The loader drops locked rows before anything else reads them. Faulty site-days stay dropped, as in `real_days.csv.gz`.

**Probes.** HERE Traffic4cast May 2019, 8 tuning days, joined to the v6.4 edges by MeTS-10's cell join and trust filter, kept at 15 minutes. Two speeds per edge and interval: `v_med`, the median over the edge's cells (MeTS-10, as in `edge_hour.csv.gz`), and `v_hm`, the harmonic mean over cells, which is what a car crossing the edge would average. An edge's free speed `v_free` is its 90th percentile of 15-minute `v_med` over the 8 days. Raw and per-edge probe data stays out of the repo; only derived tables go in.

### 1. `real_jams.csv`

- **Jam interval (probes):** `v_med < v_free / 3` (FHWA 2019's rule of thumb) with volume at least 5 in the 15 minutes.
- **Jam episode:** 2 or more consecutive jam intervals on an edge on a day (30 minutes, the width of Gomes' onset windows).
- **Check on a sample, before the list is read.** At tuning sites, take site-hours where the loop's hourly speed is under half its own free speed. If the one-third rule on the same edge's probes misses more than half of these, the primary threshold becomes `v_free / 2`, and the report says so. Both thresholds are always computed.
- **A place:** edges joined when their jam episodes overlap in time on the same day and one edge flows into the next, within an AM (05-11 h) or PM (12-21 h) period. Across days, places are joined if they share an edge. The **head** is the most downstream edge jammed on the most days. Extent is the km of edges jammed on at least 2 days, and also the median per day.
- **Start, end:** per day, first and last jam interval of the place; median and full range over days.
- **Repeatability:** days of 8 with an episode at the place. A row needs at least 2 days. One-day rows go to a count, not the list.
- **Loop rows:** site-hours where hourly speed is under a third (and separately under half) of the site's free speed, on tuning sites, with flow of at least 50/h. Listed with `source=loop`.
- **Cause:** filled only if the map plainly shows it at the head: lane drop, motorway merge or diverge. The head's junction type is a separate column (`signal` isn't a cause by itself). Otherwise blank.
- **Noise:** all 28 day pairs: Jaccard of jam edges by period, share of day A's jam edge-hours also jam on day B, top-20 heads shared. Also the list built from 4 days against the other 4.

### 2. `real_capacity.csv`

- **Flow per lane:** station flow over detectors reporting, per hour. Also the highest single lane, from the per-detector file.
- **Queue present:** hourly loop speed `< 0.7 × site free`, where site free is the site's 90th percentile hour (`metrics.py`'s frozen definition and constant), with flow of at least 50/h. **Confirmed** when the same edge's probes also have at least one 15-minute interval below half of `v_free` in that hour (FHWA accepts 15 minutes to an hour of queue).
- **Columns apart:** highest flow in hours with a queue, confirmed or not, and in hours without one. Only queue hours measure capacity. Hours without a queue give only a lower bound.
- **Saturation flow:** loops are hourly and Berlin has no signal plans, so a loop can't measure `s` directly. For sites whose edge ends at or close to a signal: `s >= q / (g/C)` with `g/C` from Hamburg's longest-green connection per junction at that hour. This is a bound and is labelled as such.

### 3. `real_free_speed.csv`

- **Night:** 01:00-04:59. **Early:** 05:00-05:59. Also 06:00-06:59, the hour used so far.
- By OSM class and by the three classes used so far (motorway includes trunk and links; arterial primary and secondary; local the rest). Weighted by probe volume as `step6_probes.py` does, and also unweighted over edges, with `v_med` and `v_hm`.
- **Closure:** at tuning sites, loop hourly speed against the speed on the same edge in the same hour, by class and hour. Loop is a point time mean; probes are a moving-fleet sample along the edge. The ratio is the closure, and it isn't assumed to be 1.
- **The question:** does the gap with the 10% day's 68, 34, 28 km/h survive? The sim numbers are quoted, and no run is made.

### 4. `real_accumulation.csv`

- **Formula:** Little's law on links, `N(h) = sum over edges of q(e,h) L(e) / v(e,h)`, with `v` the 8-day speed for that edge and hour, class speed where the edge has no probes. Per day for the spread. Over the cut, and over the box.
- **Variants:** (a) the hand calculation with class speeds, to recheck F043; (b) edge speeds `v_med`; (c) edge speeds `v_hm`; (d) as (c), with route veh-km scaled by class and hour to real counts at tuning sites; (e) main roads only, with SVZ 2019 official veh-km and the real hourly share from counts, which uses no MATSim.
- **Labels:** route veh-km is MODELLED, speeds and counts MEASURED, the mix ESTIMATED.

### 5. `real_signals.csv`

- Hamburg `primary_signal`, weekdays and weekends apart, by local hour. Cycle as spacing of green starts per connection, 20-300 s. Green share over that cycle. Every full day on disk, deduplicated on (stream, time). Also the longest-green connection per light. `detector_car` isn't used: it holds signal requests, not counts.
- Berlin's published corridor figures from report 23 as separate rows.

### 6. Jam recovery

Space-time clusters per day: jam intervals joined when the edge is the same or adjacent and the interval the same or next, at both thresholds. Duration and size (edge-intervals) distributions, with a tail exponent by maximum likelihood. On the same 15-minute bins any later run can use.

### Added after the plan amendment of 890dfc5, before computing these

**7. `real_signal_pairs.csv`, close-spaced signals (F048).** Hamburg, the 50 recorded lights, motor-vehicle connections only.
- **Geometry.** Each connection in `static/` has three lines: the ingress lane starting at the stop line, the path through the junction, and the start of the egress. A pair (upstream `c`, downstream `d`) is one where `d`'s stop line lies within 4.5 m sideways of `c`'s path extended straight, heading within 35 degrees. **Link length** runs from where `c`'s egress starts to `d`'s stop line, the same thing as a map edge between junctions. Bands: under 30 m, 30-50 m, and 50-150 m as the control.
- **Linked or not.** Same `trafficLightsID` means one controller. Otherwise linked when both run the same cycle in that hour (medians within 1 s) and the offset between green starts has an interquartile range of at most 5 s.
- **Offset:** `d`'s green start minus `c`'s, modulo cycle.
- **Overlap:** share of `c`'s green during which `d` is also green.
- **Red feed:** seconds per cycle `c` is green while `d` is red. At 0.5 cars/s/lane that is the queue fed into the link.
- **Clears:** `d` stays green at least link length plus stop-line gap at 8.3 m/s past `c`'s green end, or the red feed fits the link's storage (link / 7.5 m per lane).
- **The rule** for Berlin is stated from the under-50 m bands against the control, with its spread. Hamburg's stand-in value is stated separately.

**8. Queue certainty in `real_capacity.csv`.** The file is used both ways: real flow must fit under table capacity, and at queue-present hours real flow must reach 0.85 of it. Each highest-flow hour gets a grade. `A`: loop hourly speed under half of site free, and probes on the edge below half of `v_free` in at least 2 of the 4 intervals. `B`: loop under 0.7 of site free and probes below half in at least 1 interval. `C`: loop under 0.7 only, or no probes. `none`: loop at or above 0.7.

**9. Cars on the road twice.** F043 is variants (a) to (d), on model vehicle-km. F046 uses real counts and speeds only: (e) SVZ 2019 veh-km on the count network with the real hourly share; and (f) Edie per road-km, `k = q/v` at each tuning site, averaged by class and multiplied by the map's directed km of that class in the box. Neither includes residential streets, since no count exists there. The difference is stated.

**10. Corridor.** For B1/B5: real jam on the list, loops, probes, and whether place, start, end and discharge can be tested. Discharge can be tested only where a queue-present site sits on the corridor. If not, name a better corridor from the jam list by the same test.
