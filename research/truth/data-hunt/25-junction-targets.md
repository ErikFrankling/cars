# 25: Real numeric targets per junction type

Checked 2026-11-02. No GPU, no simulator, and nobody was contacted. Everything graded MEASURED was computed here from tracks I downloaded or already held. Table: [25-junction-targets.csv](25-junction-targets.csv). Scripts: [scripts/junction_targets/](../../../scripts/junction_targets/). Intermediate events: `cars-data/truth/junction-25/`.

Grades: **MEASURED**, **PROVIDER CLAIM**, **MODELLED**, **UNVERIFIED**.

## The answer

Real, usable targets now exist for signals by turn (23 junctions, 17 with saturation values), single-lane roundabouts (6), on-ramps (3 sites, 4 ramps) and lane ends (2 sites). Stop-controlled junctions, off-ramps, the all-way stop, the zipper and the weave have targets too, but from one or two sites, so they are thin. **Three types remain with no real target from open data: two-lane roundabouts, right-before-left, and a signed urban zipper.** A clean yield-sign junction is also missing.

Three results change earlier work:

1. **Report 05's roundabout critical gaps are too low, because of a bug.** It counted cars that had just entered from the driver's own arm, and cars leaving the ring, as conflicting traffic. I reproduced its 2.66 s on Swiss F2 with its rule. Removing those cars gives 3.41 s. The benchmark's JR1 uses that same rule on both sides.
2. **"The critical gap" isn't one number.** On the same drivers it reads 3.2–3.8 s (all first-in-line cars), 3.9–5.0 s (those who let a car go) or 4.2–5.5 s (those who also stopped). A shorter approach zone drops the first version to 0.9–1.6 s. A twin test with known drivers reads 0.4–0.8 s above the truth. **Compare simulation and reality through the same code, and never copy this number into a driver.**
3. **Real saturation flow is mostly below the design value.** The median over 17 signal sites is 2.2 s, or 1,640 veh/h/lane (1,285–1,895). The design value of 1,900 is only reached at the top of that range.

## Targets per type

All MEASURED on tuning data unless marked. "Spread" is half the p10–p90 width of the values named. The csv has about 1,500 rows, including flows by arm and movement per site.

### Signals by turn

23 junctions: Athens 7 (pNEUMA), Lankershim 4, Peachtree 4, Foggy Bottom 3, DLR Braunschweig 1, SinD 4. Queues long enough for a saturation value exist at 17 of them: Athens, Lankershim, Peachtree, DLR and SinD Changchun.

| Quantity | Through | Left | Right | All | Site range |
|---|---:|---:|---:|---:|---|
| Saturation headway, position 5+, s | | | | **2.20** | 1.90–2.80 |
| Saturation flow, veh/h/lane | | | | **1,636** | 1,285–1,895 |
| Discharge headway, position 4+, same movement, s | 2.25 | 2.00 | 2.80 (n=64) | | 1.9–3.3, 1.9–4.2, 2.2–2.8 |
| Queue headway, position 2, 3, 4, s | | | | 2.95, 2.50, 2.29 | 2.4–4.0, 2.0–3.4, 1.9–3.0 |
| Share stopping | 0.35 | 0.54 | 0.36 | | 0.09–0.61, 0.08–0.77, 0.04–0.73 |
| Delay, last 50 to 60 m against that movement's p15, s | 12 | 20 | 21 | | 3–33, 8–40, 4–49 |
| Speed inside the junction, unstopped cars, m/s | 8.4 | 5.3 | 5.0 | | 6.6–13.7, 3.9–7.0, 3.3–6.8 |

First car start after green, where states exist: DLR 1.62 s (n=3,105), Tianjin 1.33 s (53), Chongqing 0.80 s (39). DLR position 1 headway 3.62 s, on a Sunday. Left and through discharge about equally fast on Lankershim (1.9, 2.0 s). Right turns are slower where there is data, but few right-turn queues are long.

### Single-lane roundabouts

6 sites: OpenDD rdb1, 5, 6, 7 and Swiss F1, F2. 40,472 decisions in about 44 hours.

