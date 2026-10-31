# Beyond built-in SUMO AV models: coordinated vehicle behaviors

Research checked 2026-10-31. This is an implementation-oriented literature survey, not a claim that the proposed controllers have been built or validated. Published gains below are scenario-specific. Where only existence/method could be verified, the numerical evidence gap is stated explicitly instead of inventing a gain. GPU mappings and suggested parameter sweeps are proposals.

## 1. What the bachelor thesis actually studied

Read locally: [README](/home/erikf/projects/personal/thesis-src/bachelor/README.md), `/home/erikf/projects/personal/thesis-src/bachelor/config/vtypes.xml`, and the PDF *A Microscopic Traffic Simulation Study of Autonomous Vehicle Penetration Rate Effects on Traffic Flow Across Different Control Models and Scenarios*, by Erik Frankling and Adam Wallén. Extracted with `nix shell nixpkgs#poppler-utils -c pdftotext -layout <PDF> /tmp/cars-thesis.txt`.

The README names ring, Bologna, I-80 VSL and a two-signal GLOSA scenario; five tiers are Krauß, IDM, ACC, CACC and GLOSA. It defaults to penetration increments .05 and three seeds. PDF §3.3 describes a **4 km ring with 200 vehicles**, .1 s steps, 4,000 s runtime, 2,000 s warm-up and a 60 s max-speed disturbance. This differs from both physical ring experiments discussed in the validation document.

| Configured type | Actual mechanism/settings | Consequence for interpretation |
|---|---|---|
| human | IDM; accel 2.6, decel 2.0 m/s²; tau 1 s, minGap 2.5 m, speedDev .1 | A parameterized human abstraction, not a reaction/perception simulator. |
| av_basic / av_krauss | IDM / deterministic Krauß; accel 3.5, decel 2.2; tau .6 s, minGap 1.5 m, no speed dispersion | Flow improvements mix shorter following gaps, homogeneity and higher acceleration. |
| av_acc | SUMO ACC, accel 1 m/s², tau 1.5 s, minGap 2 m, max speed 33.33 m/s | More conservative longitudinal envelope than the IDM AV. |
| av_cacc | SUMO CACC, accel 1 m/s², tau .6 s, minGap 1 m; headwayTimeACC 1.5 s | Short-headway connected following with fallback; not intersection negotiation. Verify exact SUMO-version interpretation of generic parameters. |
| av_glosa | Human IDM envelope plus GLOSA device, 300 m range | Signal arrival advice is orthogonal to car-following capability. |

PDF §1.3 and §5 limitations explicitly exclude safety evaluation, non-passenger vehicles and mixtures of different AV tiers. It acknowledges model/envelope confounding and only three random seeds. Reservation management appears in its related work; it was not implemented. Thus the desired next step is a **different coordination layer**, not just another lower `tau`.

Use common acceleration/braking/length envelopes in the new comparison, then vary one capability at a time. Include the thesis configuration as a historical replication, labeled separately.

## 2. Literature: evidence, gains and GPU mapping

### Intersection reservations, FCFS, auctions and humans

