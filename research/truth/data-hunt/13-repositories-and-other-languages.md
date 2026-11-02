# 13: Data repositories and other languages

**Status: cut short.** I stopped early because the PC was overloaded (load 92, memory thrashing). The sweep is only partly done, and the gaps are listed below. A follow-up should run on the homelab.

## The answer

Yes, more exists, and two finds change the plan.

- **Hamburg publishes real signal behaviour openly.** A live API with no key covers 797 traffic lights and 20,086 lane connections. It gives signal state, program and detector occupancy to the second, plus the geometry of each ingress lane, egress lane and route. This is the signal data every earlier report failed to find. It keeps only about 8 days, so someone has to collect it, and I checked only one intersection in depth.
- **Xuancheng, China, has real routes for a whole city.** Plate cameras give complete trip paths for 30 days in April 2023, with 376,841 trips on the day I counted. It comes with a SUMO network. Its signal plans are designed by the authors, not measured.

**Stockholm got something, but less than it first seemed.** FlowSense gives a relative flow on all 204,032 street segments, from 3.2 million phones. It's only moderately accurate (Spearman ρ about 0.65 against measured counts, per the paper), and walking is mixed in. It also shows that raw 2024 GPS data for Sweden can be bought, from a company called Pickwell.

None of these three, nor Spain's phone-based OD, appears in reports 01, 02, 06 or 07 (name search). I could not check overlap with the other data-hunt reports, because that search stalled on the overloaded machine.

## Ranked: the 10 most useful that earlier reports didn't know

Grades are as the brief defines them. "Sampled" means I downloaded and read part of it. The full list, about 70 rows, is in [13-catalogue.csv](13-catalogue.csv).

