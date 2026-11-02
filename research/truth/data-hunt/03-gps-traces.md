# 03: Open and request-only GPS traces from real cars

**Status: stopped early, unfinished.** The PC was overloaded (load average 92, disk 87% busy, memory thrashing), and I was told to stop all downloads and processing. My jobs are stopped. **I did not compute real route against shortest path, so this report has no new route-choice number.** The matcher is written but untested. Section 6 lists what a homelab follow-up needs.

## The answer

Good open GPS data for private cars does exist, but no source I opened covers "all the cars in one day". GPS sources here follow a small, self-selected or professional part of traffic. Their value is showing how drivers pick routes, not how many cars drive.

- **Open now: Vehicle Energy Dataset (VED), Ann Arbor.** 383 private cars for a year, GPS every 3 s, Apache 2.0. I have the files. It has one serious limit: the start and end of every trip are deleted, and everything outside a rectangle around the city is deleted. It can test the middle of a route inside the city, but it can't give real origins and destinations or trips that leave the city.
- **Best fit for Sweden: Swedish Car Movement Data (Chalmers).** 714 private cars picked by stratified random selection from the Swedish vehicle register, 2.5 Hz, 2010 to 2012. Cars are registered in Västra Götaland and Halland, so this is the Gothenburg side, not Stockholm. The authors say it is free for research, but the access site I tried did not answer, so access is not confirmed.
- **Stockholm itself: OpenStreetMap public traces.** One central tile of about 63 km² holds about 3.5 to 3.8 million points, all years and all modes. That is on the order of 1,000 hours of movement at 1 Hz, even before removing walkers and cyclists. It can test a sample of routes, but it can't describe traffic.

Until the follow-up runs, the best route-choice measurement remains the one already in `06-demand-and-route-choice.md`: Zhu & Levinson, Minneapolis–St. Paul, 2008-era. It found 34% of trips and 13.5% of commutes on the modelled shortest-time path. I did not reopen that paper.

## Ranked sources

