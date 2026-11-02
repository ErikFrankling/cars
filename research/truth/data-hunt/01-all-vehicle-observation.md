# Data hunt 01: datasets that observe most of the cars in an area

Written 2026-11-02. **Cut short:** the PC was overloaded, so all downloads and processing stopped and this report uses only what was already on disk. Unfinished work is listed in "Unfinished" and "Fetch later".

## The answer

Erik is right that this data exists. Nothing open shows every car continuously for a whole day across a whole city, but three open sources get close, and none was in the earlier reports:

- **Cambridge, UK (best measured source):** 8 full days in June 2017. Plate cameras at about 90 sites give one row per vehicle journey, with the camera sequence, vehicle class and time between cameras. Tuesday 13 June has 178,662 journeys and 840,010 camera reads. These are real observations, but only at the cameras.
- **Xuancheng, China (most complete open package):** plate reads with turns, signal intervals for 161 junctions and turn-level lane data. It is open under CC BY, but the raw plate reads cover only one hour (25,197 vehicles). The full month is encrypted and can only be reached through the authors' tool.
- **Jinan and Shenzhen (Yu et al., another agent has these):** the only open full-day, whole-city vehicle paths I know of. They are reconstructed by matching vehicles across cameras, not directly observed. Their share figures don't work as coverage: Jinan recovers about 108% of the bureau's vehicle count and Shenzhen about 44%.

Drones, lidar and overhead cameras see nearly every vehicle, but only over about 1 to 7 km of road or for short periods. They are good for testing driving behaviour, not a city's day. I found no open plate-read dataset for Hangzhou.

For Stockholm, I found a city catalogue record for two years of plate/radar data on Hornsgatan that includes the **owner's postcode**. It has no download link, so someone has to ask for it (draft below).

## How to read the evidence

Grades: **MEASURED** means I measured it on downloaded data. **PROVIDER CLAIM** means the source's own statement. **MODELLED** means reconstructed or simulated. **UNVERIFIED** means from a search snippet or not opened.

Most paper and web pages were read through a fetch tool that returns a summary, not the original text. Check any provider number against the source before citing it. Only the MEASURED numbers come from files I read myself. "Share of all vehicles" has not been independently measured for any source here.

## Ranked table

Ranked by how much of an area's traffic it shows over a whole day, then by openness.