| # | Dataset | What it gives | Grade | Share of vehicles | Access and licence | Checked |
|---|---|---|---|---|---|---|
| 1 | [Hamburg live signals](https://tld.iot.hamburg.de/v1.1/Things) | Signals (need 5), lanes (4), detector occupancy (3) | MEASURED | Not a traffic sample | Open API, dl-de-by-2.0 per the Hamburg portal listing | Small API samples |
| 2 | [Xuancheng 2026](https://doi.org/10.6084/m9.figshare.29925824) | Routes (2), demand (1) | MEASURED paths | Paper says nearly every vehicle on covered roads; no independent check read | Open, CC BY 4.0 | Sampled 1 day |
| 3 | [FlowSense](https://zenodo.org/records/16794871) | Stockholm link flow (1, 2) | MODELLED from measured points | Unknown | Open, GPL-3.0 | Sampled |
| 4 | [Hamburg archive](https://doi.org/10.25532/OPARA-466) | Two months of signals, Sept–Oct 2023 | MEASURED, authors warn of gaps | Not a traffic sample | Open, CC BY 4.0, 31.49 GB | Sampled first 60 MB |
| 5 | [Spain MITMA](https://movilidad-opendata.mitma.es/RSS.xml) | Hourly OD (1), maybe routes (2) | MODELLED expansion of phone data | Not read | Open; licence PDF not read | Sampled 1 day |
| 6 | [Helsinki drones](https://zenodo.org/records/19684712) | Nordic driving, about 170,000 tracks | MEASURED | All vehicles in view, small area | Open, CC BY 4.0, 2.2 GB | Sampled 1 zip |
| 7 | [Athens 2024 drones](https://zenodo.org/records/19555816) | Over 800,000 tracks at 10 sites | MEASURED | All vehicles in view | Open, CC BY 4.0, 7.7 GB | Metadata |
| 8 | [Glasgow counts](https://doi.org/10.5281/zenodo.14537113) | 4 years of 15-minute urban counts (3) | MEASURED | Unknown | Open, OGL UK 3.0, 53 MB | Sampled |
| 9 | [València archive](https://zenodo.org/records/20817050) | 15-minute road state and loops, 2020–25 (3) | MEASURED, state labels not audited | Unknown | Open, CC BY 4.0, 12.6 GB | Metadata |
| 10 | [Songdo drones](https://doi.org/10.5281/zenodo.13828383) | About 700,000 tracks at 20 junctions (list's figure) | MEASURED | All vehicles in view | Open, CC BY 4.0 | File list |

### What I measured or read

- **Hamburg API:**
  - There are 20,018 primary signal streams, 20,018 program streams, 20,019 cycle-second streams and 6,579 car detector streams.
  - The oldest observation on one stream was 2026-10-24, and an hour in October 2025 returned nothing. That is where the 8-day figure comes from.
  - Connection 353_13 logged 160 state changes in one hour, and its latest readings were minutes old.
  - **Quality warnings:** some timestamps are in the future, and the latest cycle-second values I saw were all 0. Detector values are labelled "signal change request", so they aren't vehicle counts.
- **Xuancheng, 2023-04-04:**
  - 376,841 trips, averaging 14.39 road links, with peaks at 07:00 (37,486) and 17:00 (39,203).
  - 396 road segments have no camera, and 394 of those are one-lane branch roads, per the paper.
  - The network comes from OSM. Its 132 `tlLogic` entries, such as the 31 s phases I saw, are not real signal plans.
  - I did not run the join between route IDs and network edge IDs, though they share a prefix.
  - The 2020 data paper reports 97% of intersections equipped, and r = 0.748 against another count on some roads. That is the earlier release, not this one.
- **FlowSense:**
  - 85 million trajectories in Stockholm, averaging 0.9 km and 1.9 minutes, which is why walking leaks in.
  - Stockholm ρ falls from 0.600 to 0.390 when filtering by speed, so a speed filter doesn't isolate cars there. Gothenburg highways reach 0.809 with one.
  - Its ground truth is 366 sites of the same city counts report 01 found, so it adds no independent check for those sites.
  - My match joined 362 of the 366 sites to a segment within 25 m. **I did not compute my own correlation** before stopping. The saved match is `flowsense-se/match_flows_sthlm_flows_2024_random1to10.pkl`.
- **Spain, 2025-10-15:**
  - 13,643,808 rows and 157.9 million trips nationally, of which 10.13 million are within Madrid-city districts.
  - These are all modes, not cars, so the figures can't be used directly as vehicle demand.
  - Madrid's hourly profile has peaks around 08:00 and 18:00.
  - The method changed on 2025-07-01, so don't compare across that date. The notice PDF failed to download (347 bytes).

## Top 3 recommendations

1. **Start collecting Hamburg signals now, on the homelab.** History older than about 8 days disappears. Poll or subscribe by MQTT for a few weeks, then rebuild real plans for a corridor and compare stop-line behaviour with detectors. First check how many of the 797 are actually live. This would also make Hamburg a serious second city, with counts available on the [other API](https://iot.hamburg.de/v1.1/Datastreams).
2. **Use Xuancheng as the route-replay test.** Run the join check, then replay one real day through `cars` and compare link flows and hourly shape on held-out days. It tests routes, but not signals, and it's a mid-sized Chinese city rather than Stockholm.
3. **Use FlowSense only as a rank check for Stockholm.** Compare simulated link flow with its ranking on streets that have no counter, and don't calibrate to it. Compute ρ on the saved match first.

## What only Erik can do

I wrote no drafts, because his writing style skill lives in Executor, which failed to connect (503). Points for him to raise:

- **Chalmers (FlowSense authors):** can flows be cut by time of day, or restricted to car-like trajectories? Can they share the map-matched route counts in aggregate form? The paper names this as future work.
- **Pickwell:** price and terms for 2024 Stockholm points, and a sample. I never opened the provider's own site. GDPR needs review before any purchase.
- **Be-Mobile:** the [Zenodo pointer](https://zenodo.org/records/21335488) offers FCD access, mostly in the Benelux. Only worth asking if Sweden is covered.
- **Stockholm's Bluetooth sensors and LiU taxi GPS:** search results only, so first find out whether any data can be released.

## Dead ends

- **Search failures:** direct Zenodo search returned nothing (cause not investigated), but single-record calls work and DataCite covers it. WebFetch can't open arXiv or research.chalmers.se; curl works for Chalmers, and I didn't try it on arXiv.
- **Modelled, so not truth:** 20 US cities assignment, global AADT, global commuting OD, synthetic Los Angeles trajectories, Xuancheng synthetic trips.
- **Not all-car data:** the Berlin and NYC "urban traffic volume" set is Strava cycling and taxis.
- **Raw data not included:** the Kunming resilience dataset leaves out its Amap and Baidu inputs.
- **Hamburg stream IDs** from the archive return nothing on `iot.hamburg.de`. Use `tld.iot.hamburg.de`.
- **ETC2.0 Japan:** search summaries show case-by-case lending only, with no public download.

## Not covered, and how much to fetch later

**Not done:** Kaggle, PapersWithCode, IEEE DataPort and Mendeley as proper searches, survey-paper tables, Tianchi and KDD Cup data, Traffic4cast access, Chinese city portals beyond search summaries, and French, Dutch and most German, Spanish and Swedish portals. Korean and Japanese coverage is search summaries plus one JARTIC page. The catalogue's status column marks these: `NOT DONE`, `NOT OPENED`, `TITLE ONLY`, `SEARCH LISTING` and `SEARCH SUMMARY` are all unverified.

**Fetch on the homelab:**

| What | Size | Why |
|---|---|---|
| Hamburg live collector | Unmeasured; test on a few signals first | History expires after about 8 days |
| Hamburg archive | 31.49 GB zip, 164.5 GB unpacked | Stream it, never unpack on the PC |
| Xuancheng remaining 29 days | About 5.5 GB (estimate from 30 files of about 190 MB) | Held-out days |
| FlowSense `road_network.zip` | 524 MB | Geometry join |
| Spain, one week of districts | About 1 GB at 137 MB a day | Madrid profile |
| Spain route files | Sizes not read | Check first whether they really hold routes |
| Athens 2024 | 7.7 GB | Behaviour |
| Helsinki, rest | 2.2 GB | Behaviour |
| València | 12.6 GB | Congestion |
| 20-city FCD CO2 | 19.6 GB | First check whether Stockholm is included; metadata only |

**Already on disk**, under `/home/erikf/projects/personal/cars-data/datasets/`, about 900 MB: `flowsense-se`, `xuancheng-2026`, `hamburg-signals-opara`, `helsinki-drones-2026`, `glasgow-scoot-2025` (SCOOT is my mislabel, unconfirmed), `mitma-spain-od`, and raw search hits in `13-sweep`. Scripts are in [13-scripts](13-scripts).

**Next steps for the sweep:** triage the rest of `13-sweep/datacite.tsv` (635 rows), `crossref.tsv` (377) and `hf.tsv` (219), since I only read filtered views. Of the Hugging Face hits, `tjtrans/Traffic-Demand-Bench` and `CAMUS-LAB/data-road_network_eta` looked worth opening.

**New direction:** cities that publish controller data, as Hamburg does, may exist elsewhere in Germany. The search also turned up a federal real-time signal data project (EDEL), which I did not open.

## Environment

Executor returned 503 for the whole session, so I never searched the company brain and published nothing there. I did not start a repair session, because the task didn't depend on it and the machine had no room. This still needs fixing.
