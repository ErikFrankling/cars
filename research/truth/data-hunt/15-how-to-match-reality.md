# 15: How to make a city simulation match a real day

Checked 2026-11-02. Nobody was contacted. No GPU was used. Grades: **MEASURED**, **PROVIDER CLAIM**, **MODELLED**, **UNVERIFIED**. Most fit numbers below are MODELLED against MEASURED, reported by the model's own authors. I found no independent audit of any project.

## The answer

**Nobody has shown a microscopic simulation of a whole city matching real traffic on data it wasn't fitted to.** Whole cities have been run microscopically, but that isn't the same thing. The largest honest attempt is Barcelona: 2.06 million trips over 24 hours, R² 0.81 and error 0.38 on daily counts, 38% of sites at GEH<5, about 5% of cars teleported. That was on the same counts it was tuned against. Its author concludes that an exact traffic twin of a city is still far off.

**How close a real day gets to another real day.** I measured this on Berlin's detectors, in the same units the papers use. One whole site's hourly count scores error 0.19, R² 0.90 and 89% GEH<5 against the same site a week later. No published city model I opened gets near that, even on its own training data. The best in-sample hourly figure I found for a city road network is 0.32, in Salt Lake City. So the gate's basic bar, "no further from a real day than another real day", is an unbeaten record, not a normal pass mark. We should keep it and expect to report a gap.

**What works is a fixed order.** Serious projects fix the map and capacity first, then check at 50% demand that nothing jams. Then they take a decent demand estimate from independent data and fit routes. Only then do they nudge demand gently toward counts, and tune local spots last. We've been doing close to the reverse: demand fitted to estimated counts, on an unchecked map with made-up signals, then scaled to 60% to stop lock-up. Our best Stockholm day now runs at a flat 42–44 km/h all day, with no rush hour at all.

**The realistic bar** is a statistical match by road class and hour, flows within about 30–40% site by site, totals within 10%, and the main jams in the right place within about 30 minutes. That would equal or beat anything published on held-out data.

## How to read fit numbers: what a real day scores

No paper gives this, so I computed it. Berlin detectors, September 2024, Tuesday to Thursday, same detector seven days apart, 12 weekdays, all vehicles. MEASURED. [Script](scripts-15/noise_literature_units.py), [output](15-berlin-noise-literature-units.json). RMSN is root mean square error divided by the mean, the same thing as nRMSE in the Google papers. Barcelona's formula is the same.

| Real day against real day | RMSN | WAPE | R² | Slope | GEH<5 |
|---|---:|---:|---:|---:|---:|
| Whole site, hourly, 07–18 h | **0.19** | 9.1% | **0.90** | 0.94 | **89%** |
| Whole site, hourly, all 24 h | 0.26 | 10.3% | 0.91 | 0.94 | 91% |
| One lane, hourly, 07–18 h | 0.27 | 12.5% | 0.77 | 0.84 | 89% |
| Whole site, one day against the mean of other days | 0.17 | 8.3% | 0.92 | 0.98 | 90% |
| Whole site, **daily total** | 0.08 | 4.8% | 0.97 | 0.99 | **69%** |

Network level, 91 sites over 10 days: daily total varies 1.7%, a typical hour's total varies 3.0%, hourly shares of the day differ by 0.15 percentage points on the same weekday. The morning peak hour was 08:00 on all 10 days. The afternoon peak hour was 15:00 or 16:00.

Three things follow.

1. **GEH<5 on daily counts is a nearly impossible test.** A real day only gets 69% against another real day. Barcelona's 38% is on daily counts, so it's harsher than it looks, and any ">85% GEH<5 on daily counts" target would fail reality itself.
2. **Slope and R² flatter a model.** A lane scores R² 0.77 against itself a week later. Fremont's 0.845 at 15 minutes looks close to that, but its RMSN is 0.47.
3. **Limits:** one city, one month, detectors on main roads, some faulty detectors probably included, hourly only. 15-minute noise is higher and I can't measure it here. Stockholm's floor still has to be computed the same way once real data arrives.

## Ranked table: who got closest

Ranked by how much the result says about matching reality, not by size. "Held out" means data not used for any fitting.

