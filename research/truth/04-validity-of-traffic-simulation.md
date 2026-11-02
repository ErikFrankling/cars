# How much should we trust traffic microsimulation?

First draft by another model, 2026-10-31. Audited, corrected and extended the same day; the audit result is in the last section, [Reviewed by Opus](#reviewed-by-opus). No GPU was used. Three small CPU analyses were added, with scripts and outputs linked where they are used.

**Answer.** Erik is partly right. Traffic models have predicted the direction and rough size of big demand changes, and the Stockholm authors say the model was good enough for design decisions. The same paper shows its static model getting queue relief badly wrong. No opened source gives an audited sample of microsimulation forecasts checked after opening, so "true to life, at least relatively" is plausible for flows and unproven for queues.

For `cars` specifically, the largest error found here is not in the driver model. Berlin's simulated flow at 08:00 is about half the observed count, against a real day-to-day difference of about 6 to 9%. Default Krauss also overstates motorway capacity by at least 19% at dt 0.1 s, and its signal discharge changes by 15% between dt 1 s and dt 0.1 s at 50 km/h.

## How to read the evidence

- **Measured:** observations of real traffic, or comparisons with them. A measured forecast error is not a measurement of the simulator kernel alone.
- **Modelled:** simulation output, handbook values, fitted quantities. "Measured in a simulation" stays modelled.
- **Opinion:** guidance, an author's interpretation, or my proposal.
- **Not opened:** the source could not be opened in this session. Those are listed in the audit, and nothing numeric rests on them.

## 1. Forecast versus reality after road projects

None of the large samples below isolates microsimulation. They test whole forecasting systems, mostly strategic demand models.

| Study, grade | Result | Sample, funder, limits |
|---|---|---|
| [Flyvbjerg, Holm & Buhl][F], **measured** | 50% of road projects off by more than ±20%, 25% by more than ±40%. Actual minus forecast, over forecast: mean **+9.5%** (95% CI 3.0 to 15.9), SD **44.3%**. 21.3% below −20%, 28.4% above +20%. | **183 road projects** (170 highways, 10 bridges, 3 tunnels), opened 1969–1998, 14 countries including Sweden. Opening-year counts. Selected by data availability, so not a random sample. Funded by the Danish Transportation Council and Aalborg University. The stated main causes are trip generation and land use, not driving behaviour. The copy opened is a referee draft of the published paper. |
| [Hoque, Erhardt et al. 2021][H], extending NCHRP 934, **measured** | Mean **−5.6%**, mean absolute **17.3%**, 5th to 95th percentile **−37.6% to +36.9%**. 68.5% of projects below forecast. 95% meet the "half-lane rule": the error would not have changed the lane count. 46.5% deviate less than a traffic count is expected to. | **1,291 road projects, 3,912 segments**, six US states and four European countries. 44% come from one agency. Authors include practising forecasters. Funding statement not read. Bias changed sign compared with Flyvbjerg. Higher-volume roads, shorter horizons and use of a travel model all improved accuracy. |
| [POPE meta-analysis 2015][P], **measured** | **68%** of schemes within ±15% of forecast flows. Widening 62%, bypass corridors 74%, all four motorway upgrades within 15%, every one below forecast. Bypassed old roads: **78% outside ±15%**. Only 28% of schemes had journey-time benefits within 15% of forecast, 74% within 50%. | **84 schemes, 81 with comparable flows**, mostly opened 2002–2012. Commissioned by Highways England about its own programme. Journey-time comparison only for 43 schemes. Of the 30 schemes outside ±15%, stated reasons (more than one allowed): background growth 19, routing 9, land use 8, other schemes 7, **modelling accuracy 3**. More complex models did not clearly help: within ±25% were fixed demand 81% (n=48), elastic 93% (n=27), variable demand 60% (n=5). |
| [Eliasson et al.][E], Stockholm 2006, **measured vs modelled** | Cordon traffic **−16% predicted, −20% actual**. AM inbound −16 vs −19, PM inbound −18 vs −22, off-peak inbound −14 vs −24. **Queue relief failed:** on Klarastrandsviadukten–Örbyleden the model gave −1.0 min where reality gave −12.8 min, a delay cut of 19% against 94%. | **One scheme.** Funded by VINNOVA. Authors include people from the consultancy that ran the model, so not independent. Model was Sampers with **static** EMME/2 assignment, not a microsimulator. Authors call the queue failure "the one major shortcoming" and say dynamic assignment "should be a high priority". Work-trip response was wrong: 42% predicted to change destination, about 0% did. |
| [West, Börjesson & Engelson][G], Gothenburg 2013, **measured vs modelled** | Peak cordon effect close. Off-peak 7% predicted, 10% measured. Travel-time levels **33% under on one arterial and 33% over on another**, yet the before-after change was "generally neither underestimated nor overestimated". | **One scheme**, same national model. KTH and Sweco authors, so not independent. Value-of-time distribution "had to be adjusted to be consistent with observed outcome", so this is not a blind forecast. Funding not stated in the text searched. |

**What this says about "at least relatively" — opinion.** The Gothenburg result is the best evidence for Erik's position: wrong levels, right change. Stockholm is the warning: right flows, delay effect off by a factor of up to five, because the model had no spillback. Those two together suggest relative prediction works for demand and fails for queues unless the model represents queues. A microsimulator does represent queues, which is an argument for it, but I found no multi-project evidence that it delivers.

### A live case: the Berlin A100 extension, opened 27 August 2025

This is the exact situation Erik describes, and it is in a city we already simulate.

- **Modelled, 2009:** a microscopic simulation for the planning approval showed the road corridor could cope; two other consultants doubted it, per [a January 2024 motion in the Berlin parliament][A1409], which is a political document. The Elsenbrücke then lost its six-lane state, and demand forecasts rose.
- **Modelled, stated May 2025:** the Senate expected [49,000 vehicles per weekday on the Elsenbrücke, 29,000 of them to or from the A100][A22745].
- **Conflicting official readings of the same outcome.**
  - The Berlin senator told parliament in September 2025 that [traffic "did not behave as in the simulation"][A058] and that no figures existed yet.
  - The federal government said in February 2026 that [observed traffic confirms the simulation][A4236]. It describes capacity deficits at 5 of 9 junctions examined and a macroscopic shift of 43,800 vehicles a day off city streets.
  - The Green opposition's question cites [level of service F at 9 or 10 of 31 junctions][A3986]. These two denominators are not reconciled in the documents I read.
- **Measured, weak:** [102 accidents around the junction, 30 more than the year before][A3986], as stated in that opposition question. Concurrent bridge closures confound this: [Ringbahnbrücke and Westendbrücke][A058].
- **Not available:** I found no published numeric comparison of forecast and outcome, and did not read the simulation itself. [Counts were made and congestion analysis was in progress in December 2025][A24457]. The only published junction counts I found are [April 2025, before opening][A23905], and that answer says there are no working permanent detectors at the junctions asked about. Berlin's [public detector archive][BA] listed months only to June 2025 when I queried it.

## 2. What professionals accept, and what that proves

These are **opinion/guidance**, not measured predictive accuracy.

| Guidance | Criteria | Comment |
|---|---|---|
| [FHWA Toolbox III, 2004][FH04] | Wisconsin DOT draft of 2002: >85% of hourly link flows within 100 veh/h below 700, 15% from 700 to 2,700, 400 veh/h above 2,700. GEH<5 for >85%. | Calibration stopping rule, not a validity test. |
| [FHWA 2019][FH19] | Cluster real days and pick a representative day. I: 95% of simulated intervals in ±1.96σ, one miss allowed under 20 intervals. II: two-thirds, and both critical intervals, in ±1σ. III: mean absolute error ≤ between-day BDAE. IV: absolute bias ≤ BDAE/3. Worked example: BDAE 1.84 min, so bias limit 0.61 min. | The only guidance here tied to real variation. Adopted below, with a holdout added. |
| [UK TAG M3.1, May 2026][TAG] | Same flow bands, GEH<5 for >85%, journey times within 15% or 1 minute on >85% of routes. | Highway assignment guidance, not a behaviour certificate. |
| [TAG M1.2, May 2020 copy][M12] | Assume 95% confidence of ±5% for automatic counts and ±10% for manual counts. Journey-time runs to ±10% of the mean at 95%. Survey in neutral months, Monday to Thursday, March to November. | Sets the observation error any gate must allow for. A newer version exists and was not read. |
| [TfL Guidelines v4, 2021][TFL] | Vissim: GEH<5, **<3 strongly recommended on critical links**; entries within 5%; saturation flows within 10%; journey times within 15%; demand-dependent stages within 10%. "**Minimum of 20 seed values**" for calibration and validation, and "as a guide 20 simulation runs are normally sufficient". Seeds must be a continuous range, no cherry-picking. Queue length is not a validation criterion, but queues must appear at the right place and time. | More operational than GEH alone. |
| [Trafikverket simulation handbook, August 2014][TV14] | GEH<5 is "good agreement" and, verbatim, GEH "inte har någon statistik koppling" (no statistical basis). Recommends adding t-tests or Kolmogorov–Smirnov. Says Vissim defaults tend to give slightly too high saturation flows. | Swedish regulator's own critique. |
| [Trafikverket restidsnyttor 2024][TV24] | Says separate validation datasets are often missing for lack of resources. | Plain statement of normal practice. |
| [FGSV 388, 2006 catalogue][FGSV] | 40-page guidance. Catalogue shows no criteria. **Full text not obtained.** | German numbers unknown. |
| ATAP | **Not opened.** The page timed out twice, so its criteria are removed from this report. | |

### GEH against reality

`GEH = sqrt(2(M−C)²/(M+C))`, specified in [TAG][TAG]. It scales with the square root of the flow unit, so a 15-minute count gives half the hourly value. GEH=5 allows +56.6% at 100 veh/h, +16.4% at 1,000 and +11.5% at 2,000 (my calculation). Origin: [FHWA traces its use to the Wisconsin draft][FH04]. I found no study showing GEH<5 predicts forecast success.

**New measurement: how does a real day score against another real day?** Same detector, same hour, seven days apart, Tuesday to Thursday, 07:00–18:59, September 2024, Berlin. [Script](scripts/validity_berlin_noise.py), [output](04-berlin-noise-floor.json).

| Unit, no historic filter | Pairs | Median difference | Median GEH | GEH<5 | GEH<3 | Units passing >85% GEH<5 |
|---|---:|---:|---:|---:|---:|---:|
| One lane detector (347) | 26,190 | 8.7% | 1.64 | **88.5%** | 74.2% | **72%** |
| All lanes at a site (171) | 12,554 | 6.3% | 1.64 | 88.2% | 74.0% | 71% |

**Measured.** Reality itself barely clears the >85% GEH<5 gate network-wide, and over a quarter of detectors fail it against their own previous week. So the gate is not lax in aggregate: it is close to the noise floor. It is also not discriminating, because the same 5 allows far more error than the median real difference. Limits: one month, one city, detector faults are probably included, and the archive's own correlation filter moves the pass rate only to 90.1% for lanes.

## 3. Independent evaluations of SUMO, Vissim and Aimsun

I found **no independent study that runs all three against the same real trajectories**. A [2024 three-platform comparison][ORNL] (Saroj et al., Winter Simulation Conference, US DOE funded) compares the simulators with each other and finds network results consistent except at high demand for energy; its Chattanooga data is scenario input, not a truth test.

| Study, grade | Models and data | Result | Independence and limits |
|---|---|---|---|
| [Brockfeld et al.][BR1], **measured/modelled** | More than a dozen models; DGPS cars, loops, human observers. | Errors of **15–20% in headway and travel time, 2–7% in speed**, "seem to be the minimal reachable level". No best model. | Brockfeld and Wagner, DLR, the institute behind SUMO. Abstract only. |
| [Brockfeld, Kühne, Skabardonis & Wagner][BR2], **measured/modelled** | Several models on a one-lane rural road. | Mean error about **16%**, ranging **2.5–25%** across parts of the data. Fewest-parameter models did best. | As above. Abstract only. |
| [Kesting & Treiber 2008][KT], **measured/modelled** | IDM, VDIFF; **3 urban traces from a radar-equipped car**. | Spacing errors **11–29%**. Fitted parameters hit bounds, for example τ=20 s, so they are not literal behaviour. | Treiber co-developed IDM. Tiny sample. |
| [Zhu et al. 2019][Z], **measured/modelled** | GHR, Gipps, IDM, FVD, Wiedemann 99, the Vissim model; **42 drivers, 2,100 periods**, Shanghai. | Calibration 19–25%, validation 19–34%. IDM best at 19%. Between-driver error **31%**, within-driver 19%. Collisions appeared in validation. | Independent of the model authors. One city. Krauss not tested. Funding not stated in the text searched. |
| [Schrader, Al Abdraboh & Bittle 2023][SCH], **measured/modelled** | SUMO IDM, EIDM, Krauss; roadside radar at signals, Alabama. | Measured mean acceleration **0.89 m/s²** against the default 2.6. Using the measured value "fails volume-based calibration". Defaults match mean and median but not distribution shape. | Independent of SUMO developers. Abstract only, sample unknown. **Lesson: SUMO's `accel` is not the quantity a radar measures.** |
| [Salles, Kaufmann & Reuss 2020][SAL], **measured/modelled** | SUMO 1.0.1 Krauss, IDM, EIDM; drone at a 50 km/h signal, **1,050 trajectories, 540 starts from rest**, 30 green phases. | Krauss matches the observed speed curve only with low acceleration, which contradicts the measured acceleration curves. | Authors propose EIDM, so not neutral. Partly funded by Bosch. |
| [Xiao et al. 2005][XI], **measured/modelled** | Aimsun, Vissim on I-494, Minnesota; detector speeds and flows. | RMSP **12–22% before calibration, 4–6% after**, 4–6% on validation. The two are nearly equal. | Federally funded ITS Institute. One site, not trajectories, old versions. |
| [Baza-Solares et al. 2022][BZ], **measured/modelled** | SUMO 1.3.1, Aimsun 8.2; **7 detectors**, 1 peak hour, Bucaramanga. | Aimsun closer at 4 of 7, SUMO at 3. Both pass a t-test on 8 runs. | The often-quoted "13%" is the two simulators against each other, and the paper gives no real total travel time. Its text says 17.7 h (13%), its Table 11 says 18.2 h (12%). |
| [Ronaldo & Ismail 2012][LIU], **measured/modelled** | SUMO, Aimsun; E266/E75, south Stockholm, speeds. | Best SUMO fit **τ=1.7 s, σ=0.3**, far from defaults. Grid minimum RMSE about 13.9 km/h for SUMO, 19.4 for Aimsun. | Linköping student thesis, one site and peak. |
| [Liang 2025][LI], **measured/modelled** | SUMO with added logic vs SMART; Waymo data, 8 s horizon. | Realism **0.6532 vs 0.7511**, minADE **5.83 vs 1.54 m**. | Single-author preprint, University of Michigan. Benchmark metric, not flow validity, and not untouched SUMO. |

**Pattern — opinion.** Trajectory error about 15–30% is what the literature keeps finding, and between-driver variation is larger than between-model variation. So choosing a better car-following equation is unlikely to be the largest gain. Parameters and measurement definitions matter more.

**Trajectory data itself is suspect.** [Coifman & Li 2017][CL] (partly NSF funded), re-extracting NGSIM from video, report that **more than 13% of I-80 trajectories overrun their leader**, implying 747 collisions in 45 minutes that did not happen, and that the errors cannot be cleaned out afterwards. Any calibration on raw NGSIM inherits this. `cars` has an `i80_day` fixture, but it is a thesis scenario; I did not check whether its parameters came from NGSIM.

**Variability the equilibrium curve cannot show (measured).** [12 loops on the German A1][N] show scatter and headway regimes that depend on traffic state. A [25-car platoon experiment][J] (Chinese national funding) shows disturbances growing along the platoon, and non-unique speed–spacing states. These are test cases for dynamics, not numbers to match.

## 4. What is specifically wrong in SUMO's models

### Krauss

SUMO 1.28 source: [`MSCFModel_Krauss.cpp`](file:///home/erikf/projects/personal/thesis-src/sumo/src/microsim/cfmodels/MSCFModel_Krauss.cpp). Defaults: [length 5, minGap 2.5, accel 2.6, decel 4.5, σ 0.5, τ 1][SV].

1. **Step length is the reaction time.** [SUMO's docs say so][SS]: at least one step, and τ is headway, not reaction. So changing `--dt` changes driver behaviour. There is no separate driver delay in the default.
2. **Noise scales with the step.** `dawdle2` subtracts `ACCEL2SPEED(sigma * myAccel * random)` per step, so its variance per unit time depends on step length unless `sigmaStep` is set. Below `accel`, the noise scales with speed instead, so a starting car is treated differently.
3. **Capacity is set by τ and the footprint**, not by a measured distribution. Equilibrium headway is `τ + (length+minGap)/v`, so it falls with speed. At 30 m/s that formula gives 2,880 veh/h; the repo's [fundamental-diagram run](file:///home/erikf/.t3/projects/cars/results/phenomena/freeway_fd.csv) measures 2,757.
4. **Congested wave is `(length+minGap)/τ` = 27 km/h.** Measured in the same file: flow falls about 27 km/h per unit density between 45 and 120 veh/km. Real freeways are slower, see section 5.
5. **No driver heterogeneity by default**, against [between-driver error larger than within-driver][Z]. No persistence: noise is independent each step.

**New measurement: is the 1.20 s stop-line headway just a 120 km/h fixture artefact?** The repo's [`signal_discharge`](file:///home/erikf/.t3/projects/cars/results/phenomena/README.md) uses a 33.33 m/s road. I ran SUMO 1.28 on CPU, 40 stored cars, 10 seeds per cell, one lane. [Script](scripts/validity_krauss_discharge.py), [data](04-krauss-discharge.csv). **Modelled** saturation flow, veh/h per lane, from the median headway of positions 5–20:

| Road speed, τ=1 | dt 1.0 s | dt 0.5 s | dt 0.1 s |
|---|---:|---:|---:|
| 30 km/h | 1,604 | 1,742 | 1,846 |
| **50 km/h** | **1,987** | 2,192 | **2,286** |
| 70 km/h | 2,136 | 2,441 | 2,599 |
| 120 km/h | 2,157 | 2,566 | **3,074** |

Against about 1,900–2,100 in the field (section 5): partly an artefact, partly real. At 50 km/h the default is **+20% at dt 0.1 s** and **+5% at dt 1 s**. City runs use [`--dt 1`](file:///home/erikf/.t3/projects/cars/scripts/final_runs.sh), so they land near reality, apparently because the coarse step adds delay. Moving to a finer step without raising τ would inflate urban signal capacity. At 50 km/h and dt 0.1 s, τ=1.5 gives 1,742, so the matching τ sits between 1 and 1.5. That agrees with [the Stockholm thesis fit of 1.7][LIU] in direction only.

### LC2013

The primary source is [Erdmann's own paper][ER], and it is a developer evaluation.

- It states its improved metrics are avoided teleports and waiting. "Validating" there means "fewer deadlocks": "improved traffic flow is not generally a sign of a more realistic model".
- Its lane-use test feeds [one 1995 Saturday of A3 detector data][ER] and checks the simulated flows stay in equilibrium; it does not compare against held-out reality.
- Lane-change rate is compared with one US survey value, quoted as 0.26 changes per km in the text and 0.22 in its footnote.
- It says calibration and validation were still to be done, and that drivers "may accept much lower" gaps than the model allows, which matters most at ramps. **I found no later independent validation of LC2013's gap acceptance or timing.** The closest I found is a [2020 Chalmers thesis calibrating SUMO to highD][CH], whose abstract gives no numeric lane-change result; I read only that abstract.
- Lane changes are [instantaneous by default][SO] (`--lanechange.duration` 0).
- The repo's own [lane-change comparison](file:///home/erikf/.t3/projects/cars/research/lanechange-validation.json) is marked incomplete and its commands are SUMO comparisons, so it does not test reality.

### Junctions

- **Mechanism:** [right-of-way, internal lanes, blocking inside the junction][SI]. Conflicts use a time window, [`jmTimegapMinor` default 1 s][SV], with the same value as fallback in [`MSLink.cpp`](file:///home/erikf/projects/personal/thesis-src/sumo/src/microsim/MSLink.cpp). There is no accepted-gap distribution by default.
- **Why it matters — opinion:** the Swedish handbook treats [critical gap as a calibration quantity][TV14], with 50% of drivers accepting it. A 1 s window is a different quantity, so it should not be compared with published critical gaps directly.
- **Evidence:** I found no independent multi-site validation of SUMO's junction model against real gaps. Measured critical-gap numbers are not stated here because the sources I found returned 403.
- **Local:** [`results/junctions.txt`](file:///home/erikf/.t3/projects/cars/results/junctions.txt) compares `cars` with SUMO only, so it says nothing about reality.

### Teleports

[SUMO's docs][ST]: a vehicle waiting past the threshold (default 300 s) leaves the network, travels invisibly, and reinserts. Our city runs use a shorter [120 s plus `--ignore-junction-blocker 20`](file:///home/erikf/.t3/projects/cars/scripts/final_runs.sh). [Erdmann][ER] used 120 s on Braunschweig and 300 s on the A92. Teleports remove the vehicles that make up a queue, so congestion, spillback and travel time are all understated, in exactly the regime the Stockholm paper says matters. The reported counts are [23,715 in Berlin](03-berlin-forensics.md) and [294,409 in Stockholm](02-stockholm-why-overloaded.md) (from those reports, not rechecked here). Results from those runs are not evidence about real queues.

## 5. Real measured values

**Status column:** current simulator against the band. Bands are my proposal.

| Quantity | Measured or handbook | Grade, sample, source | Proposed band | Today |
|---|---|---|---|---:|
| **Signal saturation flow** | **Split 1,967, Prague 2,093 veh/h** (mean headways 1.83, 1.72 s, dry, weekday). Rain raises headway 12–15%. | Measured, a few intersections, passenger cars only, [Cvitanić & Maljković][CV]. | 1,800–2,100 at 50 km/h, dry, through lane. | dt 1: **pass** (1,987). dt 0.1: **fail** (2,286). `signal_discharge` at 120 km/h: **fail** (3,000), and the fixture needs fixing. |
| | **1,900 f/gh** base in Sweden. | Handbook, [TRVMB][TRV]. | | |
| | 1,900–2,100 is what TfL's Vissim template gives. | Modelled, [TfL][TFL]. | | |
| | Reductions in rain 0–4% light, 3–9% moderate; 1,900→1,780 is a simulation default, not a measurement. | Measured reductions, Birmingham AL, [UTCA][UT]. | | |
| **First headways** | Median **1.98, 3.09, 2.34, 2.36, 2.18 s** for positions 1–5 (n=273, 271, 71, 22, 4). | **New, measured**, one Sunday, Braunschweig, [script](scripts/validity_dlrut_discharge.py), [data](04-dlrut-discharge.json). Cars only. | Within ±15% of site median, positions 2–4. | SUMO 50 km/h, positions 2–4: dt 0.1 **2.73, 1.84, 1.61**; dt 1 **2.78, 2.52, 2.14** ([output](04-krauss-positions.json)). Fine step is 22–32% short at positions 3–4; 1 s step is 7–10% off. |
| **Start-up lost time** | About 2 s is FHWA's [rule of thumb][FS]; total lost time default 4 s per phase. | Opinion. | Unresolved. | My Sunday estimate (0.87 s, n=22) rests on only four cars at position ≥5, so it is **not usable**. |
| **Queue start wave** | **22.3 km/h** median, p10–p90 16–28. | **New, measured**, n=22 queues of ≥4 cars, one site, Sunday. | 16–28 km/h. | SUMO 50 km/h: dt 0.1 **39.7** (fail), dt 0.5 **28.7** (edge). dt 1 was **unstable** (2–17 km/h across seeds, with uneven stored queues): that test needs rework. |
| **Jam spacing** | **6.96 m** centre to centre, cars only (144 veh/km). | **New, measured**, same sample, bounding boxes. | 6.5–8 m for cars. Measure truck effect separately. | 7.5 m (133 veh/km): pass. |
| | **134.5 veh/km/lane** in Sweden. | Handbook, [TRVMB][TRV]. | | |
| | 150 veh/km is [an illustrative base case][W], not a measurement. | Modelled. | | |
| **Motorway capacity** | California SR-24 at a bottleneck: 176.2 per 5 min = **2,114 veh/h/lane**. Mean of three sites and specifications: 154 = **1,848**. | Measured, [Anderson & Davis][AD]. | **1,800–2,300** sustained per lane. Treat as Weibull, not a constant. | SUMO **2,757**, cars **2,737**, highest of the density bins in `freeway_fd`, spaced 15 veh/km: **fail, at least 19% above the band**, at dt 0.1, 30 m/s. Not run at dt 1. |
| | Sweden: 2-lane carriageway **2,160** rural, **2,025** urban per lane; 3-lane **1,933**, 1,867. Authors admit gaps in the empirical basis. | Handbook, [TRVMB][TRV], with [VTI 784 cited][TRV] (not opened). | | |
| | About 2,000 "usually stated". Quoted values are often scaled up from 5 minutes, and an hour is about **15% lower**. | Opinion, [Trafa/Movea][MO]. | | |
| | About 2,300 at bottlenecks in free flow. | Cited in [Jin][JN]. | | |
| | Capacity is random, Weibull-distributed. | German data, [Brilon & Geistefeldt][BG]. | | |
| | Rain −10 to −11%, snow −12 to −20%. | Fitted to Baltimore, Twin Cities, Seattle data, FHWA, [weather study][W]. | | |
| **Capacity drop** | **Most studies 3–18%, full table −8 to 25%**, by site and method. **Median 10%, 16 of 17 papers find one.** | Measured, [Anupriya et al. Table 1][AN] adapted from Oh & Yeo; [Hall's review, via Anderson & Davis][AD]. | 0–18%. | The fixture uses IDM with accel 0.3: SUMO **50%**, cars **32.5%** on the current tree, identical across three seeds ([edges](file:///home/erikf/.t3/projects/cars/results/phenomena/capacity_drop_edges.csv)). [README](file:///home/erikf/.t3/projects/cars/results/phenomena/README.md) still says 55.2 and 27.8. Fail, but the fixture was built to show the effect, not to match it. |
| | Toronto: up to 10%, with discharge within about 50 vehicles of a constant trend. | Measured, 2 sites, [Cassidy & Bertini][CB]. | | |
| | **No drop at all** at 3 California bottlenecks, ruling out well under 10%. | Measured, [Anderson & Davis][AD], economists using instrumental variables; no external funding. | | |
| **Freeway jam wave** | **−16 to −17 km/h** extended jams, −18 isolated waves, A5, about **400 congestions** across German freeways. OR-217: −20. | Measured, [Treiber & Kesting][TK]. | **−12 to −22 km/h**. | Equilibrium slope −27 from the FD file: fail. `phantom_jam` Krauss ring [−7.2](file:///home/erikf/.t3/projects/cars/results/phenomena/README.md): fail, unexplained, and it disagrees with −27. IDM ring −21.8: pass, but near-zero stopping, so a weak test. |
| | Review ranges −20 to −15, and −18 to −10. | [Treiber, Kesting & Helbing][TS]; [Tian et al. citing Rehborn][TI]. | | |
| **MFD** | Exists in Yokohama: **500 detectors, 140 taxis, December 2001**. "Suggests, but does not prove". | Measured, [Geroliminis & Daganzo][GD], UC Transportation Center. | No universal number. | Fixture only, no field comparison. |
| | Across more than 40 cities, network topology explains about **90%** of critical accumulation variation (adj. R² 0.88, N=107). Road density 23.46±10.36 lane-km/km². Returns diminish with network size. | Measured, [Loder et al.][L], ETH grants. | Compare same-city shape: peak and critical accumulation within field band. | |
| **Day-to-day** | Lane-hour count median difference **8.7%**, site 6.3%. P95 lane 56%, inflated by faults. | **New, measured**, Berlin, section 2. | See checklist. | Berlin 08:00 [34,405 vs 67,405 per hour](03-berlin-forensics.md), a −49% gap, is far outside it. |

**Weak points to keep in view.**

- The new discharge numbers are a single Sunday at one junction. 422 of 641 usable records come from one signal, and Sunday drivers may discharge more slowly than commuters. They show the method works, and they are not a population value. Only four cars reached position 5, so **this sample does not establish saturation headway.**
- Bounding-box length has a median of 3.47 m, which is shorter than real cars, so crossing times carry a small offset. Headways are less affected.
- "Fail" means the current fixture and configuration against a real-world band. It does not always mean the model cannot match.

## 6. Coverage

Searches were not exhaustive and this is not a systematic review. The strongest ex-post samples test whole forecasting systems. The direct microscopic studies test specific trajectories or single sites. Neither converts into a general SUMO accuracy percentage.

---

## Reviewed by Opus

### What held

- **Flyvbjerg:** 183 projects, 50% beyond ±20%, 25% beyond ±40%, +9.5%, SD 44.3%, all as written.
- **POPE:** 68%, 78%, outliers 1 and 3, Table 4–3's 30 schemes.
- **Stockholm:** every Table 1 number quoted was correct.
- **GEH:** the arithmetic and the Wisconsin provenance. TAG May 2026 date. Trafikverket's "no statistical link" remark.
- **Others:** Kesting & Treiber 11–29%, Azevedo 101 parameters and 30 sets, Jiang's 25 cars, Neubert's 12 loops, Yokohama's sensors, Cassidy & Bertini, FHWA 2019 criteria, FHWA weather values, Liang's table, SUMO defaults and teleport mechanism. The draft's replication arithmetic (385 runs, 9.5%) is correct.
- **Azevedo's caveat stands:** [counts and speeds can fit under both calibrations][AZ] while trajectory distributions differ. It is one Portuguese motorway, with MITSIMLab and 101 parameters.

### What was wrong or missing

1. **Stockholm's main finding was missing.** The draft called it a success with "uneven subgroup performance" and did not say that the model was static or that it missed queue relief by up to a factor of five. The authors put this in the abstract.
2. **ORNL was misdated:** 2024 Winter Simulation Conference, not 2025. Its funder is stated on the page the draft cited.
3. **TfL was softened:** "roughly 20 seeds normally sufficient" omitted the "minimum of 20 seed values" requirement. Both are in the text.
4. **The SUMO–Aimsun "13%" was misread as evidence about accuracy.** It is simulator against simulator, with no real value, and the paper contradicts itself (17.7 h and 13% vs 18.2 h and 12%).
5. **Funders marked unverified were findable:** Flyvbjerg, Stockholm, Jiang, Coifman, Loder, Salles.
6. **POPE's sample:** 84 total, 81 comparable. The attribution was missing: modelling accuracy is named for 3 of 30 misses and background growth for 19. That is the most relevant fact in the document for a simulator builder.
7. **The largest recent sample was absent:** Hoque/NCHRP 934, 1,291 projects.
8. **Real values were declared unavailable** when published tables, Swedish handbook values and local data exist. The earlier section 6 thresholds were arbitrary (for example "jam front within 2 km/h"), and it asked for 50 comparable days and 1,000-run caps with no basis. I replaced them.
9. **Claims not reproducible from the cited pages were dropped:** Alabama's "9 and 7 signals, six weeks" and ATAP's table.
10. **A near miss of my own.** My first Berlin analysis had a grouping bug, which I caught from an implausibly small sample; the search that led to the A100 case had the wrong year in my query. The numbers above are after the fix, and the opening date is from the Bundestag paper.

### What remains unknown

- Whether microsimulation predicts intervention effects better than simpler tools, across projects. **I found no audited sample.** That is not proof none exists.
- What happened numerically at the A100, and what its simulation actually contained. Official statements conflict.
- Measured saturation headway in Sweden, measured critical gaps, measured start-up lost time at a site with long queues.
- LC2013's real gap acceptance and timing. Independent junction-model validation.
- Stockholm-specific day-to-day variation.
- Why `phantom_jam` gives −7.2 km/h where the FD implies −27. Why capacity-drop results are identical across seeds.
- Whether fixed-τ SUMO at dt 1 reproduces motorway capacity, because the FD was only run at dt 0.1.
- Not opened: Hollander & Liu full text, Pourabdollah (403), the MULTITUDE guideline PDF (landing page only), Ciuffo et al. JRC report, Daamen book, ATAP (timeouts), Wang's thesis, Hoque's funding note, Li & Prevedouros (403), Chung et al. directly, Brilon's original 2005 paper. Earlier statements resting only on these were removed. So were the draft's data-resolution targets and its SUMO default-network row, which were opinion or are not needed here.

### Validation protocol for this repo

Everything here is a proposal, apart from the numbers it links to. Freeze it before looking at test data.

**Rules**

- [ ] Report three claims separately and never merge them: **verified** (equations), **SUMO-compatible** (a software baseline), **empirically valid**. Only the third says anything about reality.
- [ ] Freeze before testing: code hash, parameters and bounds, demand, signals, seeds, metrics. Any change after a look at test data is a new model and needs a new holdout.
- [ ] Measure the same way in sim and field: same detector position, same headway definition, same time base. Record it with each result.
- [ ] Every result carries an `empirical` or `compatibility` label. No "validated" without a level and a dataset.
- [ ] Runs with teleports are diagnostic only and cannot pass a gate above Level 2.

**Levels and thresholds**

| Level | Test | Pass | Fail or inconclusive | Runs today? |
|---|---|---|---|---|
| 0 Verification | Conservation, overlap, dt convergence, determinism. | Zero unexplained vehicles. Metrics stable from dt 0.1 to 0.05. | Any overlap or loss. | **Yes**, CPU or queued GPU. |
| 1 SUMO compatibility | `scripts/golden.py`, `junction_tests.py`, `cmp_*`. | As now. **Never reported as reality.** | | **Yes**, exists. |
| 2 Physical bands | Section 5 table, with fixtures changed to real speeds (50 km/h signal, 110 km/h motorway) at **both dt 1 and dt 0.1**, cars and SUMO. | Saturation 1,800–2,100. Motorway 1,800–2,300 sustained. Freeway wave −12 to −22. Queue start wave 16–28 km/h. Jam spacing 6.5–8 m. Drop 0–18%, reported by site. | Any out of band fails. | **Yes.** Today's results fail on saturation at dt 0.1, capacity, jam wave. Fixtures need new parameters. Needs a GPU slot for `cars`, SUMO runs on CPU. |
| 3 Driver | Open-loop replay against a measured leader on [TGSIM](file:///home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-tgsim), DLR and HIGH-SIM. Split by recording and vehicle, as in [report 05](05-real-human-driving.md). | Beats constant-speed and calibrated-Krauss baselines, CI excluding zero. Gap RMSE about 15–30% is the expected floor, so do not require lower. No overlap. | No raw NGSIM without [the Coifman caveat][CL]. | **Yes**, CPU. Data on disk, QC first. |
| 4 Junction | Observed arrivals and signals on [DLR-UT](file:///home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-dlrut), one signal withheld. | Position 2–4 headway within ±15%. Start wave in band. Per-movement discharge within 10%. | Weekday data required for saturation. One Sunday is inconclusive. | **Partly.** Extraction runs, saturation sample too thin. |
| 5 Corridor | Probe times and counts from different systems: Amsterdam primary, per [report 01](01-city-ground-truth.md). | FHWA criteria I–IV on held-out days. Each critical location passes alone. Queue onset within one 5-min bin. | Observation error exceeds gate: inconclusive. | **No.** Historical export untested. |
| 6 Network | Held-out Berlin detectors, then any city with real demand. | Replicate-against-day no worse than day-against-day on the noise floor below. | Gap larger than noise floor is a demand fault first. | **Berlin fails now**, and per [report 03](03-berlin-forensics.md) the demand is the first suspect. |
| 7 Intervention | Blind before-after, see below. | Correct sign. Effect error ≤25% of the observed effect where identifiable, for flows **and** delay. | Effect within noise: inconclusive, not a pass. | **No.** Needs post-opening data. |

**Noise floor (Level 6)**

- [ ] Compute it, do not assume it: [`validity_berlin_noise.py`](scripts/validity_berlin_noise.py) now, extended to all 2024 months in the [open archive][BA].
- [ ] Gates at hourly lane level, from the table in section 2: **median GEH ≤ 2.0, GEH<5 ≥ 85%, GEH<3 ≥ 70%**, plus median absolute difference ≤ 1.25 × the field value in each flow band.
- [ ] Compare **one replicate against one day** with **one day against another**. Comparing a seed-averaged mean against a day has less variance by construction, so it needs a stricter gate.
- [ ] Report the TAG and GEH<5 result for compatibility, and never as the pass criterion alone.
- [ ] Exclude nothing silently: state detector exclusions, and report the filter's effect (88.5% vs 90.1% here).

**Holdout**

- [ ] Split by whole day and whole site, never by row or frame.
- [ ] Berlin proposal: fit on March to April 2024, develop on May, **lock September and October 2024** weekdays, plus 30% of sites never used. Use [TAG's neutral period][M12]: Monday to Thursday, March to November.
- [ ] Hold out one signal at DLR-UT. Hold out at least one whole city or corridor.
- [ ] Demand fitted to a detector cannot then be validated by that detector.

**Replications**

- [ ] Start with 20 seeds, [TfL's minimum][TFL], as a continuous range. Never pick seeds.
- [ ] Then apply the [FHWA formula][FH19b] to the metric's own variance. If it asks for more than 20, [FHWA says investigate instability][FH19b] instead of running more.
- [ ] Target 95% half-width ≤ BDAE/3 or 1% of mean travel time, whichever is larger.
- [ ] Bimodal outcomes (breakdown or none): report breakdown probability and each state separately. Zero failures in 30 runs still allows a 9.5% failure rate.
- [ ] Intervention comparisons use paired seeds and the SD of the paired difference.
- [ ] Field days are the real uncertainty. More seeds do not replace them.

**Calibration discipline (opinion, motivated by [Azevedo et al.][AZ] and [Schrader et al.][SCH])**

- [ ] Fix measured inputs first: signals, geometry, demand. Then behaviour.
- [ ] Keep several near-optimal parameter sets and report the spread.
- [ ] Treat `accel`, `tau` and `sigma` as model parameters, not as measured quantities.
- [ ] Test each with an output not used in fitting.

**The motorway-addition test (Level 7)**

- [ ] Case: Berlin A100 section 16. Build `before` and `after` scenarios from data dated before 27 August 2025, using [April 2025 junction counts][A23905] for the before state. Include the Elsenbrücke's reduced state and the bridge closures.
- [ ] Record a blind prediction with the commit hash: flows on the Elsenbrücke (the [Senate forecast is 49,000 per weekday][A22745]) and which of the junctions show overload and when.
- [ ] Compare when counts are public, against the Senate forecast as a baseline to beat.
- [ ] Limit: one case, confounded, and our Berlin demand [is not yet credible](03-berlin-forensics.md). Fix Level 6 first, or this tests demand and nothing else.

**Run first, in order**

1. Refit `signal_discharge` and `freeway_fd` at real speeds, both time steps. Decide `tau` and `dt` policy from the result, since they currently act as one parameter.
2. Explain the −7.2 vs −27 km/h wave and the seed-identical capacity-drop result.
3. Extend the noise floor to 2024.
4. Measure queue discharge and wave speed on TGSIM and DLR HT, which carry more traffic than a Sunday junction.

### What only Erik can do

- **Ask for A100 evidence:** the Autobahn GmbH simulation and post-opening counts, from Autobahn GmbH or SenMVKU. It is outreach, so it is his call.
- **Licences:** DLR-UT is [CC BY-NC-SA 4.0](file:///home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-dlrut/README.md). The derived files here (`04-dlrut-discharge.*`) carry that restriction, which matters if `cars` becomes commercial.
- **Access only he can request:** PeMS, UTD19, NDW history, highD, and any Swedish controller logs, listed with terms in [report 01](01-city-ground-truth.md) and [report 05](05-real-human-driving.md).
- **Decide the claim:** whether `cars` aims to be "SUMO-compatible and fast" or "empirically valid". They need different τ and dt choices, because the first must keep the defaults that the second should change.

### Files added

[`scripts/validity_berlin_noise.py`](scripts/validity_berlin_noise.py) → [`04-berlin-noise-floor.json`](04-berlin-noise-floor.json). [`scripts/validity_krauss_discharge.py`](scripts/validity_krauss_discharge.py) → [`04-krauss-discharge.csv`](04-krauss-discharge.csv). [`scripts/validity_krauss_positions.py`](scripts/validity_krauss_positions.py) → [`04-krauss-positions.json`](04-krauss-positions.json). [`scripts/validity_dlrut_discharge.py`](scripts/validity_dlrut_discharge.py) → [`04-dlrut-discharge.json`](04-dlrut-discharge.json), [`04-dlrut-discharge.csv`](04-dlrut-discharge.csv). Signal coordinates transcribed from the dataset's documentation are in [`04-dlrut-signals.json`](04-dlrut-signals.json). Run from the repo root with `nix develop --command python3 -I <script>`.

[F]: https://arxiv.org/pdf/1303.6654
[H]: https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7908952/fullTextXML
[P]: https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/497241/POPE___Meta_2015_Final_210116_-_FINAL.pdf
[E]: https://docs.vlaamsparlement.be/docs/biblio/opendigibib/monografie/2013/549_accuracy_congestion_pricing.pdf
[G]: https://www.transportportal.se/swopec/CTS2016-9.pdf
[A1409]: https://www.parlament-berlin.de/adosservice/19/IIIPlen/vorgang/d19-1409.pdf
[A22745]: https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-22745.pdf
[A058]: https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/AusschussPr/m/m19-058-ip.pdf
[A4236]: https://dserver.bundestag.de/btd/21/042/2104236.pdf
[A3986]: https://dserver.bundestag.de/btd/21/039/2103986.pdf
[A24457]: https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-24457.pdf
[A23905]: https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-23905.pdf
[BA]: https://mdhopendata.blob.core.windows.net/verkehrsdetektion?restype=container&comp=list&prefix=2025/
[FH04]: https://ops.fhwa.dot.gov/trafficanalysistools/tat_vol3/sect5.htm
[FH19]: https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter5.htm
[FH19b]: https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter6.htm
[TAG]: https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/427124/webtag-tag-unit-m3-1-highway-assignment-modelling.pdf
[M12]: https://www.milton-keynes.gov.uk/sites/default/files/2022-04/CD13G_TAG-M1.2-data-sources-and-surveys.pdf
[TFL]: https://content.tfl.gov.uk/traffic-modelling-guidelines.pdf
[TV14]: https://bransch.trafikverket.se/contentassets/32ce05ecc3ac458bb8ecb802e8e2da54/handbok_for_kapacitetsanalys_med_hjalp_av_simulering.pdf
[TV24]: https://bransch.trafikverket.se/contentassets/a315cfef2b514117a3d66655c8a1dea0/2024/handledning---restidsnyttor-mikro--och-mesomodeller-2023-240401.pdf
[FGSV]: https://www.fgsv-verlag.de/verkehrsflusssimulation
[ORNL]: https://impact.ornl.gov/en/publications/a-systematic-comparison-for-consistent-scenario-development-using/
[BR1]: https://elib.dlr.de/6709/
[BR2]: https://elib.dlr.de/6646/
[KT]: https://arxiv.org/pdf/0803.4063
[Z]: https://arxiv.org/pdf/1811.06395
[SCH]: https://www.tib-op.org/ojs/index.php/scp/article/view/214
[SAL]: https://eclipse.dev/sumo/documents/2020/SUMO2020_paper_28.pdf
[XI]: https://cts-d10resmod-prd.oit.umn.edu/pdf/cts-05-05.pdf
[BZ]: https://komunikacie.uniza.sk/pdfs/csl/2022/02/02.pdf
[LIU]: https://www.diva-portal.org/smash/get/diva2:555913/FULLTEXT01.pdf
[LI]: https://arxiv.org/html/2512.18537v1
[CL]: https://ceg.osu.edu/sites/default/files/2022-06/Coifman_and_Li_2017.pdf
[SV]: https://sumo.dlr.de/docs/Definition_of_Vehicles,_Vehicle_Types,_and_Routes.html
[SS]: https://sumo.dlr.de/docs/Simulation/Safety.html
[SO]: https://sumo.dlr.de/daily/userdoc/sumo.html
[SI]: https://sumo.dlr.de/docs/Simulation/Intersections.html
[ST]: https://sumo.dlr.de/docs/Simulation/Why_Vehicles_are_teleporting.html
[ER]: https://elib.dlr.de/102254/1/Springer-SUMOs_Lane_changing_model.pdf
[CH]: https://odr.chalmers.se/items/b041b6d3-5d25-4a9f-a3a5-097b3b5ef21e
[CV]: https://cetra.grad.hr/ocs/index.php/cetra6/cetra2020/paper/download/996/848
[TRV]: https://bransch.trafikverket.se/globalassets/dokument/trvmb_kapacitet_och_framkomlighetseffekter.pdf
[UT]: https://rosap.ntl.bts.gov/view/dot/18549/dot_18549_DS1.pdf
[FS]: https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter3.htm
[W]: https://ops.fhwa.dot.gov/publications/weatherempirical/sect5.htm
[AD]: https://www.nber.org/papers/w24469.pdf
[MO]: https://www.trafa.se/globalassets/rapporter/underlagsrapporter/2011-2015/2015/movea_effekter-av-sjalvstyrande-bilar--kapacitetsanalys.pdf
[JN]: https://arxiv.org/pdf/1310.2660
[BG]: https://proceedings-paris2007.piarc.org/ressources/files/4/IP192-Geistefeldt-E.pdf
[AN]: https://arxiv.org/pdf/2104.02399
[CB]: https://digitalcommons.calpoly.edu/cenv_fac/307/
[TK]: https://arxiv.org/pdf/1008.1639
[TS]: https://arxiv.org/pdf/1004.5545
[TI]: https://mtreiber.de/publications/finalVersion_2014_lowRes.09.pdf
[GD]: https://escholarship.org/content/qt1b07t4q7/qt1b07t4q7.pdf
[L]: https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6841661/fullTextXML
[AZ]: https://web.mit.edu/cami/Public/CLA_uncertainty_CLA_TRC_2015_preprint.pdf
[N]: https://arxiv.org/pdf/cond-mat/9911311
[J]: https://itspubs.ucdavis.edu/download_pdf.php?id=2656
