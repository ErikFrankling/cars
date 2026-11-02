# How the best simulators do it, and what we invented

Research date: 2026-11-01. No GPU was used. Nothing here was tested on `cars`. Part 1 says what serious tools and projects do. Part 2 audits our specs against that. Part 3 lists what to change.

## The short version

1. **Teleporting is not universal.** SUMO relocates stuck cars after 300 s. Vissim removes a car only when it has waited too long for a lane change. Aimsun's missing-turn rule lets a car give up and carry on in its lane, and counts it as lost. MATSim pushes the car through the junction after 10 s, past the storage limit. Guidelines treat all of these as model errors to audit, not as accepted traffic.
2. **No guideline I opened gives an accepted percentage.** FHWA says to avoid unrealistic gridlock. TfL says that ideally there are no error files. The TRB primer says the result should be free of gridlock. The numbers we want do not exist in those texts, so I did not invent any.
3. **There is an established test we should run before anything else.** Trafikverket's handbook says to run extremely low demand and then 50%, and the TRB primer says to run uniformly reduced demand. Congestion at that level points to a coding error. This takes hours and goes straight at the Berlin evening gridlock.
4. **Our largest invention is the side-by-side swap, and the problem it solves is known.** Trafikverket's handbook describes the same lock in Vissim and fixes it by offsetting the stop points by at least 7 m. Aimsun's answer is to miss the turn.
5. **Force-yield is ours alone.** Every tool I read limits cooperation, then lets the waiting car lose: it misses its turn, or it is removed. None of the manuals I read makes the follower yield after a timeout. Hidas's simulator tests found that more cooperation lowered throughput.
6. **We reinvented published lane-change work.** MIT's forced-merge and courtesy line runs from Ahmed 1999 through Lee 2006 to Choudhury et al. 2009. The last was estimated on I-80, the same site report 14 used for its logit, and validated on US-101. Report 14 listed Ahmed and Choudhury as could not open. Their abstracts open and I read them, but the full texts were rate limited for me too.
7. **Simulators are not crash-free, and it is documented.** FHWA's SSAM study began by assuming no crashes, then found them in Vissim, Aimsun, Paramics and TEXAS. They could not be removed without reducing capacity. Simulated conflicts predicted crashes worse than traffic volume did: R² 0.41 against 0.68 at 83 intersections, with path-crossing conflicts under-represented. We must not report crash or safety results from human traffic. Our zero-collision rule stays as an AV requirement.
8. **City-wide micro is feasible, but no opened source shows it beats meso on flows.** Trafikverket recommends micro for small areas where detailed signals matter, and meso where route choice matters. In Munich, flows were similar and micro was closer only on speed. The best count fit I opened is a queue model: Zurich at 10 to 15% error on 161 stations. Error measures differ across projects, so this is not a league table.
9. **Inputs come first, in my reading.** A real-traffic test exists for Stockholm's trial: observed cordon change −18.1%, against −25.3% and −12.4% from two dynamic models. The older static model got traffic and travel times wrong, and its authors blame the static assignment. A Swedish test of dynamic assignment for SAMPERS says full-scale use needs signal and junction delay coding. We have no real signal plans.
10. **Where we are ahead, on the evidence so far:** fair replay tests of the car-following model, ballistic integration with a stopping certificate, a swept-path conflict table, and an exact vehicle ledger. All but the swept-path census are designs tested in Python only. The kernel has none of them yet (`grep` finds no `MODEL_HUMAN`, `lc_wait`, `F_SHADOW` or `cj_arbitrate` in `crates/`), and the CLI still defaults to `--time-to-teleport 300`.

**Audit tally:** 47 decisions: 14 established, 20 adapted, 13 invented. See Part 2.

## Grades

**F** field measured. **S** simulation or analysis. **V** vendor manual or claim. **G** guideline. **D** open-source software documentation or code, which describes what the software does and not whether it is right. **A** abstract only.

Short labels such as [am] or [tfl] are links, defined in the register at the end. Every link there was opened in this session, unless the "Could not open" list says otherwise. Citing a report by number (03, 05, 09, 14) points to our own earlier work, which was not reopened or rechecked here. Downloads and text are in `/home/erikf/projects/personal/cars-data/truth/practice/opus-20261101/`. Fetch log with hashes: [`15-fetch-ledger.jsonl`](15-fetch-ledger.jsonl). It includes failures and a few wrong papers I fetched by guessed id, which I did not use.

## Part 1. How practice handles it

### 1.1 Stuck vehicles, gridlock, missed exits

| Tool | What happens to a stuck car | Default | Grade |
|---|---|---|---|
| SUMO | "Assumed to be in grid-lock and teleported onto the next free edge"; held invisibly in a buffer if there is no room; negative threshold turns it off. Reasons logged: wrong lane, yield, jam, blocked, and others. [SUMO teleport][st] | 300 s | D |
| SUMO | Earlier alternative: ignore a junction blocker after a set time, or ignore keep-clear after a waiting time. [SUMO intersections][si] | off | D |
| Vissim | Only for a necessary lane change: at the emergency stop position, the car is removed when `DiffusTm` runs out, with a warning in the `.err` file. [Vissim lane change][vlc] I found no general junction-gridlock removal in the pages I opened. | Not on that page. The 60 s often quoted could not be verified at PTV. | V |
| Aimsun | In zone 3 the car slows, even to a stop, looking for a gap. After Maximum Give Way Time plus Additional Waiting Time Before Missing Turn at standstill, it stays in its lane. It is then counted as **Lost Inside** or **Lost Outside**. [Aimsun micro][am] [Aimsun dynamic scenarios][ad] [TfL p. 197][tfl] | Additional wait 0 s | V, G |
| MATSim | After `stuckTime` of no movement, the car is moved across the junction "despite violating the storage constraint". The book says larger values look less realistic against counts, from "systematic investigations (unfortunately never published)". `removeStuckVehicles` defaults to false; "`false` is probably the better choice". [Book §4][mb] [Code][mq] | 10 steps | D |
| Mobiliti | Meso. The car stays upstream until the next link has space. No release rule in the text I read. [Mobiliti][mo] | n/a | S |
| LPSim | The car waits if the downstream segment is full. [LPSim][lp] | n/a | S |
| Munich hybrid | "Stuck vehicles were removed from the simulation after 60 s." [Schuhmann et al.][mu] | 60 s | S |
| BeST Berlin | Published with 2,332 teleports on 2,272,641 trips (0.10%). [BeST][best] | n/a | D |
| TransModeler, Paramics, MITSIMLab, SimMobility, DynaMIT, TRANSIMS | **Not established.** I found no manual text on this. See "Could not open". | | |

**Is it a calibration flag? Yes, wherever a guideline speaks.**

- **FHWA:** "Ensure models are stable and do not create unrealistic gridlock conditions." Where a replication formula asks for 20 or more runs, investigate why the model is unstable. [FHWA ch. 6][f6] G
- **TRB DTA primer:** when gridlock sets in, "not much is gained in computing statistical measures"; the qualitative stage aims for results that "are free of gridlock". It warns that indiscriminate capacity increases can remove real bottlenecks. Diagnosis: reduce demand uniformly and see what still jams. [E-C153][ec] G
- **TfL:** audit the error files for "vehicles and Public Transport Lines being removed", "vehicles reaching the end of links while still searching for routes", and latent demand. "Ideally, no error files"; small non-critical files are acceptable. No bus may be removed by modelling issues. [TfL §7.5.2][tfl] G
- **Aimsun:** vehicles lost or missing a turn are "indicative of calibration problems". [Aimsun calibration][ac] V
- **ACT guideline:** the number of unreleased vehicles is a reported output. [ACT p. 25][act] G
- **TAG:** blocking back "is a critical part of the model" in microsimulation; beware very short links. [TAG §2.7.11][tag] G
- **Trafikverket:** test with extremely low demand, then 50%. Congestion at 50% points to hard-to-find coding errors. [Handbok][tvh] G
- **Austroads:** AP-R286 has an auditing chapter on its contents page, but its PDF returned 403 and only the landing page opened. [AP-R286][aus] **Not established.**

