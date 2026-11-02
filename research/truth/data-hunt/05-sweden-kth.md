# 05: Sweden, and what an Erik at KTH can get

Checked 2026-11-02. Nobody was contacted. Every draft below is for Erik to send himself.

## The answer

The data Erik suspected exists does exist, and most of it sits at Swedish public bodies.

The best find is one sentence in a Trafikverket report. Stockholm's toll stations log **passages per lane, per minute, around the clock, at every station**. Transportstyrelsen also holds camera passages per station, with vehicle type and the **first three digits of the owner's postcode**. Neither is public, but they are extracts that were already delivered for a named report, so they are a good fit for a records request.

The second find is a real GPS trip dataset for Stockholm. Trafikverket's project bought **599,271 INRIX trips with 48 million raw GPS points**, from 16 September to 21 October 2019, covering about 1–1.5% of traffic. Linköping University was still using it in 2025. The licence will probably block a copy of the raw points, so ask for derived tables or work with them.

The third is that Sweden's probe supplier for Trafikverket is INRIX, not TomTom. It feeds a travel-time database called STRESS, with 5-minute values around the clock. Earlier reports didn't name STRESS.

The one thing open today is Chalmers' FlowSense, a relative flow estimate for all 204,032 Stockholm road segments. I downloaded it and tested it. It ranks streets moderately well (Spearman 0.62) but a single street can be off by a factor of about 2.7, and it has no time of day. Use it as a network-wide check, not as truth.

The KTH taxi data is real and KTH says it stores it, but nobody has said it can be shared, and I'd rank it below the items above.

## Ranked

Grades: MEASURED, PROVIDER CLAIM, MODELLED, UNVERIFIED. "Opened" means I read the source itself.

| # | Source | Holder | Needs | Grade | How to get it | Cost |
|---|---|---|---|---|---|---|
| 1 | Toll-station laser counts: lane, minute, 24 h | Trafikverket or WSP (holder inferred) | Congestion, demand | MEASURED, not seen | Records request, draft 1 | Probably free or small |
| 2 | Toll camera passages: station, type, 3-digit postcode | Transportstyrelsen | Demand | MEASURED, not seen | Records request, draft 2 | Probably free or small |
| 3 | Signal plans | Stockholm Trafikkontoret | Signals | Not seen | Records request, draft 3 | Depends on the city's fees |
| 4 | STRESS travel times, 5-minute; MCS radar | Trafikverket; copies at KTH | Congestion | MEASURED and PROVIDER CLAIM | Draft 1, draft 4 | Probably free or small |
| 5 | INRIX trips with waypoints, autumn 2019 | LiU, Ramboll, perhaps Trafikverket | Routes, speeds, some demand | MEASURED, validated | Collaboration, draft 5; terms in draft 6 | Unknown |
| 6 | KTH iMobility Lab: taxi GPS, toll, MCS, bus AVL, ANPR | KTH | Congestion on city streets | MEASURED, not seen | Ask Jenelius, draft 4 | Free if a project is agreed |
| 7 | Telia Crowd Insights OD, hourly | Telia; copies at Trafikanalys, LiU | Demand | MODELLED from measured signals | Draft 7; buying is unpriced | Unknown |
| 8 | FlowSense flows for every segment | Open on Zenodo | Routes, weak | MODELLED, **tested here** | Downloaded | Free |
| 9 | Swedish car movement data: 714 random private cars, 2.5 Hz | Chalmers | Driving behaviour, routes | MEASURED, not seen | Draft 9 | Unknown |
| 10 | RVU survey trip tables | Region Stockholm, Trafikanalys | Demand | MEASURED survey | Drafts 7, 8 | Probably free or small |
| 11 | Sampers and Dynameq base year | Trafikverket | Demand prior | MODELLED | Draft 11 | No fee stated |
| 12 | Commuting between small areas (BEF301/302) | SCB | Demand | MEASURED registers | Paid order, draft 12 | Price list not opened |

The signal plans rank high because report 02 found that a simulation with signal positions and no plans gets worse. Nothing else in this list replaces them.

## Top 3 recommendations

**1. Send draft 1 and draft 2 this week, asking for the toll data.**
- Ask for the delivered extracts behind Trafikverket report 2020:176, then one recent month.
- This gives a dated test that doesn't depend on demand. Per-lane discharge at the cordon, breakdown time at Essingeleden and the shape of the peak can all be checked against `cars` per minute.
- The postcode field gives origins for real crossing vehicles. Nothing we have measures that today.
- It replaces the "ask for 15-minute passages" advice in reports 01 and 02, since far finer data exists.

**2. Send draft 3 with the two junctions from report 07 only, Västerbroplan and Sveaplan.**
- A small request is easier to answer. If it works, ask for the other 500.

