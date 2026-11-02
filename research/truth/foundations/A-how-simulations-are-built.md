# A: How a real-to-life traffic microsimulation is built

Checked 2026-11-02. Reading only: no simulation, no code, no GPU, nobody contacted. SUMO and other simulators appear here only as sources on practice, never as evidence of accuracy.

**How to read this.** Plain text and tables say what a source says, with its page or section. **Inference:** marks my own reasoning. Quotes are short; everything else is paraphrase. Section 8 lists what each source says and how much of it I read.

## The answer

**The guidance agrees on one idea: fix what can be measured directly, at the smallest scale that can measure it, before anything that can only be seen at network level. Each later step depends on the one before.** Geometry and signals set capacity. Capacity sets where queues form. Queues set delay. Delay sets routes. Routes set flows. If you tune from the far end of that chain, parameters absorb errors they did not cause, and the model is right for the wrong reason (FHWA 2004, pp. 7, 45, 54).

**Five findings change what we should do:**

1. **Nobody builds a model without first listing the real bottlenecks.** Gomes lists them from speed contours before coding. FHWA's capacity step uses only counts at bottlenecks. FHWA 2019 makes bottleneck onset and duration a required calibration measure. We score top-20 bottlenecks but have never produced the list as an input. Without it nobody can tell a false bottleneck from a real one, and "does 50% jam?" has no reference.
2. **The guidance assumes the engine is already validated.** FHWA 2004 (p. 4) presumes the developer did that. We are the developer, so the guides do not cover our largest risk. MULTITUDE and Toledo do: estimate each behaviour model on its own data first, then calibrate the whole (MULTITUDE, p. 81; Toledo framework, §2).
3. **Our main lock-up is a known, named failure with a known first fix.** Conflicting parallel lane changes are in FHWA 2019 ch. 5 and SUMO's teleport page. Gomes hit the same kind of blockage on his first run: cars could not make their lane changes before the exit, and the queue overran the site. Tuning look-back distances per decision point "corrected almost completely" the blockage. Our next planned fix is an engine lane swap. Test look-back first.
4. **Teleports off at full demand is stricter than anything published.** Every tool I read ships a relief valve, on by default in SUMO, Vissim and MATSim. Guidelines say to audit and remove the events, but I found no numeric limit in any of them. Keep it as the final test. Do not use it as the only way to look at a run.
5. **Two inputs are outside what guidance considers a valid start.** Berlin has no real signal plans, and our 50% test ran on routes that overload lanes by hand arithmetic. FHWA 2019 says that if data can't support the study, collect more or don't use microsimulation. Our own report 15 said to pick a site with real plans, and step 0 did not.

## Contents

