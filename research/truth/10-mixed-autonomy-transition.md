# Removing human drivers progressively: evidence, the thesis audit and an experiment programme

First draft by another model, 2026-10-31. Audited, corrected and extended by Opus on 2026-10-31 and 2026-11-01. The audit result and the final programme are in the last section, [Reviewed by Opus](#reviewed-by-opus). No GPU was used. New measurements in this report are CPU runs of the thesis's own SUMO 1.26 configuration, scripted in [`scripts/10_thesis_audit.py`](scripts/10_thesis_audit.py), with outputs in [`thesis-audit/`](thesis-audit/).

Grades: **FIELD** (real vehicles or operations), **SIMULATION** (assumed behaviour), **THEORY** (consequence of assumptions), **MEASURED HERE** (this repo's run of a simulator, so a statement about the model, not about traffic), **DEDUCTION** and **PROPOSAL** (mine). Funders and author ties are stated where the source gives them.

## The short answer

1. **No field evidence shows that replacing human drivers reduces congestion in a real city.** I found no causal estimate of a robotaxi fleet's effect on city travel times, in either direction.
2. **The field evidence on what automation does to flow points both ways.** Purpose-built damping works locally at 1–5% share. Commercial cruise control amplifies disturbances. Deployed robotaxis follow with a larger time gap than the humans around them, and drive 42–46% of their miles empty.
3. **What simulated gains depend on is mostly one number: the following time gap the modeller assumes.** The thesis assumed 0.6 s. The best field fit for Waymo is 1.32 s. Putting that fitted value into the thesis's own I-80 turns a 22% travel-time gain into a 90% increase in travel time.
4. **The strongest real benefit is safety, not flow**, and the strongest numbers there come from Waymo's own employees.

## 1. What was corrected in the first draft

| Claim in the draft | Verdict | What the source says |
|---|---|---|
| 7 of 7 commercial ACC unstable; disturbance 6 → 25 mph | **Held, with scope added** | Seven 2018 models from two makes, over 1,200 miles; the instability is of the data-fitted model of each. The 6 → 25 mph growth is one eight-vehicle platoon of one model, ending when the last car's ACC disengaged. Six of seven were never platooned. [Gunter et al.](https://lab-work.github.io/download/gunter2020commercially.pdf); NSF funded. |
| Stern: "40% lower **estimated** fuel. Fuel was calculated from trajectories" | **Wrong** | Fuel was logged per vehicle with OBD-II data loggers. [Stern et al., §2 and §4.1](https://arxiv.org/pdf/1705.01693). |
| Stern: maxima 15% throughput and 40% fuel | **Rounded and flattering** | 15% and 40% are the introduction's words. Table 3 gives A: +14.1%, −42.5%. B: +9.8%, −22.1%. C: **−2.5%**, −28.1%. Each is the best control interval against the first wave interval, in runs under ten minutes. Raising the setpoint from 7.5 to 8 m/s brought a wave back. [Same source](https://arxiv.org/pdf/1705.01693). |
| Waymo 46% empty | **Held for the whole period, stale as a current figure** | 53.6% occupied over 86.3 million miles, Aug 2023–Dec 2025. The occupied share started at 36% and plateaued at 55–57% from mid-2025. [Abdelhalim](https://findingspress.org/article/161870-millions-of-trips-waymo-empty-miles-california-s-first-thousand-days-of-commercial-robotaxi-service). For March 2026, 41.6% of 9.1 million miles. [SSTRP/Open Plans](https://static1.squarespace.com/static/5e71380706dc865d40a6f93c/t/6a6261cabb97e061edbc6b35/1784832458538/How+Would+For-Hire+AVs+Impact+NYC_SSTRP_Open+Plans_Update.pdf). |
| Waymo 18% lower arterial capacity | **Number held; "arterial capacity" overstated** | 2,398 → 1,972 veh/h at an **assumed** 40 mph free-flow speed, from stationary spacing–speed fits in mixed traffic, extrapolated to a 100% fleet. No Waymo-following-Waymo pair exists in the data. [Chen et al.](https://link.springer.com/article/10.1007/s42421-026-00177-1). Not a measured discharge. |
| Chauffeur experiment +60% VMT | **Held** | 43 Sacramento households, one or two weeks. Trips +25%, and 85% of added trips were zero-occupancy. [Harb et al.](https://rosap.ntl.bts.gov/view/dot/65477). |
| Shirado et al. graded "field-lab" | **Misdescribed** | Online participants remotely driving robot cars in a chicken-style task. Autosteering, specifically, stopped reciprocity from emerging, and the effect outlasted the assistance. [PNAS](https://pmc.ncbi.nlm.nih.gov/articles/PMC10743379/). |
| Bullying study "unverified" | **Now opened** | A stated-intention survey, N=998, China and South Korea: more intent to bully AVs than human drivers. It measures intention, not road behaviour. [Liu et al.](https://www.sciencedirect.com/science/article/abs/pii/S0001457519312370). |
| Thesis collisions "not reproduced here" | **Now reproduced** | 32,088–33,217 collisions per run, against 0 at baseline. See [section 8](#8-audit-of-the-thesis). |
| "Bologna, then Stockholm" as first cities | **Replaced** | [Report 01](01-city-ground-truth.md) ranks Melbourne strongest and [report 02](02-stockholm-why-overloaded.md) shows Stockholm's demand is not usable yet. See the programme. |

Numbers re-checked and correct: Ciuffo (10 vehicles, 30–60 km/h), OpenACC (16 vehicles, 11 ACC), Milanés (4 vehicles), CIRCLES engagement (38% → 78%), SFMTA (almost 600 incidents), the Cruise recall (1,194), Waymo's 7,000 dark signals, Soni (18 drivers), white-phase ranges (3.2–94.06% and 40.2–98.9%), pedestrian white phase (27% and 14.7%). Other carried entries are listed under [What remains unknown](#what-remains-unknown).

## 2. Commercial automation: amplifiers, and capacity as a product setting

**FIELD.** ACC amplifies. Besides Gunter above: [Milanés & Shladover](https://its.berkeley.edu/publications/modeling-cooperative-and-autonomous-adaptive-cruise-control-dynamic-responses-using) found strings of consecutive commercial ACC amplify speed changes, while a custom CACC stayed stable. [Ciuffo et al.](https://openresearch.surrey.ac.uk/esploro/outputs/journalArticle/Requiem-on-the-positive-effects-of/99692266102346) confirmed instability on ten cars at 30–60 km/h and warned of higher energy use and new safety risks. Their authors work at the European Commission's Joint Research Centre. [Knoop et al.](https://research.tudelft.nl/en/publications/platoon-of-sae-level-2-automated-vehicles-on-public-roads-setup-t) drove seven Level-2 cars almost 500 km on public roads and found them unsuitable as platoons beyond about three or four vehicles, and platoons hard to form in busy traffic.

**FIELD.** Mixed strings are not a free lunch either. [Zheng et al.](https://arxiv.org/abs/2204.04997) put six automated cars (1.5 s gap) among humans. At 10 vehicles they still suppressed oscillation growth. At 13 and 20 they had no significant effect. Flow rose as AV share fell: a stability–throughput trade-off.

**FIELD.** Capacity is a setting, not a property of automation. Pooling experiments from several groups, [Li et al.](https://arxiv.org/pdf/2105.05380) observed equilibrium capacities above 3,500 veh/h at ACC's *minimum* headway, with waves near 100 km/h that they flag as a safety risk, and jam spacing large enough to cut storage, and stress that the result depends on the setting. OpenACC reports prevalent time gaps such as 1.1 s on one model. [OpenACC](https://arxiv.org/pdf/2004.06342). NSF funded Li; the JRC ran OpenACC.

**Why it matters.** "An AV" spans from above 3,500 veh/h (ACC at minimum setting) to 1,972 veh/h (fitted Waymo at 40 mph). No share-versus-benefit curve means anything until this is fixed.

**SIMULATION, for scale only.** PATH's CACC model reached about 4,000 veh/h/lane at 100%, with a near-linear rise if all other cars broadcast and a lagging quadratic rise if not. [Shladover et al.](https://escholarship.org/content/qt5r33k6wk/qt5r33k6wk.pdf). No field fleet has shown this. A related attack study found compromised ACC can cut mean speed by over 7% in simulated moderate congestion while evading a GPS-trace anomaly detector. [Gunter et al.](https://arxiv.org/abs/2112.11986).

## 3. Sparse control: real, local, and not a capacity result

**FIELD, closed ring.** Stern's numbers are in section 1. The authors say multi-lane experiments are still needed to quantify benefits on freeways. [Stern et al.](https://arxiv.org/pdf/1705.01693); NSF funded.

**FIELD, open road.** CIRCLES ran 100 vehicles on I-24 in November 2022, with people in the seats, on ACC hardware given set speeds ([Jang et al.](https://arxiv.org/pdf/2402.17050)). It reports the following:

| Result | Grade and limit | Source |
|---|---|---|
| One controlled RAV4: speed variance 19.6 → 9.4 m²/s² (−52%) over a section behind it; about −50% up to 600 m; in the paper's nearest-front comparison −11% at 1,200 m and **+5% at 1,400 m**. Share about 1–3%. | FIELD, one morning hour, one lane, cars behind against cars in front. Not randomised. | [Hayat et al.](https://arxiv.org/pdf/2310.18151) |
| Engagement 38% one day, 78% the next, from driver comfort and better communications. Waves remained, as the authors expected. Their wave-damping examples are called "anecdote" and "may". | FIELD, descriptive. No network-wide causal number. | [Lee et al.](https://arxiv.org/pdf/2402.17043) |
| "Trend" of 15–20% energy savings around controlled cars; up to 20% in simulation. | FIELD trajectories with a calibrated energy model, not measured fuel. No control group. | [Researchers' account](https://bair.berkeley.edu/blog/2025/03/25/rl-av-smoothing/) |

Funders across these: NSF and US DOE EERE; also C3AI, AWS, Siemens, Toyota, GM, Nissan, Caltrans, CCTA, KACST and Tennessee DOT. An "8% density decrease" appears in a [ResearchGate summary](https://www.researchgate.net/publication/388610063_Traffic_Control_via_Connected_and_Automated_Vehicles_CAVs_An_Open-Road_Field_Experiment_with_100_CAVs). I could not find it in the [published full text](https://escholarship.org/content/qt6nb5z5c9/qt6nb5z5c9.pdf), so I do not rely on it. The final technical report on OSTI was unreachable.

**Assessment.** Damping is the best-supported low-share benefit. It reduces variance and probably energy within about a kilometre. Nothing opened shows it raising bottleneck capacity or cutting network travel time. Stern's own result moved throughput between −2.5% and +14.1%.

## 4. Robotaxis as deployed: following gap, empty miles, stalls

### Following

**FIELD trajectories, then extrapolation.** From 4,677 Waymo Open Motion episodes in six US cities, [Chen et al.](https://link.springer.com/article/10.1007/s42421-026-00177-1) (published 20 October 2026; NSF funded; no conflicts declared) fit stationary spacing against speed up to 17.9 m/s:

| | Time gap τ | Jam spacing δ | R² | Capacity at 40 mph | Capacity at 65 mph (beyond the data) |
|---|---|---|---|---|---|
| Waymo | 1.32 s | 9.05 m | 0.85 | 1,972 veh/h | 2,208 veh/h |
| Humans nearby | 1.01 s | 8.71 m | 0.60 | 2,398 veh/h | 2,740 veh/h |

Against the distant human reference the highway loss is about 30%; against the three near groups, about 15%. The episodes last 20 s, humans are seen only near the Waymo, and distant-vehicle sensing may be biased. Treat this as what today's product chooses in mixed traffic, not what automation requires. Nothing here says a Waymo would keep 1.32 s behind another Waymo.

### Empty miles

**FIELD, aggregated regulator data.** See section 1. Empty miles per trip fell from about 5.1 to 2.8, wait between trips from 28.6 to about 18 minutes, and riders per trip stayed near 1.4. [Abdelhalim](https://findingspress.org/article/161870-millions-of-trips-waymo-empty-miles-california-s-first-thousand-days-of-commercial-robotaxi-service) was part-supported by an Aspen Institute fellowship.

**Observational comparison, advocacy co-author.** [SSTRP/Open Plans](https://static1.squarespace.com/static/5e71380706dc865d40a6f93c/t/6a6261cabb97e061edbc6b35/1784832458538/How+Would+For-Hire+AVs+Impact+NYC_SSTRP_Open+Plans_Update.pdf) puts Waymo's California multiplier at 1.71 miles per occupied mile against 1.49 for NYC high-volume for-hire vehicles. That compares different cities and markets. Its summary says "14.8% more empty driving miles"; that is the gap between the total multipliers. Empty miles per occupied mile are 0.71 against 0.49, which is 45% more. The authors have also temporarily withdrawn the report's safety analysis. Its estimate that 1% less parked time adds 1.5% deadheading is a useful sensitivity, not a law.

### Stalls and correlated failure

| Date | Event | Scale | Mechanism and what is contested | Source |
|---|---|---|---|---|
| To Aug 2023 | SF city incident log | Almost 600, "likely a fraction" | Cruise and Waymo did not disclose totals. Durations from minutes to hours in city records. | [SFMTA/SFFD/SFPD](https://www.sfmta.com/sites/default/files/reports-and-documents/2023/08/2023.08.07_cpuc_status_conference_8.7.2023_final.pdf) |
| 11 Aug 2023 | Cruise, North Beach | About 10 cars, about 15 min | Cruise's first account: festival bandwidth. | [CBS](https://www.cbsnews.com/sanfrancisco/news/robotaxis-halt-traffic-in-san-franciscos-north-beach-day-after-expansion-approval) |
| 2 Oct 2023 | Cruise hits and drags a pedestrian | 1 person, 20 ft | Post-crash pullover moved the car with the person under it. | [Koopman](https://arxiv.org/pdf/2406.05281) |
| Aug 2024 | Cruise recall | 1,194 vehicles | Unexpected braking when road users suddenly close from behind. | [NHTSA filing](https://static.nhtsa.gov/odi/rcl/2024/RMISC-24E067-1279.pdf) |
| 20 Dec 2025 | Waymo, PG&E outage, SF | 7,000+ dark signals crossed | Confirmation requests spiked and backlogged, adding to congestion. Waymo says dark signals themselves were the main cause of gridlock. | [Waymo](https://waymo.com/blog/2025/12/autonomously-navigating-the-real-world/) |
| 31 Mar 2026 | Apollo Go, Wuhan | At least 100 cars, riders stuck up to 2 h, some in fast lanes | Police: "system failure". Baidu has not disclosed a cause. | [TechCrunch](https://techcrunch.com/2026/04/01/system-failure-paralyzes-baidu-robotaxis-in-china) |
| Apr–Jun 2026 | Waymo recall, freeway closures | Nearly 4,000; 13 incidents | Driving into closed construction lanes; Waymo pulled off highways. | [TechCrunch](https://techcrunch.com/2026/06/18/waymo-recalls-nearly-4000-robotaxis-to-stop-them-driving-into-highway-construction-zones/) |
| 4 Jul 2026 | Waymo, Presidio, fireworks | More than 30 stuck per KQED; Waymo gives no count | Some ran out of charge idling and were towed. Whether they caused or suffered the gridlock is contested. SFMTA also blames transit capacity and the site. | [KQED](https://www.kqed.org/news/12089915/sf-supe-to-launch-inquiry-on-waymos-july-fourth-traffic-meltdown), [ABC7](https://abc7news.com/post/waymo-fleet-clogs-presidio-july-4-fireworks-leaving-vehicles-stranded-towed/19455862/) |
| 8 Jul 2026 | NHTSA letter to developers | Industry-wide, no company named | "Clear pattern" of interference with first responders, a "functional insufficiency". I could not open the letter itself. | [Insurance Journal](https://www.insurancejournal.com/news/national/2026/07/09/876764.htm) |

**Help is a finite resource.** Waymo reports about 70 remote assistance agents on duty at any time, who advise rather than drive. [Reuters](https://www.yahoo.com/news/articles/waymo-defends-remote-assistance-workers-215835600.html). Set against a fleet of nearly 4,000 four months later, that is on the order of one per 50 vehicles. **DEDUCTION:** that ratio works when requests are independent and rare, and a shared trigger breaks it, which is what Waymo describes in December. None of these events has an exposure-normalised, causal delay estimate.

### Safety, the main real benefit

**FIELD, retrospective, Waymo-authored.** Over 56.7 million rider-only miles, against aligned human benchmarks: any-injury-reported pedestrian crashes −92% (CI −99% to −66%), cyclist −82% (−97% to −41%). City results vary; Los Angeles cyclist and pedestrian estimates are not significant. All authors are Waymo employees, and benchmarks rely on police-reported data with stated limits. [Kusano et al.](https://arxiv.org/pdf/2505.01515). I found no independent replication at this scale. This matters for the flow debate: larger time gaps may be part of how the safety is bought, though no study opened tests that link.

## 5. Humans around AVs: the sign is not settled

| Finding | Grade | Limit | Source |
|---|---|---|---|
| Smaller critical gaps and shorter headway after overtaking an apparent AV | FIELD, 18 drivers, Wizard of Oz | Small, controlled | [Soni et al.](https://research.tudelft.nl/en/publications/behavioral-adaptations-of-human-drivers-interacting-with-automate/) |
| AV-believers, sceptics and insensitive drivers. **No difference when the AV was not recognisable.** Response follows belief, not the AV's driving. | FIELD, 10 drivers, 14 runs each | Small | [Zhao et al.](https://www.sciencedirect.com/science/article/abs/pii/S0968090X18313767) |
| Shorter headway, lower volatility, higher TTC behind AVs | FIELD trajectories (Waymo) | See Jiao | [Wen et al.](https://www.sciencedirect.com/science/article/abs/pii/S0001457522001257) |
| Three non-behavioural explanations all contribute to shorter headways: data-collection differences, leader variability, leader characteristics | FIELD trajectories (Lyft) plus simulation | Warns against reading trajectories as behaviour change | [Jiao et al.](https://www.sciencedirect.com/science/article/abs/pii/S0968090X24001943) |
| Followers keep **larger** spacing behind Waymo; authors say "the evidence is not very strong" and that Lyft data pointed the other way | FIELD trajectories | Not directly comparable | [Chen et al.](https://link.springer.com/article/10.1007/s42421-026-00177-1) |
| Cut-ins in front of Waymo: median gap 7.58 vs 9.57 m, 51.7 vs 37.7 km/h, 706 vs 3,172 events, small effect (d=−0.22) | FIELD trajectories, **preprint** | Single dataset, not peer reviewed | [Alhuraish et al.](https://arxiv.org/pdf/2605.01485) |
| At unsignalised junctions AVs keep larger margins, which can surprise humans. Waymo and Lyft differ. | FIELD trajectories | Surrogates, not crashes | [Rahmani et al.](https://arxiv.org/pdf/2410.12538) |
| Punishment policy deters bullying in a virtual negotiation | THEORY plus virtual experiment | Not a road controller | [Cooper et al.](https://arxiv.org/abs/1908.08641) |

**Assessment.** "Humans bully AVs" is not established as a flow effect, and neither is "humans become calmer". The defensible model is a **mixture with a recognition switch**: a share of drivers changes gap acceptance and following only if they know the car is automated. The effect should be swept in both directions, because the direction is unknown. A model that keeps humans fixed as share rises, as the thesis did, has assumed the answer.

## 6. Pedestrians and cyclists in signal-free junctions

**THEORY: signal-free capacity.** [Tachet et al.](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0149607) derive an "up to 2-fold" capacity gain, asymptotic in batch size, for two single-lane roads crossing, using queueing theory. The paper does not model pedestrians. Its acknowledgements thank Volkswagen's research lab among others, though its funding statement says none.

**THEORY and SIMULATION: it can get worse.** [Levin, Boyles & Patel](https://ideas.repec.org/a/eee/transa/v90y2016icp14-25.html) show signals beating reservations in theoretical and realistic networks, mostly by favouring local-road traffic over arterials, and show selfish route choice producing arbitrarily large queues. A downtown grid favoured reservations.

**THEORY: walkers can hold the street.** [Millard-Ball](https://escholarship.org/content/qt5sf2f06h/qt5sf2f06h.pdf) models crossing as a game of chicken. If a vehicle reliably yields, pedestrians can cross with impunity, and motor traffic may lose speed in dense cores unless cities respond with fences and enforcement. This is the piece of theory that most directly undercuts "signal-free is faster".

**SIMULATION: the trade-off is real.** In a max-pressure AIM with pedestrians, [Wu et al.](https://www.sciencedirect.com/science/article/abs/pii/S0968090X19309623) find vehicle and pedestrian delay negatively correlated. The [pedestrian white-phase model](https://news.ncsu.edu/2024/03/traffic-signal-pedestrians-vehicles/) keeps walk intervals, reports up to 27% lower average delay as CAV share grows, and pedestrians do better too; it is a computer model, with a physical testbed under construction. A controller by Niels et al. (TRR 2024, doi:10.1177/03611981231172956) reports lower vehicle delay and similar pedestrian waits against actuated signals, but I could read only search abstracts, because [its repository](https://mediatum.ub.tum.de/doc/1739169/document.pdf) blocked me.

**FIELD, weak and mixed.** Controlled crosswalk tests show that an external display works only with gentle braking. [Izquierdo et al.](https://arxiv.org/abs/2312.07606). VR shows that signalling changes accepted gaps. [Zou et al.](https://arxiv.org/abs/2303.15352). A journalist's filmed crossing recorded Waymo yielding about 3 of 10 times at one unprotected crosswalk; that is anecdote, and it contradicts the assumption of a car that always yields. [Fowler, Washington Post](https://ca.style.yahoo.com/roads-teeming-robotaxis-crossing-street-013656599.html). I found no peer-reviewed yield-rate comparison between robotaxis and humans.

**Gaps, stated plainly.** I found no field trial of a dense signal-free junction with unrestricted pedestrians or cyclists. I found no empirical study of cyclists in coordinated junctions. Motorised-only results do not transfer.

**DEDUCTION.** Walking a 7 m carriageway at an assumed 1.2 m/s takes about 6 s. At 1,800 veh/h per conflicting lane, a 2 s slot, one group costs about three vehicle slots per lane before clearance. Signal-free gains shrink as crossing requests become frequent, and the phase structure re-emerges under another name once a maximum wait is guaranteed. Whether it pays is an empirical question, which is H7 below.

## 7. Does congestion get better overall?

**No causal measurement exists for robotaxis.** The closest natural experiment is ride-hailing. In San Francisco, weekday vehicle-hours of delay rose 62% from 2010 to 2016, against 22% in a modelled no-TNC counterfactual; speed fell 13% against 4%; about 20% of TNC miles were out of service. The study is model-based, one dense city, and the city's transport authority funded it. [Erhardt et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC6506243/).

**Induced travel.** Vehicle-km on US interstates rose one for one with lane-km; they found no evidence that transit provision affected it. [Duranton & Turner](https://ero.ontario.ca/public/public_uploads/2024-11/duranton-turner-2011-the-fundamental-law-of-road-congestion-evidence-from-us-cities.pdf). Israeli microdata show the response varies, stronger in urban regions and driven by second-car purchases. [Amedi, Bank of Israel](https://boi.org.il/media/pqaiana1/dp202603e.pdf). **DEDUCTION:** any real capacity gain from automation should be expected to be partly consumed. These studies concern roads, not software capacity, so this is an analogy.

**Removing the need to drive.** The chauffeur experiment gives +60%, a short subsidised proxy. A meta-analysis of 26 modelling studies averages +5.95% (shared +5.3%, private +6.9%). [UT Arlington release](https://www.uta.edu/news/news-releases/2026/04/21/the-promise-of-self-driving-cars-hits-a-traffic-snag). A policy brief spans 13–83% across evidence types. [UC Davis](https://escholarship.org/content/qt3302s4j4/qt3302s4j4.pdf). A review finds AVs mostly raise VMT, shared fleets could help, and results are "very sensitive to model assumptions". [Soteropoulos et al.](https://ideas.repec.org/a/taf/transr/v39y2019i1p29-49.html).

**DEDUCTION, arithmetic and not a forecast.** Demand-to-capacity index relative to today, equal to demand × empty multiplier ÷ capacity. It assumes all traffic converts and spreads evenly, which it would not.

| Scenario | Demand | Empty | Capacity | Index |
|---|---:|---:|---:|---:|
| Today's robotaxi replaces every car 1:1 | 1.00 | 1.71 | 0.82 | **2.09** |
| Private AVs with today's gap, meta-analysis demand | 1.07 | 1.00 | 0.82 | **1.30** |
| Private AVs, chauffeur demand | 1.60 | 1.00 | 0.82 | **1.95** |
| Commercial-ACC minimum setting (3,500 against 2,400), chauffeur demand | 1.60 | 1.00 | 1.46 | **1.10** |
| Pooled, priced fleet with optimistic empties, CACC at 4,000 against 2,000 | 1.25 | 1.20 | 2.00 | **0.75** |

Only the last row improves, and it needs a capacity no fleet has shown, cooperation among all vehicles, pooling that riders do not yet choose (1.4 per trip today), and road pricing.

**My assessment (opinion).**

- **Low share, today's products:** too small to see city-wide. Local stalls and curb use are the visible harms. Occasional damping is possible.
- **Medium to high share, unpriced, today's gaps:** more likely worse than better, chiefly from empty running and larger gaps. Confidence is moderate; none of it has been observed at scale.
- **High share with interoperable cooperation and per-km pricing that includes empty km:** could be better. That is a policy and standards outcome, not a consequence of removing humans.
- **Whatever the flow result:** safety and access for people who cannot drive may justify deployment. A later report should weigh these against delay rather than treat congestion as the only test.

**What would change my mind.** A staggered-rollout study showing city travel times falling with robotaxi share, or a homogeneous fleet on a real road measured at short gaps with clean recovery from cut-ins.

## 8. Audit of the thesis

Thesis: Frankling & Wallén, May 2026, [local PDF and repo](/home/erikf/projects/personal/thesis-src/bachelor). Reruns use its `config/`, `prepare_routes.py` and locked SUMO 1.26. They reproduce `results/processed/metrics.csv`: for example, I-80 100% CACC seed 0 gives 28.07 m/s and Bologna Krauss 8.63 m/s. Everything in this section is **MEASURED HERE** and says what the model does, not what traffic does. Full ledger: [`thesis-audit/sumo_ledger.csv`](thesis-audit/sumo_ledger.csv).

### A. The published figures are not the committed data

The thesis text and PDF Figures 4.4 and 4.6 show results that the repo's `metrics.csv`, its `results/plots` and a fresh rerun do not. Both sit in the same first commit, the day after the thesis date.

| Quantity, 100% share | PDF | Repo and my rerun |
|---|---|---|
| I-80 mean speed, ACC (Fig 4.4, §4.2, §5.3) | ≈33 m/s, **+20%**; "all tiers improve" | **24.5 m/s, −10.6%** |
| I-80 mean speed, CACC | ≈32 m/s, +17% | 28.1 m/s, +2.6% |
| Intersection waiting, ACC (Fig 4.6, §4.4) | ≈7 s, −60% | 11.4 s, −32% |
| Intersection waiting, CACC | ≈23 s, +45% | 21.2 s, +27% |

Ring and Bologna figures do match. So §4.2's ranking, §5.3's "on the freeway all tiers improve" and §6's "holds for all the AV control models" rest on a run that is not in the repository. I do not know which configuration produced it. I tried obvious candidates: ACC at a 0.2 s step gives 25.5 m/s, and ACC with τ=1.0 and minGap=2.5 gives 29.9 m/s, so neither reaches 33. Only Erik or Adam can identify it.

### B. The collision artefact

The pipeline never looked. `run_sweep.py` passes `--no-warnings`, `parse_results.py` reads no collision or teleport field, and §1.3 assumes safety is satisfied. SUMO's default moves the colliding follower to the next edge. [SUMO docs](https://sumo.dlr.de/docs/Simulation/Safety.html). The docs also say CACC "is known to produce collisions at the default step-length of 1s". [SUMO docs](https://sumo.dlr.de/docs/Car-Following-Models/CACC.html). The I-80 scenario uses 1 s, unlike ring and Bologna at 0.1 s.

| I-80, 100%, seeds 0–2 | Collisions per run | Veh-km on edges | Mean travel time vs baseline |
|---|---:|---:|---:|
| Human baseline | 0 | 403,800 | 698 s |
| CACC | **32,088–33,217** | **373,300 (−7.6%)** | −13.4% |
| Krauss | 3,733–3,773 | 403,770 | −27.0% |
| IDM | 1,049–1,110 | 403,100 | −22.5% |
| ACC | 0 | 403,900 | +29.7% |

- **CACC is the clear artefact.** A separate seed 0 run with collision output logged 31,613 events: 1.3 per trip, 46% of vehicles at least once, up to 10 times for one car. Median closing speed 6.6 m/s (24 km/h), and 91% above 3 m/s, heaviest on `edge_up_78` and `edge_down_78`, and 72% of them in the third simulated hour. Its threshold is a 0.1 m gap, so these are real overlaps in model terms. The vanished 30,000 veh-km and the 5.3% drop in the "throughput" metric are the same teleports seen another way.
- **Krauss is a softer case.** Its threshold is the full 1.5 m minGap. Events are low-speed (median closing 1.45 m/s), one per vehicle, almost all on on-ramp merges, and veh-km are unchanged. Merging at 1.5 m is unsafe but not a pile-up.
- **Bologna is not affected.** Collisions are 0–2 per run. Its gains cannot be explained by teleports; they are explained by the next point. ACC at 100% in Bologna instead leaves 627 of 10,069 trips unfinished and 51 teleports.

@@COLLISION_TESTS@@

### C. The ring gain is arithmetic, not wave dissipation

§5.3 says the heatmaps "confirm that the ring improvements come specifically from wave dissipation rather than from higher cruising speeds". §6 and §6.3 repeat it. That is the wrong way round.

On a closed ring, uniform speed is fixed by spacing: v = (L/N − length − minGap) / τ. At 20 m per car:

| Tier | τ, minGap | Identity v | Measured before the disturbance (1,000–2,000 s) | Thesis mean | Spread before | Spread at 3,000–4,000 s |
|---|---|---:|---:|---:|---:|---:|
| Human | 1.0, 2.5 | 12.5 | 12.39 | 12.31 | **0.008** | 1.36 |
| Krauss | 0.6, 1.5 | 22.5 | 22.59 | 22.50 | 0.000 | 0.000 |
| IDM | 0.6, 1.5 | 22.5 (IDM root 20.6) | 20.66 | 20.55 | 0.000 | 0.13 |
| CACC | 0.6, 1.0 | 23.3 | 23.44 | 23.02 | 0.18 | **2.96** |
| ACC | 1.5, 2.0 | 8.7 | 7.37 | 7.33 | 0.000 | 0.84 |
| Waymo fit | 1.32, 4.05 | 8.3 | 8.31 | n/a | 0.000 | 1.54 |

Data: [`thesis-audit/ring_windows.csv`](thesis-audit/ring_windows.csv), one seed; speeds in m/s, spread is the SD of 50 s detector means.

- **The speed difference exists before any wave.** The +82% for Krauss is present at 1,000–2,000 s, before the disturbance, on a perfectly uniform ring. There is no spontaneous jam in the baseline, so nothing is being dissipated.
- **The wave costs no mean speed.** Baseline mean is 12.39 before and 12.47 after. CACC's 85% gain in §4.1 is entirely the time gap.
- **"Fully dissipate" is false for CACC.** §4.1 and §6 say CACC fully removes the wave. Its spread *grows* from 1.6 to 3.0 m/s over the last 1,600 s, more than the human baseline's in absolute terms, with speed dipping to 13.9 m/s. Krauss and IDM do damp it.
- **The flow is unphysical.** 100% CACC gives 4,132 veh/h on one lane. That is 2.1 times the fitted Waymo value and above the 3,500 seen for ACC at minimum setting.
- **The ring test cannot do what the thesis asks of it.** Stern's ring (22 cars, 260 m) makes waves spontaneously, with a speed SD of 2.4–3.9 m/s. This one needs a kick and is decaying anyway.

### D. "Human noise" is not in the model

§5.3 and §5.4 attribute gains to "replacing unpredictable human drivers" and "removing human reaction noise". But §3.1.2 says the only stochastic element of the human IDM is `speedDev`. The baseline has no reaction noise and no reaction delay, so that mechanism cannot be what the runs show. §5.2's "each added deterministic vehicle removes a further source of the disturbance" is contradicted by the same point, by Stern (one car, 5%, not a deterministic majority) and by Gunter (deterministic ACC is unstable). §2.2.1's "AVs reduce the formation of waves since their reaction is instantaneous" is contradicted by all of section 2 above.

### E. What actually drives the "AV" tier

**One-factor test.** Every car is the human type with one change. Seed 0, against the baseline of the same seed; [`thesis-audit/sumo_ledger.csv`](thesis-audit/sumo_ledger.csv).

| Change from human | I-80 time loss | I-80 travel time | Bologna time loss | Bologna travel time |
|---|---:|---:|---:|---:|
| Baseline (s) | 195.6 | 704.2 | 205.1 | 332.1 |
| τ 1.0 → 0.6 only | **−81%** | −22.5% | **−39%** | −24% |
| minGap 2.5 → 1.5 only | −26% | −7% | not run | not run |
| accel, decel 2.6, 2.0 → 3.5, 2.2 only | −27% | −7% | −17% | −10% |
| speedDev 0.1 → 0 only | **+62%** | **+17%** | −4% | −3% |
| All four, identical to the IDM "AV" tier | −82% | −23% | −57% | −35% |

- On I-80, τ alone gives **99%** of the tier's time-loss reduction. In Bologna, **69%**.
- **Removing driver variation, the one thing that could be called "noise", makes I-80 worse** and barely moves Bologna. Uniform drivers do not stabilise this model.
- The IDM tier with the human gap (τ 1.0, minGap 2.5) and everything else AV-like is **worse** than humans on I-80: +45% time loss. Automation as modelled here is, in effect, a shorter gap. One seed each; deterministic parts vary little, and the sign of each effect is much larger than seed spread.
- Tiers keep model differences too: Krauss with the human gap still gains (−55%), which is the difference between the Krauss and IDM equations, not automation. §5.5 notes this and §5.1 then ranks them.

Compare the time-gap assumption with field data. Capacity from s = τv + δ, DEDUCTION from the sources in sections 2 and 4:

| Stream | s = τv + δ | 40 mph | 65 mph |
|---|---|---:|---:|
| Thesis human | 1.0v + 7.5 | 2,536 | 2,861 |
| Field humans near Waymo | 1.01v + 8.71 | 2,398 | 2,740 |
| **Thesis AV (IDM, Krauss)** | **0.6v + 6.5** | **3,736** | **4,371** |
| **Field Waymo fit** | **1.32v + 9.05** | **1,972** | **2,208** |

The human baseline is reasonable by this one measure, though uncalibrated and not validated against any I-80 data. The AV assumption has the opposite sign from the deployed product. At 40 mph the thesis AV has 1.89 times the capacity of fitted Waymo.

**The test.** Same runs, with the IDM tier given τ=1.32, minGap=4.05, no speedDev and the human's accel and decel:

| Scenario, share | Metric | Human baseline | Thesis IDM tier | **Waymo fit** |
|---|---|---:|---:|---:|
| I-80, 100% | Travel time | 698 s | 541 s (−22.5%) | **1,324 s (+90%)** |
| | Time loss | 189 s | 36 s (−81%) | **820 s (+333%)** |
| | Mean speed | 27.4 m/s | 31.6 (+15%) | **18.9 (−31%)** |
| I-80, 50% | Time loss | 189 s | 54 s (−71%) | **397 s (+110%)** |
| Bologna, 100% | Time loss | 205 s | 89 s (−57%) | **329 s (+60%)**, 199 trips unfinished |
| Bologna, 50% | Time loss | 205 s | 122 s (−41%) | **281 s (+37%)** |
| Ring, 100% | Mean speed | 12.3 m/s | 20.6 (+67%) | **8.3 (−33%)** |
| Intersection, 100% | Time loss | 52 s | 42 s (−19%) | 55 s (+4%); demand-limited |

Collisions in all these Waymo-fit runs: zero. The baseline is sensitive too: giving humans the field-fitted δ (τ 1.01, minGap 3.71) raises I-80 travel time from 698 to 759 s and time loss by a third. Against that baseline, Waymo fit is still +75% in travel time on I-80. I-80 Waymo-fit results are seeds 0 and 1; Bologna and the ring are seed 0.

This is a stress test, not a prediction. The fit stops at 40 mph, and it may not hold on a freeway or behind another AV. It does show that the sign of the thesis's headline result is a modelling input.

### F. Other findings, by section

| Thesis | Claim | Problem |
|---|---|---|
| §4.3, §5.1, Fig 4.5 | Bologna "throughput" up 7.5% | `flow` here is SUMO's density × speed on edges with samples. All tiers except ACC complete the same 10,069 trips with the same 16,216 veh-km. It is not more trips; the real effect is time loss (−64% Krauss). Demand-limited, so true capacity was never tested. Same for I-80 (2,773 flat). |
| §6, §1.2 | "Largest improvement generally seen when reaching 100%" | True only as totals. Per point of share the largest gain is at low share. I-80 Krauss time loss: −34% at 10%, −68% at 30%, −79% at 50%, −97.5% at 100%. Bologna Krauss: −37% at 30%, −51% at 50%, −64% at 100%. |
| §6.1 | "Meaningful benefits require high penetration rates" | Contradicted by the line above. It should not have been offered as "actionable" for planners. |
| §6, §5.4 | Hypothesis "holds for all the AV control models" | In repo data: Bologna ACC +116% time loss, −43% speed. CACC is **worse** than baseline up to 80% (+20% time loss at 50%). I-80 ACC +110%. I-80 CACC's best point is 40%, and it worsens beyond that. |
| §5.3 | Ranking "remains similar" on ring and freeway | Ring: CACC first. I-80 in repo data: CACC third, well behind Krauss and IDM. |
| §5.4 | "Bottleneck-dominated networks benefit most near full penetration" | Not in the I-80 data; see the two rows above. |
| §5.3, §6.3 | GLOSA "works perfectly"; less fuel | Waiting falls to 0.05 s, because crawling above SUMO's threshold is not "waiting". Travel time changes −0.8% and time loss −33%. No fuel or emissions were measured, yet §6.3 asserts fuel effects for every tier. Emergency braking events rise (17 → 664 on the intersection, 458 → 3,864 in Bologna), which §5.3 never saw. |
| §3.1.4–5, §5.1 | ACC tier is empirically calibrated | The equations come from production-car tests, but `accel=1.0` is a value from Porfyri's freeway ring. Using it in a city gives −43% speed mostly because cars accelerate at 1 m/s². This is what §3.1.4 warned about, then §5.1 and §6 interpret it anyway. |
| §3.2.4, §5.5 | Three seeds give SDs | At 100% Krauss, IDM and CACC on Bologna, seeds 0 and 1 give identical results to all printed digits; demand is deterministic and speedDev is zero. The SD is not uncertainty. The real uncertainty is structural, which more seeds would not fix. |
| §3.3.2, §5.3 | "Free-flow" I-80, "free-flow conditions" on the ring | Baseline I-80 has 189 s time loss, §3.3.2 says recurrent congestion, and the ring is at 50 veh/km. Trucks were removed. |
| §2.1, §3.1 | Krauss and IDM mimic Level 5 | They are parameter sets. Nothing about perception, assertiveness, stalls or recovery is represented. |
| §3.2.5, §4.4, §6.1 | "Less congested urban environments for all road users" | Trip table fixed, no empty running, no pedestrians, cyclists, buses or freight. This sentence claims what the method excluded. §5.5 admits the exclusions but §6.1 does not honour them. |

### G. What survives

- The contribution stated in §5.4, that the answer depends on the model, the share and the network and is not one number. It is stronger than the thesis knew.
- ACC and CACC differ from each other, and CACC's value depends on adjacency: the mid-share penalty is real in the model and matches the p² logic.
- A low acceleration bound and long gaps slow a city, in the model.
- GLOSA reduces stopping, in the model, while hardly changing travel time.
- §5.5's limitations were honest. §6 and §6.1 did not stay inside them.

### H. What would have to change

1. **Establish which run the PDF shows**, and issue a correction for §4.2, §4.4, §5.3 and §6 if it cannot be reproduced.
2. **Rerun everything with `dt` 0.1 at most, warnings on, and collisions, teleports and veh-km in the results table.** Any run with collision teleports is reported as failed, never averaged.
3. **Replace the ring conclusion.** Say: at fixed density, mean speed is set by the assumed time gap. Wave suppression must be measured as spread and tested on a ring that makes its own waves.
4. **Replace "throughput"** with completed trips, delay and person-hours, and test capacity by overloading.
5. **Add field-fitted AV tiers.** Without them, IDM and Krauss are upper-bound idealisations, as §3.1.3 half says.
6. **Rewrite §6 and §6.1.** Suggested text: *"In this uncalibrated, fixed-demand SUMO study, the sign and size of AV effects were determined mainly by the assumed time gap. Tiers with gaps shorter than humans gained, and tiers with longer gaps lost, with the largest gain per unit of share at low share. Field data suggest deployed vehicles use longer gaps than the shortest values assumed here. The study does not support conclusions about real deployment, safety, emissions or induced travel."*

---

## Reviewed by Opus

### What held

- The named headline numbers: 7 of 7 and 6 → 25 mph, Stern's direction of effect, Waymo's 46% over the period, −18%, +60%. Also the draft's refusal to call any of them a citywide result, and its warning against treating simulated capacity as real.
- The structure: controller, adjacency, behaviour, demand and failure are separate questions. The p² point. Keeping independent conservative AVs as a required comparison.

### What was wrong or missing

- **Errors:** Stern's fuel method, Stern's "maxima" without the −2.5% throughput, Shirado's grade, the stale 46%, the suggested first cities. See [section 1](#1-what-was-corrected-in-the-first-draft).
- **Omissions that mattered most:** the parameter table in Chen et al., which lets the simulator test a field-fitted AV directly; Li et al., showing capacity is a setting; Zheng's mixed-string result; the Wuhan and Presidio events; the 70-agent figure; Zhao's recognition result; Erhardt's natural experiment.
- **The largest gap:** the draft treated the thesis finding as a user-supplied lead and proposed auditing it. The audit took a few hours of CPU and turned up five things beyond the collision artefact: unmatched figures, arithmetic presented as dissipation, a mechanism absent from the model, a metric that is not throughput, and a conclusion its own data contradicts.
- **A report I checked is also imperfect:** SSTRP's "14.8% more empty miles" is really 45%.

### What remains unknown

- **The causal effect of robotaxis on city travel times.** No study found. It is measurable by anyone with staggered rollout dates and speed data.
- **How AVs follow each other** on real roads at any share, and whether fleets would shorten gaps if allowed. Zero field data at scale.
- **Whether larger gaps are what buys Waymo's crash record.** No study tests this. It decides whether capacity and safety trade off.
- **The direction of human adaptation.** Sources conflict; see [section 5](#5-humans-around-avs-the-sign-is-not-settled).
- **Pedestrians and cyclists in dense coordinated junctions.** No field evidence. Cyclists have almost none of any kind on this question.
- **Real rates of stalls and remote-assist demand.** Operators do not publish them, and SF reports only a known fraction.
- **Long-run demand and land use.** Chauffeur weeks are not decades.
- **What generated the thesis PDF figures.**
- **Sources I could not open this session, and so do not rely on:** Shladover 2012 (publisher 403; PATH report used instead), Mahmassani 2016 (403), Calvert 2017 (TU Delft unreachable), Tilg 2018 (bot wall), the CIRCLES final report and Hayat on OSTI (unreachable; arXiv used), NHTSA's July letter and Cruise consent order (denied; press and Koopman used), Harb's full report (denied; abstract only). Lioris, Bansal, Mahdavian and the I-15 record were opened only at abstract level or not reopened, and are dropped from the argument. The 83% figure for Harb's 13-household pilot is known only through the UC Davis brief.

### Final experiment programme for `cars`

Everything here is a **proposal**. Freeze it with a commit hash before looking at any share result. Validation levels refer to [report 04](04-validity-of-traffic-simulation.md).

#### Step 0: replace the thesis's habits

- No run counts as evidence if it has a collision teleport, an overlap, or lost demand. Collisions are reported with closing speed, and the run is marked failed. `collision.action=warn` may be used only as a diagnostic.
- `dt` 0.1 or lower, with results stable to 1% against 0.05. Reaction time stays fixed in seconds, so it does not change with `dt`. 1 s steps are banned for ACC and CACC.
- Ledger for every run: requested = waiting + active + completed + failed.
- Fixed demand is never the only answer. Capacity is tested by overload.

#### Step 1: what must be true first

**Engine.** [README](../../README.md) lists no buses, stops, pedestrians or sublanes, and 8% Bologna error with IDM minor links off by 20–160%. H7 and bus results cannot run until pedestrians and buses exist. The engine needs a pause state for stalled AVs and a finite assistance queue for H8. Elastic demand is an external outer loop.

**Human model** (gates, using the [report 05](05-real-human-driving.md) proposal or better):

| Must reproduce | Band | Source of band |
|---|---|---|
| Waves with **no kick**: 21–22 cars, 260 m | Speed SD 2.4–3.9 m/s, throughput 1,750–1,830 veh/h | [Stern](https://arxiv.org/pdf/1705.01693) |
| Stationary following | τ≈1.0 s, δ≈8.7 m, with spread | [Chen](https://link.springer.com/article/10.1007/s42421-026-00177-1) |
| Report 04 levels 0–3: discharge, wave speed, capacity drop | As in report 04 | [Report 04](04-validity-of-traffic-simulation.md) |
| Reaction delay above zero, and noise that exists | Stated, in seconds | Audit point D |
| Response to AVs | A switchable parameter: recognition share, ±20% following gap, −2 m cut-in gap | Section 5 |

**AV classes.** Each must pass its gate *before* any sweep. A label such as "AV" is never used alone.

| Class | Definition | Pass gate |
|---|---|---|
| A0 Thesis ideal | τ 0.6, for comparison only; always labelled "idealised upper bound" | None; never a headline |
| A1 Commercial ACC | Gunter/OpenACC parameters, min and max settings | Reproduces 6 → 25 mph within ±25% in eight cars; string-unstable; ≥3,500 veh/h at minimum setting |
| A2 Today's robotaxi | s = 1.32v + 9.05, conservative at merges, stall and assist states | 1,972 veh/h at 40 mph within ±5%; τ swept 1.1–1.5 |
| A3 Wave damper | FollowerStopper or PI with saturation, real sensor limits | Stern: SD −50 to −80%, throughput −3 to +14%. Hayat: variance −40 to −60% to 600 m, gone by about 1.4 km |
| A4 Cooperative CACC | Milanés gains, short gap only behind a compatible car, packet loss per [report 08](08-v2x-and-safety-first-principles.md) | String stable; zero overlap in cut-in fixtures at `dt` 0.1 |
| A5 Reservation junctions | [Report 09](09-coordinated-intersections.md) controller | Report 09 oracle; zero conflicts under message loss |

#### Step 2: hypotheses and preregistered verdicts

All on paired seeds. "Delay" is person-hours including unserved trips. A verdict needs the 95% interval on the side of the margin; otherwise it is inconclusive and is reported as such.

| # | Hypothesis | Factors | Pass | Fail |
|---|---|---|---|---|
| H1 | The time gap explains most of the idealised gain | A0 versus one-factor changes (τ, δ, accel, speedDev) | τ alone gives ≥70% of A0's delay reduction | τ gives <40% |
| H2 | Field-fitted AVs do not give the thesis result | A2 versus A0, shares 0–100, fixed demand | A2 delay at 100% is ≥10% worse than 0% on corridors | A2 better than 0% by ≥5% |
| H3 | Commercial ACC harms at rising share | A1, 0–100, signalised and motorway | Delay or wave amplitude worse at some share by ≥3% | Monotonic improvement within 1% |
| H4 | A few designed dampers smooth locally, without capacity gain | A3 at 1, 2, 5, 10% | Speed variance −30% or better to 600 m **and** bottleneck discharge within ±2% | Variance change <10%, or discharge up ≥5% (then capacity claims are reopened) |
| H5 | Adjacency sets CACC's value | A4 at 10–90%, random against fleet clusters against bottleneck targeting | Clustered beats random by ≥5% discharge at equal share | Difference <2% |
| H6 | Human response can flip the sign | Recognition 0/50/100%, follow ±20%, cut-in −2 m, for A2 and A4 | City delay moves ≥ the AV effect itself in some cell | Moves <2% everywhere |
| H7 | Signal-free gains shrink with people crossing | A5 against optimised actuated, crossing demand 0/100/500/2,000 per hour per crossing, wait cap 60 s | At ≥500 per hour, A5 no better than actuated by >5% on all-user delay, within the cap | A5 keeps ≥10% vehicle gain within the cap at 2,000 per hour |
| H8 | Correlated faults dominate rare-event harm | Same stalled count, independent against common cause, assist capacity 1 per 25/50/100, refuge or stop in lane | Common cause ≥2× stranded person-hours | <1.25× |
| H9 | Fixed-demand gains do not survive demand and empties | Demand +0/+6/+25/+60%, empty 1.0/1.2/1.5/1.7, pricing on and off | Delay above 0% baseline in ≥50% of the grid without pricing | Below baseline in ≥80% of the grid without pricing |
| H10 | The last humans matter little unless control changes | 90/95/99/100%, A2 and A4; A5 on and off | Step from 99 to 100% ≤2% without A5 | Step >5% without A5 |

H10 is the direct answer to "what requires the last human to leave". Removing them only matters if a control scheme is switched on that could not run before. A human who follows signals and a fleet that can reserve can coexist, as [Dresner & Stone](https://www.cs.utexas.edu/~aim/papers/JAIR08-dresner.pdf) and the [white-phase work](https://arxiv.org/pdf/2212.06191) try to show.

Failing a hypothesis is a result. A failed H2 would mean I am wrong about the time gap, and would be reported prominently.

#### Step 3: progressive removal on a real city

**Cities.** Bologna as a rehearsal, for thesis continuity only, without reality claims. The A10 in Amsterdam for corridor validity. Melbourne for the city result, per [report 01](01-city-ground-truth.md). No share result is published for a city until it passes report 04 level 5 or 6. Berlin and Stockholm [fail that today](03-berlin-forensics.md).

**Design.**

- **Nested assignment:** one uniform draw per trip, so that each share is the previous one plus more cars. Every comparison is paired.
- **Shares:** 0, 1, 2, 5, 10, 20, 30, 50, 70, 90, 95, 99, 100%, of *active automated vehicle-km*. Record ownership share and local share too. If AVs are randomly ordered, an AV follows an AV with probability p, so 10% share has 1% AV–AV pairs (DEDUCTION).
- **Rollout:** random private adoption; high-mileage fleets; a contiguous AV zone with its boundary inside the accounting; bottleneck targeting.
- **Layers, reported separately, never merged into one curve:**
  1. *Physical:* same trips, departures and routes. Only control changes.
  2. *Operational:* dispatch, empties, curb dwell, charging, assist queue. Unserved requests are counted.
  3. *Behavioural:* route, time and mode choice, and price, with elasticities stated as a grid, not one guess.
- **End state:** 100% appears three times: independent A2, cooperative A4, and A4 plus A5. Otherwise the experiment confounds "no humans" with "central control". Buses, freight, emergency vehicles and people on foot stay in.

**Replications and budget.** 20 paired seeds to start, then the report 04 rule. 50 at endpoints and thresholds. Bimodal results are split by state, with breakdown probability reported. Screening: 13 shares × 5 classes × 3 rollouts × 3 demand levels × 3 human responses × 20 seeds ≈ 35,100 runs. At the [README](../../README.md)'s 3.3 thesis-sized runs per second, that is about 3 hours on the GPU in short submissions, one job at a time, keeping 3 GB VRAM free. A city is far larger (Berlin 24 h takes 149 s), so screen on Bologna and take only influential cells to Melbourne. Seeds are not field days: repeat with independent demand days where data exists.

**Metrics.** Primary, chosen before running: person-hours of delay including unserved trips; p95 door-to-door time; total and empty vehicle-km; conservation and collision failures.
Secondary: bottleneck discharge and breakdown probability; network accumulation and MFD; string gain by frequency; speed variance; cut-ins and merge delay; TTC and PET surrogates, which are not crash rates; emergency braking; bus and pedestrian delay once they exist; energy from a named model and powertrain.

**Dropped from the old draft.** The 10,080-run design without human response or a stated primary metric; "first Bologna, then Stockholm".

#### Step 4: honest scenes to film

Rules: same seed and demand in each panel. Show the real run from the preregistered set, not the best one. Persistent label saying *model result*, the AV class and the time gap. End each scene on the number and its interval.

1. **"Thirty-three thousand crashes."** The thesis's own I-80, 100% CACC, with each teleport lit up and a counter beside the headline gain. Then the same run at `dt` 0.1. Needs no caveat; it is the most honest thing here.
2. **"The ruler."** A ring where nothing moves differently but a ruler between cars. τ 0.6, 1.0, 1.32. Speed changes with no wave ever present. Then Stern's ring making its own wave, one car absorbing it.
3. **"One blue car."** Damper on I-24-like traffic with the variance trace behind it, fading by 1.4 km. Beside it, an eight-car commercial ACC platoon growing a 6 mph dip to 25 mph. Field numbers on screen as the target.
4. **"Three kinds of no humans."** The city at 100% three times: Waymo-fit, thesis ideal, cooperative. Same demand. The viewer sees that "no humans" is not one thing.
5. **"The merge bill."** A tight platoon arrives at a ramp, once with humans who respect it and once with humans who cut in at 7.6 m. Who pays is visible.
6. **"A beautiful junction meets a person."** Reservation dance at no pedestrians, then 500 people per hour with a 60 s cap. Show the vehicle capacity falling with the number. Only after H7's engine work exists.
7. **"The Presidio."** Fleet stalls with one cause, assist queue visibly filling, batteries counting down, an ambulance route closing. Labelled: injected fault, not a forecast. Beside it, the same number of stalls with independent causes.
8. **"Fuller."** Fixed demand first, smooth and beautiful. Then empties drawn in another colour, and demand rising. A counter of people moved, unchanged, against vehicle-km climbing.

Do not film: 100% ideal cooperative traffic alone with a percentage gain, a signal-free junction with nobody walking, or any run with teleports hidden.

### What only Erik can do

- **Identify the run behind PDF Figures 4.4 and 4.6**, with Adam Wallén. The raw XML is not in the repository.
- **Decide on a correction.** Whether and how to tell the supervisor, examiner or KTH about §4.2, §4.4, §5.3 and §6 is his and Adam's decision. I contacted nobody.
- **Dataset terms.** Accepting licences for Waymo Open Motion and any I-24 MOTION access needs his account. I did not try.
- **Scope.** Whether to build pedestrians, buses and stall states into the engine. H7 and H8 cannot run without them, and those are the questions the public will care about.

### Files added

- [`scripts/10_thesis_audit.py`](scripts/10_thesis_audit.py), [`scripts/10_thesis_audit_cases.py`](scripts/10_thesis_audit_cases.py), [`scripts/10_thesis_ring_windows.py`](scripts/10_thesis_ring_windows.py): reruns, read-only against the thesis repo. Run them inside the thesis flake's dev shell.
- [`thesis-audit/sumo_ledger.csv`](thesis-audit/sumo_ledger.csv), [`thesis-audit/ring_windows.csv`](thesis-audit/ring_windows.csv), [`thesis-audit/i80_collisions_summary.md`](thesis-audit/i80_collisions_summary.md): results.