**No opened guideline gives an acceptable percentage** of removed vehicles or teleports. TfL's error-file wording is the nearest thing to a limit. Report thresholds as ours, labelled.

**How models avoid deadlock in the first place:**

| Method | Source | Grade |
|---|---|---|
| Keep-clear at entry: enter only with space beyond | SUMO no-block heuristic [si]; Aimsun yellow box, with a speed threshold [an]; Vissim "Avoid blocking", below | D, V |
| Lane-choice zones that start early by distance | Aimsun zones 1–3, with per-vehicle look-ahead factor [am]; TRANSIMS urgency weight growing toward the junction [tr]; LC2013 urgency [lc] | V, S, D |
| Long enough links before turns | Aimsun has no speed foresight beyond the preceding section, so short sections are discouraged; solid lines at junction approaches make cars miss turns [tfl] | G |
| Do not place stop lines in another turn's path | Stops future-year gridlock [tfl] | G |
| Offset stop points between neighbouring lanes | Two cars with the same Emergency Stop distance lock each other and the whole approach blocks (my translation); make the distances differ by at least 7 m [Handbok p. 106][tvh] | G |
| Extra connections in weaving sections | SUMO names the lane-change deadlock as "imperfection of the lane-change model" [st] | D |
| Infinite storage in early assignment iterations | Aimsun's mesoscopic DUE, Queue Propagation off: all-or-nothing loading gridlocks, so turn storage off until paths are feasible [ad] | V |

**Missing an exit** is modelled in all three commercial or open tools that I could read. Aimsun: the car misses it and is counted. Vissim: the car is removed. SUMO: "wrong lane" teleport. Report 14 already found real misses are cheap, about 2 minutes on Twin Cities trips. No tool I read forces the follower to give way.

### 1.2 Collisions

**By construction, in principle.** Aimsun's Gipps-based model "avoids crashes when the Gap remains positive". [am] V. SUMO's default model "is supposed to never reduce the gap below the minGap", and SUMO registers a collision when it does. [SUMO safety][ss] D. CityFlow computes a collision-free speed and resolves junctions at precomputed cross points. [CityFlow][cf] S. LPSim's cell representation cannot hold two cars: "we are not simulating the case that vehicles crash". [lp] S.

**In fact, no.** FHWA's SSAM work "assumed that none of the simulation systems would have any crashes", and found otherwise. All systems had TTC = 0 events. In Aimsun and Vissim they fell at link entries and exits. Removing them needed "modeling techniques that resulted in unrealistic driver behaviors and unrealistic facility performance (e.g., reduced approach capacity and throughput)". [SSAM pp. 266–267][ssam] [SSAM ch. 6][ss6] S, F for the crash data. Later tool versions may differ: Vissim added conflict areas in 4.3 as a response. Aimsun also has an explicit "Imprudent Lane Changing" option in which either car may need up to twice its maximum deceleration, and Aggressiveness that accepts short gaps with later relaxation. [am] V

**How it is verified.** SUMO has an opt-in `--collision.check-junctions`, which detects overlap of vehicle shapes. [ss] D. SSAM post-processes trajectories at about 0.1 s using vehicle rectangles. [SSAM brief][sb]. Its 2003 report warns that point-vehicle gap logic makes surrogates wrong. [SSAM 2003][ss03] G

**Surrogate measures.** A conflict is TTC under 1.5 s. Field test at 83 signalised intersections, using insurance claims: R² 0.41 for conflicts against crashes, Spearman 0.463; ADT models gave 0.68; path-crossing conflicts were under-represented; high-conflict and high-crash sites did not line up well. The authors call the result not definitive. [ss6] F against S. **What is accepted:** relative comparison of designs, with caveats. **What is not:** crash frequency from simulated crashes. I could not open Essa & Sayed or Huang et al. on simulated against field conflicts.

**Crossing conflicts in junctions:**

| Tool | Method | Grade |
|---|---|---|
| Vissim | Conflict areas with status, front and rear gap times (default 0.5 s), minimum gap blocking 3.0 s, merge safety factor, visibility distance, percentage anticipating routes, percentage avoiding blocking of minor flow, and avoid blocking of major flow. Automatically typed: merge, branch, crossing. [Vissim conflicts][vca] | V |
| Aimsun | Gap model from distance to a theoretical collision point, speeds, accelerations and clearing time. Required gap falls from MaximumGap to MinimumGap after waiting. Yellow box flag. [am] [an] | V |
| SimMobility | "Conflict points" with gap acceptance on intersection priorities. [SimMobility][sm] | S |
| CityFlow | Precomputed cross points decide who passes. [cf] | S |
| SUMO | Foe bits on links, with a right-of-way and blocking check on internal lanes. [si] | D |

### 1.3 Lane change