**3. Email David Gundlegård (draft 5) and Erik Jenelius (draft 4) together, and pitch a project.**
- As a KTH student, a supervised thesis or data agreement is the realistic way to touch raw INRIX and taxi points.
- If they say no, the derived tables still give route shares between zones and street speeds by hour, which is what the simulator needs.
- A hard records request to a research group should be the fallback. Those groups are the people Erik would want to work with.

## What the law allows, and the trap

I read these directly: tryckfrihetsförordningen, offentlighets- och sekretesslagen and avgiftsförordningen on lagen.nu, HFD 2015 ref 25, and KTH's own page. This is my reading, not legal advice.

- **Anyone can ask.** No format is required. An authority can't ask who you are or why, beyond what it needs to judge secrecy (TF 2 kap. 18 §). Purpose can still help when secrecy is close.
- **Universities count.** KTH, LiU and Lund are state authorities. **Chalmers tekniska högskola AB and Stiftelsen Chalmers are both listed in the OSL annex with "all verksamhet"**, even though Chalmers isn't state-run. Uppsala's guidance says research data is generally a public record during the research and whoever funds it, and is normally kept 10 years after the project. I only found that retention rule at Uppsala, not at KTH.
- **The trap is new compilations.** A compilation from a database only counts as held if it takes "rutinbetonade åtgärder" (TF 2 kap. 6 §). In HFD 2015 ref 25, 4–6 hours of programming and checks was too much, so the authority could refuse. **So ask for files that already exist**, such as what was delivered for a named report. Finished files count whatever the effort. Every draft does this first.
- **Electronic copies are a favour.** An authority doesn't have to hand over a recording in any form but a printout (TF 2 kap. 16 §). KTH says the same. So be polite, keep the request small and offer a smaller version.
- **Cost.** State authorities: free on site, and paper copies are free up to 9 pages, 50 kr for 10 pages, then 2 kr a page (avgiftsförordningen 15–16 §§), plus postage. KTH's electronic copies: 9 files free, 10 files 125 kr, then 5 kr a file. It counts files, so **one big file should be free at KTH**. Stockholm stad and Region Stockholm set their own fees, and I didn't verify those.
- **Secrecy to expect.**
  - OSL 31 kap. 16 §: business details of a firm dealing with an authority, if there's a special reason to expect harm. This is INRIX, Telia and TomTom.
  - OSL 24 kap. 5 §: at universities, business details or research results from research done with a private party. This is the taxi and INRIX data at KTH and LiU.
  - OSL 24 kap. 8 §: statistics work, for information traceable to a person. This is raw RVU.
  - OSL 27 kap.: tax secrecy, which covers trängselskatt. Totals by station and hour shouldn't identify anyone. A 3-digit postcode crossed with fine time bins could get close, so draft 2 asks for it as a separate, coarser table.
- **If refused,** ask for a written decision. Only a decision can be appealed. Trafikverket and KTH both say so.

