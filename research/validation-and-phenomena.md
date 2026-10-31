# Validating a microscopic simulator and reproducing traffic phenomena

Research checked 2026-10-31. Scope: a new synchronous, GPU-oriented simulator compared with SUMO and observations. All scenario dimensions and acceptance tolerances below are **proposed engineering choices**, unless explicitly attributed. Published ranges are plausibility checks, not universal constants. No experiments were run for this report.

## 1. What validation must establish

Use three independent questions: (1) does the implementation solve its intended equations and enforce geometry correctly? (verification); (2) does it reproduce the chosen SUMO configuration statistically? (cross-simulator equivalence); (3) does it predict held-out real observations? (empirical validation). Agreement with SUMO alone establishes neither reality nor the validity of hypothetical AV controllers.

Freeze SUMO version/commit, integration method, step length, action-step length, car-following/lane-change parameters, road geometry including internal junction links, signal programs, vehicle dimensions, departure rules, routes and random inputs. Supply identical departure schedules rather than merely the same integer seed: random-number consumption differs between engines. Separate car-following, lane changes, junction decisions and route choice before combining them. Account for all requested departures, including vehicles waiting outside a full network. Disable or separately count teleportation and collision recovery.

Calibrate on one day/demand regime/driver sample; validate on another, including congestion and recovery. Match observation definitions: detector flow versus arrivals, point speed versus space-mean speed, passenger-car units versus vehicles, completed-trip time versus censored trips. Use independent runs or day/block bootstrap intervals, not millions of correlated vehicle samples treated as independent.

### Metrics and their interpretation

Here M is modeled and O observed/reference, over n matched observations.

| Metric | Definition and application | Threshold interpretation |
|---|---|---|
| GEH | sqrt(2(M−O)^2/(M+O)), conventionally hourly veh/h; both zero → zero | GEH <5 on ≥85% of counts is a familiar operational criterion; 5–10 investigate, >10 explain. It is not a hypothesis-test p-value. Do not apply the same threshold to arbitrary interval counts. |
| RMSNE | sqrt(mean(((M−O)/O)^2)) | No universal standard cutoff. Exclude/stratify zero denominators explicitly; use normalized RMSE by mean O for sparse flows. Proposed gates below. |
| Theil U1 | RMSE(M,O)/(RMS(M)+RMS(O)) | 0 is perfect; no universal traffic cutoff. Name U1 explicitly: U2 instead compares prediction errors to a naive forecast. Report bias/variance/covariance decomposition as diagnostics. |
| FD | q(k), v(k), capacity, critical density, jam density, backward branch slope | Fit triangular and smooth alternatives to held-out bins; bootstrap fitted parameters. R² alone can hide wrong congested branches and aggregation bias. |
| MFD | lane-length weighted network flow and density; also production P=ΣqL and accumulation N=ΣkL | Compare peak production, critical accumulation, loading/recovery separately, density heterogeneity and trip completions. Production and network exit flow are different. |
| KS | D=sup|F_M−F_O|, e.g. route/time-stratified travel-time CDFs | Report D and block-bootstrap uncertainty. p>0.05 does not establish equivalence; large data reject tiny irrelevant differences. |
| Wasserstein W1 | integral |F_M−F_O| dt for one-dimensional travel times | Units are seconds. Normalize by median reference time for interpretable effect size; keep absolute tail errors too. |
| Trajectory errors | speed, position, bumper gap, acceleration and jerk RMSE; response lag | Align initial states and leader forcing. Long chaotic platoon trajectories should be assessed by distributions and growth rates, not pointwise equality forever. |

