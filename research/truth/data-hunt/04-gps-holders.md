# 04: The companies that hold everyone's GPS

## The answer

Nobody sells or gives away "every car's route on one day". The raw traces stay inside the companies. What gets out is aggregates: speeds per road, zone-to-zone trip counts, and modelled volumes.

The biggest free release is **HERE's Traffic4cast data**. It's real GPS from a large mixed vehicle fleet, in 5-minute bins and roughly 100 m cells with 4 headings, for 12 cities including Berlin (180 days in the MeTS-10 version), London, Madrid and Melbourne. It costs nothing and takes one web form. Sweden isn't in it, and it has no routes. Congestion truth (need 3) is what it gives you.

For **Stockholm**, the real options are:
- TomTom's 30-day free trial
- KTH's own iMobility Lab, which stores taxi GPS and number-plate camera data
- a paid Telia licence

The data exists and people here already use it. Trafikverket buys INRIX travel times for about 4,500 km of road. Aalto University has bought hourly Telia trip matrices that include Stockholm, down to 250 m, running until 2027.

No company publishes how much of Swedish traffic it sees. The numbers below are provider claims or foreign measurements, and they range from about 2% to "up to one in five".

Grades used below: **M** = measured, **P** = provider claim, **Mod** = modelled, **U** = unverified (only a search excerpt or a secondary source, or I couldn't open the original).

## Ranked table

"Needs" means: 1 demand, 2 routes, 3 congestion truth, 4 maps, 5 signals.

| # | Source | What it is | Area and period | Share of vehicles, and how known | Sampling and level | Access and price | Licence | Sweden? | Downloaded? | Needs |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **HERE Traffic4cast + MeTS-10 pipeline** | GPS probes turned into "traffic movies": probe count and mean speed. MeTS-10 is the code that maps them onto OSM roads. | Antwerp, Bangkok, Barcelona, Berlin, Chicago, Istanbul, London, Madrid, Melbourne, Moscow, 2019–2021, 108–361 days; New York and Vienna are also on HERE's list. [M] | **Unknown.** Provider mix isn't public, and counts are capped and normalised to 0–255, so they can't be read as a share. | 5 min, about 100 m, 4 headings. Link-level at best, no routes. | Free, instant, after a form. | Academic and non-commercial only. No redistribution, including derivatives. | No | Paper and notes only. **The data sits behind the form, see below.** | 3, weakly 1 |
| 2 | **TomTom MOVE** (O/D Analysis, Traffic Stats, Traffic Volume) | OD matrices between your own zones, "via" zones and selected-link analysis, travel time percentiles, modelled hourly volumes | Traffic Stats: Sweden from 2014. Volumes: Sweden from 2024, road classes FRC 0–7. O/D: Sweden not confirmed. [M, TomTom docs] | "Up to one in every five vehicles" and "more than one in five globally" [P]. NDW, a Dutch buyer, says 10–20% (report 06). Nothing for Sweden. | Traces; outputs are per zone pair or per road segment | **30-day free trial**, then sales quote. No price or academic plan found. | Not read; trial terms need checking | Yes | No (needs an account) | 1, 2, 3 |
| 3 | **KTH iMobility Lab** | "1500 GPS-equipped taxis", ANPR cameras, Bluetooth, microwave detectors, bus AVL and passenger counts [P, lab page] | Stockholm. Taxis at least Sep 2012–Sep 2013. | Occupied taxis only. Share not measured. | A KTH thesis reports about 15 s between points over six months, not stated to be this same file. Taxis may use bus lanes. | Ask. Terms aren't published. | Unknown | Yes | No | 2, 3, some 1 |
| 4 | **Swedish Car Movement Data (Chalmers)** | GPS loggers in private cars chosen by stratified random selection from the vehicle register | Västra Götaland and Kungsbacka, 2010–2012. 714 cars, 528 with over 30 days. [M, final report] | Tiny, but the **selection method is known**, which is rare | **2.5 Hz** positions and speed, matched to the road database | Research use only, tiered for privacy. In 2013 it was run by Lindholmen Science Park; current contact not verified. | Agreement with the car owners limits use to research on vehicle movements, energy, safety and societal planning | Yes, but Gothenburg region and old | No | 2, some 1 |
| 5 | **Telia Crowd Insights** | Mobile network signalling: OD matrices, visits, road segment volumes. All modes, not cars. | Sweden. Aalto's purchase: Stockholm and 10 other municipalities, from 1 Jan 2023, quarterly until Nov 2027. | Telia had 32–33% of Swedish mobile subscriptions in 2021–22 (Trafikanalys). That's phones, not cars. Results are scaled up. | Hourly or daily, down to 250 m in cities | Commercial, no price public. Aalto's copy is restricted to Aalto people. | Purchased licence | Yes | No | 1 |
| 6 | **Trafikanalys + Telia (public)** | Trips by county, month, mode and purpose, combining Telia with the RVU survey | Sweden, 2020–2023 | Same as above. Marked experimental. | County level | Public interactive tables | Not stated | Yes | No, tables only | 1 (totals only) |
| 7 | **INRIX through Trafikverket** | Travel times on short road segments | About 4,500 km, mainly around Stockholm, Gothenburg and Malmö [M, Trafikverket 2023] | Unknown | 1-minute realtime values, also kept as history | Bought under contract. A public request might work, but contracts can restrict sharing. | Contract | Yes | No | 3 |
| 8 | **Spectus / Cuebiq Social Impact** | App location data, aggregated | Geography not stated | Unknown | Aggregates, or a clean room | Pro bono for "qualified academic research" | Restrictions apply | Not verified | No | 1 |
| 9 | **Google Environmental Insights Explorer** | Yearly km driven and trip counts per city: inbound, outbound, inside | City level | Unknown | Annual totals, partly modelled | Sign-up for people who work in or with a city | Varies | Stockholm not verified | No | 1 (one total) |
| 10 | **Mapbox Traffic Data sample** | Typical speed per OSM node pair, every 5 minutes through a week | Wilmington, North Carolina, out of date | 700M monthly app users claimed [P] | 2,016 speed columns per road | Sample is free. Full data needs a licence. | Testing only | No | **Yes**, 80 MB, 248,280 rows | Format example only |

### More on number 1, because it's the one to get

**The download.** There is no MeTS-10 file. You download HERE's movies and generate MeTS-10 yourself with [the pipeline](https://github.com/iarai/MeTS-10), because the licences don't allow publishing the result (paper, Supplement A). The only live source is [HERE's sample data page](https://www.here.com/developer/sample-map-data). The file list in the page source is:

- 2019: Berlin, Istanbul, Moscow (2018 data)
- 2020: Berlin, Moscow
- 2021: Antwerp, Bangkok, Barcelona, Berlin, Chicago, Istanbul, Melbourne, Moscow, New York, Vienna
- 2022: London, Madrid, Melbourne. The [2022 README](https://github.com/iarai/NeurIPS2022-traffic4cast) says 2.8, 4.0 and 0.9 GB.

**I did not download the movies.** The page says you fill in the form and thereby agree to academic and non-commercial use. The direct S3 links are visible in the page source, but using them would skip that agreement, and the brief says no forms in Erik's name. So this is one job for Erik, about five minutes.

**What's inside** ([spec](https://github.com/iarai/MeTS-10/blob/master/README_DATA_SPECIFICATION.md), [paper](https://arxiv.org/abs/2302.08761)). Each day is 288 × 495 × 436 × 8 bytes, which I calculate as about 497 MB uncompressed, or about 90 GB for Berlin's 180 days. The 2022 archives also include the matched road graph and public loop counters, up to 7,000 per city.

**How good each city is** (paper, Table VIII, 20 sampled days). "8–18 coverage" is the share of road segments with a speed value in daytime. [M]

| City (year) | Days | Dates | 8–18 coverage | Mean segment volume | Loops in the 2022 archive? |
|---|---|---|---|---|---|
| Moscow (2021) | 361 | 2019-01 to 06, 2020-01 to 06 | 0.71 | 46.9 | No |
| Istanbul (2021) | 180 | 2019-01 to 06 | 0.63 | 24.5 | No |
| **Berlin (2021)** | 180 | 2019-01 to 06 | **0.36** | 57.3 | No, but the paper validates against 547 sensors |
| **Madrid (2022)** | 109 | 2021-06 to 12 | **0.36** | 22.1 | **Yes** |
| **London (2022)** | 110 | 2019-07 to 2020-01 | **0.24** | 8.2 | **Yes** |
| Antwerp (2021) | 361 | 2019-01 to 06, 2020-01 to 06 | 0.17 | 7.1 | No |
| Chicago (2021) | 180 | 2019-01 to 06 | 0.11 | 9.8 | No |
| Barcelona (2021) | 361 | 2019-01 to 06, 2020-01 to 06 | 0.09 | 6.2 | No |
| Melbourne (2021) | 180 | 2019-01 to 06 | 0.08 | 5.6 | No |
| Melbourne (2022) | 108 | 2020-06 to 12 | 0.08 | 4.5 | Yes, but see below |
| Bangkok (2021) | 361 | 2019-01 to 06, 2020-01 to 06 | 0.05 | 7.5 | No |

Volume is normalised, so comparing it between cities is only a rough guide.

**Things to watch:**
- **Melbourne is thin.** Report 01 ranks it as the strongest city, but this dataset is sparse there. The 2022 window also falls in Melbourne's 2020 lockdown (from memory, not re-checked), so it doesn't show a normal day. Berlin, Madrid and London are better for this test.
- **"Volume" isn't a flow.** It's the number of GPS points in a cell, capped and rescaled, so slow cars count more than fast ones. It's a relative signal at best.
- **Speed is a mean of instantaneous GPS speeds.** That's close to space-mean speed, so compare it with space-mean speed from `cars`. Comparing with time-mean will look wrong (the paper finds this difference against Uber).
- **Validation.** The authors compared against 547 sensors in Berlin, 236 speed sensors in London and 404 in Madrid, and report "good alignment". Sensors usually read a bit higher than MeTS-10. In Berlin, 10 motorway or trunk sensors (2%) read 10–15 km/h lower. I didn't find one headline error figure. [M, by the authors]
- **Licence.** Academic and non-commercial only, with no redistribution of derivatives. **If `cars` ever becomes commercial, or the repo goes public with derived files, this data can't go with it.** Keep it in `cars-data`, not the repo.

**Test it enables.** Run Berlin on a weekday and compare 15-minute speeds per road class against MeTS-10. Use the spread between real weekdays as the noise floor, as report 06 recommends. The data doesn't depend on our demand, so it's a real check. In London and Madrid, divide probe volume by loop count per site, which shows how uneven the probe share is.

**Work.** Downloading and running the pipeline takes about a day. Use `heavy` for anything over 10 minutes. Matching MeTS-10 edges to our networks and adding the comparison script is maybe 2–3 days more.

### How much of traffic do they see?

| Holder | Figure | Grade |
|---|---|---|
| TomTom | "More than one in five vehicles on the road globally" ([product sheet 2024](https://download.tomtom.com/open/banners/historical-traffic-volumes-product-sheet.pdf)); "up to one in every five" ([OD page](https://www.tomtom.com/products/origin-destination-matrix-analysis/)) | P |
| TomTom in the Netherlands | 10–20%, varying by time and place (NDW, via report 06) | Buyer's spec |
| Wejo in New Jersey, USA | 2.3–4.4% by road type, against 46 counting stations ([paper](https://arxiv.org/abs/2208.04703)) | M |
| INRIX Trips, USA | "About 10% of trips" (same paper, quoting others) | U |
| HERE | "Around 1%", may vary drastically (a HERE patent, search excerpt only) | U |
| Google, Apple | Nothing published that I could find | None |
| Telia | 32–33% of Swedish subscriptions ([Trafikanalys PM 2023:6](https://www.trafa.se/globalassets/pm/2023/pm-2023_6-mobilnatsdata-som-kalla-till-resvanor-i-sverige.pdf)) | M, phones not cars |
| Telenor | About 20% of Swedish subscriptions (Trafikverket 2020) | M, phones not cars |

**Probe share isn't constant.** [Luo et al. 2026](https://trid.trb.org/View/2701453) matched loops and probes in Madrid, Luzern, Zurich and London. Share is only uniform within about 0.4 km and half an hour, so one scaling factor for a city is wrong. MFD estimates still stay within about 6%. I only read the abstract.

### Real prices

| Product | Price | Grade |
|---|---|---|
| StreetLight, San Mateo County 2020 | $440,000 normal rate per year, $275,000 discounted first year, $363,000 later; **a 50-zone single project about $24,000+**; $99,000 per agency under 300,000 people ([C/CAG slides](https://ccag.ca.gov/wp-content/uploads/2020/04/6.3_StreetLight-Presentation.pdf)) | M, public document |
| Replica, Portland 2018 | $457,300 for 12 months, 20 cents per person ([BikePortland](https://bikeportland.org/2018/12/05/portland-ponders-pilot-of-powerful-transportation-data-tool-292817)) | Reported from the ordinance |
| Replica, El Paso 2020 | $170,000 per year, $510,000 for 3 years ([agenda](https://www2.elpasotexas.gov/municipal-clerk/agenda/03-31-20/19.2.1.pdf)) | M, public document |
| Google Roads Management Insights | About $150,000–$1.5M per year, public sector only ([third-party blog](https://blog.afi.io/blog/roads-management-insights-from-google/)) | U |
| TomTom historic data licence, UK | £359,841 to May 2025; buyer unknown ([Contracts Finder](https://www.contractsfinder.service.gov.uk/Notice/8dcb1260-3e81-49fb-bfbb-7cc6c62ed7c6) blocked me, search excerpt only) | U |
| TomTom, HERE, INRIX, Mapbox, Telia, Veraset | No published price. All say to contact sales. | None |
| TomTom API free tier | 2,500 non-tile requests a day ([pricing](https://developer.tomtom.com/pricing), search excerpt). Storage terms not checked. | U |

These US prices are for agency licences and aren't quotes for Stockholm. StreetLight's research page offers ["budget-conscious licenses"](https://info.streetlightdata.com/transportation-research) for academics (search excerpt, page wouldn't open), but report 06 found it documents only US and Canada.

## Top 3 recommendations

**1. Get Traffic4cast and generate MeTS-10 for Berlin, then London and Madrid.** It's free today and it's real congestion truth.
Next step: Erik fills in the form. An agent then downloads Berlin 2021 and London 2022, runs the pipeline with `heavy`, and adds the speed comparison.

**2. Use the TomTom trial on Stockholm, once, when it's ready.** It's the only route I found to real Stockholm OD, selected-link route shares, travel time percentiles and modelled hourly volumes, with no person having to say yes.
Next step: prepare first, because the clock runs once. Get the zone GeoJSON from the `cars` Stockholm network, pick the dates and the corridors. Then Erik creates the account, reads the trial terms, and we pull everything in one go.

Three things I couldn't verify:
- whether O/D Analysis covers Sweden (its page says to check the map selector or ask)
- the trial's caps (docs show 20,000 km² and 600 regions as a standard grant, and contracts can differ)
- whether the trial terms allow research use and publishing

Sweden was TomTom's weakest country in its 2024 volume check, according to a search excerpt of [the validation page](https://docs.tomtom.com/historical-traffic-volumes/documentation/accuracy-and-validation/2024), which returned 404 when I opened it. It gave SQV 0.82 and a 95th percentile error above 30%, on 855 counters. So treat volumes as Mod and check them against `Arstrafik`.

**3. Ask KTH's iMobility Lab.** Erik is at KTH, and this is Stockholm-specific GPS, plate cameras and detectors, already collected.
Next step: Erik sends draft A. The taxis give real paths and travel times through Stockholm, which would be a route choice test on real paths, with the known bias that they're occupied taxis using bus lanes. Older data matters less for road layout than for demand.

## The order for most real data, least money

1. **HERE Traffic4cast.** 0 kr, five minutes. Real GPS, many months. Not Sweden, no routes.
2. **TomTom 30-day trial.** 0 kr. Stockholm OD and travel times, if the terms and coverage hold.
3. **KTH iMobility.** 0 kr if they agree. Stockholm taxi paths, ANPR.
4. **Chalmers car movement data.** 0 kr if they agree. 2.5 Hz traces from randomly selected Swedish private cars. It also helps the driver model work in report 05.
5. **Trafikanalys public tables.** 0 kr, county totals for checking demand. Then a free run of Trafikverket's own API, which report 01 already lists.
6. **Telia.** Ask for a research quote. Trafikanalys says finer than county or under a year isn't fully reliable, so check it before paying. In Trafikverket's 2020 trial, the Telia-based flow estimate averaged −1.9% against traditional counts, yet 50% of sites missed the ±5% goal. Telenor's averaged 28.9% off, and 92% missed it. [M]
7. **TomTom or INRIX academic deal.** Unknown price. INRIX said in 2018 that it gives some universities free or discounted data, and names Texas A&M and Maryland ([case study](https://inrix.com/wp-content/uploads/2018/10/Indiana-Case-Study_FINAL.pdf)). It's worth one email.
8. **Don't buy** StreetLight, Replica, Veraset or similar for this. They're US-focused or unverified for Sweden, cost far too much, or are raw phone pings with hard GDPR questions (report 06).

## What only Erik can do

1. **Fill in the HERE form** at the page above, as a student, with a real description. Only do it if `cars` is non-commercial for this use. That's his call, and I can't tell from here.
2. **Create the TomTom MOVE account**, when the zones are ready.
3. **Send the drafts below**, if he wants. Nothing has been sent. Please check the facts about yourself and whether the named people are still in those roles.

**A. KTH iMobility Lab** (the lab page names Erik Jenelius as director)

> Hi Erik,
>
> I'm a student at KTH and I'm building a GPU traffic simulator. I want to test it on Stockholm against real data instead of other simulators.
>
> I saw the iMobility Lab has GPS from taxis, ANPR and detector data. Would it be possible for me to use some of it for research? I mainly need travel times and paths on normal weekdays. Aggregated data is fine.
>
> Could we talk for 15 minutes?
>
> Thanks,
> Erik

**B. Chalmers** (the [project page](https://research.chalmers.se/project/8908) lists Sten Karlsson and Sonia Yeh, not checked if current)

> Hi,
>
> I'm a student at KTH working on a traffic simulator. I read about the Swedish car movement data project. Can researchers outside Chalmers still get access to the GPS data, and who should I ask?
>
> I'd like to use it to look at real routes and speed profiles. Trip-level data without home locations would be fine.
>
> Thanks,
> Erik

**C. Telia Crowd Insights, or to TomTom or INRIX with the product name swapped**

> Hi,
>
> I'm a student at KTH building a traffic simulator for Stockholm. I'm interested in Crowd Insights trip data (origin-destination, hourly) for Stockholm county for a few weeks.
>
> Do you have research or student pricing? What would a small extract cost, and can results be published?
>
> Thanks,
> Erik

**D. Trafikverket, in Swedish** (Per-Olof Svensk is the contact on the 2023 report TRV 2022/53136)

> Hej,
>
> Jag är student på KTH och bygger en trafiksimulator för Stockholm. Ni skriver i rapporten "Fordonsgenererade data till nytta för Trafikverket" att ni köper restider från INRIX.
>
> Får man använda historiska restider för Stockholm i forskning? Jag behöver några vanliga vardagar. Om det inte går, kan jag få ta del av vad avtalet säger om det?
>
> Tack,
> Erik

## Dead ends

- **IARAI's Traffic4cast site:** `www.iarai.ac.at` no longer resolves, so old forum download routes are dead. The 2022 test inputs on [Google Drive](https://drive.google.com/uc?export=download&id=16MDOeCHVIjM9Sy3cvFP-XX8r7LH1gYFQ) return 404. I found no open mirror.
- **Uber Movement:** the site has been [gone since 1 Oct 2023](https://zenodo.org/records/10479336). The only archive found is five Indian cities. No Berlin or London mirror found, and no sign of Stockholm.
- **Waze for Cities:** [for government and road operators](https://waze.com/wiki/USA/Waze_for_Cities), who are expected to share data back. A [TU Delft request](https://www.waze.com/discuss/t/waze-connected-citizens-program-university-membership/90007) for a university route got no real answer. Trafikverket is already a partner, per its 2023 report.
- **Google Roads Management Insights:** [public sector and road operators only](https://developers.google.com/maps/documentation/roads-management-insights/guidelines), limited to their own territory. No Sweden customer found. Worth knowing Trafikverket or Stockholm stad could buy it. Vehicle counts are only planned, per the blog above (U).
- **Project Green Light:** [no Swedish city named, no public data](https://sites.research.google/greenlight/). For cities only.
- **Google EIE:** [for people working in or with a city](https://insights.sustainability.google/resources). Yearly totals only, so it can't give routes. Stockholm not verified.
- **Google research datasets, Apple:** no current traffic release found.
- **Wejo:** went into administration in 2023; some intellectual property went to Jacobs for $14M (trade press, search excerpt). **Otonomo:** merged into Urgently in 2023. **Teralytics:** no recent news, and its site blocked me, so status is unknown. **Arity:** US only and [sued by Texas in 2025](https://insurify.com/car-insurance/news/texas-ag-suing-allstate-data-collection/) over how it collects data.
- **Mapbox Movement:** an activity index, not vehicles. [Sweden isn't a standard region](https://docs.mapbox.com/data/movement/overview/), though custom requests exist.
- **StreetLight, Replica:** US and Canada (report 06).
- **Meta Data for Good:** [HDX](https://data.humdata.org/m/dataset/movement-range-maps) blocked me. From search excerpts it's area-level, not vehicles, and movement range stopped in 2022. Not useful.
- **Dewey / Veraset:** academic platform through university subscriptions, price not published. I couldn't verify whether KTH subscribes or whether Sweden is covered.
- **Volvo Cars:** I found no research GPS dataset. Volvo sells friction data to Trafikverket, and that's the known link. Zenseact Open Dataset is sensor data, with sequences from Warsaw, 3.4 TB, by application.
- **Bolt:** [€300,000 lab with ETH Zürich](https://zagdaily.com/featured/bolt-funds-e300k-research-project-to-propel-shared-mobility-across-europe/), partner cities Seville and Hanover. No public data, nothing for Stockholm. **Lyft:** nothing found (light search).
- **Tele2 and Tre:** no Swedish mobility product found. Telenor and Tre partnered in Trafikverket's 2020 trial, and the Tre partner dropped out.
- **INRIX + MetroLab Challenge:** [free API access for up to a year](https://inrix.com/inrix-metrolab-challenge/), but through the US MetroLab Network and with a 2025 deadline on the page.
- **HERE's other free samples:** the road maps cover 31 places and none are Swedish.
- **Orbis:** its road network is the same as Overture's transportation theme, which is free (search excerpt). Lane products are paid. Maps are other reports' area.

## Corrections to earlier reports

- **06, section on academic releases:** treats MeTS-10 as a dataset you can open. It's a pipeline, and you must get HERE's movies and generate it yourself under a no-redistribution licence.
- **06, TomTom row:** "no Stockholm extract" still holds, but Sweden is documented: Traffic Stats from 2014, modelled volumes from 2024, and a free trial.
- **01, Melbourne as strongest:** still true for open counts and signals, but not for GPS speed coverage, where it's among the weakest.
- **01, `TravelTimeRoute`:** the API notes say travel times come from detectors, but Trafikverket's 2023 report says FCD from INRIX feeds its travel times and trafiken.nu. It may be mixed. Check before calling it independent of probes.

## New directions I couldn't cover

- **A consented panel.** The EU Data Act lets car owners share their own vehicle data with a third party they choose, with stronger direct-access rules for products from 12 Sep 2026. A KTH student panel could give real routes legally. Small, but actually Stockholm.
- **Public records.** Offentlighetsprincipen could reveal what Trafikverket, Stockholm stad or Region Stockholm paid for data, and on what terms. That would give the first real Swedish prices.
- **Turning shares and signal timing from FCD.** Trafikverket's 2023 table lists route choice and turning shares as data types that can be bought. TomTom Junction Analytics and INRIX Signal Analytics may cover needs 2 and 5 (from memory, not verified).
- **Luo et al. 2026:** check whether its matched probe and loop data can be shared.
- **Compass IoT in Melbourne:** connected vehicle data from many car makers in Australia, with no research terms found. **Geotab:** gives Swinburne researchers access; a similar KTH deal is untested. **Mercedes:** sells to the Dutch government and Trafikverket.
- **HERE's hackathon files** (Berlin, Chicago, Krakow, Mexico, Cairo) are listed after the same form. Contents unknown.
- **Stockholm taxi data outside KTH.** Theses from 2015 used taxi GPS from winter 2014–15 at about 15 s intervals. The company behind it isn't named in what I read.

## What I actually did

Downloaded to `/home/erikf/projects/personal/cars-data/datasets/`: the MeTS-10 paper (`mets10-paper/`), HERE's general release note (`here-t4c-notes/`), and the Mapbox sample (`mapbox-traffic-sample/`). No account or form was used, and nobody was contacted. I read the Trafikverket 2023 and 2020 reports, the Trafikanalys memo, the Chalmers report and the MeTS-10 paper by extracting their text and reading the relevant sections, not cover to cover. Anything marked U rests on a search excerpt or a secondary source.