| Source | Request as a record? | Where |
|---|---|---|
| Laser counts, STRESS, MCS, INRIX contract, Sampers | Yes | [Trafikverket's e-service](https://etjanster.trafikverket.se/begaran-om-utlamnande-av-allman-handling/) or trafikverket@trafikverket.se |
| Toll camera passages | Yes, totals | Transportstyrelsen [registry](https://www.transportstyrelsen.se/sv/om-oss/kontakta-oss/registratur-och-vaxel/), 0771-503 503; no email found |
| Signal plans, Medy counts | Yes | trafikkontoret@stockholm.se, registry 08-508 27 112 (phone from a search snippet) |
| RVU, bus AVL | Yes, but raw RVU may hit secrecy | [registrator.tf@regionstockholm.se](https://www.regionstockholm.se/sprak/english/contact-us/general-questions/official-agency-mailboxes/); the page's visible text says `.sf` but the link says `.tf`, and the Trafiknämnden row confirms `.tf` |
| Taxi, MCS, toll copies at KTH | Yes if still stored; expect 24:5 | [info@kth.se or registrator@kth.se](https://www.kth.se/om/kontakt/utlamnande-av-allman-handling-pa-kth-1.1252489) |
| INRIX at LiU | Yes if stored; expect 24:5 and 31:16 | [registrator@liu.se](https://liu.se/en/contact-liu) |
| Telia extracts at Trafikanalys | Only if downloaded and kept | trafikanalys@trafa.se |
| Car movement data, FlowSense raw | Chalmers is covered, but personal data will likely block raw GPS | Researchers first |
| Telia, Tele2, TomTom, INRIX, Taxi Stockholm | **No**, private firms | Commercial only |
| SCB commuting tables | Sold as a product | SCB |

## Each source

### 1–2. Toll stations: laser and camera
- **Measures:** laser gives passages per lane at all stations for every minute of the day. Camera gives passages per station during charging hours, with size, type, fuel, environmental class, 3-digit postcode and owner type. MEASURED, as described in [Trafikverket report 2020:176](https://trafikverket.diva-portal.org/smash/get/diva2:1505873/FULLTEXT01.pdf), section 2.1.1, opened. Its figures show passages per 10 minutes at Essingeleden.
- **Area and period:** the Stockholm cordon and Essingeleden. The report used February and March of 2019 and 2020. How far back the data goes is unknown.
- **Share observed:** close to all vehicles passing is my inference from fixed lane detectors. Accuracy wasn't stated.
- **Holder:** the report says camera data was delivered by Transportstyrelsen. It doesn't name who holds the laser data, so asking Trafikverket first is my inference. WSP did the analysis. Contacts named: Sofia Heldemar and Peter Huledal, as of 2020.
- **Also:** the [KTH/LiU MMTL report](https://fudinfo.trafikverket.se/fudinfoexternwebb/Publikationer/Publikationer_007701_007800/Publikation_007779/MMTL_final%20report_report.pdf) (TRV 2020/118663, opened) lists "Toll, 57 sensors, 1 hour", so researchers already got hourly copies.
- **Limits:** link-level, not routes. Camera has no weekends or nights.
- **Licence:** public record, no licence terms. Commercial reuse wasn't checked.
- **Test in `cars`:** per-lane flow against time per portal, discharge rate after queue onset, and departure-time shape. Origins by postcode against our demand.
- **Work:** about a day to join station IDs to the net, using the control-point table. Not downloaded, because it isn't public.

### 3. Signal plans
- Reports 01 and 07 found 502–537 installations in the register and no timings. The [city page](https://start.stockholm/om-stockholms-stad/organisation/fackforvaltningar/trafikkontoret/) (opened) says Trafikplaneringsavdelningen is responsible for the city's signals.
- A [2020 report from that department](https://skonhetsradet.stockholm/wp-content/uploads/sites/10/2020/09/Rapport-trafikstyrda-tidplaneval-resultat.2020021.pdf) on traffic-controlled plan selection turned up in search. I did not open it. It suggests plans exist in usable form.
- I don't know if they'd claim a security reason to refuse, so that's UNVERIFIED. **Test:** queue length and discharge at real junctions. **Work:** a converter per controller format, unknown until a sample arrives.

### 4. STRESS and MCS
- **STRESS:** route travel times per 5 minutes, around the clock (report 2020:176). Trafikverket's [2025 state-of-traffic report](https://diva-portal.org/smash/get/diva2:2068724/FULLTEXT01.pdf) (TRV 2026/66916, opened) uses it for its travel-time index maps, with Otto Åstrand as contact. The sources don't describe what feeds it. That it draws on the purchased INRIX times is my inference.
- **INRIX feed:** Trafikverket buys [1-minute values on short segments](https://trafikverket.test.diva-portal.org/smash/get/diva2:30799/FULLTEXT01.pdf), about 4,500 km, mainly around Stockholm, Göteborg and Malmö, used in real time and as history for planning (report dated 2023-01-09, opened).
- **MCS:** the MMTL report lists 572 radar sensors hourly for a 5-week case study and for 2017. It also lists 220,000 link-count observations from 700 sensors, and Medy with 157 city sensors.
- **Test:** travel time by time of day on E4, Essingeleden and Södra länken, independent of flows. This is the congestion truth report 01 said was missing.
- **Open question:** whether the open `TravelTimeRoute` API exposes the same numbers. Report 01 raised this too, and it needs an API key.

### 5. INRIX trips with waypoints
- **Source:** [Probedata förstudie](https://fudinfo.trafikverket.se/fudinfoexternwebb/Publikationer/Publikationer_004501_004600/Publikation_004533/Probedata%20F%C3%B6rstudie%20Publik.pdf), TRV 2019/98384, Ramboll and LiU, 2021-01-12, opened.
- **Size:** 599,271 trips, 458,947 device IDs, 48,234,266 waypoints, 59,206,005 trajectory rows matched to OSM. 16 Sep–21 Oct 2019. Stockholm, E4 to Norrköping, and Norrköping. All trips started in Sweden.
- **Share:** measured against MCS, usually **1–1.5%** on big roads, 0.5–4% by day, below 1% on small roads. INRIX told them about two thirds of raw data was removed because IDs change too often. With it, INRIX estimated 3–5%, for speeds only (PROVIDER CLAIM).
- **Sampling:** up to about 60 s for light vehicles. Median trip has under 30 points.
- **Bias:** too many commercial and medium-heavy vehicles, about 25%. On Uppsalavägen it shows 19–34% heavy, against 3.5–4.9% measured.
- **Validation:** speeds agree well with MCS. Hourly probe counts correlate well with flow. Route tests covered only two OD pairs, with more real routes than the calibrated route set. The authors say traditional OD matrices are hard at this rate, since many pairs get only a few trips a day.
- **Still alive:** MMTL (2024) reports 421,000 trips through its Stockholm area. [DAST slides](https://intra.kth.se/polopoly_fs/1.1410478.1750137751!/Datadriven%20skattning%20av%20trafikarbete%20%28DAST%29%20-%20David%20Gundleg%C3%A5rd.pdf) (June 2025, opened) still list it. People: David Gundlegård (leads DAST, contact on MMTL), Otto Åstrand at Trafikverket.
- **Access:** licence terms not seen. Map-matching costs extra. Price not published in anything I read. Draft 6 asks.
- **Test:** route shares for busy OD pairs against `cars`' routes, trip-level speed against simulated speed on the same links. This is the only real route-level source for Stockholm I found.
- **Work:** several days for map-matching to our net. Weeks if raw access needs an agreement first.

### 6. KTH taxi data
- **Holder:** the [iMobility Lab page](https://www.byv.kth.se/en/avd/transportvetenskap/forskning-urban-mobi/imobility-lab-1.875178) (opened) says the lab stores data from "1500 GPS-equipped taxis", plus motorway detectors, Bluetooth, bus AVL and APC, and ANPR. Director Erik Jenelius, with Matej Cebecauer, Wilco Burghout and Athina Tympakianaki. It says nothing on sharing.
- **Content:** [Rahmani's thesis](https://kth.diva-portal.org/smash/get/diva2:813447/FULLTEXT01.pdf) (opened) says "more than 1500 taxis", with position, ID, hired/free status and time.
- **Supplier:** Taxi Stockholm, from a 2012 KTH news article seen only as a search snippet. That page now returns HTTP 500. UNVERIFIED but consistent.
- **Period:** a snippet of Rahmani's Videos page said Sep 2012–Sep 2013. That page is now a 404, with no archive copy. UNVERIFIED. Other periods may exist.
- **Limits:** taxis may use bus lanes, as the thesis notes, so speeds are biased fast near them. Occupied taxis don't choose routes like commuters. Far below 1% of vehicles, by my estimate.
- **Jenelius & Koutsopoulos 2013:** abstract says low-frequency probes in a Stockholm case study. I couldn't open the full text.
- **Other taxi data:** two 2015 theses used a different-looking set, averaging **15 seconds** between points over about six months, mostly winter 2014–15 ([Axelsson at Valtech](https://www.diva-portal.org/smash/get/diva2:854508/FULLTEXT01.pdf), [Wedin](https://www.diva-portal.org/smash/get/diva2:848038/FULLTEXT01.pdf), both opened). Neither names the supplier. So a taxi operator or its contractor has shared finer data with students before.
- **Test:** street speed by time of day on inner-city links, where we have nothing independent.

### 7. Telia Crowd Insights
- [Trafikanalys PM 2023:6](https://www.trafa.se/globalassets/pm/2023/pm-2023_6-mobilnatsdata-som-kalla-till-resvanor-i-sverige.pdf) (opened): data by day and hour, on 290 municipalities, 1,624 grouped DeSO and 22,626 grid cells of at least 500 m. It can be downloaded as CSV for county, municipality and grouped DeSO. Trafikanalys used 2019–2021.
- **Share:** Telia had 32–33% of subscriptions, scaled up to the population by Telia.
- **Quality:** [PM 2025:8](https://prod.trafa.se/globalassets/pm/2025/pm-2025-8-kombinerade-mobilnatsdata-och-enkatdata-for-att-beskriva-resmonster--metod-pm.pdf) says the earlier analysis found reliability problems and Telia has since changed its method, lowering trip totals. Earlier years aren't comparable. DAST lists low spatial resolution, SIMs per car and water as error sources.
- **Use:** MMTL used the routed "ROAD" OD on 31 zones in Stockholm. It's a demand marginal, not car drivers. Price not found.

### 8. FlowSense: downloaded and tested
- **Source:** [Zenodo 16794871](https://zenodo.org/records/16794871), GPL-3.0, opened. [Paper](https://research.chalmers.se/publication/549663/file/549663_Fulltext.pdf) opened. Saved in `/home/erikf/projects/personal/cars-data/datasets/flowsense-zenodo/` (flows and ground truth; I skipped the 524 MB road network zip).
- **Measures:** phone GNSS from aggregator Pickwell, 2024. In Stockholm, 1,292 million points from 3.2 million devices became 85 million trajectories, averaging 0.9 km and 1.9 min. Published samples use about 100,000 to 1 million trajectories. Mixed modes. **The published flows have no time of day**, and the paper lists that as future work.
- **Licence:** GPL-3.0 on the data is unusual. Using it as a test reference shouldn't taint `cars`, but check before shipping any of it inside the product.
- **My test** (`research/truth/data-hunt/scripts/05_flowsense_check.py`): file `random1to10` against Stockholm's measured weekday counts, joined within 15 m at 360 of 366 sites. I summed the 24 hourly columns.

  | Measure | Result |
  |---|---|
  | Spearman | **0.616** (paper: 0.600–0.656 depending on sample) |
  | Pearson | 0.608 |
  | Pearson on logs | 0.551 |
  | 80% of sites within a factor of | 0.28 to 2.68 of the fitted line |
  | Trajectories per measured vehicle/day, 10,000–20,000 veh/day | median 0.031 (p10 0.014, p90 0.045) |
  | Same, under 2,000 veh/day | median 0.065 (p10 0.010, p90 0.478) |

  The join ignores direction, so this slightly understates what the data can do. Busy streets scale fairly consistently and quiet streets don't, which fits walkers and cyclists in the mix.
- **Use:** run `cars` route flows through the same comparison, as a whole-network check on streets that have no counter. Finding streets with heavy simulated flow and almost no FlowSense trajectories should expose net and routing errors. **Work:** about a day.
- **Pickwell:** I found nothing about the company. Raw phone location data like this comes with serious privacy questions, so I wouldn't buy it without legal advice.

### 9. Swedish car movement data
- [Chalmers record](https://research.chalmers.se/publication/187380) opened: 714 private cars randomly drawn in strata from the vehicle register, GPS at 2.5 Hz, 528 with over 30 days, June 2010–September 2012. Lead: Sten Karlsson.
- Available for research, classified by type because some data is private. Terms not found. The final report PDF wasn't opened.
- Few cars in Stockholm at any moment, so no flows. But a random sample of ordinary drivers at 2.5 Hz is rare. **Test:** free-flow speeds, acceleration and braking against the driver model, and trip chains. Overlaps with `research/truth/05-real-human-driving.md`.

### 10–12. Demand inputs
- **RVU:** Region Stockholm 2024, n=11,985 (reports 01, 02). Trafikanalys's [quality declaration](https://www.trafa.se/globalassets/statistik/resvanor/2021/kvalitetsdeklaration-trafikanalys-rvu-2021.pdf) (opened) confirms 24 kap. 8 § applies and names Andreas Holmström as a contact as of 2021. Smallest coding is DeSO, but Trafikanalys says small areas aren't reliable at this sample size. So ask for tables by start hour and large area, not microdata.
- **Sampers:** the [official page](https://bransch.trafikverket.se/tjanster/system-och-verktyg/Prognos--och-analysverktyg/Sampers/) (opened) says access goes through the contact form. No fee stated. Paul Larsson and Anna Enström are named, phone only. MODELLED, so it's a starting point, not truth.
- **Region's model:** a [VTI project record](https://projektdatabas.vti.se/bib/3227) in search results mentions a Sampers and MATSim system for Region Stockholm. Not opened.
- **SCB:** [AMPAK](https://www.scb.se/vara-tjanster/bestall-data-och-statistik/regionala-statistikprodukter/statistikpaket/ampak--delomradesniva/) (opened) sells BEF301/302, home-to-work counts between small areas. Contact Caroline Rathsmann. Price list not opened. [Grid statistics](https://www.scb.se/vara-tjanster/oppna-data/oppna-geodata/?menu=open) are open geodata, but that page doesn't state cell sizes or licence.

### Fields common to everything above
All of it covers Sweden. Only FlowSense was downloaded, plus 20 or so reports in `/home/erikf/projects/personal/cars-data/datasets/se-docs/`.

## What only Erik can do

Drafts are below, written from the style summary in Erik's KTH memory file, because the brain skill `erik-writing-style` couldn't be loaded here. **Read them against the full skill before sending.** Check these first:
- That the contact people are still in those jobs. Several names are from 2020–2021.
- Whether he wants to mention the thesis or the simulator at all. He doesn't have to.
- How he wants to sign, and whether to use his KTH address.

Send in this order: 1, 2, 3, then 4 and 5 together, then the rest.

---

**Draft 1. Trafikverket: toll flows, STRESS and MCS**
To: `trafikverket@trafikverket.se` or the [e-service](https://etjanster.trafikverket.se/begaran-om-utlamnande-av-allman-handling/). Copy Otto Åstrand (`[e-mail removed]`).
Subject: Begäran om allmän handling: flöden vid betalstationer och restider i Stockholm

> Hej!
>
> Jag vill begära ut följande allmänna handlingar. Det gäller filer som redan finns, så ni behöver inte ta fram något nytt.
>
> 1. Laserdatan från betalstationerna för trängselskatt i Stockholm som användes i Rapport 2020:176 (Utvärdering av förändrad trängselskatt 2020), avsnitt 2.1.1. Alltså passager per körfält och minut, för veckorna 7–8 och 10–11 år 2019 och 2020.
> 2. Restidsdatan från Stress-databasen som användes i samma rapport, per rutt och 5-minutersperiod, samt en lista över rutterna.
> 3. MCS-data för Essingeleden, E4 och Södra länken, flöde och hastighet per körfält, för samma veckor om det finns.
>
> Om ni inte har uppgifterna i del 1 kan ni väl säga vem som har dem. Sofia Heldemar och Peter Huledal står som kontaktpersoner i rapporten.
>
> Jag vill gärna ha det som CSV eller liknande via e-post eller länk. Är det för mycket så räcker en vecka från 2020 som första steg.
>
> Om något inte kan lämnas ut vill jag ha ett skriftligt beslut med besvärshänvisning.
>
> Tack!
> Erik Frankling

---

**Draft 2. Transportstyrelsen: camera passages**
To: Transportstyrelsen's registry, through the [contact form](https://www.transportstyrelsen.se/sv/om-oss/kontakta-oss/kontaktformular/kontakt-allmanna-fragor/) or by calling 0771-503 503 to ask for the mailbox. I found no address.
Subject: Begäran om allmän handling: trängselskattepassager per betalstation

> Hej!
>
> Jag vill begära ut passagedata från trängselskattesystemet i Stockholm. I Trafikverkets Rapport 2020:176 står det att kameradata per betalstation har levererats från Transportstyrelsen. Jag vill i första hand ha den leveransen, utan registreringsnummer eller andra uppgifter om enskilda.
>
> Det jag vill ha är:
>
> 1. Antal passager per betalstation, riktning och 15 minuter, uppdelat på fordonstyp.
> 2. Antal passager per betalstation och riktning under förmiddagens och eftermiddagens högtrafik, uppdelat på de tre första siffrorna i ägarens postnummer och på fysisk eller juridisk ägare. Små celler får gärna tas bort.
>
> Finns inte den leveransen kvar vill jag ha motsvarande för en månad under hösten 2025, om det går att ta fram med rutinbetonade åtgärder. Säg gärna till om någon annan period redan finns sammanställd.
>
> CSV via e-post eller länk går bra. Om något inte kan lämnas ut vill jag ha ett skriftligt beslut med besvärshänvisning.
>
> Tack!
> Erik Frankling

---

**Draft 3. Stockholm Trafikkontoret: signal plans**
To: `trafikkontoret@stockholm.se`, for Trafikplaneringsavdelningen.
Subject: Begäran om allmän handling: signalplaner Västerbroplan och Sveaplan

> Hej!
>
> Jag vill begära ut signalplaner för två korsningar: Västerbroplan och Sveaplan. Jag skulle vilja ha:
>
> 1. Tidplaner för en vanlig vardag, med omloppstid, faser och gröntider.
> 2. Hur tidplanerna väljs under dygnet, och eventuell samordning med grannkorsningar.
> 3. Var detektorerna sitter, om det finns med i samma handlingar.
>
> Det går bra med de filer eller pdf:er ni redan har. Jag behöver inget nytt framtaget.
>
> Jag vill också gärna veta vilket format signalplanerna finns i, och om det finns en samlad förteckning över alla anläggningar.
>
> Finns det även timdata från era fasta mätstationer (Medy) för oktober 2024 så vill jag gärna ha den också.
>
> Om något inte kan lämnas ut vill jag ha ett skriftligt beslut med besvärshänvisning.
>
> Tack!
> Erik Frankling

---

**Draft 4. KTH: Erik Jenelius**
To: Erik Jenelius at KTH (address on his KTH profile). This is a normal question, not a records request. If it leads nowhere, send 4b.
Subject: Trafikdata i iMobility Lab, fråga från KTH-student

> Hej Erik!
>
> Jag pluggar på KTH och bygger en trafiksimulator som kör på GPU. Det började som mitt kandidatarbete. Nu försöker jag jämföra den mot riktig data för Stockholm, och det är där jag fastnar.
>
> Jag såg att iMobility Lab har GPS-data från taxibilar, MCS och trängselskatteportaler. Tre frågor:
>
> 1. Finns taxidatan kvar, och för vilka år?
> 2. Går det att få tillgång till den, eller till MCS och portaldata, som student? Till exempel i ett examensarbete eller under ett avtal.
> 3. Om rådata inte går, finns det färdiga länkhastigheter per timme som jag kan få?
>
> Jag kan gärna komma förbi och visa vad jag har.
>
> Mvh
> Erik Frankling

**Draft 4b. KTH registry, if needed**
To: `registrator@kth.se`
Subject: Begäran om allmän handling: taxi-GPS i iMobility Lab

> Hej!
>
> Jag vill begära ut GPS-data från taxibilar i Stockholm som lagras i iMobility Lab på avdelningen för transportvetenskap. Jag vill ha en vecka i oktober, från det senaste året som finns, med tid, position, fordons-id och status. Fordons-id får gärna bytas ut mot löpnummer.
>
> Jag vill också veta vilka perioder som finns och om det finns något avtal som styr utlämnandet.
>
> Det går bra med en enda fil. Om något inte kan lämnas ut vill jag ha ett skriftligt beslut med besvärshänvisning.
>
> Tack!
> Erik Frankling

---

**Draft 5. LiU: David Gundlegård**
To: `[e-mail removed]`. Copy Clas Rydergren if he wants.
Subject: INRIX-resorna från Probedata-förstudien

> Hej David!
>
> Jag pluggar på KTH och bygger en trafiksimulator för Stockholm. Jag läste er förstudie om probedata (TRV 2019/98384) och MMTL-rapporten. INRIX-resorna från hösten 2019 är det närmaste riktiga ruttval jag har hittat för Stockholm.
>
> Tillåter avtalet med INRIX något av det här?
>
> 1. Att jag får resultat i aggregerad form: ruttandelar mellan zoner och medelhastighet per länk och timme.
> 2. Att jag skickar min kod och att ni kör den på er sida.
> 3. Att jag får tillgång under ett projekt eller examensarbete.
>
> Vet du vad det kostar att köpa motsvarande dataset i dag? Det vore också bra att veta.
>
> Jag vill gärna höra vad som är möjligt, och kan visa vad jag har om det är intressant.
>
> Mvh
> Erik Frankling

---

**Draft 6. Trafikverket: INRIX contract and probe data**
To: `trafikverket@trafikverket.se` or the e-service.
Subject: Begäran om allmän handling: avtal om probedata

> Hej!
>
> Jag vill begära ut följande:
>
> 1. Avtalet eller beställningen för INRIX-datasetet "Trips with waypoints and trajectories" i ärende TRV 2019/98384, med pris och villkor för hur data får användas och delas.
> 2. Gällande avtal för restider från INRIX, med samma uppgifter.
> 3. Eventuella avtal om hastighetsdata från TomTom.
> 4. En kort beskrivning av databasen Stress, om det finns något dokument: vilka rutter, vilka datakällor och hur långt tillbaka data finns.
> 5. Om ni har en kopia av INRIX-datasetet, besked om det kan lämnas ut.
>
> Jag har också hört om ett verktyg som heter Luse. Om det finns dokumentation om det vill jag gärna ha den.
>
> Delar av avtal får gärna maskas om det behövs. Om något inte kan lämnas ut vill jag ha ett skriftligt beslut med besvärshänvisning.
>
> Tack!
> Erik Frankling

---

**Draft 7. Trafikanalys: Telia and RVU**
To: `trafikanalys@trafa.se`, for Andreas Holmström (named as of 2021).
Subject: Begäran om allmän handling: mobilnätsdata och RVU för Stockholms län

> Hej!
>
> Jag vill begära ut två saker:
>
> 1. De CSV-filer med Telias mobilnätsdata som ni använde i PM 2023:6, för Stockholms län. Helst resor per timme mellan grupperade DeSO, annars per kommun.
> 2. Från RVU: bilförarresor i Stockholms län per starttimme och avståndsklass, för de senaste åren. Avidentifierade tabeller räcker.
>
> Om avtalet med Telia hindrar del 1 vill jag gärna veta vad det står i det och vad ni betalar för tillgången.
>
> Om något inte kan lämnas ut vill jag ha ett skriftligt beslut med besvärshänvisning.
>
> Tack!
> Erik Frankling

---

**Draft 8. Region Stockholm: RVU and bus data**
To: `registrator.tf@regionstockholm.se`
Subject: Begäran om allmän handling: resvaneundersökning 2024

> Hej!
>
> Jag vill begära ut tabeller från resvaneundersökningen för Stockholms län 2024:
>
> 1. Antal bilförarresor per starttimme, för vardagar.
> 2. Antal bilförarresor mellan kommuner eller större områden, per högtrafik och övrig tid.
> 3. Fördelning av reslängd för bilförare.
>
> Finns de inte sammanställda vill jag ha den avidentifierade resfilen, om det går. Annars säg gärna vilka tabeller som redan finns.
>
> Om något inte kan lämnas ut vill jag ha ett skriftligt beslut med besvärshänvisning.
>
> Tack!
> Erik Frankling

---

**Draft 9. Chalmers: Sten Karlsson**
To: Sten Karlsson (address on Chalmers' site; he may have retired, so ask Physical Resource Theory if it bounces).
Subject: Swedish car movement data

> Hej!
>
> Jag pluggar på KTH och bygger en trafiksimulator. Jag är intresserad av er GPS-loggning av privatbilar från 2010–2012. Går datan att få tillgång till för forskning eller ett studentprojekt?
>
> Det jag helst vill ha är hastighet och acceleration över tid, gärna utan positioner om det gör det enklare med integriteten. Hur ansöker man, och finns det några villkor?
>
> Mvh
> Erik Frankling

---

**Draft 10. Chalmers: Roos Teeuwen and Jorge Gil**
To: `[e-mail removed]`. Copy Jorge Gil. English, since I don't know that Roos Teeuwen writes Swedish.
Subject: FlowSense flows by time of day?

> Hi Roos,
>
> I'm a student at KTH working on a traffic simulator for Stockholm, and I've been comparing it with your FlowSense flows. Thanks for publishing them.
>
> Do you have, or plan to publish, flows split by time of day and direction? Even morning peak, evening peak and the rest would help a lot. If it's easier, I could also send you my code to run on your side.
>
> Best,
> Erik Frankling

---

**Draft 11. Trafikverket: Sampers and Dynameq**
To: the Sampers administrators through the [contact form](https://etjanster.trafikverket.se/kundfragor-trafikverket), for Paul Larsson or Anna Enström.
Subject: Basprognos Sampers och Dynameq Storstockholm

> Hej!
>
> Jag pluggar på KTH och bygger en trafiksimulator för Stockholm. Jag skulle vilja ha den gällande OD-matrisen för biltrafik i Stockholmsregionen från Sampers, helst per tidsperiod, och nätet och matriserna från Dynameq Storstockholm.
>
> Går det att få som student, och vilka villkor gäller? Kan man även få det utan själva programvaran?
>
> Tack!
> Erik Frankling

---

**Draft 12. SCB: price**
To: `[e-mail removed]`
Subject: Pris på BEF301 och BEF302 för Stockholms län

> Hej Caroline!
>
> Vad kostar BEF301 och BEF302 för Stockholms län på delområdesnivå, för senaste året? Finns det något pris för studenter?
>
> Tack!
> Erik Frankling

---

## Dead ends

- **Trafikverket's "Luse" tool.** I found no trace of it, in searches or in about 20 Trafikverket and research reports I grepped. Closest real match is STRESS. Draft 6 asks. Treat "Luse" as UNVERIFIED and possibly misremembered.
- **Trafikverket buying TomTom for traffic operations.** Not found. The agency's 2023 report says INRIX. A [2021 research memo](https://fudinfo.trafikverket.se/fudinfoexternwebb/Publikationer/Publikationer_005901_006000/Publikation_005945/PM_Effektsamband_2021-12-20.pdf) did use TomTom and INRIX speeds for one study. No TomTom contract was found, though I didn't search TED or Trafikverket's tender records.
- **`people.kth.se/~mahmoodr/`.** 404, no Wayback snapshot. The thesis on DiVA has what matters.
- **KTH news article on the taxis.** HTTP 500 now, no archive.
- **Tele2 mobility data.** No product found, no sign that Trafikverket or the Region buys it. Absence from one search only. Trafikanalys says it has only had access to Telia.
- **Telia prices.** Nothing public.
- **Public toll data by station.** Transportstyrelsen publishes monthly totals. I saw no public per-station series.
- **Trafikflödeskartan.** Trafikverket's method report describes it as showing ÅDT estimates per road section (search snippet of a 2015 report). It's yearly estimates, so no use as congestion truth. Not opened live.
- **Current Stockholm stad probe contract.** Only 2003–2009 records of buying travel times from a Dutch supplier, on just under 50 sections. Nothing recent found.
- **SL and KTH AVL agreement details.** Nothing found. Bus AVL is reachable through KoDa anyway (report 01).
- **Lund and Malmö.** One search found nothing useful beyond Malmö's open traffic counts. Under-researched, not ruled out.
- **OSL secrecy for toll passages by postcode.** I read the rule but found no case on it. It may go either way.

## Corrections to earlier reports

- **Reports 01, 02:** ask for per-minute, per-lane laser data, not just 15-minute passages. Transportstyrelsen's camera data only covers charging hours. The laser data is the one that runs around the clock.
- **Report 02 section 10, report 01:** "MCS archive" should be asked for together with STRESS, which they don't name.
- **Report 02:** the "POST" pattern is real, and MMTL gives the actual table of sources, which is stronger evidence than POST's description.
- **Report 06:** TomTom is listed first among connected-car sources. For Sweden, INRIX is the documented supplier.

## New directions I couldn't cover

- **Medy, 157 city sensors with hourly data.** Could be a much better city-street flow source than `Arstrafik` samples. Draft 3 asks.
- **WSP.** Their analysts hold toll data delivered for the 2020 evaluation. Consultants aren't covered by the records rules, but they may know what exists.
- **Taxi operators directly.** The 15-second set from 2015 suggests someone shared finer data. Worth asking Taxi Stockholm and Cabonline, commercially.
- **Trafik Stockholm's monthly disturbance reports,** cited in the 2025 Trafikverket report. Dated incidents would let `cars` exclude bad days from comparisons.
- **Other Stockholm road reports with Trafikverket contact Otto Åstrand.** Links DAST and the state-of-traffic series, so likely the most useful single person at Trafikverket.
- **Gothenburg.** FlowSense reports Spearman 0.81 at highway sites there. Its ground truth files are in the same Zenodo download. Trafikverket and the city's counts could make it a second test city.
- **Thesis route.** A KTH degree project with Jenelius, or at Trafikverket, may be the fastest legal way to raw data.