| # | Dataset | What and how | Area | Period | Share of all vehicles, and how known | Sampling, level | Access, licence | Downloaded? |
|---|---|---|---|---|---|---|---|---|
| 1 | **Jinan / Shenzhen** (Yu 2023) | Vehicle paths recovered from camera video | Whole city, >1,000 km² per a citing paper | 1 day Jinan, 2 days Shenzhen in the report I read | Jinan 963,125 vs about 0.89 M bureau figure (108%), Shenzhen 44% of a government total. PROVIDER CLAIM, MODELLED | Camera sightings, route | Figshare. Another agent has it | By another agent |
| 2 | **Cambridge ANPR 2017** | Plate cameras, trip chains and OD tables | Greater Cambridge, 96 numbered locations, 91 site sheets on 13 June | 8 days, 24 h, 10–17 June 2017 | Unknown. The workbooks refer to manual counts and match rates, but I didn't find them. 82.2% of reads fall in a chain of 2+ cameras (MEASURED, my calculation) | Per journey, camera-to-camera route | Open download. **Licence not found** | 1 of 8 days |
| 3 | **Xuancheng** (Wang 2023) | Plate reads, signals, lanes; month of reconstructed flow | Whole city: 1,156 directed links, 399 nodes, about 28 × 20 km | Raw: 1 h, 9 Sep 2020. Modelled: Sep 2020 | 97% of junctions have readers, about 80,000 vehicles/day (PROVIDER CLAIM). Share not independently measured | Per vehicle at junctions, route with gaps | Figshare, CC BY 4.0. Full month encrypted | Yes, except `fcd.csv` and `fullTraj.zip` |
| 4 | **Xuancheng trips** (Li 2023) | Synthetic trips built from plate data | Same city | Source month Aug–Sep 2019 | 823,177 vehicles, 9,002,572 trips in source (PROVIDER CLAIM). Release is MODELLED | Trip | Data link not confirmed | No |
| 5 | **Padua AVI** | Plate cameras, hashed, aggregated before release | City, about 93 km², 66 of 96 sensors kept | 6 Feb–1 Apr 2026 | About 400,000 passages/day (PROVIDER CLAIM). Share not stated | 10 min counts, hourly transition and travel-time tables. No trips | Zenodo, CC BY 4.0 | Yes, 31 MB, partly inspected |
| 6 | **Taiwan M06A** | Toll-gantry trip records | National freeways only | Published since 2016 | Not verified | Per trip, gantry sequence | Free, Open Government Data License 1.0. Archive host timed out from here | No. Folder `taiwan-freeway` suggests another agent has it |
| 7 | **I-24 MOTION** | 276 overhead cameras | 6.75 km freeway | 47 h over 10 days | About 150,000 vehicles/day road. Tracking recall 0.95–0.96 against hand labels (PROVIDER CLAIM) | 25 Hz, trajectory | Registration. Page refuses automated access. Licence not found | No |
| 8 | **Songdo Traffic** | 10 drones | 20 junctions, not continuous | 4 days, 10 sessions/day, 2022 | Near-all in view is expected, but no detection rate reported. About 700,000 trajectories (PROVIDER CLAIM) | 29.97 Hz, trajectory, lanes | Zenodo, CC BY 4.0, 41 GB | 1 junction-day |
| 9 | **pNEUMA** | Drone swarm | Athens, 1.3 km² per the SWIFTraj table | Morning sessions | About 0.5 M vehicles (PROVIDER CLAIM), share not measured | Trajectory | Zenodo CC BY; EPFL footer conflicts (report 05), 15.76 GB | No |
| 10 | **LADDMS** | 8 lidar sites, 5 signalised | North Nashville corridor | 120 days, continuous | Not stated. One example site-day has 48,695 tracks of all road users (PROVIDER CLAIM) | 10 Hz, IDs per site, not stitched | Zenodo CC BY 4.0. Full data link not confirmed | No |
| 11 | **SWIFTraj** | 16 drones | Nanjing, 4.5 km freeway, about 2 km² urban | Morning peaks, 12–18 min flights | Not stated | Trajectory | Site has "Request Access". Licence not found | No |
| 12 | **Austin Bluetooth** | Device reads at roadside sensors | City sensors | 2016-01-01 to 2021-12-21, 412,529,530 reads (MEASURED via API) | Unknown, only devices that broadcast | Per device at sensors | Open API, City of Austin terms | API samples only |
| 13 | **Hornsgatan** | 4 ANPR/radar sensors | One street, Ringvägen–Ansgariegatan | 1 Aug 2022–31 Jul 2024 | Not stated | Passages with type, direction, time, owner's postcode | **No download link.** Must be requested | No |
| 14 | **DRIFT** | Drones | 9 junctions, Daejeon | Not checked | 81,699 trajectories (PROVIDER CLAIM) | Trajectory | GitHub, licence not checked | No |
| 15 | **Pully** | 2 drones | Part of a Swiss town | Several sessions | Not stated | 30 Hz, trajectory | Zenodo, CC BY 4.0, about 0.77 GB | 1 file: 209 tracks, 16 min |
| 16 | **TUMDOT-MUC** | 12 drones | 700 m core, Munich | 2 afternoons | UNVERIFIED, from a search result | 0.08 s | Free with credit | No |
| 17 | **Zen Traffic Data** | Roadside cameras | About 2 km, Osaka | 1-hour sets | UNVERIFIED, from papers citing it | 0.1 s | **Site down today**, new users must email | No |

None of these covers Sweden except Hornsgatan.

## Top 3 recommendations

### 1. Cambridge: test routes and travel times on real vehicle journeys

- **What I measured for 13 June 2017:**
  - 178,662 chains, 511,922 camera-to-camera hops, 840,010 reads at 91 sites.
  - 87% of chains are cars. Peaks are 16,178 chains at 07:00 and 16,667 at 17:00.
  - Median hop 3.4 min, median chain 10.7 min, 10,681 distinct first/last camera pairs.
- **Limits:**
  - No vehicle ID, so one car's separate journeys can't be linked.
  - Chains stop after 2 hours or when a car passes outbound at an external camera.
  - Paths between cameras are unknown.
  - The notes list camera failures, for example site 17 southbound for the entire survey and site 22 until 12:00.
  - The reports are marked preliminary and the licence is unclear.
- **Serves:** demand and routes at camera level, plus travel times by time of day. Not maps or signals.
- **Test in `cars`:** build Cambridge from OSM, fit demand on some days, then compare route shares between camera pairs and hop times on a held-out day. Travel times are only independent if they aren't used in the fit.
- **Next step:** on the homelab, fetch the other 7 days and run `scripts-01/cambridge_chains.py` on each, then turn the `Location Plan` sheet into camera coordinates. Estimated 2–3 days of work.

### 2. Xuancheng: test a whole city with real signals

