# 06: Collecting our own congestion truth by sampling public sources

## The answer

**Sampling Google, TomTom, HERE or Azure to build our own table is cheap but breaks their terms.** 129,024 live calls over four weeks would cost €109 on TomTom and about $1,182 on Google. All four restrict keeping the results, Google bans bulk download by name, and Waze bans automated access outright. So I did not write a collector for them. Mapbox is the cheapest and its Terms of Service have no explicit storage ban, but I could not read its Product Terms, so it stays unresolved.

**Two better routes need no sampling at all:**

1. **KoDa, a real archive of Stockholm bus positions.** It starts on 1 December 2020, is free and is CC0. It needs a free key from Erik. It gives dated bus travel times by hour straight away, with no weeks of collecting.
2. **TomTom Traffic Stats, measured car speeds per road segment per hour.** Sweden is covered from 2014, and there is a self-serve 30-day trial. TomTom's own docs list this use: "Use the speeds and travel times in transportation models as the actual driven ground truth." The catch is that it's for evaluation only and downloads must be deleted after 60 days. Keeping results needs TomTom's permission (draft below).

**With no key at all,** SL's departures API works today. I built a collector and ran it live: it recovered 56 stop-to-stop bus times on 14 lines between 03:53 and 05:31 this morning. That proves the pipeline works, but it contains no rush hour. Its terms forbid building your own copy, so it's for short tests only. Real collection should use KoDa.

## Ranked table

Grades: MEASURED (I ran it or counted it), PROVIDER CLAIM (their docs, read by me), UNVERIFIED (not opened, or a search snippet only).

| # | Source | What it measures | Stored table allowed? | Cost | Key Erik must provide |
|---|---|---|---|---|---|
| 1 | **KoDa VehiclePositions, SL** | Real GPS of buses, dated, Stockholm county, from 1 Dec 2020 | **Yes, CC0** | Free | Trafiklab account and key |
| 2 | **TomTom Traffic Stats** (API, MOVE portal, Batch) | Car and device GPS, hourly speed per segment, with percentiles. Sweden from 2014 | **Evaluation only**, delete downloads within 60 days | Trial free, then contact sales | TomTom MOVE or MyTomTom account |
| 3 | **Trafikverket TravelTimeRoute and TrafficFlow** | Detector-based travel time, speed and flow, live | **Yes, CC0** (from report 01, not reopened) | Free | Trafikverket API key |
| 4 | **SL Transport departures** | Predicted and settled times per stop, live | **No long-term copy**, see below | Free | **None. Prototype works today** |
| 5 | Mapbox Directions | Route duration, live, or typical with `depart_at` and `duration_typical` | **Unresolved.** Product Terms unreadable | 100k free, then $2.00 per 1,000 | Mapbox token |
| 6 | TomTom Routing and Flow Segment | Live, historic and free-flow time in one call; flow speed | **No**, clause 11.4 | 20k free a month, Routing tier 1 €1.00 | TomTom key |
| 7 | HERE Routing and Traffic | Route time, flow speed | **No**: benchmarking banned, cache headers only | Free tier; prices not readable | HERE key |
| 8 | Google Routes | Route time with traffic models | **No**, clauses quoted below | 5,000 free, then $10 per 1,000 | Google Cloud billing and key |
| 9 | Azure Maps | Route time, traffic | **No** derived database; cache only for latency, 6 months at most | 1,000 free; prices not readable | Azure subscription |
| 10 | Waze | Crowd-sourced alerts and jams | **No**: automated access banned; data for partners only | Partner programme | Partner approval |
| 11 | Bing Maps | Route time | Service closing | Free tier retired, Enterprise ends 30 June 2028 | Not an option |

## Terms, in their own words

I read these directly. This is my reading and not legal advice.

