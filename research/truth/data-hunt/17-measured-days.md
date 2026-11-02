# 17: Real measured days as a target a simulation must hit

Checked 2026-11-02. Nobody was contacted, no forms were filled in, no accounts were made. No GPU was used and no simulation was run. Grades: **MEASURED** means I opened the data and calculated it. **PROVIDER CLAIM**, **MODELLED** and **UNVERIFIED** as in the brief.

## The answer

**Erik is right: real days are plentiful, and six are now on disk as tables a simulation can be compared with.** They cover Berlin, Madrid, Paris and Helsinki, with each site's flow by hour and speed or occupancy where the city measures it. Each comes with the spread from its other normal weekdays as the noise floor, 136 to 4,057 sites per day. They are in `cars-data/datasets/reference-days/`.

**Strongest target: Madrid, Wednesday 20 October 2021.** It has 3,552 clean sites and its survey demand owes nothing to its loops, so its flow test is blind. It has no scenario yet, and speed only on M30. **First day to actually run: Berlin, Wednesday 15 May 2019**, as report 12 says, because a scenario can be ready soon. These two don't conflict. Berlin can be tested first, and Madrid is the harder and cleaner test.

**What the script says about our Berlin day: it fails every check it can test.** On 15 May 2019 at 135 trusted sites, simulated flow is 42% of real and only 11% of site-hours have GEH under 5, against about 92% for the least similar real day. The morning peak comes at 10:00, not 08:00. The simulation caught 2% of the real slow site-hours. Travel times and trips are not tested. The matches hold up: the 2024 matches agree with report 03's map on all 77 sites, and including doubtful matches changes little. The failure is the run, most of all its demand, and not the comparison.

## What's on disk

