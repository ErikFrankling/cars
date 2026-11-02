# D. From demand to lanes: how to get a feasible network load before the first microscopic run

Written 2026-11-02. Reading and static arithmetic only: no simulation, no GPU, nobody contacted. Not committed.

Conventions. "Source:" means the source says it, with URL and section. "Inference:" means I worked it out and no source says it. "Ours:" means our repo. SUMO, or matching any simulator, is not a reference here. The reference is real counts and real probe speeds.

Local copies of downloads are in `/tmp/foundations-d/<name>/` (temporary).

## 1. Short answer

**Go from demand to lanes in layers, and carry only who, where, when and vehicle class across models. Routes, link flows, capacities and free speeds belong to the model that made them.** Between MATSim and the microscopic run there is a missing layer: a macroscopic assignment at 100% demand on our own map, with capacity per movement, scored directly on real counts and probe speeds. It runs in minutes. It needs no GPU. This layer exists in practice (FHWA-HRT-21-082, p. 25), and we skipped it.

**What was wrong with what we did, in order:**

1. **We imported routes as if they were demand.** About 80% of edges over 900 veh/lane/h are MATSim's own flow, and they run at v/c 0.55 on MATSim's capacities. MATSim's capacity on most primary and secondary signal approaches is a floor constant, 0.4 × a car-following maximum, 845 veh/lane/h, whatever the signal and turn. Unsignalled secondary roads get about 2,000.
2. **The overload is computable with no simulation.** Against our map's movement capacities, MATSim's routes overload 311-365 movements at 100%, 11-20 at 50%, 1-6 at 40% and none at 30%. With give-way at the 60% of HBS that our engine measures, the first overloads appear at 30% and none at 20%, which is where the stepped run stops. That's one match, but no simulation went into it.
3. **We used the microscopic simulator as the first assignment tool.** E-C153 and FHWA say a gridlocked run gives no useful statistics and no stable assignment. Our cost table is per edge, can't see a turn's queue, charges spillback to the victim, and copies the last bin after a stall. So report 23's conclusion that "the fault left is not route choice" isn't shown. No test yet has used routes assigned on this map's capacities.

**The pipeline** (section 4): demand table, movement table, static tests, macro assignment, score, boundary flows, vehicles and lanes, micro, feedback. Micro enters only after macro reproduces counts and the rush hour within report 15's Credible bars.

**Cheapest first steps.** (a) **Real flow is a lower bound on real capacity:** test counts against the movement table at tuning sites, no model needed. (b) Run the static screen on both real and engine capacities. (c) Single peak-hour assignment with movement delay. BPR on links won't do: it adds about 1 s at capacity on a 100 m street, where a signal adds 10+ s at any flow, and FHWA's own test found BPR underestimates delay above v/c 0.9.

**What to expect.** Relative gap about 0.1-1% in macro with conflicts, several percent in kinematic wave, 5-15% in micro. Real drivers themselves sit around 5-10% on a shortest-time basis. Stop on stability, not a target. Equilibrium may not exist or be unique with priority junctions (Boyles §11.3).

**Sub-area.** Run the region with detail in the district, then cut. Metered flows go in, time-varying exit capacity comes out, and a queue at a gate is either real (extend the area) or an error (fix it). Test all this in macro first, at the cost of a minute per test rather than a micro campaign.

**Omitted traffic isn't the first-order fix here.** v6.4 already has 48% commercial and goods by km in this district. Cruising is under 1% of km on GPS evidence. Buses are small in km and large in lost kerb capacity.

**Weakest points.** Signals in every number here are invented. Run times are arithmetic. Several primary sources were abstract only (section 6).

## 2. What we did, and what our own files show

Everything in this section is **Ours**. Grades follow report 23: nothing here is a simulation result unless it says so.

**Provenance warning.** An earlier attempt at this job ran static scripts and wrote nothing. Their code and JSON are in `/tmp/foundations-d/scripts/`. I read the code and the JSON. I did not re-run them, and `/tmp` is temporary, so the numbers below are the only copy that will last. All of them read files and do arithmetic; none simulates. Signals in them are the netconvert programs of map m10, which report 23 grades INVENTED.

### 2.1 The routes are MATSim's, so our cut did not cause the overload

`compare_all.json`, our route file against MATSim's own legs, edge by edge over 8,728 shared edges, both ×10:

| Reading | Result |
|---|---|
| Our daily edge flow ÷ MATSim's, p10 / p50 / p90 | 0.96 / 1.00 / 1.03 |
| Edges off by over 30% up, or over 30% down | 2.4%, 0.2% |
| Edges over 900 veh/lane/h at 07, 08, 15, 16 h | 279, 274, 281, 315 |
| ... of which MATSim's own flow already does it | 218, 232, 237, 272 |
| ... of which our U-turn repairs and class graphs added the flow | 54, 31, 38, 35 |
| ... of which our map has fewer lanes than MATSim's | 6, 10, 5, 7 |

So about 80% of the "900+" edges are MATSim's own result on MATSim's own lanes. Report 23's framing, "these routes never met this map's lanes", is right, but the lane mismatch is the small part. The large part is that MATSim's supply lets this flow through.

### 2.2 On MATSim's own capacities, these routes are nearly all feasible

`matsim_vc2.json`, MATSim's link flow per hour against its own `capacity`, 7,530 links in the box:

| Hour | Loaded links | v/c over 1.0 | v/c over 1.0 on `maxInflowUsedInQsim` | Over 900 per lane | Median v/c of those |
|---|---:|---:|---:|---:|---:|
| 07 | 6,900 | 0 | 14 | 210 | 0.55 |
| 08 | 7,052 | 0 | 16 | 234 | 0.55 |
| 15 | 7,114 | 0 | 22 | 231 | 0.55 |
| 16 | 7,129 | 0 | 31 | 267 | 0.55 |

**Inference.** "Over 900 per lane" means nothing to MATSim. Those links run at half of its capacity. MATSim converged to a sensible state on its own supply. Only the supply differs from our map's.

### 2.3 What MATSim's capacity and free speed are, in this district

`ms4.json` and `matsim_more.json`, MATSim's per-lane capacity by class and end of link. "Other" means priority and right-before-left together; floor counts are for priority only, so their totals differ from the first column:

| Class, link ends at | Links | Capacity per lane, p50 | At the code's floor | Free speed ÷ limit, p50 |
|---|---:|---:|---:|---:|
| primary, signal | 200 | 845 | 127 of 181 | 0.51 |
| secondary, signal | 674 | 845 | 341 of 558 | 0.45 |
| tertiary, signal | 300 | 1,097 | 56 of 232 | 0.46 |
| residential, signal | 501 | 1,034 | 22 of 397 | 0.47 |
| primary, other | 260 | 1,690 | 104 of 191 | 0.69 |
| secondary, other | 1,114 | 2,039 | 200 of 839 | 0.69 |
| tertiary, other | 737 | 1,979 | 35 of 502 | 0.79 |
| residential, other | 4,273 | 800 | | 0.85 |

