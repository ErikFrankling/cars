# 11. Real signal timing: what exists, and how to generate Swedish programs

Grades used: MEASURED (I counted it from data I opened), PROVIDER CLAIM (the owner says so), MODELLED (came out of a simulation or formula), UNVERIFIED (not opened or not confirmed). Everything was opened on 2026-11-02 unless marked.

## The answer

Stockholm's actual timing files are not public, but much more of the logic is than earlier reports found. The city publishes its controller specification, and a 2008 city report lists **31 coordinated systems with their real cycle lengths**: mostly 80 to 100 s, 155 controllers in total, with a clock schedule (100 s 06-10, 80 s 10-14, 100 s 14-19, 80 s 19-22, free at night). Sweden's legal rules give clearance, yellow, minimum green and walking speed as formulas. The open register gives groups, left arrows and bus priority lamps per installation, and its numbering is 85% clockwise, as the city's handbook says it should be (random would be 50%). Together that is enough to generate programs far closer to reality than netconvert's.

I wrote a prototype that rewrites all 903 programs in the register net by these rules. **What is still open: how many of the 631,888 teleports it removes.** The SUMO A/B on the homelab did not finish inside the time box: it first failed on a route error and is now queued behind other jobs. A static screen points the same way (lanes over nominal capacity: 42 generated, 6 to 8 rule-based, of 1,791 loaded lanes) but is not proof. See [below](#did-generated-programs-cause-the-teleports).

No open live signal feed exists in Sweden that I could find. Two real ones are open elsewhere and I downloaded samples: Hamburg (796 signals, live per-second API, no key) and Perth (about 1,070 sites, cycle-by-cycle phase times, 22+ months). A records request is still worth sending. It's the only route to true Stockholm plans, and Vienna and Sydney show it can be refused.

## Ranked sources

| # | Source | What it gives | Area and period | Share of vehicles / signals | Access, licence | Sweden? | Downloaded? | Needs | Test it enables | Work |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Stockholm handbook 05.04 and Del 7, Matsis report, tidplan and adaptive reports, plus the register** | Controller logic, 31 corridors with cycles, clock plans, one worked junction, cap of 100 s, groups, arrows | Stockholm, 2008 to 2021 | Cycles for 155 of 546 controllers then (28%). Register: 525 installations with vehicle groups. PROVIDER CLAIM for documents, MEASURED for register | Open PDFs and open WFS. Register text says free reuse | Yes | Yes | 5 | Generator rules, realism check on cycles | Spec below |
| 2 | **Transportstyrelsen TSFS 2014:30, SKL guide, VGU Råd 2022:003** | Legal yellow, clearance formula, min green, walking speed, when left turns must be separate, LHOVRA detectors | Sweden, current | All signals by law, since 2018-01-01 for existing ones | Open | Yes | Yes | 5 | Unit tests on every generated phase | Small |
| 3 | **Perth: Main Roads WA SCATS history** | Per cycle: actual cycle, phase times A to G, per-detector volume, coordination flag, for each site | Western Australia, 22 monthly folders from 2024-11 to 2026-09 (2025-10 not listed) | About 1,070 sites per month, MEASURED from folder counts. Green times are SCATS-reported, "no guarantee this data is accurate" | Open SharePoint link, no login, CC BY 4.0, commercial use allowed with attribution | No | Yes: 60 random sites of 2026-09, 78 MB, 59 usable. A whole month is 1.6 GB | 5, 3 | External realism test of cycle and phase distributions, and capacity against measured flow | 1 to 2 days. Left-hand traffic |
| 4 | **Hamburg: LSBG traffic-light SensorThings API and TU Dresden archive** | Live per-second state per connection, cycle second, program id, detector calls | Hamburg. Archive Sep to Oct 2023, API today | 796 lights, 20,018 primary streams, MEASURED. In my sample 37 of 60 had usable data in at least one window | API open, no key. dl-de/by-2.0. Archive CC BY 4.0, 31.5 GB zip, 165 GB unzipped | No | 60-light sample of one Friday. Archive not downloaded | 5, 3 | Real signal behaviour against generated. Actuation model test, with detector calls and states in one stream | 1 to 3 days, plus a map |
| 5 | **Melbourne controller sheets** (report 01) | Phase sequence, min, max, yellow, all-red, detector maps | Victoria | Sites across the state. SCATS splits not included | Open, 27 bundles of 2 to 3 GB | No | Not by me, see report 01 | 5 | Structure check | Left-hand |
| 6 | **Chinese FCD paper (NavInfo, Baidu authors), arXiv 2507.14190** | Method plus about 100 intersections of FCD with vision ground truth | Beijing, Shanghai, Shenzhen | Probes: 3 s sampling. 10,304 test intersections. Acc-5 on cycle 91% overall. PROVIDER CLAIM | Paper CC BY 4.0. Code and data on [OneDrive](https://1drv.ms/f/s!AiPwiDNbcd1umbcgLBfuYy3IP71N), not opened | No | No | 5 | Inference method if a Swedish probe source appears | Medium |
| 7 | **SL buses, Trafiklab GTFS-RT VehiclePositions** | Bus positions on a 2 s feed cycle, PROVIDER CLAIM. Could reveal cycle and red on bus corridors | Stockholm, live | Buses only, not all SL vehicles confirmed. Passing every few minutes | Key needed, Erik must sign up | Yes | No | 5, 3 | Check generated cycles against real ones on bus streets, without asking anyone | About 1 week of collection |
| 8 | **NordicWay Interchange** | SPATEM/MAPEM from Gothenburg, Uppsala (intersections 303 to 305, six at launch), one Trafikverket site (6830) | Sweden, pilots 2018 to 2023 | A few sites | Closed to OEMs and partners | Yes | No | 5 | Real Swedish state stream, if a partner lets Erik in | Needs a person |
| 9 | **OpenTrafficMap, Graz and Vienna** | Open-source ESP32 receiver of over-the-air SPATEM/MAPEM. Live map. 165 Graz signals planned to broadcast, per a blog | Austria, 2026 | Not checked | Code open on Codeberg. Page opened, no data API found | No | No | 5 | Build your own recorder if anything in Stockholm ever broadcasts | Hardware |
| 10 | **Tampa CV pilot SPaT sample, Orem MAP** | J2735 SPaT | US | Sample | CC, data.transportation.gov. The id I tried returned 404, so UNVERIFIED | No | No | 5 | Little | Low value |

## Top 3 recommendations

1. **Build the generator in the spec below and run the A/B in `cars`.** Next step: start from `research/truth/data-hunt/scripts-11/swedish_tls.py`, which already rewrites every program in the register net. Run the queued SUMO A/B result first (command below), then the same comparison in `cars` on the GPU, which I was not allowed to use.
2. **Send the records request below, starting small.** Next step: Erik sends draft 1, three installations in Västerbroplan (3302, 3304, 3342) plus the list of coordinated systems. Their plans can be compared directly with the published P2/P3/P4 clock times, and the same documents show how much the generator gets wrong.
3. **Use Perth and Hamburg as outside truth for the generator now, and get a Trafiklab key for Stockholm's own check.** Next step: compare generated cycle, phase count and green share with both (scripts in `scripts-11/`). Then Erik gets a key and a builder collects a week of SL positions on Hornsgatan and Odengatan, and tests whether bus stops line up with 100 s and 80 s by clock hour.

## What only Erik can do

- **Send the requests.** Nobody has been contacted. Two drafts follow. I could not load `erik-writing-style` because the Executor server returns 503 (repair thread [Executor MCP down for Claude sessions (503)](t3-thread://v2/638dd505-c97b-41e7-b7a7-7d91b3b9fd67/mcp:launch:c8b7463707a745440cddb6c23738795cbc3ad6964fbf9782a93e059055d0873e) is already running). So these are plain drafts that have not been through the style skill. Erik should edit them to his voice.
- **Get a Trafiklab key** for GTFS Regional or GTFS Sweden 3 realtime, for recommendation 3.
- **Ask a NordicWay partner** (RISE or Trafikverket) whether a research account on the interchange is possible. I don't recommend this before the request below has an answer.

### Draft 1: Trafikkontoret, Stockholm

To: trafikkontoret@stockholm.se (address on the city's page; I found no separate registry address)

> Ämne: Begäran om allmänna handlingar: tidplaner för trafiksignaler
>
> Hej,
>
> Jag begär att få ta del av följande allmänna handlingar för trafiksignalanläggningarna 3302, 3304 och 3342 (Västerbroplan och Gjörwellsgatan/Rålambsvägen):
>
> 1. Funktionsbeskrivning för oberoende styrning (enligt DV8) och för central eller lokal samordning.
> 2. Signalväxlingsscheman eller motsvarande för gällande tidplaner (P1 till P4): omloppstid, gröntider, startbesked och förskjutning.
> 3. Klockslag för tidplanval.
> 4. Detektorfunktioner, med detektoravstånd och intervalltider.
> 5. Säkerhetstidshandlingar (spärrmatris, säkerhets- och rödtider).
>
> Jag ber också om en förteckning över stadens samordnade signalsystem med ingående anläggningar och omloppstider, motsvarande listan i Matsis-rapporten från 2008.
>
> Jag behöver inte kabelplaner, IP-adresser, inkopplingsscheman eller andra uppgifter om styrsystemets kommunikation. Om någon del omfattas av sekretess, stryk den delen och lämna ut resten.
>
> Jag vill gärna ha handlingarna digitalt, i det format de finns. Om begäran helt eller delvis avslås vill jag ha ett skriftligt beslut med besvärshänvisning.
>
> Tack på förhand.
>
> Erik Frankling

Why it is worded this way:
- The document names come from the city's own handbook Del 7, section 70.24. The file types in item 2 and 5 come from Uppsala's handbook, which names `signalväxlingsscheman`, `spärrmatris` and `styrpulstabell samordning`, so Stockholm's own names may differ.
- The likeliest refusal is OSL 18 kap. 8 §: secrecy for information about a "säkerhets- eller bevakningsåtgärd" concerning "byggnader eller andra anläggningar", if disclosure would defeat its purpose. Timing isn't obviously a security measure. Leaving out cabling and communication removes the strongest argument. I found no Swedish case on signal plans either way (UNVERIFIED that none exists).
- Erik doesn't need to explain why he wants them: TF 2 kap. 18 § limits what the authority may ask. Stating a purpose is optional.
- If it goes well, the next ask is the rest of the signal areas, then Hornsgatan, Valhallavägen and Långholmsgatan, which the 2020 report names as coordinated systems.

### Draft 2: Uppsala kommun or Trafikverket, if Stockholm refuses

> Hej,
>
> Jag begär att få ta del av signalväxlingsscheman (anläggningsnummer-n-TPx), spärrmatris (-S), säkerhets- och rödtider (-R), detektorfunktioner (-D) och styrpulstabell för samordning (-P) för anläggning [nummer]. Filnamnen följer er tekniska handbok, version 1.1. Kabelplaner och nätverksuppgifter behövs inte. Digital form går bra.
>
> Erik Frankling

## Which documents exist

**PROVIDER CLAIM,** Stockholm [Teknisk handbok 2012 Del 7][del7] section 70.24 lists: kombinerad signal- och kabelplan, säkerhetstidshandlingar, funktionsbeskrivning enligt DV8 for isolated control, detektorfunktioner, funktionsbeskrivning for local and central coordination, väg-tid-diagram, programmeringsunderlag for bus priority. [Uppsala's handbook][upp] adds a file naming scheme, which shows what a timing folder looks like: `034-1` signal plan, `034-S` spärrmatris, `034-R` safety and red times, `034-D` detector functions, `034-3-TP8` switching scheme for time plan 8, `034-P` control pulses for coordination.

## Who runs them

- **MEASURED:** 4,793 of 5,127 vehicle lanterns in the register are Swarco (Futurit, CIFLOW). This is lantern hardware, not proof of the controllers.
- **PROVIDER CLAIM:** Swarco's page says it is Stockholm's main signal supplier and service partner (search snippet only, page returned 403). Matsis used a Swarco controller simulator with Vissim and mentions Ericsson's ELC controller and Swarco's SPOT adaptive system, which the city dropped in 2005. ONE Nordic took over repair for about 300 installations in northern Stockholm from 2023-02-01. Monitoring is OmniVue, replacing EC-Trak. A 2021 notice shows the city buying controllers through a dynamic purchasing system: 3 for Vasagatan, 200,000 SEK.
- **UNVERIFIED:** current controller model mix.

## The spec

Goal: from `net.xml` and the register, produce one program per controller and time plan that obeys Swedish law and looks like Stockholm's real ones. Prototype: [swedish_tls.py](scripts-11/swedish_tls.py) implements S1 and S3 to S7 in simple form. It does not do S2, S8 beyond tier 1, or S9. Evidence tag per rule: [L] law, [S] Stockholm document, [V] national guidance, [M] measured here, [A] my assumption, to be replaced when data arrives.

### S1. Inputs and controllers

1. One controller per installation, as report 07's `maps_patch_tls.py` already does. [S] Handbook 5.7.1: one apparatus can hold up to 4 independent rings, so one installation can run several nodes.
2. From `Signallykta`, per `anläggnings-id`: groups `F<n>`, `G<n>`, `C<n>`, `S<n>`. Use `typ`, not `namn`, for meaning: `Fordon 3-skens, v-pil` is a protected left, `h-pil` a right arrow, `Kollektivglas` a bus signal, `Priolampa` bus priority.
3. Also from register: 1 group or a `Tryckknapp` with no vehicle conflict means a crossing on a road. `Tryckknapp` `namn` `T<n>` gives push buttons.
4. Where the register is silent (other municipalities, state roads): geometry only, flagged in output.

Measured register counts: 525 installations with vehicle groups, median 4. 170 have a left arrow group and 79 of those have two. 132 have a right arrow. 149 have a bus priority lamp. 287 have cycle signal groups and 495 pedestrian groups. Table: `/home/erikf/projects/personal/cars-data/datasets/signal-program-spec/register_groups.csv`.

### S2. Group to approach

[S] Handbook 5.2: groups are numbered clockwise from the west, vehicles first, then cycle and pedestrian. Uppsala's handbook repeats vehicles-first.

**MEASURED** with [numbering_test.py](scripts-11/numbering_test.py) on 310 installations with 3+ groups, taking each group's first lantern: 85% of steps go clockwise, against 50% by chance. 78% of installations are at least 75% clockwise. The first group sits west in 51% and south in 31%, so the start point isn't reliable and the order is. This overturns report 07's "not worth it before phase order is known" in part: the groups can now be attached to approaches.

Algorithm:
1. Bearing of each approach at the node, clockwise from west.
2. Sort F groups by number, approaches by bearing. Try all rotations, choose the one minimising distance from each group's first lantern to its approach's stop line.
3. Arrow groups attach to the left lane of the approach they follow. Number of groups per approach must equal 1 + arrows.
4. Report mismatches per installation. Do not fail: fall back to geometry.

### S3. Phase structure

| Situation | Result | Source |
|---|---|---|
| Crossing streets going straight | Always separated in time | [L] TSFS 2014:30 2 kap. 2 § |
| Limit ≥ 60 km/h and a left turn | Protected, arrows required | [L] 3 kap. 18 §, SKL guide |
| Two left lanes | Protected in both directions, regardless of speed | [V] VGU Råd 10.3.3.3.7, [SKL] 3 kap. 17 § |
| Left lane plus shared lane with through | Approach gets its own phase ("särskild fas per tillfart") | [V] 10.3.3.3.8 |
| Protected left one way | Opposite left protected too | [V] 10.3.3.3.6 says must, SKL says should |
| Own left lane, under 60 km/h, no arrow in register | Permissive with opposing through (blandfas), state `g` | [V] 10.3.3.3.6 |
| Shared left and through | Blandfas only. Not with high left share | [V] 10.3.3.3.3 |
| Register has `v-pil` for the approach | Protected | [M] register |
| Own lane right turn | Blandfas with through. Arrow only if the left of the complementary flow is protected | [V] 10.3.3.3.4 |
| Three-leg, side road | Side road one phase, shared lane allowed | [V] 10.3.3.3.9 |
| Crossing on a road | Vehicle green, then pedestrian phase on call. Both directions change together | [S] 5.10.2 |
| Pedestrian next to junction | Follows parallel vehicle group during day (06-20) in inner city | [S] Del 7, 71.1 |
| No left lane, no arrow, over 60 km/h | Own phase per approach, or check the turn ban | [SKL] |

Phase order: left phase before through ([A], 2-phase left-first), main road first. Real controllers can start a group inside or after a phase and can run acyclic ([S] 5.3): leave that out at first.

For extra nodes inside one installation: a crossing mirrors the movement next to it, shifted by travel time; a node with conflicts gets its own ring and shares the cycle. This is the single biggest difference from netconvert, where a crossing 15 m from the junction can sit at red while the junction is green.

### S4. Times that follow from law

| Item | Value | Source |
|---|---|---|
| Yellow | 4 s under 60 km/h, 5 s at 60 or more. Cycle signal 3 s | [L] §§ 12-13 |
| Red-yellow | 1.5 s | [L] § 11 |
| Min green | 4 s law. Stockholm: 4 to 6 s, at least 5 s where cycles share | [L] § 14, [S] 5.7.2 |
| Cycle signal green | at least 5 s | [L] § 15 |
| Pedestrian green + flash | width / 1.4 m/s, at least 5 s flash if flash is used | [L] § 16, [S] 5.7.3 |
| Clearance `ts` | `ts = (s_ut + l_f)/v_ut − s_in/v_in`, `ts > 0` | [L] § 4 |
| `l_f` | 6 m, 2 m for cycle and moped | [L] § 10 |
| Speeds | Limit 30/40/50/60/70 km/h gives 8/10/12/14/15 m/s. Cycle 5, moped 8, walking 1.4, flash 2.0 | [L] § 9 |
| Cycle value | Highest of all traffic types; if it's a cycle, may subtract 1 s | [L] § 5 |

`s_ut` and `s_in` come from the conflict points of each movement pair along `via` lanes. Compute each pair, then each change takes the largest. The prototype simplifies with the conflict point at 60% and 30% of the longest through movement. A builder should use real geometry from the internal lanes, then log `ts`.

Red-yellow: the lost time of a change is `yellow + ts`, not `yellow + ts + 1.5`, since red-yellow runs inside the conflicting group's clearance. A simple engine can show red for it.

### S5. Cycle lengths and time plans

**This is the part the old reports lacked.** Real Stockholm, [Matsis][matsis] section 4.3, before the project (PROVIDER CLAIM, 2008, likely changed since):

| System | Controllers | Cycle s | | System | Controllers | Cycle s |
|---|---:|---:|---|---|---:|---:|
| Odengatan | 21 | 70-95 | | Fleminggatan | 5 | 56-82 |
| Norrtull | 3 | 115 | | Londonviadukten | 1 | 80-100 |
| Valhallavägen västra | 2 | 80-90 | | Strandvägen | 8 | 80-100 |
| Valhallavägen centrala | 6 | 70-90 | | Långholmsgatan | 8 | 90-100 |
| Valhallavägen östra | 2 | 60 | | Ringvägen västra | 4 | 90-100 |
| Lidingövägen | 5 | 80-100 | | Södermalmstorg | 4 | 90-100 |
| Sveavägen södra | 5 | 80-100 | | Götgatan | 6 | 90-100 |
| Birger Jarlsgatan/Tegnérgatan | 3 | 66-80 | | Folkungagatan | 3 | 60-80 |
| Sergels torg | 7 | 70-90 | | Ringvägen östra | 8 | 80-100 |
| Stureplan | 3 | 80 | | Åbyvägen | not given | not given |
| Vasagatan | 7 | 90 | | Huddingevägen/Örby slottsväg | 3 | 70-100 |
| Tegelbacken | 6 | 90 | | Örbyleden/Lingvägen | 2 | 100 |
| Skeppsbron | 6 | 80-100 | | Alviksvägen | 2 | 90-120 |
| Gustaf Adolfs torg | 3 | 80-100 | | Ulvsundavägen | 7 | 80-100 |
| Fridhemsplan | 7 | 76-100 | | | | |
| Västerbroplan | 3 | 80-100 | | | | |
| S:t Eriksplan | 5 | 80-100 | | | | |

MEASURED from that table: 155 controllers listed; the top of the range is exactly 100 s for 17 of 30 systems and 85 of 155 controllers. Report 07's "one corridor and a handbook" can be replaced by this.

Rules:
- Coordinated, by clock [S]: use the table. Where it gives a range, top value in peaks, bottom value off-peak. Matsis's example: P4 100 s 06-10, P2 80 s 10-14, P3 100 s 14-19, P2 19-22 (the text has a footnote mark on 22), then "nattetid släpps signalerna oftast fria". The 2020 report for Västerbroplan: P4 100 s 06-09, P3 100 s 09-18, P2 85 s 18-23. P1 is the isolated plan.
- Cap [S]: 100 s in the inner city under coordination (Del 7 71.1, 2012). Uppsala's is 120 s. Controllers can be set to at most 180 s, one group may go green twice per cycle.
- Share [S]: about 30% coordinated (160 of 546 in 2008). Systems of up to about 10 junctions for classic coordination, with the 21-controller Odengatan as the largest. Local coordination for 3 or 4 close junctions, 100-200 m apart, variable cycle.
- Unlisted systems [A]: controllers under 350 m apart on the highest-flow roads, clustered until the share is about 30%, cycles snapped to 70/85/100, the handbook's own example.
- Isolated, day [S]: traffic-actuated, with max greens. Worked example from the [adaptive report][adapt], Bergslagsvägen-Avestagatan, a 4-leg junction with protected lefts on the main road: main through F1+F4 max plus fråntid 42 s, side roads F3 and F6 30 s, left F5 max 15 s (temporarily 23 s, 32 s with fråntid), far detector 130 m. Budget: 42 + 30 + 15 + three changes of about 6 s = about 105 s. Handbook example of max green: 20 s and "t ex 30 sekunder".
- Isolated budget [A]: sum of max greens + lost time ≤ cycle cap of 100 s (120 s outside inner city). Netconvert's `maxDur=50` on every phase breaks this: **MEASURED,** on `v5_inventory` the fully-saturated cycle is 106 s at the median and 212 s at p90, up to 540 s, against 100 s. 585 of 903 controllers can exceed 100 s and 106 can exceed 180 s, more than any Stockholm controller is specified to run. Under load this matters: one extra 50 s phase is a 50 s longer red for everyone else.

External check on the same scale, MEASURED: Hamburg, one Friday, spacing of green starts per connection, 37 lights: **median 90 s in the morning, midday and evening, 75 s late evening**, p10 to p90 about 75 to 150 s, where the long values are mostly a group skipping cycles. Median green share per connection 25%, p10 9%, p90 67%. About 35 to 50% of connections ran an exact cycle (quartile spread ≤ 2 s). Perth, September 2026, 59 random sites, reported cycle per site: **median 88 s at weekday peak (p10 60, p90 147), 80 s by day, 64 s at night**, median 3 phases, largest phase 43% of the cycle at peak, and a typical site's peak cycle varies by 30 s. Stockholm's published 80-100 s fits. So does the netconvert nominal 90 s; its error is in structure, in max cycle and in equal split, not in that number.

### S6. Green split

- Flow ratio per phase: worst lane group `q / (n × s)`. `s = 1,900 veh/h/lane` until measured ([report 04](../04-validity-of-traffic-simulation.md) has discharge data).
- Equal saturation: `g_i = y_i / Y × (C − L)`. Floors from S4. Iterate twice for floors.
- Source for `q`: city counts if they exist, then Stockholm's `Arstrafik` counts, then assigned routes after convergence. Assigned flows make programs depend on demand: note that, and re-generate after route feedback only every few rounds. Without flows: lane count and road class, tested below as `nodemand`.
- Design check [V]: VGU Råd 10.3.3.2 says load in the worst lane should stay at or under 0.8 in a normal peak hour, computed with CAPCAL or similar. A generated program over 1.0 in a normal peak is suspect, and the place to look first for demand errors.
- Webster alone gives cycles that are too short at this 60% demand, so cycles come from S5, with Webster only as a floor.

### S7. Offsets

Progressive for the dominant direction by clock plan: `offset(b) = offset(a) + L_ab / v`. Start from the junction that sets the cycle (S:t Eriksplan: "the central junction's cycle sets the system"). Two-way bands: try the alternate-half-cycle pattern when spacing near `C × v / 2`, then pick with a bandwidth score. Non-coordinated: `offset` is meaningless. Random offset for the static ones. Never all zero.

### S8. Actuation, LHOVRA and fine logic

Tiers, build them in order:

1. **Phase actuation with SUMO's own logic.** `type=actuated`, `minDur` from floors, `maxDur` from S5's budget. Use for isolated, single-node. `cars` already runs this (`actuated.rs`). Set `max-gap` 3 s [S: interval 0-5 s].
2. **Detector positions.** [V] LHOVRA layout, VGU Råd figures 10.82 and 10.83:

| Function | 70 km/h, m from stop line | 50 km/h |
|---|---|---|
| L truck priority | 250 | not used |
| H main road | 180, 130 | 130, 90 |
| O accident reduction | 130, 80 | 90, 55 |
| V variable yellow | 80, 10 | 55, 8 |
| R red-running | 80 | 55 |
| A all-red turn | 130, 80, 10 | 90, 55, 8 |

At least 3 detectors on primary approaches, 2 on secondary. Long loop at stop line needs min green only. The handbook says LHOVRA was built for rural junctions and parts are used in cities. `cars`' `DETECTOR_GAP` is fixed from SUMO's defaults, so it needs a per-program setting.

3. **Behaviours worth adding, by likely effect on flows:** fråntid (extended green, usually ≤ 10 s, at most 15 s); `hänger kvar` (stays green until a conflicting call, "by far the commonest"); skipping a group with no call (`endast`), with `alltid` as the default under coordination; viloläge; O (seek a gap in the dilemma zone before ending green); V (yellow reduced by up to 2 s if the approach is empty, not with cycles in mix). Each needs a group-level controller in WGSL: group state is not in today's phase-list model.
4. **Bus priority.** `Priolampa` shows 149 installations. PRIBUSS functions: green extension (BF), recalled start (ÅTS), extra phase (EF), shortening (AK). Do after the bus model.
5. **Time-plan switching.** A program per clock period, switching at a fixed second. `cars` reads one program per controller and has no WAUT support (found no such code): builders must add this, or run one plan per time window at first. Change rule [S]: never cut red-yellow, min green or pedestrian clearance.

Pedestrians are not simulated. Assume a call every cycle in the inner city from 06 to 20 ([S] 71.1), reduce by share of push buttons elsewhere. This is a guess with real capacity consequences: side-road floors of 15 to 25 s come from crossing the main road. Hamburg's pedestrian detector streams could measure call rates.

### S9. Checks, as tests

Every generated program must pass: no conflicting `G` (from the net's foes), every link green at least once per cycle, yellow per S4 before any red, min greens met, one cycle within a system, cycle cap, and identical net topology to the input.

Realism:
| Test | Target | Source |
|---|---|---|
| Share coordinated | about 30% | Matsis |
| Cycle of coordinated | 70-100 s, mode 100 in peaks | Matsis, Del 7 |
| Max cycle, isolated | ≤ 100-120 s | Del 7, worked example |
| Phases per installation | Matches F group count | Register |
| Green share per approach | Within Perth and Hamburg ranges | Measured here |
| Named plans | Västerbroplan, Vasagatan, Valhallavägen reproduce their published cycles | Reports |
| Bus trajectories | Stop patterns repeat at the cycle | After a key |
| True plans | Direct comparison | If the request succeeds |

Traffic: A/B on the register net, one change at a time, per the factorial in report 02.

### Not in the spec, on purpose

Adaptive control: Stockholm rejected SPOT in 2005 and its later "smart" functions are limited tests at one junction, with mixed results in Vissim, so nothing suggests wide use. Tram logic, trains and bridge openings: rare, deferred. MOVA: not used as a Swedish standard here, as far as I can find (UNVERIFIED). SOS is a research algorithm from 1997, from the same group as LHOVRA. I found no evidence of it in Stockholm; the handbook doesn't mention it (searched its full text). So "SOS" in earlier notes can be dropped as a Stockholm assumption.

## Did generated programs cause the teleports?

**Not answered yet, by measurement.** What I have:

Measured on `v5_inventory`, comparing netconvert's programs with the prototype's on the same net and same 07:00-09:00 flows from `v5_r2` (MODELLED, a static screen):

| | Generated | Rule-based, cycle 100 s plans | Rule-based, Webster-limited |
|---|---:|---:|---:|
| Saturated cycle, median s | 106 | 100 | 70 |
| Saturated cycle, p90 s | 212 | 120 | 120 |
| Saturated cycle, max s | 540 | 122 | 124 |
| Lanes with flow over nominal capacity, of 1,791 loaded | 42 | 6 | 8 |

The screen uses displayed green and 1,900 veh/h, and ignores blocking, stubs and start-up, so it can't name a teleport count. Flows are 60% demand. It says generated programs have about six times as many over-capacity lanes, and red periods up to about four times longer under load. Most teleports in a lock-up come from spillback, which this screen can't see.

Report 02's own factorial points the same way: `--tls.join` alone goes from 1,721 to 8,572 by 10:00, and 51 of 103 stuck lane heads wait on red. That is consistent with programs being a large part, not a measurement of it. The 9,558 versus 631,888 gap also includes capacity from signals that don't exist in the low-teleport net, so generated programs can't explain all of it, and even good programs won't reach 9,558.

**The A/B that answers it for 00:00-10:00** (SUMO 1.28, register net, `v5_r2` demand, time-to-teleport 120, junction blocker 20; routes with missing connections dropped in every run, because SUMO refuses what `cars --trusted` accepts):

- `gen`: netconvert's programs.
- `plan`: rule-based, 100 s for coordinated and multi-node installations, as in the morning plan P4, with flows from the routes.
- `nod`: same, with no flows at all, from lane counts only, so not circular with demand.

Status when I stopped: queued in the homelab small slot as `run-c755662a` (agent-job `heavy-c531e14badc9`), each run capped at 25 minutes and running one after the other. Results:

```sh
cd /home/erikf/projects/personal/cars-data/datasets/signal-program-spec/run
agent-job status heavy-c531e14badc9
heavy pull gen.stat.xml plan.stat.xml nod.stat.xml gen.sum.xml plan.sum.xml nod.sum.xml gen.log plan.log nod.log
```

Read `teleports total` in each `.log` (from `--duration-log.statistics`) and the teleport line in the `.stat.xml`. Same-engine differences matter here: report 02 found `cars` teleports 35-64% more than SUMO on the same input, so `gen` will not equal 13,444. Compare `plan` and `nod` with `gen`, and don't compare them with report 02's number. If the small slot kills a run for memory (limit 3 GB), rerun with `heavy --big`.

Limits of the prototype, which also apply to that result:
- 693 of 903 programs are static, because a multi-node installation is one timeline. Real ones are actuated inside the plan, so its capacity is a bit low at uneven demand.
- Only 107 of 271 register left arrows found an approach: 164 could not be placed, since the prototype doesn't do S2 and many approaches have no left-only lane in the net. 173 of 763 axes with lefts got protection.
- Coordinated share is 20% against the real 30%. No time plans, no group logic, no pedestrians other than a floor. Simplified clearance geometry.
- A good `plan` result would show that realistic programs remove lock-up, not that they are Stockholm's programs. A bad one would point at the map or demand instead, which is worth knowing too.

## Open feeds elsewhere

- **Hamburg** (`tld.iot.hamburg.de/v1.1`): OGC SensorThings, MQTT too. Thing = one lane connection (`353_12`). Streams: `primary_signal`, `signal_program`, `cycle_second`, `detector_car`, `bus_checkout`, and cycle and pedestrian detectors. Status codes: 0 dark, 1 red, 2 amber, 3 green, 4 red-amber, 5 and 6 flashing, 9 unknown. History is queryable by date. Counts: 20,085 things, 80,276 streams, 6,579 car detector streams. Note: data recorded only when a light is online, 337 of my 720 windows were empty, and timestamps run to 2030 on a few streams, so filter.
- **Perth:** folder per month, one parquet per site. Columns include `Actual Cycle Time`, `Phase Time A` to `G`, `Phase Time`, `Measured Volume`, `Married` (coordinating), `Active Link Plan`. Detector map: `mainroadsopendata.mainroads.wa.gov.au/api/LmSaDetector/{site}` works with no key. TrafficMap also has site diagrams, phase sequence charts and link and offset plans per site (seen in its information sheet, not downloaded). This is the best open real-program data found. It runs SCATS, and drives on the left.
- **Netherlands:** Talking Traffic/UDAP is for road authorities and certified providers ([Traffic Technology Today][udap]). NDW's docs say V-Log needs a DEXTER account and live feeds a subscription (search result, not opened). A Utrecht request ([wob file][utrecht], not opened) suggests municipalities hand out V-Log on request. No open download found.
- **Vienna, Salzburg, Graz:** Austria has C-ITS live, per [AustriaTech's 2025 slides][at]. No open file. A Vienna request was refused as a "security vulnerability", per [an OSM forum thread][osmvie] (second-hand, and no decision read). That thread also says the vendor holds the data and that reprogramming costs tens of thousands of euros per crossing: UNVERIFIED, and useful to know.
- **Tampere:** the portal lists an open real-time API under CC BY 4.0, with volumes and queues. `trafficlights.tampere.fi` timed out twice from here on 2026-11-02. Metadata date 2017. Treat as dead until shown otherwise.
- **Sweden:** MEASURED absence in what I searched: no open SPaT or MAPEM feed. NordicWay shows Gothenburg, Uppsala and Trafikverket pushed SPATEM to a partner interchange, with latencies of 200 to 1,600 ms in 2020, and Stockholm took part in time-to-green and bus priority tests. Closed.

## Inferring timing from data

| Method | Data | Result | Grade | Fits Stockholm? |
|---|---|---|---|---|
| [Liao et al. 2025](https://arxiv.org/abs/2507.14190) | 3 s FCD, 7.1 M trajectories, 10,304 intersections, production in a Chinese navigation platform, 15 M records a day for 2 M signals | Cycle within 5 s for 91% overall, 94% at Beijing rush hour, 71% off-peak Shenzhen. Handles changing time plans | PROVIDER CLAIM, with vision ground truth | Method yes. No such data here |
| [Fayazi et al. 2014](https://cecas.clemson.edu/~avahidi/wp-content/uploads/2016/11/Fayazi_J1_Draft.pdf) | Public bus feed, San Francisco, about one update per 200 m, a bus every 5 to 10 minutes | Cycle and red from a few days at fixed-time signals. Checked at one junction | PROVIDER CLAIM | **Best fit**: Trafiklab's feed is denser. Weak at actuated signals |
| [Ugirumurera et al. 2023](https://arxiv.org/abs/2308.02370) | XGBoost plus NN on probes from a calibrated SUMO model, Chattanooga 39 intersections, real plans as truth | Cycle error under 0.56 s, red 7.2 s | MODELLED. Trained on simulated probes | Warns that the good numbers come from a model |
| Yu and Lu, AGCD (via the papers above) | Low-rate taxis | Cycle at fixed-time | Not opened | Later methods beat it per Table II above |
| Amap, Uber | | **Found no published method.** Google's [Green Light](https://sites.research.google/greenlight/) uses Maps trends and gives advice to cities, without sharing the underlying timing | Dead end for data | Google could tell Stockholm, not us |

Limits for Stockholm: actuated and skip-capable signals have no fixed cycle, so every method here does worst where most Stockholm signals sit. Bus stops near signals and bus priority at 149 installations both bias bus-based estimates. The result is best used as a check of cycle length on coordinated corridors.

Video: Jinan (Yu 2023) and any traffic cameras could read queue discharge. Report 01 and Trafik Stockholm cameras are out of scope here.

## Dead ends

- Tampa SPaT data id `mfvh-n8ma` gave 404. A catalog page exists, sample only.
- Main Roads WA catalogue page for real-time data: 404 today, with a disruption notice elsewhere. WebSocket demo page exists, Wikipedia says "previously". Use parquet.
- Transport for NSW: refused SCATS phase data "as a matter of policy", [Walk Sydney][walk].
- Webster alone as the cycle rule: cycles fall to 50-70 s at this demand, off the city's values.
- Better Intersections site: only its title loaded here. It is a crowdsourced signal timing map, per its author's forum post. Not opened.
- Local `nix shell nixpkgs#...` hung on a Nix lock, and the local `duckdb` hung on every query. Use a store path Python, and pyarrow via `nix-store -qR`.
- A VGU 2004:80 Del 13 full PDF: not found. `docplayer.se` doesn't resolve from here. Tammergård's table cites it, and the current Råd has the same layouts.

## New directions I noticed

- **Hamburg's streams let a builder test actuation itself:** detector calls and resulting greens at the same second, for hundreds of junctions, which is unusual. Good for validating `actuated.rs` against real signals, not just SUMO.
- **Perth joins timing with detector counts per cycle,** so it offers saturation flow by site with real green. That helps report 04's discharge question.
- **OpenTrafficMap's receiver** if Stockholm signals ever broadcast. NordicWay shows the city tested it. A €20 receiver near Sergels torg could answer this in an afternoon, with Erik on site.
- **Stockholm's `Tryckknapp` and `Varningslykta`, `Wigwag` layers** show button and emergency signals. Fire stations affect programs rarely, but they're mapped.
- **The 2020 thermal camera thresholds** (P2 ≥12, P4 ≥29, P3 ≥38 vehicles per 3 minutes at detector D1, for example) are real volume-to-plan rules, a small real calibration of when peak plans apply.

## Files

- Scripts: `research/truth/data-hunt/scripts-11/` (`swedish_tls.py`, `tls_stats.py`, `register_groups.py`, `numbering_test.py`, `hamburg_sample.py`, `hamburg_stats.py`, `perth_stats.py`).
- Data: `/home/erikf/projects/personal/cars-data/datasets/{signal-docs-sweden,hamburg-tld,perth-scats,signal-program-spec}/`.

## Sources read

- [del7]: Stockholm Teknisk handbok samlingsdokument 2012, Del 7 Trafiksignaler. Read section 70-73. https://tillstand.stockholm/globalassets/foretag-och-organisationer/tillstand-och-regler/tillstand-regler-och-tillsyn/mark--och-gatuarbeten/teknisk-handbok-for-byggande-drift-och-underhall-pa-offentlig-mark/teknisk-handbok-samlingsdokument-2012-10-01.pdf
- Handling 05.04 Styrteknik, Trafikkontoret 2015. All 40 pages of text; figures not read. Same folder, `05.04-styrteknik-styrapparater-v1.pdf`.
- [matsis]: Kronborg, Matsis, 2008-12-02. Read sections 3, 4.3, 5, 6, 7.3. https://insynsverige.se/documentHandler.ashx?did=104694
- Trafikstyrda tidplaneval, 2020-02-21. All. https://skonhetsradet.stockholm/wp-content/uploads/sites/10/2020/09/Rapport-trafikstyrda-tidplaneval-resultat.2020021.pdf
- [adapt]: Trafikstyrda tidplaneval och förbättrad adaptivitet, 2019-09-03. All text; tables are images, not read. https://skonhetsradet.stockholm/wp-content/uploads/sites/10/2021/01/Rapport-adativa-funktioner.pdf
- TSFS 2014:30. Chapters 1-2 in full. https://www.transportstyrelsen.se/tsfs/TSFS%202014_30.pdf
- SKL, Kör när det är grönt, 2017. Sections on the rules; not the whole book. https://extra.skr.se/download/18.45167e4317e2b341b24ad3d0/1642682743800/7585-566-0.pdf
- VGU Råd, TRV 2022:003. Section 10.3.3 including figures 10.82-83. https://trafikverket.diva-portal.org/smash/get/diva2:1621302/FULLTEXT03.pdf
- VGU Krav remiss 2024-07-01. Section 9.2.3, definitions; a draft. https://bransch.trafikverket.se/contentassets/a0cd02aa9edc466aa43707d2066a33c5/remiss_vgu_2024.pdf
- [upp]: Uppsala Teknisk handbok Trafiksignaler v1.1, 2024. All. https://tekniskhandbok.uppsala.se/globalassets/teknisk-handbok/dokument/tekniska-anlaggningar/th-trafiksignaler-ver-1.1.pdf
- Tammergård, Intelligent styrning av trafiksignaler. LHOVRA table and Epics section only. https://www.k2centrum.se/wp-content/uploads/2025/02/tammergard_intelligent_styrning_av_trafiksignaler.pdf
- Cykeltrafik och trafiksignaler. Skimmed: says cycles should if possible stay under 80 s in the peak, for cyclists' sake. http://www.exempelbanken.se/Uploaded/ExampleDocuments/980191521/original/3204_cykeltrafik_och_trafiksignaler.pdf
- NordicWay 2 Activity 9 final report; sections on signals. https://cdn.prod.website-files.com/5c487d8f7febe4125879c2d8/5fe31251770a09c2b1b33b96_NW2_A9_%20Final%20report_ver1.0.pdf . NordicWay 3 page: https://www.nordicway.net/flagship/traffic-signals
- OSL 18 kap. 8 § and TF 2 kap. 18 §: https://lagen.nu/2009:400, https://lagen.nu/1949:105
- Hamburg archive: https://doi.org/10.25532/OPARA-466 . API: https://tld.iot.hamburg.de/v1.1
- Perth: https://www.arcgis.com/home/item.html?id=327c0f079090426c8e1e64b07972b3ee , info sheet https://reportingcentreresources.mainroads.wa.gov.au/pdf/TrafficMap_Information_Sheet_Traffic_Lights.pdf , data dictionary in the SharePoint folder.
- [walk]: https://walksydney.org/2025/09/20/why-wont-transport-for-nsw-share-scats-traffic-signal-phasing-data/
- [osmvie]: https://community.openstreetmap.org/t/city-of-vienna-traffic-signal-timing-data-request-anfrage-nach-ampelzeitdaten/144832
- [udap]: https://www.traffictechnologytoday.com/?p=27105 (search result only). [at]: https://austria-in-space.at/resources/pdf/events/03-20250129-pole-position-with-satellite-navigation-pnt-meets-mobility-austriatech.pdf (search result only). [utrecht]: https://www.utrecht.nl/fileadmin/uploads/documenten/7.extern/wob/2023/2023-0091_V-Log_aanvraag_tbv_verkeersongeval/verzoek.pdf (search result only).
- ONE Nordic: https://www.mynewsdesk.com/se/one-nordic/pressreleases/one-nordic-ser-till-att-stockholms-trafikanlaeggningar-fungerar-3229049 . TED notice 2021: https://ted.europa.eu/en/notice/600039-2021/pdf . OmniVue decision: https://insynsverige.se/documentHandler.ashx?did=105886

[del7]: https://tillstand.stockholm/globalassets/foretag-och-organisationer/tillstand-och-regler/tillstand-regler-och-tillsyn/mark--och-gatuarbeten/teknisk-handbok-for-byggande-drift-och-underhall-pa-offentlig-mark/teknisk-handbok-samlingsdokument-2012-10-01.pdf
[matsis]: https://insynsverige.se/documentHandler.ashx?did=104694
[adapt]: https://skonhetsradet.stockholm/wp-content/uploads/sites/10/2021/01/Rapport-adativa-funktioner.pdf
[upp]: https://tekniskhandbok.uppsala.se/globalassets/teknisk-handbok/dokument/tekniska-anlaggningar/th-trafiksignaler-ver-1.1.pdf
[walk]: https://walksydney.org/2025/09/20/why-wont-transport-for-nsw-share-scats-traffic-signal-phasing-data/
[osmvie]: https://community.openstreetmap.org/t/city-of-vienna-traffic-signal-timing-data-request-anfrage-nach-ampelzeitdaten/144832
[udap]: https://www.traffictechnologytoday.com/?p=27105
[at]: https://austria-in-space.at/resources/pdf/events/03-20250129-pole-position-with-satellite-navigation-pnt-meets-mobility-austriatech.pdf
[utrecht]: https://www.utrecht.nl/fileadmin/uploads/documenten/7.extern/wob/2023/2023-0091_V-Log_aanvraag_tbv_verkeersongeval/verzoek.pdf
