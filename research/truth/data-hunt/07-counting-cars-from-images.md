# 07: Counting real cars from images

**Status: partial.** I was told to stop mid-run because Erik's PC was overloaded (load 92, memory thrashing). The core test ran. The unfinished parts are listed under [Unfinished](#unfinished), with what to run and how big it is. Nothing of mine is still running.

## The answer

**Yes, this works, but as a test of density and queue shape at one moment, not as a source of flows or peak congestion.**

- **Free Swedish imagery is much better than earlier reports assumed.** Lantmäteriet has 0.16 m colour orthophotos of Stockholm, free under CC BY 4.0, and its public catalogue gives the capture time of every photo to the second. Downloading the full files needs a free Geotorget login, which only Erik can create. Report 07's maps work only looked at 0.5–0.6 m imagery.
- **A small open detector counts cars on the CPU.** On 6 central Stockholm roads (77 hand-counted vehicles) it found 91% with 89% precision at a 0.5 threshold. Errors on a single road were large, from −19% to +50%, and they cancel in the total. This is one trial, with the threshold picked on the same data and the labels made by me.
- **The images agree with measured counts on scale, but this is not validation yet.** Seven roads held 91 vehicles, against 124.5 expected from weekday counts (ratio 0.73, range 0.36–1.10). The only image I could get is from a **Saturday** morning and the counts are weekday averages, so that gap can't be interpreted. The Tuesday 9 May 2023 flight would fix this, but it needs the login.
- **No flight covers the morning peak.** There's about one flight every two years, in daylight. Images can test off-peak density and queues at signals, but they can't test rush-hour breakdown.
- **The surprise is the public road cameras.** The Trafik Stockholm page lists 327 live cameras. Every image downloaded with no key and states its photo time, and the ones I logged refresh about once a minute. That is the only source here that could show queues through the rush hour. I only tested it at night, and no archive turned up, so data starts the day logging starts.
- **Sentinel-2 won't help in the city.** Published work says the colour-offset effect needs about 50 km/h or more and gives relative counts, not absolute ones. My own test did not finish.

Grades used: MEASURED (I ran or read it directly), PROVIDER CLAIM, MODELLED, UNVERIFIED.

## What I tested

**Imagery.** Nine 2048×2048 px crops at 0.16 m (328 m square), about 5.4 MB in total, from Lantmäteriet's public Min karta viewing service. Files are in `/home/erikf/projects/personal/cars-data/datasets/imagery-stockholm/` (176 MB with everything). Image source: © Lantmäteriet, CC BY 4.0, processed.