**The established structure** (Gipps' necessity, desirability and feasibility):

| Source | What it adds | Data | Grade |
|---|---|---|---|
| [Ahmed 1999][ah] | Three steps: consider, target lane, gap acceptance. "Since acceptable gaps are hard to find in a heavily congested traffic, a forced merging model that captures forced lane changing behavior and courtesy yielding". Discrete choice, heterogeneity via headway threshold and reaction-time distributions | I-93, Boston | F, A |
| [Rao 2006][ra] | Explicit forced merging. Effects of relative speed, distance to the mandatory point, lag acceleration. Aggressive drivers persist | Trajectories | F, A |
| [Lee 2006][le] | **A single critical-gap function covering normal, forced and cooperative merging.** Affected by mainline speed, lead and lag interactions, urgency. Transferability tested, better than the existing MITSIMLab model | Two California sites | F, A |
| [Choudhury et al. 2009][ch] | Merging plan is latent. Joint plan, gap acceptance, target-gap and acceleration. **Estimated on I-80, validated in MITSIMLab on US-101** | NGSIM | F, A |
| [Ramanujam 2007][rm] | Adds lane-change duration as a third level. Notes models assume changes finish in one step, while "past works report average lane change durations to the order of 5-6 seconds" | Arterial, California | F, A |
| [Ben-Akiva, Choudhury & Toledo 2019][bct] | Summary chapter. Integrated, target lane, cooperative and forced, heterogeneity and correlation. "In all cases, a substantial improvement in simulation capability" | Authors' own validation | S, A |
| [SimMobility][sm] | Runs on these estimated models. Lateral speed constant during the change, sine under way | | S |

**Why research reached those forms.** Gaps stop existing in congestion, so a pure gap model stalls. The plan is unobservable, so it is modelled as latent. And urgency acts through distance to the mandatory point. Report 14's I-80 measurement found the same: distance dominates and waiting time adds nothing once distance is known.

**Courtesy in tools is simple:**

- **Aimsun:** a percentage, "Cooperation Creating a Gap", by section and vehicle type. Only for compulsory changes in zones 2 and 3. It also uses a two-leaders car-following model: the changer slows for its target-lane leader before moving, with a negative gap if needed. Gaps are evaluated forward, adjacent or backward. [am] V
- **Vissim:** the trailing car brakes cooperatively up to `CoopDecel` (default −3 m/s²), stopping when it would need more. Safety distance multiplied by 0.6 during the change. `MinClear` 0.5 m. [vlc] V
- **LC2013:** strategic, cooperative, speed-gain and keep-right stages, with neighbours asked by urgency. [lc] D

**Hidas's tests (simulation only).** Aimsun, Vissim and ARTEMiS gave similar macroscopic results, each with weaknesses. In ARTEMiS more follower cooperation reduced flow and speed on the main road (flow −6%, speed −18%) with no gain at the ramp, and "more cooperation leads to more congestion and lower maximum throughput". A 5 s maximum wait with minimum cooperation gave unacceptably many lost vehicles, cured by a longer wait. Vissim's results got poor at a 1.0 s step. Lost vehicles were consistently high in Aimsun then, in 2004. [Hidas 2004][hi] S. **Hidas 2005's observed free, forced and cooperative counts could not be opened.**

**Laval and the void.** Lane changers are "particles endowed with realistic mechanical properties"; they create voids, and these reproduce both capacity drop and the moving-bottleneck relation, without recalibrating, with four parameters. [Laval & Daganzo][la] S, A. Keane & Gao find relaxation "necessary for correctly simulating traffic breakdown with realistic values of capacity drop". [Keane & Gao][kg] S. Vissim offers slow recovery after standstill: 40% of normal acceleration within 2,000 m. [Vissim recovery][vre] V

**Duration.** SUMO defaults to 0 s and supports a shadow-lane mode when set above that. [SUMO source][sf] D. Measured: mean 5.7 s, median 5.55 s for cars, 6.22 and 6.08 s for heavy vehicles. [Li et al.][ld2] F. Cars' right changes mean 7.8 s, median 7.6 s, n=1,550, at German sites. [ld1] F. Reports 05 and 11 measured the same range on our own data.

[Zheng's 2014 review][zh] sorts models into decision models and impact models. Only its abstract opened.

### 1.4 Car following, heterogeneity, desired speed

| Tool | Model | Parameter spread | Evidence given by the vendor or project | Grade |
|---|---|---|---|---|
| Vissim | Wiedemann 1974, 1999: psycho-physical thresholds and four driving states. CC1 gap time is a distribution and "the dominant factor for the capacity". [W99][vw] [Wied][vwm] | "The perception of speed differences as well as the desired speed and safety distance kept vary across the driver population" | Cited to Wiedemann; no accuracy given | V |
| Aimsun | Gipps, modified, with sensitivity factor and a separate reaction time at stop, which has "a strong influence in the queue discharge". [am] | Reaction time drawn per vehicle from a user distribution. Truncated normal for many others | None in the manual | V |
| SUMO | Krauss by default, others selectable. [sv] | `speedFactor` default `normc(1,0.1,0.2,2)`, about 95% between 80 and 120% of the limit | None in the docs | D |
| MITSIM, SimMobility | Stimulus-response family, estimated. [ah] [sm] | Headway threshold and reaction time distributions | Estimated on real data | F, A |

**Evidence that tools are not interchangeable:**

- All systems were "vaguely comparable" in light traffic and diverged in congestion. [ssam] S
- The Trafikverket handbook: Vissim with default parameters tends to give slightly too high saturation flows. Saturation flow is an output, set mainly by car-following parameters, speed through the junction and yielding. [tvh] G
- A German study calibrated Babsim, Vissim, Aimsun, Paramics and SUMO to HBS capacity at a 5% tolerance: met "as a rule" except SUMO, which deviated more. [HBS study][hbs] S, A
- Kurtc and Treiber: inter- to intra-driver ratio about 0.6% for speed and 4.7–5.9% for gap calibration, reconstructed I-80. [Kurtc][kt] F

**Heterogeneity.** All tools draw per-vehicle parameters. I found no paper showing per-vehicle draws reproduce a specific measured spread at city scale, and a head-to-head of Wiedemann against Gipps against IDM on trajectory data did not surface. Punzo's calibration guideline and Ossen et al. on heterogeneity only appeared in search results and could not be opened, so I use no numbers from them. **Desired speed:** TfL ships template distributions and sets them per link with Desired Speed Decisions. [tfl] G. Nothing opened gives measured Swedish distributions.

### 1.5 Junctions, saturation, signals

**Swedish reference values exist, and we weren't using them.** From [TRVMB Kapacitet][trv] (Trafikverket's capacity method, chapters 2, 4, 5; G):

| Quantity | Value | Our value |
|---|---|---|
| Base critical gap, 50 km/h major road, give-way: major left / minor right / straight / left | 4.8 / 5.0 / 5.1 / 5.3 s | Report 05 persona; roundabout and US figures |
| Same, stop sign | 4.8 / 5.7 / 5.8 / 6.0 s | |
| Same, 70 km/h give-way | 5.7 / 5.9 / 6.0 / 6.2 s | |
| Base saturation flow per lane, as I read the figure's layout: through / turning / each of double turning. Mixed lanes come from a diagram | 1,900 / 1,700 / 1,500 veh per green hour | Band 1,800–2,100; 2.05 s = 1,756 for our measured case |
| Follow-up, left turn in signal | `af = 0.54 × ag` | none |
| Jam density | 134.5 veh/km/lane, 7.43 m spacing | Band 6.5–8 m, 7.0 m from DLR |

These are guideline design values and not measurements I checked. Report 04's "Measured saturation headway in Sweden" remains unknown.

**Real controllers in the loop.** Vissim offers fixed time, Vissig, VAP, external DLL, Siemens VA, VS-Plus, LISA+ OMTC, SCATS, SCOOT and others. [Vissim signals][vsc] V. Aimsun links to SCATS, Yunex UTC (with SCOOT), UTOPIA and VS-Plus. [Aimsun adaptive][aad] V. Trafikverket: a simplified VAP is normally enough to study delay and queues; for exact control use a simulator from the controller maker with the street's programming, and where street programming isn't available "extensive work" is needed. It also gives rules of thumb for reducing actuated control to fixed time, such as 75% of max time and 50% of "fråntid", and mentions LHOVRA functions. [Handbok p. 82 ff.][tvh] G.

**Accuracy evidence.** For pretimed and isolated actuated, emulator, HIL and SIL matched. For signal transition logic the emulator differed significantly. [Stevanovic et al.][stv] S, A. So actuated-style emulation is defensible, and coordination transition is not. Projects that used real plans: SimMobility with SCATS phases [sm], InTAS with 20 real signal programs [in], Stockholm's CONTRAM with signal plans and saturation flows "adapted to correctly represent the actual traffic situation" [dp]. SUMO's own default is fixed cycle 90 s. [SUMO signals][stl] D

### 1.6 Real deployments

**I found no independent audit of any of these.** All fits are by the authors, and most are on calibration data.

| Project | Scale | Type | Calibrated against | Accuracy reported | Time | Grade |
|---|---|---|---|---|---|---|
| **Singapore** SimMobility ST [sm] | Extended CBD, over 1,200 intersections, over 2,000 loops, 1,497 OD pairs | Micro, MITSIM based | 360 sensors, 5-min counts, 30-min GPS OD times, Aug 2013; 250 W-SPSA iterations | RMSN 0.72 → 0.37 on calibration counts; "seems to be satisfactory given the above small number of sensors and relatively large number of parameters" | not stated | S against F |
| **Melbourne** [ml] | Metro, CBD result | Meso DTA | Freeway loops, SCATS, probes; bi-level OD | RMSE −50%, R² 0.53 → 0.92 (CBD, calibration) | ongoing | S, A |
| **Sydney** [sy] | "First large-scale simulation-based DTA in Australia" | Meso | 322 calibration points | 80% within bound. Warns other metrics are needed | ongoing | S, A |
| **Sydney model hierarchy** [sya] | Macro, meso, micro levels | Hierarchical | | | | S |
| **Zurich** [zu] | Metro, full agent day | MATSim queue | 161 count stations, Cadyts behavioural calibration | 10–15% error throughout the period, cross-validated. Reproduction error −80% | not stated | S against F |
| **New York** [ny] | 8M+ population | MATSim | INRIX, East River screenline | Speed 7.2% freeways, 17.1% arterials. Screenline +1.8%. **Median 29% on select link counts** | | S against F |
| **Bay Area** Mobiliti [mo] | 19M trips, 1M links, 3 min on 256 cores | Meso, Time Warp | PeMS, Caltrans | 72% of 2,061 links R² > 0.7, 55% speed R² > 0.4, 7 of 8 bridges within ±25% | | S against F |
| **Bay Area** LPSim [lp] | 2.82M trips in 6.28 min on one V100; 9.01M in 21 min on two V100; same demand 0.0398 h on two A100, 113× a Xeon at 4.49 h; 224k nodes | Micro on GPU | Refers to another paper | Not in this paper | | S |
| **Berlin** BeST [best] | 2.25M car trips, whole city, 7 h on CPU | Micro SUMO | Counts on some streets | Compared by figure. **Report 03 found half the real traffic missing** | | D |
| **Berlin** MATSim [mb24] | Open scenario | Agent | Counts, modal split, distances | Rakow et al. note commercial and external traffic is hard | | S |
| **Hamburg** [ha] | Metro, MATSim | Agent | Demand from Senozon, mode calibration | No flow accuracy in what I read | | S |
| **Munich** [mu] | Region meso, Schwabing micro | SUMO meso-micro with MATSim | Flows, FCD | K-S p > 0.05, flows "acceptable". Speeds "significant differences", micro closer than meso | | S against F |
| **Ingolstadt** InTAS [in] | City, 20 real signals | Micro SUMO | 24 measurement points | Compared to counts | | S |
| **Luxembourg** LuST [lu] | City | Micro SUMO | Real data, on SUMO 0.26 | "With more recent versions... cannot be considered validated" | | D |
| **Los Angeles** [kl] | Greater LA, five sub-networks | Micro INTEGRATION | Abstract gives no accuracy | "Completely feasible" | | S, A |
| **Stockholm** CONTRAM/SILVESTER [dp] | City; CONTRAM "used and calibrated for decades" | Meso + departure time | 59 calibration links | 95% of link flow variability. Trial: observed −18.1% cordon, SILVESTER −25.3%, METROPOLIS −12.4% | decades | S against F |
| **Stockholm** static model [en] | Region | Static with VDFs | Before-after trial | Overestimates traffic effect, substantially underestimates travel-time effect. Steeper VDFs barely help. Abstract: dynamic assignment "crucial" | | F, A |
| **Sweden** SAMPERS with dynamic assignment [cts] | Stockholm, Essingeleden | Test of several DTA packages | Link volumes, times | Right order with moderate network work; wrong time profile of speed and volume on Essingeleden. Full use needs signal and junction delay coding | | S |
| **Los Angeles** DynaMIT [ba] | LA network case | Meso, real-time DTA | Archived sensor data | Simultaneous demand and supply calibration improves on sequential, shown on a synthetic network; LA for scale | | S, A |

**Calibration practice is often thin.** A California review found "many studies paid little attention to model calibration, or at least not documented it". [Zhang & Ma][ucb] G. FHWA's 2019 criteria use time-variant envelopes from comparable days, and Criterion I is 95% of outputs within about 2σ. [FHWA ch. 5][f5] G. TAG's convergence target is 0.1% for static models [tag]. Aimsun's vendor guidance is RGap 5–10% for DUE [adt].

### 1.7 Is full-city micro meaningful?

- **Feasible:** yes. LA in INTEGRATION; LPSim on GPUs. Neither shows accuracy in what I opened.
- **Worthwhile on flows:** not shown. Zurich's queue model gets 10–15% on counts. Munich's flows were similar between micro and meso.
- **Worthwhile on speeds:** Munich's only comparison favours micro.
- **Official Swedish position:** micro for smaller influence areas with limited route-choice effects and detailed signals. Meso for larger areas where route-choice effects matter. A "simplified meso" can replace micro in small systems. [Trafikverket restid][tvt] G. Known weaknesses of macro models: blocking back, weaving, junction capacity.
- **Primer:** most DTA uses meso because detailed interaction isn't needed for route choice, at the cost of "aggregate" depiction. [ec] G
- **Hybrid problem:** consistency at the boundaries; hybrid demand needs equal network and route representation. [mu] S
- **My reading:** our speed removes the compute reason for meso, not the calibration reason. Thousands of unknown OD cells and signals dominate error. Micro adds value where lane choice, queues and signals drive the question, which includes every AV comparison we care about. A queue baseline on the same network would show what micro adds. **Opinion.**

### 1.8 Parallel and GPU updates

| Source | Conflict method | Determinism |
|---|---|---|
| [TRANSIMS][tr] | Lane change as a separate substep, strictly parallel on time t. Three-lane conflicts prevented by **left on even steps, right on odd**: "collision free". Note that this is an artefact of decision time scale, and real cars can target the same spot too. | Fixed order; queue competition first-come by processing order |
| [Rickert et al.][ri] | Two substeps. Parallel updates make platoons oscillate between lanes ("ping pong"), so add randomness. | CA |
| [LPSim][lp] | Atomic writes. "Only one vehicle's thread successfully writes." IDM with look-ahead | No claim in what I read. Winner depends on thread order |
| [GPU simulator][gpo] and [MOSS][mos] | Read-only snapshot, then update | No claim found |
| [CityFlow][cf] | Multithreaded, cross points | No claim found |
| [Mobiliti][mo] | Time Warp: speculation and rollback, no locks | Enforces event order |
| **`cars`** | Priority claim on 8 m cells, two-phase, from the existing `lc_commit` | `atomicMin` on an urgency-and-rank key, so the winner doesn't depend on thread order. Report 08's test 18 demands exact determinism. Better than first-writer-wins |

I found no GPU traffic paper that states and tests exact determinism. **Not found is not proof.** FLAME GPU and Heywood et al. were searched for and not reached.

## Part 2. Audit of our specs

**ESTABLISHED** means a named source does the same. **ADAPTED** means we changed something, and I say what. **INVENTED** means I found no source. A parameter inside an established form is classified by the parameter if the parameter is what's asked about.

| # | Decision | Where | Class | Basis | What to do |
|---|---|---|---|---|---|
| 1 | Teleports off in any counted run | 06 §8.9, 14, AV-REQ | ADAPTED | SUMO allows it [st]. Stricter than every tool's default. Fits FHWA, primer, TfL. | Keep, but only with #5 and #2. Code default is still 300 s and Berlin scripts use 120 s, so "off by default" isn't true yet. |
| 2 | Stall abort: no arrival in 15 sim min | 06 §8.9 | INVENTED | No source. Run-control only. | Keep, as control. Not behaviour. |
| 3 | `network_suspect` if gridlock at ≤50% demand | 06 §8.9 | ESTABLISHED | Trafikverket 50% test [tvh]. Primer reduced-demand test [ec]. | Cite them. Add very low demand first. |
| 4 | Never scale demand or capacity to pass | 06 §8.9 | ESTABLISHED | Primer against indiscriminate capacity [ec]. TAG limits [tag]. | Keep. |
| 5 | Missed turn after waiting at green | 14 §4 | ESTABLISHED | Aimsun [am], TfL flags lost vehicles [tfl]. Not built. | **Build first.** |
| 6 | `T_MISS` = 120 s, fixed | 14 | INVENTED | Concept in #5. Aimsun uses per-vehicle give-way time and a 0 s default addition. Hidas: 5 s too short, 60 s fine in ARTEMiS [hi]. | Per-vehicle draw; report lost per 1,000 trips. |
| 7 | Human no-block rule, always on | port of SUMO | ESTABLISHED | SUMO [si], Vissim [vca], Aimsun [an]. But Vissim applies it to a percentage: space below length + 0.5 m, blocker under 5 m/s and under 75% of desired speed. TfL lists real blocking as a behaviour to observe [tfl]. | Add a compliance percentage. |
| 8 | AV exit credits and run-out check | 09 | ADAPTED | Yellow box and storage. Mobiliti and LPSim wait for space. Our change: counts committed cars. 25 overlaps off, 0 on, own model. | Keep. |
| 9 | Point-of-no-return recheck | 09 | INVENTED | No source. Tests: queue-after-grant overlaps vanish. | Keep. Say it's ours. |
| 10 | Cut test for impossible demand, verdict ladder | 06 §8.9 | INVENTED | No source for the ladder. The primer's advice is to find the first bottlenecks and fix inputs [ec]. | Keep as a diagnostic. Report it as ours. |
| 11 | 2D oriented-rectangle audit, count and never repair | 09, AV-REQ | ESTABLISHED | SUMO shape overlap [ss], SSAM rectangles [ss03]. | Keep. |
| 12 | Zero-collision hard test | AV-REQ | ADAPTED | True for AV planners in theory [rs] [po]. SSAM says not attainable for human models without capacity loss [ssam]. | Apply to AV tiers only. Human traffic: report and locate. |
| 13 | Swept-path conflict table, not SUMO foes | 09 | ADAPTED | Vissim conflict areas, CityFlow cross points, SimMobility conflict points. Our census found 12% missing and 18% spurious against SUMO foes. | Keep. Report upstream if it reproduces. Better than practice on evidence. |
| 14 | Courtesy logit coefficients | 14 | ADAPTED | Discrete choice with urgency: Ahmed, Lee, Choudhury. We fit let-in per vehicle at I-80, one site; passive and active mixed. Tools use a fixed percent. | Replace structure with #15. |
| 15 | Keep critical gap and follower response separate | 14 | ADAPTED | Lee and Choudhury use a single gap function with latent plan. We have not compared. Hidas warns on cooperation. | Fetch theses. Compare on I-80 and US-101. |
| 16 | Urgency via remaining distance | 14 | ESTABLISHED | Rao, Lee, Aimsun zones, TRANSIMS, LC2013. | Keep. |
| 17 | Driver trait + pair hash, split 0.7/0.7 | 14 | INVENTED | Driver heterogeneity established [bct] [ra]. Pair term and split are ours. Spec says assumed. | Drop pair term unless a test needs it. Keep driver trait. |
| 18 | Wait term in `eta`: from 60 s, +6 per 30 s | 14 | INVENTED | Report 14 measured no wait effect. Aimsun has a wait effect only for give-way gaps. | Remove from behaviour. Replaced by #5. |
| 19 | `T_U0, T_U1` = 30, 90 s gap shrink | 14 | ADAPTED | Form close to Aimsun's reduction with wait at junctions [am]. Numbers ours. Polus: slow. | Use Aimsun's form as baseline. Parameters to fit. |
| 20 | `T_FORCE` = 90 s force follower | 14 | INVENTED | **No tool does this.** Vissim stops cooperating above `CoopDecel`. Aimsun cooperation is a percent. | Remove as behaviour. Keep only as labelled last resort, counted. |
| 21 | Side-by-side swap | 14 | INVENTED | Same lock in Vissim and SUMO. Practice breaks symmetry instead [tvh]. No swap found (SUMO's `swap` in `MSLaneChanger` is container handling). Prototype works. | Replace with offset stops, then miss turn. |
| 22 | `S_MIN` = 0.5 m | 14 | ESTABLISHED | Vissim default [vlc]. | Keep. |
| 23 | `B_YIELD` 1.5, max 3.0 m/s² | 14 | ADAPTED | TGSIM; Vissim −3 [vlc]. | Keep. |
| 24 | `TAU_MIN` max(0.3, dt), `B_EM` 7.5 | 14 | INVENTED | Tail reading. Practice: Vissim 0.6 factor, Aimsun Aggressiveness, 2× limit. | Test a 0.6 factor as baseline. |
| 25 | Blinker share 93%, `ETA_NOSIGNAL` −1 | 14 | ADAPTED | 93% field, Sweden, 103 drivers. −1 is opinion. | Keep as switch. No tool models it. |
| 26 | Keep LC2013 strategic stage | 14, 11 | ESTABLISHED | SUMO [lc]. Caveat: SUMO calls it imperfect [st]. | Keep as compatibility baseline. |
| 27 | Finite duration, near-constant 0.6 m/s | 11, 05 | ESTABLISHED | SimMobility constant lateral [sm]. Field 5–8 s [ld1] [ld2] [rm]. | Keep. |
| 28 | Shadow in old lane | 11 | ADAPTED | SUMO has a shadow lane for continuous change [sf]. Ours is a sorted clone with speed advice. Not prototyped. | Prototype with capacity-drop test. Laval predicts it matters. |
| 29 | Priority claims on lane-change targets | kernel | ADAPTED | TRANSIMS odd-even, LPSim atomic. Ours is order-independent. | Keep. Add to test 18. |
| 30 | `MODEL_HUMAN`: linear gap and speed feedback with lag | 05 | ADAPTED | Stimulus-response family as in MITSIM [ah] [sm]. Replay-tested against Krauss and IDM; **Wiedemann not compared**. Equations of Ahmed not opened. | Keep. Add Wiedemann and Gipps as baselines. Run capacity drop. |
| 31 | `k2 √(15/g)` gap scaling | 05 | INVENTED | Fitted. A gap-scaled speed term is standard in the family, but no equation source was opened. | Keep, flagged fit. |
| 32 | 1 s lag, noise 0.2 m/s² | 05 | ADAPTED | Reaction time is established [am]. Values chosen looking at held-out chains. | Blind test. |
| 33 | Gains not per-driver; T, s0, launch per vehicle | 05 | ADAPTED | All tools draw per vehicle [vwm] [am] [sv]. Vissim's dominant spread is the gap time, ours too. Kurtc's small ratios agree. Anonymous tracks limit it. "No per-driver parameters" overstates what the spec does. | Keep. Ask for SHRP2-type data. |
| 34 | Desired speed = limit × factor | 05 | ESTABLISHED | SUMO default [sv], TfL templates [tfl]. | Measure locally. |
| 35 | Closed-form safe speed certificate | 11, 08 | ADAPTED | Gipps core [am], RSS Definition 1 [rs], CityFlow. Our change: min(b_F, b_L), brake ramp, response in the tick. 23,956 Python trials. | Keep. Better than tools by SSAM's evidence, if the kernel confirms. |
| 36 | Ballistic update | 11, 05 | ESTABLISHED | Treiber & Kanagaraj [ti], CityFlow. | Keep. |
| 37 | Critical gaps by persona | 05 | ADAPTED | Swiss and old US sources. | Use TRVMB in Stockholm. |
| 38 | Saturation band and target | 04, 11 | ESTABLISHED | TRVMB 1,900, DLR-UT. | Keep. Report site. |
| 39 | Jam spacing band | 04 | ESTABLISHED | TRVMB 7.43 m; DLR 7.0 m. | Keep. |
| 40 | OSM recipe base options | 07 | ESTABLISHED | SUMO recommended options [so]. | Keep. |
| 41 | Drop `--tls.discard-simple`; add turn lanes, access | 07 | ADAPTED | Departs from SUMO's list, with our measured reasons. | Keep. The evidence is local to Stockholm. |
| 42 | One controller per register installation | 07 | ADAPTED | Practice uses plans; InTAS did it by hand. Ours automates with a public register. Better than OSM guess, on evidence. | Keep. |
| 43 | Split programs above 120 s at 30, 12, 5 m | 07 | INVENTED | No source. Works around netconvert. 180 s comes from Stockholm's handbook. | Replace by real plans at key sites. Label the rest placeholders. |
| 44 | 15% reroute cap | 06 | ADAPTED | MATSim 10% ReRoute [mb], Zurich 10% per module [zu]. Toy-tuned. | Test 10%. |
| 45 | Memory 0.3 on cost | 06 | INVENTED | Form like Gawron, but SUMO's default beta is 0.9 [dua], source. Toy only. | Test 0.9 and 0.3. |
| 46 | Earliest-start scheduler, greedy | 09 | ADAPTED | Reservation from AIM [ai]. Polling gives proofs of no collisions and a delay bound [po]. Xu et al. found MCTS best on efficiency [xu]. Ours: one greedy list with conflict table. | Compare with MCTS and polling. Unknown gap to optimal. |
| 47 | 0.3 s margin, 4 s horizon, 0.5 s tick, K=6, R=32 | 09 | INVENTED | Sensitivity tested in Python only. | Keep. Publish sweep. |

Tally: 14 ESTABLISHED, 20 ADAPTED, 13 INVENTED. Not audited here, because they are not design choices about practice, and their own reports grade them: V2X channel values (08, 12), physics tables (11), route search (06 §8.5), parameters in AV-REQUIREMENTS.

### What is better than practice, with evidence

- **Swept-path conflicts** over foe bits, from 3,605 pairs on 265 Berlin junctions: 12% missing and 18% spurious (report 09). Local census, not a claim about Vissim.
- **Replay tests.** Reports 05 and 04 hold out data and compare fair baselines. Most practice only fits aggregate outputs, and the California review says calibration is often undocumented [ucb]. Our test has limits: single windows, no capacity drop.
- **Exact ledger and no hidden removal.** SUMO's teleport leaves the car invisible; ours forbids it in counted runs. Not yet built.
- **Certificate.** Practice accepts unintended crashes and hides them with geographic filters [ssam]. A design that aims for none is better, if the GPU run shows it holds at realistic capacity. **That condition is exactly where SSAM says practice failed.**
- **Determinism test,** demanded explicitly; I didn't find it in GPU papers.

### Where practice is known wrong

- Static assignment for congestion charging: wrong traffic response and travel-time response [en].
- SUMO default parameters at capacity: greater deviation than others in the HBS study [hbs], and report 04's dt dependence. Vissim defaults: saturation slightly high [tvh].
- MATSim's `stuckTime` rests on unpublished evidence, by its own book [mb].
- Assumption that simulators don't crash [ssam].
- Published "validated" scenarios that don't remain valid: LuST's README says so itself [lu]; BeST lost half the demand, per report 03.
- Emulated advanced signal logic differs from real controllers [stv].

### Where we are wrong or weak, plainly

- Report 14 took forced merging from its own data and could not read the people who estimated it on the same site.
- Report 05 chose lag and noise looking at held-out chains. Capacity drop and lane-change closed loop are untested. Practice treats those as central.
- Report 07 has default signals in every build. Every project that claimed realism used real plans for at least part of the network.
- Report 06's cap and memory come from a queueing toy. It says so.
- Reports 05, 09, 11 and 14 are Python. None has reached the kernel.
- The specs never had a report like this one. Several "opinions" (50% demand test, urgency by distance) were already practice.

## Part 3. What to change

Ranked by expected value per effort. These are changes to specs and builds; I did not edit them, under this task's rules.

| # | Change | Why, source | Effort | Spec |
|---|---:|---|---|---|
| 1 | **Run the low-demand gate on Berlin and Stockholm**: very low demand, then 50%, with teleports off. Any queue is a coding fault, with its location. | [Trafikverket][tvh], [E-C153][ec]. Directly targets the 23,715 teleports and the evening cluster. | Hours, one GPU job at a time | 04, 06 |
| 2 | **Build missed turns and reroute.** Replace `T_FORCE` as the guarantee. Count Lost Inside, Lost Outside, and lost per 1,000 trips, reported with travel time. | [Aimsun][am], [TfL p. 197][tfl], report 14's Twin Cities cost. Needs Rust rerouting. | Days | 14 §4 |
| 3 | **Replace swap with offset stop points**, by hash, at least one car length apart, at lane-change end positions. Swap only as a counted fallback. | [Trafikverket p. 106][tvh] on the same deadlock. SUMO names it too [st]. | Hours | 14 §4 |
| 4 | **Remove time terms from courtesy** (`eta` backstop). Implement Aimsun-style two-leader anticipation. Add a cooperation sweep on I-80 and check throughput. | [Aimsun][am]; [Hidas][hi] warns more cooperation can lower flow; report 14 found no time effect. | Days | 14 |
| 5 | **Read Lee 2006, Choudhury 2009, Ahmed 1999 in full, then decide if the single critical-gap function replaces our logit.** Same I-80. | [Lee][le], [Choudhury][ch], [Ahmed][ah]. DSpace rate limited me; retry later. | Hours to days | 14 |
| 6 | **Test capacity drop and relaxation before any city claim for `MODEL_HUMAN`.** On-ramp, with and without shadow. Our tiny gap gain may already give slow relaxation, so measure it. | [Keane & Gao][kg], [Laval & Daganzo][la], [Vissim recovery][vre]. Report 05 left it untested. | Days | 05, 11 |
| 7 | **Add Wiedemann and Gipps to the replay tournament.** They are what the field uses. Report 05 didn't compare them. | [Vissim][vwm], [Aimsun][am]. | Days, CPU | 05 |
| 8 | **Real signals before realism claims.** Hand-code plans at the top sites in 07's list. Keep automated splits as placeholders, flagged. Emulate actuation and do not claim coordination transition. | [InTAS][in], [SimMobility][sm], [Stevanovic][stv], [Trafikverket][tvh], [CTS 2014][cts]. Needs Erik's request. | Weeks, data | 07 |
| 9 | **Replace defaults with TRVMB in Stockholm:** critical gaps, saturation, follow-up, jam density. Note them as design values. | [TRVMB][trv]. | Hours | 05, 07 |
| 10 | **Exit-clear compliance for humans** as a percentage, using Vissim's conditions as the starting rule. | [Vissim conflict areas][vca], [TfL][tfl] on observed blocking. | Hours | 05 |
| 11 | **Conflict output, SSAM style.** TTC < 1.5 s, PET, type. State that it is relative only, and that crossing conflicts are under-represented. Never publish human crash rates. | [SSAM][ssam], [ss6]. `--trace` already has the data. | Days | 08, 10 |
| 12 | **Scope the zero-collision rule to AV tiers in wording.** Human models count and locate. | [SSAM][ssam]. Decision for Erik, since AV-REQUIREMENTS is his. | Minutes | AV-REQ |
| 13 | **Route loop:** test cap 10% vs 15% and memory 0.3 vs 0.9, report RG, and compare with SUMO's Gawron on LuST. Keep turn-level costs on the list. | [MATSim][mb], [SUMO DUA][dua], which warns of underestimate on turning. | Days | 06 |
| 14 | **Queue baseline on the same net.** Show what micro adds to count fit and to speed. Claim only what shows up. | [Trafikverket][tvt], [Munich][mu], [E-C153][ec], [Zurich][zu]. | Days | 06 |
| 15 | **Scheduler baselines:** MCTS and polling on the same cases. | [Xu][xu], [Miculescu & Karaman][po]. | Days | 09 |

### The 15 references everyone should read

1. [FHWA Traffic Analysis Toolbox III, 2019][f5]. The acceptance logic.
2. [TfL Traffic Modelling Guidelines][tfl]. The most operational guide, covering Aimsun, Vissim and error files. Long; read B3 and B7.
3. [Trafikverket Handbok för kapacitetsanalys med simulering][tvh]. Swedish practice, with the 50% test and the lock.
4. [TRVMB Kapacitet][trv]. Swedish design values.
5. [Aimsun Next: microsimulation vehicle movement][am]. The clearest full description of production driving behaviour.
6. [Vissim lane change][vlc] and [conflict areas][vca]. Defaults and failure rules.
7. [SUMO: why vehicles teleport][st] and [safety][ss].
8. [SSAM final report][ssam], especially pp. 266–267. Why simulators crash.
9. [TRB E-C153 DTA Primer][ec]. Gridlock diagnosis and convergence.
10. [TAG M3.1][tag]. Validation and convergence for appraisal.
11. [MATSim book, part one][mb]. Stuck time and how a queue city model works.
12. [Choudhury et al. 2009][ch] with [Ben-Akiva, Choudhury & Toledo][bct]. Forced and cooperative merging, estimated.
13. [Keane & Gao][kg] with [Laval & Daganzo][la]. Why lane changes create capacity drop.
14. [de Palma et al. on Stockholm][dp] with [Engelson & van Amelsfort][en]. The one real prediction test on our own city.
15. [SimMobility Short-Term][sm]. The closest published analogue of what we want: city micro, communication, real calibration.

## Could not open, not established

**Could not open:**

| Item | Result |
|---|---|
| PTV default for diffusion time | PTV 2025 page shows none; often quoted as 60 s; not confirmed |
| Maryland SHA Vissim guidance | 403, also in browser |
| Austroads AP-R286-06 PDF, R621 slides | 403; landing page only |
| Transport for NSW Traffic Modelling Guidelines (2013) | 404 at the guessed URL; only a technical direction citing it opened [nsw] |
| Vicroads, WA Main Roads, WSDOT, Oregon, Virginia, Caltrans guides | 403 or 404 at guessed URLs; not searched further. NCDOT TransModeler guidance opened, with nothing on gridlock in my search. |
| TransModeler user guide, Paramics manual | Not found openly; only product pages. **So I make no claim about them on stuck cars.** |
| MITSIMLab documentation on gridlock | Not found |
| POLARIS | ANL page 403, ScienceDirect blocked. **No claims.** |
| BEAM | LBL page opened with no accuracy; eScholarship blocked by bot check. **No claims.** |
| Laval & Daganzo full text, Zheng 2014 full text | Publisher; abstracts only |
| Hidas 2002, 2005 TR-C | Publisher; his 2004 ATRF paper opened instead |
| Ahmed, Lee, Rao, Ramanujam, Choudhury full texts | DSpace rate limit (429). **Abstracts read in browser; equations not read.** |
| Toledo 2003 thesis, Toledo 2007, Toledo & Zohar | Not reached |
| Essa & Sayed, Huang et al., Fan et al. on simulated conflicts | Not reached. Only search snippets |
| Punzo guidelines, Ossen et al. | Not reached, no numbers used |
| HCM critical gap tables, Brilon, Troutbeck, Kimber RR67, FGSV | Paid or not reached. TRVMB used. |
| FLAME GPU, Heywood et al. | Not reached |
| Aimsun Manhattan and London case studies, Lower Manhattan TRB paper | 404, 403 |
| VISSIG, VS-PLUS, SCOOT and SCATS documentation | Only lists of options; no accuracy data. SCATSIM not found |
| Stockholm's controller documentation | Only through Trafikverket's handbook and report 07's sources |
| A published Essingeleden microsimulation validation | Not found. CTS 2014 reports only the DTA test |
| Build time of named projects | Almost never stated |

**Not established at all:**

- A guideline's accepted teleport or removal percentage.
- Whether full-city micro beats meso on flows.
- A measured rate of real gridlock in a city.
- Measured Swedish desired speeds.
- Independent audits of named projects.
- Whether our certificate keeps capacity at the GPU level.

## What only Erik can do

- **Request signal plans** from Trafikkontoret, as in report 07. It is the largest single input we lack.
- **Library access** to Hidas 2005, Laval & Daganzo, Zheng 2014, Toledo 2007, Essa & Sayed and the HCM. Hidas 2005 is the one I would check first.
- **Vendor access:** a Vissim or Aimsun licence or evaluation, if he wants them run against `cars` on one junction. Not needed for the ranked list.
- **Decide row 12,** that zero collisions binds AV tiers and not human traffic. The requirements file is his.

## Source register

**Guidelines and handbooks (G).**

[f5]: https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter5.htm
[f6]: https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter6.htm
[tfl]: https://content.tfl.gov.uk/traffic-modelling-guidelines.pdf
[tag]: https://assets.publishing.service.gov.uk/media/6a033d074fb0713aa63ea802/tag-m3-1-highway-assignment-modelling.pdf
[act]: https://www.cityservices.act.gov.au/__data/assets/pdf_file/0009/1539576/ACT-Traffic-Microsimulation-Modelling-Guidelines_TCCS.pdf
[aus]: https://austroads.gov.au/publications/traffic-management/ap-r286-06
[ec]: https://onlinepubs.trb.org/onlinepubs/circulars/ec153.pdf
[tvh]: https://bransch.trafikverket.se/contentassets/32ce05ecc3ac458bb8ecb802e8e2da54/handbok_for_kapacitetsanalys_med_hjalp_av_simulering.pdf
[tvt]: https://bransch.trafikverket.se/contentassets/a315cfef2b514117a3d66655c8a1dea0/2024/handledning---restidsnyttor-mikro--och-mesomodeller-2023-240401.pdf
[trv]: https://bransch.trafikverket.se/globalassets/dokument/trvmb_kapacitet_och_framkomlighetseffekter.pdf
[ucb]: https://escholarship.org/content/qt3hh8f7nz/qt3hh8f7nz.pdf
[nsw]: https://standards.transport.nsw.gov.au/_entity/annotation/ebd99ea5-a835-ed11-9db2-000d3ae019e0

[FHWA 2019 ch. 5][f5], [ch. 6][f6], [TfL][tfl], [TAG M3.1][tag], [ACT, via browser][act], [Austroads landing page][aus], [TRB E-C153][ec], [Trafikverket handbook][tvh], [Trafikverket restid][tvt], [TRVMB][trv], [Zhang & Ma][ucb], [RMS TD 2017/001][nsw].

**Vendor manuals (V).**

[vlc]: https://cgi.ptvgroup.com/vision-help/VISSIM_2025_ENG/Content/4_BasisdatenSim/FahrverhaltensparameterFahrstreifenwechsel_bearb.htm
[vca]: https://cgi.ptvgroup.com/vision-help/VISSIM_2026_EN-DE/en-us/Content/5_Netzbearbeiten/Konfliktflaechen_Attr.htm
[vwm]: https://cgi.ptvgroup.com/vision-help/VISSIM_2025_ENG/Content/4_BasisdatenSim/DasVerkehrsflussmodellnachWiedemann.htm
[vw]: https://cgi.ptvgroup.com/vision-help/VISSIM_2025_ENG/Content/4_BasisdatenSim/FahrverhaltensparameterFolgeverh_Wied99.htm
[vre]: https://cgi.ptvgroup.com/vision-help/VISSIM_2025_ENG/Content/4_BasisdatenSim/Fahrverhaltenspar_Erhol.htm
[vsc]: https://cgi.ptvgroup.com/vision-help/VISSIM_2025_ENG/Content/5_Netzbearbeiten/Lichtsignalanlagen_modellieren.htm
[am]: https://docs.aimsun.com/next/latest/UsersManual/MicrosimulationModellingVehicleMovement.html
[an]: https://docs.aimsun.com/next/latest/UsersManual/NodeEditing.html
[ad]: https://docs.aimsun.com/next/latest/UsersManual/DynamicScenariosAndExperiments.html
[adt]: https://docs.aimsun.com/next/latest/UsersManual/DynamicTrafficAssignment.html
[ac]: https://docs.aimsun.com/next/latest/UsersManual/CalibrationAndValidationOfAimsunModels.html
[aad]: https://docs.aimsun.com/next/latest/UsersManual/AdaptiveControlInterfaces.html

[Vissim lane change][vlc], [conflict areas][vca], [Wiedemann][vwm], [W99][vw], [recovery][vre], [signals][vsc]. [Aimsun micro][am], [nodes][an], [dynamic scenarios][ad], [DTA][adt], [calibration][ac], [adaptive][aad].

**Open-source documentation and code (D).**

[st]: https://sumo.dlr.de/docs/Simulation/Why_Vehicles_are_teleporting.html
[ss]: https://sumo.dlr.de/docs/Simulation/Safety.html
[si]: https://sumo.dlr.de/docs/Simulation/Intersections.html
[so]: https://sumo.dlr.de/docs/Networks/Import/OpenStreetMap.html
[stl]: https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html
[dua]: https://sumo.dlr.de/docs/Demand/Dynamic_User_Assignment.html
[sv]: https://sumo.dlr.de/docs/Definition_of_Vehicles,_Vehicle_Types,_and_Routes.html
[sf]: file:///home/erikf/projects/personal/thesis-src/sumo/src/microsim/lcmodels/MSAbstractLaneChangeModel.h
[lc]: https://elib.dlr.de/102254/1/Springer-SUMOs_Lane_changing_model.pdf
[mb]: https://www.matsim.org/files/book/partOne-latest.pdf
[mq]: https://matsim.org/doxygen/_q_sim_config_group_8java_source.html
[best]: https://github.com/mosaic-addons/best-scenario
[lu]: https://github.com/lcodeca/LuSTScenario
[ha]: https://github.com/matsim-scenarios/matsim-hamburg

[SUMO teleport][st], [safety][ss], [intersections][si], [OSM import][so], [signals][stl], [DUA][dua], [vehicle types][sv], [shadow lane source][sf], `RODUAFrame.cpp:125` for Gawron defaults, [LC2013, Erdmann][lc], [MATSim book][mb], [QSim config][mq], [BeST][best], [LuST][lu], [MATSim Hamburg][ha].

**Lane changing.**

[ah]: https://dspace.mit.edu/handle/1721.1/9662
[le]: https://dspace.mit.edu/handle/1721.1/34607
[ra]: https://dspace.mit.edu/handle/1721.1/34602
[rm]: https://dspace.mit.edu/handle/1721.1/39286
[ch]: https://dspace.mit.edu/handle/1721.1/89070
[bct]: https://cris.iucc.ac.il/en/publications/integrated-lane-changing-models/
[hi]: https://australasiantransportresearchforum.org.au/wp-content/uploads/2022/03/2004_Hidas.pdf
[zh]: https://ideas.repec.org/a/eee/transb/v60y2014icp16-32.html
[la]: https://its.berkeley.edu/node/4685
[kg]: https://arxiv.org/pdf/1904.08395
[ld1]: https://arxiv.org/pdf/2108.06640
[ld2]: https://arxiv.org/pdf/2108.05710
[tr]: https://arxiv.org/pdf/adap-org/9710003
[ri]: https://arxiv.org/pdf/cond-mat/9512119

[Ahmed][ah], [Lee][le], [Rao][ra], [Ramanujam][rm], [Choudhury et al.][ch], [Ben-Akiva et al.][bct], [Hidas 2004][hi], [Zheng abstract][zh], [Laval & Daganzo abstract][la], [Keane & Gao][kg], [Li et al. 1][ld1], [Li et al. 2][ld2], [TRANSIMS flow][tr], [Rickert][ri].

**Safety, car following and physics.**

[ssam]: https://www.fhwa.dot.gov/publications/research/safety/08051/08051.pdf
[ss6]: https://www.fhwa.dot.gov/publications/research/safety/08051/06.cfm
[sb]: https://www.fhwa.dot.gov/publications/research/safety/08049/08049.pdf
[ss03]: https://www.fhwa.dot.gov/publications/research/safety/03050/03050.pdf
[rs]: https://arxiv.org/pdf/1708.06374
[ti]: https://arxiv.org/pdf/1403.4881
[kt]: https://arxiv.org/pdf/1610.03124
[hbs]: https://trid.trb.org/View/1461094
[stv]: https://midasnetwork.us/papers/microscopic-modeling-of-traffic-signal-operations-comparative-evaluation-of-hardware-in-the-loop-and-software-in-the-loop-simulations/

[SSAM final][ssam], [chapter 6][ss6], [brief][sb], [2003 report][ss03], [RSS][rs], [Treiber & Kanagaraj][ti], [Kurtc & Treiber][kt], [HBS study abstract][hbs], [Stevanovic abstract][stv].

**Deployments.**

[sm]: https://web.mit.edu/cami/Public/CLA_SimMobilityST_TRB_2017.pdf
[ml]: https://trid.trb.org/View/1438614
[sy]: https://fis.tu-dresden.de/portal/en/publications/deployment-and-calibration-considerations-for-largescale-regional-dynamic-traffic-assignment(3a7ae756-ce13-434d-bbcf-0327096c13d3).html
[sya]: https://arxiv.org/pdf/1906.04739
[zu]: https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2010/10-07/20100801-submitted.pdf
[ny]: https://arxiv.org/pdf/2008.04762
[mb24]: https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2024/24-22/RakowEtAl_MATSimBerlinEWGT.pdf
[mu]: https://www.mdpi.com/2624-6511/8/1/2
[in]: https://arxiv.org/pdf/2011.11995
[kl]: https://sri.com/?p=87733
[dp]: https://wctrs-society.com/wp-content/uploads/abstracts/rio/general/2090.pdf
[en]: https://ideas.repec.org/a/taf/transp/v38y2015i6p684-707.html
[cts]: https://www.transportportal.se/swopec/CTS2014-10.pdf
[ba]: https://dspace.mit.edu/handle/1721.1/35120

[SimMobility][sm], [Melbourne abstract][ml], [Sydney abstract][sy], [Sydney hierarchy][sya], [Zurich][zu], [New York][ny], [Berlin 2024][mb24], [Munich, via browser][mu], [InTAS][in], [Los Angeles abstract][kl], [Stockholm comparison][dp], [Engelson & van Amelsfort abstract][en], [SAMPERS test][cts], [Balakrishna abstract][ba].

**Parallel and scheduling.**

[mo]: https://escholarship.org/content/qt43r1046c/qt43r1046c.pdf
[lp]: https://arxiv.org/pdf/2406.08496
[cf]: https://arxiv.org/pdf/1905.05217
[mos]: https://arxiv.org/pdf/2405.12520
[gpo]: https://arxiv.org/pdf/2406.10661
[ai]: https://www.cs.utexas.edu/~aim/papers/JAIR08-dresner.pdf
[po]: https://arxiv.org/pdf/1607.07896
[xu]: https://arxiv.org/pdf/2010.03148

[Mobiliti][mo], [LPSim][lp], [CityFlow][cf], [MOSS][mos], [GPU simulator][gpo], [AIM][ai], [Miculescu & Karaman][po], [Xu et al.][xu].