1. [The construction order](#1-the-construction-order)
2. [Where the sources disagree](#2-where-the-sources-disagree)
3. [What must be right before any network run](#3-what-must-be-right-before-any-network-run)
4. [When a network locks](#4-when-a-network-locks)
5. [What our project skipped or did out of order](#5-what-our-project-skipped-or-did-out-of-order)
6. [Ten sentences](#6-ten-sentences)
7. [Where reports 15, 20 and 22 are wrong or shallow](#7-where-reports-15-20-and-22-are-wrong-or-shallow)
8. [What each source says, and what I could not read](#8-what-each-source-says-and-what-i-could-not-read)

---

## 1. The construction order

No single source gives all of this. FHWA 2004 is the skeleton: scope, data, base model, error check, calibration (capacity, then routes, then system), then use. Steps 2 and 3 come from other sources and are marked. The exit numbers are the sources' own unless marked.

### Step 0. Fix the question, the scope, the targets and the time step

**Do.** State what the model must answer and what it won't. Choose the area and hours. Write calibration targets and validation data down before the work starts.

**Why.** FHWA says a tight scope is what makes microsimulation pay, and compares it to a microscope (2004, p. 13). A scope covering large areas tends to rule it out (p. 13). The model should contain all the congestion, or it measures capacity and not demand (p. 12, note 1). TfL fixes the time step before calibration because changing it later changes driver behaviour and forces re-validation (v4, §7.4.1.2).

**Exit.** A written scope. Queues must not reach the edge of the model (FHWA 2004, pp. 13, 81). Hours run from before congestion starts to after it clears (FHWA 2019 ch. 3).

**Numbers.** Fremont: 21 km², 37 signals, about 2,500 person-hours (Fremont, pp. 7, 22). Gomes: 15 miles of freeway. FHWA: budget about 50% for data and coding, 25% calibration, 25% use (2004, p. 17, note 6). TfL: 0.2 s step (§7.4.1.2). FHWA: most tools use 0.1 s (2004, p. 95).

### Step 1. Collect data at the same time, and clean it

**Do.** Geometry from drawings or aerial images. Signal plans from the operator, checked in the field. Counts at most 15 minutes, starting before congestion and ending after it. Travel times, speeds and queues on the same days as the counts. Capacity measured where queues discharge.

**Why.** A model can't reproduce speeds from a day other than its demand (FHWA 2004, p. 27, note 17). A count inside a queue measures capacity, not demand (p. 25). Input errors distort calibration (p. 7). MULTITUDE: distrust even digital maps, because lanes and controller logic often differ from the record (p. 59).

**Exit.**
- Upstream and downstream counts agree within 10% where no source or sink lies between (FHWA 2004, p. 31, note 19).
- Field capacity within 25% of the HCM; beyond that, recheck both (p. 31, note 20).
- Days free of bad weather, roadworks, incidents and events (Trafikverket 2014, §2.7.3).
- Sensors audited. In Des Moines, one bad detector on a parallel street made the freeway impossible to fit (report 15).

**Numbers.**
- Saturation flow measured at every signal running at 90% of capacity or more (FHWA 2004, p. 30).
- Field capacity needs a queue of at least 15 minutes (p. 56), ideally an hour (pp. 29-30).
- Day-to-day counts vary by 10% or more (p. 31).
- Ten or more floating-car runs in congestion (p. 28).

### Step 2. Estimate each behaviour model separately, on disaggregate data

**This step is missing from the practitioner guides, because they assume the vendor did it.**

**Do.** Fit car following, lane changing, gap acceptance and route choice from trajectories and surveys, outside any network. Test each on held-out data (Toledo framework, §2; MULTITUDE, p. 81).

**Why.** Aggregate data can't separate the models. Their effects are confounded in flows and speeds (Toledo et al. in Daamen 2014, §6.3.2; MULTITUDE, p. 83). Treiber and Kesting: use plausible published values, fix what the data can't see, keep the rest inside a box of plausible values, and check the fit surface has a real minimum inside it (2013, §6).

**Exit.** Plausible values on held-out data. No tipping-point data in the fit (Treiber and Kesting 2013, §6). Spatiotemporal features of oscillations (wavelength, propagation speed, growth rate) tested against data (Treiber and Kesting 2010, §5).

**Numbers.** Fit error has a floor of about 20% in rms, which cannot separate models (2013, §6). Global calibration on gaps is more reliable than on speed or acceleration. 1 Hz is enough, and at least 300 s of data is needed (2013, §6).

**Inference.** For us this is report 22's levels 1 and 2. It belongs before a city, not alongside one.

### Step 3. Find the real bottlenecks and explain them

**Do.** Plot speed contours and flows from field data. For each bottleneck, record location, activation time, queue extent and clearance time. Say what causes it: geometry, weaving, or demand over capacity.

**Why.** Overall performance is largely set at these points (FHWA 2019 ch. 5). Most counts are at non-critical locations, so calibrating to all of them first wastes the signal (FHWA 2004, p. 55, note 9). The reasons chosen then limit which parameters may change (Gomes, pp. iii-iv, 19).

**Exit.** A table of real bottlenecks with times. Gomes: three bottlenecks, nine indicators (start, end and extent for each). He identified them **before coding** (report, pp. iii, 11).

**Numbers.**
- Gomes' measured onset windows are 30 minutes wide, for example 6:00-6:30 (Table 3).
- FHWA 2019: bottleneck congestion speed threshold as a rule of thumb one third of free-flow speed, onset and duration within 15-minute intervals.
- Zhang and Ma: location all; duration within ±2 periods (often 15 min); spillback within ±1 section (UC Berkeley report, Table 7).

### Step 4. Build the model in layers

**Do.** Link and node blueprint; link geometry; control; demand; behaviour; run control (FHWA 2004, p. 7; 2019 ch. 3). Prefer measured values, and leave behaviour parameters at defaults until there is evidence (TfL §7.4.2.2; TAG 5.4.5).

**Why.** Each layer can be checked by itself. Consistent coding rules reduce later adjustment (TAG 5.4.5).

**Exit.** A QA plan run and documented. Headline statistics and a map of which data is measured and which is derived (TAG 5.4.2-5.4.3).

**Numbers.** SF DTA imported every relevant signal from real timing plans and judged them about 99% right after QA. Fremont's network with signals took about 600 person-hours, and signal setup took longest (pp. 7, 10).

### Step 5. Check for errors, in three tiers, before any calibration

**Do, in this order** (FHWA 2004, pp. 45-49; 2019 ch. 4):
1. **Software.** Known bugs, patches. Code a single link or intersection whose result you can compute by hand, and compare (2004, p. 48).
2. **Inputs.** Connectivity, lanes, speeds, controls, prohibited turns, vehicle mix, sources and sinks. Overlay on a map. Colour links by attribute to spot breaks.
3. **Animation, low demand.** Demand so low there is no congestion. Follow single vehicles for several OD pairs and look where they slow unexpectedly. Those places are usually coding errors.
4. **Animation, 50% demand.** Demand is usually not yet high enough to cause congestion. If it appears, it may come from subtle coding errors affecting lane distribution or headways. Check all demand loads and leaves.

Signals: run reduced, balanced volumes to confirm all phases are served (2004, p. 50). Forbid infeasible paths; FHWA's own example is U-turns at an interchange (p. 50, note 6).

**The primer's version** (TRB E-C153, pp. 36-37, 44): run a uniformly reduced demand to reach roughly free flow, and see if unusual congestion still forms. Begin with a **flat** demand matrix scaled down, because a peaked profile generates more congestion from the same cars. Use peak loading only after capacity-side coding errors are gone. Do not compare with data until the model is stable and gridlock-free.

**Why.** Calibration can't be used to debug. Coding errors get absorbed as false parameter values (FHWA 2004, p. 7; TAG 5.4.1: do not start calibration until the network passes basic checks).

**Exit (FHWA 2004, p. 49).** All inputs correct, parameters reasonable, animation looks right against field knowledge. At 50%, travel time and delay reflect free flow (p. 51). Seed-to-seed spread small. A large spread suggests coding errors or gridlock from contention, and such runs must not be used (2019 ch. 5).

**Numbers.** Fremont: 50% test, then full demand flagged at sites under 50% or over 200% of real flow. 43 logged issues, about 500 person-hours (p. 11). Fixes: lane connections, lane counts, section geometry, parking lots used as cut-throughs, signal imports, missing synchronisation between operators.

**Do not expect the model to be free of congestion if the demand itself is overloaded.** See section 3b.

### Step 6. Calibrate capacity, global first, then local

**Do** (FHWA 2004, pp. 55-61):
1. Measure capacity in the field at bottlenecks.
2. Get model capacity by forcing a queue: raise demand temporarily if the model shows none there.
3. Temporarily raise capacity at any **false bottleneck** so the run can proceed. Remove these later.
4. Select one or two capacity parameters: headway, reaction time, gap, standstill distance, startup lost time.
5. Minimise squared error against field capacity, over several seeds, inside physical bounds.
6. Fine-tune locally, sparingly, because a link factor isn't behaviour-based and stays in all future runs.

**Why.** Capacity decides when and where the system goes from free to congested (FHWA 2004, p. 29). Global first means even uncongested links are right (p. 56, note 10). Once capacities are right, wrong bottleneck locations should go away by themselves (p. 69). Route choice depends on speeds from this step (FHWA 2013 DTA guide, §8.6).

**Exit.**
- Modelled saturation flow within 10% of observed (TfL §7.5.2.2).
- Each bottleneck's maximum throughput within the range across all days of that travel condition (FHWA 2019 ch. 5).
- TAG: capacity must be at least the count on every turn, and changes of order 20% are defensible, larger need more explanation (6.2.3, 6.2.8).

**Numbers.** At signals, queue of at least 10 per lane, discard the first three headways (FHWA 2004, pp. 56-58). Ten replications in FHWA's example. There, seed SD is 33-45 veh/h at about 1,800 (Table 5). TfL: default Vissim gives 1,900-2,100 at 20 mph and runs too freely, so it adds reduced-speed areas at stop lines to hit measured flow (§7.4.2.4). Lausanne measured 1.5 s reaction at stop from five positions at several signals (Bert 2005, §3.2).

### Step 7. Calibrate routes and demand against the other counts

**Do.** Remove the temporary demand. Compare modelled volumes with counts away from bottlenecks. Adjust route parameters, global then local (FHWA 2004, p. 62). Do OD work with a strong prior.

**Why.** With capacity right, what's left at non-bottleneck sites should be routes or demand (p. 69). OD estimation assumes a working traffic model (MULTITUDE, p. 59). Eliminate coding errors and calibrate flow and routes before touching OD, which is a last resort (FHWA 2013, §8.6).

**Exit.**
- TAG 3.3: screenlines within 5% on 95% of cases. Flows within 100 veh/h under 700, 15% between 700 and 2,700, 400 veh/h above, on over 85% of cases. GEH under 5 on over 85%.
- TAG Table 5: matrix estimation must stay small. Zonal cells slope 0.98-1.02, R² over 0.95. Trip ends slope 0.99-1.01, R² over 0.98. Trip length mean and SD within 5%. Sector changes within 5%. If it can't reach the targets inside those limits, report a lower standard (3.3.3).
- Assignment stable: %GAP under 0.1% or stable and documented, and over 98% of links changing by under 1% for four iterations (TAG Table 4).
- TfL: all entry flows within 5% (§7.5.2.1).

**Numbers.** Fremont: without regularisation, fit slope 0.92 and R² 0.91, test slope 1.30 and R² 0.81. They then set a large penalty for moving from the prior (pp. 13-14).

**Known: route cost needs a road hierarchy.** Lausanne, San Francisco and Barcelona each found drivers overuse small streets on pure time, and added a preference for main roads (Bert §4.1; SF "Generalized Cost Functions"; Barcelona).

### Step 8. Calibrate system performance, sparingly

**Do.** Compare travel times, queues and queue duration with field data. Make small changes only, since they can undo steps 6 and 7 (FHWA 2004, p. 63).

**Exit.**
- FHWA 2019's four criteria on a real representative day, in one run, for each measure and condition: 95% inside ±1.96σ; two thirds and both critical periods inside ±1σ; mean absolute error at most the between-day error; absolute bias at most a third of that.
- At least one travel-time measure and one bottleneck measure.
- TAG Table 3 and TfL: journey times within 15% (TAG: or 1 minute, on over 85% of routes).
- TfL: queues in the right place at the right time; length isn't a criterion because it can't be measured alike (§7.5.2.5).

**Numbers.** Gomes matched all nine indicators by manual iteration, with a few global changes and two local ones. After the look-back fix, default CC4/CC5 produced almost no congestion, so a global following parameter had to change before the real jams appeared (p. 19).

### Step 9. Validate on independent data, then test a change

**Do.** Compare with data never used in calibration (FHWA 2004, p. 4; TAG 3.3.1; TfL §2.4.2). Prefer data covering a change in the system (FHWA 2013, §8.7). Report spread across seeds, not only means (MULTITUDE, p. 26).

**Why.** Validation error is usually larger than calibration error (MULTITUDE, p. 60). Counts used to fit OD can't validate the model alone (p. 83). TAG: meeting the numbers doesn't make a model fit for purpose, and they aren't targets to constrain the model to (3.2.2, 3.3.2).

**Exit.** Thresholds set before running (MULTITUDE, p. 60). TfL also requires a continuous seed range, no cherry-picking, at least 20 seeds (§7.5.1).

**Numbers.** FHWA 2019: `N = (t·s/(e·x̄))²`, with four initial runs, 5% tolerance floor. If N exceeds 20, investigate instead of running more: it may mean gridlock or coding errors (ch. 6).

### What is known to work and known to fail

| Known to work | Evidence | Known to fail | Evidence |
|---|---|---|---|
| Listing real bottlenecks, then choosing parameters by their cause | Gomes: nine indicators met with few changes | Tuning all counts first | FHWA 2004, p. 55, note 9 |
| Near-empty, then reduced-demand checks | FHWA; E-C153; Fremont found 43 issues | Debugging through calibration | TAG 5.4.1; FHWA 2004, p. 7 |
| Measured capacity, global then local | FHWA; TfL; Lausanne's measured reaction time | Software defaults as if calibrated | FHWA 2019 ch. 5; FHWA 2004, p. 53 |
| Look-back tuned per decision point | Gomes §12; TxDOT warns the default may be too late | One look-back everywhere: too short blocks, too long bunches | Gomes §12 |
| Strong prior on OD, with a test split | Fremont; TAG Table 5 | Free OD fit | Fremont: fit slope 0.92, test slope 1.30 |
| Road hierarchy in route cost | Lausanne, SF, Barcelona | Pure travel time on a dense grid | SF: traffic moved to streets without counts |
| Equilibrium from low demand upward | Barcelona 2% steps; Aimsun incremental DUE | Assignment from a jam | Barcelona; report 23 |
| A short list of tuned parameters | Fremont 35 to 10; MULTITUDE p. 20 | Automation hiding manual choices | Calibration Illusion |
| Named cause and evidence for each local fix | Gomes; TAG 6.2.5; HA via MULTITUDE | GEH as an objective; synthetic average days | MULTITUDE p. 26; FHWA 2019 ch. 5 |

**Not known to work anywhere:** a city-scale micro model that reaches held-out accuracy with no relief valve. Report 15 reached the same conclusion on accuracy; this report adds the valve.

---

## 2. Where the sources disagree

| Question | One side | Other side | My reading (**inference**) |
|---|---|---|---|
| **Demand before or after capacity?** | FHWA 2004: capacity first, demand presumed checked at entries (p. 55, note 9). It has no OD step at all. MULTITUDE §A notes that assumption and says Austroads and SIAS add OD calibration (p. 64). FHWA 2013: OD last resort | MULTITUDE Issue 6: inputs, then demand, and only then driver parameters (pp. 21, 59-60). Fremont: network, OD static, then routes and driver | Not a real conflict if capacity is calibrated in isolated scenes. Those don't depend on network demand. FHWA gets there by temporarily raising demand at each bottleneck. MULTITUDE's "driver parameters" are the network-level tuning after that |
| **Sequential or joint?** | FHWA 2004, 2019: essential to break into steps or you circle forever. Trafikverket: one parameter at a time | Lausanne: everything interacts, so all must be evaluated in parallel (Bert §1). Toledo ch. 6: joint gives the most efficient estimates (§6.5). Calibration Illusion: a parameter hierarchy that permits sequential calibration is currently unknown (§3.1.4) | Sequential for finding faults, joint at the end. Jha (Des Moines) did both: driver on one isolated section, then joint iteration on OD and routes. Report 15 said this too |
| **Calibrate on one run or many?** | FHWA 2019: single run per condition. Seed variation is second order against travel conditions | FHWA 2004: several per parameter set; TfL: at least 20 for both calibration and validation. Hollander and Liu (via Toledo ch. 6): most methods use too few | Both agree a large seed spread is a warning. FHWA 2019's stance assumes a stable model. Ours isn't |
| **What is the reference?** | FHWA 2019: one real representative day. Synthetic averages not recommended | E-C153: averaging is common; or average and pick the day nearest it. TfL: often one survey day against a mean of 20 seeds. Gomes: composite inputs, so no error norm at all, only pattern goals | Report 22's all-pairs rule is stricter than all. It agrees with FHWA in spirit |
| **Is GEH usable?** | TAG, TfL, FHWA Table 4, ODOT: yes. TfL also wants under 3 on critical links | MULTITUDE: inappropriate for calibration because many parameter sets satisfy it (p. 26). Imported from planning models without reflection (p. 13) | Report only, as report 22 says. TAG itself calls it an assessment and not a target |
| **Local fixes** | FHWA: allowed, sparingly. Gomes: two locals, with named causes. I-210: heavy local tuning (report 15) | RMS NSW (via MULTITUDE, p. 37): unjustified remote speed changes get the model rejected. HA: only with observed basis. TAG: no arbitrary changes to measurable quantities | Named cause plus external evidence, counted. Report 22 rule 7 agrees |
| **Queue length** | Gomes, FHWA 2004, Zhang: calibrate to queue extent | TfL: not a criterion; location and period are | Use extent only where derived from a contour or loops, not from a definition-dependent count |
| **Time step** | TfL: fixed before calibration, 0.2 s. Treiber and Kanagaraj: integration scheme and step act like reaction time | Fremont lists time step among parameters to calibrate (p. 15) | Fix it. Calibration Illusion found 10% changes to such parameters could more than double MAPE |
| **Driver defaults** | FHWA 2004 example: defaults judged enough (p. 42, note 27). TfL: defaults unless measured | FHWA 2019: defaults aren't a calibrated model. FHWA 2004: rarely accurate for a real site (p. 53) | Measured values first |
| **How big can it be?** | FHWA: large scope tends to rule microsimulation out (p. 13) | MULTITUDE: no guideline says small areas only (p. 64). Des Moines, Barcelona did metro scale | Possible, unvalidated at that scale. Report 15 stands |
| **Valves** | SUMO: gridlocks are common, fix the flow. FHWA 2019: models with unrealistic gridlock are not usable | MATSim: moves stuck vehicles after 10 s by default and says longer times gave less realistic counts, in unpublished tests (book §4.4). Gomes: cut Vissim's diffusion to 1 s at off-ramps | Section 4 |

---

## 3. What must be right before any network run

### 3a. The list, and the small test for each

Thresholds are the sources' where a source is named; **inference** otherwise.

| # | What | Small test | Pass | Source |
|---:|---|---|---|---|
| 1 | Engine does what the theory says | Single link, single junction, result computed by hand | Matches. If not, it's a software bug | FHWA 2004, p. 48 |
| 2 | Time step chosen | Same scene at the chosen step and smaller | Metrics don't move beyond noise | TfL §7.4.1.2; Treiber and Kanagaraj; report 22 V5 |
| 3 | Steady-state flow against density | Long road or ring, sweep density. Compare with the model's analytic fundamental diagram | Capacity and jam spacing as derived. Gomes uses (safe gap + length) × capacity = free speed | Treiber and Kesting book §11.4 (ToC only); Gomes p. 16 |
| 4 | Car following on real leaders | Replay and closed chains from held-out trajectories | Report 22's M-levels | Toledo framework; Treiber and Kesting 2013 |
| 5 | String stability and waves | Platoon perturbation; congested bottleneck | Wavelength, speed and growth rate near data | Treiber and Kesting 2010 |
| 6 | Queue discharge at a signal | One lane, queue of 10+, drop the first three, repeat over seeds | Within 10% of measured | FHWA 2004, p. 58; TfL §7.5.2.2 |
| 7 | Give-way capacity | Minor flow against major flow, with random gaps | On gap-acceptance theory, from measured critical gap and follow-up | Report 22 JP/JR; FHWA list p. 58; Austroads critique (search result) |
| 8 | Lane changing under pressure | Short road with crossing demand, a weave, a lane drop, an off-ramp at realistic flows | Nothing stops for good; flow near the merge or weave target; change position realistic | **Inference**, from Gomes §12, SUMO, FHWA 2019 ch. 5 |
| 9 | Look-back distance | Sweep per decision type on the scene above | Too short blocks at the exit; too long bunches far upstream (Gomes). Regions don't overlap | Gomes p. 17; TxDOT 13.5.3; TfL §7.4.2.1 |
| 10 | Vehicle length and spacing | Measure from queue scenes | Within measured; don't use as a gridlock dial. SF's model tipped into gridlock from 1 ft of truck length | SF; report 15 |
| 11 | Signals | Reduced balanced volume, all phases served; real timing checked in the field | Every phase runs; demand-dependent stages within 10% of on-street | FHWA 2004, p. 50; TfL §7.5.2.3 |
| 12 | Free-flow speed on each road class | Near-empty net, trace single vehicles | No unexpected slowdowns; speeds near real early-morning speeds | FHWA 2004, pp. 46-47 |
| 13 | Routes drivable on this map's lanes | Static check per route | No impossible lane sequence; no forbidden turns; no U-turn artefacts | FHWA 2004, p. 50; our `cars lanes` |
| 14 | Insertion | Trip ends and entries | Enter on a usable lane; entry flows within 5%; blocked vehicles counted | SUMO; TfL §7.5.2.1; FHWA 2004, p. 81 |
| 15 | Demand against capacity, by hand | Per-turn modelled capacity against count or assigned flow | Capacity at least the count (TAG); no gateway over capacity (FHWA App. F) | TAG 6.2.3; FHWA 2004, pp. 129-131 |
| 16 | Real congestion map | Contours from the data | A table of real jams, so false ones can be named | Gomes; FHWA 2004, p. 57 |
| 17 | Instrument | Virtual sensor against what the field device does | Same definition; point data isn't link data | FHWA 2004, p. 80; MULTITUDE, p. 84 |
| 18 | Warm-up | First vehicles drive on an empty network | About twice the longest travel time, or simulate from before the peak | MULTITUDE, p. 20 |
| 19 | Target known beforehand | Thresholds written before the run | Set in advance | MULTITUDE, p. 60 |

### 3b. How practitioners know what will happen before they run

- **Capacity by formula.** `c = s·g/C` per signal approach (FHWA 2004, p. 56). HCM as a fallback or cross-check (p. 57).
- **Compare demand with capacity at each point.** Gomes compares ramp flows with nominal capacity at each bottleneck. Where the numbers don't explain the queue, he infers a capacity loss and names a cause (curves, weaving) before running (pp. 11-12).
- **Queue arithmetic.** Delay still in queue at the end of a run is `Q²/(2C)` (FHWA 2004, p. 82).
- **Gateway excess.** `X = (D−C)/C`, then reduce downstream demand in proportion, before running (pp. 129-131).
- **Expected speeds at 50%.** Should reflect free flow (p. 51).
- **Parallel analytic models.** TfL builds deterministic signal models with microsimulation in the same project. Modelled saturation flow can be checked against the validated deterministic model (§2.1.4, §7.5.2.2).
- **Analytic network capacity.** The method of cuts gives a street's capacity and fundamental diagram from block lengths and signal settings, and an upper bound for networks. It was compared with San Francisco and Yokohama (Daganzo and Geroliminis 2008, abstract). Later work extends it to irregular networks (Tilg et al. 2022, search result only).
- **Sensitivity beforehand.** SF: small input changes can cause big network changes once links run on the back side of the flow curve, so expect it.

**Inference: applying this to our district today, by hand, with no run.** Report 23 gives 268-317 of about 8,300 edges over 900 veh/lane/h at full demand, and 27-37 over 1,500, some at 2,447 on one-lane tertiary roads.

| Case | Lane capacity at `s` = 1,800 | Demand per lane at 100% | At 50% |
|---|---:|---:|---:|
| Green share 0.31 (Hamburg median, report 23) | 558 | over 900 on 268-317 edges | over 450 on those; over 750 on 27-37 |
| Green share 0.43 (generator median) | 774 | same | same |

This is a rough bound. It assumes the edge ends at a signal and that lanes are used evenly, and not every edge does or is.

So at 100%, up to about 300 edges would be over capacity before any queue spills. These can't be real routes at real flows: in reality drivers wouldn't choose them, or the flow couldn't arrive. At 50%, the 27-37 worst edges are at or over signal capacity at typical green, up to about 1,220 per lane. That means **FHWA's expectation of no congestion at 50% can't be assumed for these routes**, and congestion at 50% can't be read as a coding error alone. Report 23's own static count, using each signal's program, agrees in kind: 16 of 2,050 loaded lanes over capacity at 50%. Retiming cut that to 2, yet running cars rose (22,685 against 19,825), so static signal capacity isn't the whole limit. FHWA's named suspects at this test are lane distribution and headways (p. 47).

---

## 4. When a network locks

### 4a. What they do, in order

1. **Stop comparing with data.** There is little to gain from statistics while a model is gridlocked, and an unconverged assignment isn't comparable (E-C153, p. 37). Same point in FHWA 2019 ch. 5.
2. **Drop demand uniformly until it runs free.** See where unusual congestion still forms. That usually finds coding errors (E-C153, p. 37). Use a flat profile first (p. 44). Coding errors tend to produce more congestion, not less (p. 36).
3. **Find the origin, not the queue.** Scroll to the first link where outflow falls and density rises (SF). Look at the few minutes before a persistent queue, and don't confuse a secondary queue with its cause (FHWA 2004, p. 80). Lausanne: analyse the OD of vehicles in the gridlock, since it often hides route and assignment problems or a badly modelled junction (Bert §3.1). Our `cars jam` and `cars why` do this.
4. **Check expectations in the field.** The first suspect is the analyst's own belief about what's real (FHWA 2004, p. 47).
5. **Fix input errors, not capacities.** Raising capacity indiscriminately can remove real bottlenecks and invalidate scenarios (E-C153, p. 37).
6. **Fix lane changing with look-back.** Gomes tuned each off-ramp individually so lane-change zones don't overlap (Table 2). SF traced gridlock to last-minute lane changes at US-101 diverges and adjusted behaviour there. TxDOT warns the default distance may be too late. FHWA treats warning-sign position as coding (2004, p. 47, note 4).
7. **Temporarily remove false bottlenecks.** Raise capacity by link so the run can go on. Reverse before finishing (FHWA 2004, p. 57). Keep it logged.
8. **Reach equilibrium from below.** Barcelona: start at 2% of demand and add 2% per iteration, because a jam gives no useful travel costs. Aimsun: turn off queue propagation in early iterations of incremental assignment to find feasible paths, with reduced demand (Aimsun DUE docs). Des Moines: bound habitual travel times at five times free flow, because unreal jams cause overcorrection (§4.1).
9. **Check route cost.** Hierarchy penalties (Bert §4.1, SF). Lausanne also warns about flip-flop oscillation from cost update timing.
10. **Start earlier.** Advance the simulation start so congestion can evolve gradually (E-C153, p. 37).
11. **Only then shorten a valve for what remains**, and only where the effect is small (Gomes, p. 18).

**Known to fail:** raising demand because flows look low when they are low from congestion, called one of the most common errors (E-C153, p. 44). Cutting vehicle length to escape gridlock (SF, report 15). Scaling demand and calling it a result (our Stockholm, report 15).

### 4b. The relief valves

| Tool | Valve | Default | What its source says |
|---|---|---|---|
| **SUMO** | Teleport the front car if stopped at a junction this long, to the next free edge. Records reason: wrong lane, yield, jam, blocked and others | 300 s; off with a negative value | [Docs](https://sumo.dlr.de/docs/Simulation/Why_Vehicles_are_teleporting.html): gridlocks are rather common in congested scenarios. Solve them by improving flow: junction priorities, signal timings or demand. Two vehicles each blocking the other's lane change is listed as a model imperfection |
| **Vissim** | Diffusion: remove a vehicle waiting at the emergency stop position for a lane change. Warning written to the error file | 60 s | [PTV manual](https://cgi.ptvgroup.com/vision-help/VISSIM_2025_ENG/Content/4_BasisdatenSim/FahrverhaltensparameterFahrstreifenwechsel_bearb.htm), default from [Hidas 2004](https://australasiantransportresearchforum.org.au/wp-content/uploads/2022/03/2004_Hidas.pdf) and Gomes. Gomes cut it to 1 s at off-ramps after tuning look-back, and kept 60 s at merges so entering cars weren't evaporated (p. 18) |
| **Aimsun (micro)** | Network Checker. Stationary vehicle detection over a max time: log, stop or delete. Lost vehicle detection: log or delete | Off until enabled; no default stated | [Manual](https://docs.aimsun.com/next/26.0.0/UsersManual/DynamicNetworkChecks.html). Vehicles that miss a turn become "lost" and are [counted separately](https://docs.aimsun.com/next/latest/UsersManual/StatisticalSimulationResults.html) |
| **Aimsun (meso)** | Queue jump: a stuck vehicle jumps to the next section | Fast track feature | Same page |
| **Aimsun DUE** | Queue propagation off in early iterations: infinite storage | Option | Avoids gridlock from poor early paths, per its [manual](https://docs.aimsun.com/next/latest/UsersManual/DynamicScenariosAndExperiments.html) |
| **MATSim** | `stuckTime`: move the front vehicle across a junction despite full storage | 10 s in the book and source (a Sioux Falls config comment says 30) | [Book §4.4](https://www.matsim.org/files/book/partOne-latest.pdf): added to resolve gridlocks. Unpublished tests found longer times less realistic against counts. A [source comment](https://matsim.org/doxygen/_q_sim_config_group_8java_source.html) calls forcing vehicles forward probably the better choice over removing them |
| **VISUM DUE** | Minimum capacity factor for gridlock conditions, to avoid artificial gridlock | Set to 0 in that study | [Swedish SAMPERS report](https://www.transportportal.se/swopec/CTS2014-10.pdf), Figure 12 |

I did not get Paramics, TransModeler, CORSIM or Dynameq settings. Their manuals were not reachable.

**What practice says about valves.**
- TfL: audit error files for removed vehicles, cars reaching link ends still looking for routes, and latent demand. Ideally none; small non-critical files are acceptable (§7.5.2.7).
- FHWA: blocked vehicles at entries aren't in delay statistics. Extend the network or add their delay back (2004, pp. 81-82).
- Barcelona reports about 5% teleports as a sanity check, and says the metric matches nothing real.
- **I found no guideline with a numeric limit on removed vehicles.**

**Inference.**
- Report 15 and the gate require teleports off. No published project I read has run a city that way. Keep the rule as the final test. Report that no comparison exists.
- A valve stands in for things real drivers do that a rule-bound model doesn't: creep and squeeze past, wave someone in, give up, take the next street. MATSim's unpublished finding points the same way: strict storage may fit counts worse.
- The honest replacement is behaviour, not teleport. A driver who can't make a lane change **misses the turn and reroutes**. Aimsun already treats these as "lost" and counts them; the I-210 model has rules for vehicles that miss turns. Report 23's "giving-up rule" is this idea. It needs its own measured rate.
- **A valve is also a microscope.** One run with a 300 s valve, logging reason, place and time for every event, gives a map of all seeds in the day at once. Teleports-off gives one seed per round, because the first jam hides the others. That doesn't change the gate. It makes the hill climb faster. Use it for finding faults, never for scores.
- Our 10% demand comes from a model with the valve on. Default MATSim moves vehicles across junctions after a few seconds whatever the storage. I could not open Berlin v6.4's config to confirm its value. The flows of 2,447 veh/lane/h on one lane are what you'd expect from plans that never had to fit this map's lanes.

---

## 5. What our project skipped or did out of order

Against [report 23](../23-berlin-2019-first-gate.md) and [STATUS](../STATUS.md). Verdicts are mine.

| Step | What guidance asks | What we did | Verdict |
|---|---|---|---|
| 0. Scope | Tight scope, all congestion inside, time step fixed | 49 km² district chosen by sensor count. dt 1 for map work, because only Krauss has capacity in band there. Human and physics tried at dt 1 and 0.5. Boundary: free exits, suspected artefact at Karl-Liebknecht-Straße | **Time step not fixed. Boundary unresolved** |
| 0. Site | Report 15: must have real signal plans, counts, speeds on the same dates | No Berlin window has plans, so signals "don't separate them" | **Skipped own rule** |
| 1. Data | Clean, simultaneous, filtered | 94 QC sites, weather checked in part (16 May's 12.7 mm is still in the floor), probes, noise floor | **Ahead of practice.** Roadworks and events unchecked |
| 1. Signals | Real plans (Des Moines, SF, Fremont, TfL all do this) | 487 netconvert controllers, **INVENTED**, offset 0 | **Missing input.** FHWA 2019 ch. 2: if data is short, collect more or reconsider |
| 2. Behaviour on disaggregate data | Each model fitted and held out first | Done in reports 05, 18, 21, 25, but **physical and human drivers were then put on a city while failing isolated capacity**: physics 18-25% low at the time, human 1,500 | **Out of order.** STATUS now has this as path item 1 |
| 3. Bottleneck table | Real jams listed before coding | Not made. Top-20 scored afterward: 28% against a floor of 80% | **Skipped. Biggest gap** |
| 4. Layers | All coded before checking | Bus lanes, turn lanes and buses not in while 50% runs | **Out of order** |
| 5a. Software test by hand | Single link and junction | Step 3 scenes do it, one seed each, dt 1 | Partial |
| 5b. Input audit | Connectivity, lanes, turns | Good: 540 short edges, 172 lane differences, U-turns, log kept | **Matches practice.** U-turns is FHWA's own example |
| 5c. Near-empty trace | Follow single vehicles, find slowdowns | Started at 10%, not near-empty. **The 10% day runs below real 06:00 speeds on every class: motorway 68 vs 75, arterial 34 vs 37, local 28 vs 35 km/h (−9%, −8%, −20%, my arithmetic on report 23's table).** Report 23 cautions that probe and sim speeds aren't quite the same measure and were not closed against detectors. Noted, not chased | **Skipped.** A failed or unproven test left open. If real, low free speed feeds routes |
| 5d. 50% | Flat, reduced, stable, then peak | Peaked demand, 50% copies of a 10% sample, on routes never fitted to this map | **Ran too early.** See 3b |
| 6. Capacity at real bottlenecks | Measured discharge per site; global then local | Generic bands in generic scenes, no site-level measure. **Hourly loops with speeds could give it**, using hours where a queue is present (FHWA accepts 15 min to 1 h) | **Skipped.** Bands aren't calibration |
| 6. False bottlenecks | Temporary capacity to let the run go on | Not used. Teleports off is the only mode | **Not used** |
| 7. Routes | After capacity | `cars-assign` ran at 50%: 25 iterations, gap 33% to 11%, stalled, −7% | **Out of order.** Stepped run queued; Barcelona's 2% steps support it |
| 7. Demand | Prior plus strong penalty, TAG limits, independent check | v6.4 fitted to same stations, 100% from ten copies ±150 s (**invented**). Site R² 0.31, volume on wrong classes | Prior reasonable. **Copies untested as a cause** |
| 8. System | After routes | Scored for diagnosis only, and labelled so | Fine |
| 9. Validation | Independent | Frozen sites, locked months, no peek | **Ahead of practice** |
| Log | Logbook, one change at a time | `rounds.csv` | **Matches practice** |
| Runs | Stable, several seeds | Mostly one seed. Report says under 10% means nothing. Seeds chaotic | FHWA 2019 reads the chaos itself as a finding. **A single number isn't a usable score here** |
| Ladder | Segment, sub-network, network (Kunde via Toledo ch. 6). Driver on one section (Des Moines). Corridor (Gomes) | Scene to 49 km² in one jump. **No corridor rung** | **Skipped** |

**Fair credit.** Our noise floor, locked data and tuning log go further than any guideline. FHWA 2019's between-day error is the only comparable idea I found. Report 23 labels every input honestly. STATUS has already moved driver capacity to the top. The order is the problem, not the honesty.

**What I think follows (inference), in order. None of this has been run.**

1. **Freeze dt.** Everything below depends on it.
2. **Make the bottleneck table** for the district from probes and loops: place, onset, extent, clearance, likely cause, all with noise from the 8 days. Measure queue discharge at loop sites with queues present.
3. **Fix what's measured in scenes**: free speed by class, first closing probes against detectors, then the 8-20% gap if it survives. Discharge, give-way, and a new lane-change-under-pressure scene with look-back sweeps. Then re-test the engine lane swap against that baseline.
4. **Add a corridor rung.** One arterial with a real jam, with known timing. Options: Berlin B1/B5 has published cycle lengths (Senate answer, report 23). Hamburg has live signal state and detectors per lane on a 50-light district (report 26), which could give saturation flow directly. Calibrate there before the district.
5. **Static assignment on this map's turn capacities, before any micro run**, so hand arithmetic shows no lane over capacity at the test demand. Then near-empty, then flat reduced, then 50% peak, then 100%.
6. **One logged valve run** to map all seeds at once, kept out of scores.
7. **Independent draws for 100%** instead of ten copies, if the plans allow it. Otherwise measure what the copies do.

---

## 6. Ten sentences

1. Fix what you can measure before you tune what you can't, because a tuned parameter will quietly absorb any input error beneath it.
2. List the real bottlenecks, with times and causes, before you write the model, or you won't know which of its jams are false.
3. Capacity comes first because it decides where queues form, queues decide delay, delay decides routes, and routes decide flows.
4. Measure capacity only where a real queue discharges, and in the model force a queue the same way, since a count without a queue upstream measures demand.
5. Test each behaviour rule alone in a scene you can compute by hand, then a corridor with a real jam, and a city last; errors you can't trace at city scale are the normal case.
6. At very low demand nothing may slow without a reason, and at reduced flat demand nothing may queue without one; if it does, you have a coding or lane-distribution error, unless simple arithmetic already says the demand doesn't fit.
7. When seeds disagree strongly, the model is unstable and that is the result to explain, usually coding errors or lane changes in contention, so do not fit anything to it.
8. Don't compare a locked model with data, and don't reach equilibrium from a jam; lower the demand, find the first link whose outflow falls, fix inputs, and approach full demand from below.
9. Low flow in a congested model usually means too much demand or too little capacity, not too little demand, and matching flows proves little because many wrong demands and parameters fit the same counts.
10. A relief valve hides what real drivers do and your model doesn't, so count every use by place and reason, and validate only on data never used for fitting, against how much two real days differ.

---

## 7. Where reports 15, 20 and 22 are wrong or shallow

**Report 15**
- **Bottlenecks are at step 8. That's the wrong end.** The report's own text cites FHWA's DTA guide as bottlenecks first. FHWA 2004, FHWA 2019 and Gomes all start from them. They belong before map checking (as a list) and at the capacity step (as measured discharge).
- **"FHWA says supply, then routes, then OD last" merges two documents.** FHWA 2004 has no OD step: it assumes demand is checked at entries. "OD last resort" is the 2013 DTA guide. MULTITUDE puts demand before driver parameters. Report 15 reports no disagreement.
- **The 50% test isn't Fremont's.** It's in FHWA since 2004 (pp. 46-47), with a very low-demand stage before it that report 15 replaces by 10%.
- **Step 2 is too strong.** "Anything left is a coding error" goes beyond FHWA, which says usually and may. E-C153 adds flat demand first. On unconstrained routes the claim is false (3b).
- **The summary sentence reverses its own recipe.** It says map and capacity, then 50%. FHWA and the recipe say 50% before capacity calibration.
- **TAG numbers are read as targets.** TAG 3.2.2 and 3.3.2 say they aren't, and that meeting them proves no fitness. I read the May 2026 version.
- **Missing: engine verification as a step**, and any "before you run" arithmetic, and a corridor rung (it goes from isolated tests to a 20-50 km² district).
- **It asks for real signal plans, but gives no fallback when a city has none.** Report 23 then took Berlin anyway, and the gap was only labelled.

**Report 20**
- **"Do not build any of this before demand and signals are fixed" clashes with capacity-first.** Friction is capacity. Practice handles it at the capacity step as a measured factor without simulating people: SF used HCM reduction factors from pedestrian counts at 50 sites, applied by area type. FHWA uses link factors for parking and driveways (p. 61). TfL uses reduced-speed areas at stop lines (§7.4.2.4). **Inference:** a measured area factor is a cheap first version of rows 1 and 2. The mechanisms can come later, tested in isolated scenes where network lock-up doesn't matter.
- **The ranking is by mechanism, not by measured gap.** Practice starts from where measured discharge disagrees with the model.
- **It has no row for look-back distance.** Lane-change look-back and warning position are named coding items in FHWA, Gomes, TxDOT and TfL. The nearest row is 17, which defers lane use to report 18. In our engine `lc.wgsl:899` computes look-ahead from a per-type formula, not per decision point, and I found no test of it against a weave or a short road.
- **Row 6's fix (dt) is listed as quick, but it comes first** and invalidates anything calibrated before it.

**Report 22**
- **It scores, it doesn't construct.** N17 and C5 measure bottlenecks after a run. Nothing makes the real list an input.
- **V1 "teleports 0" isn't flagged as beyond all practice.** No comparison exists.
- **It notes Hollander and Liu, Barceló and Toledo unopened.** Toledo's framework and chapter 6 of Daamen are now read here and support its levels. Hollander and Liu and Barceló are still not.
- **It keeps "seeds aren't days" as open.** FHWA 2019 goes further: seed variation is second order, and days are first order. The cluster and representative-day machinery is a tested answer, though report 22 rightly prefers all pairs.
- **Its rule 2, "fix map, signals, demand before behaviour tuning", cites FHWA for an order FHWA doesn't give.** That order is MULTITUDE's. FHWA tunes capacity parameters before routes, with demand presumed checked. The report doesn't say they differ.

**Status board**
- **"Capacity in band" isn't calibration.** Bands come from handbooks. FHWA and TfL ask for measured values at the sites that matter, within 10%. TfL's RR67 note shows handbook values can be 15% over London's real flows (report 20).
- **"Cars running at 07:30" mixes causes and is chaotic on one seed.** Number of primary seeds by place would say more.

---

## 8. What each source says, and what I could not read

### Read, with what they say that matters

**[FHWA Traffic Analysis Toolbox III, 2004](https://ops.fhwa.dot.gov/trafficanalysistools/tat_vol3/Vol3_Guidelines.pdf)** (Dowling, Skabardonis, Alexiadis; FHWA-HRT-04-040). Read: introduction; ch. 1 most; ch. 2-5 in full; ch. 6 sections on runs, bias and animation; Appendix A; Appendix F.
- Calibration assumes the behaviour models are sound (p. 54). The developer has validated the software (p. 4).
- Parameters are correlated; you can circle forever; split them into certain and uncertain, keep the uncertain few (p. 54).
- Capacity, then routes, then system; each global then local (p. 55).
- Calibrating to all counts is the old way. Focus on critical counts at bottlenecks first (p. 55, note 9).
- Six programs differed 13% on existing speeds and 69% on forecast speeds (Bloomberg et al., p. 53).
- Most micro parameters can't be observed directly (p. 96).
- Runs can vary by 25% (pp. 77, 105).
- Key event to look for: persistent queues (p. 80).

**[FHWA 2019 update](https://ops.fhwa.dot.gov/publications/fhwahop18036/index.htm).** Read ch. 3-6 from a local copy; ch. 2 through a fetched summary.
- Travel conditions by cluster analysis; one real representative day each; envelope from all days; four criteria.
- Variation is mainly external: demand, incidents, weather.
- Calibrate bottleneck throughput first, then travel demand and route parameters ("one successful strategy").
- Large seed spread may mean coding errors or unresolved contention. Unstable runs must not be used.

**[FHWA DTA guide, 2013, §8](https://ops.fhwa.dot.gov/publications/fhwahop13015/sec8.htm).** Fetched summary. Bottlenecks are the focus; traffic flow, then routes, then OD as a last resort; validation should ideally cover a system change. No gridlock section; no numeric thresholds.

**[TRB E-C153, DTA primer, 2011](https://onlinepubs.trb.org/onlinepubs/circulars/ec153.pdf).** Read pp. 36-38 and 44-45. Qualitative stage before quantitative. Reduced demand as diagnosis; flat demand first; capacity increases can remove real bottlenecks; low flows may mean congestion.

**[MULTITUDE: Traffic Simulation, Case for Guidelines, 2014](https://publications.jrc.ec.europa.eu/repository/bitstream/JRC88526/2014_multitude_guidelines_on-line.pdf)** (Antoniou, Barceló, Brackstone et al.; EUR 26534). Read main ch. 1-5 and Appendix A Issues 1, 6, 7 (first part), 9, 10, 11. Not read: Issues 2-5, 8, 12 appendix text, Appendices B and C.
- 19% of practitioners don't calibrate; of the rest only 55% use guidelines (p. 9). Roughly two thirds of studies use no data (Wagner, p. 71).
- Guidelines copy each other, so repetition isn't proof (p. 13). GEH came from planning models (p. 13).
- It proposes no order of its own past the four stages in Issue 6.
- Tweaking driver behaviour is tempting because getting OD and geometry right is the hard part; get the situation right first (p. 72). Authors ask if we over-calibrate junctions to cover for poor behaviour models, parameterising the place rather than the situation (p. 73).
- Full automation of calibration would be unwise (p. 28).
- Sensitivity analysis should first be done by developers (p. 27). As developers, this is on us.

**[Toledo et al., ch. 6 of Daamen et al. 2014](https://toledo.net.technion.ac.il/files/2016/01/CRC_MULTITUDE_TrafficSimulationDraft_15.pdf).** Author's draft, 18 pp. Read §6.3.2, 6.4, 6.5. It is a literature review, not case studies with numbers.
- Aggregate data can't identify individual models; results don't transfer well (§6.3.2).
- Sequential supply then demand ignores interaction; simultaneous is more efficient (§6.5).
- Optimisers are mostly tested on small networks and small parameter sets (§6.3.2).
- If initial parameter ranges miss the real value, calibration can't succeed (Park and Qi, §6.3.2).
- Kunde 2002: segment, sub-network, network (§6.3.1).

**[Toledo, Koutsopoulos, Ben-Akiva framework](https://tristanconference.org/system/tristan-v/website/pdf/abstract_00172.pdf)** and **[Des Moines, Jha et al.](https://wctrs-society.com/wp-content/uploads/abstracts/istanbul/1363.pdf).** Read through §3 and §4.1. Two phases: disaggregate estimation, then aggregate calibration. In Des Moines, driver parameters were fit on one I-235 section whose OD follows from counts, and then fixed, while OD, routes and habitual times iterate. Signal data was among the hardest to get, spread over 20 counties. Over 80% of OD pairs under 1 veh/h, carrying 15% of demand.

**[TfL Traffic Modelling Guidelines v4, 2021](https://content.tfl.gov.uk/traffic-modelling-guidelines.pdf).** Read §2.4, §7.4 most, §7.5. Pages in text. Junction and network models for scheme approval, audited in stages. Time step fixed. Change seed often during calibration to avoid fitting to one. Saturated models are more variable, because small changes amplify.

**[DfT TAG Unit M3.1, May 2026](https://www.gov.uk/transport-analysis-guidance-tag).** Read §3.1-3.4, tables 1-5, 5.4.1-5.4.5, 6.2.2-6.2.9. It is for assignment models, not micro. Check structure and connectivity first, then link attributes, then junction detail (6.2.9). Do not let matrix estimation move far from the prior to reach targets.

**[Trafikverket handbook 2014](https://bransch.trafikverket.se/contentassets/32ce05ecc3ac458bb8ecb802e8e2da54/handbok_for_kapacitetsanalys_med_hjalp_av_simulering.pdf).** Read §2.7.1 and §2.7.3 parts. Follows FHWA's order: decide which parameters matter and which are certain, set bounds, verify entry, then capacity, routes, fine-tuning. Keep a calibration logbook. One parameter at a time. Lists goodness-of-fit advice based on Hollander and Liu.

**[Gomes, May, Horowitz 2004](https://horowitz.me.berkeley.edu/Publications_files/All_papers_numbered/Gomes_may_horowitz_PATH_report04.pdf)** (PATH, I-210 West). Read abstract, §9, §11-13. Best written-up corridor. Defaults gave the blockage at the last off-ramps. Fixes in order: look-back per ramp, diffusion at off-ramps only, CC0 and CC4/5 globally, CC1 at two curves. Composite data, so qualitative targets. Manual iteration preferred to search because of run time and sense.

**[Fremont, Cabannes et al. 2022](https://bayen.berkeley.edu/sites/default/files/creating_calibrating_conference.pdf).** Read in full, excluding references. Order: fix network and demand; scale to entries with no simulation; static OD with a large prior penalty; choose route model; sensitivity 35 to 10; genetic algorithm. No reproducible way to create accurate demand exists (p. 7). Not good enough for the city's engineers at flow nRMSE 47% (p. 22).

**[San Francisco DTA, SFCTA 2012](https://sfcta.org/sites/default/files/2019-03/SFDTAFinalCalibrationandValidationReport.pdf).** Read the calibration process section; not the appendices. Quality inputs, measure what's measurable, avoid changing speed and capacity arbitrarily, avoid OD estimation, keep a log of runs. Software version changes results significantly.

**[Lausanne, Bert, Torday, Dumont 2005](https://www.strc.ch/2005/Bert.pdf).** Read to §4.2. 100 km², 16,006 sections, 148 signals, 61,594 veh/h in the rush hour, moderate congestion, Aimsun. Turn coding at a multi-lane roundabout can change flows by a factor of 2. Chose 40% guided and 20% free-flow-path vehicles.

**[Barcelona SUMO 2022](https://doi.org/10.3390/ijgi11010024).** Read assignment and tuning sections. See report 15.

**[Calibration Illusion 2026](https://arxiv.org/pdf/2608.19642)** (working paper). Read §3.1, the passage on manual dependence, and §8. Parameter interactions grow with scale. 10% changes to parameters usually excluded could more than double speed-field MAPE. Stop-and-go wave reproduction fails at large scale.

**[Treiber and Kesting 2013, calibration](https://arxiv.org/pdf/1403.4990)**, **[2010, spatiotemporal](https://arxiv.org/pdf/1008.1639)**, **[Treiber and Kanagaraj, integration](https://arxiv.org/abs/1403.4881)**. Read conclusions and method summaries. Note: the file `treiber2013.txt` in `validation-lit` is the integration paper, not the 2013 book.

**Docs:** [SUMO teleports](https://sumo.dlr.de/docs/Simulation/Why_Vehicles_are_teleporting.html), [Aimsun network checks](https://docs.aimsun.com/next/26.0.0/UsersManual/DynamicNetworkChecks.html), [TxDOT 13.5.3](https://www.txdot.gov/manuals/des/tsp/chapter-13-microsimulation-analysis/13-5-calibration/13-5-3-calibration-parameters-and-best-practices.html), PTV Vissim lane-change help and Hidas ATRF (local copies in `cars-data/truth/practice/opus-20261101/`), MATSim book §4.4 (same folder).

**[UC Berkeley, Zhang and Ma, Part 1](https://escholarship.org/uc/item/3hh8f7nz).** Read Table 7 only.

**Scanned only, numbers taken from report 15:** [I-210 Connected Corridors](https://escholarship.org/content/qt1xw8q5j1/qt1xw8q5j1.pdf) (I read the boundary and permanent-action passages: temporary speed reductions at the edge when congestion lies outside the model; forced turns and destination changes used only after route-cost changes failed). [Mobiliti](https://escholarship.org/content/qt43r1046c/qt43r1046c.pdf) (mesoscopic, with storage constraints and no lane changing or car following, so it says little about micro construction).

### Not reached

| Source | What happened | What I used instead |
|---|---|---|
| **Barceló (ed.) 2010** | Springer returns a bot page. No open copy found. RePEc and INFORMS show no text | Barceló co-authored MULTITUDE; the RePEc abstract says ch. 1 covers DTA and calibration. **Nothing here rests on the book** |
| **Hollander and Liu 2008** | Springer blocked, USP copy requires login, ResearchGate 403, no OA in OpenAlex | Secondary only: Toledo ch. 6 §6.3.2, Trafikverket §2.7.3, MULTITUDE Appendix C. **Its reported view: too few repetitions; mean values waste the stochastic output; avoid error measures where signs cancel.** Treat as second hand |
| **Daamen et al. 2014, other chapters** | Only ch. 6 draft found on an author's page; siblings 404 | MULTITUDE report covers related ground |
| **Treiber and Kesting book** | Only [the table of contents](https://traffic-flow-dynamics.org/res/TrafficFlowDynamics_TableOfContents_2ndEdition.pdf). Ch. 17 is Calibration and Validation, ch. 16 Stability, §11.4 fundamental diagram | Their open papers |
| **FGSV Hinweise 2006** | Paid; only the [TRID record](https://trid.trb.org/View/940230) | MULTITUDE p. 12: project workflow, RMSE, no thresholds, replication formula |
| **Austroads AP-R286/06, RMS NSW, HA 2007** | Not reachable from here | MULTITUDE's description only |
| **Chu et al. 2003** | IEEE only | [Abstract through UCI](https://its.uci.edu/research_products/conference-paper-a-calibration-procedure-for-microscopic-traffic-simulation): multi-stage procedure on a southern California corridor |
| **Toledo et al. 2003, Stockholm; Toledo and Koutsopoulos 2004** | Sage | Report 15's record; Toledo framework paper |
| **Other city write-ups** | Only Lausanne is new here | Report 15's dead ends stand |
| **Dowling et al. 2004 (TRR)** | Not found | Toledo ch. 6's summary, same content as FHWA |
| **Berlin v6.4 MATSim config** | Path 404, not in search | Defaults from MATSim source; flagged as unconfirmed |
| **Paramics, TransModeler, Dynameq, CORSIM valves** | No manual reachable | Not stated |

Downloads are in `/tmp/foundations-a/`, each in its own folder, parsed as text with poppler and read as data. Nothing downloaded was executed.