| # | Project | Type, scale | Fit on fitting data | Fit on held-out data | Read |
|---|---|---|---|---:|---|
| 1 | **Des Moines**, MITSIMLab, ~2004 | **Micro**, all major roads, 200 sq mi, 3,756 links, ~250 signals, AM and PM peaks | About 90% of points within 100 veh | **Travel times on 4 corridors: +4%, +2%, −4%, +40%** | Full |
| 2 | **Zurich**, MATSim + Cadyts, 2010 | Queue model, 10% sample, 187,484 agents, full day | 10–15% count error, 80% better | **10-fold on 161 sensors: about 30% better than uncalibrated.** No absolute error given | Full |
| 3 | **New York**, MATSim, 2021 | Queue model, 4% sample | Speeds 7.2% freeway, 17.1% arterial; screenline +1.8% | **46 road counts: median 29%, mean 39.8%** | Part |
| 4 | **Stockholm Brunnsviken**, MITSIMLab, 2002 | Micro, small mixed network | Not read | **Second dataset a year later** for flows, travel times, queues. Numbers not read | Abstract |
| 5 | **Stockholm trial**, SILVESTER and METROPOLIS | Meso | 95% of link flow variability, 59 links | **Real change −18.1%; models −25.3%, −12.4%** | Via report 15 |
| 6 | **Bay Area Mobiliti**, 2023 | Meso, 19M trips | Demand taken from SFCTA's model, which has its own calibration; not fitted to these counts in this paper | 72% of 2,061 links with time-series R²>0.7; 55% speed R²>0.4; 7 of 8 bridge directions within ±25%; VMT −7%. Rerouting share was chosen by best fit | Part |
| 7 | **Barcelona**, SUMO, 2022 | **Micro**, 182 km² core, 2,506 km, 2.06M trips, 24 h | R² 0.81, RMSN 0.385, 38% GEH<5, about 5% teleports | None: settings tuned on the same 488 detectors | Part |
| 8 | **Fremont**, Aimsun, 2022 | **Micro**, 21 km², 4,705 links, 37 signals, 130,000 cars, 6 h | R² 0.845, slope 0.976, **RMSN 0.47** at 15 min | Mid-stage only: fit slope 0.92 and R² 0.91, test slope 1.30 and R² 0.81 | Full |
| 9 | **I-210, Los Angeles**, Aimsun, ~2022 | **Micro**, corridor, 1,000 lane-miles, 465 signals, all week | Most periods >85% GEH<5, totals within 5%, one run each | None found. Same sets "calibrate and validate" | Ch. 7, 19 |
| 10 | **Singapore SimMobility**, 2017 | **Micro**, CBD, 1,200+ intersections, **only 48,988 trips** | RMSN 0.72→0.37 on 360 sensors | None | Part |
| 11 | **Singapore expressways**, DynaMIT, W-SPSA | Meso | Counts 0.426→0.216, speeds 0.321→0.164 | None | Part |
| 12 | **San Francisco**, Dynameq, 2012 | Meso, evening peak | 13% low everywhere, RMSE 55% at 15 min, about 40% hourly above 500 veh; 65% of links in bound, 47% of turns | Not separate | Part |
| 13 | **Salt Lake City**, Google, 2021 | SUMO, 429 roads | RMSN 1.20→0.32 hourly (SPSA stayed at 1.17) | None | Full |
| 14 | **Six US metros**, Google, 2025 | SUMO, **highways only**, each hour fitted alone | 43.5% better than SPSA; no absolute error in the paper | None. "Satisfactory" fit everywhere "remains challenging" | Full |
| 15 | **Melbourne**, Aimsun, 2017–18 | Meso, 55,719 links, 2.1M cars, 06–10 only | CBD RMSE −50%, R² 0.53→0.92 | Journal paper blocked. An R² 0.75 on Google travel times is only a search excerpt: UNVERIFIED | Abstract, README |
| 16 | **Sydney**, 2016 | Meso | 80% of 322 points in bound | Warns link fit alone isn't enough | Abstract |
| 17 | **Beijing**, DynaMIT-P, 2012 | Meso, 18 sq mi, 630,000 cars, 4 h | Numbers not read | Not known | Abstract |
| 18 | **Berlin**, MATSim, 2019–24 | Queue model, 10% | 346 stations fitted | Report 03: 0.93 of counts at fitted sites, **0.75 across the official network**. Newer version says volumes "generally too low" | Part |

**Those Berlin numbers are the clearest evidence in the list.** The same model scores 0.93 where it was fitted and 0.75 where it wasn't.

## What each project did, in order

**Fremont** is the only one that publishes its whole recipe with hours, so it's the template. [Paper](https://bayen.berkeley.edu/sites/default/files/creating_calibrating_conference.pdf). Full text read.
- *Started from:* OSM, city signal plans, SF-CHAMP demand plus a StreetLight study, 83 detectors.
- *Order:* (1) clean map by hand against satellite and Street View. (2) Run **50% demand and check nothing jams**, then full demand and look at sites under 50% or over 200% of real flow. (3) Scale total demand to boundary counts, no simulation. (4) Small OD adjustment with a static assignment, with a large penalty for moving from the prior. (5) Choose route model. (6) Reduce 35 parameters to 10 by sensitivity, then a genetic algorithm.
- *Time:* **about 2,500 person-hours**: 600 map, 600 demand, 400 traffic data, 500 fixing 43 logged errors. Signal setup took the longest in the map work.
- *Checks:* delay over time, then flow regressions per 15 minutes, speed distributions, time-space plots of I-680 by eye.
- *Admitted:* no reproducible way to make accurate demand exists; the prior was biased toward San Francisco; Aimsun's default OD adjustment overfit; the 47% error isn't good enough for the city's engineers to use as is.