- **Plate reads (MEASURED):** 141,304 records. One ID has 4,762 of them and looks like a placeholder for unread plates (my inference), so I removed it, leaving 136,542 records and 25,197 vehicles. Only 58.9% of consecutive reads are on adjacent links, so routes still have gaps. Reads touch 549 of 1,156 links.
- **Signal file test (MEASURED):**
  - The file has 61,423 intervals across 1,790 movements at 161 junctions, but the paper doesn't say where it came from or define it. Treating intervals as green is my inference.
  - **74.0% of 69,718 reads fall inside their movement's interval, against 35.9% expected by chance.**
  - 17.1% of intervals on busy movements have no reads, so the file isn't simply derived from the reads.
  - Cycles are very regular (median variation 0.7%, common values 120, 133 and 60 s). That looks like controller plans, but it is not proof.
  - 26% of reads fall outside, and that is unexplained.
- **Month of virtual loops (MODELLED):** 5,022,131 rows, 794 roads, 29 days (5 Sep missing), about 1.3–1.9 M passages/day. Network speed only falls from about 8.4 to 6.7 m/s, so this city has mild congestion in this data. Compared with plate reads on 390 links for 07:00–08:00, the ratio has median 0.89 and ranges from 0.26 to 1.33 (p10–p90), so don't treat these loops as truth.
- **Validation is thin (PROVIDER CLAIM):** manual counts at two junctions (r = 0.748, RMSE 4.3 veh/min) and correlations of about 0.74–0.75 with Amap and Baidu. The paper says lane-level information "lacks confidence", and 50.3% of links have `nlane=0` in the segment file (MEASURED).
- **Serves:** demand, routes, signals and part of maps, in one consistent hour.
- **Test in `cars`:** convert `road_network_stream_level.csv` and `signal.csv` into a network, start each vehicle from its first read, run 07:00–08:00, and compare link times and turn counts with reads held out.
- **Next step:** write the converter, about 1–2 days. It is a model test, not a replacement for Stockholm: one hour, in a less congested city.

### 3. Hornsgatan: ask Stockholm for the data

It is the only Stockholm source I found with plate-derived fields, and the owner's postcode could show where traffic on that street comes from. It covers one street, and postcode of the registered owner is not the same as trip origin. It may also count as personal data, so ask only for aggregated data. Draft below.

**Runner-up:** Songdo for junction behaviour. Position error is mostly under 1 m and speed error about ±1 km/h against an RTK vehicle (PROVIDER CLAIM). The one junction-day I checked has 40–260 vehicles per session (MEASURED). It has lanes but no signal timing that I found.

## What only Erik can do

1. **Send the two drafts below**, if he wants them. Nothing has been sent.
2. **Decide on Xuancheng's tool.** Reaching the full month means running a downloaded launcher and `measurement.jar`, which the brief forbids. It should only run isolated on the homelab if Erik approves. I did not try to break the encryption. Whether its 10 s output covers all vehicles or only commercial ones is unknown, and that decides how much it's worth.
3. **Register for I-24 MOTION** if he wants that data. It needs a verified account.

### Draft: Hornsgatan data

To: the contact in the catalogue record (Anders Broberg, `[e-mail removed]`). Erik should check he's the right person.

> Hej Anders,
>
> Jag såg datamängden "SLK Trafikdata ANPR/radar - Hornsgatan" i Stockholms dataportal. Jag bygger en trafiksimulator över Stockholm och vill jämföra den med riktiga trafikflöden.
>
> Går det att få ut datan, eller en del av den? Det räcker med passager per tid, riktning och fordonstyp, och postnummer på områdesnivå. Jag behöver inga registreringsnummer.
>
> Vet du också vilken licens som gäller?
>
> Tack!
> Erik

### Draft: Cambridge licence and counts

To: `contactus@greatercambridge.org.uk` (listed on the dataset record).

> Hi,
>
> I'm using your Greater Cambridge ANPR trip chain and OD reports from June 2017 to test a traffic simulator. Which licence are they under? Also, were final versions ever released, and are the manual counts from the survey available?
>
> Thanks!
> Erik

## Fetch later (homelab, when there's room)

Run through `heavy -- <cmd>`. Sizes are from the repository listings unless marked as estimates.

| Priority | What | Size | Where | Why |
|---|---|---|---|---|
| 1 | Cambridge trip chains, other 7 days | about 90 MB (estimate) | URLs in the data.gov.uk record | Full week |
| 2 | Cambridge OD reports, other 7 days | about 400 MB (estimate), much larger unpacked | Same record | Parse only on the homelab: reading these sheets in full took over 9 minutes here |
| 3 | Xuancheng `fcd.csv` | 3.42 GB | `https://ndownloader.figshare.com/files/33524447` | Have only the first 2 MB. MODELLED |
| 4 | Songdo trajectories, other 79 junction-days | about 12 GB (estimate) | Zenodo 17924857 | Skip `sample_videos.zip` (26.8 GB). `orthophotos.zip` is 1.8 GB if needed |
| 5 | Pully, remaining files | about 0.77 GB | Zenodo 12568873 | Small drone check |
| 6 | LADDMS one-day sample | 3.8 GB | Zenodo 16415608 | Lidar format and flow check |
| 7 | pNEUMA | 15.76 GB | Zenodo 10491409 | Only if not already held from report 05 |
| 8 | Xuancheng `fullTraj.zip` | 7.2 GB | `https://ndownloader.figshare.com/files/33524966` | Encrypted. Useless unless Erik approves the tool |
| 9 | Taiwan M06A | Unknown | `tisvcloud.freeway.gov.tw/history/TDCS/M06A/` | Check the other agent's report first. Try from the homelab |
| 10 | Austin, a few single days | Query by date, not the whole set | API `qnpj-zrb9` | Only after testing whether IDs persist |