The GEH convention and broader calibration workflow appear in [FHWA Traffic Analysis Toolbox, Volume III](https://ops.fhwa.dot.gov/trafficanalysistools/tat_vol3/). Agency requirements differ: [ATAP model-development guidance](https://www.atap.gov.au/tools-techniques/travel-demand-modelling/5-model-development) gives examples with different GEH coverage. Thus 85% is a useful benchmark, not a universal standard. For empirical trajectory methods see [Treiber & Kesting, *Microscopic Calibration and Validation of Car-Following Models—A Systematic Approach* (2014)](https://arxiv.org/abs/1403.4990) and [Kesting & Treiber, *Calibrating Car-Following Models using Trajectory Data* (2008)](https://arxiv.org/abs/0803.4063).

### What has actually been validated in and around SUMO

| Work, verified link | Measurements/comparison | What it establishes and what it does not |
|---|---|---|
| Brockfeld, Kühne & Wagner (2004), [*Calibration and Validation of Microscopic Traffic Flow Models*, TRR 1876, 62–70](https://doi.org/10.3141/1876-07) | Ten models, Japanese test-track DGPS leader/follower data; measured leader fed to models, fitted follower headway time series. Calibration errors 12–17%, validation 17–22%, exceptional transfer errors up to 60%. | Foundational model-validation evidence, not a certificate for every modern SUMO release or junction model. Driver differences exceeded model differences. |
| SUMO [San Pablo Dam calibration tutorial](https://sumo.dlr.de/daily/userdoc/Tutorials/Calibration/San_Pablo_Dam.html) | Real-world vehicle passage observations; calibrate SUMO-Krauß parameters and evaluate passage-time errors with a validation script. | A reproducible calibration example. The tutorial is documentation, not a peer-reviewed independent validation study. |
| Erdmann, Rummel & Wagner (2017), [*SUMO and the German Handbook for the Dimensioning of Highways (HBS)*](https://elib.dlr.de/112657/) | Compares one HBS scenario against SUMO; handbook performance benchmark. | Analytical/engineering cross-check, not direct proof against field trajectories. Repository record and abstract verified; no unsupported numerical accuracy claim made here. |
| Salles, Kaufmann & Reuss (2020), [*Extending the Intelligent Driver Model in SUMO and Verifying the Drive Off Trajectories with Aerial Measurements*](https://eclipse.dev/sumo/documents/2020/SUMO2020_paper_28.pdf) | Drone-observed urban drive-off speed/acceleration trajectories compared with IDM variants and Krauß; extended IDM better captures acceleration shape. | Direct evidence for this manoeuvre; cannot be generalized to lane changing or a city. See also the maintained [EIDM documentation](https://sumo.dlr.de/docs/Car-Following-Models/EIDM.html). |
| *Enhancing SUMO simulator for simulation based testing and validation of autonomous vehicles* (2021), [paper](https://arxiv.org/abs/2109.11620) | Calibrates IDM to highway and urban naturalistic trajectories and samples parameter distributions. | Supports heterogeneous background-driver calibration, rather than assuming default parameters represent everyone. |

The standard [Alvarez Lopez et al. (2018), *Microscopic Traffic Simulation using SUMO*](https://doi.org/10.1109/ITSC.2018.8569938) describes the platform; cite individual calibration studies for specific realism claims. Likewise [Erdmann (2015), *SUMO’s Lane-changing model*](https://elib.dlr.de/102254/) explains behavior architecture, not blanket empirical validation.

## 2. Phenomena, numeric anchors and minimal experiments

Default proposed experiment settings: passenger cars 5 m, standstill gap 2–2.5 m; Δt=0.1 s, convergence runs at 0.05 and 0.2 s; 20 independent parameter/noise seeds; 600 s warm-up plus 1,800 s measurement unless stated. Human reaction/noise must be explicit; a perfectly homogeneous deterministic equilibrium will not spontaneously perturb itself. Test reasonable parameter *regions*, not a single tuned animation.

| Phenomenon and published anchor | Minimal proposed scenario and demand | Measurements/plots | Video treatment |
|---|---|---|---|
| Freeway capacity: ideal HCM benchmark 2,400 pc/h/lane at ≥70 mph; subtract 50 per 5 mph lower free-flow speed ([FHWA](https://ops.fhwa.dot.gov/publications/fhwahop19029/ch4.htm)). Practical flows depend on trucks, weaving and weather. | 5 km, one lane, 100–120 km/h, open downstream; demand staircase 1,000–2,600 veh/h in 200 increments, 15 min each; Δt=.1 s. | Discharge versus offered demand, q–k–v; breakdown probability by demand. | Demand counter rises until a moving queue suddenly appears. |
| Signal saturation: commonly 1,500–2,000 passenger cars/h/lane; ideal 1,900. Start-up loss about 2 s; total phase loss often 4 s ([FHWA signal timing manual, ch.3](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter3.htm)). | 500 m approach, 40 prequeued cars; 60 s cycle, 30 s green, 900–1,200 veh/h; 30 cycles, .1 s. | Stop-line departure headway by queue index, cumulative departures, effective green and loss. | Highlight first four cars, then a metronome of steady discharge. |
| Jam storage: published calibrated example 230 veh/mile ≈143 veh/km; explored bounds 140–250 veh/mile ≈87–155 veh/km ([VTRC 22-R7](https://vtrc.virginia.gov/media/vtrc/vtrc-pdf/vtrc-pdf/22-R7.pdf)). Geometry gives 133–143 veh/km for 5 m cars and 2–2.5 m gaps, a derived value. | 1 km dead-end queue behind red; fill at 1,800 veh/h until storage exhausted, .1 s. | Measured stopped gaps, vehicle count per usable lane length; no storage on junction polygons. | Fill a ruler-marked road; show upstream insertion queue once full. |
| Backward waves near −15 km/h; published oscillation range −10 to −20 km/h ([Zheng et al. 2011](https://www.sciencedirect.com/science/article/pii/S0191261511000622)). | 5 km near-capacity lane, 30 s brake pulse at midpoint, 1,800–2,200 veh/h, .1 s. | Time–space speed field; fit front slope; check shock relation w=(q₂−q₁)/(k₂−k₁). | Track one vehicle downstream and the red jam front upstream simultaneously. |
| Capacity drop: congested discharge below prebreakdown flow; empirical A4 lane-drop example reports higher discharge states 6,040 and 5,700 veh/h ([Yuan et al., *Capacity drop: a comparison between stop-and-go wave and standing queue at lane-drop bottleneck*](https://doi.org/10.1080/21680566.2016.1245163)). Those are state flows, not a universal percentage range. | 6 km two-to-one lane drop; demand ramp across capacity then hold; .1 s, 1 h. | Define prebreakdown reference and sustained postbreakdown discharge; report 100(q_pre−q_post)/q_pre. Explore a **proposed** 5–20% drop envelope, not a mandated law. | Queue forms while the downstream counter visibly slows. |
| Stop-and-go periods: field observations show several-minute cycles ([Mauch & Cassidy, *Freeway Traffic Oscillations: Observations and Predictions*, 2002](https://escholarship.org/uc/item/89c3h1vv)). No universal period. | 10 km congested freeway with weak bottleneck, demand 105% of measured capacity; 1 h, .1 s. | Speed autocorrelation and PSD; proposed exploratory 2–10 min search band; wave speeds and amplitudes. | Compress an hour into a minute; pair roadway with scrolling time–space plot. |
| Sugiyama et al. (2008): 22 cars on 230 m ring, instructed around 30 km/h; jam emerges without bottleneck ([NJP 10, 033001](https://doi.org/10.1088/1367-2630/10/3/033001)). | Exact ring/vehicle count; heterogeneous human following, .1 s, 10 min; equal initial spacing plus small seeded perturbations. | Unwrapped trajectories, speed variance, backward jam speed, stop fractions. | Overhead circle and unrolled strip; show jam persisting with no obstacle. |
| Stern et al. (2018): 260 m ring, 21–22 vehicles, one controlled vehicle (<5%); compares velocity, braking and estimated fuel ([TRC 89, 205–221](https://doi.org/10.1016/j.trc.2018.02.005); [author preprint](https://arxiv.org/abs/1705.01693)). | 260 m, 22 cars; establish waves then switch one controller on/off; .1 s, 15 min. | Before/after velocity SD, braking events, mean speed; same fuel model in both engines. | Color the single AV; synchronized switch reveals waves dissolving. |
| String instability: downstream leader disturbances grow toward following vehicles; anticipation can stabilize ([Treiber, Kesting & Helbing 2006](https://doi.org/10.1016/j.physa.2005.05.001)). | 20-car platoon on 5 km road; 15 m/s leader with ±2 m/s sine, periods 10–120 s; .1 s. | Frequency gain |V_i/V_0|, phase lag, peak/RMS growth by index. | Leader brake pulse grows into a full stop at the rear. |
| Spillback and gridlock: finite storage and cyclic blocking are essential mechanisms; network performance falls with accumulation ([Daganzo 2007, *Urban gridlock: Macroscopic modeling and mitigation approaches*](https://doi.org/10.1016/j.trb.2006.03.001)). | Spillback: two signals 150 m apart, downstream 20% green, 1,200 veh/h. Gridlock: four 150 m links in a directed cycle, cross-inflows ramped until full; .1 s. | Queue fronts, blocked-green time, junction occupancy, exits and conservation. | Green light with no movement, then four-way blocking domino effect. |
| MFD: Geroliminis & Daganzo (2008), Yokohama empirical aggregate relation ([TRB 42, 759–770](https://doi.org/10.1016/j.trb.2008.02.002)). No transferable numerical critical density. | 5×5 grid, 250 m blocks, 50 km/h, 60 s signals; ramp boundary arrivals 200→900→200 veh/h/entry over 2 h; .1 s. | Weighted q–k, P–N, mean speed, exits, spatial density variance. | Heatmap city beside moving dot on MFD, crest then collapse. |
| MFD hysteresis: loading and recovery differ because congestion distribution changes ([Gayah & Daganzo 2011, *Clockwise hysteresis loops in the MFD*](https://escholarship.org/uc/item/2x98k1x2)). Loop shape/direction depends on conditions. | Same grid; spatially concentrated demand pulse versus uniform pulse; 30 min load, 30 min drain, .1 s. | Color P–N by time; match N bins on each branch; plot heterogeneity and signed loop area. | Two city snapshots at identical N but different throughput. |

Do not force every car-following model to display every phenomenon: stochastic Krauß and IDM stability regions differ. First match a specific SUMO configuration; separately determine whether a calibrated model family reproduces observations. A model can match capacity yet get wave propagation or storage wrong.

## 3. A concrete acceptance protocol

All numeric gates in this section are **proposed project thresholds**, except the identified GEH convention. They are deliberately stricter for engine equivalence than for human prediction. Pre-register primary outcomes and equivalence margins before tuning.

### Level A: one vehicle and platoons

Fixtures: free acceleration 0→30 m/s, bounded braking, stationary obstacle, prescribed leader braking, sine sweeps, cut-in, stop-line approach; 20-car platoon. Start with deterministic identical model equations at .1 s; repeat .05 s and .2 s with reaction time held fixed in seconds.

* Deterministic short 60 s replay: speed RMSE ≤0.2 m/s, position RMSE ≤1 m, gap RMSE ≤1 m, reaction lag difference ≤.1 s; bounded acceleration error ≤.2 m/s² away from switching instants. These detect integration/update-order defects without demanding bit equality.
* Halving Δt changes mean discharge/travel time <1%; otherwise keep refining before judging behavior.
* Platoon transfer gains differ ≤10% over tested frequencies; agree on stable/unstable classification except within 5% of gain=1, which is labeled indeterminate. Compare stochastic ensemble speed/gap CDFs with D≤.10 and normalized W1≤.05.
* Hard invariants: zero overlaps under the test's feasible braking assumptions; zero negative speed; exact vehicle conservation; no unreported teleport. Check swept trajectories between timesteps, not only sampled positions. Impossible initial states are separately classified.

### Level B: small-network macroscopic behavior

Use every fixture above, an on-ramp, isolated signal and 5×5 grid; at least 20 paired demand realizations. Begin with 20 and add up to 100 if a primary equivalence interval is too wide. Bootstrap independent runs. Require the 95% CI for the difference to lie entirely within the margin (a conservative equivalence decision), not merely overlap zero.

* Capacity and sustained discharge ±5%; critical density ±10%; jam density ±5%; wave speed ±2 km/h; signal saturation ±5%, start-up lost time ±.5 s. Margins distinguish physically meaningful flow errors from sampling variability.
* Mean route travel time ±5%; p95 ±10%; travel-time KS D≤.10; W1/median≤.05. Queue p95 ±10% or 2 vehicles, whichever larger. Compare completed and unfinished trips; clear the network or report survival curves.
* Hourly flow GEH<5 at ≥85% of detectors plus every designated bottleneck; total entered/exited count difference ≤2%. RMSNE≤.15 for non-sparse count bins; U1≤.10 for speed and travel-time series. These latter limits are design choices.
* Peak MFD production ±5%, critical N ±10%, loading/recovery production within ±10% in populated N bins. Require same congestion mechanism and branch ordering; signed loop area within ±20% only where reference loop exceeds bootstrap noise.
* Capacity-drop difference ≤3 percentage points when the reference exhibits a robust drop; dominant oscillation period ±20% when PSD has a distinct peak. Do not fail a model for an undefined/noisy period.

### Level C: city scale and reality

Freeze an imported city, routing and signal controller; run morning peak with ≥30 min warm-up, ≥2 h demand and a drain period. Validate SUMO and the new engine against the same independent counts/probe times, rather than tuning our output toward SUMO errors. Start 10 independent demand/noise runs and increase to 30 if needed for precision. Use multiple days, including incidents or unusual demand as stress cases, without fitting to them.

* Cross-engine: ≥85% hourly link counts GEH<5, all critical bottlenecks within ±10%; screenline counts ±5%; total completed demand ±2%; network mean travel time ±5%, p95 ±10%, normalized W1≤.10 by major OD/time cohort. Peak production ±5%, critical accumulation ±10%.
* Against reality: provisional travel-time mean ±10%, p95 ±15%, normalized W1≤.10; counts use the operational GEH gate; speed RMSE≤3 m/s on matched 5 min bins. Accept margins only if compatible with sensor error/day-to-day variability. The 17–22% trajectory transfer errors in Brockfeld et al. warn against treating submeter human prediction as an empirical norm.
* Report failures by congestion state, geography, route and vehicle class. No single weighted score may hide blocked roads, wrong bottleneck locations or lost demand. Keep route-choice calibration separate from vehicle dynamics.

Deliver manifest, parameter files, input/output hashes, SUMO version, seeds, exact aggregation definitions, confidence intervals, censoring counts and failures. Performance tests report vehicle-steps/s separately; faster execution never substitutes for these gates.

## 4. Suggested video suite (12)

Each uses a fixed camera and synchronized SUMO/ours panels, identical demand realization, speed colors, time/scale legend and a small metric trace. Label AV demonstrations as interventions, not human-baseline validation.

1. Empty road to freeway breakdown: demand staircase and live discharge counter.
2. Signal queue launch: first four delayed departures versus saturation rhythm.
3. Storage limit: full link and externally queued arrivals.
4. Phantom jam: Sugiyama ring, overhead plus unrolled road.
5. Backward wave versus forward moving car: opposing arrows and measured slope.
6. Brake pulse through a platoon: front mild slowing, rear full stop.
7. One AV dissolves waves: Stern-style switch-on and off, human control replay beside it.
8. Lane drop and capacity drop: identical demand before and after queue activation.
9. Ramp merge: growing disturbances and discharge across penetration levels.
10. Spillback: downstream red blocks an upstream green.
11. Gridlock: four-link cyclic deadlock, then keep-clear policy intervention.
12. City breathes: demand pulse, city heatmap and MFD loading/recovery loop.

## 5. Comparison graph suite (22)

Plot both simulators with run-level 95% intervals; include observations wherever available. Do not hide divergent runs with only an ensemble average.

1. Single-vehicle speed and position replay.
2. Acceleration versus speed, including drive-off observations.
3. Bumper-gap versus relative-speed scatter.
4. Leader/follower braking response and lag.
5. Platoon perturbation amplitude versus vehicle index.
6. String transfer gain versus frequency.
7. Signal departure headway versus queue position.
8. Start-up lost time and saturation-flow distributions.
9. Offered demand versus realized freeway discharge.
10. Flow–density FD with fitted congested/free branches.
11. Speed–density diagram.
12. Breakdown probability versus demand.
13. Pre/post breakdown capacity-drop distributions.
14. Time–space speed fields with front slopes.
15. Speed autocorrelation/PSD and dominant period.
16. Ring speed variance and stop fraction over time.
17. Detector count scatter with GEH contours and residual map.
18. Route/time-stratified travel-time ECDFs.
19. Travel-time QQ plot including p95/p99 and unfinished share.
20. Queue length/blocked-green time and cumulative arrivals/departures.
21. Network MFD with loading/recovery arrows and uncertainty.
22. Production versus accumulation colored by density heterogeneity; paired equal-N city states.

Bibliographic limitation: all named papers were checked against author, publisher or institutional records. Where a full paper was inaccessible, this report deliberately avoids claiming unverified numerical fit errors. The phenomenon recipes and all pass gates are new proposals, not results already obtained.
