# City ground truth: choose the evidence before choosing the simulator

Audit date: **31 October 2026**, reviewed the same night (see [Reviewed by Opus](#reviewed-by-opus)). Recommendation and scores are **opinion**, based on the evidence opened below, not a measured league table of cities. Earlier `research/` reports were used only as leads. No simulation, GPU work, account creation, form submission or communication with data owners was performed.

## Decision

**Strongest independent evidence: Melbourne.** It is the only candidate found here with all five evidence types openly published: signal controller sheets, stop-line counts dense enough to hold out thousands of sites, travel-survey microdata, a non-loop sensor network with 15-minute speed histograms, and Bluetooth travel times behind an API key. No login is needed for the first four. Its weaknesses are real: survey OD is only at council level, actual adaptive green splits are not published, Bluetooth has no verified archive, and the engine has no left-hand-traffic support (zero `lefthand` hits in `crates/` and `scripts/`). [Signal sheets][MC], [counts][MV], [VISTA][VI], [TIRTL][TI], [Bluetooth][BT]

**Other winners by mechanism.** The A10 in Amsterdam is the cleanest corridor test: loops about every 400 m against GPS-derived route times, and no signals. Madrid has by far the best open OD: 222,744 survey trips between 1,259 zones. Neither is a full package: Amsterdam has almost no urban detectors and Madrid has no open congestion measure independent of its loops. [NDW FCD][NF], [EDM2018 trips][EDV]

**Stockholm cannot be primary yet, but the earlier verdict here was wrong about why.** An anonymous layer that this report missed, `od_gis:Arstrafik`, holds **63,047 records, all labelled `Uppmätt` (measured)**, from **4,053 sites since 1991**, with hourly direction-split flows and speed statistics. That is enough to falsify the current Stockholm demand tonight. It has no dated days, no peak-hour speeds and no travel times, so it cannot test congestion dynamics. Exactly what Stockholm can and cannot do, with and without Erik's registration, is in [Can Stockholm become primary?](#can-stockholm-become-primary) [Årstrafik][SAR]

The crucial distinctions are **observed versus inferred**, **sensor locations versus network coverage**, **different output variables versus independent observations**, and **a downloadable SUMO scenario versus a measurement dataset**. These are proposed audit principles (opinion), illustrated concretely by Madrid's computed `carga`, NDW's loop-derived versus probe-derived travel times, and LuST's explicit version-specific validation warning. [Madrid schema][MD], [NDW provenance][NT], [LuST maintainers][LU]

## Evidence standard and scoring

**Measured** means an observation or an audit of a retrieved file. It does not mean error-free. **Modelled** means inferred demand, corrected/imputed counts, reconstructed travel times, classified trajectories or synthetic congestion indices. **Opinion** means a recommendation, score, inference about identifiability or proposed experiment. Unknown means **not verified in this session**, not proof of absence.

Scores are deliberately simple and reproducible: five dimensions, each 0–4, summed to /20. A = actual anonymous access (0 failed, 1 gated, 2 partial/metadata, 3 sample, 4 substantial observations); H = usable historical replication (0 none demonstrated, 1 annual summaries, 2 limited campaign/uncertain archive, 3 documented archive, 4 downloaded historical observations plus archive); T = temporal detail (0 annual/bands, 1 hourly, 2 unspecified/heterogeneous, 3 3–15 min, 4 minute/passages/trajectories); N = network relevance (0 none, 1 single corridor, 2 selective/unknown, 3 multiple urban corridors, 4 extensive urban series); I = independent congestion evidence (0 none verified, 1 documented lead, 2 described operational alternative, 3 sample with provenance incomplete, 4 retrieved alternative plus documented provenance). Scores measure **the evidence established here**, not intrinsic city quality. Missing lane/control/demand information is reported separately and remains an acquisition gate.

Count, speed, occupancy, travel time and trajectory abbreviations are Q, V, O, TT and Tr. C = class or length category. Counts below are not road-network coverage percentages; **no candidate's fraction of lane-km observed was established**. National counts must never be relabelled as city counts. Numeric observations calculated here are reproducible with [the audit script](scripts/city_audit.py) and [its output](01-city-sample-audit.json). Exact curl commands, status codes, hashes and failures are in [the download ledger](01-city-download-log.md) and the [review ledger](01-city-review-download-log.md).

## Ranked shortlist

Ties share rank. The second table adds **every other UTD19 city**, rather than silently omitting less famous cities. UTD-only entries share a conservative score because city-specific files could not be fetched without the prohibited signup. That is a ranking of current verification, not a claim that their sensors or science are identical. Scores were revised in review; the older [score chart](fig/01-city-evidence.html) is superseded by this table. [UTD19 access terms and city list][U]

| Rank | City/corridor; score (A,H,T,N,I) | What is actually measured; sites and density | Time, years and producer | Access/licence; fetched evidence and main flaw |
|---|---|---|---|---|
| 1 | **Melbourne / Victoria 18** (4,4,3,4,3) | Per-detector Q at signal sites: on Tue 20 Oct 2026, 3,867 sites inside a Melbourne box, 3,428 with at least 4 live detectors. Separate TIRTL infrared sensors give Q, V bins and class: 382 of 406 sites in the box, mostly freeway. Bluetooth and freeway TT APIs exist. | 15 min; annual archive files from 2014, monthly to October 2026; DTP/SCATS, TIRTL. TT APIs are near real time. | CC BY 4.0 (Bluetooth CC BY-NC 4.0). 127,428,210-byte ZIP and 109,520,482-byte TIRTL ZIP streamed. TT APIs return 401 without a key; no TT payload seen. [Volumes][MV], [ZIP][MELZ], [TIRTL][TI], [Bluetooth][BT] |
| 2 | **Amsterdam / A10–NDW 17** (4,3,4,2,4) | Q,V,C loops; separate GPS-derived TT. In the box: 1,559 count sites, all loops, 1,412 Rijkswaterstaat; 3,642 TT routes (3,037 FCD, 605 loop, 0 ANPR). A10 mainline: 181 records, median 0.4 km apart. | 60 s publication, but FCD speeds are smoothed over the last 15 vehicles, up to 30 min. Open count history from 2010 advertised; open-TT history needs login. | Anonymous gzip XML fetched and parsed. CC0 default, exceptions prevail. Dexter Open Data exports need name, email and reCAPTCHA, no account. No historical payload obtained. [Point metadata][NS], [TT metadata][NC], [terms][NL], [Dexter Open Data][DXO] |
| 3 | **Madrid 15** (4,4,3,4,0) | Q,O; V only on M30/C30; 4,487 point IDs (4,073 urban, 414 M30/C30) and 12,512,133 rows in the December 2022 download; 4,904 live point records. Spatial density not yet calculated. | 15 min archive, 5 min live; July 2013–September 2026 advertised. City circulation authority. | CC BY 4.0; 79,348,668-byte ZIP fetched, CSV streamed and recounted. `carga` is modelled from Q/O, not independent congestion truth. [Archive][M], [file][MZ], [schema][MD], [live][ML] |
| 4= | **New York 14** (3,3,3,2,3) | Toll-gantry entries by crossing and vehicle class, separate from NYC DOT speed/travel-time links. Sensor count, lanes, signals and OD not audited. | 10 min gantry series from 2025; live speed links. MTA, NYC DOT. | Anonymous JSON sample only; 5 and 3 rows read. Entries exclude exemption and repeat-entry information. Added in review as a lead, not audited further. [Entries][NY], [metadata][NYM], [speeds][NYS] |
| 4= | **Helsinki / Finnish Digitraffic 14** (4,4,4,2,0) | Individual Q,V,C, lane/direction passages; national station response has 521 records including inactive records, not 521 active Helsinki sites. | Raw sample 1 January 2024; raw files since December 2021; volume reports since 2010; Fintraffic. | CC BY 4.0. 1,673,804-byte station-day CSV fetched. Corrected aggregate counts and raw detections may differ; city local streets not demonstrated. [Raw data][FR], [documentation][FD], [licence][FL], [stations][FS] |
| 6= | **Berlin 12** (4,4,1,3,0) | Q,V, passenger/heavy categories; January 2015 sample: 502 detector IDs, 369,013 hourly rows. These are lane detectors, not 502 junctions. | Hourly sample January 2015; Berlin's detection archive. | dl-de-by-2.0; actual 4,634,033-byte CSV.gz opened. Sample is explicitly under `alte_qualitaetssicherung`; historical revision announced in 2025. [Archive][B], [sample][BZ] |
| 6= | **Zurich 12** (3,4,1,4,0) | Q at counting locations; detailed detector-location plans linked. Do not equate the current city dataset with the UTD subset without matching records. | Hourly since 2012; city DAV, previous-day updates. | Catalog declares CCZero; first 65,536 bytes of 2012 CSV fetched (206). First row missing, not zero. Imputation flag matters. [Catalog JSON][ZJ], [CSV][ZZ] |
| 6= | **Paris 12** (4,3,1,4,0) | Q,O on >3,000 road sections per city; not all have both. Five initial API rows had null Q/O; second filtered query returned non-null Q. | Hourly, timestamp marks period end; live portal keeps 13 rolling months and links history. DVD/Lutèce. | Anonymous JSON fetched; API metadata declares ODbL. Major-road sampling; hourly bins hide queue cycles. [Description][P], [sample][PS], [licence metadata][PJ] |
| 9= | **London + UK WebTRIS 11** (2,3,2,2,2) | WebTRIS Q/speed/class sources on England's strategic roads; sites endpoint returned 20,076 records nationally, not active London sites. The TfL monitoring document names INRIX and iBus for journey-time data; ANPR appears only in its glossary. | Historic service; updates paused September 2026. TfL/SRN are different networks. | Site JSON fetched; daily observation request returned empty body. Observation licence not resolved; do not equate WebTRIS with central London's signals. [WebTRIS][W], [sites][WS], [TfL][LT] |
| 9= | **Los Angeles / PeMS 11** (1,3,3,3,1) | Freeway Q,V,O leads, C/toll-tag integration; nearly 40,000 detectors is California total, city count not verified. | Caltrans advertises >10 years; exact selected archive interval unverified here. | Login HTML fetched, no observations. Account application free, usually 1–2 business days. Speeds/derived delays depend on algorithms; PeMS14 reprocessed history. [Caltrans][CA], [portal][CP] |
| 9= | **Bay Area / PeMS 11** (1,3,3,3,1) | Same PeMS evidence; district-specific station density not established. Toll-tag integration does not prove an independently downloadable TT subset. | Same Caltrans archive; years must match chosen network. | Same account/rights uncertainty. Freeways cannot establish San Francisco local-street realism. [Caltrans][CA], [portal][CP] |
| 9= | **Norway trafikkdata / Oslo acquisition target 11** (4,4,1,2,0) | Public Q and length classes per lane/direction/point. National point query returned 10,546 records, including bicycle points; not all active motor-traffic sites. Oslo density unknown. | Hourly sample: 1 January 2024, Ørbekk point; NPRA. | NLOD. Read-only GraphQL POST succeeds; GET only serves explorer. Fetched 24 hourly Q records, first 79 veh/h. Ørbekk is not claimed to be an Oslo sample. [Official metadata][NO], [API with exact POST in ledger][NG] |
| 13= | **Athens pNEUMA 10** (2,2,4,2,0) | Naturalistic drone Tr,V,C; project advertises >0.5 million trajectories and >100 intersections across campaign, not simultaneously observed whole-city cars. | 2018 mornings; landing page says five days, actual selector lists four dates. EPFL/Barmpounakis/Geroliminis. | Landing, selector and Zenodo metadata/README fetched; no trajectory payload. Full original ZIP 15.8 GB exceeds cap. Website has inconsistent CC BY/CC BY-NC notices. [Overview][AE], [selector][AD], [Zenodo][AZ] |
| 13= | **Stockholm 10** (4,1,1,3,1) | Measured `Arstrafik`: 4,053 sites; hourly Q by direction and heavy share; speed mean, median and p85 on about half the records. Each year 2019–2025 about 390–560 sites, with 80–157 directional records at 100+ measurement days. A separate estimated layer has 16,698 features. | Annual average weekdays per site since 1991; median 5 measurement days. No dated days. Trafikkontoret, sometimes Trafikverket. | Anonymous WFS, 265,889,338 bytes, fully read. Reuse terms not confirmed as a standard licence. Live flow, TT and bus archive need keys. [Årstrafik][SAR], [method notes][SAV], [estimated layer][SW] |
| 15 | **UTD-only cities, below: 8** (1,2,3,2,0) | Q,O or V at stationary detectors; city counts and usable-road fraction unverified. | ETH assembled campaign 2017–2019; do not confuse collection campaign with each city's observation dates. | Signup and academic/noncommercial conditions; no city observations fetched. [UTD19][U] |
| 16 | **Nashville I-24 MOTION 7** (0,2,4,1,0) | Camera-derived vehicle Tr; first INCEPTION release 47 h across 10 days, 4 miles ≈6.44 km. Not a city network. | First public release September 2023; Vanderbilt/Work group. | Data URL failed TLS verification; www hostname DNS failed. No payload/licence verified. Annotation/tracking uncertainty and corridor scope remain. [Producer announcement][I24] |
| 17 | **Ingolstadt InTAS 6** (2,2,1,1,0) | Authors report validation at 24 traffic-measuring points, 20 TLS, NRMSE 0.33. These are reported model-evaluation results, not a new measured audit. | 2020 scenario publication; 24 h simulation; TH Ingolstadt. | GPLv3 scenario README fetched; raw measured time series and held-out sites not recovered. Model contains lanes/signals but provenance needs audit. [Maintainer README][IN] |
| 18 | **Luxembourg LuST 4** (2,1,0,1,0) | Synthetic scenario; no raw measurement sample recovered. | 24 h simulated mobility; authors explicitly restrict validation claim to SUMO 0.26. | MIT; README fetched. SUMO loop outputs are modelled data. No present-day observational coverage established. [Maintainers][LU] |
| 19 | **Cologne / TAPAS 3** (2,0,0,1,0) | Synthetic activity-demand scenario; real OD trajectories not established. | Scenario documentation, observation years unknown here. DLR. | Official docs fetched; noncommercial terms plus request to inform maintainers. No contact made. Lane/control files would not establish empirical truth. [DLR][CO] |

The PeMS T=3 entries are provisional potential scores; the exact export schema was not retrieved. Reducing both T scores to 2 changes neither recommendation. Zurich A=3 reflects a partial CSV, H=4 a historical observation plus verified archive catalog; the distinction is deliberate. Re-score after acquisition rather than interpreting a one-point difference as statistically significant.

### Every remaining UTD19 city

Each row below is **rank 15, score 8/20**, with the same fully specified UTD-only profile in the previous table: Q/O or V, typically 3–5 min; city-specific sites, years, licence exceptions, lane maps, real signal programs, OD, independent congestion and payload retrieval **unverified**. Common producer/access source is the [ETH UTD19 portal][U], opened and fetched this session. The point of listing them individually is to preserve the search space; no unsupported ordering among them is warranted.

| City | City | City | City |
|---|---|---|---|
| Augsburg | Basel | Berne | Birmingham |
| Bolton | Bremen | Bordeaux | Cagliari |
| Constance | Darmstadt | Essen | Frankfurt |
| Graz | Groningen | Hamburg | Innsbruck |
| Kassel | Lucerne | Manchester | Marseille |
| Munich | Rotterdam | Santander | Speyer |
| Strasbourg | Stuttgart | Taipei | Tokyo |
| Toronto | Torino | Toulouse | Utrecht |
| Vilnius | Wolfsburg | — | — |

London, Los Angeles, Madrid, Melbourne, Paris and Zurich complete the portal's 40-city list and have dedicated entries above. Amsterdam, Berlin, Stockholm and Helsinki are not asserted to be UTD19 cities. **UTD data is not automatically independent of a municipality's archive: it can be the same detectors republished.** This last statement is an experimental-design caution, not a verified record-level equivalence for all 40 cities. [Portal provenance][U]

### Scientific validity of the UTD19 lead

**Measured inputs, modelled network states:** Loder, Ambühl, Menendez and Axhausen (2019; ETH/NYU) analyse **107 regional networks in 41 cities**. Their typical detector interval is **300 s**. They filter errors/noise, rescale occupancy and calibrate network speed using Google Directions queries for **1,000 random OD pairs**, **1–6 km**, excluding freeways. Their MFD is therefore an estimated aggregate boundary, not directly observed vehicle accumulation or microscopic trajectories. The paper acknowledges a mostly European sample, missing intersection-design/transit-priority information and no explicit traffic-control treatment. Its regional networks and 41-city analysis should not be silently equated with the public portal's 40-city release. [Full primary paper, methods and discussion][UP]

**Opinion:** use raw UTD observations as a challenge dataset where rights permit, but do not demand that a simulator reproduce the paper's fitted MFD and then call that independent confirmation of reality. In particular, a Google speed series used to calibrate that reference cannot also be an untouched validation source for the same reference. This warning follows from the published calibration procedure, not from a fresh reanalysis of their data. [Methods][UP]

## Controls, lanes, demand and genuinely independent tests

This matrix is intentionally strict. **Lanes in a simulator or a detector's lane count do not certify surveyed lane centre lines and turn connections. A signal pole layer does not supply phase durations, offsets or actuation logic.** These are opinion-level criteria for accepting a microscopic network, with the specific evidence below. For all UTD-only cities the four inventory fields remain unknown; the portal promises detector geocoding, not operational controller programs or observed OD. [UTD portal][U]

| Candidate | Real signal programs published? | Lane-level road information? | Observed OD / travel survey? | Independent congestion and proposed holdout (opinion) |
|---|---|---|---|---|
| Amsterdam | Not verified for Amsterdam. NDW VLOG exists; >250 Hague installations documented, access through Dexter by the road manager. Do not transfer that count to Amsterdam. An A10 test needs no urban signals. [VLOG][NV], [Dexter docs][DXD] | Measurement-site lane counts and coordinates fetched; full turn geometry unverified. [NS] | NDW documents licensed FCD OD since 2023, for road managers; not a census and not open. [NF] | 134 A10-named routes in the box are all FCD. Fit boundary and ramp Q only; reserve TT and alternate mainline loops. Reject the 605 loop-derived routes from the independent set. [NC], [NT] |
| Madrid | Controller histories not retrieved. Open layers give signalised crossings and signal heads with installation data, not timings. CRTM's model report mentions signal representation; that is modelled. [MS], [MR] | Detector location dataset linked; lane-resolved connectivity not verified. [MD] | **Open trip microdata:** `EDM2018VIAJES` has 222,744 rows with zones `VORIZT1259`/`VDESZT1259`, start and end times, mode, distance and expansion weight; zone layers published. Reuse licence covers commercial use. [EDV], [EDA], [ECL] | No separate probe/ANPR sample verified. Withhold entire corridors and weeks; test O and M30 V as additional, sensor-correlated outcomes. `carga` is not independent. [MD] |
| Melbourne | **Controller sheets for sites across Victoria**, 27 bundles of about 2–3 GB. A sampled sheet gives phase sequence, minimum and maximum greens, yellow, all-red, gap, headway and detector-to-phase maps. Its SCATS page says the values are typical only; real adaptive splits are not published. [MC] | Detector and group maps in the sheets, some as images; whole-network lane topology not verified. [MC] | **Open microdata:** VISTA 2024–25 has 2,485 households and 22,444 stops with weights and 10 jackknife replicates, 32,000+ households since 2012. Geography is council level (LGA), too coarse for routes. [VI], [VE], [VS] | TIRTL speed bins are never fitted. Bluetooth is the arterial TT test once a key exists. Hold out 30% of blocks of SCATS sites. [TI], [BT], [MV] |
| Helsinki | Not verified. | Fintraffic publishes archived Digiroad under CC BY 4.0, but says the Digiroad service ended 2026-09-30. Road centre lines are not lane centre lines; no lane-turn sample verified. [DG] | HSL 2023 survey is randomly invited travel diaries; respondent n not established here. Aalto distributor states separate agreement and academic/noncommercial use for 2012/2018/2023. [HS], [HA] | No independent probe TT sample. Hold out station-days and vehicle-class speed distributions; raw and corrected counts are related, not independent. [FD] |
| Berlin | BeST contains simulated signals; measured operational programs not established. [BE] | BeST lane network is modelled; date/geometry audit needed. [BE] | BeST converts modelled demand; no complete observed OD established. [BE] | Withhold whole detectors and days unused in scenario generation. A published count fit alone is not an independent test. [B], [BE] |
| Zurich | Not verified. | City links detailed detector plans; full road-lane connectivity unverified. [Z] | Raw travel-survey/OD payload not verified. | No separately fetched probe series. Separate measured/imputed observations; withhold locations and periods. [Z] |
| Paris | Not verified. | Georeferenced road-section reference available, not proof of lane turns. [P] | Raw survey/OD payload not verified. | Hold out sections/weeks and O jointly with Q. Separate-probe coverage unverified; do not promote loop-based state labels to independent truth. [P] |
| London / WebTRIS | Not verified. | WebTRIS coordinates, not audited lane network. [WS] | Raw survey/OD payload not verified. | The TfL document names INRIX and iBus for journey times, used in internal dashboards; open histories not verified. Would be independent if it does not reuse fitted loops. [LT] |
| LA and Bay Area | Not verified; freeway control still needs ramps, closures and restrictions. | PeMS includes roadway inventory, no lane-connectivity download verified. [CA] | Raw OD/travel survey not verified here. | Toll-tag data integration is documented, but provenance/exports not retrieved. Hold out districts' sites/days; don't treat imputed V as separately measured speed. [CA] |
| Athens | Not verified; stop-line departures could reveal realised states, which would then be inferred inputs. | Lane inference methodology linked in producer FAQ, not a surveyed network guarantee. [AD] | Tracks reveal within-camera movements, not full-city OD; short tracks require censoring. [AZ] | Hold out entire days and intersections. If trajectories define arrival demand, reserve interior behaviour/exit times and do not fit on them. [AZ] |
| Stockholm | 537 signal installations and 12,150 heads open, with no timings. NVDB junctions: 9,447, of which 748 flagged signalled and 4,134 unknown. No plans found. [SL], [SK] | Open today: turn bans, junctions, bus lanes, width and speed layers. Lane codes per link, including turn lanes, need a free key (`AntalKörfält2`). [SC], [TLA] | RVU 2024: 11,985 responses, 21% response rate, report tables only. No OD microdata. [RV] | Bus positions from 1 Dec 2020 (key) are the only verified dated source separate from detectors. `TravelTimeRoute` is documented as detector-based, so its independence is unproven. Monthly toll totals are a weak cordon check. [KD], [TTR], [TX] |
| Oslo / Norway | Not verified. | Per-lane count metadata; full geometry not verified. [NO] | Raw survey/OD not verified here. | Public API description provides Q only; independent TT not verified. Hold out whole points/weeks; sample query verified, Oslo sample still needed. [NO], [NG] |
| Nashville I-24 | No urban signals within this freeway test scope; ramp/control histories unverified. | Trajectory road-coordinate mapping and lane validation not fetched. | Boundary crossing demand could be extracted from tracks; city OD absent from this verified evidence. | Entire recording days for test; tracking-derived acceleration needs independent error assessment. [I24] |
| InTAS | Authors claim 20 real TLS representations, but operational provenance/exact dates unverified. [IN] | Modelled lane network. [IN] | Raw observed OD not recovered. | Recover measuring-point data and calibration membership before selecting held-out points. [IN] |
| LuST | Static/actuated simulation variants, not established real program recordings. [LU] | Modelled lane network. [LU] | Raw observed OD not recovered. | No independent sample established; integration benchmark only until acquisition. [LU] |
| Cologne | Real signal histories not established. | Simulation network; observational geometry audit outstanding. | Activity-based modelled demand, not established measured OD. | No independent sample established; no reality claim from model outputs. [CO] |

## Why Melbourne is the evidence winner

**Measured, counts:** on Tuesday 20 October 2026 the Victoria-wide file has 119,699 detector rows. Inside a box I chose (lat −38.25 to −37.45, lon 144.55 to 145.55) it has 3,867 sites, of which **3,707 have at least one live detector and 3,428 have at least four**, with a median of 9 live detectors per site. "Live" is my definition: at least 48 positive quarter-hours and no negatives. Of 97,384 rows in the box, only 36,638 are live, 58,145 are zero or negative all day and 3,475 contain negative values. The meaning of the negatives was not documented in what I opened. One detector peaks at 759 vehicles in 15 minutes, which is 3,036 veh/h and needs quality control. [Sample ZIP][MELZ], [signal sites][MSG], [calculation](01-city-review-melbourne.json)

**Measured, independent sensor:** TIRTL devices are infrared loggers, not loops. They publish volume per 15 minutes by site, heading, vehicle class and speed bin. The site list has 406 entries, 382 in the box; by name, about 283 are freeway-like and 123 are not. 278 sites appear in one sampled day. This is the only open congestion measure found that combines no login, a dated archive and different hardware. It measures point speed, not travel time, and mostly on freeways. [TIRTL][TI], [sites][TIS]

**Measured, signals:** I range-read one sheet bundle of 2,057,942,635 bytes and 8,228 members, without downloading it. Site 100's sheet gives phase sequence AB, minimum green 10 and 5 s, maximum extension 40 and 15 s, yellow 4.5 and 3.0 s, all-red 1.5 and 2.0 s, gaps and detector functions. It is dated 2005, so it may be stale. Another sample, site 2's PDF, opens with an unrelated internal email and staff contact details and has no text layer. Sheets therefore need OCR and triage, and raw sheets should not be republished. How many of the 5,066 listed sites have usable current sheets is unknown. [Sheets][MC], [one bundle][MOP]

**Limits:** SCATS sees stop lines, so queued demand is censored by capacity. Green splits vary adaptively and are not public. VISTA OD is council level. Bluetooth (CC BY-NC) and freeway TT return 401 without a key and serve latest values, so history must be collected from the day the key exists. Melbourne also drives on the left and the engine has no left-hand support, so this is a port, not a data swap. [Bluetooth][BT], [freeway TT][FW], [VISTA notes][VE]

## The A10 corridor, and what it cannot tell us

**Measured audit:** the TT configuration contains `ABM01_A10_HRL_CP_S102`, named “A10 Noord HRL tussen Coenplein en afrit S102”, equipment `fcd`, period **60 s**, endpoints (52.424908,4.894054) and (52.395519,4.844007). The separately retrieved TT feed contains the same ID, timestamp **2026-10-31T21:57:00Z**, duration **184.1438 s** and type **reconstituted**. A review snapshot at 22:56 gave **185.61 s** with a published "normally expected" time of 202.85 s. This verifies a real, joinable public congestion observable, not a completed validation. The independent sample size is unknown: `numberOfInputValuesUsed` tops out at 100 and 100 is its most common value, so it looks like a percentage, not cars (inference). [Metadata][NC], [TT feed][ND], [calculation](01-city-review-ndw.json)

**Measured/modelled distinction:** NDW says FCD originates in GPS devices, bought under licence from Be-Mobile since March 2017. Each 50 m segment speed averages **the last 15 detected vehicles, looking back up to 30 minutes, weighted to recent ones, and is capped at 120% of the speed limit**. A route time needs at least 60% of its length covered; gaps are filled from neighbouring segments. So the 60 s period is a publication rate, not resolution: shockwave timing will be blurred, more so at low probe volumes, and free-flow speed is clipped. NDW compared FCD with ANPR at procurement but the figures were not on the page I read. Whether Be-Mobile mixes loop data into its speeds is not stated. NDW also publishes loop-derived TT, computed from adjacent loops about 400 m apart, so the independent test must select `fcd` and exclude `lus`. The box contains no ANPR routes. [FCD documentation][NF], [TT documentation][NT]

**Measured coverage:** parsing Rijkswaterstaat site IDs gives 91 and 90 records on the two A10 carriageways over about 32 km, at a median of 0.4 km and p90 of 0.6 km, plus 79 ramp-like `vw` records. Whether every ramp is covered is **not verified**. It decides whether the boundary closes, so check it first. [Point metadata][NS], [calculation](01-city-review-final-checks.json)

**History:** count and speed exports are open through Dexter Open Data without an account, but each needs a name, email and reCAPTCHA: up to 20 locations for 366 days, or the expert export of all locations for 8 days. Dexter's explorer redirects to sign-in, and the historical open-data forms offer vehicle data, not route times. So **route-time history needs a login that NDW grants through its servicedesk**, while route times can be collected openly from now on. The tested collector stores about 156 KB per pass for the box, or about 225 MB per day. Note NDW retires the v2.3 feeds on 9 February 2027; the collector uses v3. [Dexter Open Data][DXO], [expert export][DXE], [standard export][DXA], [Dexter docs][DXD], [portal notice][NI], [collector](scripts/city_review_ndw_collect.py)

**Measured spatial inventory:** the point configuration contains **1,559 site records** in latitude **52.30–52.45° N**, longitude **4.70–5.00° E**, all loops, 1,412 from Rijkswaterstaat. Only 147 are not, and only 6 carry the prefix `GAD02`, whose records name Amsterdam tunnels. **This is a motorway dataset, not an Amsterdam city dataset.** The earlier audit reported zero TT routes in the box because it searched for latitude tags while routes use `posList`; the true figure is 3,642. [NDW coordinates][NS], [calculation](01-city-review-ndw.json)

Even a successful A10 experiment cannot establish urban signal coordination, curbside parking effects, pedestrians, mixed modes, minor-street route choice or full-city OD. Those are excluded mechanisms by design, not evidence that the simulator handles them. This is why Madrid's urban series and Athens' trajectory campaigns are complementary tests, and why freeway evidence must not be marketed as “Amsterdam reproduced”. This scope judgement is opinion based on the dataset scopes above. [NDW][NT], [Madrid][M], [Athens][AE]

### Madrid: the strongest open demand evidence, with an honest claim boundary

**Measured audit:** the downloaded December 2022 ZIP expands to one CSV of **745,284,107 bytes**. Streaming it found **12,512,133 records**, **4,487 distinct point IDs** (4,073 urban, 414 M30/C30), **31 dates**, **12,491,063 `N` quality codes** and **21,070 blank quality codes**. An independent recount in review matched. All 11,304,905 urban rows have zero speed. This is a file inventory, not 12 million independent experiments or a quality certificate. First row: point 1001, M30, 00:00 on 1 December, intensity **3,240 veh/h**, O **9%**, speed **59 km/h**. [Actual ZIP][MZ]

**Measured survey, new in review:** CRTM publishes the 2018 household survey as open files. `EDM2018VIAJES.xlsx` (22,877,595 bytes) has **222,744 trip rows** with origin and destination in **1,259 zones**, start and end times, mode, distance and an expansion weight. Zone geometries are open. CRTM's licence permits commercial and non-commercial reuse. This is by far the finest open OD found for any candidate, and it needs 2018 counts to match; monthly archives for 2018 are listed. It is still a sampled diary, not a census of vehicle trips, and it is eight years old. [Trip file][EDV], [catalogue with zones][EDA], [licence][ECL]

**Measured/modelled:** the October 2023 official schema specifies 15 min integration; divide intensity by four for interval vehicle counts. Negative values mean missing data. Urban `vmed` is not generally observed; speed is provided for M30. `carga` is a synthetic function of intensity/occupancy and configurable coefficients, so it cannot independently validate a count-calibrated model. Quality and integration-count fields must survive ingestion. [Schema][MD]

**Opinion: use Madrid when a retrospective full urban experiment must start now.** Fit demand on a subset of corridors/weeks; freeze those choices; evaluate held-out Q/O, M30 speed, the timing and persistence of congestion, and out-of-sample days. This supplies real falsification for aggregate outputs, but not independent-modal confirmation or microscopic trajectory validity. Use 2018 survey-informed demand only with matching 2018 observations/geometry, or quantify the date mismatch explicitly. CRTM's modelling report is a source for how survey evidence became a model, not an observed OD census. [Archive][M], [CRTM report][MR]

### Can Stockholm become primary?

**Measured, the layer this report missed:** `od_gis:Arstrafik` is anonymous and all **63,047 features are `Uppmätt`**. They come from **4,053 site IDs**, with period labels ending 1991 to 2026. Each carries 24 hourly flows for all and heavy vehicles, direction, `antal_mätdygn`, an NVDB key, and on 49% of records mean, median and p85 speed. The city says the averages are computed from its own measurements and in some cases Trafikverket's. The busiest long-running records are Essingeleden at Kristineberg, at about 53,000–55,000 vehicles per direction per day and 231–235 measurement days a year. One Nynäsvägen record shows 91,600 on 3 days, so quality screening is needed. [Full layer][SAR], [method notes][SAV], [calculation](01-city-review-stockholm-arstrafik2.json)

| Label year | Sites | Directional records | ≥5 days | ≥100 days | ≥5,000 veh/day |
|---|---:|---:|---:|---:|---:|
| 2023 | 420 | 734 | 534 | 99 | 259 |
| 2024 | 522 | 933 | 659 | 80 | 312 |
| 2025 | 509 | 912 | 681 | 103 | 284 |

**Its limits, measured:** the median site-year rests on **5 measurement days**. Hourly values are annual-average weekday figures, not dated series. Period fields are templates: a 2026 record ends on `2026-12-20`, a date still in the future, so sampling days cannot be recovered and 2026 is partial. Speed is one daily figure, not by hour, and it is null at the Essingeleden sites. There are also no lanes. On directional records with at least 5,000 vehicles a day, the largest hour holds 7.4%, 9.2% and 11.6% of the day at the 10th, 50th and 90th percentiles, a real profile target that one synthetic curve will not meet.

**Measured, what our scenario used instead:** `scripts/stockholm/map_counts.py:41` reads `Trafikflode_Motorfordon`. All 16,698 features there are `Skattad trafik`, and most were updated in 2016. A crude join to 2024–25 measured two-way totals, same street name and midpoints within 80 m, matched 509 site-years. Measured over estimated has a **median of 0.97, an interquartile range of 0.75–1.19, and a 5th–95th percentile range of 0.19–3.60**. Only **26.1% are within ±10%, 38.9% are off by more than 30%**, and the summed total is 0.873. Bad matches inflate the tails, so treat these as bounds on scale, not a survey of error. But the conclusion is direct: fitting street-level demand to this layer fits a decade-old estimate, and newer measurements exist for free. [Calculation](01-city-review-stockholm-arstrafik3.json)

**What can be done for Stockholm:**

| Access | Data | Test it allows | What it cannot do |
|---|---|---|---|
| **Today, no login** | `Arstrafik`; `Signallykta` (12,150 heads, 537 installations); `NVDB_Korsning` (9,447, 748 signalled, 4,134 unknown); turn bans and bus lanes; monthly toll totals (September 2026: 8,858,400 passages over 22 days, about 402,700 a day); RVU tables (11,985 responses, 21% response rate); OSM; TomTom's 2025 metro figure of 42.8% (opaque). | Hold out sites and years to falsify link flows, direction split and hourly profile. Check cordon scale. Audit signal locations. **Executable now**: split frozen in [the hold-out file](01-city-review-stockholm-holdout.csv). | No dated days, per-lane flow, peak speed, travel time, queues or breakdown. No signal plans. No OD. |
| **Trafikverket API key** (registration, email check, licence; no fee mentioned) | `TrafficFlow`: site, lane, flow rate, speed, vehicle type, period, quality. `TravelTimeRoute`: route, length, speed, travel time, free-flow time, status. NVDB: `AntalKörfält2` lane codes with turn and bus lanes, `Korsning`, `Stopplikt`, `Väjningsplikt`, `Betalstation`, `Trafik`. CC0. | Dated per-lane flow and speed where sites exist, such as breakdown and recovery on E4/Essingeleden, **from the day collection starts**. Real lane counts, replacing OSM guesses. | Coverage and retention are unknown until tested. **Live only is my working assumption**; the API is described as real time. `TravelTimeRoute` says it is computed from detectors, so it is not proven independent of `TrafficFlow`. |
| **Lastkajen account** (email, CC0 licence) | NVDB packages and custom area orders, including history. | Dated network state. | No traffic time series verified there. Its product list is behind login. |
| **Trafiklab key** (not Trafikverket) | KoDa: daily archives of SL `VehiclePositions` from 1 December 2020, static GTFS from February 2020. | **The one verified dated, historical, loop-independent Stockholm source.** Bus running times by hour on mixed-traffic links, for a chosen week, without waiting. | Buses dwell at stops and use bus lanes, so only peak-to-off-peak ratios on mixed-traffic links are usable. No payload tested without a key. |
| **Request to an owner** (only Erik can ask) | MCS archive, per-station toll passages by 15–60 minutes, signal plans from Trafikkontoret, Sampers matrices. | Everything else: the real test of capacity and wave propagation. | Release not verified. MCS radar data exists: [VTI report 969][VTI] compares against it on the E4 north of Stockholm. |

**So, honestly:** today Stockholm can falsify demand, not congestion. With the keys and a few weeks of collection, an E4/Essingeleden corridor becomes a real dated test, with buses as an independent check on urban links only. It still lacks signal plans, which blocks urban junction claims. Melbourne has more of this open today. [TrafficFlow][TFL], [TravelTimeRoute][TTR], [lanes][TLA], [junctions][TKO], [API terms][TAI], [request format][TRQ], [Lastkajen][LKI], [licence setting][LKS], [KoDa][KD], [toll totals][TX], [RVU report][RV], [TomTom][TTI]

**Notices:** the city ended its LvWS API on **2026-10-21**, phased out API keys on **2026-10-07** and said NVDB layers would be removed in autumn 2026. `NVDB_Korsning` still answered on 31 October, so download now. [City notices][SN]

**Opinion: Stockholm promotion gate:** obtain (1) dated 1–5 min Q,V with sensor IDs, coordinates, lane/direction and quality flags, (2) probe or ANPR TT with confirmed separate provenance on congested routes, (3) signal stages, offsets, timing plans and actuation rules for the same dates, (4) lane/turn topology for the same roadworks state, and (5) driver-only OD constraints. Choose held-out corridors and dates *before* fitting.

## Validation design to prevent circular success (opinion)

1. Define the observation operator before fitting: passage counts, lane or multi-lane denominator, spot versus space-mean speed, occupancy detector length, TT route/cohort, timestamp start/end, units and timezone. Madrid's 15 min intensity and Paris's end-of-hour timestamp show concrete reasons. [Madrid][MD], [Paris][P]
2. Partition by whole places and contiguous days, not random rows. Example project choice: training weeks 1–2, development week 3, locked week 4 plus held-out corridors. Record upstream scenario-calibration inputs; a new copy of old fitted counts is not an independent test.
3. Fit demand on boundary counts and survey constraints; fit behaviour on a different city/campaign subset; provide signals as measured inputs rather than parameters adjusted until queue results look right. Freeze routes, signals and parameters before opening the final outcome series.
4. Amsterdam: reserve probe TT and internal speed entirely; Madrid: reserve corridor Q/O/M30 speed and explicitly label correlated sensing. Athens/I-24: hold out days, use boundary tracks as inputs, internal trajectories as outcomes, and account for truncated tracks. Never call outputs independent merely because columns have different names.
5. Report uncertainty by independent days/routes, not millions of autocorrelated rows; publish missingness and coverage, errors by congestion state, unfinished trips and excluded sensors. Compare each simulator with observations. SUMO agreement remains a software-baseline result.

## Reproduction and retrieval limits

The original audit also produced an [evidence-score chart](fig/01-city-evidence.html). It shows the scores before review and visualises a judgement rubric, not observed simulator accuracy.

The original audit's downloads are under a newly created, initially empty timestamp directory inside `/home/erikf/projects/personal/cars-data/truth/city-ground-truth/`. The review's are in `/home/erikf/projects/personal/cars-data/truth/city/review-20261031T221426Z/`, about 730 MB, listed in the [review ledger](01-city-review-download-log.md). Responses are treated as untrusted bytes, never executed. Data parsing used Python isolated mode, serial processing and <1.8 GiB address-space caps; no GPU. The two larger ZIPs were streamed without extraction. Total on-disk responses/headers/manifests are about **230 MB**, well below 5 GB. One archive was still finishing while the first byte inventory was produced; the ledger's final total is authoritative.

From repository root, these exact acquisition invocations were tested:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 nix develop --command python3 -I research/truth/scripts/city_fetch.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 nix develop --command python3 -I research/truth/scripts/city_fetch.py research/truth/scripts/city_more.json
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 nix develop --command python3 -I research/truth/scripts/city_fetch.py research/truth/scripts/city_last.json
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 nix develop --command python3 -I research/truth/scripts/city_fetch.py research/truth/scripts/city_extra.json
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 nix develop --command python3 -I research/truth/scripts/city_fetch.py research/truth/scripts/city_metadata.json
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 nix develop --command python3 -I research/truth/scripts/city_fetch.py research/truth/scripts/city_norway.json
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 nix develop --command python3 -I research/truth/scripts/city_fetch.py research/truth/scripts/city_norway_volume.json
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 nix develop --command python3 -I research/truth/scripts/city_audit.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 nix develop --command python3 -I research/truth/scripts/city_finish.py
```

Each invocation creates a fresh directory. Do not repeat indefinitely under a fixed cumulative budget. Curl caps are 12 MB by default and 180 MB for the two explicitly marked large files; no multi-GB archive is silently fetched. The [download ledger](01-city-download-log.md) records **the actual curl command for every request**, including outputs and SHA-256. HTTP 200 HTML is distinguished from observations. No curl `-k` was used. Finland initially rejected requests without gzip; adding `--compressed` fixed metadata/raw acquisition, while guessed station IDs 1 and 101 returned 404 for current readings. The successful raw historical CSV is separate evidence, not an assertion those current IDs work.

Unsuccessful/uncompleted payload verification is explicit: all UTD city files (signup; ETH research-collection alternate record also returned 403), PeMS (account), InTAS/LuST/Cologne raw observations (not recovered), Athens trajectories (15.8 GB ZIP or form; neither used), I-24 (TLS/DNS), UK daily report (empty response), and all cities' claimed complete operational signal archives. Norway's initial GET failures were resolved by using a read-only JSON GraphQL POST, not an account or application form. Existing source limitations were recorded rather than bypassed.

## Actions only Erik can take, if he chooses those datasets

No action is required for the Madrid archive and EDM2018, Stockholm's `Arstrafik`, Melbourne's counts, TIRTL, VISTA and signal sheets, or anonymous NDW snapshots. The following were **not done**:

* **Trafikverket API (Stockholm):** register on Datautbytesportalen, accept the licence, verify the email, and copy the key. This unlocks `TrafficFlow`, `TravelTimeRoute` and NVDB lane data. [Onboarding][TAI]
* **Lastkajen (Stockholm):** register with an email and accept the licence, for NVDB packages and area orders. [Lastkajen][LKI]
* **Trafiklab (Stockholm):** get a key for KoDa bus positions. [KoDa][KD]
* **Victoria DTP (Melbourne):** get the `KeyId` API key for Bluetooth and freeway travel times. Bluetooth is CC BY-NC, so check before any commercial use. [Bluetooth][BT]
* **NDW Dexter Open Data (Amsterdam):** enter a name and email and solve a reCAPTCHA per export. No account, but a human has to do it. [Expert export][DXE]
* **Stockholm owners:** ask Trafikverket for the MCS archive, Transportstyrelsen for per-station passages by 15–60 minutes, Trafikkontoret for signal plans, and Trafikverket for Sampers matrices. Release is not guaranteed.

* **UTD19:** enter name, email, organisation; accept academic/noncommercial conditions and attribution requirements; obtain the emailed download link. A research signup is not permission for commercial reuse. [Exact form/terms][U]
* **PeMS:** apply for the free account and wait for approval (Caltrans says normally 1–2 business days); then check terms and obtain district station metadata plus original quality/imputation fields. [Official instructions][CA]
* **NDW route-time history and raw products:** request the appropriate Dexter/mijnNDW access from its servicedesk, describing required route-time, metadata and signal-log dates. Loop history does not need this. Approval and raw FCD eligibility for an independent developer are **not guaranteed**. That is contact with another party and was not performed. [Dexter access][NX], [FCD restrictions][NF]
* **Athens:** for a bounded website subset, choose drone/date/time and accept terms personally; alternatively authorise a later bounded ZIP-range/subset acquisition. Resolve the website's conflicting BY versus BY-NC wording against the selected record before redistribution. No form was submitted. [Download interface][AD], [record][AZ]
* **HSL travel diaries:** arrange the separate data agreement if needed; access is described for Aalto students/staff and academic/noncommercial use. No entitlement for Erik was established. [Distributor terms][HA]

## Primary sources opened in this session

References apply to the linked claims and tables above. Data-file observations were read locally through Python `-I` after curl retrieval; metadata and papers were opened through web retrieval or curl. No secondary dataset mirror is treated as ground truth.

[VTI]: https://trafikverket.diva-portal.org/smash/get/diva2%3A1699487/FULLTEXT01.pdf
[SAR]: https://openstreetgs.stockholm.se/geoservice/api/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=od_gis:Arstrafik&outputFormat=application/json&srsName=EPSG:4326
[SAV]: https://openstreetgs.stockholm.se/Home/Visualisering/AMVD
[SK]: https://openstreetgs.stockholm.se/geoservice/api/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=od_gis:NVDB_Korsning&outputFormat=application/json&srsName=EPSG:4326
[SL]: https://openstreetgs.stockholm.se/geoservice/api/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=od_gis:Signallykta&maxFeatures=2&outputFormat=application/json
[TFL]: https://data.trafikverket.se/apb/prod/schematree/Road.TrafficInfo.TrafficFlow/1.5/data?annotations=true
[TTR]: https://data.trafikverket.se/apb/prod/schematree/Road.TrafficInfo.TravelTimeRoute/1.6/data?annotations=true
[TLA]: https://data.trafikverket.se/apb/prod/schematree/V%C3%A4gdata.NVDB_DK_O.AntalK%C3%B6rf%C3%A4lt2/1.2/data?annotations=true
[TKO]: https://data.trafikverket.se/apb/prod/schematree/V%C3%A4gdata.NVDB_DK_O.Korsning/1.2/data?annotations=true
[TAI]: https://www.trafikverket.se/e-tjanster/trafikverkets-oppna-api-for-trafikinformation/
[TRQ]: https://data.trafikverket.se/documentation/datacache/the-request
[LKI]: https://www.trafikverket.se/e-tjanster/lastkajen--sveriges-vag--och-jarnvagsdata/
[LKS]: https://lastkajen.trafikverket.se/api/Setting/GetPublicSettings
[KD]: https://www.trafiklab.se/api/our-apis/koda/
[TX]: https://www.transportstyrelsen.se/sv/om-oss/statistik-och-analys/statistik-inom-vagtrafik/trangselskatt-statistik/stockholm/
[RV]: https://www.regionstockholm.se/496707/contentassets/d423312f6696457c9a4e659d501a86e0/resvaneundersokning_for_stockholmsregionen_2024.pdf
[TTI]: https://www.tomtom.com/traffic-index/city/stockholm/
[TI]: https://opendata.transport.vic.gov.au/api/3/action/package_search?q=traffic+volume&rows=20
[TIS]: https://opendata.transport.vic.gov.au/dataset/e2d78fb5-e16d-43b9-bcdc-607d9b4855f5/resource/1f685833-24fd-4eb0-af11-2e7cfc94da74/download/tirtl_sites.csv
[BT]: https://opendata.transport.vic.gov.au/api/3/action/package_search?q=bluetooth&rows=20
[FW]: https://opendata.transport.vic.gov.au/dataset/e36f8371-dd4c-4e66-9102-938a52aefcbc/resource/4dfc6821-0170-4848-ae98-96b57608c192/download/freeway_travel_time_traffic.openapi.json
[VI]: https://opendata.transport.vic.gov.au/api/3/action/package_search?q=VISTA+travel+survey&rows=20
[VE]: https://opendata.transport.vic.gov.au/dataset/174fbf40-bef0-434a-8af0-891c7f3d2323/resource/928cf922-b37d-4111-b2fb-fde0838b8620/download/vista_2021_2026_explanatory_document-updated-2026.pdf
[VS]: https://opendata.transport.vic.gov.au/dataset/174fbf40-bef0-434a-8af0-891c7f3d2323/resource/aabd62ce-980f-43ce-871a-bdb36dfeb547/download/stops_vista_2024_2025.csv
[MSG]: https://opendata.transport.vic.gov.au/dataset/923af458-363d-469f-bc5e-84746a80b9a2/resource/1036a318-8867-4dc6-bd84-fc3bcd6cbdb9/download/victorian_traffic_signals.csv
[MOP]: https://opendata.transport.vic.gov.au/dataset/48ec6c0a-994e-4f27-b3b8-bd7ffa86deda/resource/3d5b2b43-4c28-4e7a-b268-761545755a9c/download/0-249.zip
[EDV]: https://www.arcgis.com/sharing/rest/content/items/6afd4db8175d4902ada0803f08ccf50e/data
[EDA]: https://data-crtm.opendata.arcgis.com/api/v3/datasets?q=EDM2018
[ECL]: https://www.crtm.es/licencia-de-uso
[MS]: https://datos.madrid.es/api/3/action/package_search?q=trafico&rows=30
[NY]: https://data.ny.gov/resource/t6yz-b64h.json?$limit=5
[NYM]: https://data.ny.gov/api/views/t6yz-b64h
[NYS]: https://data.cityofnewyork.us/resource/i4gi-tjb9.json?$limit=3
[DXO]: https://dexter.ndw.nu/opendata/overview
[DXE]: https://dexter.ndw.nu/opendata/expert-avg
[DXA]: https://dexter.ndw.nu/opendata/avg
[DXD]: https://docs.ndw.nu/handleidingen/DEXTER/
[NI]: https://opendata.ndw.nu/

[U]: https://utd19.ethz.ch/
[UP]: https://pmc.ncbi.nlm.nih.gov/articles/PMC6841661/
[M]: https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico
[MZ]: https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico/resource/208627-0-transporte-ptomedida-historico-zip/download/208627-0-transporte-ptomedida-historico-zip.zip
[MD]: https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico/resource/208627-81-transporte-ptomedida-historico/download/208627-81-transporte-ptomedida-historico.pdf
[ML]: https://informo.madrid.es/informo/tmadrid/pm.xml
[MR]: https://www.crtm.es/media/987213/edm18_doc7_model_v03_01.pdf
[NT]: https://docs.ndw.nu/producten/reistijden/
[NF]: https://docs.ndw.nu/producten/fcd/
[NC]: https://opendata.ndw.nu/reistijden_configuratie_meetlocaties.xml.gz
[NS]: https://opendata.ndw.nu/snelheden_en_intensiteiten_configuratie_meetlocaties.xml.gz
[ND]: https://opendata.ndw.nu/traveltime.xml.gz
[NL]: https://docs.ndw.nu/algemeen/data-gebruiksvoorwaarden/
[NX]: https://www.ndw.nu/applicaties/dexter
[NV]: https://docs.ndw.nu/producten/VLOG/
[MV]: https://opendata.transport.vic.gov.au/dataset/traffic-signal-volume-data
[MC]: https://opendata.transport.vic.gov.au/dataset/traffic-signal-configuration-data-sheets
[MELZ]: https://opendata.transport.vic.gov.au/dataset/331b846b-1e18-415f-a3f3-ce4198d86c82/resource/001ace40-280b-462d-b580-7a79e70185fb/download/traffic_signal_volume_data_october_2026.zip
[FR]: https://tie.digitraffic.fi/api/tms/v1/history/raw/lamraw_101_24_1.csv
[FD]: https://www.digitraffic.fi/en/road-traffic/lam/
[FL]: https://www.digitraffic.fi/en/terms-of-service/
[FS]: https://tie.digitraffic.fi/api/tms/v1/stations
[DG]: https://www.fintraffic.fi/fi/digitaalisetpalvelut-4?language_content_entity=en
[HS]: https://www.hsl.fi/en/hsl/research-and-surveys/travelsurvey2023
[HA]: https://datahub.aalto.fi/en/data-sources/hsl-travel-survey
[B]: https://api.viz.berlin.de/daten/verkehrsdetektion
[BZ]: https://mdhopendata.blob.core.windows.net/verkehrsdetektion/2015/alte_qualitaetssicherung/Fahrstreifendetektoren/det_val_hr_2015_01.csv.gz
[BE]: https://github.com/mosaic-addons/best-scenario
[Z]: https://data.stadt-zuerich.ch/dataset/sid_dav_verkehrszaehlung_miv_od2031
[ZJ]: https://data.stadt-zuerich.ch/api/3/action/package_show?id=sid_dav_verkehrszaehlung_miv_od2031
[ZZ]: https://data.stadt-zuerich.ch/dataset/sid_dav_verkehrszaehlung_miv_od2031/download/sid_dav_verkehrszaehlung_miv_OD2031_2012.csv
[P]: https://opendata.paris.fr/explore/dataset/comptages-routiers-permanents/
[PJ]: https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/comptages-routiers-permanents
[PS]: https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/comptages-routiers-permanents/records?where=q%20is%20not%20null&limit=5
[W]: https://webtris.highwaysengland.co.uk/
[WS]: https://webtris.highwaysengland.co.uk/api/v1.0/sites
[LT]: https://content.tfl.gov.uk/stig-record-of-decision-traffic-monitoring.pdf
[CA]: https://dot.ca.gov/programs/traffic-operations/mpr/pems-source
[CP]: https://pems.dot.ca.gov/
[AE]: https://open-traffic.epfl.ch/
[AD]: https://open-traffic.epfl.ch/index.php/downloads/
[AZ]: https://zenodo.org/records/10491409
[SH]: https://openstreetgs.stockholm.se/home/
[SN]: https://openstreetgs.stockholm.se/Home/News
[SC]: https://openstreetgs.stockholm.se/geoservice/api/wfs?service=WFS&request=GetCapabilities
[SW]: https://openstreetgs.stockholm.se/geoservice/api/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=od_gis:Trafikflode_Motorfordon&maxFeatures=3&outputFormat=application/json
[SR]: https://www.regionstockholm.se/dokument/kollektivtrafik/rapport/2025/resvaneundersokning-for-stockholms-lan-2024/
[NO]: https://dataut.vegvesen.no/dataset/trafikkdata/resource/968a10a7-f704-4cd7-9795-de69e8cad2bc
[NG]: https://trafikkdata-api.atlas.vegvesen.no/
[I24]: https://lab-work.github.io/blog/I24M-data/
[IN]: https://raw.githubusercontent.com/silaslobo/InTAS/master/README.md
[LU]: https://raw.githubusercontent.com/lcodeca/LuSTScenario/master/README.md
[CO]: https://sumo.dlr.de/docs/Data/Scenarios/TAPASCologne.html

## Reviewed by Opus

Reviewed 31 October to 1 November 2026, against sources opened in this session: 146 logged requests plus browser reads, about 730 MB, listed in the [review ledger](01-city-review-download-log.md). Nothing was submitted to any form and no account was created. No simulation was run. Grades: **measured** means read from a retrieved file or a publisher's own document; **modelled** and **opinion** as defined above.

### What held

* **Madrid:** 12,512,133 rows, 4,487 IDs, 31 dates, quality codes, `carga` is modelled, divide intensity by four. Recounted independently (measured). [ZIP][MZ], [schema][MD]
* **Berlin:** 369,013 rows, 502 detector IDs, dl-de-by-2.0, 2025 revision notice (measured). [Sample][BZ], [index][B]
* **Finland:** 521 station records, 506 gathering and 15 temporarily removed, raw files since December 2021, CC BY 4.0, Digiroad ended 30.9.2026 (measured). [Stations][FS], [docs][FD], [Digiroad][DG]
* **NDW:** CC0 default, 20,598 and 67,674 site records, the A10 route is `fcd` and `reconstituted` (measured). [Terms][NL], [TT metadata][NC]
* **Stockholm's estimated layer:** the sibling report's census of 16,698 `Skattad trafik` features reproduced (measured). [WFS][SW]
* **Others:** Paris ODbL and end-of-hour stamps; Zurich CCZero; WebTRIS 20,076 sites and its pause notice; pNEUMA's conflicting licences and 15.76 GB file; PeMS account terms; InTAS's 24 points, 20 TLS and NRMSE 0.33 (the authors' claim, modelled); LuST's SUMO 0.26 caveat; Cologne's terms; I-24's TLS failure; Norway's GraphQL POST, first hour 79 vehicles; UTD19's 40 cities, and the paper's 41 cities, 107 networks and Google calibration on 1,000 OD pairs.

### What was wrong, now corrected above

1. **Stockholm's verdict rested on a missed layer.** The report sampled three estimated features and said genuine observations were not established. `od_gis:Arstrafik` has 63,047 measured records from 4,053 sites, anonymously. The sibling report's "count source entirely estimated" is true only of the layer our scenario used. [Årstrafik][SAR]
2. **Amsterdam was ranked first with an overstated claim.** It is a motorway dataset, since all 1,559 sites are loops and 1,412 are Rijkswaterstaat. The 60 s FCD period hides smoothing over the last 15 vehicles and up to 30 minutes, plus a cap at 120% of the limit. [FCD][NF]
3. **NDW history was described as a servicedesk request.** Counts and speeds are open through Dexter Open Data with name, email and reCAPTCHA. Route-time history does need a login. [Dexter Open Data][DXO]
4. **A script bug hid Amsterdam's routes.** The audit showed zero TT records in the box because routes use `posList`. There are 3,642: 3,037 FCD, 605 loop, 0 ANPR.
5. **Melbourne was underrated.** "No V/O/TT established" and "survey not verified" were both wrong: TIRTL, Bluetooth, freeway TT and VISTA are published. The sheets were dismissed as unfetched but can be range-read. It also has data problems the report missed: 60% of detector rows in the box are zero or negative on a sampled Tuesday. [TIRTL][TI], [VISTA][VI]
6. **Madrid's survey was marked unverified.** Trip microdata for 222,744 trips over 1,259 zones is open, with a licence covering commercial use. [Trip file][EDV], [licence][ECL]
7. **The London claim was unsupported.** The TfL document does not describe LCAP ANPR journey times. ANPR and LCAP appear only in its glossary, and its journey-time sources are INRIX and iBus. [TfL][LT]
8. **RVU detail was thin.** The exact figure is 11,985 responses with a 21% response rate, in a report whose earlier cited PDF URL now returns 404. [RVU][RV]
9. **Stale or missing Stockholm facts.** Trafikverket's onboarding, CC0 licence, the schemas of `TrafficFlow` and `TravelTimeRoute`, Lastkajen's terms and KoDa were all absent. They are now in the Stockholm table.

### What remains unknown

* **Stockholm:** `TrafficFlow` site coverage and retention; whether `TravelTimeRoute` shares detectors with `TrafficFlow`, which decides whether it is independent; what Lastkajen lists behind login; whether a Trafiklab or Trafikverket key has any cost; the exact reuse terms for `Arstrafik`; whether owners would release MCS, per-station tolls or signal plans.
* **Melbourne:** Bluetooth link count, coverage and any archive; meaning of negative SCATS values; share of sheets that are current and parseable; lane topology; real green splits.
* **Amsterdam:** whether every A10 ramp has a working detector; whether Be-Mobile speeds include loop data; NDW's published FCD-versus-ANPR error figures; whether Erik would be granted a route-time login.
* **Madrid:** any open congestion measure separate from its loops; lane topology; signal timings.
* **New York:** only samples were read. OD, lanes and signals were not audited.
* **All:** no peak congestion has been observed here. Every live sample was taken at night on 31 October. No simulator has been compared with any of this.

### Recommendation (opinion)

1. **Melbourne has the strongest evidence.** If the question is which city could best prove the simulator true to life, it is Melbourne, and Stockholm does not beat it today.
2. **Run the Stockholm count test first anyway.** It needs no new data or engine work, and our scenario has never seen these measurements. It will probably be the fastest honest result available.
3. **Start the A10 collector now.** It is the cheapest real test of congestion dynamics and needs no signals. Route times missed today can only be recovered later through an NDW login.
4. **Get the Stockholm keys.** They cost a few minutes and start the clock on dated data. Promote Stockholm only if `TrafficFlow` proves to cover the E4/Essingeleden and a travel-time source proves separate.
5. **Do Melbourne after left-hand support.** Use Madrid's EDM2018 as the demand-side test of OD methods, not as a congestion test.

### Data plan

**Anonymous, about 1 GB (Stockholm, Melbourne, Madrid).** It creates a new empty directory and never executes anything. Each URL was opened or header-checked in review, except `NVDB_Forbjuden_svang`, which is listed in the capabilities but was not fetched. WFS endpoints answer 405 to HEAD but worked on GET.

```bash
nix develop --command python3 -I research/truth/scripts/city_review_fetch.py research/truth/scripts/city_review_plan.json
```

**Stockholm hold-out, already frozen.** Rerun only to reproduce it; do not change the seed after any fit.

```bash
nix develop --command python3 -I research/truth/scripts/city_review_split.py <run_dir>/sthlm-arstrafik.body research/truth/01-city-review-stockholm-holdout.csv
```

**A10 collector.** One pass tested. It is not running. Start it through `heavy` per AGENTS.md, for 28 days, about 6 GB. Checkout paths on the homelab were not tested.

```bash
heavy -- nix develop --command python3 -I research/truth/scripts/city_review_ndw_collect.py /home/erikf/projects/personal/cars-data/truth/city/ndw-a10 0
```

**One Melbourne signal bundle, range-read.** Tested.

```bash
nix develop --command python3 -I research/truth/scripts/city_review_rangezip.py "https://opendata.transport.vic.gov.au/dataset/48ec6c0a-994e-4f27-b3b8-bd7ffa86deda/resource/3d5b2b43-4c28-4e7a-b268-761545755a9c/download/0-249.zip" <new_empty_dir> '0-249/01[0-9][0-9]_files/sheet0*(1[0-9]|[0-9])\.htm$' 200
```

**After Erik gets keys. Written from the published docs and untested, because no key exists yet.**

```bash
curl -s -H 'Content-Type: text/xml' -d "<REQUEST><LOGIN authenticationkey=\"$TRV_KEY\"/><QUERY objecttype=\"TrafficFlow\" namespace=\"Road.TrafficInfo\" schemaversion=\"1.5\" limit=\"1000\"><FILTER><EQ name=\"CountyNo\" value=\"1\"/></FILTER></QUERY></REQUEST>" https://api.trafikinfo.trafikverket.se/v2/data.json
curl -s -H 'Content-Type: text/xml' -d "<REQUEST><LOGIN authenticationkey=\"$TRV_KEY\"/><QUERY objecttype=\"TravelTimeRoute\" namespace=\"Road.TrafficInfo\" schemaversion=\"1.6\" limit=\"1000\"><FILTER><EQ name=\"CountyNo\" value=\"1\"/></FILTER></QUERY></REQUEST>" https://api.trafikinfo.trafikverket.se/v2/data.json
curl -s -o sl-vp-2025-10-07.7z "https://api.koda.trafiklab.se/KoDa/api/v2/gtfs-rt/sl/VehiclePositions?date=2025-10-07&key=$TRAFIKLAB_KEY"  # HTTP 202 means retry every 30 s
curl -s -H "KeyId: $VIC_KEY" https://api.opendata.transport.vic.gov.au/opendata/roads/bluetooth-travel-time/v1/links
```

**Which sets calibrate and which are held out (opinion).** Freeze these before fitting. Compare within the same observation operator: for FCD, run NDW's last-15-vehicles, 30-minute, 120%-cap rule over a simulated probe sample before comparing. SUMO runs are baselines only.

| Test | Calibrate on | Hold out, never fit | Excluded |
|---|---|---|---|
| **Stockholm, counts (now)** | `calibrate` sites, 2023–24 (461 sites), hourly direction flows. RVU tables as soft constraints. | `holdout_space` sites: 260 of 847, whole blocks out of 60, 14 with 100+ days, not fitted in any year. All 2025 values at every site. Monthly toll totals for 2025. | `Trafikflode_Motorfordon` as validation, 2026 (partial), records under 5 days, TomTom. |
| **Stockholm, dynamics (keys)** | First 2 weeks of `TrafficFlow` at corridor boundaries and ramps; NVDB lanes. | Week 4 and alternate internal sites. KoDa bus running-time ratios on mixed-traffic links. `TravelTimeRoute` only if shown separate. | Bus-lane links; any TT built from the fitted detectors. |
| **A10, dynamics** | Ramp and boundary loop flows, weeks 1–2, Tuesday–Thursday. Week 3 for development. | Week 4; alternate mainline loops at every other position; every `fcd` route time, all four weeks. | 605 `lus` routes, as they derive from the loops; `normallyExpectedTravelTime`, as it is a modelled baseline. |
| **Melbourne, city** | SCATS September 2026 at 70% of ~2 km blocks; VISTA 2022–25 for time of day and trip length; signal sheets as inputs. | SCATS at 30% of blocks, and all of October 2026. TIRTL speed bins. Bluetooth TT once collected. | Non-live detectors; adaptive splits as if they were known. |
| **Madrid, demand** | EDM2018 OD; October 2018 urban Q at 70% of blocks. | November 2018 and 30% of blocks: Q and O. M30/C30 speed, labelled loop-correlated. | `carga`. |

**Pass criteria.** Use the preregistered targets in [the Stockholm report](02-stockholm-why-overloaded.md) as a starting point (GEH, screenline and travel-time bands). They are opinion, not standards. Report error per independent day and site, and publish failures.

### What only Erik can do

1. Register for the Trafikverket API, Lastkajen, Trafiklab and Victoria's open-data API, then give agents the keys through a secure route.
2. Decide whether to start the 28-day A10 collector, and solve the reCAPTCHA for any Dexter Open Data export.
3. Decide whether to ask owners for MCS, per-station toll passages, signal plans and Sampers matrices, and whether to ask NDW for route-time history. Those are contacts with other people, so this review sent nothing. [Sampers access][SMP]
4. Decide whether commercial use is planned. Bluetooth is CC BY-NC, and UTD19 is academic and non-commercial.

[SMP]: https://bransch.trafikverket.se/tjanster/system-och-verktyg/Prognos--och-analysverktyg/Sampers/