The ranking is my judgement of usefulness for route choice. Grades: MEASURED (I opened the data and measured it), PROVIDER CLAIM (read on the source's own page or paper), UNVERIFIED (search snippet, memory or an older report only). I found no accuracy validation for any of these unless stated, and I did not look for it in depth.

| # | Source | What, where, when | Share of traffic | Sampling, level | Access, licence | Sweden | Downloaded | Grade |
|---|---|---|---|---|---|---|---|---|
| 1 | [VED](https://github.com/gsoh/VED) ([paper](https://arxiv.org/abs/1905.02081)) | 383 private cars with OBD-II loggers, Ann Arbor, 1 Nov 2017 to 9 Nov 2018, 373,964 miles | Not known. About 1,600 km per day across the fleet (my arithmetic). Recruited volunteers, with extra effort to recruit hybrids and EVs | GPS 3 s, speed 1 s. Route level, middle of trip only | Open, Apache 2.0 | No | Yes, 176 MB, 3.0 GB unpacked | PROVIDER CLAIM. File format seen |
| 2 | [Swedish Car Movement Data](https://research.chalmers.se/publication/187380) ([paper](https://publications.lib.chalmers.se/records/fulltext/local_165497.pdf)) | 714 private cars, 528 with over 30 days of logs. Registered in Västra Götaland or Halland. Jun 2010 to Sep 2012 | Not measured. Stratified random sample from the vehicle register, which is the only sample here designed to represent private cars | 2.5 Hz. Route level if raw positions are released | "Freely available" for research, tiered by privacy. Commercial use and licence unknown. See dead ends | **Yes** | No | PROVIDER CLAIM |
| 3 | [OSM public traces](https://wiki.openstreetmap.org/wiki/API_v0.6) | Volunteer GPS uploads worldwide. The first page I fetched in Stockholm was from Oct 2026 | Very small and unknown. Mappers, all modes mixed | Varies. First track was 1 Hz. Route level only for traces with timestamps | Open API, 5,000 points per page, bbox up to 0.25°. Licence of the traces not verified | **Yes** | 17 pages, 85,000 points, Stockholm | MEASURED for density, not for car share |
| 4 | [Porto taxis](https://archive.ics.uci.edu/dataset/339/taxi+service+trajectory+prediction+challenge+ecml+pkdd+2015) | 442 taxis, 1,710,671 trips. Holiday references are 2013 to 2014 | Taxis only, share unknown | 15 s. Route level, real trip ends as far as stated | Open, CC BY 4.0 | No | Yes, 534 MB zip, not opened | PROVIDER CLAIM |
| 5 | Transportation Secure Data Center (NREL), household GPS surveys, e.g. Atlanta 2011 | US household travel surveys with vehicle GPS. Atlanta: 1,277 reported in the GPS part | Weighted survey samples, so bias can be corrected. Not verified | Second-by-second reported. Public tier removes coordinates. Spatial data only inside a secure desktop | Free application. Outputs must be aggregated. www.nrel.gov did not resolve from here | No | No | UNVERIFIED, snippets only |
| 6 | [Grab-Posisi](https://engineering.grab.com/grab-posisi) | 84K trajectories, Singapore and Jakarta, April 2019, cars and motorcycles | Ride-hail drivers only, share unknown | 1 s, route level. Real start and end removed | Email request. No commercial use | No | No | PROVIDER CLAIM |
| 7 | [Shenzhen private cars, Hunan University](https://github.com/HunanUniversityZhuXiao/PrivateCarTrajectoryData) | Private cars, reportedly Jan 2016. The repo itself states no car count, period or city | Unknown | Reportedly about 1 minute, which makes route recovery weak | Signed agreement by email, about 14 working days. Nonprofit scientific use. I did not read the licence PDF | No | No | Access: PROVIDER CLAIM. Details: UNVERIFIED |
| 8 | PriTraj | Reportedly 60,000 cars, 10 million trajectories, 12 months, over 20 Chinese cities, GPS and OBD | Unknown | Unknown | Called public in a [2025 survey](https://dl.acm.org/doi/10.1145/3715902), but I found no paper or download | No | No | UNVERIFIED. The survey page returned 403 |
| 9 | [T-Drive](https://www.microsoft.com/en-us/research/publication/t-drive-trajectory-data-sample/) | 10,357 taxis, Beijing as I recall (page did not state it), one week, about 15 million points | Taxis only | Interval not stated on the page | OneDrive download. Licence not stated, citation asked | No | No | PROVIDER CLAIM |
| 10 | [GeoLife](https://www.microsoft.com/en-us/download/details.aspx?id=52367) | 182 users, 17,621 trajectories, 2007 to 2012, all modes, 298.7 MB | Tiny, volunteers | 91% dense | Open download. Licence not stated | No | No | PROVIDER CLAIM. Matches report 06 |
| 11 | DiDi GAIA, Chengdu and Xi'an | Ride-hail | Unknown | Not checked | [Site](https://outreach.didichuxing.com/) has a datasets link. Availability not confirmed | No | No | UNVERIFIED |
| 12 | [Chicago ride-hail trips](https://data.cityofchicago.org/api/views/6dvr-xwnh.json) | All reported ride-hail trips from 2025, with earlier years linked | All ride-hail reported to the city, not all cars | Tract centroids, times rounded to 15 min. **No routes** | Open portal | No | No | PROVIDER CLAIM |
| 13 | [NYC TLC](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) | Taxi and for-hire trips | Taxi and for-hire only | Taxi zones. The page mentions no routes | Open | No | No | PROVIDER CLAIM |
| 14 | [Waymo Open Motion](https://waymo.com/open/about/) | 103,354 segments of 20 s at 10 Hz, 6 US cities | Cars seen around an AV. Clips too short for route choice | 10 Hz, clips only | Non-commercial, research only | No | No | PROVIDER CLAIM |
| 15 | Argoverse 2 Motion, nuPlan | Argoverse: 250,000 clips of 11 s (from report 05). nuPlan page came back empty | Same as Waymo | Clips | Not checked here | No | No | UNVERIFIED |
| 16 | Strava-like sources, MoveBank | As far as I recall, Strava Metro is cyclists and pedestrians and MoveBank is animal tracking. Neither looks useful for cars | Not relevant | Not relevant | Not opened | Unknown | No | UNVERIFIED |

### What each one serves

| Sources | Need served | Test it would enable in `cars` | Work |
|---|---|---|---|
| VED, OSM traces, Porto, Grab, T-Drive | Routes. VED and Grab also give link speeds (congestion, biased sample) | Compare route overlap and time loss on `cars` routes with real ones. Check whether real drivers spread over routes as much as assignment does | Matcher (written, untested) plus a comparison script (not written) |
| Swedish Car Movement Data | Routes, trip lengths and daily patterns in Sweden. Possibly demand shape, not a full OD matrix | Same route test on Swedish roads, plus trip-length and departure-time distributions | Depends on what they release |
| TSDC | Routes and trip patterns from a weighted sample | Same test, run inside their secure desktop | Application, then porting to their environment |
| Chicago, NYC | Demand for ride-hail only | Time-of-day shape of for-hire demand, not usable for routes | Low |
| Waymo, Argoverse, nuPlan | Driver behaviour around an AV, not routes | Car-following and gap checks on short clips | Already weighed in report 05 |

No source here serves maps or signals.

## What I actually measured

- **OSM density, central Stockholm: about 3.52 to 3.84 million points** in tile lon 18.0–18.1, lat 59.3–59.4 (about 63 km²).
  - Method: bisecting page numbers. Page 704 was full and page 768 was not. Page 736 returned a 503, so I stopped there with that range.
  - It counts all years and all modes, and I did not filter for cars.
  - "1,000 hours" assumes every point is 1 s of movement, which is a rough scale and not a measurement.
- **OSM sample:** 17 pages from bbox 17.95, 59.27, 18.20, 59.40, 85,000 points. The first page had 5,000 points in 6 tracks, all timestamped, and the first track ran at 1 Hz. The rest is not analysed.
- **OSM API speed:** deep pages and wide boxes often return 503. My run reached page 17 in about 20 minutes under heavy local load, then gave up after repeated failures.
- **VED format:** rows repeat the last GPS position many times. In the first files, 9,046,708 rows held 1,744,919 distinct positions, about 5 to 1. That point file stopped partway through, so don't use it.
- **Road networks fetched:** Ann Arbor, Porto and Stockholm from Overpass. Ann Arbor gives 29,288 directed links after I fixed a bug where ways were listed twice.

## Top 3 recommendations

1. **Run route against shortest on VED, with Porto as the taxi comparison, on the homelab.**
   - Next step: section 6. Test the matcher on synthetic traces first.
   - Output: share of trips on the shortest and fastest route, route overlap, time loss, and how many distinct routes each origin-destination pair uses. Then compare with Zhu & Levinson.
   - Fastest route should use speeds learned from half the cars and tested on the other half, so the speeds don't come from the same trips.
2. **Erik asks Chalmers for the Swedish Car Movement Data.** It is the only representative sample of Swedish private cars I found. The key question is whether raw positions can be used for map matching. Draft below. Reports `04-gps-holders.md` and `05-sweden-kth.md` also mention this project, so check them first to avoid asking twice.
3. **After the matcher is proven, filter OSM traces in Stockholm to car-like trips.**
   - Next step: fetch small tiles slowly, from a time when the API is healthy.
   - Keep only traces with timestamps, then filter on speed. Measure how much comes from a few uploaders.
   - Report the car-trip count first and treat it as a sample only. If it's only a few hundred trips, say so and stop there.

## What only Erik can do

These are drafts for Erik to send himself. Nothing has been sent. Fill in the brackets, because I don't know what he wants to state about his affiliation or purpose.

**Chalmers.** The report names Sten Karlsson as project lead. I did not verify a current email address.

> Hi Sten,
>
> I'm building a traffic simulator and want to check it against how real cars drive in Sweden. I read about the Swedish car movement data project and saw that the data is available for research.
>
> Is it still possible to get access? I'd mostly need the GPS positions for the trips, so I can match them to roads and look at which routes people take. If that part is too sensitive, could I run the analysis on your side, or get matched routes without trip ends?
>
> I'm [affiliation], and this is for [purpose].
>
> Thanks,
> Erik

**Grab-Posisi**, to grab.posisi@grabtaxi.com. Their page asks for name, contact details, institution and planned use, and it rules out commercial use.

> Hi,
>
> I'd like to request access to Grab-Posisi. I'm Erik Frankling, [affiliation], [contact details]. I want to compare the routes drivers take with shortest and fastest routes, as a check for a traffic simulator. It's for [purpose], not commercial use.
>
> Thanks,
> Erik

**Hunan University:** Erik would have to read and sign [the agreement](https://github.com/HunanUniversityZhuXiao/PrivateCarTrajectoryData/blob/master/Trajectory-data-license-v3.pdf) himself and email a scan to [e-mail removed]. It is low priority: the sampling is reportedly about one minute and the terms cover nonprofit scientific use only.

**TSDC:** this needs Erik's own online application. Only worth it if Chalmers says no.

## Dead ends

- **OSRM from nixpkgs:** not in the cache, so it has to compile on the builder. I stopped it and wrote my own matcher. A compiled OSRM would be a useful cross-check if the builder has room.
- **`www.chalmers.se/brd`:** the project homepage named in the report returns 404. `database.testsitesweden.com`, the access site it cites, gave no response in one 25 s check under load. It may just be old.
- **`www.nrel.gov`:** did not resolve from this machine. Mirrors appeared in search results but I did not open them.
- **Open European private-car GPS on Zenodo:** one extended search found nothing usable. [Attika / Track & Know](https://zenodo.org/records/4449665) is reported as not publicly accessible, and [Czech floating car data](https://zenodo.org/records/2250119) and [CODECO](https://zenodo.org/records/19006361) are reported as simulated. These come from search summaries, not from opening the records.
- **OSM planet GPX dump:** [7 GB compressed, 55 GB raw, last from 2013](https://wiki.openstreetmap.org/wiki/Planet.gpx), raw coordinates with no track files. It works for a density map, not routes.
- **Trip tables:** Chicago and NYC have no routes, so they can't answer route-choice questions.

## 6. Unfinished, and what the follow-up needs

**Not done:**
- Route against shortest path, on any dataset.
- Matcher validation. The synthetic test did not finish within 200 s at load 66, and the profile run printed nothing before its timeout.
- The comparison script, which is not written.
- Car filtering of OSM traces, and any denominators for share of traffic.

**Code in `scripts/datahunt/` (all mine except the others noted below):**
- `routenet.py`: road graph, matcher, routing with turn costs.
- `test_match.py`: synthetic matcher test. Its `sys.path` is hardcoded to this PC.
- `ved_prepare.py`: VED to a compact point file.
- `overpass_roads.py`, `osm_trace_fetch.py`, `osm_trace_density.py`. The density script counts a failed page as full, so check its stderr.
- Other agents' scripts are also in that folder, so leave them alone.

**Known issues to check in `routenet.py`:**
- Service roads are left out, so traces through car parks will break into pieces.
- A trace that loops back onto the same link is treated as staying on that link.
- Speed defaults, 15 s per signal and turn penalties are my own assumptions.
- Roads are today's OSM, compared with trips from 2013 to 2018.
- VED's clock and time zone are unchecked. Check that trips per hour show a normal peak before using time of day.

**Already on disk, no need to fetch again**, under `/home/erikf/projects/personal/cars-data/datasets/`:

| Path | Size | State |
|---|---|---|
| `ved/VED_DynamicData_Part1.7z`, `Part2.7z` | 176 MB | Complete |
| `ved/extracted/` | 3.0 GB | 54 weekly CSVs |
| `ved/points.csv.gz` | 26 MB | **Truncated, delete and rebuild** |
| `porto/porto.zip` | 534 MB | Size matches UCI's listing, not opened |
| `ved/roads/annarbor.json` | 27 MB | Complete |
| `porto/roads/porto.json` | 46 MB | Complete |
| `osm-traces-stockholm/roads/stockholm.json` | 43 MB | Complete |
| `osm-traces-stockholm/pages/` | 8.6 MB | 17 pages |

**Still to fetch:**

| What | Size | Note |
|---|---|---|
| VED static files (`.xlsx`) | About 31 KB | Optional, vehicle types |
| More OSM pages, central tile | About 370 to 400 MB for all of it, at about 525 KB per page | Slow and failure-prone. Use small tiles at 1 request per second or slower. Stop when enough car trips exist. It's a shared public API |
| GeoLife | 299 MB | Optional, only if more private-car routes are needed |
| Grab-Posisi | About 2 GB | Only after approval |

**How to run it on the homelab (not tested):**
1. Wait until the machine has room. `heavy` syncs files from the PC, so a 3 GB sync adds disk load.
2. Make a new folder holding the scripts in one subfolder and only the VED archives, Porto zip and road JSONs in another.
3. From that folder, run `heavy --big -- <cmd>`. The folder is outside git, so `heavy` syncs it as it is and enters no dev shell. The command has to bring Python with numpy and scipy itself, e.g. through `nix shell`.
4. Run Python with `-I`, and fix the hardcoded path in `test_match.py`.
5. Order: synthetic test (3 s with 6 m noise, then 15 s with 10 m noise), rebuild VED points, a few hundred trips, then all trips, then Porto.
6. `heavy pull` the results back. Nothing returns on its own.

**Share of traffic:** this column stays mostly "unknown", because the denominators need traffic counts for each city. For VED, compare fleet passes on a road with official counts on that road, once the follow-up has matched routes.

## New directions I couldn't cover

- **Dashcam GPS tracks:** Mapillary and KartaView sequences in Stockholm could be another open source of car routes. I did not check this, and the same mapper bias would apply.
- **Stockholm congestion-charge passages:** real vehicle passes at the cordon could give counts and timing. Not checked, and another report may cover it.
- **Older Stockholm taxi GPS:** I recall KTH work using it, not verified. `05-sweden-kth.md` may cover this.
- **Wejo through CDRC (UK):** reported as 50,000 connected cars for a month, by application. From a search summary only.
- **Italian insurance telematics ("PriIta"):** reported as 779,000 cars, listed as non-public or partly public. Survey summary only.
