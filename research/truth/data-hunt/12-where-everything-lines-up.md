# 12: Which place can prove human-only traffic is close to a real day?

Checked 2026-11-02. Nobody was contacted, no accounts were made, and no download was run as a program. Ranked for the test in `research/truth/VALIDATION-GATE.md`, not for general data richness.

Grades: **MEASURED** means I opened the data or a file and calculated it. **PROVIDER CLAIM** means the source says so. **MODELLED** means inferred or simulated. **UNVERIFIED** means I could not open it. Scores and recommendations are my opinion.

## The answer

**No place has everything. Run the first gate on Berlin, on Wednesday 15 May 2019, and use Madrid as the second, stricter city.** Stockholm can't run this test today: it has no open dated network counts, no open dated speeds and no measured OD.

Berlin wins because it's the only place where a whole test can start soon. It has open dated flows and speeds through the day, probe speeds from the same months, a ready demand of 4.42 M trips and right-hand traffic.

Three things about Berlin differ from how it was described:

1. **2024 is the wrong year for the probe speeds.** We hold only September 2024 detectors, while MeTS-10 Berlin covers January to June 2019. I downloaded May 2019 detectors, and they work.
2. **MATSim v6.4 demand isn't blind on flows.** It was fitted to 2018 counts from the same traffic centre. 222 of 266 detector cross-sections sit within 50 m of a calibration station on the same carriageway. Only 24 are more than 200 m away. Speeds are still a blind test.
3. **Berlin has no real signal timing that I could find.** A pass there can't show that signals are right, and the gate must label them as estimated.

Madrid is the opposite: its survey demand owes nothing to its loops, so its flow test is blind, but nobody has built the scenario yet.

## Ranking

Each column is 0 to 3. A score of 0 for independent demand means the place can't pass rule 4 of the gate, so those places rank below the rest whatever their total. "Can run" means right-hand traffic plus how much of a scenario exists. It gives no credit for past use.

| Rank | Place and day | Dated flows | Dated speeds | Independent demand | Dates line up | Can run | Total | In one line |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | **Berlin, May 2019** | 2 | 2 (3 with the HERE form) | 1 | 2 | 3 | **10** | Blind on speed and on 24 stations, ready soon |
| 2 | **Madrid, autumn 2021** | 3 | 1 (3 with the HERE form) | 2 | 1 | 1 | **8** | Best flows and blind demand, but must be built |
| 3 | **Melbourne, first half of 2019** | 3 | 1 | 2 | 2 | 0 | **8** | Engine has no left-hand traffic, and probe data is thin |
| 4 | **Shenzhen, Apr and Aug 2021** | 1 | 2 | 1 | 1 | 1 | **6** | Demand from one day, test on another, but only 44% of vehicles |
| 5 | Hong Kong, any day from 2022 | 3 | 2 | 0 | 3 | 0 | 8 | Excellent sensors, no open demand found, left-hand |
| 6 | Jinan, 17 Oct 2022 | 1 | 2 | 0 | 2 | 2 | 7 | One day, so demand and truth share a source. Engine test only |
| 7 | Xuancheng, Sept 2020 | 1 | 1 | 0 | 2 | 1 | 5 | Its "loops" are resampled from the same reconstruction |
| 8 | London, late 2019 | 1 | 1 | 0 | 2 | 0 | 4 | No open demand found, left-hand |
| 9 | **Stockholm, today** | 0 | 0 | 0 | 0 | 2 | **2** | Could jump if Swedish owners release data. Unproven |
| 10 | Hamburg | 0 | 0 | 0 | 0 | 2 | 2 | Not a gate city, but the best signal data I found |

Singapore isn't scored because almost everything relevant needs a signed request. If granted it could beat most of this table, though it drives on the left.

## Berlin in detail

### What I measured

**Detectors, May 2019 (MEASURED).** The file has 266 cross-sections with hourly flow and speed, split into all vehicles, cars and trucks. 238 are complete on all 11 Tue–Thu days I tested. These are main roads, not the whole network.

Real network shape on Wed 15 May 2019, for those 238 cross-sections, with speed as flow-weighted harmonic mean:

| Hour | 03 | 06 | 07 | 08 | 10 | 12 | 14 | 15 | 16 | 17 | 18 | 20 | 22 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Crossings per hour (thousands) | 17 | 169 | 207 | 212 | 185 | 186 | 206 | 216 | 220 | 214 | 201 | 123 | 93 |
| Speed (km/h) | 46.9 | 43.7 | 39.9 | 38.2 | 40.8 | 39.4 | 37.5 | 35.0 | 34.6 | 37.6 | 38.9 | 44.4 | 45.4 |