**Detector.** [LibreRFDETRn-obb](https://huggingface.co/LibreYOLO/LibreRFDETRn-obb), ONNX, 108 MB, CC BY 4.0. Its authors call it "ultra-experimental", and it was trained on 932 drone images, not on orthophotos. I chose it because ONNX runs without unpickling downloaded weights. It took about 0.7 s per 384 px window on the CPU (one probe), and about a minute per crop with the machine under load.

**Hand counts.** I labelled vehicles by eye on each road's carriageway, with a road corridor drawn by hand. Only the corridor is scored; off the road the detector fires on roofs, boats and construction sites, so it can't be used without a road mask.

### Detector against hand counts (MEASURED, 6 roads)

| Threshold | Found | False | Missed | Recall | Precision | Count ÷ hand count |
|---|---:|---:|---:|---:|---:|---:|
| 0.25 | 74 | 28 | 3 | 0.961 | 0.725 | 1.325 |
| 0.30 | 73 | 21 | 4 | 0.948 | 0.777 | 1.221 |
| 0.40 | 71 | 15 | 6 | 0.922 | 0.826 | 1.117 |
| **0.50** | **70** | **9** | **7** | **0.909** | **0.886** | **1.026** |
| 0.60 | 63 | 5 | 14 | 0.818 | 0.926 | 0.883 |

### Each road against the measured count

Expected vehicles = weekday flow ÷ speed × road length, for the hour of the photo. Weekday flows are from `od_gis:Arstrafik` 2025. Hand-count noise is roughly ±√N.

| Road | Length | Photo (Sat 31 May 2025) | Weekday flow, veh/h (days measured) | Speed, km/h | Expected | Hand | Ratio | Detector at 0.5 |
|---|---:|---|---:|---|---:|---:|---:|---:|
| Essingeleden, Kristineberg | 329 m | 09:39 | 6,901 (231) | 70, assumed limit | 32.4 | 26 | 0.80 | 21 |
| Johanneshovsbron | 370 m | 10:00 | 2,929 (216) | 60, assumed | 18.1 | 8 | 0.44 | 12 |
| Klarastrandsleden | 335 m | 10:10 | 2,390 (202) | 47, measured 2024 at another site record | 17.1 | 14 | 0.82 | 15 |
| Drottningholmsvägen | 341 m | 09:39 | 3,144 (5) | 65, measured | 16.5 | 6 | 0.36 | 6 |
| Stadsgårdsleden | 346 m | 10:00 | 1,222 (5) | 35, measured | 12.1 | 10 | 0.83 | 14 |
| Hornsgatan | 342 m | 10:10 | 1,597 (5) | 35, measured | 15.6 | 13 | 0.83 | 11 |
| Sveavägen | 240 m | 10:00 | 1,804 (6) | 34, measured | 12.7 | 14 | 1.10 | not scored |
| **Total** | | | | | **124.5** | **91** | **0.73** | |

### How much to trust this

- **Labels:** one labeller (me), with no independent check. I saw the detector's boxes for Essingeleden and Hornsgatan before finishing those labels, so those two aren't blind.
- **Threshold:** chosen on the same 6 roads it is scored on. There is no held-out test, so 91%/89% is probably optimistic.
- **The 1.026 total:** partly luck, because road errors cancel: −19%, +50%, +7%, 0%, +40%, −15%.
- **Saturday versus weekday:** I found no Saturday count to compare with, so the 0.73 mixes real weekend traffic with any counting error.
- **Image date:** I assume the viewing service shows the 2025 flight, since it's the newest. Shadows fit a morning sun, but that is not proof, and the service's feature-info lookup is disabled. All photo times above depend on this (UNVERIFIED).
- **Published comparison:** the closest study, on Narvik, reached only 0.74 precision and 0.66 recall on aerial images. Expect my figures to fall on harder streets and a larger sample.

### What the images show that counters don't

- **Queue shape at signals (MEASURED by eye, two roads only):** on Hornsgatan 7 of 13 vehicles sit in the westernmost 40 m, at the junction. On Stadsgårdsleden 7 of 10 sit in the easternmost 83 m. A simulator can be tested on this directly.
- **Parked cars and side roads:** both are clearly visible. They help a parking census, but they also cause false counts, and a road mask has to exclude them.
- **Lane arrows and bus-lane paint are readable at 0.16 m** at the sites I looked at. This corrects report 07 for need 4: it said arrows weren't reliably readable, but that was at 0.5–0.6 m on Esri imagery.
- **Things that hide cars:** tall buildings lean over the road (Hötorget towers on Sveavägen), and trees and deep shadow cover parts of streets. Tunnels show nothing.

## How much imagery exists (MEASURED from the catalogue)

From Lantmäteriet's [STAC catalogue](https://api.lantmateriet.se/stac-bild/v1/): 735 collections nationally, 1,050 items over a Stockholm box (17.90–18.20°E, 59.25–59.42°N). Each photo's time is in a public `_flygbild.json` next to its tile, and that file and the thumbnail need no login.

| Flight | Resolution | Days | Local time | Size for 69 tiles |
|---|---:|---|---|---:|
| 2025-05-31 | 0.16 m | Sat | 08:40–10:55 | 46.9 GB |
| **2023-05-09** | **0.16 m** | **Tue, best one** | **09:46–12:21** | **48.0 GB** |
| 2021-04-08, 04-18 | 0.16 m | Thu, Sun | 09:53–15:52 | 51.3 GB |
| 2019-06-18, 07-20 | 0.16 m | Tue, Sat | 09:53–11:50 | 50.2 GB |
| 2017-07-06 | 0.25 m | Thu | 10:21–12:01 | 15.8 GB |
| 2015-07-02, 08-14 | 0.25 m | Thu, Fri | 09:45–16:09 | 16.0 GB |
| 2013-05-06, 05-20 | 0.25 m | Mon, Wed | 10:34–15:00 | 15.9 GB |
| 2011-06-04, 06-27 | 0.5 m | Sat, Mon | 09:31–10:48 | 6.0 GB (24 tiles) |

Older flights (2005–2009 colour, and black and white back to 1958) have placeholder dates or are too coarse. Sizes for the 2013–2019 and 2011 rows count one image type where the catalogue lists two. July and August flights will show holiday traffic.

**No flight starts before 08:40, and the only weekday flights start at 09:45 or later.** Only 2015 runs past 16:00, and I didn't check which tiles that covers.

## Ranked sources

| # | Source and what it measures | Area, period | Share of vehicles seen | Sampling | Accuracy known | Access and licence | Downloaded? | Needs served | Test in `cars` | Work |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Lantmäteriet orthophoto**, aerial photo | All Sweden; Stockholm 0.16 m in 2019–2025 | All vehicles in the open at that moment, minus hidden ones; measured only on my sample | One moment, about every 2 years | My trial above | Free, CC BY 4.0, Geotorget login, GDPR review and special terms. The tif returns 401 without login. Catalogue and photo times are open | Crops via the viewer; catalogue and one photo-time file directly | 3 (off-peak), 4 | Density by road class, queue shape at signals, lane use, at the photo's exact time | Days for a corridor; about 31 CPU-hours for all tiles (MODELLED) |
| 2 | **Trafik Stockholm / Trafikverket cameras**, live CCTV stills | 327 cameras around Stockholm, 63 in the central box; live | Whatever each view covers; not known | About 1 per minute, measured on a few cameras at night. Most frames 385×217 px | None for counting; daytime untested | No key needed for images (MEASURED). Licence not verified. Listing the cameras officially needs a Trafikverket key; the public page also lists them | One full round, 9.4 MB, plus a 6-minute log | 3, including peak | Queue length and congestion onset through the rush hour | Medium: a logger, plus camera geometry and a detector suited to low oblique views |
| 3 | **Stockholm stad orthophoto** | City only; 8 cm; 11, 14 and 17 May 2024 (Sat, Tue, Fri) | As row 1, sharper | One flight known | None | Spec found, city holds copyright, files and WMS exist. Price and terms unknown. No such layer in the open WMS I checked | Spec only | 3, 4 | As row 1, and lane paint | Needs a person, see the draft |
| 4 | **Sentinel-2**, colour offset of moving vehicles | World; free archive; 22 clear passes listed for tile 34VCL, Apr 2025–Oct 2026 | Large fast vehicles, undercounted | About 12:15–12:25 summer time, every few days when clear | [Fisser 2022](https://www.mdpi.com/2072-4292/14/7/1595): F1 0.74, r 0.82 at 26 German stations, low on 81% of dates (from a search summary of the abstract; MDPI blocked me). [Buthmann 2026](https://isprs-annals.copernicus.org/articles/XI-3-2026/43/2026/isprs-annals-XI-3-2026-43-2026.pdf): F1 0.53, needs about 50 km/h (read) | Open COGs, no key | One subset, 3.9 MB; analysis unfinished | 3, motorways only, trends | Relative midday motorway trend only | Small, but low value |
| 5 | **Esri World Imagery** | Stockholm: WorldView-2, 0.5 m, 2025-06-14 (a Saturday) | As row 1, coarser | One image | Stated position error 8.47 m | No key to view; `exportTilesAllowed` is false; terms not read | Metadata only | 4 weakly | None better than row 1 | Not worth it |
| 6 | **Pléiades Neo, Maxar/Vantor, Planet** | Any city, on order | 0.3–0.5 m; cars about 5×8 px at 0.5 m on Pléiades (search snippet) | Can be ordered, including for a peak hour | Not verified | Paid, prices not found | No | 3, including chosen hours | A commissioned peak snapshot | Needs a quote |
| 7 | **SkySat / Jilin-1 satellite video** | Short clips, on order | Vehicles at about 1 m | Up to 30 frames/s per one snippet | F-scores 0.98 and 0.87 from a search summary, UNVERIFIED | Paid | No | 3 | Speed and density in one clip | Unknown |
| 8 | **Mapillary** | Street-level, crowd-sourced | Random, not simultaneous | Irregular | None | Token needed, which I can't create; per-image licensing to be checked | No | 4 | Lane and sign checks, not traffic (my opinion) | Unknown |
| 9 | **Google and Bing aerial** | World | | | | Terms could not be read | No | | Don't use until the terms are read | |

### Published detector accuracy

- **DOTA benchmark** ([paper](https://arxiv.org/abs/2102.12219), read): Faster R-CNN OBB with RoI Transformer scores AP 77.45 on small vehicles. When tiny vehicles under 10 px are added, it drops to 52.05. So size in pixels matters most.
- **YOLO26 OBB** ([Ultralytics](https://docs.ultralytics.com/tasks/obb/), PROVIDER CLAIM): mAP50 78.9–81.7 across all DOTA classes, with no per-class figures.
- **Narvik, real road network** ([NR page](https://nr.no/publikasjon/1896663/), read): precision 0.74, recall 0.66, daily-traffic RMSE 2,279, bias −383. It found parked versus driving cars hard to separate, and that short urban links need several images.
- **Search summaries only, UNVERIFIED:** LR-CNN 92.54 AP on VEDAI, and a German-Dutch airborne test at 52.7 versus 59.3 vehicles/km against manual counts.

I found no paper that validates a simulator against city-wide orthophoto counts. Absence from a few searches isn't proof.

## Top 3 recommendations

1. **Rerun this on the Tuesday 9 May 2023 flight.** It's the one test that removes the Saturday problem. *Next step:* Erik makes a Geotorget account and accepts the terms; then run steps 5 and 6 below on about 5 tiles (roughly 3.5 GB). Compare with `cars` running that hour on density by road class and vehicles near stop lines.
2. **Log the public cameras through one weekday peak.** It's free and it's the only way here to see real queues over time. *Next step:* step 4 below, about 93 MB. Then look at the frames before building anything, because daytime usefulness is untested.
3. **Use the 0.16 m imagery for lane arrows and bus lanes in the maps work.** This gives value even if car counting doesn't pan out. *Next step:* rerun report 07's 20 sites with the viewer crops, then with full tiles after the login.

## What only Erik can do

- **Create a Geotorget account** and accept the orthophoto terms. The catalogue says use is legally assessed under GDPR, so approval may not be instant. I did not try this.
- **Decide about the viewing service.** I fetched 10 small crops from Min karta. Its page allows publishing images and screenshots with attribution and doesn't mention automated use, but [one OSM forum poster](https://community.openstreetmap.org/t/wms-server-lantmateriet/137129) says the service needs permission. I treated this as a small sample only; anything larger should go through the login.
- **Send the draft below** if the 8 cm image is wanted. It isn't essential.

### Draft for Stockholm stad (not sent)

The `erik-writing-style` skill couldn't be loaded because the Executor server wouldn't connect, so this needs Erik's own edit.

> **Till:** geodataservice@stockholm.se
> **Ämne:** Ortofoto 2024 för forskning om trafik
>
> Hej,
>
> Jag bygger en trafiksimulator för Stockholm och vill jämföra den med verkligheten genom att räkna bilar i flygbilder. Jag såg i er produktspecifikation att ortofotot från maj 2024 har 8 cm upplösning.
>
> Tre frågor:
> 1. Vad kostar det, och vilka villkor gäller, för en mindre del av innerstaden?
> 2. Finns fototiden för varje bild, inte bara datumet?
> 3. Får jag publicera utsnitt och resultat?
>
> Vänliga hälsningar,
> Erik Frankling

## Unfinished

| Not done | State |
|---|---|
| Sveavägen detector score | Detection finished after scoring ran; not scored |
| Accuracy at 0.32 m and 0.5 m (satellite-like) | Stopped before any result, so **I have no measured figure for how accuracy falls with resolution** |
| Sentinel-2 test | One subset downloaded; analysis timed out twice under load. No truck counts exist |
| Cameras in daylight | Only night frames. The one frame I viewed (Kungsängen, 03:52) showed no vehicles. Several cameras returned identical 15,670-byte frames, possibly a placeholder; not inspected |
| Second detector | A DOTA-trained YOLO was not tried, because its weights are pickled files that should be loaded with restrictions on the homelab |
| Trafikverket and Google terms | Pages couldn't be read. Camera licence is unverified |
| Company brain | Not searched, and no feedback or publish, because Executor is down. I didn't start the usual repair session, since a new agent would add load to the overloaded PC. **It still needs fixing** |

## What to run later

Run on the homelab or an idle PC, in this order. Set `B=/home/erikf/projects/personal/cars-data/datasets/imagery-stockholm`; scripts are in `research/truth/scripts/imagery/`. **The commands are untested on the worker.** `heavy` syncs only git-listed files, or the current directory outside git, and `$B` isn't in the repo. So first make a job folder outside git holding copies of `scripts/imagery`, plus `model/`, `tiles/`, `tiles7/`, `det016/`, `s2/` and `caps/central_sites.json`, then run `heavy --small --no-develop -- ...` from there. Use `heavy pull` to get results back. Run Python with `-I`, and don't run anything from inside the downloads.

| Step | What | Command | Size and cost |
|---|---|---|---:|
| 1 | Environment | `nix build --no-link --print-out-paths --impure --expr 'let p=import (builtins.getFlake "nixpkgs") {system="x86_64-linux";}; in p.python3.withPackages (q: with q; [numpy pillow onnxruntime rasterio pyproj scipy shapely])'` | Cached on the PC; on the worker a download of unknown size |
| 2 | Score Sveavägen | `python3 -I evaluate.py $B` | Under a minute, no download. It also needs step 3's output for the other rows |
| 3 | Accuracy against resolution | `python3 -I detect.py $B/model/LibreRFDETRn-obb.onnx $B/tiles7 $B/det032 0.32`, then the same with `det050 0.5`; then step 2 again | 686 windows, about 10–15 min on 3 threads, under 1 GB RAM, no download |
| 4 | Camera log, weekday 07:00–09:30 | First change `cams_log.py` to keep a set of seen photo times, because the server sometimes returns older frames and it saves those again. Then `python3 -I cams_log.py --inventory $B/cams/snap1/inventory.json --out $B/cams/peak1 --names "Sveavägen,Odengatan,Hornsg,Götgatan,Fredhäll,Centralbron,Tegelbacken,Traneberg,Johanneshovsbron,Skansbron" --minutes 150 --every 60` | About 20 cameras, about 93 MB, almost no CPU. All 327 would be 1.4 GB per 2.5 h, or about 14 GB a day, and need a parallel fetch |
| 5 | Sentinel-2 analysis | `python3 -I s2_analyse.py $B S2C_34VCL_20260410_0_L2A`, then `s2_trucks.py` per clear scene | About 1 min for one; about 4 MB each, about 90 MB for 22 scenes |
| 6 | **Needs Erik's login:** Tuesday flight, central corridors | Fetch tiles from `orto-o2-2023`, reading only road windows from the COGs where possible, then run `detect.py` | About 700 MB per tile, about 3.5 GB for 5. Script not written: `fetch_sites.py` uses the viewer only |
| 7 | All of Stockholm, one flight | Same | 48 GB, about 31 CPU-hours for full tiles at 0.67 s/window (MODELLED); roads only is perhaps 3–6 hours (rough guess at road share). `heavy --big` only |

**To reach a real test:** step 6, then about 500 more hand labels from roads not used here, held out from threshold choice, and a detector trained on orthophotos. Label by someone other than the threshold-setter if possible.

## Dead ends

- **`hades.slu.se` Lantmäteriet mirror:** 403, for SLU users.
- **`ortofoto-ar` and historical paths on minkarta:** return an HTML page, not a WMS. So the viewer can only give the newest flight, not the Tuesday one.
- **`dl1.lantmateriet.se/bild/data/...tif`:** 401 without login. The `/bild/pub/` folder is open but holds only thumbnails and photo-time files.
- **Stockholm's `openstreetgs` WMS:** no orthophoto layer. The data portal's search API returned HTTP 500.
- **Guessed Trafikverket v1 image URL:** 404. Use the v2 URLs in `cams/snap1/inventory.json`.
- **Hugging Face search for DOTA YOLO in ONNX:** nothing usable turned up in several searches; those repos hold `.pt` files or other formats.

## New directions, not covered

- **Commissioning one drone or aircraft pass in a peak hour** over one corridor: repeated frames give speed and queues directly. This may need permits and money.
- **Shadow and building lean correction** using the laser height model, to recover cars hidden on tall streets.
- **Kerbside parking census** from four 0.16 m flights: real parked-car blockage on each link, useful to capacity in `cars`.
- **Other Swedish cities:** the same catalogue covers 735 collections, so any city test in this report can be repeated cheaply.
- **Other cities' camera archives,** such as the Jinan set in the brief, could train the low-angle detector that step 4 will need.

## Sources I opened

- Lantmäteriet [STAC catalogue](https://api.lantmateriet.se/stac-bild/v1/), [Min karta terms](https://www.lantmateriet.se/sv/kartor/vara-karttjanster/min-karta/), [download guide](https://www.lantmateriet.se/contentassets/6b85c93c6954407e855c896da5a415f2/guide_radiant_earth_ortofoto.pdf), [product description PDF](https://www.lantmateriet.se/globalassets/geodata/geodataprodukter/flyg--och-satellitbilder/e_pb_ortofoto.pdf)
- Stockholm stad [orthophoto specification](https://dataportalen.stockholm.se/dataportalen/Data/Stadsbyggnadskontoret/Allm%C3%A4n_produktspecifikation_Ortofoto.pdf), `od_gis:Arstrafik` (cached copy from report 01)
- [Trafik Stockholm cameras](https://trafiken.nu/stockholm/kameror/), [Earth Search STAC](https://earth-search.aws.element84.com/v1), [Esri World Imagery metadata](https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer?f=json)
- Papers as linked above. Numbers in `$B/evaluation.json`; note its 0.32 m and 0.5 m rows are empty zeros because those runs never finished, not real results.