## Unfinished

- **Cambridge share of traffic:** not measured. It needs the manual counts or an independent count source.
- **Citation search:** Yu 2023 and Wang 2023 citers were checked by title only. pNEUMA's list was only partly read, and I-24's wasn't run. Unopened titles worth reading:
  - "Measuring the recoverability of all individual vehicle paths with incomplete and imperfect roadside vehicle identification sensors" (2026)
  - "Vehicle trajectory reconstruction with sparse ALPR data" (2025)
  - VisionTraj (2025)
  - VarieD (2026)
  - SPT (2025)
  - the Glasgow urban traffic control dataset (2025)
- **Not opened or not checked:** Leeds ANPR project page, London congestion charge camera counts, Dublin journey-time files, V2X-Seq (search only), DRIFT's licence, the Li 2023 data link, and the Stockholm sensor API PDFs (downloaded, not read).
- **Austin IDs:** not established whether they persist across sensors or days. One sampled address hit one sensor 12 times in 18 minutes, so stationary devices need filtering.

## Dead ends

- **St Eriksgatan/Fleminggatan sensor API (Stockholm, CC BY 4.0, Oct 2020–Apr 2021):** the catalogue's example URL and a second dated query both return 404. Data collection ended 30 April 2021.
- **Transportstyrelsen congestion tax page, 2025:** monthly totals only, about 8 M passages in a typical month, no per-station data. Report 01's request for station data still stands.
- **Hangzhou and Jinan signal-control benchmarks:** 1 to 16 junctions, 1 hour, simplified. Hangzhou 1x1 uses fixed turning ratios. Not city data.
- **Plate-read searches for Hangzhou:** one paper used private camera data at six junctions. No open city-wide set found. Repository searches mostly return plate images for recognition training.
- **Baltimore spy plane:** about 90% of the city, 12 h/day for six months, ruled unconstitutional, with most data to be destroyed. No release found. Don't pursue.
- **WPAFB 2009 aerial imagery:** access not verified, and small labelled regions only. VETRA is also out: search results give CC BY-NC-ND and it's built for tracker testing.
- **Alpujarra, Spain:** 4 plate cameras in tourist villages. Open, but too small.
- **`wiki.cam.ac.uk` "Every Car in Cambridge":** the host doesn't resolve from here. Its snippet (about 90 cameras, about 4 M movements) is UNVERIFIED and appears to describe this same survey.
- **OpenAlex cursor paging** returned 401. Page-number paging worked (`scripts-01/citers2.py`).

## Corrections to earlier reports

- **Report 06** says no city we use has free trip data. That still holds for our cities, but open per-journey plate chains and open whole-city plate reads do exist elsewhere.
- **Report 01** doesn't list Cambridge, Xuancheng, Padua or Songdo.
- **Report 02** mentions Stockholm travel-time cameras. A search snippet says Trafik Stockholm's live travel times use Bluetooth/Wi-Fi (BlipTrack). The article refused access, so this is UNVERIFIED and worth checking, not a correction yet.

## New directions

- **Temporary plate surveys commissioned by councils.** Cambridge was a one-off consultant survey published in full. UK councils may have published more, so search their portals for "ANPR", "trip chain" and "OD report".
- **Searching open data portals directly** found three leads that web search missed, including Cambridge and Hornsgatan. Other agents should try it (`scripts-01/repo_sweep.py`).
- **Long fixed lidar deployments** such as LADDMS give months of continuous junction data, which drone studies can't.

## Files

- **Data:** `/home/erikf/projects/personal/cars-data/datasets/`, in `xuancheng-holographic`, `cambridge-anpr-2017`, `padua-avi`, `songdo-traffic`, `pully-drones`, `stockholm-sankt-eriks`.
- **Scripts:** `research/truth/data-hunt/scripts-01/`.
- **Load on the PC:** one of my parsers ran for over 9 minutes before I stopped it, and I downloaded about 1 GB in total. It added to the load. Nothing of mine should be running now.