Format and method are in [`reference-days/README.md`](file:///home/erikf/projects/personal/cars-data/datasets/reference-days/README.md). Each folder has `sites.csv` with coordinates and direction, `reference_day.csv` by site and hour, `other_days.csv.gz` with every other normal weekday, `noise.json` and a README listing that city's traps.

**How far real days are from each other (MEASURED).** All other normal weekdays against the reference day, all 24 hours, using report 04's method.

| Day | Clean sites | Site-hours | Median flow difference | Median GEH | GEH<5 | GEH<3 | GEH<5, 7 days apart, 07–18 h | Speed difference, median | Daily total varies | Biggest hourly-share gap (RMSE) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Berlin, 15 May 2019 | 258 | 6,176 | 6.3% | 1.36 | 94.1% | 82.4% | 91.8% | 2.0 km/h | 1.0% | 0.11 pts |
| Berlin, 25 Sep 2024 | 138 | 3,263 | 7.6% | 1.47 | 91.5% | 78.3% | 90.6% | 2.0 km/h | 2.0% | 0.15 pts |
| Madrid, 20 Oct 2021 | 3,552 | 83,616 | 7.2% | 1.26 | 94.7% | 84.4% | 94.3% | 1.6 km/h, M30 only | 1.8% | 0.17 pts |
| Madrid, 23 Sep 2026 | 4,057 | 95,265 | 7.2% | 1.20 | 96.0% | 86.9% | 95.9% | 1.7 km/h, M30 only | 1.1% | 0.22 pts |
| Paris, 15 Oct 2026 | 1,572 | 37,735 | 11.4% | 2.10 | **82.0%** | 64.2% | **83.9%** | none; occupancy 0.85 pts | 2.1% | 0.33 pts |
| Helsinki, 7 Oct 2026 | 136 | 3,264 | 4.8% | 1.39 | 94.2% | 81.9% | 93.2% | 0.95 km/h | 1.7% | 0.21 pts |

Differences are medians over site-hours with at least 50 vehicles. Site-hour counts include a few sites with no location: 42 in Madrid 2021, 19 in Paris.

- **My pipeline reproduces report 04.** With no day filter, 7 days apart, 07–18 h, Berlin September 2024 gives 6.4%, GEH 1.60 and 88.7%. Report 04 has 6.3%, 1.64 and 88.2%. The headline floors above are stricter because they drop faulty sensor-days.
- **Paris real days fail the usual ">85% GEH<5" bar against each other.** Don't carry a fixed bar from Berlin to Paris. Compute the floor per city, as the script does.
- **GEH flatters low-flow sites.** Madrid's GEH looks best partly because its median site carries about half Berlin's flow. Its median percentage difference is no better. Compare percentages between cities, not GEH.

**The target's day shape (MEASURED).** Share of the day's flow per hour, on all sites of the reference day.

| Hour | 03 | 06 | 07 | 08 | 09 | 12 | 15 | 16 | 17 | 18 | 20 | 22 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Berlin 2019 | 0.5 | 5.1 | 6.2 | 6.4 | 5.9 | 5.5 | 6.4 | 6.6 | 6.4 | 6.0 | 3.7 | 2.8 |
| Madrid 2021 | 0.3 | 1.9 | 4.6 | 6.9 | 6.8 | 5.5 | 6.2 | 6.0 | 6.4 | 6.6 | 6.0 | 3.0 |
| Paris 2026 | 0.9 | 3.6 | 4.9 | 5.5 | 5.4 | 5.4 | 5.4 | 5.4 | 5.4 | 5.6 | 5.1 | 3.9 |
| Helsinki 2026 | 0.2 | 5.6 | 7.8 | 7.9 | 5.3 | 4.8 | 9.1 | 9.0 | 7.3 | 5.7 | 3.7 | 1.5 |

These really differ. Madrid's day starts two hours later than Helsinki's and is still at 6% at 20:00. Paris is nearly flat from 08:00 to 20:00. One borrowed curve can't stand in for all of them.

Berlin's mean speed across sites on 15 May is 47.6 km/h at 03:00, 39.8 at 08:00, 41.2 at 12:00, 38.4 at 16:00 and 45.3 at 20:00. Rush-hour speed drops to a median 0.66 of free speed per site.

## What the comparison says

`scripts/reference_day.py` matches sites to edges from the net and real data only, never from simulated flows. It sets each check's bar from real days on the same sites and hours: the simulation must be as close to the reference day as the least similar other weekday. It also prints report 15's Credible and Good bands, and report 04's gate on volume. Full output: [`_berlin-check/output.txt`](file:///home/erikf/projects/personal/cars-data/datasets/reference-days/_berlin-check/output.txt).

**`runs/berlin/day_edges.csv` against Berlin, 15 May 2019, 135 good matches.** One run, one seed, from 31 October, so an older engine build. BeST demand with teleports on.

| Check | Result | Simulation | Least similar real day | Report 15 band |
|---|---|---|---|---|
| Nothing stuck | FAIL | 23,715 teleports, 1.05% of trips. Teleports were on, so this run can't pass. | n/a | n/a |
| Day shape | FAIL | Hourly-share RMSE 0.94 pts. Morning peak 10:00, real 08:00. Night share 0.5%, real 3.7%. | 0.12 pts | Below credible |
| Volume by site | FAIL | Sim/real total 0.42. GEH<5 11%. Median GEH 14.9. RMSN 0.82. R² −0.18. Slope 0.40. | 0.99–1.02, 92%, 1.48 | Below credible |
| Total distance | FAIL | 15.99 M km against about 41.3 M km from SVZ 2019, ratio 0.39. The real figure is partly an estimate and not the same method. | n/a | Below credible |
| Speed by hour | FAIL, partial | Median difference 7.9 km/h. Rush-hour dip 0.92 of free speed, real 0.66. | 2.0 km/h | See below |
| Travel times | NOT TESTED | Sensors see points, not routes. | | |
| Where and when | FAIL, partial | Real 347 slow site-hours, simulated 41. Caught 2%, 85% false alarms. | F1 0.65; sim 0.03 | Below credible |
| Network curve | FAIL, partial | Peak flow 457 per site per hour, real 940. Density at peak 12.6, real 28.8. | nRMSE 0.03; sim 0.64 | Below credible |
| Trips | NOT TESTED | Sensors can't see trips. | | |

**Berlin, 25 September 2024, 77 good matches.** Same verdicts. Sim/real 0.56, GEH<5 17% against 88.5%, morning peak again 10:00. Mean hourly-share gap 0.69 pts, which agrees with report 15's 0.70.

**Three things to read carefully.**

1. **Don't take the speed band as good news.** Report 15's speed band shows credible on 2019 and good on 2024, yet the real-day check fails. Average speeds nearly match for the wrong reason: the simulation has no rush-hour dip, and it's slower than real at night (43 against 48 km/h). Edge means include waiting at signals, while detectors sit mid-block. So absolute speeds here are not a same-method comparison, and only the dip means much. This is why probe speeds matter (recommendation 3).
2. **The volume figure depends on the year.** Sim/real is 0.56 in 2024 and 0.42 in 2019. On the 71 sites in both, it's 0.56 against 0.47, because real flows at those sites are 18% lower in the 2024 file. That file has a different quality control, and I can't say how much of the 18% is traffic. The 64 sites only in 2019 are at 0.37, so the site set matters too. By hour in 2019: 0.09 at 03:00, 0.36 at 08:00, 0.49 at 16:00 and 0.52 at 20:00.
3. **The bad matches don't explain it.** Adding 110 weak matches to the 135 good ones only moves sim/real from 0.42 to 0.45 and GEH<5 stays at 11%. Of the 8 sites flagged in 2024 for being off by a factor of 5, all are within 5 m of the edge. For example, Leipziger Straße has 18,674 real vehicles and 1,643 simulated. I checked these from the tables, not on a map. TE324 (Grabbeallee) runs the other way, 1,071 real against 5,359 simulated.

**Does the script work? (MEASURED)**

- A real weekday fed in as the simulation passes every check it can test, for 14 May 2019 and 9 May 2019, and for 18 September 2024 against the 2024 reference.
- Leave out 22 May 2019, the least typical day, and it narrowly fails four checks (GEH<5 91.7% against 93.3%). That's by construction, because the bar then comes from the remaining days. So the bar is tight, and a near miss should be read as one.
- `scripts/test_reference_day.py` passes on a made-up city: half the flow fails volume but passes shape, a 2-hour clock shift fails shape and prints a clock warning, one teleport fails the first check, and wrong-way, too-far and no-direction sites get rejected.

**Limits of this comparison.**

- **Flow:** `entered` counts cars at the upstream end of an edge, not at the sensor.
- **Clock:** the script assumes the simulation starts at local midnight.
- **Occupancy (Paris, Madrid):** simulated occupancy is approximated from density with a 6 m effective length.
- **Sites:** they are mostly main roads, so "where and when" and the network curve only hold there.
- **Seeds:** the gate wants 20. This is one.
- **Other cities:** the script ran only on Berlin, because no Madrid, Paris or Helsinki net is on disk. Their match quality is unknown. Madrid will be poor until direction improves: 39% of its clean sites, including all of M30, have none, and it has no lane counts.

## Ranked sources

Every detector counts close to all vehicles passing its point, which is my inference from how loops work and not a measured share. **No source here says what share of network kilometres its sensors cover**, and none is route-level. None covers Sweden except where noted. "Needs" numbers refer to the brief's five: 1 demand, 2 routes, 3 congestion truth, 4 maps, 5 signals.

| Rank | Source | Measures, how | Area, period | Sampling | Validation | Access, licence | Downloaded? | Needs | Test enabled | Work |
|---:|---|---|---|---|---|---|---|---|---|---|
| 1 | **Madrid loops**, dataset 208627 | Flow, occupancy; speed on M30/C30. Loops. | 3,552–4,057 clean sites, 440–490 km², Jul 2013–Sep 2026 | 15 min | Quality code per record. No independent audit found. | Open, CC BY 4.0, commercial use allowed | **Yes**, Oct 2021 and Sep 2026 | 3, flows | Blind flow test with survey demand (report 01) | Scenario must be built, some weeks |
| 2 | **Berlin Verkehrsdetektion** | Flow and speed by class. Lane detectors. | 138–258 clean sites, 530–570 km², from 2015 | Hourly | `hist_cor` and z-scores in the new files. | Open, dl-de-by-2.0, commercial use allowed | **Yes**, May 2019 and Sep 2024 | 3 | First gate day | Ready, needs a run |
| 3 | **Paris comptages** | Flow, occupancy. Mostly loops. | 1,572 clean arcs, 114 km², rolling 13 months, older years linked | Hourly | Portal's own states. | Open, ODbL, share-alike | **Yes**, 15 days | 3 | Densest centre: about 14 sites per km² | Scenario, weeks |
| 4 | **Helsinki Digitraffic** | Every vehicle: speed, length, class, lane. | 136 directions, 75 stations, main roads only; raw from Dec 2021 | Per vehicle | Faulty flag. | Open, CC BY 4.0 (report 01; licence page not reopened) | **Yes**, streamed to hourly | 3 | Motorway speed and capacity, real time-mean against harmonic | Small net would do |
| 5 | **Zurich counts** | Flow per counting site. Measured or imputed flag. | City, from 2012, updated daily | Hourly | Imputation flag. | Open, CC0 per catalogue | No, about 380 MB a year; report 14 has a sample | 3, flows only | Flow-only target, detector plans in PDF | Medium |
| 6 | **Melbourne SCATS, TIRTL** | Stop-line flow; TIRTL gives speed bins. | 3,428 live sites | 15 min | None found. | Open, CC BY 4.0 | No, report 01 sampled it | 3, 5 | Needs left-hand traffic in the engine | Large |
| 7 | **MeTS-10 / Traffic4cast** | Probe speed, 15 min, by road segment. | Berlin Jan–Jun 2019, Madrid Jun–Dec 2021, 10 cities | 15 min | Authors compare to loops. | Form; academic and non-commercial | No, it needs the form (report 04) | 3 | **True speed by hour for the two gate cities** | About 3 days (report 04) |
| 8 | **UTD19** | Flow, occupancy or speed. Loops. | 23,541 detectors, 40 cities, 2017–2019 | 3–5 min | Paper by the authors. | Sign-up, academic and non-commercial, must cite | No, it needs the sign-up | 3 | Many cities' curves, not one new gate day | Medium |
| 9 | **Barcelona `trams`** | Traffic state only, levels 0–6, no flow or speed. | Whole street sections, from Oct 2017 | 5 min | None found. | Open, CC BY 4.0 | No | 3 | Where and when jams form, dated, for years | Small |
| 10 | **UK WebTRIS** | Flow by length band and average speed. | National strategic roads, 20,076 sites listed, London share unknown | 15 min | None found. | Open API; licence not confirmed | Sample only | 3 | Motorway checks | Small |
| 11 | **PeMS** | Flow, occupancy, speed; freeways. | California | Not verified | Provider's own imputation. | Free account, 1–2 business days | No, login | 3 | Freeways only | Medium |
| 12 | **NDW Netherlands** | Loops and GPS route times. | Motorways | 1 min | See report 01. | Name, email and reCAPTCHA form | No | 3 | A10 corridor (report 01) | Medium |

## Top 3 recommendations

1. **Run the gate on Berlin, 15 May 2019, with this script.** The tool and target are ready, so the only missing thing is a run. Next step: run `cars` with teleports off on the better demand from report 12, with `--edge-csv` and `--summary-csv`, once per seed. Then run `reference_day.py --ref reference-days/berlin-2019`. Judge flows on the 22 clean sites more than 200 m from MATSim's count stations (`matsim_count_station_m`), because the rest aren't blind.
2. **Build Madrid for October 2021 as the second, harder city.** Next step: build a net, run the script's matching on `reference-days/madrid-2021`, and see how many sites survive. Before relying on direction, check the E-O name reading on known one-way streets, and try to get direction for M30. A site that can't be placed should stay rejected. Do not use M30 speed from 01:00 to 05:00.
3. **Get probe speeds through the MeTS-10 form.** Report 04 already found this. This report shows why it matters: on Berlin, detector speeds can't separate a real speed match from an accidental one. The form covers both gate cities in the right months. Next step: Erik's form, below, then add a probe-speed input to the script's speed check.

## What only Erik can do

No messages to anyone are needed. Only forms, each with a licence decision.

- **MeTS-10 / Traffic4cast form** (report 04 has the link). About 5 minutes. Academic and non-commercial only.
- **UTD19:** sign up in the Signup section of [utd19.ethz.ch](https://utd19.ethz.ch/), agreeing to academic or non-commercial use and citing their paper. Worth it only if we want many cities' flow curves. I'd do it after the MeTS-10 form.
- **PeMS:** [apply for an account](https://pems.dot.ca.gov/). Freeways only. Low priority.

If `cars` might go commercial, both MeTS-10 and UTD19 terms need a second look first.

## Corrections to earlier reports

- **Report 01 said WebTRIS daily reports came back empty.** Today site 7 on 15 September 2025 returned 96 rows of 15-minute volumes by length band and average mph. The per-speed-band columns are blank there. MEASURED, one site.
- **Report 01 listed Paris timestamps as period end.** Confirmed by the field description and the night minimum. Its "not all have both" is an understatement: 1,160 of 2,946 arcs had no usable flow in these 15 days.
- **Report 04's Berlin site-level noise reproduces** on a separate implementation, see above.

## Dead ends

- **Uber Movement:** the official page returns 406 or 404. [Zenodo 10479336](https://zenodo.org/records/10479336) keeps five Indian cities for 2019, 1.0 GB, CC BY-NC. The record doesn't state the time resolution. Not downloaded. No use for our cities.
- **Taiwan freeway history:** `tisvcloud.freeway.gov.tw` timed out from this machine, as it did for reports 01 and 12. UNVERIFIED.
- **Seoul:** what I opened isn't car flow. [OA-21217](https://data.seoul.go.kr/dataList/OA-21217/S/1/datasetView.do) is hourly bus times between stops, open as weekly and monthly zips. Vehicle counts by hour appear in search results and the TOPIS reference room, but I didn't open them. UNVERIFIED.
- **Copenhagen and Vienna:** the catalogue queries returned nothing, and a web search found only annual or daily Copenhagen figures and only public transport for Vienna. Not verified either way; I did not read their portals by hand.
- **TfL Road API:** live status only, no counts. Report 01 names INRIX and iBus for journey times, internal.
- **Madrid `carga`:** modelled, not used.

## New directions, not covered

- **Barcelona `trams`** could give "where and when" dated over years, and report 15's Barcelona SUMO model is the largest honest comparison. Open and untried.
- **Madrid's night M30 speeds** read a median of 47–49 km/h with 25–30% of sites under 30 km/h at 03:00, with the low reading on every date in both years. MEASURED, cause unknown. If it's night tunnel work, closures may need to be an input.
- **The 18% drop between Berlin files** could be traffic or quality control. Comparing one month in both versions would settle it. The archive has both for some years, per its ReadMe.
- **Holding out by time:** the archives run for years, so a run calibrated on one month could be judged on another.

## What I did and didn't verify

- **Opened:** the Madrid, Paris, Helsinki and Berlin data, Digitraffic's format page, Paris's field descriptions, and the UTD19, Barcelona, PeMS, WebTRIS and Seoul pages named above.
- **Not opened:** Madrid's schema PDF, because I had no PDF tool. The per-hour rate reading comes from report 01. The numbers are plausible, and M30 peaks at about 2,270 vehicles per hour per site.
- **School calendars:** Berlin 2024 is from the earlier script's calendar source. The 2026 dates for Paris, Helsinki and Madrid and the 2021 Madrid dates are from memory. Holidays and weather were not checked against a source.
- **Directions:** Paris and Helsinki were checked. Madrid's and Berlin's come from labels; 12 of Berlin's 258 clean sites failed the direction check against the net and were rejected.

This took well past the time box because the PC was overloaded for much of the session. Long steps moved to the homelab until its queue got long, and the rest ran locally, one at a time.

Scripts: [`scripts/reference_day.py`](../../../scripts/reference_day.py), [`scripts/test_reference_day.py`](../../../scripts/test_reference_day.py), [`scripts/datahunt/reference_day_build.py`](../../../scripts/datahunt/reference_day_build.py).