| Quantity | Median of sites | Site range | Within-site spread |
|---|---:|---|---|
| Critical gap, all first-in-line cars, s | **3.42** | 3.18–3.76 | 0.13–0.30 between blocks of 5 flights; 0.09–0.53 between arms |
| Critical gap, those who let a car go, s | 4.3 | 3.9–5.0 | |
| Critical gap, stopped and let a car go, s | 4.6 | 4.2–5.5 | |
| Follow-up headway, s | **2.71** | 2.54–3.23 | 0.08–0.44 |
| Entry flow, veh/h | 1,273 | 497–1,605 | |
| Share of entrants stopping | 0.10 | 0.04–0.25 | |
| Entry speed unstopped, m/s | 6.3 | 5.2–7.1 | |
| Speed in the ring, m/s | 6.9 | 5.0–7.4 through | |
| Exit speed, m/s | 8.7 | 6.3–9.9 | |
| Queue, p95 of the longest per arm-minute, cars | 3 | 1–5 | |
| Entered with a ring car under 2 s away | 0.7% | 0.4–2.1% | |

**Acceptance curve, the sturdiest form of this target.** Share accepted, by gap:

| Gap, s | 2–3 | 3–4 | 4–5 | 5–6 | 6–8 |
|---|---:|---:|---:|---:|---:|
| Median of sites | 0.09 | 0.62 | 0.88 | 0.95 | 0.99 |
| Site range | 0.04–0.20 | 0.38–0.70 | 0.84–0.92 | 0.90–0.99 | 0.97–0.99 |

**Capacity is weak.** Few minutes saturate: 18% of arm-minutes on F1, 2.5% on rdb6, 1.6% on rdb1, about none elsewhere. Observed entry flow in those minutes:

| Circulating, veh/h | F1 | rdb1 | rdb6 |
|---|---:|---:|---:|
| 0–300 | 587 | 645 | |
| 300–600 | 581 | 467 | |
| 600–900 | 400 | 355 | 492 |
| 900–1,300 | | 315 | 463 |

