# 09: Better road map data than plain OpenStreetMap

Written 2026-11-02. Grades: **MEASURED** (I downloaded or queried it and counted), **PROVIDER CLAIM** (a source's own page says so), **MODELLED** (my estimate), **UNVERIFIED** (not opened or not confirmed).

## The answer

**The source that would improve the simulator most is Stockholm city's own legal traffic rules, and it is free, with no login.** The city's open WFS has 58,661 geometry records of its local traffic regulations, each with a line on the map, the full legal text, a date and a link to the official register. They name the lane: "Hornsgatans södra körbana, höger körfält", "Valhallavägens södra körbana, mittkörfält". Report 07 did not use this layer. **Lane counts are the one thing it doesn't give.** The best source for those is NVDB `AntalKörfält2`, which needs Erik to get a key.

**Overture is not better than what we have for this.** Its road schema has no lane field at all, and in central Stockholm it is OSM with new packaging. TomTom's share is 720 short segments with no attributes. Nobody open offers lane-level maps of Stockholm.

What the rules show about our nets, within central Stockholm (MEASURED by geometry matching, with limits below):

| Check | `v5_inventory` | `n7_ramps` |
|---|---:|---:|
| Bus-lane rule records with a bus-only lane in the net, of 455 | 120 | **0** |
| Multi-lane edges under a bus rule but fully open to cars | 189 edges, 16.2 km | 256 edges, 31.1 km |
| Upper estimate of major-road lane-km that shouldn't be car lanes (MODELLED) | 2.8% | 5.1% |
| Road length with a speed limit more than 5 km/h from NVDB | 12.5% major, 11.3% minor | 12.7%, 11.2% |
| NVDB forbidden turns (154 in the area) still open | 66 | 71 |
| One-way rules on plain streets that the net has two-way or reversed | 17 long enough to check; NVDB also has a one-way at 12 | near-identical |

**No simulation has been run on any of this.** Report 02 already found that closing bus lanes alone raises teleports (1,721 to 2,692), so a truer map may make the overload worse until demand and signals are fixed. It is more correct, and the effect on traffic is unknown.

## Ranked sources

| # | Source | Gives | Result in central Stockholm | Access |
|---|---|---|---|---|
| 1 | **Stockholm LTFR rules** (WFS `ltfr:LTFR_FORESKRIFT`) | Bus lanes with lane position, one-ways, vehicle bans, turn bans, pedestrian streets, speed rules, dates, exemptions | Found real errors in both nets. Downloaded | Open, no key |
| 2 | **NVDB layers on the same WFS** | Bus lanes, forbidden turns, speed limits (live, changed October 2026), road width | Speed and turn errors found. Width is not usable | Open, no key |
| 3 | **NVDB `AntalKörfält2`** (Trafikverket API) | Official lanes per link and number of bus lanes, not which lane is which | **Blocked:** API answers 401 with no key | Free key, Erik |
| 4 | **Trafikverket NetInfo WMS** | NVDB one-ways (not on the city WFS), bans, stops, state-road traffic flows; no lanes | Worked as a second opinion on one-ways | Open, no login |
| 5 | **Mapillary** signs and road markings | Detected signs; possibly arrows | Not tried: every request needs a token | Free token, Erik |
| 6 | **Panoramax** street photos | Lane markings and signs by eye | 13 of 100 sections, 5 of 30 junctions; settled one site | Open, CC BY-SA |
| 7 | **Esri aerial** (0.5 m) | Road layout, some lane counts | Weak for lanes: 47 of 100 judged, 64% match. No arrows | No key; terms unread |
| 8 | **Overture 2026-10-21** | OSM's data, plus TomTom's 720 segments | No lane field. Adds almost nothing here | Open, ODbL. Downloaded |
| 9 | HERE HD Live Map | Lane model; a Stockholm tile is used in MathWorks' example | Not available to test | Separate agreement with HERE; price unknown |
| 10 | TomTom Orbis Lane Model | Lane geometry and markings | PROVIDER CLAIM: lane-level available in Germany; other countries unnamed | Sales; price unknown |
| 11 | Microsoft RoadDetections | Road lines and width from imagery | No lanes, Sweden not named. Not downloaded | ODbL, archived |
| 12 | Argoverse 2, Zenseact | HD maps elsewhere; Warsaw driving data | No Stockholm map | Open |

Every source here describes the road, not traffic. So share of vehicles observed, sampling rate and route-level or link-level don't apply to any of them, and they all serve need 4 (maps) only.

## Source records

| Source | Measures, how | Area, period | Validation | Licence, commercial use | Downloaded | Test it enables | Work |
|---|---|---|---|---|---|---|---|
| LTFR | Legal decisions with drawn geometry | Stockholm municipality only; rules in force now, with dates. Only 649 of 58,661 records have ended, so history is thin | Legally binding text. Links to Transportstyrelsen's RDT; I opened 19 rule pages. Street reality not checked beyond one site | PROVIDER CLAIM: "får vidareutnyttjas fritt ... licensfritt" unless stated otherwise. Commercial use not separately addressed | Yes: index of all, geometry and titles of all, full text of 3,203 | Net with rules against without, on identical demand | 1–2 days |
| NVDB layers on city WFS | Official road database, live | County-wide layers; I took central Stockholm plus existing full layers | Newest change 2026-10-21 (MEASURED) | Same | Yes | Speed and turn A/B | Hours |
| `AntalKörfält2` | Official lane count | Sweden, current | Unknown until opened | PROVIDER CLAIM via OSM wiki: NVDB is CC0 | No, blocked | Fix missing-tag lanes; check net lane counts | 1 day after key |
| NetInfo | WMS with feature queries | Sweden | Capabilities: fees none, constraints none. Search excerpt of the service description says CC0; the PDF returned 404 when I opened it | CC0 UNVERIFIED | Queried, about 110 points | Independent check of rule matches | Done |
| Mapillary | Detections from crowd photos | Coverage in Stockholm unknown | Unknown | Not stated in the page I read | No | Turn-arrow and sign check | 1–2 days after token |
| Panoramax | Crowd 360° photos, mostly July 2026 here | Thin | By eye | CC BY-SA 4.0 | 7 photos | Spot checks | Done |
| Esri | Satellite, June 2025 | Global | Stated accuracy 8.47 m (report 07) | Terms unread: private analysis only | Tiles for 130 sites | Layout check | Done |
| Overture | Conflation; OSM here | Global, monthly | 98 of 100 one-way, 96 of 100 class, 91 of 97 speed match OSM (MEASURED) | ODbL | Yes: 52,313 road segments, 8 MB | None beyond OSM | None |

## The comparison

I picked 100 sections (15 trunk or primary, 40 secondary, 25 tertiary, 20 local; seed 9; no tunnels or bridges) and 30 junctions (18 signalised, 12 not; the 8 named sites from report 07 that fall in the area, plus random). Full tables: [sections](09-data/sections_compare.csv), [junctions](09-data/junctions_compare.csv).

**100 sections, MEASURED:**

| Attribute | What each source says |
|---|---|
| Lane count, OSM | 72 tagged. Net follows the tag on 71 (the other had a lane added by ramp guessing). **28 have no tag and take the default.** |
| Lane count, NVDB | Blocked. |
| Lane count, width | 70 have a width, 62 of them "minimum value", and 39 work out below 2.5 m a lane (my matcher adds the other carriageway on divided roads, which overstates that). Not usable for lanes. |
| Lane count, aerial, read blind before seeing the net | I could judge 47. 30 match (64%): 20 of 32 tagged, 10 of 15 untagged. Most tagged misses are likely my misreads of parking and bus lanes. On untagged roads I saw more lanes than the net on 4 of 5 misses (Ekelundsvägen twice, Sveavägen, Henriksdalsvägen). |
| Lane count, Overture, TomTom open data | No field. |
| Bus lanes | 18 sections have a bus rule, 17 an NVDB bus lane. `v5` has a bus lane on 9, **`n7` on none**. 8 of the ways have a `psv:lanes` or `bus:lanes` tag. |
| One-way | 3 sections have a rule. Overture equals OSM on 98 of 100, so it adds nothing. |
| Speed | 98 comparable, 80 within 5 km/h. Most misses are net 50 against NVDB 40. |
| `v5` against `n7` | 10 sections differ in car lanes, 8 of them because `v5` closed a bus lane. |

**30 junctions, MEASURED:**

- **Turn lanes are the real gap.** Only 20 of 159 approaches (13%) have arrows in OSM. NVDB doesn't hold them: nvdb2osm's documentation says "NVDB saknar även information om vilka fält som är till för att svänga". No open source has them.
- Turn bans: 4 NVDB bans at these junctions, 1 still open in `v5`. Overture has turn restrictions on 27 nearby segments, and they come from OSM.
- NVDB's signal flag is not reliable. It says no signal at Tegelbacken (J04) and Hornsgatan/Ringvägen (J16), where the city register has 41 and 33 lanterns within 70 m. Don't use it to delete signals.
- Roslagstull (J07) is still unsettled: NVDB says signals, the register has none, the net has a priority junction. Report 07 found the same.
- Aerial shows junction layout and it looked right at all 30. Arrows can't be read from it at this resolution. One Panoramax photo does show arrows, so street imagery can do it where it exists.

**Rule by rule, across central Stockholm:**

1. **Bus lanes.** 455 records. `v5`: 120 honoured, 302 open, 33 no matching edge. `n7`: 0 honoured, because it was built without `--osm.lane-access`. Recent ones are often missing from OSM: Valhallavägen's 2025 rules have `lanes=3` and no bus tag. Checked by eye at one site: a July 2026 photo at rule 0180 2025-04961 shows a blue bus-lane sign and "BUS" painted in the left lane, where the net has three car lanes. A Vattugatan photo was inconclusive and one for Hantverkargatan showed a sculpture. So the precision of the 189 and 256 edge counts is **not** established, and they could be off in either direction: I matched against a truncated edge list, and some matches may be neighbouring roads.
2. **A cheap bug.** Of the 43 tagged ways on those 189 `v5` edges, 37 use `lanes:psv=1`, as on Ringvägen. netconvert doesn't read that form: `lanes:psv` appears nowhere in `NIImporter_OpenStreetMap.cpp`. 26 ways in the area have it. The tag gives no position, and the rule text supplies it.
3. **One-car-lane edges under a bus rule.** 187 edges in `v5`. Many are probably right for cars, with the bus lane mapped as a separate way or not at all. Odengatan is the example: rules put a bus lane in the left lane, and the net shows one car lane. I do not count these as errors.
4. **One-ways.** 339 rule records. 217 agree, 56 have no car edge, 66 disagree. Of those 66, 27 are false alarms from my matcher (one rule per carriageway, cycle paths, loop wording) and 5 name a carriageway and need a look. **34 are on plain streets, from 22 rules; 17 of those rules are long enough to test.** NVDB has a one-way there at 12 of 17, against 26 of 30 on a control set of rules where the net agrees. So these are real disagreements between official sources and OSM. [List](09-data/oneway_adjudicated.csv).
   - **Best-proven:** Upplandsgatan, rule 0180 2026:04082, in force 3 October 2026 and confirmed in NVDB under the same number. Our OSM clip's newest edit is 23 October, so OSM hadn't caught up.
   - **Needs a street check:** Osquars Backe, Alviksvägen and Industrigatan, where OSM says `oneway=no` outright, so a mapper may have looked. NVDB has no one-way at Osquars Backe. I did not compare NVDB's direction with the net.
5. **Speed.** Ringvägen, 3.55 km: net 50, NVDB 40. I read the rule: 40 km/h from 22 October 2025. Hornsgatan, 1.24 km: same, from 23 October 2025. So OSM is over a year behind here. Some misses are unchecked and may be matching errors or apply to parallel roads, such as Drottningholmsvägen at net 50 and NVDB 60.
6. **Turn bans.** 154 NVDB records in the area. In `v5`: 66 matched an open movement (48 of them left turns), 61 had an approach but no matching movement, 27 no approach. NVDB gives no exemptions, so buses may be allowed through. The 62 LTFR turn, U-turn, mandatory-direction and no-entry records have exemptions in the text. **I did not check those against net movements.**
7. **Lane lower bounds.** A rule naming a "middle" lane implies at least 3 lanes, "left" or "right" at least 2. 81 of 326 checkable records imply more lanes than the net has. Most are likely the same case as point 3.

**Corrections to report 07:**

- It treated `--osm.lane-access` as nearly solving bus lanes, with 293 of 295 tagged edges fixed. That's right against OSM's tags, but OSM's tags are the limit: against the legal rules, `v5` honours 120 of 455 records.
- It said reading NVDB needs no login. That is what Trafikverket's page says, but `AntalKörfält2` returned "Invalid authentication" to an anonymous request.
- It listed Overture, Lanelet2, OpenDRIVE and TomTom as unopened. Overture is now tested, and no Stockholm Lanelet2 or OpenDRIVE map turned up in one search (UNVERIFIED that none exists).

## How to merge it into the network build

Add one stage to `research/truth/scripts/maps_recipe.sh`, between step 2 (OSM to plain files) and step 4 (rebuild). OSM stays the base and each layer overrides a named attribute:

| Order | Layer | Edit | Plain file |
|---|---|---|---|
| 1 | NVDB `AntalKörfält2`, when there's a key | Set lanes only where OSM has no tag; list disagreements for review | `plain.edg.xml` |
| 2 | LTFR bus rules, with NVDB as second opinion | Pick the lane from the text (right, left, middle), set `allow="bus"` on it. A bus-only carriageway closes the edge to cars | `plain.edg.xml` |
| 3 | `lanes:psv=N` with no position | Use the rule's position; default to the right lane only if no rule exists, and flag it | `plain.edg.xml` |
| 4 | LTFR one-ways plus NetInfo | Remove the banned direction | `plain.edg.xml` |
| 5 | NVDB turn bans and LTFR turn rules | `<delete>` the connection, or keep it for buses where the text exempts them | `plain.con.xml` |
| 6 | NVDB speed, LTFR as tie-break | Set speed per edge and direction | `plain.edg.xml` |
| 7 | LTFR vehicle bans and pedestrian streets | Full-time bans close the edge. Timed and through-traffic-only bans are listed, not applied | `plain.edg.xml` |

Rules for the stage:

- **Match by geometry, not ID.** Parallel within 35°, within 15 m, covering at least half the rule, and the street name agrees. [`rules_vs_net.py`](09-scripts/rules_vs_net.py) and [`lane_rules.py`](09-scripts/lane_rules.py) already do most of this.
- **Don't apply anything automatically that fails a match test.** It goes in a review list, with the false-alarm classes from point 4 filtered out.
- **Write provenance for every edit:** source, rule number, date, confidence, as report 07 proposed.
- **Date-stamp the net.** Filter on `VALID_FROM` and `VALID_TO`, so it says "as of 2026-10-23" and matches the OSM clip.
- **Keep the existing guards:** route repair with `duarouter`, `maps_sanity.py`, plus new checks for rules honoured and rules unmatched.
- **Outside the municipality nothing changes**, because LTFR stops there. NVDB layers still apply.

Test: same demand, `n7_ramps` against `n7_ramps` plus each layer in turn, compared on the existing Stockholm metrics. I built none of this: the stage is a design, and netconvert hasn't run with these edits.

## Top 3 recommendations

1. **Build the rule overlay from the open sources, starting with bus lanes and `lanes:psv`.** Next step: write `apply_rules.py` from the two matching scripts, add it to `maps_recipe.sh`, and run the A/B above. No permission needed. Do the bus-lane precision check first: 30 random edges from [the list](09-data/lr_v5_bus.csv), by photo or by Erik.
2. **Get the NVDB key and take `AntalKörfält2`.** It's the only official lane count: 28 of 100 sections have no OSM tag, and report 07's 188 false lane drops depend on it. Next step: Erik registers, then load it through `api.trafikinfo.trafikverket.se/v2/data.json`, 10,000 records a page (the `nvdb-downloader` QGIS plugin documents the call). Compare it with the net before changing anything, because its accuracy in the city is unknown.
3. **Treat turn lanes as a separate survey, and don't buy a map yet.** No open source has them: 13% of sampled approaches have OSM arrows. Next step: use a Mapillary token and Panoramax to read arrows at the 100 busiest signal approaches, and merge them as `turn:lanes`. Only ask HERE for a price if that fails.

## What only Erik can do

1. **NVDB key.** Create an account at [data.trafikverket.se](https://data.trafikverket.se/). Read its licence terms when you accept them; I couldn't read them without signing in. Hand the key over through a secret request, not in chat.
2. **Mapillary token.** Free client token from Mapillary's developer dashboard, which needs an account.
3. **Street check, a few minutes each.** Which way can you drive on Industrigatan (Fridhemsgatan to Kungsholms Strand), Alviksvägen by Alviksplan, and Osquars Backe? The rules say one-way; OSM says two-way. These decide how far to trust LTFR over OSM.
4. **Esri's terms**, before publishing any aerial image. Same open point as report 07.
5. **Draft to the city's geodata office**, optional. It asks about kerb lines and road markings, which I couldn't find in open data. I couldn't load your writing style because the Executor server is down, so rewrite this in your own words:

> Hej! Jag bygger en öppen trafiksimulering av Stockholm och använder Trafikkontorets öppna WFS. Finns körbanekanter, vägmarkeringar eller körfältspilar som vektordata, och går de att få för forskning eller öppet bruk? Vad gäller i så fall för villkor?
>
> To: geodataservice@stockholm.se

## Dead ends

- **Overture lanes.** The full `segment` schema of release 2026-10-21 has no field with "lane" in it (MEASURED, read from the bucket).
- **TomTom through Overture.** 720 segments, 36.9 km, 717 of class `unknown`, none with attributes I could see. Only 20% lie within 15 m of our net, and half are over 50 m away. Not a route to TomTom's lanes.
- **`nvdb-osm-map-data` bucket.** The OSM wiki points to monthly NVDB conversions there. It returns `NoSuchBucket`.
- **NVDB without a key.** API returns 401. NetInfo has no lane layer in any of the 4 versions I read. The city WFS has none either.
- **Width as a lane proxy.** Mostly minimum values.
- **Stockholm WFS for kerbs or markings.** None among its 121 layers. `dataportalen.stockholm.se` metadata redirects to a sign-in page.
- **KartaView.** `api.openstreetcam.org` fails its certificate check. I did not look for another address.
- **Lane-level research maps.** Argoverse 2 covers six US cities, and it's non-commercial. Zenseact's development kit describes driving around Warsaw and no HD map. nuPlan's page came back empty (UNVERIFIED). A search found an HD map project on AstaZero's test track, not a city (UNVERIFIED).
- **Lantmäteriet.** Its open data Q&A page returned 404. A search excerpt says CC0 with a free account and geometry without lane detail (UNVERIFIED). It wouldn't help with lanes.
- **Stockholm's orthophoto.** The city's spec lists it, but the text I could read gave no resolution or open terms. Unresolved.

Don't use the OAuth client secret visible in the Trafikverket portal's public JavaScript. I saw it while looking for API paths and did not use it.

## New directions I noticed

- **Roadworks by date.** The same WFS has `Gatuarbete`, `TA-plan` and `TA-plan_med_storre_trafikpaverkan`. Closures during a validation day could explain some congestion mismatches. Not examined.
- **State roads and neighbouring towns.** RDT rule pages embed their geometry as GeoJSON (seen on two pages), and the register covers other authorities, which could fill LTFR's gap. Bulk access is unverified.
- **NetInfo's other layers:** `ForbudMotTrafik`, `Svangmojlighet`, `Hallplats`, `Mittremsa`, `ADT_total`. The last one is traffic flow, which other agents may want.
- **Time-of-day rules.** Timed bans in LTFR could become time-dependent closures. Parking rules could model kerb lanes lost at set hours.
- **`ForbjudenFardriktning`** through NetInfo could check every one-way in the county, not just the rules I tested.

## Limits of this work

- Everything comes from matching geometry to net edges. I checked conflicts by reading rule text and with NVDB, but only one bus site and no one-way site against a street photo.
- Blind lane counts were by me, from 0.5 m imagery, with an 8 m offset. Treat them as weak.
- Central area only: longitude 17.97–18.13, latitude 59.295–59.365.
- Executor was down throughout (503), so I could not search or update the company brain. Nothing from this session has been published there.
- A `pkill -f` aimed at my own stuck job matched my own shell instead. I then stopped the job by process ID. Nothing else was touched.

## Files

- Scripts: [09-scripts/](09-scripts/). Evidence: [09-data/](09-data/).
- Downloads: `cars-data/datasets/overture-2026-10-21/`, `stockholm-wfs-09/`, `panoramax-09/`. Working files and image sheets: `cars-data/scratch-09/`.

## Sources opened

- Stockholm WFS and terms: `apigw.stockholm.se/Open/VirtialOpenDataGeoServerDMZ.svc/Rest/api/wfs`, [openstreetgs.stockholm.se/Home](https://openstreetgs.stockholm.se/Home), [/Data](https://openstreetgs.stockholm.se/Data)
- RDT rules, for example [0180 2026:04082](https://rdt.transportstyrelsen.se/rdt/AF06_View.aspx?BeslutsMyndighetKod=0180&BeslutadAr=2026&LopNr=04082)
- NVDB: [nvdb.se, hämta aktuella data](https://www.nvdb.se/sv/kund/hamta-aktuella-data/), [Trafikverket news on the 12 datasets](https://bransch.trafikverket.se/tjanster/data-kartor-och-geodatatjanster/nyheter-om-trafikverkets-data/2025/nvdb-vagdata-tillgangliga-i-trafikverkets-datautbytesportal-for-anvandning-i-oppet-api/), `geo-netinfo.trafikverket.se/mapservice/wms.axd/NetInfo`, [nvdb-downloader](https://github.com/matself/nvdb-downloader)
- OSM and NVDB: [Sweden highway import](https://wiki.openstreetmap.org/wiki/Import/Catalogue/Sweden_highway_import), [nvdb2osm README](https://github.com/atorger/nvdb2osm)
- Overture: [segment schema](https://docs.overturemaps.org/schema/reference/transportation/segment/), [release calendar](https://docs.overturemaps.org/release-calendar/), `s3://overturemaps-us-west-2/release/2026-10-21.0/`
- Commercial: [TomTom Orbis Lane Model](https://www.tomtom.com/newsroom/press-releases/general/129429267311461/tomtom-launches-orbis-lane-model-maps-for-fresh-lane-level-precision-at-scale/), [MathWorks HERE reader](https://www.mathworks.com/help/driving/ref/herehdlmreader.html)
- Other: [Mapillary API](https://www.mapillary.com/developer/api-documentation), [Panoramax API](https://api.panoramax.xyz/api/search), [Microsoft RoadDetections](https://github.com/microsoft/RoadDetections), [Argoverse 2](https://www.argoverse.org/av2.html), [Zenseact kit](https://github.com/zenseact-github/development_kit)
- SUMO 1.28 source: `thesis-src/sumo/src/netimport/NIImporter_OpenStreetMap.cpp`