**Google.** Erik's billing address would be in Sweden, so the EEA terms apply. Google's main terms say so: "If Customer's billing account address is in the European Economic Area, the Google Maps Platform EEA Terms of Service... will govern". [EEA terms](https://cloud.google.com/terms/maps-platform/eea), section 3.3.2:
- "(a) No Scraping. Customer will not export, extract, or otherwise scrape Google Maps Content for use outside the Services. For example, Customer will not: (i) pre-fetch, index, store, reshare, or rehost Google Maps Content outside of the Services; (ii) bulk download Google Maps Content".
- "(b) No Caching" except as the service terms allow. For Routes, [those terms](https://cloud.google.com/terms/maps-platform/eea/maps-service-terms) (20.2) allow only "latitude and longitude values" for 30 days, not durations.
- "(c)... (v) use Google Maps Content to improve machine learning and artificial intelligence models, including to train, test, validate or fine-tune the models." This bears directly on the learned drivers work.

**TomTom developer APIs.** [Portal terms](https://docs.tomtom.com/legal/terms-and-conditions):
- 11.4: "The caching or storing of any Results shall be prohibited except" within the cache-control headers.
- 11.6.1 bans "the creation of any secondary or derived database".
- 2.2 limits free use to Evaluation Use, defined as "internal evaluation and testing by you of the Licensed Products". Production use needs a Permitted Solution, which must include asset management functionality (2.1).
- 11.6.10 bans benchmarking against "similar products of TomTom's competitors" without written approval. So comparing TomTom with Google is out.

**TomTom Traffic Stats** falls under the same terms as a "Traffic Analytics Product". Clause 11.6.12 bans keeping downloaded copies for "longer than 90 days, or 60 days where applicable in the case of a Traffic Analytics Product". Whether a derived comparison may be kept or published is not clear, so ask.

**HERE.** [Platform terms](https://www.here.com/en-gb/terms/here-platform-terms), effective 18 September 2023:
- 6.4 bans use "for: (i) benchmarking of third-party data sets".
- 6.4(j) limits storing to 30 days "unless Results are used solely for your internal testing, evaluation".
- But the Location Services exhibit (1.3) adds: "you may not use HERE Materials in a manner that pre-fetches, caches, or stores data or Results, except as explicitly allowed by the caching headers". The second clause cuts against the first carve-out.
- 6.4(f) bans use with any machine learning system, including "predictive analytics".

**Azure Maps.** [Microsoft Product Terms](https://www.microsoft.com/licensing/terms/productoffering/MicrosoftAzure/MCA) ban "a derived database populated wholly or partially with Customer's content" and allow caching only "to reduce latency", for at most 6 months.

**Waze.** [Terms](https://support.google.com/waze/answer/12373727), modified 8 July 2026: you may not "use automated means to access Content from the Service" or "mass download Content or create a database by systematically downloading and storing Content". The licence is for "personal, non-commercial purposes". So I did not touch Waze's unofficial live-map endpoints, and there is no prototype. Real feeds go through the [partner programme](https://www.waze.com/partners/wazeforcities).

**Mapbox.** The [Terms of Service](https://www.mapbox.com/legal/tos) I read contain no explicit storage ban. A third-party guide, [gotime](https://gotime.readthedocs.io/en/stable/compliance.html), quotes "you may not cache, store, or export any map content", but that sentence is **not in the current text I downloaded**. The [Product Terms](https://www.mapbox.com/legal/product-terms) rendered empty both with curl and in a browser, so **unverified**. Free non-production use means "internal development, evaluation, testing and demonstration and not in the course of any business operation, process or analysis". Applications related to analytics must buy a licence for production use. Don't treat Mapbox as cleared until the Product Terms are read.

**SL Transport.** The [API page](https://www.trafiklab.se/api/other-apis/sl/transport/) says "No API key is required", but also: "You should however not make excessive requests". For volume it points to GTFS Regional. The [SL API terms](https://www.trafiklab.se/api/other-apis/sl/licence/) ban "copy Provided Data in order to create your own transcript of the Provided Data", except temporary caching. They also assume a registered account, which this no-key API doesn't require. So I kept the test small, and the collector refuses runs over 3 hours.

**KoDa.** [Licence](https://www.trafiklab.se/api/our-apis/koda/license/): "Data from the KoDa API is available under the CC0 1.0 Universal". GTFS Regional is CC0 too. Trafiklab: "All the data on Trafiklab is provided free of charge". This settles an open question in report 01: the key has no cost.

## Per-source record

| | KoDa VehiclePositions | TomTom Traffic Stats | SL Transport (no key) |
|---|---|---|---|
| **Measures, how** | Bus GPS published as GTFS-RT, archived daily | Floating car data from devices, in-dash systems and apps | Stop-board times; settled value close to the actual call |
| **Area, period** | SL region, 1 Dec 2020 to yesterday (PROVIDER CLAIM) | Sweden from 2014 (PROVIDER CLAIM). Some history may be removed for privacy | Live only |
| **Share of vehicles** | About 0% of cars. It samples buses, not cars. Share of the bus fleet reporting: UNVERIFIED | Undisclosed for Stockholm. NDW describes 10 to 20% in the Netherlands (report 06). Ramboll's Stockholm study says "low penetration rate" | Buses only |
| **Sampling rate** | Live feed updates every 2 s (PROVIDER CLAIM). Rate in the archive: not seen | Hourly aggregates | 3 departures per line and direction per poll (MEASURED) |
| **Level** | Trip-level tracks, so any road section | Route and segment | Stop pairs |
| **Accuracy** | Not tested without a key. See limits below | "Good agreement" with MCS radar in Stockholm, 5 weeks in 2019, on slides with no numbers ([Ramboll, POLIS 2021](https://polisnetwork.eu/wp-content/uploads/2021/12/3B.-Joakim-Ahlberg.pdf)). Whether TomTom was the supplier isn't stated | See test below |
| **Access** | Free key | Self-serve trial | Open |
| **Licence** | CC0, commercial use fine | Evaluation only | CC-BY style, no transcript |
| **Covers Sweden** | Yes | Yes | Yes |
| **Downloaded?** | **No.** Answers HTTP 400 "Access key has to be supplied" (MEASURED) | **No.** Needs an account. Docs read | **Yes**, plus the full stop list: 14,194 stop points, 6,502 sites |
| **Needs served** | Congestion truth | Congestion truth; partly routes | Congestion truth (test only) |
| **Test in `cars`** | Peak-to-night time ratio per section, on real dates | Car speed by hour per section, the direct test | Checks the pipeline only |
| **Integration work** | About 1 day, scripts written | About 1 day once a key exists | Done |

### What each API returns
- **TomTom Routing** ([docs](https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/calculate-route)) has `computeTravelTimeFor`, which returns `noTrafficTravelTimeInSeconds`, `historicTrafficTravelTimeInSeconds` and `liveTrafficIncidentsTravelTimeInSeconds` in one call, plus `departAt`.
- **TomTom Flow Segment** ([docs](https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/traffic-flow/flow-segment-data)) returns `currentSpeed`, `freeFlowSpeed`, `currentTravelTime`, `freeFlowTravelTime`, `confidence` and `roadClosure`.
- **Google Routes** ([docs](https://developers.google.com/maps/documentation/routes/traffic-model)) has `BEST_GUESS`, `PESSIMISTIC` and `OPTIMISTIC`, with a future departure time. `TRAFFIC_AWARE` needs the Pro SKU. [Prices](https://developers.google.com/maps/billing-and-pricing/pricing).
- **Mapbox** ([Directions](https://docs.mapbox.com/api/navigation/directions/)) has `depart_at` and `duration_typical`. Matrix is limited to 10 coordinates with `driving-traffic`.
- **HERE:** field names not verified, its docs did not render for me.

**Accuracy of these APIs is thin.** I found no peer-reviewed Stockholm validation. A Jordan study reports trip-time accuracy of 70% for Google, 57% for HERE and 52% for Waze, but I saw only a search snippet (the page returned 404), so UNVERIFIED. A route API also returns a *model output*, smoothed and blended with history. Grade any table from one as MODELLED, not measured. Traffic Stats aggregates raw GPS, so it's closer to measurement.

### Bus as a congestion sensor: what it can and can't do
Trafiklab's own [KoDa page](https://www.trafiklab.se/api/our-apis/koda/) says public transport "can also be seen as a sensor in traffic". [Pu et al. 2009](https://www.worldtransitresearch.info/research/94) studied whether buses are sensitive enough to infer car conditions, and I read the abstract only. Peng et al. 2020 reportedly found a 6.96 km/h mean absolute difference against loop detectors, but the page returned 403, so that's a search snippet only, UNVERIFIED.

Limits:
- **Stops and signals:** dwell time is mixed in. Compare ratios, peak against night, on the same section, rather than absolute speed.
- **Bus lanes:** a bus in its own lane says nothing about cars.
- **Priority at signals:** may differ from cars. UNVERIFIED for SL.
- **Headway:** few buses per hour on some sections.

**Bus lanes need their own mask, and I found a map gap on the way.** I counted lanes in `stockholm.net.xml`: **only 2 of 82,496 non-internal lanes allow buses but not cars** (MEASURED). OSM has 404 of 154,216 road ways tagged as busway or bus lane (MEASURED; tag absence doesn't prove there's no lane). Conversion seems to drop nearly all of them, so `cars` lets cars use lanes they can't use in real life. Tagged share by road name:

| Most tagged | Ways tagged | | No tags found | Ways |
|---|---|---|---|---|
| Roslagsvägen | 25 of 62 | | Essingeleden | 54 |
| Folkungagatan | 41 of 110 | | Sveavägen | 111 |
| Västerbron | 2 of 6 | | Birger Jarlsgatan | 117 |
| Skanstullsbron | 4 of 14 | | Norra länken | 37 |
| Valhallavägen | 24 of 163 | | Klarastrandsleden | 38 |
| Odengatan | 14 of 102 | | Hantverkargatan | 36 |
| Södertäljevägen | 16 of 147 | | Centralbron, Södra länken, Johanneshovsbron | 19, 11, 8 |

Counts are in `cars-data/datasets/congestion-sampling/design/osm-bus-lane-ways.txt`.

## The collection design

**Corridors:** 24 named roads, both directions, **48 directed corridors with 238 gates**, 218 km in total. All are cut from the `cars` Stockholm network so measured and simulated roads match. Files: [`corridors.csv`](../../../scripts/congestion/corridors.csv) (gates, about every 1 km) and [`corridors_edges.csv`](../../../scripts/congestion/corridors_edges.csv) (start, end, length, lanes).

| Class | Directed | km | Roads |
|---|---|---|---|
| Motorway | 16 | 132 | Essingeleden, Södra länken, Norra länken, Nynäsvägen, Värmdöleden, Uppsalavägen, Södertäljevägen, Centralbron |
| Arterial | 10 | 38 | Roslagsvägen, Drottningholmsvägen, Västerbron, Klarastrandsleden, Johanneshovsbron |
| Urban | 22 | 48 | Hornsgatan, Ringvägen, Götgatan, Folkungagatan, Sveavägen, Birger Jarlsgatan, Valhallavägen, Odengatan, Sankt Eriksgatan, Hantverkargatan, Lidingövägen |

Gates are ordered along each road's main axis, so strongly curved roads may need a manual check. Which bus lines use each corridor comes from the first KoDa static file. The net has no edges named E4 or E20 (`audit.json`), so those roads are here under Uppsalavägen, Södertäljevägen and Essingeleden. Södra länken gives only about 0.8 to 0.9 km per direction under that name, too short to use alone, so its real length needs edges found another way. The `bus_lane_length_share` column in `corridors_edges.csv` reads about zero because of the net gap described above, so use the OSM counts or NVDB instead.

**Step A: bus table from KoDa. Cost $0.**
- Dates: 2025-10-07, 08, 09, 14, 15, 16, 21, 22, 23 (Tuesday to Thursday, no school break), plus 2025-10-11 and 12 (weekend). Add 2020 and 2023 dates later for trend checks.
- Run: `koda_fetch.py`, extract with `nix shell nixpkgs#p7zip`, then `koda_segments.py`. Each archive takes 1 to 60 minutes to build on first request. One at a time, up to 3 at once at most.
- Output: section, date, hour, number of buses, median time, 15th and 85th percentile, km/h.
- Archive sizes are unknown until a key exists. If decoding one day takes over 10 minutes, it goes through `heavy`.

**Step B: car table from TomTom Traffic Stats. Trial, free.**
- Route Analysis on the same 48 corridors, Tuesday to Thursday by hour, October 2025 to match Step A. Routes can use up to 50 via points.
- Start the 30-day clock only when an agent is ready to run it. Route length and date limits show only after login.
- Delete downloads within 60 days unless TomTom says otherwise.
- Compare with bus results on the same sections. That gives the bus-to-car relationship, which then lets six years of bus data say something about cars.

**Step C: motorway check from Trafikverket. Cost $0.**
TravelTimeRoute and TrafficFlow, sources as in report 01, polled every 5 minutes as my default. Report 01's working assumption is that they're live only, in which case every day without a key is lost data. I wrote no collector, since it needs a key to test. It's independent of both sources above, though report 01 notes it may not be independent of `TrafficFlow`.

**The commercial sampling option, costed for completeness.** Only worth doing under a licence that allows keeping results:

| Option | Calls | Google Pro | TomTom Routing | Mapbox Directions |
|---|---|---|---|---|
| Typical table: 48 corridors, every 15 min, 3 day types, future departure time. Needs only one run. | 13,824 | $88 | Free | Free |
| Live: 48 corridors, every 15 min, 4 weeks | 129,024 | $1,182 | €109 | $58 |

MEASURED arithmetic from prices I read. TomTom's €1.00 is read as per 1,000; the unit wasn't printed in the text I extracted. Google assumes the Pro SKU. HERE and Azure prices didn't render. Route APIs can switch path between calls, so pin the route with via points. This table gets you modelled output at best. Step B gets you measurements for free, so I'd skip this.

**How it tests `cars`.** Run `cars run --trace`, then apply the same gates to simulated cars through `scripts/cars_trace.py`:
- *Motorways:* simulated km/h by hour against Traffic Stats and Trafikverket.
- *Urban:* for each section and hour, time divided by the same section's night time, simulated against real. Only on sections with no bus lane.
- *Pass mark:* to be set from the day-to-day spread in the real data, which Step A provides.

The gate logic is tested on a synthetic GTFS-RT feed only, with exact results (18.0 km/h recovered from a 5 m/s track). The `cars` side isn't written yet, about half a day.

## The live no-key test

I polled 14 sites along inner-city and suburban corridors on Monday 2 November 2026, from 03:53 to 05:31 CET, with no key and no account (MEASURED). I stopped the first run early and restarted it slower because the API began rate limiting.

| Result | Value |
|---|---|
| Rows logged | 4,277 bus calls |
| Pace | First run one poll every 4.3 s; second run one every 6.4 s with a 60 s back-off |
| HTTP 429 | 7 or more in about 11 minutes in the first run; 14 of 616 polls (2.3%) in the second |
| Calls seen, per journey and stop | 374 |
| Dropped as unsettled | 202 (54%), not tracked or not seen close to their time |
| Stop-to-stop times recovered | 56, on 14 lines, in 46 line, stop-pair and hour rows |
| Rows with more than one bus | 10 of 46 |
| Straight-line speed | Median 18 km/h, range 7.7 to 44 |
| Actual minus scheduled time | Median +7 s, range -158 to +272 s |

**What this shows:** the method works from the feed alone, including pairing one journey across stops. Line 4, for example, gave Fridhemsplan to Hornstull in 354 s against 300 s scheduled at 05:00 to 06:00.

**What it doesn't show:** anything about congestion. The run ended at 05:31, before any rush hour, and every tracked bus in the log was in `NORMALPROGRESS`. I chose not to run it through the morning peak, because of the time box and the no-transcript clause.

**Why this feed can't replace KoDa:**
- `expected` is SL's own prediction shortly before the call, not a measured pass.
- With 90 s polling, times are only good to about a minute or two. Short sections are unreliable: Odenplan to S:t Eriksplan on line 697 came out at 70 s against 228 s scheduled.
- The API starts refusing requests at only about 10 to 14 polls a minute, so the 14 sites used here are close to the practical limit.

Files: `cars-data/datasets/congestion-sampling/sl-departures-test/` (`merged.csv`, `segments.csv`).

## Scripts

All in `scripts/congestion/`, standard library only:
- `sl_departures_collect.py`: no-key collector, refuses runs over 3 h, backs off on 429.
- `sl_departures_segments.py`: stop-to-stop times from that log, drops unsettled values.
- `koda_fetch.py`: downloads KoDa archives, handles HTTP 202. Needs `TRAFIKLAB_KEY`, not run yet.
- `koda_segments.py`: decodes GTFS-RT without dependencies and builds the hourly section table. Tested on a synthetic feed only, never on real KoDa files.
- `make_corridors.py`: builds the corridor files from a SUMO net.

Samples, terms text and logs are in `/home/erikf/projects/personal/cars-data/datasets/congestion-sampling/`.

## Top 3 recommendations

1. **KoDa bus table.** Next step: Erik creates the Trafiklab key. Then one agent runs Step A on one test day to learn file size and rate, then the other ten. About a day of agent time.
2. **TomTom Traffic Stats trial.** Next step: Erik creates a MOVE account and hands over the key when an agent is ready. It's the only direct measurement of car speed by hour across Stockholm I found that can start today. Send the permission question below at the same time.
3. **Trafikverket collection, started now, plus putting bus lanes in the net.** Next step: Erik creates the Trafikverket key (report 01 asks for this too). The bus-lane conversion gap goes to whoever owns the map work, because it affects capacity on the roads above.

## What only Erik can do

1. **Create a Trafiklab account and key** at trafiklab.se, with a project that includes KoDa and GTFS Regional. Free. Bronze is enough, since KoDa has no call limit.
2. **Create a TomTom MOVE account** at move.tomtom.com when ready, which starts the 30-day clock.
3. **Create a Trafikverket API key**, as in report 01.
4. **Optional, send the note below to TomTom.** It only matters if results should be kept or published.

**Draft to TomTom.** Not checked against Erik's writing style, because the Executor server was down during this work. Check it before sending.

> Hi,
>
> I'm building an open traffic simulator of Stockholm and want to check it against real speeds. I'm looking at Traffic Stats for about 50 routes in Stockholm, by hour, for October 2025.
>
> Under your terms I read the evaluation as internal testing, with downloads deleted after 60 days. Two questions:
>
> 1. Can I keep the hourly speed tables after that, for my own validation work?
> 2. Can I publish comparison results, such as the error between simulated and measured speed per road?
>
> If that needs a paid licence, what would it cost for this size, and is there a research rate?
>
> Thanks,
> Erik Frankling

## Dead ends

- **KoDa or GTFS-RT without a key:** HTTP 400 and 403 (MEASURED). I searched for a public mirror or sample of SL VehiclePositions and found none.
- **Whole-day timetable from SL departures:** tempting, since `forecast=1200` reaches 20 hours ahead. But the feed returns only 3 departures per line and direction (line 4 direction 1 gave exactly 3), and `forecast=1440` returned no departures. KoDa static GTFS is the right tool.
- **Waze live-map endpoints:** not tried, because the terms ban automated access.
- **Bing Maps:** free tier retired, Enterprise ends 30 June 2028.
- **Keys embedded in public websites:** not looked for and not tried. They aren't access anyone gave us.
- **Unread:** `legal.here.com` returned 503 throughout, but the same terms are at `www.here.com/en-gb/terms/`.

## New directions I couldn't cover

- **EU text and data mining exceptions** (Directive 2019/790, articles 3 and 4). Article 3 covers research organisations and may be why university groups can do what a private person can't. I could not open the text (EUR-Lex returned an empty 202), so **unverified**. If Erik has a KTH link, ask KTH. Worth a lawyer's view before relying on it.
- **Ramboll's CODE PROBE project with Trafikverket:** Stockholm probe data validated against MCS radar over 5 weeks in 2019. Its report would name the supplier and give numbers. Slides only so far.
- **TomTom Batch on Databricks or Microsoft Fabric:** the terms mention in-place evaluation there. Whether Stockholm is among the sample areas is visible only after login.
- **Mapbox Traffic Data and Movement Data:** paid products, not priced here.
- **Other Swedish operators in KoDa:** Gothenburg, Skåne and others use the same format, so the scripts could carry over.
- **The `journey.state` field in SL's feed:** it has `SLOWPROGRESS` and `NOPROGRESS` values, which might be a ready-made delay flag. Not studied.

## Corrections to earlier reports

- **Report 01** says "whether a Trafiklab or Trafikverket key has any cost" is open. Trafiklab: free of charge. Its no-login row also leaves out SL Transport, which is reachable for short live tests.
- **Report 02** says "No link-level historical API data or licence obtained" for TomTom. Still true that none was obtained, but a self-serve trial of exactly that exists.
- **Report 01 and the brief** on KoDa: confirmed. SL VehiclePositions from 1 December 2020 (page modified 16 October 2026).