This is well under what the gaps predict (MODELLED: Siegloch with rdb6's 3.40 and 2.54 gives about 740 at 1,100 circulating, against 463). My "queued 80% of the minute" test doesn't prove the queue was served without a break, and pedestrians weren't removed. Treat this as a diagnostic.

### Stop and give-way

| Site | Critical gap, all (95% CI), s | Those who rejected, s | Stopped and rejected, s | Full stop / rolling / none | Rejected a gap | Grade |
|---|---|---:|---:|---|---:|---|
| Athens, stop node, 3 weekdays, n=374 | **3.42** (3.13–3.73) | 3.86 | 4.94 | 22% / 43% / 35% | 27% | MEASURED, one site |
| Athens, unsigned, behaves as priority, n=276 | 3.43 (2.62–4.61) | | | 16% / 14% / 69% | 6% | MEASURED, rule UNVERIFIED |
| Athens, slip road beside a signal, n=352 | 6.51 (5.66–7.14) | | | 27% / 16% / 57% | 16% | **WEAK**: mixed with the signal queue |

Follow-up on the stop site is 5.0 s (n=43), longer than its critical gap, so I don't trust it. Minor flows are 114–166 veh/h, conflicting flow 240–360 veh/h, and no minor arm ever saturates. **There's no clean yield-sign site.** Delay against major flow is in the csv but noisy.

### Right-before-left: NO DATA

I tested the Athens crossings. If the rule applied, the car from the right would enter first:

| Site | Right-hand car first | Pairs |
|---|---:|---:|
| Stop node | 0.51 | 69 |
| Unsigned b | 0.48 | 40 |
| Slip | 0.42 | 36 |
| Unsigned a | 0.80 | 10, too few |

So these are not right-before-left in practice, and I won't call anything a target. The test is in the csv as `car_from_right_entered_first_share`, ready for inD.

### All-way stop

One site, thin: **Foggy Bottom, H St and 22nd St**, named all-way stop in TGSIM's data dictionary (report 22 had it as unchecked). Two approaches on one-way streets, 293 cars in two hours. MEASURED:

- Flow 152 veh/h.
- Full stop 61%, rolling 35%, no slowing 3%.
- Stopped time 4.7 s (p10–p90 0.4–19.8).
- Headway between entries when the next car was waiting 6.1 s (n=24).
- First come, first served 36% (n=28). **Not behaviour to copy**: a person was within 16 m in the 3 s before 83% of entries.

### On-ramps, lane ends, zipper proxy

| Site | Merges | Position in lane, p50 (physical) | Last third | Merge speed, m/s | Gap to new follower / leader, s | Stopped in lane | Alternation (random) |
|---|---:|---:|---:|---:|---|---:|---|
| I-80 Powell, congested | 641 | 1.03 | 0.88 | 4.5 | 1.17 / 0.88 | 30% | **0.71 (0.50)** |
| US-101 Ventura, aux lane | 343 | 0.28 | 0.18 | 12.2 | 1.05 / 0.81 | 0% | 0.41 (0.40) |
| A39 north, free | 2,486 | 0.15 | 0.02 | 25.8 | 2.39 / 3.89 | 0% | 0.39 (0.50), free flow |
| A39 south, free, lane runs out of view | 315 | 0.59 | 0.08 | 24.3 | 6.28 / 4.17 | 0% | |
| I-395 aux lane end | 2,023 | 0.82 | 0.95 | 8.5 | 1.41 / 0.91 | 2% | **0.64 (0.50)** |
| DRaT, short fading lane | 42 | | | 16.2 | | | THIN |

- **Physical position** is where the car comes within 1.8 m of the target lane's path. Label positions are in the csv too, but report 18 shows I-80's lane label ends at an imaginary line. A value above 1 means past that line.
- **Zipper proxy:** at congested lane ends, about 90% merge in the last third, and alternation is well above random: 0.71 on I-80 (n=1,022) and 0.64 on I-395. Where the lane is long (US-101) order is random. The csv carries these under `zipper_proxy`. They're freeway lane ends, and `zipper` itself stays `NO_DATA`.
- Flow per lane past the merge: I-80 1,260, US-101 1,268, I-395 1,218 veh/h/lane, block p10–p90 half-width 80–243. DRaT free 1,239 (29 m/s), congested 1,202 (10 m/s). **I saw no breakdown from free flow, so capacity drop isn't measured here.** Report 04's band stands.

### Off-ramps, weaving

| Off-ramp | Diverges | From exit lane start, p50 (p10–p90), m | Speed, m/s | Exit flow, veh/h |
|---|---:|---|---:|---:|
| US-101 Cahuenga | 247 | 11 (0–13) | 18.1 | 306 |
| I-395 left exit | 524 | 50 (32–68) | 12.0 | 252 |

**Weave, one site: US-101 Ventura to Cahuenga, about 220 m.** Weaving share 0.10. By movement: through 90%, ramp to main 7%, main to ramp 4%, ramp to ramp 3 cars. Speed: through 10.6, main to ramp 16.5, ramp to main 12.1 m/s. Changes in or out of the aux lane sit at p50 0.16 of its length (p10–p90 0.04–0.96). 1.13 lane changes per veh-km, unfiltered labels.

## The noise floor

| Spread | Result | Source |
|---|---|---|
| **Day to day, flow** | Half-range 4–9% across 3 weekdays, 7 junctions | Athens |
| Day to day, stop share | ±0.03–0.06 | Athens |
| Day to day, discharge headway, position 4+ | ±0–0.2 s, mostly ≤0.1 | Athens |
| Session to session, critical gap | 0.13–0.30 s between blocks of 5 flights (dates not in the data) | OpenDD |
| Arm to arm, critical gap | 0.09–0.53 s | OpenDD, Swiss |
| **Site to site, critical gap** | 3.18–3.76 s | OpenDD, Swiss |
| Site to site, follow-up | 2.54–3.23 s | OpenDD, Swiss |
| Site to site, saturation headway | 1.90–2.80 s | 17 sites |

**Only Athens gives a true day-to-day floor here**, and only over 3 mornings. Every other "spread" is across sessions or blocks within one day, so it probably understates real day-to-day noise. Site-to-site spread is about as big as, or bigger than, within-site spread. So one frozen configuration should expect to sit inside the site range, not on any one site's value.

## Held out

Written to [splits.toml](../../../scripts/junction_targets/splits.toml) before reading the driving data. Rows in the csv have `split=heldout` and **no values**: the same scripts compute them at an approved reveal. Rule: `sha256(name + "cars-bench-v1") mod 100 < 30`. Tuning scripts refuse these sites.

| Set | State |
|---|---|
| OpenDD rdb2, 3, 4 | Zips on disk. Only the maps were opened |
| pNEUMA drones d3, d6, d8, and all of 29 Oct 2018 | Never downloaded. d3 and d6 border tuning drones, so some streets may be shared |
| Swiss L1 | Report 05 already printed 2.72 and 2.33 s, so it's a weak hold-out |
| DLR UT signal group 7 | Removed from every number here |
| Helsinki, Songdo | In the bench's `locked.toml`. **Not downloaded or opened** |
| Pully, TUMDOT | Report 22 section 9. Not downloaded |

**A slip to disclose.** My first download queue included Helsinki and Pully, written before I had read `locked.toml`. I stopped it during OpenDD, before either began. No file from them was fetched, so nothing is spent. Earlier samples of Helsinki, Songdo and Pully stayed unread by me.

**Report 22 listed Athens as locked; this task named it as a source.** I followed the task and split it as above. Reports 19 to 21 had already read a pNEUMA file from 24 Oct, and report 20 and 21 name d1.

**Not independent:** NGSIM and DLR UT discharge were fit targets in report 05, so they're tuning only. Neither NGSIM site has a second day.

## What this data can't measure

- **Two-lane roundabouts.** All 7 OpenDD rings and the Swiss ones look single-lane. rounD should fill this (not opened). Helsinki is locked, and its lanes are unknown to me.
- **Right-before-left, and a signed yield junction.** See above. inD should fill both, but I haven't seen its site list beyond a search summary (UNVERIFIED).
- **A true zipper.** Only a freeway proxy.
- **Capacity at give-way junctions:** minor arms never saturate. Roundabouts: barely. Freeways: no breakdown observed.
- **Signal phase in most data.** Lost time and position 1 need states: DLR, plus SinD Tianjin and Chongqing. On Changchun and Xi'an two lights serve four arms, so I removed phase-based rows. pNEUMA, NGSIM and Foggy Bottom have none here (Peachtree's timing sheets exist and I didn't use them).
- **Who gave way, in full.** I have time margins (PET) and rejection shares. I don't have whether the ring or major-road car braked.
- **Effects of pedestrians and bikes.** Not filtered from gaps or capacity. Report 20 finds them large at some sites.
- **Motorcycles in Athens.** Removed from cars' conflicts, which likely inflates Athens gaps and headways a little. Size not measured.
- **Full delay and queue.** Delay covers only the last 50 to 60 m (40 m on stop sites, 25 m at roundabouts). Queues longer than the view are cut.
- **Lanes.** Clustered from where cars stop, not a map, except NGSIM's labels. Changchun's 2.8 s may be a clustering effect.
- **Weekday, peak at most sites.** DLR is a Sunday, pNEUMA is morning, and NGSIM runs are 17–34 minutes.

## Ranked sources

All observe vehicles in view; none measures a share of a city.

| # | Source | Measures | Area, period | Rate | Access, licence | Sweden | Downloaded | Serves | Test | Work left |
|---|---|---|---|---:|---|---|---|---|---|---|
| 1 | **OpenDD v3** | Drone, 7 single-lane rings | Wolfsburg, Ingolstadt, 62 h | 30 Hz | [Open](https://l3pilot.eu/data/opendd.html), CC BY-ND 4.0 | No | All, 4 read | Roundabouts | JR | Scene per ring |
| 2 | **pNEUMA** | Drones | Athens, 4 weekdays, 2018 | 25 Hz | [Open](https://zenodo.org/records/10491409). CC BY on Zenodo; EPFL page conflicts (report 05) | No | 39 members, streamed by range | Signals, stop | JS, JP | Scene per junction |
| 3 | **NGSIM** Lankershim, Peachtree, I-80, US-101 | Video, lanes, turns | US, 2005–06 | 10 Hz | Open, CC BY-SA 3.0 per report 05 | No | Held | Signals by turn, ramps, weave | JS, JO, JW | Scene |
| 4 | **TGSIM** Foggy, I-395 | Fixed cameras | DC, 2023 | 10 Hz | Open, CC0 | No | Held | All-way, lane end, exit | JA, JL, JF | Scene |
| 5 | **Swiss roundabouts** | Drone | Aargau, 2023 | 30 Hz | Open, CC BY 4.0 | No | Held | JR | JR | Exists in bench |
| 6 | **DLR UT, HT** | Trajectories, plus controller states at UT | Braunschweig, A39 | 5–20 Hz | Open, CC BY-NC-SA | No | Held | Signal states, free on-ramps | JS, JO | Exists |
| 7 | **SinD samples** | Drone with light states | 4 Chinese cities, 15–26 min each | 10 Hz | [Open samples](https://github.com/SOTIF-AVLab/SinD/tree/main/Data), Git LFS. **README badge says non-commercial, LICENSE file is CC0**. Full set by request | No | Samples | States, by turn | JS | Mixed traffic |
| 8 | DRaT | Drone | Fort Worth, 80 min | 8 Hz | Open, CC BY 4.0 | No | Held | Lane end, thin | JL | |

### Would fill, once approved

| Source | Would fill | State |
|---|---|---|
| **inD** | Priority, right-before-left | Pending. UNVERIFIED |
| **rounD** | Two-lane rings | Pending. UNVERIFIED |
| **exiD** | Ramps, weaving, merge position in free flow, more sites | Pending |
| **highD** | Motorway capacity, lane changes, little junction value | Pending |
| **SinD full** | Weekday signals with states, 6 junctions | Needs request, draft below |

### Published cross-checks, never targets

PROVIDER CLAIM, in the csv as `split=crosscheck`.

| Guide | Value | Compared with |
|---|---|---|
| [TRVMB](https://bransch.trafikverket.se/globalassets/dokument/trvmb_kapacitet_och_framkomlighetseffekter.pdf) roundabout | 3.4 s critical gap, 2.4 s follow-up | 3.42 and 2.71 here, **close** |
| TRVMB give way / stop, 50 km/h major, right turn | 5.0 / 5.7 s | 3.4–4.9 here, lower |
| [WisDOT 2020](https://www.wisconsindot.gov/dtsdManuals/traffic-ops/programs/analysis/roundabout-analysis.pdf), one-lane | 4.6 s, or 3.8 s when exiting cars are handled. Follow-up 2.8 s in the state manual | Matches this report's "those who rejected" versus "all" split in spirit |
| HCM 6, one-lane, as quoted in WisDOT | 5.0 s | 4.2–5.5 s, stopped and rejected |
| TRVMB, FHWA saturation | 1,900 veh/h/lane (FHWA 1,800 for planning) | Median 1,636 here |

HCM itself and HBS weren't opened: paid or unavailable to me. So HBS has no number here.

My reading (OPINION): guides differ in part because they count different drivers. That needs checking against their methods.

## Top 3 recommendations

1. **Fix JR1 and JR2 in the benchmark before the first official score, and read this table.** Next step: the benchmark builder replaces `roundabout_decisions` with `rb.py`'s rule on both sides, and takes the acceptance curve as the primary metric. This is a registry change, so it's cheapest now. The new metric IDs in the csv's `bench_id` column are proposals, since I did not touch that branch: `JS9–10, JP4–6, JR5–7, JA1–8, JF1–3, JW1–3, JB1`. Filter on `split=tune`.
2. **Build scenes for the sites with strong targets first.** Next step: roundabouts rdb1, rdb6, F1; signals Lankershim int 2 and Athens d7; ramps I-80, US-101, I-395. These cover the large gaps with one frozen configuration. `rb.py` and `jx.py` take plain tracks, but **no adapter from `cars run --trace` exists yet**, because a trace needs lane shapes to give x and y. The bench's `metrics/extract.py` is the place to add it.
3. **Fill the holes.** inD and rounD once approved. Run `car_from_right_entered_first_share` and `gap_acceptance_share` on them first. Then decide whether Helsinki is worth spending: it's the only open multi-year day-to-day record of junctions I found, nine days over three years.

## What only Erik can do

- **Keep or spend Helsinki.** Using it for floors would turn it from held-out into tuning. Its value as a long noise floor is high, and I think the answer is to split it by scene. Your call, since `reveal.py` keeps this to you.
- **Send the SinD request if you want the full set.** Their README asks for an educational address and this subject line: `[Apply for SinD] Erik Frankling_Sweden_KTH`. To `[e-mail removed]` and `[e-mail removed]`; their README lists two more. Non-commercial use applies per their README badge. Draft:

  > Hi,
  >
  > I'm a student at KTH and I'm working on a traffic simulator as a follow-up to my bachelor's thesis. I'd like to compare how it handles signalized intersections with real data, and SinD has the signal states I need.
  >
  > Could I get access to the full dataset? It's for non-commercial research. I don't need the Diffuser weights.
  >
  > Thanks,
  > Erik Frankling
  > Department: fill in

  Check the department line, and that "follow-up to my bachelor's thesis" is how you'd describe it.
- **Licence choices.** OpenDD's CC BY-ND may limit publishing derived tables as a dataset, DLR's are NC-SA, and SinD's badge conflicts with its licence file. Fine for this work. Worth a look before publishing the csv.

## Dead ends

| Tried | Result |
|---|---|
| Peachtree at 13th St as a stop site | Under 60 minor cars in 17 minutes, and my line finder caught the main road. Removed |
| I-24 MOTION | `i24motion.org` doesn't answer from here. Not verified |
| Zen Traffic Data | Site says access is suspended for a security fix |
| CitySim | Form needs a person. Skipped as told |
| UTE weaving sites | Full data on Baidu; only samples public. Not fetched |
| HDSVT, 620 MB, CC BY | Downloaded. Latitude is the same to 6 decimals on all lane lines, so the geographic files can't separate lanes. The pixel files need a scale I didn't derive. Unanalysed |
| DRIFT, Daejeon | [On Hugging Face](https://huggingface.co/datasets/Hj-Lee/The-DRIFT), 14.5 GB, not locked. Not used, time. Good next signal source |
| Short approach zone, 2 m, for the gap | Reads 0.9–1.6 s, since rolling cars look like tiny lags. Kept 6 m |
| Roundabout capacity from "queued" minutes | Reads well below the gap-based estimate. Diagnostic only |
| OSM stop tags in Athens | Many sit on low-flow or no-conflict approaches. Only one held up. Finding crossings from the tracks found two more |

## New directions

- **Acceptance curve instead of a critical gap**, everywhere gaps are scored.
- **Alternation against random order** as a zipper metric. I found no one publishing it, though my search wasn't exhaustive.
- **DRIFT, and Songdo's lane polygons at an approved reveal,** for weekday signals with many cycles.
- **Infer phases from discharge** in pNEUMA to get position 1 and lost time on weekdays.
- **Peachtree's timing sheets** would add a weekday site with real states.

## Reproduce

From a directory that isn't a data folder. Set up: `source /home/erikf/projects/personal/cars-data/dev-env.sh`, `S=scripts/junction_targets`.

```sh
$S/fetch.sh opendd                               # then unzip tuning tracks and all maps to jt25-opendd/x
python3 -I $S/pneuma_fetch.py d5:20181024:0830 ... # d5, d7, d9, d10; 24 Oct, 30 Oct, 1 Nov; 0830, 0900, 0930. Plus 0900 on 24 Oct for d1, d2, d4
python3 -I $S/roundabouts.py opendd rdb1          # also rdb5, 6, 7; swiss F1, F2
python3 -I $S/rb_metrics.py roundabout "SITE:roundabout_single:SOURCE URL:tune" ...
python3 -I $S/foggy.py; python3 -I $S/ngsim.py; python3 -I $S/dlr.py; python3 -I $S/sind.py; python3 -I $S/drat.py
python3 -I $S/pneuma_scan.py; python3 -I $S/pneuma_discover.py; python3 -I $S/pneuma_signals.py; python3 -I $S/priority_run.py
cd SCRATCH_WITH_research/truth && python3 -I $S/ramps.py   # the merging library wants that relative folder; needs its cache
python3 -I $S/build_csv.py; python3 -I $S/test_targets.py; python3 -I $S/test_twin.py
```

SinD samples came from `media.githubusercontent.com/media/SOTIF-AVLab/SinD/main/Data/...` into `jt25-sind/`, named by path with separators replaced. Nothing here is committed.

`test_twin.py` puts known drivers through the roundabout code: true critical gaps of 3.0, 3.5 and 4.5 s read 3.56, 4.29 and 5.30 s, while follow-up reads within 0.07 s of truth. It passes when the offset stays between 0 and 1 s, which documents the offset, not an accuracy.