The total is 3,343,370 crossings. The rush-hour dip is clear in both peaks.

**How much one real day differs from another (MEASURED).** This is the gate's basic bar. Figures use eight normal Tue–Thu days in May 2019, hours 06 to 20, all day pairs:

| Measure | Between real days |
|---|---|
| Site-hours with GEH under 5 (a standard flow-match score; lower is closer) | 90.3% |
| GEH, median / 95th percentile | 1.57 / 7.11 |
| Flow difference at a site, where flow is at least 200/h: median / 95th percentile | 5.5% / 24.8% |
| Speed difference at a site: median / 95th percentile | 2.0 / 13.0 km/h |
| Network daily total across 11 days | 3.29 to 3.45 M |
| Network speed at 08:00 / 16:00 across 11 days | 33.5–39.7 / 33.3–37.5 km/h |

The 11-day ranges include days next to holidays, so they're wider than a normal-week spread. On 15 May, 318 of 3,936 site-hours at 74 cross-sections were under 25 km/h, which gives a "where and when" target.

**Is v6.4 independent of these sensors? (MEASURED and read in the source)**

- The [Makefile](https://github.com/matsim-scenarios/matsim-berlin/blob/release/v6/Makefile) builds `berlin-v6.4-counts-vmz.xml.gz` from `vmz_counts_2018/Datenexport_2018_TU_Berlin.xlsx`. The file has 461 locations, is marked year 2018, and holds hourly values.
- I matched those links to the public cross-sections by position and direction: 222 are within 50 m on the same carriageway, 235 within 100 m, 242 within 200 m. **24 are farther than 200 m, and 31 farther than 100 m.** List: `cars-data/datasets/berlin-2019-detectors/holdout_match.json`.
- The published `plans-initial` isn't the clean version. The Makefile builds it from `plans_cadyts`, after count-based selection. The earlier `berlin-initial-v6.4-25pct.plans.xml.gz` isn't in the public input folder I listed.
- The fit is limited. Per the [scenario description](https://svn.vsp.tu-berlin.de/repos/public-svn/matsim/scenarios/countries/de/berlin/berlin-v6.4/documentation/berlin-v6.4-scenario-description.pdf), counts choose among five candidate location sets per agent. Mode share and distances are fitted to the SrV 2018 survey. So counts shape where trips go more than how many there are.
- Its authors report that daily simulated volumes are generally too low, particularly on motorways ([Rakow et al.](https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2024/24-22/RakowEtAl_MATSimBerlinEWGT.pdf)). Commercial traffic rests on older, weaker data. So a volume failure at the gate wouldn't by itself point to our engine.

### What each gate check would really prove there

| Gate check | Berlin evidence | Blind? |
|---|---|---|
| Nothing stuck | The run itself, teleports off | Yes |
| Day shape | Detector hourly flow | **Partly.** Same sensors were fitted to 2018 hourly values |
| Volume at sites | 24 clean cross-sections; SVZ 2019 links | **Yes, on those.** The other 242 aren't blind. SVZ is expanded from 12-hour counts, with 12.6 M km of 41.3 M estimated (report 03) |
| Total distance | Official 41.3 M km per working day, 2019 | Yes, but part estimated |
| Speed by hour | Detector speeds; MeTS-10 per road class | **Yes.** Neither was used to fit demand |
| Travel times | 1,000 routes at 10 hours in `routes-ref.csv.gz`, from routing services | **Weak.** Commercial estimates from a later year, used to set v6.4's free speeds. `cars` must not take those speeds if this check is to stay blind. The dip in them is small, 40.5 to 46.9 km/h |
| Where and when | Slow site-hours; MeTS-10 segments | Yes |
| Network curve | Only at the 238 sites | Yes, but a sensor-site curve, not the whole network |
| Trips | SrV distances and durations | **No.** Fitted to the same survey |

### Inputs to label under gate rule 3

| Input | Label |
|---|---|
| Demand | MODELLED from survey and census, partly fitted to 2018 counts |
| Trucks and vans | MODELLED, from older and weaker data |
| Network | OSM of 2023-01-01, so four years after the test day. BeST's is OSM of November 2020, hand-adjusted. A May 2019 OSM extract would be cleaner |
| Lanes | Estimated from OSM |
| Signals | **Estimated.** One search found no open Berlin signal programs. Not proof they don't exist |
| Weather, roadworks, events on 15 May | Not checked. Do it before freezing the day |

### Why not September 2024?

It's still useful as a second day, because the OSM network is closer to it. But it has no MeTS-10, and SVZ and SrV are five to six years older. Report 03's 16–24% level gap between detectors and SVZ compared 2024 with 2019. Rerunning it with 2019 detectors removes the year from that question, and should be done first.

## The other places

**Madrid (rank 2).**
- *Flows:* report 01 audited December 2022 at 4,073 urban points, every 15 minutes. The catalogue lists 2019 and 2021 months, including October 2021, but I did **not** download them, so the 2021 site count is UNVERIFIED.
- *Speeds:* urban loops have none, only M30 does. So urban speed rests on MeTS-10 alone, with 0.36 daytime coverage and dates of June to December 2021 (paper, Table I).
- *Demand:* EDM2018 has 222,744 diary trips across 1,259 zones (report 01). It's independent of the loops, but covers residents only, has no trucks, and is three years older, with the pandemic in between.
- *A trap:* the open phone OD doesn't cover the probe window. Version 1 ends 9 May 2021 and version 2 starts in 2022 ([codebook](https://ftp.fau.de/cran/web/packages/spanishoddata/vignettes/v1-2020-2021-mitma-data-codebook.html)). I didn't confirm that it splits by mode.

**Melbourne (rank 3).** Report 01 called it the evidence winner, but for this test it isn't.
- *Flows:* the 2019 SCATS file is listed at 1.46 GB under CC BY 4.0. I read the metadata only.
- *Speeds:* probe coverage is just 0.08.
- *Demand:* [AToM](https://arxiv.org/abs/2112.12071) is open and built from census and VISTA 2016–18. It calibrates mode choice, and its check against road data is on hourly shares at 87 segments, with error under 25% in peak hours. It has no freight or outside travellers by its own account, so totals would come out low.
- *Blocker:* the engine has no left-hand traffic.

**Shenzhen and Jinan (ranks 4 and 6, [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10582153/)).** Figures are PROVIDER CLAIM.
- *Jinan:* 17 Oct 2022, 1,838 cameras, 963,125 vehicles against about 0.89 M reported by the traffic bureau. Speed against Amap has an error (MAE) of 7.66 km/h.
- *Shenzhen:* 16 Apr and 24 Aug 2021, 1,460 cameras in four districts, about 44% of vehicles. Recovered trajectories were checked on 423 vehicles, with F1 0.86.
- *Limits:* paths between cameras are inferred, there are no signals, and the map is OSM. Jinan has only one day, so demand and flow truth are the same data.
- *Use:* feed recovered trips in and compare speeds. That's a good **engine test with near-true demand**, but it doesn't pass this gate.
- I only read the paper. I didn't open the Jinan files another agent downloaded.

**Xuancheng (rank 7, [collection](https://doi.org/10.6084/m9.figshare.c.5796776.v1), [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC9877028/)).** CC BY 4.0, about 80,000 vehicles a day, cameras at about 97% of intersections.
- `loop.csv` and the floating-car file are resampled from the reconstructed trajectories, so they aren't independent sensors.
- Independent checks are modest: flow correlation 0.748 at two junctions in one hour, and travel-time correlation about 0.69 to 0.75 against map services.
- Full trajectories are encrypted behind a program, which our rules don't let us run. A person would have to approve running it in a sandbox.
- `signal.csv` holds green intervals per movement, but the paper doesn't say where they came from (UNVERIFIED), and they cover only a morning sample.
- Sources disagree on that sample's hour: the listing says 8:00–9:00, the paper 7:00–8:00, and the first `lpr.csv` rows I read are at 07:22 on 2020-09-09.
- I stopped my scan of the month's day shapes because the PC was overloaded. It isn't needed for the ranking.

**Hong Kong (rank 5).** MEASURED: one snapshot has 580 detectors and 3,208 lane rows, per lane, every 30 seconds, with speed, volume and occupancy. The official archive lists 2,748 versions over two days in January 2022 (1.18 GB) and 2,829 over three days in January 2025 (1.98 GB), so it has gaps to check. Journey times are archived too (checked for January 2024). I found no open OD, though that was not an exhaustive search. It drives on the left.

**Hamburg (rank 10, but a real find).** [Open signal feed](https://tld.iot.hamburg.de/v1.1/), MEASURED:
- 797 junctions, 20,086 lane connections with geometry and lane type, and 20,018 signal streams with per-second state changes.
- 6,579 car-detector streams. One lane had 3,134 detector events on one day. Whether those events are vehicle counts is UNVERIFIED.
- History is rolling, about nine days: the oldest values on my test streams were 24 Oct, and a 2024 query returned nothing.
- Quality filtering is needed, because some timestamps are in 2007, 2009 or the future.
- I found no probe speeds or OD, so it can't be a gate city. Signal programs here are measured, which Berlin lacks.

**Stockholm (rank 9).** Scored without credit for being home.
- Open today: `Arstrafik` has no dated days, and FlowSense (report 05) has no time of day.
- Key-gated: Trafikverket flows are probably live-only, and bus positions are a partial speed signal.
- Report 05 found valuable non-public extracts: per-lane, per-minute toll passages, and 599,271 INRIX trips from 16 Sep to 21 Oct 2019. I didn't verify those. If released, autumn 2019 could become a strong test, so the score should be redone then.

**Singapore.** The [on-request list](https://datamall.lta.gov.sg/content/datamall/en/on-request_datasets.html) names signal phase timing per junction, junction loop counts, taxi GPS every 30 seconds, and private-hire and taxi trips with pick-up and drop-off coordinates. It needs a data sharing form with an NDA. Approval isn't known, and it isn't clear whether a private individual qualifies.

## Sources

| Source | Measures, how | Share of vehicles | Rate | Level | Accuracy | Access, licence | Sweden | Downloaded | Serves | Work (opinion) |
|---|---|---|---|---|---|---|---|---|---|---|
| Berlin detectors 2019 | Lane detectors, flow and speed | All passing, at 266 sections. Network share unknown | Hourly | Link | Old QA; quality field | Open, dl-de-by-2.0 (report 01) | No | **Yes, May 2019** | Truth | Days |
| Traffic4cast + MeTS-10 Berlin | GPS probes | Unknown fleet share | 5–15 min | Segment | Sensor comparison by authors | Free form, academic and non-commercial | No | No (paper read) | Truth | About 3–4 days (report 04) |
| MATSim v6.4 | Agent model | Modelled 10% and 25% samples | Per trip | Route | Authors: volumes low | CC BY 4.0 | No | Counts, routes, description; plan heads only | Demand | 1–2 weeks to map and route |
| Madrid loops | Loops | All passing, at sites | 15 min | Link | Quality flags | CC BY 4.0 | No | Not this session | Truth | Days |
| Madrid EDM2018 | Travel diary | 222,744 weighted trips | Per trip | Zone OD | Survey | Reuse allowed (report 01) | No | Not this session | Demand | Weeks with routing and trucks |
| Hong Kong detectors | Fixed detectors | All passing, at sites | 30 s | Lane | Validity flag | Open; licence not checked | No | Snapshot | Truth | Days, plus left-hand port |
| Hamburg TLD | Controller feed | Signals: all listed junctions | Per change | Lane connection | Bad timestamps exist | Open; dl-de-by-2.0 on sibling datasets, this one not checked | No | Samples | Signals, lanes | Days |
| Jinan / Shenzhen | Camera re-identification | Jinan near all, by bureau figure; Shenzhen 44% | Per camera | Route, inferred | See above | figshare; licence not stated on page | No | Other agent holds Jinan | Demand, routes | About a week |
| Xuancheng | License plates | About 97% of junctions; vehicle share not established | Per junction | Stream | r about 0.7 | CC BY 4.0 | No | Other agent holds it | Engine test | Days; trajectories blocked |
| Songdo Traffic | 10 drones, 20 junctions | All in view, in sessions | 30 Hz | Trajectory | No figure on record page | CC BY 4.0 | No | Other agent's folder | Local queues | Later |

## Top 3 recommendations

**1. Make Berlin, 15 May 2019, the first gate.** Freeze the rules before anything runs.
- Next steps: Erik fills in the HERE form. Then an agent generates MeTS-10 for May 2019 with `heavy`, rechecks the 15 May conditions, routes v6.4 and adds virtual detectors that measure like the real ones.
- Pass bar: the between-days table above.
- Report the 24 clean stations and all speed checks as the blind result. Report the other 242 as in-sample.

**2. Make Madrid the replication city, because its flow test is blind.**
- Next steps: after the same form, get Madrid 2022 movies, download October 2021 loops and confirm the site count.
- Build car-driver demand from EDM2018, with trucks labelled invented or modelled.
- Do this after Berlin's pipeline exists, since most of it carries over.

**3. Collect a week of Hamburg signals, as a test of the signal assumption.**
- Berlin's timing is estimated. Real Hamburg cycle lengths and green shares by road class give a measured range for a similar German city. Use that range to test how much Berlin's result changes with timing.
- Next step: a small daily collector for a sample of junctions, gentle on the service, within the nine-day window. It isn't written yet.

## What only Erik can do

1. **HERE Traffic4cast form** (report 04 has the details). Free, for educational use. It requires accepting non-commercial, no-redistribution terms, which could matter if `cars` ever goes commercial.
2. **Ask TU Berlin for the count-free plans.** Getting them would make Berlin's flow test blind at every station.
3. **Ask Berlin for signal programs.** Lower priority.
4. **Decide on Singapore's form.** Worth it only if a left-hand port is acceptable, and the NDA would limit publishing.
5. **Decide on Xuancheng's program.** Only if you want its full trajectories; it would need a sandbox.

These are plain drafts. **They haven't had the `erik-writing-style` pass, because Executor was down for this session (503).** Please edit them before sending.

To the VSP group at TU Berlin:

> Hello, I'm building a traffic simulator and want to test it against a measured day in Berlin in 2019, using your v6.4 scenario as demand. To keep the flow check blind, I'd need the plans from before count-based selection: `berlin-initial-v6.4-25pct.plans.xml.gz` and the small-scale commercial input used for the Cadyts step. They don't seem to be in the public input folder. Could you share them, or tell me if that isn't possible? I'd credit the scenario as you ask. Thanks, Erik Frankling

To Berlin's Senate transport department:

> Hello, I'm testing a traffic simulator against measured Berlin traffic from May 2019 and would like to use real signal timing. Are signal programs (cycle times and green times per time of day) available for research for a sample of main-road junctions, ideally as they were in 2019? If there's a process for requesting this, please point me to it. Thanks, Erik Frankling

## Dead ends and what wasn't opened

- **Taiwan freeway history (`tisvcloud.freeway.gov.tw`):** timed out from this machine three times. TDX returned only a tiny stub. The per-vehicle trip claim is UNVERIFIED and comes from memory. It would be freeway-only, and demand and truth would share a source.
- **Utah ATSPM:** 403. The raw archive is unconfirmed.
- **Seoul signals:** the nationwide live feed runs from March 2026 and needs a key. The provider says "for reference only", and it describes no archive. TOPIS was only opened at its home page, not assessed.
- **Spain's mobility portal:** 403 to my fetch, so I relied on the codebook.
- **Singapore real-time taxi URL:** my guessed URL returned 404. **Hong Kong speed map:** same.
- **v6.4 `plans-initial` as a clean demand:** it isn't. Don't repeat this idea.
- **Uber Movement:** gone (report 04).
- **Hamburg history:** there's no long archive through this feed.
- **Not newly opened, because the priority changed mid-task:** Copenhagen, Dublin, Bologna, Ingolstadt, Nashville, New York, Los Angeles, Paris, Barcelona, Zurich, Helsinki, Netherlands, Tokyo, Hangzhou, Toronto (catalogue fetched, not assessed). Where report 01 covers them I didn't re-score them. None is ranked here, and that's not evidence that they fail. I found no reason to expect full-day network speeds plus independent demand in them, but that's unproven.
- **Small full-observation sites (Athens, Songdo, Lankershim):** they don't cover a day or a network. They suit junction checks, not this gate.

## New directions

- **A May 2019 OSM extract for Berlin,** so that network and test day match.
- **Stockholm, autumn 2019, if released:** INRIX trips and toll passages from the same weeks. It would be demand and flow from separate sources.
- **Istanbul and Moscow** have much higher MeTS-10 coverage (0.63 and 0.71). I didn't check whether either has open dated flows.
- **Shenzhen's two days** allow train-on-one, test-on-the-other, if the open district boundaries can be handled.

## Reproduce

Scripts are in `research/truth/data-hunt/scripts-12/`: `berlin2019.py`, `berlin_noise.py`, `holdout_berlin.py`, `routesref.py`, `hamburg_inventory.py`, `stamm.py`, `peek_plans.py`, and `fetch-log.txt` for most anonymous fetches. Data is in `cars-data/datasets/`: `berlin-2019-detectors`, `matsim-berlin-docs`, `hamburg-tld`, `hk-td`, `singapore`, `xuancheng`, `melbourne-atom`. I deleted the bulky plan samples and link geometries after use; the URLs are in the v6.4 input folder.

The position match uses my own conversion from WGS84 to UTM zone 32, the zone the link coordinates fit. It produced a median distance of 14 m with sensible street names in the samples I read, but a nearby calibration station on a parallel road could still count as a match, so the 24 is a cautious count.