**Dresner & Stone (2008), [A Multiagent Approach to Autonomous Intersection Management](https://www.cs.utexas.edu/~aim/papers/JAIR08-dresner.pdf), JAIR 31, 591–656.** Custom microscopic simulation tests reservations against signals/stop signs, including turning and human-compatible extensions. The manager tests space–time tile occupancy for a requested arrival trajectory, allowing multiple compatible movements simultaneously. The paper contains demand-dependent delay curves; no single transferable percent gain is asserted here. This is simulation evidence, not road deployment. FCFS means priority by request ordering, not that every direction is served one car at a time.

GPU: precompute swept cell/time masks for each turning path and candidate entry time/speed. Each vehicle writes request candidates; a junction workgroup sorts by request time plus deterministic ID and accepts mutually compatible masks. Vehicles read committed grants next stage. Different junctions run in parallel; arbitration inside each junction is coordinated. Grid occupancy must cover vehicle length, width and continuous motion, including tails after entry.

**Vasirani & Ossowski (2012), [A Market-Inspired Approach for Intersection Management in Urban Road Traffic Networks](https://nlp.aaai.org/Papers/JAIR/Vol43/JAIR4316.pdf), JAIR 43, 621–659.** Reservation allocation uses combinatorial auctions and network traffic assignment. Section 5.2 reports about **30% less delay for high bidders than low bidders**, while warning that auction priority alone increases population-average delay. This is a distributional advantage, not a network throughput improvement. An auction changes priority and fairness, not collision physics.

GPU: replace FCFS priority with bid/social-cost score, test a bounded set of compatible request bundles in parallel, choose the highest feasible objective. Deterministic tie-breaking and waiting-time aging prevent nondeterminism/starvation. Charge accounting stays separate from physical feasibility. Report mean delay, p99 delay and delay by bid/income group alongside throughput.

**Sharon & Stone (2017), [A Protocol for Mixed Autonomous and Human-Operated Vehicles at Intersections](https://www.cs.utexas.edu/~pstone/Papers/bib2html-links/ABMUS17-Sharon.pdf).** H-AIM experiments show AV delay benefits even at **1%** penetration, whereas the earlier AIM mixed-traffic approach offered little/no improvement below roughly **90%**. This is not a 1% network capacity gain. The [2022 Hybrid-AIM technical report](https://arxiv.org/abs/2204.07704) documents the simulator. Do not confuse Hybrid-AIM with unrelated “Heuristic AIM” papers.

GPU: reserve sensed human trajectories conservatively, retain human-readable signal permissions, and grant AV slots only if compatible with those permissions and occupancy predictions. An AV must not cause a following human to interpret an AV-only permission as a green signal. Unknown intentions get reachable occupancy tubes, not exact future trajectories.

### Slot-based and signal-free intersections

**Tachet et al. (2016), [Revisiting Street Intersections Using Slot-Based Systems](https://doi.org/10.1371/journal.pone.0149607), PLOS ONE 11, e0149607.** Generalized queueing analysis compares FIXED signals, FAIR FCFS slots and BATCH platoon service. BATCH asymptotically approaches **2× service capacity**; FAIR capacity is only marginally above FIXED, although both reduce delay. The analyzed switching setup is about **1.47 s**, around five times shorter than typical signal setup in that comparison. This is chiefly analytical capacity/delay evidence, not a SUMO city field validation.

GPU: batch compatible requests by approach/turn and downstream space; optimize bounded group size and waiting limit. A reservation is a sequence of resource occupancies, not a single timestamp. Discretize candidate slots, then refine/check continuous trajectories. Several different directions can cross at once where swept paths are disjoint; intersecting paths may share the junction only at different occupancy times.

Start with 500 m approaches, 50 km/h, 5–10 s reservation horizon, .05–.1 s physics and .1 s slot grid (all proposed). Compare optimized signals, FCFS, batching and auction priority at identical demands. Sweep turning shares and asymmetry: an easy all-straight intersection exaggerates benefits.

### Platoons and string-stable CACC

**Lioris, Pedarsani, Tascikaraoglu & Varaiya (2017), [Platoons of connected vehicles can double throughput in urban roads](https://doi.org/10.1016/j.trc.2017.01.023), TRC 77, 292–305; [preprint](https://arxiv.org/abs/1511.00775).** Queueing analysis and PointQ discrete-event simulation of **16 intersections/73 links** investigate 2–3× saturation flows. Proposed platoon crossing headways around **.75 s at 45 mph**, or .7 s at 30 mph, support roughly **4,800 veh/h per movement**. Network gains follow the imposed discharge-rate scaling; they do not independently demonstrate that real vehicles can achieve it safely.

GPU: platoon IDs and member order, leader command broadcast, feedforward follower control, compressed intraplatoon gaps and larger interplatoon gaps. At signals, plan launch jointly; verify downstream storage for the whole batch. Record formation overhead, breaks and cut-ins. Do not multiply lane capacity globally when only a few adjacent pairs are connected.

**Ploeg et al. (2011), [Design and experimental evaluation of cooperative adaptive cruise control](https://doi.org/10.1109/ITSC.2011.6082981); [author PDF](https://vandewouw.dc.tue.nl/ITSC2011_Ploeg.pdf).** Six passenger vehicles demonstrated string-stable following at **.7 s**; the analysis suggests below .5 s with improved communication latency. This is stronger physical evidence for short headways than a pure microsimulation assumption, but does not prove a city-scale capacity multiplier.

GPU: feedback on gap/relative speed plus communicated predecessor acceleration feedforward, with actuator lag and message delays represented as history buffers. Check frequency-domain gains and packet-loss degradation. Shorter gaps require a feasible braking envelope, not only linear stability.

Derived illustration, not a published result: at speed v, front-to-front equilibrium spacing is L+s₀+vh. For v=30 m/s, L=5 m, s₀=2 m, h=.7 s gives q=3600v/(L+s₀+vh)≈3,857 veh/h; h=1.5 s gives ≈2,077. Therefore 3600/h alone overestimates finite-length vehicle capacity. Also distinguish time gap from measured front-to-front departure headway.

### Connected cruise control and multi-anticipation

**Ge & Orosz (2014), [Dynamics of connected vehicle systems with delayed acceleration feedback](https://doi.org/10.1016/j.trc.2014.04.014), TRC 46, 46–64**, and **Ge & Orosz (2015), [Optimized connected cruise control with time delay](https://public.websites.umich.edu/~orosz/articles/TDS_2015_Jin.pdf)** analyze/select feedback from multiple predecessors, including human-driven vehicles and communication delay. The gain is a larger stable operating region, not a verified universal throughput percentage. Some feedback choices destabilize the string.

**Treiber, Kesting & Helbing (2006), [Delays, inaccuracies and anticipation in microscopic traffic models](https://doi.org/10.1016/j.physa.2005.05.001)** shows how spatial/temporal anticipation can counter destabilization from reaction delay and estimation errors. Its method combines delayed observations and multiple leaders; it is not unlimited knowledge of their future decisions.

GPU: fixed-width neighbor arrays (e.g. 1, 2, 4, 8 predecessors, proposed ablation); gather past states with time stamps, apply weighted relative-speed/acceleration feedback or multi-leader IDM terms. O(NK) for bounded K; no all-to-all vehicle matrix. A connected human may broadcast state but cannot promise to obey a control command. Compare transfer gains, latency margin and RMS acceleration before making a capacity claim.

### Wave damping, learned policies and mixed autonomy

**Stern et al. (2018), [Dissipation of stop-and-go waves via control of autonomous vehicles: Field experiments](https://doi.org/10.1016/j.trc.2018.02.005); [full preprint](https://arxiv.org/html/1705.01693v1).** One AV among 21–22 vehicles on a 260 m ring damped waves. Reported improvements include **up to 40% less estimated fuel consumption and 15% greater throughput**. Experiment A contrasts velocity SD **3.31→.64 m/s** in selected wave/autonomy intervals. Fuel was modeled from trajectories; these are not universal savings or randomized city evidence.

GPU: FollowerStopper or PI-with-saturation per controlled vehicle, using local gap/speed and an estimated target traffic speed; no junction scheduler needed. Test on/off with matched disturbance, plus density/controller-target sweeps.

**Wu et al., [Flow: A Modular Learning Framework for Mixed Autonomy Traffic](https://arxiv.org/abs/1710.05465), final T-RO version (2021), [DOI](https://doi.org/10.1109/TRO.2021.3087314).** SUMO-based RL experiments cover rings and other modular networks. Final-version abstract reports **up to 57% higher system-level velocity with 4–7% AV adoption**. Earlier drafts report different headline figures; specify the version. This is simulation performance, sensitive to human model, reward and observation assumptions.

GPU: batch identical small neural networks over AV observations; store recurrent state separately if used; safety-filter outputs. Train with randomized demand/driver/communication parameters and evaluate held-out geometries. Avoid claims based solely on a policy trained and tested against the same deterministic human model.

**Talebpour & Mahmassani (2016), [Influence of connected and autonomous vehicles on traffic flow stability and throughput](https://doi.org/10.1016/j.trc.2016.07.007), TRC 71, 143–163; [institutional record](https://experts.illinois.edu/en/publications/influence-of-connected-and-autonomous-vehicles-on-traffic-flow-st/).** Distinguishes human, connected and automated classes using microscopic simulation and stability analysis over penetration. Connectivity and automation have different effects. No single verified numerical capacity multiplier is reproduced here; it depends on penetration, distributions and control law. Companion [Mahmassani (2016), *Autonomous Vehicles and Connected Vehicle Systems: Flow and Operations Considerations*](https://doi.org/10.1287/trsc.2016.0712) describes small effects at low shares and larger ones as adoption grows.

GPU: separate equipment, automation, cooperative authority and current communication health into independent fields. Sample class ordering; do not use a network penetration scalar as the following controller. For random independent placement, fraction of adjacent AV–AV pairs is p²: at p=.1 only .01 of all pairs qualify, although .1 of AVs have an AV leader. Deliberate platoon sorting changes this calculation and consumes maneuver capacity.

### Lane-free traffic

**Papageorgiou et al. (2021), [Lane-Free Artificial-Fluid Concept for Vehicular Traffic](https://doi.org/10.1109/JPROC.2020.3042681), Proceedings of the IEEE 109(2), 114–121; [preprint](https://arxiv.org/abs/1905.11642).** Proposes lane-free movement plus communicating “nudges” from behind and illustrates it in preliminary simulations. Capacity can vary continuously with road width. A generally established percent capacity gain is not supplied by the verified abstract and should not be invented.

GPU: two-dimensional continuous positions, bicycle or bounded lateral dynamics, spatial bins and bounded neighbor lists, repulsive boundary/vehicle potentials plus desired-speed terms. Nudging is a command/incentive to move, not physical pushing. Enforce nonintersecting swept vehicle footprints. A lane-ID simulator needs a new geometry/dynamics layer for this tier; removing lane markings in the renderer is insufficient. Use physically segregated fully cooperative corridors first; unknown humans remain lane-based with larger uncertainty regions.

### Cooperative merging, coordinated lane changes and eco-driving

**Rios-Torres & Malikopoulos (2017), [Automated and Cooperative Vehicle Merging at Highway On-Ramps](https://doi.org/10.1109/TITS.2016.2587582); [full paper](https://ids-lab.net/wp-content/uploads/2023/07/Paper2-18z6vpl.pdf).** Optimal-control trajectory simulations reported fuel reductions **52.7%/48.1%** and travel-time reductions **7.1%/13.5%** in two cases versus a baseline where secondary-road vehicles stop and wait for mainline vehicles. At 29 m/s an example required a **1,200 m control zone**, a material feasibility limitation. These are not comparisons with an already optimized cooperative merge.

GPU: allocate merge ordering/time using virtual conflict-point positions, then solve bounded acceleration trajectories independently in parallel. Replan only after committed ordering updates. Project proposed trajectories through speed, acceleration, jerk and rear-end constraints; infeasible requests wait or use conventional merging. Precompute analytic segment coefficients where applicable.

**Wang et al. (2016), [Model predictive control–based cooperative lane change strategy for improving traffic flow](https://doi.org/10.1177/1687814016632992).** Uses multi-vehicle cooperative MPC rather than just ego gap acceptance. **Chen et al. (2021), [Cooperation Method of Connected and Automated Vehicles at Unsignalized Intersections: Lane Changing and Arrival Scheduling](https://arxiv.org/abs/2109.14175)** combines formation/path assignment and graph-based scheduling. Both papers exist; a specific percentage benefit could not be reliably extracted in this review, so neither is used as a quantitative promise.

GPU: candidate lane-change bundles involve ego, target-lane leader/follower and affected origin-lane follower. Score trajectory candidates in parallel; conflict graph arbitration commits disjoint bundles. Resolve swaps, reciprocal yielding and two vehicles claiming the same gap. Longitudinal acceleration plans for all bundle participants must be committed atomically; successful ego motion alone is not sufficient.

**Katsaros, Kernchen, Dianati & Rieck (2011), [Performance study of a Green Light Optimized Speed Advisory (GLOSA) application using an integrated cooperative ITS simulation platform](https://doi.org/10.1109/VNC.2011.6117131).** Paper identity and SUMO/cooperative-ITS method verified through [Warwick’s author record](https://wrap.warwick.ac.uk/view/author_id/350678.html). Often quoted 7% fuel and 80% stop-time reductions were not checked against an accessible primary full text here and are **not adopted as verified gains**. Eco-driving evidence with directly verified numbers is the merging study above and Stern’s trajectory-based fuel estimates.

GPU: broadcast SPaT and queue-tail estimates; each vehicle evaluates bounded cruise/acceleration candidates over several signal windows using a consistent energy model. Include speed, comfort and queue constraints. GLOSA can reduce stops without increasing throughput; optimize and report energy, stops, journey time and throughput separately. Integrate wheel power/drag/rolling resistance and powertrain efficiency consistently; the sum of squared accelerations is a comfort/control surrogate, not liters of fuel.

## 3. Shared-buffer execution design

All vehicles stepping at once requires explicit transaction stages; naive simultaneous writes to a reservation table create schedule-order artifacts.

1. **Snapshot:** structure-of-arrays `x,y,v,a,lane,route,leaderId,type,platoonId,capabilities`; immutable state S(t). Stable IDs survive compaction.
2. **Perception/communications:** build sorted lane lists or spatial bins; construct timestamped neighbor observations. Separate true state from sensed/message state. Delay, drop, range and clock error apply before controller reads.
3. **Propose:** each vehicle writes acceleration and candidate maneuvers/arrival windows to its own output slots. Fixed-capacity request buffers include overflow counters and safe deferral.
4. **Arbitrate:** junction/merge/lane-change workgroups process requests with deterministic priority. Evaluate candidates in parallel, but commit a mutually consistent accepted set. Centralized means authority per conflict region, not one GPU thread controlling the city.
5. **Publish:** grants contain plan/version, validity interval, participating IDs and fallback. Whole bundles commit or none do. Use global dispatch boundaries where workgroup barriers cannot synchronize the device.
6. **Actuate:** each vehicle consumes only committed commands, applies lag and bounded safety projection, then writes S(t+Δt). Decide explicitly whether new grants act this tick after a dispatch boundary or next tick; include that delay in validation.
7. **Check:** continuous/swept footprint overlap, downstream storage, braking feasibility, slot conformance, starvation and conservation. Double-buffer swap and record diagnostics.

Distributed alternative: vehicles exchange candidate plans and use a consistent priority/consensus protocol within a conflict region. Shared memory may make the simulation cheap, but it must not silently give the modeled vehicles instantaneous global knowledge. Compare centralized and distributed controllers with the same communication budget, prediction horizon and feasible set. Local optimization can be GPU parallel; globally optimal multi-junction scheduling is combinatorial. Use bounded candidate searches, receding horizons and corridor decomposition; report optimality only where proved.

Proposed planning cadence 5–10 Hz with physics 10–20 Hz; test .05/.1/.2 s and communication latency 0/50/100/200 ms, packet loss 0/1/5/10%, including burst loss. A slot time quantum and integration step are separate parameters. Test clocks ±10–100 ms and localization ±.1–1 m as sensitivity assumptions, not claims about hardware.

## 4. Nine behavior tiers

These are capability combinations, not SAE automation levels. Preserve orthogonal flags so an eco-driving CACC vehicle can also negotiate slots.

| Tier | Capability | Information and authority | Useful experiment |
|---|---|---|---|
| 0 | Calibrated heterogeneous humans | Delayed/noisy sensing; normal signal/priority rules | Empirical baseline, FD, start-up loss, waves |
| 1 | Precise unconnected AV | Sensor-only following, same physical envelope | Isolate homogeneity and reaction effects |
| 2 | Anticipatory/CCC AV | Several communicated predecessors; no promise they obey | Wave damping versus latency and leader mix |
| 3 | String-stable CACC | Verified connected leader acceleration and health; fallback ACC | .7 s starting headway hypothesis, dropout tests |
| 4 | Managed platoons | Membership/leader authority, joint launch, merge/split | Signal discharge and formation cost |
| 5 | Signal-aware eco-driving | SPaT, queue estimates, energy objective | Stops/energy, matched throughput |
| 6 | Hybrid reservation AV | Junction authority plus sensed humans and signal compatibility | 1–100% penetration; all-user delay and fairness |
| 7 | Fully coordinated corridor/network | Slot batching, merge and lane-change contracts; finite storage | Crossing ballet, demand frontier, robustness |
| 8 | Lane-free cooperative fleet | Continuous 2D control and verified domain membership | Width–capacity curves in segregated roads |

## 5. Penetration, safety margins and the “superhuman” experiment

The desired ideal case is legitimate as a clearly labeled counterfactual: perfect state, perfect communication, exact actuation, known braking, no human/pedestrian intrusions. Remove **human reaction and uncertainty allowances** there; retain nonoverlap, finite vehicle size, acceleration limits and finite storage. Never let high average penetration remove the margin behind a particular unknown leader.

A practical simulation envelope uses gap ≥ s₀ + vτ_effective + max(0, v_f²/(2b_f) − v_l²/(2b_l)) plus state/actuation uncertainty, with a carefully derived discrete-time bound. This expression is a design sketch, not a proved controller. `τ_effective` includes communication age, controller period and actuation lag. A car being connected does not mean its maximum braking is known.

* **Low p:** retain signals and conventional priority. Wave damping/eco-driving may help without adjacent AVs. No global headway reduction.
* **Intermediate p:** only verified, healthy connected pairs use shorter gaps. Humans interrupt platoons; unknown turns reserve broader junction occupancy. Reserve space for the platoon tail and human followers. Separate connected humans from controllable AVs.
* **High p:** reservation scheduling can dominate in a controlled zone, but every unconnected human/pedestrian/cyclist still needs a compatible protected interval or sensed reachable region. Zone eligibility is local, not the fleet percentage.
* **All verified cooperative vehicles:** allow concurrent nonconflicting paths and fine time interleaving; reserve exit storage. Compare finite uncertainty against a perfect-information upper bound. Relaxing uncertainty does not make two vehicle footprints fit in the same place/time.
* **Communication failure:** use expiring grants and pre-agreed completion/stop behavior. Existing committed occupancy remains reserved until safely cleared; never erase an occupied slot on timeout. Open following gaps before reduced authority becomes unsafe; abrupt fallback cannot create space instantly.

## 6. Implementation and experiment order

First validate human baseline using [the validation protocol](validation-and-phenomena.md). Implement tiers 2–3 and a Stern-style controller next: they are local, O(NK), and test parallel update semantics. Add single-junction FCFS, then batching, then H-AIM humans. Add downstream-storage-aware coordination before multi-junction claims. Auctions and lane-free control are later research axes, not prerequisites.

Use p=0,.01,.05,.1,.25,.5,.75,.9,1 with 20+ independent runs; compare random placement against deliberate platooning. Use demand sweeps through saturation, not just fixed under-capacity flows. Report system/user-group mean and p95/p99 delay, throughput, stopped time, energy, jerk, conflict/overlap counts, failed reservations, fairness and external insertion queues. Keep total demanded trips identical. Include conventional optimized signal control and identical physical envelopes as baselines.

For each controller run four ablations: local sensing only; truthful delayed communication; perfect communication; perfect-information centralized upper bound. Add human cut-ins and packet bursts. Report the last stable demand level and confidence intervals rather than a single dramatic animation. A promising first demo is four directions crossing with visible time–space reservations, followed by a human vehicle entering and the controller expanding protection around it.

## Evidence boundary

The cited papers' existence was checked using primary author/publisher/institutional records. Primary numerical results are provided where retrievable; explicit gaps remain for universal auction, CCC, multi-anticipation, lane-free and cooperative-lane-change percentage gains. Those methods often report stability regions or case-specific curves rather than a portable gain. Extract their exact case tables before claiming replication. This document supplies a buildable research design while keeping such gaps visible.