The floor is in `ApplyNetworkParams`: `--capacity-bounds` default `0.4,0.6,0.8` of `capacityEstimate(v)` for signal, right-before-left, priority. `capacityEstimate` is headway 1.2 s plus 7 m ([source](https://github.com/matsim-org/matsim-libs/blob/main/contribs/application/src/main/java/org/matsim/application/prepare/network/params/ApplyNetworkParams.java)). At 50 km/h that is 2,113 veh/h, so 0.4 × 2,113 = 845 and 0.8 × 2,113 = 1,690. Those are the table's medians.

**Inference, and this is the core of "why the routes aren't feasible here":**

1. On most primary and secondary signal approaches, MATSim's capacity isn't a model of that signal. It is a constant, 0.4 of a car-following maximum, the same for every approach and every turn at that speed.
2. At a junction with no signal, a 1-lane secondary road gets about 2,000 veh/h. A link's capacity doesn't change with the flow it has to yield to. The fitted model sees road class and junction type, not the day's major flow. There is no conflict between crossing streams at a MATSim node: the QSim limits outflow per link, not per movement (MATSim book §1.3, see section 3.4).
3. Capacity is per link, so all turns share it. A 1-lane approach with 1,000 veh/h, 20% of them turning left against a heavy opposing flow, is fine in MATSim. On a real lane, the left-turners block the through traffic behind them.

**Free speed: the road hierarchy is gone.** Length-weighted free speed inside the district (`matsim_more.json`), MATSim against limit: primary 25.7 against 41.9 km/h, secondary 27.3 against 46.1, tertiary 27.5 against 41.9, residential 22.6 against 30.3. **In MATSim's free-flow times, a primary road is slower than a tertiary road and only 14% faster than a residential street.** Real probe speeds at 06:00 (report 23) are arterial 37 and local 35 km/h. That table doesn't split primary from tertiary, so I can't give the real ordering. **Inference, not proven:** this free-speed ordering is a plausible direct cause of report 23's "primary −22%, tertiary +26%". Time-only routing on those speeds has no reason to prefer a primary road. Test it in the macro layer (section 4, step 4).

### 2.4 Against this map's movements, these routes are overloaded by about 3×

`movement_screen3.json`. Capacity per movement, not per edge: signal protected `s·f_dir·g/C`, s = 1,640 (report 25's measured median over 17 signal sites, range 1,285-1,895; the design value 1,900 was also run), f_dir 0.85 right, 0.90 left, 0.7 U-turn; permissive and priority by Siegloch with HBS gaps (5.9/3.0 s minor right, 6.5/3.4 s cross, 5.5/2.6 s major left); right-before-left with 4.5/2.5 s (a screen only). Per incoming edge, flows split over allowed lanes to minimise the worst lane's use. Flows are MATSim's routes on m10, timed at departure + 1.3 × free flow.

| Demand | Movements over capacity, 08 h (signal + minor + major) | Same, 16 h | Sum of excess, 08 h, veh/h | Signal approaches whose red-time queue exceeds their storage, 08 h (of 1,679) |
|---:|---:|---:|---:|---:|
| 100% | 186 + 111 + 14 = 311 | 217 + 134 + 14 = 365 | 81,321 | 311 |
| 80% | 92 + 58 + 4 = 154 | 181 | 29,362 | 238 |
| 60% | 22 + 22 = 44 | 51 | 5,419 | 162 |
| 50% | 6 + 5 = 11 | 20 | 1,429 | 131 |
| 40% | 1 | 6 | 126 | 88 |
| 30% | 0 | 0 | 0 | 50 |
| 20% | 0 | 0 | 0 | 27 |
| 10% | 0 | 0 | 0 | 11 |

`movement_screen2.json` tests sensitivity, movements over capacity, 08 h and 16 h:

| Demand | s = 1,640, HBS give-way (above) | s = 1,900, HBS give-way | s = 1,640, give-way at 60% of HBS (about what our engine measures, report 23) |
|---:|---:|---:|---:|
| 100% | 311, 365 | 252, 304 | 379, 445 |
| 50% | 11, 20 | 8, 13 | 29, 35 |
| 30% | 0, 0 | 0, 0 | **1, 3** |
| 20% | 0, 0 | 0, 0 | **0, 0** |

**Inference, three readings.**

1. **Capacity alone predicts the district's feasible load on these routes: about 40% of demand.** Movement overload starts at 40%, is small at 50% and large at 80%. You don't need a microscopic run to know 100% can't work on these routes on these signals.
2. **The stepped run's limit falls where the screen says, once the screen uses the engine's own give-way.** The stepped run holds at 20% and freezes at 30%. With HBS give-way, the screen has no overload at 30%. With give-way at 60% of HBS, which is what report 23 measured for our engine, it has 0 at 20% and 1 to 3 minor movements at 30%. On fixed routes, one overloaded movement grows a queue without limit. One match isn't proof. The stepped run may not have used these exact routes, and I didn't check that. It is still the first time a number computed with no simulation has predicted where this district stops. Separately, at 30% the last column shows 50 approaches where a plain red-time queue doesn't fit on the approach. Those are places where blockage starts before capacity runs out, which agrees with report C's seeds and report 23's "cars blocked abreast". **A feasibility test needs a capacity test and a storage test, on the engine's capacities as well as the real ones.**
3. **This is why starting assignment in the micro stalls.** At 100% the excess, summed over movements, is 81,000 to 104,000 veh/h on routes that were never asked about those movements. The first micro day is therefore in a jam, whichever iteration count you choose.

The screen also finds coding suspects with no run at all. Its worst movements at 100%: Bebelplatz at 54× (capacity about 7 veh/h), a motorway link at 42× (capacity about 1 veh/h), and Karl-Liebknecht-Straße at 15× on a primary approach, a movement coded as yielding across a merged cluster. Karl-Liebknecht-Straße is also in the screen's list at 50%, and report 23 names it as the worst jam cluster. **Inference:** a primary road or motorway link with single-digit capacity is more likely wrong priority coding in a joined junction than real traffic. Those are map fixes, found statically.

### 2.5 How our assignment measures cost

`crates/cars-assign/src/costs.rs`, `CostTable::from_day`: per edge and 300 s bin, `cost = ff + q / rate`, where `q` is cumulative-in minus cumulative-out, and `rate = max(measured outflow, 0.25 × peak outflow of that edge that day)`. Costs after a stall copy the last bin to the end of the day. `route.rs` searches an edge graph with those per-edge costs. `Supply` has no signal, turn or movement field; `nominal_capacity` is `lanes × min(3600/(1 + 7/v), 2400)`, flagged in the code as deliberately optimistic, and used for cut checks only.

**Inference, what this implies:**

- **A turn-level bottleneck is invisible to route choice.** One edge has one cost, whatever you do at its end. If left-turners queue and through traffic doesn't, the table charges both the same. Or the reverse: a car turning right at a jammed through-movement sees the queue only if it's in that queue.
- **Spillback reads as the victim's own delay.** An edge held by a queue from downstream has a low `left` count, so its peak falls and its cost rises. Route choice then avoids the victim, not the cause, and the cause's cost rises only as far as its own queue. In a jam the cap is whatever the jam let through.
- **In a stalled day, all later bins hold the stall's value.** So the "time" in time-dependent costs is lost for the rest of that day. 24 of 25 iterations stalled around 10:25 in report 23's run, so roughly the second half of the day never got fresh feedback in any of them.
- **The cost is correct bookkeeping, and the fix isn't here.** This estimator is reasonable near equilibrium in free-ish traffic. It is the wrong instrument to start from a jam. That's a statement about where to use it (section 4, step 8), not a request to rewrite it.

### 2.6 What the demand contains

`matsim_more.json`, vehicle-km on the district's links by MATSim subpopulation, total 5.37 M km a day (×10): Berlin residents 46.0%, small-scale commercial 31.9%, goods 14.9% (of which 8.3 points by truck, 6.6 by car), Brandenburg residents 6.1%, long-distance freight 1.1%.

**So v6.4 already holds commercial and goods traffic, 48% of its vehicle-km in this district.** "Demand models omit commercial traffic" is not our gap here. Our gap may be the reverse (section 3.8). Report 15's item 8 and report 16's item 9 describe Stockholm and BeST, not this scenario.

## 3. Sources: what they say

How much I read is marked: **read** (the named pages), **abstract** (abstract or catalogue record only), **snippet** (a search result reports it), **not opened**. Anything else is my own inference and says so.

### 3.1 TRB Circular E-C153, *Dynamic Traffic Assignment: A Primer* (Chiu et al. 2011)

[PDF](https://onlinepubs.trb.org/onlinepubs/circulars/ec153.pdf). **Read:** pp. 11-12, 21, 26, 34, 36-38, 44.

- **Relative gap** is the standard convergence measure. There is no recommended threshold. Gap rises with realism and with congestion, "as a result, it is difficult to recommend specific thresholds". What matters is that it is "relatively stable when the DTA run is terminated". It tends to rise for later departures (Characterizing a DTA Solution, p. 34).
- **Gridlock in early runs.** Coding errors usually produce more congestion, not less. Spillback engulfs cars that don't contribute to the original queue, and separate queues merge. In that state "not much is gained in computing statistical measures" against data (pp. 36-37).
- **What to do about it (p. 37):** find the initial bottlenecks; fix input errors that cause unrealistic capacity reductions; keep capacities realistic, because bottlenecks may also come from "unrealistic O-D demand inputs or route choice models", and raising capacities indiscriminately can remove real bottlenecks. Start the simulation earlier. Run "with correct network and control setting but with a uniformly reduced O-D demand level", and watch where unusual congestion still forms.
- **Stability first.** A gridlocked assignment "will often not converge to a stable solution", and comparing it with data is of questionable value. The purpose of the qualitative stage is a solution that is stable, free of gridlock and resembles real congestion (p. 37).
- **Loading profile (p. 44).** A time-varying profile "will inevitably generate more congestion than a flat (static) demand". Start with a flat matrix, scaled down, until capacity coding errors are gone.
- **Flows vs demand (p. 44).** Raising demand because modelled flows are low when they are low from congestion only makes it worse.
- **Sub-areas (p. 26).** Some tools extract a subnetwork "along with the corresponding time-varying, gate-to-gate demand matrix or vehicle trajectories (routes)", which go to a microscopic model.

### 3.2 Multi-resolution modelling

**FHWA-HRT-22-055, Multiresolution Modeling Guidebook** ([PDF](https://www.fhwa.dot.gov/publications/research/operations/22055/22055.pdf); the [Caltrans guidebook](https://dot.ca.gov/-/media/dot-media/programs/research-innovation-system-information/documents/final-reports/multiresolution-modeling-for-traffic-analysis-guidebook-a11y.pdf) is the same text). **Read:** Feedback and Convergence (pp. 37-39), case study (pp. 55-57).

- Volume-delay functions let flow exceed capacity, treat each segment as independent and have no spillback. Inaccurate macroscopic inputs carry into the micro model (Introduction).
- **"Capacity is an input to the macroscopic models. However, capacity is an output in most mesoscopic models and all microscopic models."** So the analyst must tune all levels to obtain "segment-level and turn movement-level capacities consistent with each other", and use calibrated capacities from the higher-resolution model to refine the upper levels (p. 38).
- **The failure we have, in one sentence:** "If the macroscopic and mesoscopic models underestimate delay on a given path, the heavy assigned traffic may produce unrealistic gridlock in the microscopic network" (p. 37).
- Recommended: a **feedback loop from micro up to meso and macro**, not one-way flow down. Derive VDF parameters from micro results per segment if affordable (p. 38). Plot delay against v/c per critical segment. Even then, VDFs may be unrealistic when oversaturated, and meso may miss turn-bay spillover and lane-change effects (p. 39).
- **Numbers, Table 2, West Palm Beach downtown, capacity per lane per hour:**

| Link | Measured from micro | Default in macro | Default in demand model |
|---|---:|---:|---:|
| Okeechobee Blvd | 850 | 1,715 | 1,035 |
| S Tamarind Ave | 650 | 1,470 | 1,035 |
| Banyan Blvd | 400 | 1,470 | 1,035 |
| S Australian Blvd | 850 | 2,205 | 1,902 |

So regional capacities overstate downtown by 1.2-2.6× (demand model) and 2-3.7× (macro). **Inference:** this is the same size of error we have. MATSim's 1,690-2,050 per lane on unsignalled approaches, against our movement capacities, is that table.

- Table 3, one junction, per lane by movement: meso 386-1,117, micro 326-794, HCS 278-638. Through and turn capacities differ by 2×, so link-level capacity can't represent them.
- **BPR tested:** "the BPR model calibration improved the results slightly, the analysis showed that the BPR underestimates the delays, particularly for v/c ratios higher than 0.9" (pp. 57-58).
- Zones: "Without such updates, the simulation models may show unrealistic gridlock due to vehicles accessing the network in large numbers at the wrong locations" (pp. 27-28).
- ODME: "measured link flows do not represent the demand in congested areas with capacity constraints" (citing Lu, Zhou and Zhang 2013).

**FHWA-HRT-21-082, MRM State of Practice** ([PDF](https://www.fhwa.dot.gov/publications/research/operations/21082/21082.pdf)). **Read:** Subarea Analysis and Boundary Conditions (p. 13), Subarea Macroscopic Modeling (pp. 25-26).

- "After identifying the subarea boundaries, analysts should conduct path-based traffic assignment in the higher level network to generate path flows entering, exiting, and bypassing the subarea." Zonal connectors should be converted to side streets near the boundary, so sub-area OD estimation is consistent.
- The sub-area should keep sensitivity to demand changes in the whole network, and the whole network to supply changes in the sub-area (citing Zhou et al. 2006).
- **Practice has a layer we skipped:** an extra level between the demand model and the micro: a refined sub-area in a static assignment tool with updated geometry, detail, refined zones, connectors **and signal timing**, used to "produce inputs to microscopic simulation models" (p. 25).

**FHWA-HOP-13-015, Traffic Analysis Toolbox XIV, DTA Guidebook** ([§2](https://ops.fhwa.dot.gov/publications/fhwahop13015/sec2.htm), [§6](https://ops.fhwa.dot.gov/publications/fhwahop13015/sec6.htm)). **Read:** §2.2 stability, §6 sub-area extraction.

- "No useful simulation statistics can be obtained from a gridlocked network because the flow is zero and the travel time is infinity for one or more links." A run with many vehicles waiting at entries "is not a valid one". A relative gap of zero is probably not achievable with a stochastic simulation.
- Sub-area extraction yields O-D tables "for each individual time period", which seed the sub-area matrix. Disaggregate regional zones by land use, not area.

**ODOT APM v2, ch. 8** ([PDF](https://www.oregon.gov/odot/Planning/Documents/APMv2_Ch8.pdf)), **read** §8.2.2 heading only: two kinds of sub-area, *focusing* (add detail inside the regional model, keep the region running) and *windowing* (cut a part out, the rest becomes externals). **Inference:** we windowed. The sources point to focusing first, then windowing with flows from the focused model.

**Chen and Machemehl 2017** ([PDF](https://www.iieta.org/download/file/fid/93793)), **read** abstract and review: sub-network size is defined by how far rerouting reaches. An earlier VISTA study used a size parameter of 4-10 link hops around a changed link. Too small misses rerouting; beyond 10 gives no real time saving. This is for a change at one link, so it doesn't set the size for a whole district.

**Zhou, Erdogan and Mahmassani 2006**, TRR 1964, pp. 176-184, **abstract** via [VTI catalogue](https://bibliotek.vti.se/bib/265190): two-stage sub-area demand. First produce a time-dependent sub-area OD by extraction, then a bilevel update combining that with archived counts.

**Sbayti, Lu and Mahmassani 2007**, TRR 2029, pp. 22-30, **abstract**: MSA is by far the most used heuristic in simulation DTA, and its convergence on real networks is uncertain, partly because simulators are not well behaved. The fix uses local, vehicle-level information from the simulation to pick step sizes. I don't have their numbers.

**Zhou and Taylor 2014, DTALite** (Cogent Engineering 1:961345), **snippet only**, the PDF returned 403: Newell's simplified kinematic wave for loading, needing only link capacity and free-flow speed, plus agent-based DTA and OD calibration in one system. The open-source [DTALite](https://github.com/asu-trans-ai-lab/DTALite) takes GMNS networks. I have no run times from it.

### 3.3 Assignment theory

**Boyles, Lownes and Unnikrishnan, *Transportation Network Analysis*** ([arXiv 2502.05182](https://arxiv.org/pdf/2502.05182)), **read** in part: §5-6 (Beckmann, algorithms), §11.2-11.3 (dynamic equilibrium).

- Wardrop's first principle, Beckmann's convex program and BPR: with continuous, increasing link costs, static equilibrium link flows exist and are unique. Static assignment needs only free-flow time and capacity per link.
- Frank-Wolfe zigzags and has trouble reaching high precision (§6). MSA steps must fall slowly enough not to stop short, and fast enough not to "overshoot the equilibrium and oscillate" (§11.2.2).
- **Dynamic equilibrium may not exist and need not be unique.** §11.3 gives a network with no equilibrium. "The reason no equilibrium exists is because the node model ... is not continuous in the sending and receiving flows", and "when building node models that capture absolute priority (as at yields, two-way stops, or signals with permitted turns), ensuring continuity is difficult". **Inference:** a microscopic model with absolute give-way and fixed routes is the extreme of this. Don't expect the gap to go to zero, and don't read a stuck gap as a bug on its own.

**Boyce, Ralevic-Dekic and Bar-Gera 2004** ([TR 155](https://www.niss.org/sites/default/files/technicalreports/tr155.pdf)), **read** abstract and results: 39,800 links, 1,510 zones. Link flow differences between scenarios are stable only at a relative gap of about 0.01%. Frank-Wolfe "does not achieve a stable or highly converged solution". RG 1% took about 25 equivalent FW iterations, 0.1% 92, 0.01% 534.

**Patil, Ross and Boyles 2021** ([PDF](https://par.nsf.gov/servlets/purl/10389228)), **abstract**: VMT and total time stabilise by RG 10⁻⁴, link flows by 10⁻⁵, most-used paths by 10⁻⁶.

**Nie and Zhang 2010** ([PDF](https://transportation.tech.northwestern.edu/docs/research/core-topics/transportation-network-modeling-and-planning/10.10072Fs11067-007-9022-y.pdf)), **read** conclusions: line searches converge faster and more stably than MSA. Equilibrium "is sensitive to the spatial distribution of queues", so the loading model needs real queue-end speeds.

**BPR.** Function from the [FHWA guide](https://www.fhwa.dot.gov/publications/research/operations/22055/22055.pdf) appendix. **Inference by arithmetic:** with α = 0.15, delay at v/c = 1 is 15% of free-flow time. On a 100 m street at 50 km/h, that is 1 s. A signal at 50% green, 90 s cycle gives over 10 s of uniform delay at low flow, and a lot more near capacity. So a link-only BPR on an urban signal network **has the wrong shape**. It is the junction that sets delay.

**DfT TAG M3.1** ([PDF](https://assets.publishing.service.gov.uk/media/6a033d074fb0713aa63ea802/tag-m3-1-highway-assignment-modelling.pdf)), **read** §2.7, Appendix E.8, Tables via report A. §2.7.5: "in congested networks, junction delays are critical and therefore junctions should be modelled explicitly and congested assignment techniques applied". §2.7.6 names time slices, flow metering and blocking back as the extensions. E.8: where metering isn't modelled, assigned flows can exceed capacity, and over-capacity functions are needed: AN1A and Akçelik, "based on theory rather than empirical data". Exit criteria come from report A: %GAP under 0.1% or stable and documented, over 98% of links changing under 1% for four iterations.

**Node models.** Corthout, Flötteröd, Viti and Tampère, "Non-unique flows in macroscopic first-order intersection models" ([report TRANSP-OR 110520](https://infoscience.epfl.ch/record/167471/files/CorFloVitTam2011.pdf?version=6)), and Flötteröd and Rohde, "Operational macroscopic modeling of complex urban road intersections" ([report TRANSP-OR 101204](https://infoscience.epfl.ch/record/163232/files/FloeRoh2010.pdf?version=3)), both **abstracts**, both working in the generic node model class of Tampère et al. Corthout: "most intersection models embedded in macroscopic Dynamic Network Loading (DNL) models are not well suited for urban and regional applications ... because so-called internal intersection supply constraints, bounding flows due to crossing and merging conflicts inherent to the intersection itself, are missing". Intersection models "can produce non-unique flow patterns under identical boundary conditions", and they keep point-like nodes rather than spatial ones. Flötteröd and Rohde give an operational node model built on the incremental transfer principle. This is the theory for putting movement capacities in a kinematic-wave loader. **Inference:** use point-like junctions in the macro layer, and accept that a given boundary state need not fix one flow pattern.

**Capacity-constrained and quasi-dynamic assignment.**

- **STAQ, Brederode et al. 2019** ([record](https://research.utwente.nl/en/publications/static-traffic-assignment-with-queuing-model-properties-and-appli/)), **abstract**, the full text timed out both times: captures flow metering and spillback at bottlenecks like a dynamic model, at little more input and compute than static. RG below 10⁻⁴ on large networks.
- **Chan et al. 2021, QDTA** ([arXiv 2104.12911](https://arxiv.org/pdf/2104.12911)), **read** abstract and intro: a sequence of static problems at 15-minute steps, with residual demand carried over. 96 steps on a 1 M link network in about 4 minutes on 1,024 cores, a speedup of over 36× on serial. **Inference:** that is about 2.4 h serial for 1 M links. Scaled linearly, our 8,800 edges take about 1.3 minutes. Treat that as an order of magnitude.
- **Seo 2026, UNsim** ([arXiv 2604.11380](https://arxiv.org/pdf/2604.11380v3)), **abstract**: differentiable kinematic-wave simulation with route choice, about 2,500 links and 1 M vehicles over 3 h, 3,000 gradient iterations in about 40 minutes. Our size class. A way to fit OD and capacity with gradients later.

**Peeta and Ziliaskopoulos 2001** (Networks and Spatial Economics 1:233-265): **not opened**, only the bibliographic record. I make no claim from it.

### 3.4 MATSim

**MATSim book** (Horni, Nagel, Axhausen 2016, [open copy](https://openresearchlibrary.org/ext/api/media/27f59836-d5af-40ca-a7f4-8ea2033c958f/assets/external_content.pdf)), **read** §1.3, §4.3.1, §97.5.

- "The MATSim traffic flow model is strongly based on the two link attributes: storage capacity and flow capacity." Flow capacity is the outflow capacity of a link. QSim has no inflow capacity (§1.3). Signals and lanes are optional extensions.
- Sample scenarios: for a 10% sample, `flowCapacityFactor` and `storageCapacityFactor` should be 0.1 (§4.3.1).
- Stuck time: after that many seconds without movement, "a vehicle is moved across an intersection despite violating the storage constraint". It was "introduced to resolve grid-locks". Default 10 s. Unpublished tests found longer values less realistic against counts (§4.3.1).
- Single-queue fundamental diagram: flat at medium densities, jam waves move at L per 1 s, not 15 km/h (§97.5).

**OpenBerlin v6.4** ([config](https://raw.githubusercontent.com/matsim-scenarios/matsim-berlin/release/v6/input/v6.4/berlin-v6.4.config.xml), [README](https://github.com/matsim-scenarios/matsim-berlin), [scenario](https://raw.githubusercontent.com/matsim-scenarios/matsim-berlin/release/v6/src/main/java/org/matsim/run/OpenBerlinScenario.java)), **read**:

- `flowCapacityFactor` 0.1, `storageCapacityFactor` 0.1, **`stuckTime` 30 s**, `trafficDynamics` kinematicWaves, `linkDynamics` PassingQ, end 36:00.
- Subpopulations `person`, `freight`, `goodsTraffic`, `commercialPersonTraffic`, `commercialPersonTraffic_service`. README: "calibrated taking into consideration the traffic counts, modal split and mode-specific trip distance distributions".

**How link capacities are set, v6.x** ([`BerlinNetworkParams`](https://raw.githubusercontent.com/matsim-scenarios/matsim-berlin/release/v6/src/main/java/org/matsim/prepare/network/BerlinNetworkParams.java), `ApplyNetworkParams`, `HBSNetworkParams`, **read** code):

- A fitted predictor per junction type (`traffic_light`, `right_before_left`, `priority`) gives capacity per lane and a speed factor per link. Results are clamped: floor 0.4, 0.6, 0.8 of `capacityEstimate(v)`, ceiling 1.0 of it.
- `capacityEstimate(v)` is car-following only: `v/(1.2 v + 7)`.
- `HBSNetworkParams` is an alternative set. Its comment says "Traffic lights are not considered".
- Rakow et al. ([KoMoDnext 2021](https://elib.dlr.de/144810/1/KoMoDnext_ITS-Hamburg_2021.pdf), **snippet**) describe the related pipeline: simulate signalised junctions in SUMO, then pass the flow capacities to MATSim. I did not establish what v6.4's predictors were trained on. Report 23 says free speeds came from routing services. So no part of this has met this map's programs.

**Ziemke, Kaddoura and Nagel 2019** ([PDF](https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2019/19-01/ZiemkeEtAl2019OpenBerlinScenarioVSPWP.pdf)), **read** §2.3-2.4. This is v5, not v6.4. Network from OSM: all road classes in Berlin, main roads outside, 73,689 nodes and 159,039 links. Counts: 346 stations, 8,304 hourly values. Calibration: Cadyts on activity locations against counts, with **all travellers on the car network and capacities scaled by the car share (0.31 instead of 0.10)**, then a manual mode step. "Freight ... simplified" from BASt counts. **Inference:** the demand was fitted so a queue model on those capacities matched counts. It's a joint fit of demand and supply, so demand can't be carried off alone without care.

**Inference, why these routes need not be feasible on a lane-level map with signals:**

| MATSim | Our map | Effect |
|---|---|---|
| Outflow limit per link, all turns together | Lane groups, each with its own green | Left-turner queue doesn't exist in MATSim |
| No crossing conflict at a node | Crossing flows share one junction | Sum over approaches isn't limited |
| Signal = constant 0.4 × maximum at most primary and secondary approaches | Green share 0.15 / 0.31 / 0.60 at p10 / p50 / p90, measured in Hamburg (report 23) | Low-green approaches get far too much |
| Priority: capacity doesn't vary with opposing flow | Siegloch against the actual major flow | A secondary or tertiary approach gets about 2,000 and a residential one about 800, whatever the major flow. HBS gives 736, 451, 277 at major flows of 400, 800, 1,200 (report 23) |
| `stuckTime` 30 s forces the head across | No valve | Spillback never closes the loop in MATSim |
| Free speed = limit × fitted factor, about 0.45-0.85 by class and junction | Limit, with signal delay separate | No main-road preference. Primary is slower than tertiary |
| Activity on a link, no turn rules | Turn rules | 29.3% of vehicles with a U-turn (report 23) |
| Joint fit to counts | | Flows match some counts for reasons that don't carry over |

### 3.5 Day-to-day and Cadyts

**Flötteröd, Bierlaire and Nagel 2011**, Transportation Science ([PDF](https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2008/08-19/FloeBierNage2010TS_dec2010.pdf)), **read** abstract and §2: "the analyst's prior knowledge is represented by the dynamic traffic simulator itself and the measurements are comprised of time-dependent traffic counts". Each traveller's plan gets a utility offset from the log-likelihood gradient. Cadyts needs only a simulation system that can produce realisations.

**[Cadyts manual](https://transp-or.epfl.ch/cadyts/Cadyts_manual_1-1-0.pdf)**, not read beyond the title.

**Inference:** Cadyts corrects choices given a simulator. So its corrections are specific to that simulator's supply. Report 15 already says "corrections don't transfer". Report 12 says the published `plans-initial` are post-Cadyts. So the plans we hold carry corrections for MATSim's capacities, and we can't remove them.

**Day-to-day dynamics.** Boyles §11 and Nie and Zhang above cover fixed points. I did not read a day-to-day stability source in this job. Report 06's prototype tested capped against uncapped switching on our own grid.

### 3.6 How far real routes spread around the shortest path

**Zhu and Levinson 2015** ([PLOS ONE](https://pmc.ncbi.nlm.nih.gov/articles/PMC4534461/)), **read via a fetch summary**, 143 GPS subjects, 25,157 trips, Minneapolis-St Paul:

| | All trips | Commute |
|---|---:|---:|
| On the shortest-time path, strict | 34% | 13.5% |
| Within 10% | 40% | 21.7% |
| Less than 5% longer in time | about 55% (non-commute) | about 30% |
| Less than 20% longer in time | about 80% (non-commute) | about 70% |

About 50% of trips are under 30 s longer than the shortest-time route, almost 90% under 5 minutes. The share on the shortest path falls to about 5% at 20 miles. "Most travelers prefer using freeways to local streets." Best route-set generators find only 63% of observed routes at 80% overlap.

**Lima et al. 2016** ([J. R. Soc. Interface](https://royalsocietypublishing.org/doi/10.1098/rsif.2016.0021), local copy read for Fig. 3): 34% of routes chosen are not any of the shortest paths, and over 53% of the preferred routes are not optimal. **Second-hand:** this is the abstract-level claim in the caption; I didn't check their method.

**San Francisco DTA calibration** ([SFCTA](https://sfcta.org/sites/default/files/2019-03/SFDTAFinalCalibrationandValidationReport.pdf)), **read** calibration section: traffic dispersed "much more broadly throughout the grid network" than in the static model, with the exact same demand. Fix: lower free speeds on stop-controlled streets for acceleration time, then a generalised cost that raises perceived time on locals and collectors. Final gaps in a late run: min 0.6%, max 12.8%, mean 5.7%, "not a stable convergence", 60 iterations, 20.2 h.

**Inference.** Real trips are mostly not shortest-time. From their Fig. 4, half of commutes lose about 10% in time, and half of other trips under 5%. So real traffic has a **relative gap of the order of 5-10%, not 0.1%**, measured on a shortest-time basis. Their shortest times are themselves estimates, so that figure is rough. It doesn't mean people are irrational: it means perceived cost isn't our cost. Consequence: a deterministic UE solved to 10⁻⁴ is a numerical target for a stable solution, not a behavioural claim. Use perception noise and a hierarchy term, then solve *that* to stability.

### 3.7 OD estimation from counts

- **Cascetta 1984** (Transportation Research 18B:289-299), **not opened**, **snippet** on GLS: combine a prior matrix with counts, weighted by the covariances of each. **I have no page references.**
- **Marzano, Papola and Simonelli 2009**, "Limits and perspectives of effective O-D matrix correction using traffic counts" (TR-C 17:120-132), **snippet**: correction generally can't work when independent observed link flows are fewer than OD unknowns, and they generally are. They look to within-day dynamics for more equations.
- **Antoniou et al. 2016** (TR-C 66:79-98, [record](https://hdl.handle.net/2117/86110)), **abstract**: OD flows are unobservable except on closed highways, which is why performance is hard to measure. It offers a synthetic benchmark. Report 15 step 7's synthetic recovery test is this idea.
- **Yang et al. 1992** (TR 26B:417-434), **not opened**: congestion-aware bilevel estimation exists because the assignment map depends on the matrix.
- **[arXiv 2202.00099](https://arxiv.org/pdf/2202.00099)**, **abstract**: bilevel OD estimation with a meso simulation inside, treated as a costly black box.
- **FHWA-HRT-22-055** (above): flows don't represent demand in congested areas; use travel-time or density measures as well.
- **TAG M3.1** (via report A): limits on matrix change. Zonal cells slope 0.98-1.02, R² over 0.95. Trip ends slope 0.99-1.01. Trip length ±5%. Sector changes ±5%.
- **Report A, Fremont:** without regularisation, fit slope 0.92 and R² 0.91, test slope 1.30 and R² 0.81.

**Inference, what counts can and can't determine, for our 94 district sites:**

| Quantity | Counts determine? | Why |
|---|---|---|
| Lower bound on a movement's or lane's capacity | **Yes** | Real flow can't exceed real capacity. No model in between |
| Total entering and leaving through a screenline with all roads counted | Mostly | We have only part of the cordon. SVZ fills some |
| Class split of vehicle-km | Yes, statistically | Sites by class. Primary −22%, tertiary +26% is this |
| Time profile per site or gate | Yes, where counted | Report 23: peak ±1 h |
| Route split at a junction not counted | No | Needs probes or GPS |
| OD cell values | **No** | Thousands of cells per hour against 94 sites |
| Demand on a congested road | **No** | Count is throughput |
| Whether fit is right for the right reason | No | Fremont |

### 3.8 What demand models usually omit, in shares of vehicle-km

These are other cities. None is measured for our district.

| Traffic | Number | Source | Reading |
|---|---|---|---|
| Vans | 13% of motorised km, London; 14% GB (2011) | [TfL Tech Note 5](https://content.tfl.gov.uk/technical-note-05-what-are-the-main-trends-and-developments-affecting-van-traffic.pdf), read | |
| Vans | 16% of km, London 2017, 10% in 1993 | [Travel in London 11](https://foi.tfl.gov.uk/FOI-1690-1920/travel-in-london-report-11.pdf) §7, read | |
| Heavy goods | 3% central and inner London, 4% outer | Same | Detector trucks in Berlin: 8.33% of crossings, but 3.23% of city-street km (report 03) |
| Commercial, German city | 34% of city mileage, 10% at the edge, up to 70% in the centre | [BASt-indexed report](https://trid.trb.org/View/997088), **snippet only**, year unknown | v6.4's 48% in a central district is plausible on this, but it's weak evidence |
| Ride-hail | At least 6.5% of weekday VMT citywide, up to 20% intra-city in San Francisco, 20% of its VMT out of service | [SFCTA TNCs Today](https://SFCTA.org/sites/default/files/2019-02/TNCs_Today_112917_0.pdf), read | 2016 US figures; Berlin isn't SF. 43% of TNC VMT is 18:30-03:00, 26% in peak periods ([Erhardt 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6506243/)) |
| Ride-hail, growth | Almost half of the VMT growth 2010-16 in SF | Erhardt 2019, read | |
| Cruising for parking | **Under 1% of vehicle travel, under 5-6% of trips** in SF and Ann Arbor, GPS | [Millard-Ball, Hampshire and Weinberger 2020](https://millardball.its.ucla.edu/wp-content/uploads/sites/22/2022/06/Weinberger_Millard-Ball_Hampshire_2020_Parking_search_caused_congestion_fuss_preprint.pdf), read | Against the often-quoted 30% ([Shoup 2006](https://doi.org/10.1016/j.tranpol.2006.05.005), not opened), which they explain as a figure for near-destination traffic |
| Buses | About 2% of site flow in Berlin BeST | Report 03, modelled | Small in km. Large in capacity, because they stop in the lane and hold bus lanes (report 20, item 2) |
| Through traffic | **No source reached with a share** | Report 16, item 11: Berlin motorway ratio falls from 0.56 to 0.06 toward the map edge | v6.4 `freight` is 1.1% of the district's km. Any non-Berlin through car is in Brandenburg's 6.1% or absent |
| Taxis, Berlin | **No source reached** | | Not a v6.4 subpopulation by name |

**Inference for our case.** Our demand already holds about the right vehicle-km by the static check (4.18 vs 4.18 M km on main roads). Missing buses, taxis and cruising probably add a few percent of km, plus a real capacity loss for buses and kerb stops. Commercial traffic might be too high, not too low. So **adding omitted traffic is not the first-order fix**. It should stay on the list as a capacity term at the kerb and a few percent of demand, and not be treated as a large gap. And it can't explain the feasibility failure: more traffic makes it worse.

## 4. The correct pipeline for our case

Sections 4.1-4.3 are **Inference**, built from the sources in section 3 and our files. Where a step rests on a source, it says so. Formulas not marked as read are standard ones written from memory: check them against HBS, Webster and Akçelik before coding.

### 4.1 The principle

**Each layer's output is conditional on the supply it was computed on. Pass forward only what doesn't depend on that supply, and recompute the rest.**

| From MATSim v6.4 | Carry it forward? | Why |
|---|---|---|
| Who travels, from where, to where, when, in what vehicle | **Yes**, with the caveat that plans are post-Cadyts | The closest thing to demand that we hold |
| Routes | **No** | They answer "best path on MATSim's capacities and free speeds" |
| Link flows | **No**, except as a screen | Same |
| Free speeds, capacities | **No** | Inputs of a different model. Section 2.3 |
| Times of crossing the cut | **No**, once supply has changed | They come from MATSim's experienced times |

**What capacity means at each layer** (FHWA-HRT-22-055, p. 38, generalised):

| Layer | Capacity is | Set from | Handed to |
|---|---|---|---|
| Regional queue model (MATSim) | An input per link, fitted | Road class, junction type | Nothing below |
| Macro on our map | An input per movement | Our lanes, signals, HBS, real saturation flow | Micro, as flows and paths |
| Micro | An output | Engine physics | Back to macro, as a check |

The check that links them: **macro's input capacity, micro's measured capacity and real flows must agree per class of movement. A gap between micro and real is an engine bug. A gap between macro and real is a table bug.**

**The correct layering:**

```
Step 0  Demand table, whole region: who, where, when, class. No routes.
Step 1  Movement table from our map: capacity, storage, free time, per movement.
Step 2  Static tests, no assignment: real counts against capacity; cuts; demand-fraction screen.
Step 3  Macro assignment at 100% demand with movement costs. One CPU, minutes.
Step 4  Score macro against real counts and probes. Fix table and demand by rule. Limited OD last.
Step 5  Boundary flows for the district, from the region macro.
Step 6  From path flows to vehicles, routes and lanes. Static lane checks.
Step 7  Micro enters. Isolated capacity, then district with macro's routes.
Step 8  Micro feedback: small route refinement; measured capacities back into step 1.
```

We went from step 0 straight to step 7, on routes from a different supply, then used step 8's tool to do step 3's job. That's the error in one line.

### 4.2 Step by step

#### Step 0. Demand table

- **In:** v6.4 legs for the whole region, not the cut: 540,377 vehicle legs at 10%, with origin, destination, departure, subpopulation, class.
- **Out:** a table with no routes, plus zones. Weight 10 per record, kept fractional: the macro layer doesn't need ten clones. Zones small enough that no connector overloads a street; connect to side streets. FHWA-HRT-22-055 (pp. 27-28) names wrong access points as a cause of unrealistic gridlock.
- **Know it's right, with no run:** report 23's checks, already done: vehicle-km on main roads, cordon (−14% against SVZ), peak ±1 h. Add a table of the largest trip ends per connector per hour against that side street's capacity. Add the share of vehicle-km by subpopulation, and compare commercial's 48% with a German source when one is reached (section 3.8).

#### Step 1. Movement table

- **In:** `net.xml` connections, `tlLogic` and foes from m10 or later; lanes from OSM 2019; report 25's saturation flows.
- **Out:** one row per movement: from-edge, to-edge, lanes used, lane group, type, capacity, cycle, green, conflicting movements, storage, free-flow time without junction delay.

| Movement | Capacity per lane, veh/h |
|---|---|
| Signal, protected | `s · f_dir · f_hv · g/C`. `s` = 1,640, range 1,285-1,895 (report 25). `f_dir` 0.85 right, 0.90 left, as in the screen |
| Signal, permissive | `(g/C) · (3600/t_f) · exp(−q_opp (t_g − t_f/2)/3600)`, with `q_opp` the opposing flow in that green, plus a sneaker allowance per cycle |
| Priority, ranks 2-3 | Siegloch with HBS gaps, as above, `q` the flow it yields to, reduced by the chance that a higher-rank movement is queueing |
| Right before left | Same form with shorter gaps. Weakly grounded. Flag every use |
| Mid-block | `lanes · v/(1.2 v + 7)`, class-bounded. Same form as MATSim's `capacityEstimate` |
| Shared lane | Split the movements over the allowed lanes to minimise the worst lane's use (the screen's method). A permissive left on a shared lane caps the whole lane |
| Storage | `L · lanes / 7.5` per lane group, turn pockets on their own |

- **Signals are invented in Berlin.** So set cycles from Hamburg (75 s at night, 90 s at 07-20 h, report 26) and the Senate corridor figures. Set greens by equal degree of saturation on **converged macro flows**, with minimum greens, not on MATSim's. Report 23's retiming to MATSim's flows got worse in the micro, but those flows hadn't been assigned on this map, so that test says little. Label every value INVENTED. Rerun at s = 1,285, 1,640 and 1,895: that band moves dozens of movements (section 2.4).
- **Kerb and pedestrians:** a capacity factor only where there's evidence. SF measured pedestrian friction on turns; report 16 says we have none. Bus lanes from OSM 2019 cut lanes outright.
- **Know it's right, with no run.** Four tests:
  1. **Real flow is a lower bound on real capacity.** For each tuning site, day and hour: real flow on that lane group ≤ 1.1 × table capacity. This needs no model, no demand and no routes, so it's the most direct test we have. It isn't done. Sites run on main roads, so it will find main-road table errors first.
  2. **Distribution sanity.** Per-lane capacities should sit near FHWA Table 3's HCS and micro values for one Florida junction: through 330-660, left 280-410, right 560-790. A rough check only.
  3. **Engine parity.** Run report 23's isolated scenes per movement class. Ratio to the table should be 0.9-1.1. Today give-way is 0.57-0.66. Saturation is 1,870-1,895 against report 25's 1,640, so it may be the opposite way round.
  4. **Directed cuts** (`cuts.rs`). Feed it movement capacities, not `nominal_capacity`. Cut capacity ≥ real counted flow across it. A cut below real flow is a table bug, proved.

#### Step 2. Static screen at demand fractions

- **In:** step 1's table, MATSim's flows.
- **Out:** the table in section 2.4, run twice: on real capacities and on the engine's. A list of movements with capacity under 50 veh/h on main roads, and of approaches whose red-time queue exceeds storage.
- **Runs in** seconds. The scripts exist only in `/tmp/foundations-d/scripts/`, so move them into `scripts/berlin2019/`.
- **Exit:** every coding suspect explained. It tells you how far the old routes will go. It says nothing about how far correct routes will go. That's step 3.

#### Step 3. Macro assignment with movement costs

**Which model.** Three options, cheapest first. Start with the first. Move on only if the score says so.

| Model | Costs | Handles | Misses | Cost on one CPU (estimate) |
|---|---|---|---|---|
| **A. Movement-delay static, one peak hour** | `t0 + d(X)` | Junction delay, conflicts, spread | Time, queue transfer, spillback | 1-3 minutes |
| **B. Multi-period with residual queues** (QDTA, STAQ family) | Same, 15-30 min steps; flow out capped at capacity; rest carried forward | Rush hour, metering, queue timing, by point queue | Spillback unless added | About 1-20 minutes for a day |
| **C. Kinematic wave** (Newell cumulative counts, point-like node model) | Experienced | Spillback, blocked movements | Lane-level detail; non-unique | 10-30 minutes for 5 h |

**Why not BPR on links.** Section 3.3: BPR at capacity adds 1 s on a 100 m street, against 10+ s of uniform delay at a signal at any flow. It makes signals invisible until flow is well over capacity. That repeats MATSim's error in a new form.

**The cost function.**

```
t(e, m) = L_e / v_e + d_m(X_g)     X_g = (sum of flows in lane group g) / c_g
Signal:  d = 0.5 C (1 − g/C)² / (1 − min(1, X) g/C)  +  900 T [(X − 1) + sqrt((X − 1)² + 8 k I X / (c T))]
Priority: same overflow term, with c from Siegloch; a minimal service time 3600/c
T = period in hours. k and I as in Akçelik. Cap X at about 3 in costs, to keep numbers finite.
```

- `v_e`: **real** free speed per class. Use 90th-percentile probe speed per edge or class, with junction delay removed, not MATSim's factor. San Francisco found the same issue with stop-controlled streets (section 3.6). Report 23: real 06:00 speeds exceed our free speeds by 7-9% on motorway and arterial.
- Route cost: `t(e, m) × (1 + β_class) × (1 + ε)`. `β_class` is a preference on locals and collectors, fitted to class share. `ε` is perception noise, per origin and iteration, of the order of 10-20% in time. Both are grounded in Zhu and Levinson, San Francisco, Barcelona and Lausanne. Without them, equilibrium piles all flow on a single best path, which real drivers don't do, and that alone can raise lane loads.
- Vehicle classes: truck and van PCE, per class, with class-closed movements (report 23's 2.2% drop).

**Conflicts make it non-separable.** A permissive or priority movement's `c` depends on other movements' flow, so there's no Beckmann objective. Line-search Frank-Wolfe has no formal basis then. Do what practice does: hold `c` fixed for some inner iterations, then update `c` and greens in an outer loop. Don't expect monotone gap.

**Algorithm.** Path-based or a Frank-Wolfe variant that stores the all-or-nothing paths with weights, because step 6 needs paths. MSA steps for outer iterations are fine. Boyce: plain FW is weak at high precision. Nie and Zhang: line searches beat MSA when they are valid. `route.rs`'s edge graph already has the connection in it. Add a cost per connection.

**Run-time estimate.**

| Item | Number | From |
|---|---|---|
| Full shortest-path tree, 71,133 edges | 17.5-32 ms | Report 06 |
| Same, 8,800 edges (linear) | 2-4 ms | Inference |
| One iteration, 1,000 origins, one period | 2-4 s | Inference |
| A: 50 iterations | 2-3 min | Inference |
| B: 20 periods, warm start, 15 iterations each | 10-20 min. QDTA scaled by links says about 1.3 min, so treat this as a ceiling | Inference; [Chan et al.](https://arxiv.org/pdf/2104.12911) |
| C: 8,800 links × 3,600 steps of 5 s = 32 M link-steps | 6-30 s per load at 0.2-1 µs per step, plus route update | Inference |
| Region, 159,039 links in v5 (v6.4's size not checked) | About 18× district per iteration, 1,500 zones. Under an hour for a period: `heavy` | Inference |

**Kinematic-wave catch.** Stability needs `Δt ≤ L/v` for all links (stated in [UNsim](https://arxiv.org/pdf/2604.11380v3)). At 5 s and 50 km/h, that's 70 m. We have 540 edges under a car length on the 2023 cut. So contract chains and treat turn pockets as part of their road. The macro network is not the micro network, and needs an edge map between them.

**Know it's right, with no micro.**

- Feasible: no residual in the network by about 20:00. Vehicles in network bounded. Entry waits small (FHWA XIV: many waiting vehicles make a run invalid).
- Stable: section 4.4.
- Movement X > 1 is not a failure on its own. Real cities have oversaturated movements. It's compared with the real list in step 4.

#### Step 4. Score macro directly against the real day

**Use the frozen `metrics.py` and `step6_probes.py` unchanged**, on tuning sites only. Nothing about the hold-out moves. Macro flows have no seed noise and no ×10 sampling noise (report 23: 11% at 800 veh/h).

| Check | Macro output | Real | Target |
|---|---|---|---|
| Volume per site and hour | Lane-group flow | Detectors | Report 15's Credible: RMSN ≤ 0.40, R² ≥ 0.75, slope 0.85-1.15, GEH<5 ≥ 60% |
| Bias by class | Same | Sites | ±15%. Today primary −22%, tertiary +26% |
| Speed by class and hour | `L/t(e, m)` | HERE probes | Motorway ±10%, arterial ±20% |
| Rush hour | Lowest ÷ highest hour | 0.46 motorway, 0.69 arterial | ±0.10. Today 0.96, 0.97 |
| Bottlenecks | Movements with X > 1 per hour | Real list from probes, per report A's finding 1 | ≥60% caught, ≤40% false. Floor 73%, 33% |
| Cordon | Gate flows | SVZ | ±10%. Today −14% |

This is **the replacement for "does SUMO jam too?"**. Report 23 used SUMO to split inputs from engine, knowing it isn't evidence of accuracy. Macro does that job with real data as the reference. If macro with real capacities reproduces counts and rush hours, and micro on the same flows jams, the engine or the map's lane detail is at fault.

**What to change, read from flow and speed together.** Counts alone can't separate these. Flow and speed can.

| Modelled flow vs count | Modelled speed vs probe | Reading | Change |
|---|---|---|---|
| Low | Too low | Capacity too low there or just downstream | Step 1, within measured ranges |
| Low | Right or high | Traffic goes elsewhere, or isn't in the demand | `v_e`, `β_class`; then demand at the cordon |
| High | Right | Capacity fine, too many routes | Route cost |
| High | Too low | Route overload | Route cost; check OD |
| Right | Too high | Junction delay or kerb friction missing | Step 1 |
| Right | Too low | Capacity too low, and not the limit here | Step 1 |

**OD adjustment last, and small.** Only when route and capacity are done, and only a time-profile or gate-level factor first (report 15, step 6). Cell-level adjustment within TAG limits, if at all. v6.4 is post-Cadyts, on these counts, so most apparent OD error here isn't OD. Counts don't identify OD (section 3.7), and in congestion they're not demand. Report 15's synthetic recovery test comes before any real use.

**Stop condition.** If macro can't reach Credible with capacities inside measured ranges and small OD changes, no micro will. Report it and go to data.

#### Step 5. Boundary

See section 4.3.

#### Step 6. From path flows to vehicles and lanes

- **In:** path flows per OD and period from step 3 or 4; departure times from step 0; movement table.
- **Out:** a route file with whole vehicles.
- **How:** per OD and period, split real departures over paths in proportion to path flow, stratified so movement flows stay close. The ×10 step is ten copies with departures ±150 s, which report 23 labels INVENTED. Splitting them over macro's paths at least stops all ten taking one route. Test how much the spread matters. Trip ends go on the kerb side with no U-turn out-and-backs (report 23: 34,060 of them).
- **Know it's right, with no run:**
  - Recount movements from the route file: within ±5% of macro in each hour.
  - `cars lanes`: share of trips that can't be driven lane by lane at 3 s per change. Report 23 reached 2%. Aim lower.
  - `lane_load.py`, `signal_check.py`: no lane group over 1.0 apart from step 4's real bottleneck list.
  - **Lane-change demand on short roads:** vehicles per hour needing a change, per edge, against what that length can serve. Report 23's largest stuck class is two cars abreast on a short road. Find these before the run.
  - Rerun step 2's screen on the route file. This should now pass at 100% except at real bottlenecks.

#### Step 7. Micro enters here

1. **Isolated capacity first** (report 15, step 3; step 1's parity test).
2. **District, macro's routes, flat reduced demand** (E-C153 pp. 37, 44). Any persistent queue is a coding error or an engine gap. This is the exit test report 15 meant for step 2. It's only valid on routes assigned on this map.
3. **Then peak profile, 50%, then 100%.** Compare per movement with macro: discharge rate, queue place and time, vehicles in network. Disagreement where macro has no queue points to engine or lane detail. Report C's waits and report 23's seeds are the tools.
4. **Valve as microscope** (report A): one run with a logged valve maps all seeds at once. Teleports off stays the final test.

**Why not before.** In a jam, "flow is zero and the travel time is infinity" (FHWA XIV), and "the assignment algorithm will often not converge" (E-C153 p. 37). Section 2.5 shows what our cost table does then. Micro assignment is also costly: about 5-6 minutes per iteration (report 06), for a noisy gradient. Macro gives a clean gradient in a few seconds per iteration.

#### Step 8. Micro feedback

- **Route refinement in micro,** only from below gridlock: `Capped` switching from macro's path sets, small share. Movement-level GPU counters first, so that a turn's queue is charged to the turn. Today it isn't (section 2.5).
- **Capacities upward** (FHWA-HRT-22-055, p. 38): measured `c` per movement class back into step 1 as a parallel table; rerun macro. Macro on the engine's table predicts the micro. Macro on the real table predicts reality. The gap between those two predictions is the engine's error, in vehicle-hours, per class of movement. That's the most useful number this pipeline gives.
- **Stop when:** macro and micro agree within 10% on vehicles in network and speed per class, per hour.

### 4.3 The sub-area boundary

**Source.** FHWA-HRT-21-082 (p. 13): path-based assignment in the higher-level network, giving "path flows entering, exiting, and bypassing the subarea". E-C153 (p. 26): "time-varying, gate-to-gate demand matrix or vehicle trajectories". Zhou et al. 2006: extraction, then a bilevel update against counts. FHWA 2004 and TfL, via report A and report 20: extend the network so queues sit inside it. FHWA XIV §6: sub-area ODs per time period.

**Ours.** Report 20 item 16: "Insertion waits off-network, exits are free sinks." Report 23: worst jam cluster near the east edge, "I haven't ruled out a boundary artefact".

**Inference, what to do:**

1. **Focus, then window.** Run step 3 on the **region** with movement detail inside the district (and a ring), MATSim-style class capacities outside, with their floors reviewed. Then cut. Don't cut first. Queues outside change crossing times and metering. A cut from MATSim's times is a cut through MATSim's queues.
2. **Inflow per gate, per class, per 5-15 min, is metered flow.** It's the macro's **outflow** of the last upstream link, never unconstrained OD demand. Real upstream signals and bottlenecks meter it. An unmetered gate delivers a surge no real street delivers.
3. **Outflow per gate is a time series, not a free sink.** Set exit capacity per period from the macro's downstream receiving flow. A free exit raises the district's capacity and hides any real queue that backs in from outside.
4. **Queues that lie outside.** If macro has a queue at a gate for over 15 minutes:
   - Probes show a real queue there: extend the area past it, because the queue is part of the problem.
   - Probes show none: it's a demand or capacity error at that gate. Fix it, don't model it.
5. **A ring.** Simulate past the scored area, at least past the first signal beyond each gate, and score inside. Size it by the longest real queue that crosses the boundary in probes. Chen and Machemehl's size rule is about one changed link, so it doesn't set this. No source gave me a district-scale number.
6. **Keep bypass trips** (FHWA SOP). They take capacity. A trip that leaves and comes back is one trip in macro and two timed pieces in micro. `matsim_vc2.json` counts 141,826 legs touching the box, against report 23's 176,236 pieces: 24% more, if they count the same thing. Check this. Each piece's entry time then comes from macro, so pieces of one trip stay coherent.
7. **Test the boundary in macro first.** Report 23's planned "larger cut, to test the boundary" costs a full micro campaign. In macro it's a one-minute comparison: district on its own against district inside the region; free exits against capped; metered gates against raw demand. Any difference tells you which gates matter before any run.

### 4.4 What convergence to expect

| Layer | Measure | Expect | Source |
|---|---|---|---|
| Static, separable costs | Relative gap | 1% in about 25 FW-equivalent iterations, 0.1% in 92, 0.01% in 534 | Boyce 2004 |
| Stable metrics | Relative gap | VMT and time at 10⁻⁴, link flows at 10⁻⁵, paths at 10⁻⁶ | Patil et al. 2021 |
| TAG exit | %GAP, link change | Under 0.1%, or stable and documented; 98% of links under 1% for four iterations | TAG, via report A |
| Static with conflicts (ours, step 3A) | Relative gap | 0.1-1%, not monotone | Inference |
| Capacity-constrained | Relative gap | Below 10⁻⁴ on their networks | STAQ, abstract |
| Kinematic-wave DTA | Relative gap | Several percent, rising with congestion and for later departures | E-C153 p. 34; Inference |
| Commercial DTA, San Francisco | Relative gap | Min 0.6%, max 12.8%, mean 5.7%, 60 iterations, 20.2 h | SFCTA report |
| Micro | Relative gap | Not below its own seed noise. Probably 5-15%, stable | FHWA XIV; E-C153: more realism, more gap. Number is inference |
| Real drivers | Gap on a shortest-time basis | 5-10% | Zhu and Levinson; Inference |

**What to use as the stopping rule:** stability, not a gap target. Scores on counts and speeds that no longer move, flows changing under 1% for four iterations. **Existence and uniqueness aren't guaranteed** once junctions have absolute priority (Boyles §11.3, Corthout et al.), so a gap that stops falling isn't by itself a bug. Report 06's target of RG < 2% and report 15's stable under 5% are fine for macro. Report 06's is probably out of reach for micro.

**What a gap measured in a jam means: little.** Report 23's fall from 33% to 11% had 24 of 25 iterations stalled around 10:25, with costs after the stall copied from the last bin (section 2.5).

## 5. Where our reports and code are wrong

**Inference, from section 2 and 3.** Ranked by how much each changes what we do.

| # | Where | What it says | What's wrong | Do instead |
|---:|---|---|---|---|
| 1 | Report 23, hill climb | "The map doesn't hold under sensible routes, so the fault left is not route choice" | **Not shown.** Those routes came from a micro loop that began in a jam: relative gap 11%, 24 of 25 iterations stalled near 10:25, edge costs with no turn level, costs after a stall copied from the last bin. No run has yet tested routes assigned on this map's capacities | Macro at 100%, then micro on those routes |
| 2 | Report 23, "Next fixes" and ranking | Lane swap first, step 5 "once 50% passes". "Routes overload lanes" is rank 4 | **Circular.** 50% can't pass reliably on routes that overload movements at 40-50%. For the failure at 30% and up, this is rank 1. Lane swap matters for the 10% seeds, and report C explains how it turns a small overload into a lock. It doesn't remove the overload | Step 3 now, in parallel with the swap |
| 3 | Report 15, recipe, step 2 and step 5 | Step 2 "*Exit:* no persistent queue anywhere at 50% ... Anything left is a coding error". Step 5 assigns afterwards, with report 06's micro loop | **Order is wrong for imported routes.** Step 2's reading is valid only on routes assigned on this supply. The recipe has no macro layer at all, though FHWA's practice survey describes one and E-C153 says a flat, reduced profile first | Section 4.1's order |
| 4 | Report 23, "What stops 50%" | "Not signal capacity, routes, fleet, or the kernel alone" | Routes aren't excluded (see 1). "Signals aren't the limit at 50%" is fair on the signal side for these flows. It leaves out minor movements: 5-9 over capacity at 50%, and 23-24 at the engine's give-way | Screen every movement type |
| 5 | Report 23, step 4 | "MATSim's queue model has its own capacities, and these routes never met this map's lanes" | True but it blurs two things. About 80% of the 900+ edges are MATSim's own flow on its own lanes, at v/c about 0.55. **The headline 2,447 on one lane can't be MATSim's own flow on its own lanes:** its highest in the five peak hours I have is 1,840 per lane (16 h, a 1-lane secondary with capacity 2,033), and no link exceeds v/c 1. Hour binning differs between the two counts, so check this edge rather than take it as settled. Of the 29-38 edges above 1,500, 3-9 have flow our routes added and 3-4 have fewer lanes on our map | Trace that edge with `compare_link.py` |
| 6 | Reports 15, 23, step 3 band | Saturation at 50 km/h, 1,800-2,100. Main is "the only one with capacity in band" | **Conflicts with report 25:** measured median 1,640, range 1,285-1,895, "the design value of 1,900 is only reached at the top of that range". These aren't Berlin sites. The driver choice rests on that band | Settle with step 1's count test |
| 7 | Report A, §3b, §4b | Table at green 0.31/0.43 per edge. "I could not open Berlin v6.4's config". "Default MATSim moves vehicles ... after a few seconds". "2,447 ... what you'd expect from plans that never had to fit" | Superseded by the movement screen. The config opens: **`stuckTime` 30 s**, kinematicWaves, PassingQ. See 5 on 2,447 | Use section 2.4 |
| 8 | Reports 15 (item 8), 16 (item 9) | "Missing vehicles", commercial traffic as a main gap | Right for Stockholm and BeST. **v6.4 has 48% commercial and goods by km in this district.** Missing traffic here is buses, taxis, cruising: small in km, bigger in kerb capacity | Section 3.8 |
| 9 | Report 06, §7 and the cut checks | A static max flow check failed, and directional cuts replace it | Fine as far as it goes. **Don't read it as "static checks don't work".** The movement screen is a static check, and it matches the stepped run's limit. Cuts use `nominal_capacity` (`lanes × min(3600/(1 + 7/v), 2400)`) and `cuts.rs:279` falls back to half of it, which is still above most signal approaches' real capacity. So "no cut violated" says little in a signal network | Feed `cuts.rs` the movement table |
| 10 | Report 06, §8 | Target RG < 2% | Reasonable for macro. Probably out of reach for micro. E-C153 gives no threshold and says gap rises with realism and congestion | Stability, section 4.4 |
| 11 | `costs.rs`, `route.rs` | Cost per edge per bin; no cost on connections | Correct bookkeeping at the wrong grain. Route choice can't see a queue that belongs to one turn. Spillback is charged to the victim. Not a bug report: it's a reason to use it later, from below gridlock, with per-connection counters | Section 4.2, step 8 |
| 12 | `Supply` in `costs.rs` | Lanes, length, free flow, speed only | No signals, no conflicts, no storage by lane group, so the crate can't state a capacity. It can't do steps 1-3 today | New table, per step 1 |

**Not wrong, and worth keeping.** Report 23's map fixes and U-turn removal stand. Teleports off stays the final test. Report 15's frozen hold-out and floors are what make step 4 possible. Report A's list of relief valves and the order "stop comparing, drop demand, find the origin" stand. **Report C isn't in conflict with this.** Its finding that the lock happens at 2-4% of jam density is what a few overloaded movements look like: the network is empty and a handful of movements are over. C explains why a small overload becomes a lock. This report explains why the overload is there. Both fixes are needed.

## 6. What I did not reach

**Sources, not opened or abstract only** (marked in section 3):

- Full text timed out or refused: STAQ (Brederode et al. 2019), Bliemer et al. on quasi-dynamic loading, DTALite (Zhou and Taylor 2014), TMIP DTA practical guide, Rakow working paper 21-05.
- Abstract only: Sbayti et al. 2007, Zhou et al. 2006, Antoniou et al. 2016, Marzano et al. 2009. So their numbers are not here.
- Not opened at all: Peeta and Ziliaskopoulos 2001, Cascetta 1984, Yang et al. 1992, Wardrop 1952, Beckmann et al. 1956 (RAND 404), BPR 1964, Shoup 2006. What I say on those comes from Boyles's textbook or second-hand.
- Cadyts manual, only opened. Flötteröd's day-to-day stability work, not read.
- Zhu and Levinson's numbers came through a summarising fetch of the PLOS page. Check the figures before quoting them in anything formal.

**Facts I could not establish:**

- What v6.4's capacity predictors were trained on, and how their free-speed factors were fitted. I read the code that applies them, and report 23's statement on routing services.
- The link count of v6.4's whole network. I used v5's 159,039.
- A share for through traffic, or for taxis, in Berlin. A German commercial share only as one weak snippet.
- Whether the stepped run used the same routes as the screen. If it re-routed between steps, the match at 30% means something different.

**Not done, on purpose:**

- I re-ran nothing. The screens are the earlier attempt's, on netconvert's signals, on MATSim's routes. Move those scripts out of `/tmp` before relying on them. The storage column is a mean red-time queue with no platoon pattern or offsets, and I didn't see its split by edge length (`movement_screen4.py` prints it, and no output was saved).
- The real-count lower-bound test in step 1 isn't run. It's the cheapest next thing.
- **Run-time figures in step 3 are arithmetic, not benchmarks.** Convergence for movement-level assignment with conflicts is my estimate, and no source gives it for a network like ours.
- No macro has been built, so I can't say whether 100% fits. Real traffic proves it fits on the real network. Whether it fits on our table is what step 3 answers.