**I-210** shows what "85% GEH<5" costs. [Report](https://escholarship.org/uc/item/1xw8q5j1). Chapters 7 and 19 read.
- *Started from:* PeMS, signal detector counts, agency counts, traffic studies, an LA Metro truck survey, every signal coded. Reference flow is the mean of five consecutive days, only from detectors with at least 80% data. Paths compared with Google and Waze.
- *Tuned by hand, section by section:* lane-change cooperation 50–100%, aggressiveness 0–65%, queue-discharge acceleration from ×0.5 to **×5**, **negative** reaction-time additions, look-ahead per turn, added route costs per section.
- *Admitted:* one run per period because more took too long. Detectors seem to undercount in congestion. 1–3% of data points are suspect. On freeways they favoured speeds over flows to keep ramp meters behaving.
- *Read:* it's very good on its own data, but with that many local dials the result doesn't prove the model predicts anything.

**San Francisco** shows how close to gridlock these models sit. [Report](https://sfcta.org/sites/default/files/2019-03/SFDTAFinalCalibrationandValidationReport.pdf).
- To avoid gridlock they **cut effective car length from an observed 24 ft to 21 ft**. A change of 0.5–1 ft moves downtown between light and heavy congestion.
- A 20% cut in gap acceptance or follow-up time clears moderate gridlock. Response time was set below observed values.
- Traffic spread onto streets without counts, so they added a route cost penalty on minor roads.
- Temporal profile came from PeMS counts at four entry points. Transit-only lanes first caused gridlock. Signal plans needed manual fixes.
- *Admitted:* trucks, parking, pedestrians and outside trips are weak.

**Barcelona.** [Paper](https://doi.org/10.3390/ijgi11010024). Discussion, method and appendix read.
- *Demand:* phone-derived OD, which overestimates trips, so scaled per subarea to surveys. Hourly histograms from surveys, skew-normal peak correction for direction. 3.19M trips, 2.06M touching the core, through traffic included.
- *Tuned:* rerouting probability, a road-priority weight in route choice, step length. Only 2–3 parameters. Best rerouting probability was 1.
- *Key finding:* time-only route choice underloads main roads. A road-hierarchy preference improves the fit. Same result as San Francisco, and it matches our Stockholm finding of starved motorways.
- Its Table A1 reviews 13 large urban micro scenarios. Most validate qualitatively or at few sites. Cologne, Monaco and Turin are qualitative. Bologna covers one hour.

**Zurich.** [Paper](https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2010/10-07/20100801-submitted.pdf). Synthetic population from census, agents adapt routes, departure time and mode for 500 iterations, Cadyts rewards plans that help counts. Under 21 hours on one machine, under 10% extra cost. It moved the daily rhythm of demand toward counts. *Admitted:* corrections are tied to the network, so they don't carry over if you add a lane. Too few sensors reach all agents.

**New York.** [Paper](https://arxiv.org/pdf/2008.04762). Speed by road type and hour first, from INRIX, then SPSA on link capacity factors using 19 crossings. Validate on 46 other links and ten subway stations. Tuned 0.15 flow capacity for a 4% sample.

**Des Moines.** [Paper](https://wctrs-society.com/wp-content/uploads/abstracts/istanbul/1363.pdf). Joint OD and behaviour calibration on about 400 sensors at 15 minutes. Real problems they report:
- Over 80% of OD pairs had under 1 vehicle per hour, yet carried about 15% of demand, so they had to be merged.
- One bad detector on a parallel street made the freeway impossible to fit, so sensors must be audited first.
- Small coding errors are punishing at this scale.

**Singapore SimMobility.** [Paper](https://web.mit.edu/cami/Public/CLA_SimMobilityST_TRB_2017.pdf). 11 route and 112 driving parameters plus demand, W-SPSA, 250 iterations, SCATS phases, taxi GPS OD times. It's the closest published analogue to us, and it's a CBD with 49,000 trips, tuned and tested on the same counts. Report 15 didn't mention the trip count.

**Beijing.** [Abstract](https://dspace.mit.edu/handle/1721.1/99219), PDF rate limited. Early attempts failed with unrealistic queues building on ring roads. What fixed it: Path-size Logit routes, explicit lane groups for queues, a capacity fix for very short links, dynamic capacity for bicycles and pedestrians, all parameters fitted together. **Same failure site as ours: very short links.**

**Melbourne.** [Abstract](https://trid.trb.org/View/1438614), [repo](https://github.com/meeadsaberi/dynamel), [later description](https://arxiv.org/pdf/2011.11892). Capacity curves first, from months of freeway loops. Then bi-level OD at 15-minute steps. Later joint OD and signal timing by SPSA. Free model, but needs an Aimsun licence.

**Stockholm work to build on:**
- [Brunnsviken](https://bibliotek.vti.se/bib/258412): iterative OD, route and driver fitting, validated a year later. The temporal holdout we should copy.
- [SAMPERS with DTA packages](https://www.transportportal.se/swopec/CTS2014-10.pdf): right order of size with moderate network work, wrong time profile on Essingeleden, full use needs signal and junction coding. Workshop participants said signals could be taken from the city's databases.
- [Linköping thesis, Wei 2026](https://trid.trb.org/View/2752029) (record only): central Stockholm OD from phones, counts, turning shares and GPS, link capacities by PLS regression, better than SPSA. No numbers in what I could read.
- [CODE PROBE](https://fudinfo.trafikverket.se/fudinfoexternwebb/Publikationer/Publikationer_007601_007700/Publikation_007670/CODEPROBE_final_Report.pdf) (summary read): five weeks of GPS, phone, SAMPERS and counts in Stockholm. GPS covers a few percent of the fleet. Hourly link-flow estimates explain much of the variation but errors are large on thin links. **The Swedish stack we need already exists at LiU.** Report 05 has the data details and a draft.

## Methods: what the evidence supports

| Method | Evidence | Verdict for us |
|---|---|---|
| **Scale to boundary counts** | Fremont, San Francisco's entry profile | Do first. Cheap, safe |
| **GLS with a prior** | Fremont: unregularised fit gets training R² 0.91 and test slope 1.30, so they made the prior penalty very large | Use, with a strong prior and a test set |
| **SPSA** | Stalls in high dimensions: Salt Lake 1.20→1.17 in 15 iterations; [Singapore](https://web.mit.edu/cami/Public/CLA_WSPSAinPractice_ISTTT_2015_preprint.pdf) stalled at high values | Not plain |
| **W-SPSA** | Same 2 runs per iteration, with a sparse map of which sensors each OD affects. Singapore expressway 0.43→0.22 | **Yes.** Fits a GPU that makes runs cheap |
| **Metamodel (Osorio, Google)** | Best per run: [Salt Lake](https://arxiv.org/pdf/2109.11392) 1.20→0.32 in 15 iterations. [Six metros](https://arxiv.org/pdf/2501.04783) | Worth trying when runs get scarce. Needs route shares fixed |
| **Cadyts** | Zurich, Berlin. Adjusts choices, not OD | Good idea to reimplement. Corrections don't transfer |
| **Travel times or speeds as the target** | Abundant, but weak on demand. [Google's Seattle test](https://arxiv.org/pdf/2502.19528), with known truth: fit to travel times alone leaves demand error about 2.04, a 15% count sample cuts it to 0.72 | Use both. Never times alone |
| **Joint demand and supply** | [Balakrishna](https://dspace.mit.edu/handle/1721.1/35120) (abstract): better than sequential, shown on a synthetic network. Beijing needed it. FHWA says supply, then routes, then OD last | Sequential first, so errors stay visible. Joint only at the end |
| **Differentiable models** | Analytic surrogates work (Google, UNsim in report 06). Report 06: gradient methods recover OD only with sensors on every link | Coarse surrogate only. **I found no differentiable microsimulator with lane changes fitted to a real city** |
| **Learned simulators** | [LCSim](https://arxiv.org/pdf/2406.19781) in Jinan and Shenzhen: over 90% of trips within 20 s of real arrival, but each car is *given* its real schedule as a goal. That's replay | Not a prediction test. Don't count it |
| **Generated OD** | MOSS reports Spearman 0.741 Beijing, 0.488 Shanghai: search excerpt, UNVERIFIED | At best a prior |
| **Phone data** | Barcelona: overestimates trips, needs survey scaling. Reports 05 and 06 | Best single demand prior we could buy, after scaling |

**One more warning.** [The Calibration Illusion](https://arxiv.org/pdf/2608.19642) (MIT and others, August 2026, working paper) tested automatic calibration on real highway data with an open benchmark. It finds a lot of undocumented manual work behind "automatic" methods, a 10% change in time step can upset results, and **every method failed to reproduce stop-and-go waves at large scale**. It also says performance falls as scenarios grow and is worse than the literature implies. [Wang et al.](https://arxiv.org/pdf/2409.19090) cite earlier work showing drivers individually calibrated from trajectories still miss congestion propagation. So our careful driver model won't give us the jams by itself.

## What it took to get rush hours in the right place at the right time

Nobody claims to have solved it across a whole city and a whole day. What people did:

1. **Most avoid it.** Melbourne fits 06–10, Beijing 4 hours, San Francisco 15:30–18:30, Bologna one hour, Des Moines two peaks. Google fits each hour separately. Barcelona, Zurich, Mobiliti and I-210 are the full-day exceptions I found.
2. **Departure times come from measurements, by direction.** Barcelona: survey histograms with a directional correction. San Francisco: counts at entry points. I-210: separate matrices per period. Zurich: Cadyts shifts plans between hours. Report 03 shows why survey starts aren't enough: on Berlin roads the survey's shape was further off (1.01 points) than the simulation's (0.70).
3. **Count at passage time, not departure time.** Report 06 already says this.
4. **The bottleneck has to have the right capacity.** FHWA's [DTA guide](https://ops.fhwa.dot.gov/publications/fhwahop13015/sec8.htm) puts bottlenecks first. Queues must form where the existing-conditions report says, and OD adjustment is a last resort.
5. **Then most of them tune the local spot.** I-210 and San Francisco did it openly. Without that, jams are in the wrong place.
6. **Checks stay visual.** Fremont, I-210, Barcelona and New York compare time-space plots or maps by eye. I found no city project publishing a score for jam location and timing. [Treiber and Kesting](https://arxiv.org/pdf/1008.1639) offer real criteria for freeways. That's a gap we can fill, and a contribution in itself.

## What we are doing wrong

Having read reports 02, 03, 04 and 06, plus the current report page.

| # | What we do | Why it's wrong | Evidence |
|---|---|---|---|
| 1 | **Whole city first.** 34 × 30 km Stockholm, Berlin | Fremont spent 2,500 hours on 21 km². Errors in a big net can't be traced | Fremont; Des Moines |
| 2 | **Demand fitted to counts, and those counts aren't measurements.** 99.55% of the features are "Skattad trafik" from 2016 | Counts validate, they don't identify. Using the same counts to check is circular | Report 02, 06 |
| 3 | **Scale to 60% to stop lock-up** | Hides the failure. It leaves 60% of real cordon traffic, motorway km at 32% of target and **a flat 42–44 km/h all day**. TomTom's Stockholm figures of about 26 km/h morning and 20 km/h evening aren't the same measure, but no rush hour at all is plainly wrong | Report 02 |
| 4 | **Optimise for fewer teleports** | Over ten route-choice iterations teleports went 284k→54k while held-out error moved only 79.5%→77.3% and flow stayed at about a third (0.28→0.34). Lock-up and realism are different problems | Report page |
| 5 | **Map chosen because it jams least.** 457 lights against 519 real | Capacity from signals that don't exist. Real positions with made-up plans give 631,888 teleports | Report 02, 07 |
| 6 | **Supply never checked against reality.** "No saturation flow or queue has been compared with observation" | Everyone else does this first. τ and dt are one parameter, motorway capacity 19%+ too high at dt 0.1, wave speed wrong | Report 02, 04 |
| 7 | **Hourly profile invented.** Jump ×7 at 06:00, one curve for all roads | Real peaks differ by place: Essingeleden 6–7% in peak hour against 12% at Bålsta (report 02's first draft, its review couldn't recheck the PDF) | Report 02 |
| 8 | **Missing vehicles.** Berlin has 8.3% trucks at detectors and buses, modelled with one car type; Stockholm has no through trips or trucks | Berlin MATSim names commercial traffic as its main gap too | Report 03 |
| 9 | **Route choice by time only** | Barcelona and San Francisco both needed a preference for main roads. We haven't tested it, and it may explain starved motorways | New |
| 10 | **Fixed trip lengths and "fragments"**, now improved | Report 02 fixed much of this. Keep the cordon test | Report 02 |
| 11 | **Benchmarked against other simulators' scenarios** | BeST "matches" at four plots; 14% of 149 sites are within ±20% | Report 03 |
| 12 | **AV work ahead of human validation** | Now banned by the gate | Gate |

**What we already do right, which most projects don't:** a frozen hold-out (260 of 847 measured sites plus all 2025 values), teleports treated as failures, a measured noise floor, report 06's guards on how far OD may move, connection bans now honoured in `net.rs` (commit `76719b4`, so report 02's note on that is out of date). And our speed is a real edge: published teams get a handful of runs where we could do hundreds. At the measured 148 s per Berlin day, 500 runs is about 21 hours, GPU queue permitting.

## The recipe

Each step has an exit test. If it fails, fix that step and don't move on. Don't use later steps to hide earlier faults. Thresholds are proposals (opinion), based on the sources above.

**Inputs needed**

| Input | Minimum | Better | Used for |
|---|---|---|---|
| Map | OSM plus manual fixes | National road database lanes | Everything |
| Signals | Real plans at all main junctions | Plans plus detector logic | Capacity |
| Demand prior | Commuting registers plus survey | Phone OD or base-year regional model | Step 4 |
| Trucks, buses, through traffic | Separate tables | Gantry or toll data | Step 4 |
| Counts, hourly, dated | 100+ real sites, none estimated | Lane-level, 15 min | Steps 6, 9 |
| Speeds by hour | Probe data, same dates | Travel times on named routes too | Steps 7, 9 |
| Same-period weekdays | 10+ days | Across several weeks | Noise floor |

**Step 0. Pick a district, not a city.** 20–50 km², with real signal plans, hourly counts and probe speeds for the same dates. The city is whichever has that data, whatever we used before. Then grow: corridor, district, city. *Exit:* an input table labelled measured, estimated or invented, per gate rule 3.

**Step 1. Freeze the test, before any fit.** Choose the day and hold out whole sites, whole corridors and whole days. Write the metric code. Run it on real day against real day. *Exit:* a noise-floor table for every gate check, the same way as the table above, plus the jam-location score.

**Step 2. Fix the map, with demand low.** Check connectivity, lanes, turn bans, bus lanes, ramps, links under a car length. Log every issue. Fremont logged 43, on a map a fraction of ours. Run 10%, then **50%**, teleports off. *Exit:* no persistent queue anywhere at 50%, nothing stuck. Anything left is a coding error. Don't touch demand.

**Step 3. Check capacity without a city.** Isolated tests per road class at real speeds: saturation flow, motorway capacity, jam spacing, wave speed, capacity drop, all in report 04's bands. Decide τ and dt here. Put real signal plans in. *Exit:* report 04's Level 2 bands, discharge within 10% of measured at sampled junctions. Keep every value inside measured ranges. San Francisco's 24→21 ft is how you end up with a model that's right for the wrong reason.

**Step 4. Build demand from independent data, with no simulation.** Registers, phones or regional model, scaled by survey. Add trucks, buses, through trips separately. Departure curves per area and direction. *Exit, on static checks:* total vehicle-km within 15% of official, trip length within 10% of survey, cordon within 15%, peak not invented. **Do not use validation counts here.**

**Step 5. Route assignment until stable.** Use report 06's loop: capped switching, teleports off, departure time last. Test a main-road preference against time-only. *Exit:* relative gap stable under 5%, traffic share by road class within 15% of targets, sampled routes look like Google or probe routes, no gridlock at 100%. If it jams at 100% here, go back to steps 2 and 3, using report 06's verdict ladder. **Never scale demand to pass.**

**Step 6. Fix totals by time, boundary by boundary.** One factor per entry and period. *Exit:* boundary flows within 10%, day shape within the Credible band below.

**Step 7. Gently correct OD.** Synthetic recovery test first: inject a known OD and recover it. Then W-SPSA or report 06's cell fit, against counts and speeds, 15-minute passage time, on the training set only. Limit OD change per TAG M3.1. Refit from two priors. *Exit:* selection-set error falls and stops at the noise floor, the training gap stays small, OD changes stay in limits. If two priors fit equally with different ODs, say OD is unidentified.

**Step 8. Fix the worst bottlenecks, and count every fix.** Only where a named cause exists: wrong lanes, a real signal plan, a measured discharge. Use a sensitivity screen to keep the parameter list short, as Fremont did (35 to 10). *Exit:* a public log of each change and its effect on the selection set. If the number of local fixes approaches the number of validation sites, the model has stopped being evidence.

**Step 9. Open the hold-out once.** 20 seeds, one replicate against one real day, every gate check. Any change after this is a new model and needs a new hold-out. Report pass, partial or fail per check.

**Step 10. Predict something it never saw.** Another season, a closure, or a before/after such as the Stockholm trial or Berlin A100. Sign and rough size first. Only this justifies comparing policies.

## Acceptance thresholds for VALIDATION-GATE.md

Ready to paste. The **floor** is the binding bar: where we miss it, report the gap as a failure, as the gate says. **Credible** is about the best published on held-out data. **Good** is better than anything I found published at city scale on held-out data. Credible and Good are my proposals, not standards. All at held-out sites, one replicate against one day. Floors marked "compute" must be measured with step 1's code.

| Check | Metric | Real-day floor | Credible | Good | Today |
|---|---|---|---|---|---|
| Nothing stuck | Teleports off, trips unfinished 2 h after demand ends | n/a | ≤0.5% | ≤0.1% | Stockholm locks at 100% |
| | Waiting to enter more than 15 min | n/a | ≤1% | ≤0.2% | Not reported |
| | Runs at full demand | n/a | Required | Required | 60% only |
| Day shape | Mean difference in hourly share of day, network | 0.15 points | ≤0.5 | ≤0.3 | Berlin 0.70 |
| | Peak hour, AM and PM | Same hour; PM ±1 | ±1 h | Same hour | Berlin AM weak |
| Volume | Hourly site RMSN | **0.19** | ≤0.40 | ≤0.30 | Far off |
| | Hourly site R² and slope | 0.90, 0.94 | ≥0.75, 0.85–1.15 | ≥0.85, 0.9–1.1 | Not reported |
| | Hourly site GEH<5 | 89% | ≥60% | ≥75% | Not reported |
| | Hourly site WAPE | 9% | ≤35% | ≤20% | **77.3%**, if WAPE; metric to confirm |
| | Total vehicle-km | 1.7% | ±10% | ±5% | Berlin about −60% of official total |
| | Screenlines and cordon by hour | Compute | ±10% | ±5% | 60% in recipe |
| Speed | Mean by class and hour, motorway | Compute | ±10% | ±5% | Flat 42–44 km/h |
| | Same, arterials | Compute | ±20% | ±10% | Same |
| | Share of motorway links with speed time-series R²>0.4 | Compute | ≥55% | ≥70% | Not run |
| Travel time | Routes within 15% or 1 min, peak hours, median | Compute | ≥70% | ≥85% (TAG) | Not run |
| Where and when | Congested link-hours caught, and false alarms | Compute | ≥60%, ≤40% | ≥75%, ≤25% | Not run |
| | Top-20 bottlenecks shared with real | Compute | ≥50% | ≥70% | Not run |
| | Onset and clearance at named jams | Compute | ±30 min | ±15 min | Not run |
| Network curve | Peak flow and critical accumulation, same area | Compute | ±20% | ±10% | Not run |
| Trips | Mean length and duration against survey or probes | Survey error | ±15% | ±5% | Not run |

Don't use GEH<5 on daily totals as a pass mark, because real days only get 69%. Don't quote R² alone. Never quote training error as validation.

**What would count as a real result:** the Credible column on held-out data with teleports off at full demand, even in one district. I found no city-scale micro model that has shown that. It's worth more than any number of whole-city runs that don't jam.

## Top 3 recommendations

1. **Stop tuning whole Stockholm. Do Fremont's recipe on one district.** *Next step:* pick the 20–50 km² site with real plans and same-date counts and speeds, then write step 1's metric code and run it real against real. Report 14 and 16 should settle which city. Rule: data decides.
2. **Run the 50% test with teleports off on our current map, and test a main-road preference in routing.** *Next step:* the 50% run is hours of work and is what report 15 and Fremont both say comes first. The main-road test is one cost term and may explain why motorways get a third of their target.
3. **Add a jam-location score to the gate, and build W-SPSA on `cars`.** *Next step:* score congested link-hours from probe speeds, real against real, then model against real. Then implement W-SPSA from the sparse sensor map report 06 already outlines. Nobody publishes either at city scale with held-out data, and our GPU is what makes it affordable.

## What only Erik can do

Report 05 already has the drafts, written in his style, so I haven't duplicated them:

- **Toll passages per lane and minute** (drafts 1, 2): the best independent timing truth for Stockholm.
- **Signal plans from Trafikkontoret** (draft 3): every serious project coded real plans. SAMPERS workshop participants said the city's databases hold them.
- **Linköping collaboration** (draft 5): they hold Stockholm GPS, phone and count data and have already calibrated central Stockholm. I couldn't open the thesis text, so ask for it too.

**Decisions:**
- Agree that "Credible" is what we call a real result, while the floor stays binding.
- Decide how many local fixes are allowed before a scenario stops counting. I suggest fewer than one for every five held-out sites.

## Dead ends

| Tried | Result |
|---|---|
| London (LoHAM, ONE) | No public network-level validation found, only local Vissim reports. Aimsun London page gave 403 in report 15 |
| Madrid Aimsun | Only M-30 real-time forecasting descriptions, no validation numbers |
| Barcelona Aimsun | [Extended abstract](https://limos.engin.umich.edu/istdm2021/wp-content/uploads/sites/2/2021/05/ISTDM-2021-Extended-Abstract-0080.pdf): 9,250 links, 202 zones, Orange phone OD, INRIX, 70 count stations. Computational test, no fit numbers. Good data recipe |
| Manhattan Aimsun | Case study 404, NYCDOT slides 403. Search excerpts only: validation called hard |
| Shanghai and Beijing whole-city micro | Only speed benchmarks with no calibration, as far as I could see. Hangzhou Xiaoshan SUMO paper seen only as an excerpt |
| Melbourne journal paper, Beijing PDF, Balakrishna thesis, Toledo TRR | ScienceDirect and ResearchGate 403, DSpace 429, Sage blocked |
| SHRP2 C10 Jacksonville and Sacramento | Found the reports, full text not reached. Worth a retry: real regional activity model plus dynamic assignment |
| POLARIS, BEAM, Chattanooga, Toronto, Munich (new) | Not reached, or no fit numbers in what I could open. Munich rests on report 15 |
| Çolak et al. 2016, phone demand | PDF fetch failed, not read, not used |

**Not established:** a score for jam location at city scale, 15-minute noise floor, Stockholm's own noise floor by hour, how long most projects took.

## Corrections to earlier reports

- **Report 15, Zurich:** "10–15% error, cross-validated" merges two things. 10–15% is on fitted counts. The cross-validation is about 30% better than uncalibrated, with no absolute error.
- **Report 15, Singapore:** omits that the demand is 48,988 trips, and that the 0.37 is on fitted counts.
- **Report 02 §9.6:** 85% GEH<5 at held-out sites is near the real-day floor of 89% and unmatched in print. Keep it as an aim, not a first pass mark.
- **Report 02:** "`cars` reads permissions only from lanes" no longer holds (commit `76719b4`).
- **Report 04, Level 5:** queue onset within one 5-minute bin has no published support. Set it from real-day data.

## New directions

- **A score for jam location**, publishable by itself, tested real against real.
- **Replay as a diagnostic.** Give cars real schedules and routes, as LCSim does, with a dataset like Jinan. If jams still land in the wrong place, supply is at fault and not demand. That's the cleanest test I can think of to split the two.
- **A queue model on the same net**, as report 15 proposed. It would show what micro adds. Nothing I read shows micro beating meso on flows.
- **Many near-optimal fits.** With fast runs we can keep hundreds of settings and report the spread. That answers the "many demands give the same congestion" problem Google admits.

## Sources

PDFs and text are in `/home/erikf/projects/personal/cars-data/truth/practice/matchreal-20261102/`. Fetch log: [15-fetch-ledger.tsv](15-fetch-ledger.tsv). Nothing downloaded was run.

**Read in full:** [Fremont](https://bayen.berkeley.edu/sites/default/files/creating_calibrating_conference.pdf), [Google six metros](https://arxiv.org/pdf/2501.04783), [Zurich](https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2010/10-07/20100801-submitted.pdf) (results, discussion).

**Relevant sections read:** [Google Salt Lake](https://arxiv.org/pdf/2109.11392), [Google speeds](https://arxiv.org/pdf/2412.14089), [Google segment counts](https://arxiv.org/pdf/2502.19528), [Google blog](https://www.research.google/blog/urban-mobility-solutions-calibrating-digital-twins-at-scale/), [I-210](https://escholarship.org/uc/item/1xw8q5j1), [San Francisco](https://sfcta.org/sites/default/files/2019-03/SFDTAFinalCalibrationandValidationReport.pdf), [Barcelona SUMO](https://doi.org/10.3390/ijgi11010024), [Barcelona MATSim](https://arxiv.org/pdf/1803.06375), [New York](https://arxiv.org/pdf/2008.04762), [Mobiliti](https://escholarship.org/content/qt43r1046c/qt43r1046c.pdf), [SimMobility](https://web.mit.edu/cami/Public/CLA_SimMobilityST_TRB_2017.pdf), [W-SPSA](https://web.mit.edu/cami/Public/CLA_WSPSAinPractice_ISTTT_2015_preprint.pdf), [Des Moines](https://wctrs-society.com/wp-content/uploads/abstracts/istanbul/1363.pdf), [Toledo framework](https://wctrs-society.com/wp-content/uploads/abstracts/istanbul/1361.pdf), [Berlin 2019](https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2019/19-01/ZiemkeEtAl2019OpenBerlinScenarioVSPWP.pdf), [Berlin 2024](https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2024/24-22/RakowEtAl_MATSimBerlinEWGT.pdf), [Calibration Illusion](https://arxiv.org/pdf/2608.19642), [Wang et al.](https://arxiv.org/pdf/2409.19090), [LCSim](https://arxiv.org/pdf/2406.19781), [Osorio and Zhang](https://web.mit.edu/osorioc/www/papers/zhaOsoODcalib.pdf), [Melbourne toll](https://arxiv.org/pdf/2011.11892), [Virginia](https://vtrc.virginia.gov/media/vtrc/vtrc-pdf/vtrc-pdf/22-R7.pdf), [SAMPERS DTA](https://www.transportportal.se/swopec/CTS2014-10.pdf), [CODE PROBE](https://fudinfo.trafikverket.se/fudinfoexternwebb/Publikationer/Publikationer_007601_007700/Publikation_007670/CODEPROBE_final_Report.pdf), [FHWA DTA guide](https://ops.fhwa.dot.gov/publications/fhwahop13015/sec8.htm).

**Abstract or record only:** [Melbourne](https://trid.trb.org/View/1438614), [DynaMel repo](https://github.com/meeadsaberi/dynamel), [Sydney](https://fis.tu-dresden.de/portal/en/publications/deployment-and-calibration-considerations-for-largescale-regional-dynamic-traffic-assignment(3a7ae756-ce13-434d-bbcf-0327096c13d3).html), [Beijing](https://dspace.mit.edu/handle/1721.1/99219), [Brunnsviken](https://bibliotek.vti.se/bib/258412), [Wei 2026](https://trid.trb.org/View/2752029).

**Search excerpt only, UNVERIFIED:** Balakrishna on Los Angeles, MOSS OD figures, Melbourne R² 0.75, Manhattan.

**From our own reports, not reopened:** Stockholm trial, Munich, UNsim, Ma and Qian, TAG, FHWA 2019.
