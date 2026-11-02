# C: Why real traffic stays fluid, and when a network must lock

Checked 2026-11-02. Reading only: no simulation, no GPU, nobody contacted. The only things I computed are small static sums on our own files (lane-km, ring sizes, saved `seeds.json` tables) and closed-form numbers for the test scenes. Scripts are in `/tmp/foundations-c/scripts/`. SUMO and other tools appear only as facts about how a tool works.

**How to read this.** "Source" says what a source says, and I say how much of it I read: **read** (full text or the pages named), **abstract** (abstract or catalogue record), **second-hand** (another paper or a search snippet reports it), **not opened**. "**Inference**" is my own reasoning. "**Ours**" is what our files and saved runs show.

## The answer

**Real traffic doesn't avoid locks by having fewer dangerous moments. It avoids them because every wait ends quickly. Our simulator's waits don't.** Four findings support that sentence. The first two come from our own files, the third is a formal result, the fourth is published theory:

1. **The Berlin lock is not a density limit.** At 50% the district leaves the healthy curve at 2.4 to 5.1 cars per lane-km, 2 to 4% of jam density. Rigid-route grid theory only collapses within hours near 25% of jam density, and real networks' mean critical density is about 28 cars per lane-km, more than five times higher.
2. **One car at the root stays there for half an hour or more.** In six saved Berlin runs, the top seeds' root car was held from first to last sample for a median of 30 min when it wanted a lane change, 60 min at a yield and 30 min at a signal, up to 240 min. The longest wait measured at the real I-80 lane end is 79 s, and every one of the 610 cars got in. A held head fills a median Berlin block in 78 to 157 s at 300 to 600 cars an hour. Anything longer spills.
3. **Fixed routes turn every wait into a wait for one exact thing.** Formal result: when each waiter needs one specific resource, a cycle means deadlock. When a waiter can take any of several, deadlock needs a knot, a set with no way out at all. A human who gives up a turn lives in the second world. Our cars live in the first. In 1997 the Dallas microsimulation authors wrote the same in words: this lock "cannot be seen in real-world traffic, because drivers move out of the lanes and pass on the on-coming lane or they abandon their current route and choose a detour".
4. **The theory already predicts "different places every run".** Daganzo, Gayah and Gonzales show three gridlocks in three runs of the same grid, and say the question is "not whether the system can ever jam, but how long this takes on average". So the 6-17% overlap of first stops is what a spread-out hazard looks like. It doesn't point at a list of junctions to fix.

**What this changes:**

- Stop treating seed junctions as a to-do list, unless a place repeats across seeds. Measure hold time and seed rate by hold type instead.
- Run one test no one here has run: the published closed grid with rigid routes. It has no lane choice, so it separates junction logic from lane logic in an afternoon. If `cars` locks well below a quarter of jam density there, the fault is in the kernel and no map fix will cure it.
- Give every hold type an end, not only the wrong-lane stop at the very end of a lane. The new branch rule fires within 15 m of the lane end. 62% of the lane-change root vehicle-hours in those saved runs stand further back than that, where LC2013's blocker margin of 20-40 m can park them.
- Don't assume more discipline means fewer locks. At six US sites drivers entered a blocked junction at 55-89% of the chances they had (pooled 75%), and 74% of the blocked time was partial, with others going round. We use 100% compliance on main and 90% on the physical driver. No German figure exists yet, so it should be measured.
- Don't build departure-time or trip-suppression effects to solve 50%. They act between days and on a scale of about 11%. They can't explain a lock at half of real demand.

**What is not known.** I found no study that measures how much any one of these behaviours moves a real network. No field study gives a share of missed turns per trip. The ranking below is my judgement, and each item ships with an ablation test for that reason.

## 1. The fact in numbers

**Ours.** District `m12`: 8,804 car edges, 1,415 lane-km on 49 km², 28.9 lane-km per km². Median edge 98 m, p25 56 m. 21.7% of edges under 50 m. Jam storage at 7.5 m per car: 188,726 cars.

| State | Cars on road | Per km² | Per lane-km | Share of jam |
|---|---:|---:|---:|---:|
| Healthy 10%, 07:30 (report 23) | 1,403 | 29 | 1.0 | 0.7% |
| **50% as it leaves the healthy curve, 06:00-06:30, Krauss** | **3,453-7,214** | **70-147** | **2.4-5.1** | **1.8-3.8%** |
| Healthy 100% at 07:30 (10 × the 10% run) | 14,030 | 286 | 9.9 | 7.4% |
| 50%, Krauss, 07:30, best map and worst map | 14,792-19,825 | 302-405 | 10.5-14.0 | 7.8-10.5% |
| 50%, physical driver, 07:30 | 31,955 | 652 | 22.6 | 16.9% |
| Nairobi's simulated bifurcation, 40 veh/mi-lane (DGG 2010), same lane-km | about 35,000 | | 25 | |
| **Real mean critical point, 41 cities (Loder 2019): 653 veh/km² at 23.46 lane-km/km²**; 27.8 is my division | see below | | **27.8** | |
| The same scaled to this district with Loder's elasticity 0.839 | 38,100, ±47% | 778 | 27 | 20% |
| Rigid grid, "few hours to collapse" at k ≈ kj/4 (DGG 2010) | 47,181 | 963 | 33 | 25% |
| Loder: critical accumulation "does not exceed one third" of jam | 62,900 | | 44 | 33% |
| Two-bin rigid model, jam at kj/2 | 94,363 | | 67 | 50% |

**Inference.**

- Averages over all lanes flatter this, because traffic concentrates. Even with all traffic on a third of the lanes, the onset is at 7 to 15 cars per lane-km, still below every line.
- Report 23 also found at 50% that retiming leaves 2 of 2,050 loaded lanes over capacity. So neither density nor lane flow says this should lock.
- I tried Loder's regression (Table 1) directly. Read from flattened XML, it gives 265 at the sample means instead of the reported 653, so I don't trust my reading of it and used the mean ratio and elasticity. The ±47% is the sample's spread. Loder's lane-km comes from OpenStreetMap on detector regions, so the match to our lane-km is rough.

Real Berlin at full demand (report 23, MEASURED, 8 days): arterials 25 km/h at their worst hour against 37 at 06:00, local streets 22 against 35. It slows by about a third and does not stop.

## 2. Theory: when must a network lock?

### 2.1 Gridlock as a reservoir (Daganzo)

**Source.** [Daganzo 2005 working paper](https://escholarship.org/uc/item/7w6232wq), read, §3-4. It is the earlier form of [Daganzo 2007, TR-B 41](https://its.berkeley.edu/publications/urban-gridlock-macroscopic-modeling-and-mitigation-approaches), which I could only reach as a record. A system "is subject to gridlock" for accumulations where steady-state outflow falls as accumulation rises. Outflow is a unimodal function G(n). Past the peak there is positive feedback: more cars, less outflow, more cars, until G is zero at the jam accumulation. On a ring with heavy demand, there is an upper bound on how many cars can be served, and above it "the queue would never dissipate". With inflow limited to hold n at the peak, the queue dissipates for any demand. So this kind of gridlock is a dynamic outcome, avoided by limiting inflow. It is not a logical necessity.

### 2.2 Rigid routes make the network unstable (Daganzo, Gayah, Gonzales)

**Source.** [Working paper May 2010](https://escholarship.org/uc/item/7qd590bv), read in full, published as [TR-B 45(1)](https://its.berkeley.edu/node/4628) 2011. I call it DGG below.

- Network: homogeneous grid of one-way roads, alternating direction, closed population, drivers turning at random (§2).
- Two-bin model: above a critical density, the even state is unstable. Stable states are uneven and have lower flow, and the network jams somewhere in kj/2 to kj. "Even though turning causes the phenomenon, the effect is independent of the proportion of turning traffic" (§3).
- Full grid with uncorrelated turns (§4.2): "If we were to run an infinitely long simulation of a network with only enough vehicles to fill four links, the system would eventually lock itself in a pattern with vehicles wrapping around a block. Clearly, for large networks, virtually the whole range of densities is unstable. Thus, the relevant question for real networks is not whether the system can ever jam, but how long this takes on average."
- Time to collapse (Fig. 9-10): none seen in 50-hour runs below kj/4. A narrow metastable range near kj/4 where it takes "a few hours". Under an hour above. Insensitive to the turning share. Fig. 8 shows **three different gridlock patterns from three runs**.
- Above the critical density, the stable state in large networks is "complete gridlock with zero flow".
- Their results are "a 'worst case'" because drivers follow rigid routes (§5). If a share α won't turn from a less congested bin into a more congested one, the bifurcation density rises linearly with α, from kc at α near 0 to kj/2 at α_c = 1 − w/v. Above α_c the lower branch disappears.
- Field: Yokohama's measured data never reached densities that show a bifurcation, "probably due to the fact that real drivers adapt more intelligently to traffic conditions that simulated drivers". Nairobi's simulation bifurcates as low as 40 veh/mi-lane because it lacks redundancy and a few key junctions restrict it.
- Limits they state: homogeneous, redundant, no exits.

**Inference, for our numbers.** With v = 50 km/h, w = 20 km/h and kj = 133/km, kc = 38 and α_c = 0.6. α of 0.3 gives a bifurcation at 52 per lane-km. Those are two-bin numbers. Use the grid's kj/4 as the safer rigid-route line.

### 2.3 Recovery is less stable than loading (Gayah, Daganzo; Geroliminis, Sun)

**Source.** [Gayah and Daganzo 2010 working paper](https://escholarship.org/uc/item/2x98k1x2), read, published in [TR-B 45(4)](https://its.berkeley.edu/node/4621). Networks are "inherently more unstable as they recover from congestion than as they are loaded", because very congested areas clear more slowly than less congested ones. Clockwise loops are expected after a disturbance, especially if many drivers don't adapt. The Toulouse field case had a loop only on the day of a truck strike (they report Buisson and Ladier second-hand). Yokohama has none.

[Geroliminis and Sun 2011, TR-A](https://infoscience.epfl.ch/bitstreams/dd751200-cbac-421a-8f8c-9f3ad8877098/download), read in part. Twin Cities freeway loops: real network-level hysteresis, flow differences close to 20% at the same occupancy between onset and offset, on freeways where drivers have fewer options.

[Elmegreen et al. 2023](https://arxiv.org/pdf/2401.00882), read in part, modelled: rush hours in eight cities take up to twice as long to unravel as to fill; "gridlock in our models begins at intersections regardless of the available road space in the network". Synthetic origins and destinations, so treat it as model behaviour.

### 2.4 Real jams spread and recover at measurable rates

**Source.** [Saberi et al. 2020, Nature Communications](https://pmc.ncbi.nlm.nih.gov/articles/PMC7138808/), read. A simple contagion model fits how congested links spread: rates β and μ, R0 = kβ/μ. If R0 ≤ 1, "congestion" stays a local thing. Google speeds, 10-minute samples, six cities, one morning in June 2018. R0 is nearly the same across cities at a speed-ratio threshold of 0.2. Spreading takes "a few hours" and recovery comes "within a few hours after the peak". On calibrated Melbourne (mesoscopic, Aimsun) at threshold 0.2, k = 2.12, β = 0.0577, μ = 0.0812, which gives R0 of about 1.51 (my arithmetic). More demand lowers μ and raises R0.

[Zhang et al. 2019, PNAS](https://pmc.ncbi.nlm.nih.gov/articles/PMC6500150/), read. Beijing and Shenzhen, GPS floating cars, 30 days in October 2015, 1-minute. Jam clusters tracked in space and time. Recovery duration Φ(T) ~ T^−3.13 (±0.06), cluster size P(S) ~ S^−2.34 (±0.02), similar across workdays and cities. Scale-free means no typical size and a long tail. They do not say whether every jam ended within a day.

**Inference.** Ours is the limit μ → 0: a held root car that never lets go gives R0 → ∞ for any seed. Both distributions can be computed on our HERE probes and on simulated speeds. They are a jam-lifetime test nobody here has run.

### 2.5 Do real cities lock, for how long, and what ends it?

I found no table of how often real cities lock. What exists is event reports.

| Event | Size and length | What started it | What ended it | Grade |
|---|---|---|---|---|
| [Interstate 95, Virginia, 3-4 Jan 2022](https://www.fairfaxcounty.gov/boardofsupervisors/sites/boardofsupervisors/files/assets/meeting-materials/2022/oct18-legislative-winter-weather-event-i-95-incident-after-action-report.pdf) | Clusters of stuck vehicles over 40 miles. Traffic stopped overnight; "last trapped motorists" out about 15:30, reopened 19:30 | Up to 3 in/h of snow, jackknifed trucks blocking all lanes | Ramps closed, tow trucks, plows against traffic, immobile cars pulled out. [OSIG audit](https://www.osig.virginia.gov/media/governorvirginiagov/office-of-the-state-inspector-general/pdf/performance-audits/I-95-Snow-Incident-Report-FINAL-8-11-22.pdf): troopers got motorists "to make a path for the snow plows" | Read. Agency reports |
| [Atlanta, 28-29 Jan 2014](https://www.ajc.com/news/atlanta-news/atlanta-snowmaggedon-2014-the-january-snow-storm-that-paralyzed-atlanta/KTEPKGS2RNHBTEOCIOFVSKNWFE/) | People stuck 12-16 hours, cars abandoned, lasting into 29 Jan | Light snow that froze, plus schools and employers releasing everyone together | Not established. No source I saw isolates the mechanism, beyond people leaving their cars | News, second-hand |
| [Beijing-Tibet highway, Aug 2010](https://www.npr.org/sections/thetwo-way/2010/08/23/129376194/traffic-jam-beijing-tibet) | About 60 miles, about 12 days, accounts conflict | Roadworks, trucks | Not established | News, second-hand |
| [Beijing, one evening in Sept 2010](https://chinadigitaltimes.net/2010/09/record-140-traffic-jams-hit-beijing-in-single-evening/) | "Record 140 traffic jams" in one evening, a count of jams and not hours | Not established. A Friday evening | Not established | News, second-hand |
| Toulouse truck strike (via Gayah and Daganzo) | Low flows through recovery, one day | Strike on the ring road, drivers on unfamiliar routes | Peak passed | Second-hand |

[Olmos et al. 2018, PNAS](https://pmc.ncbi.nlm.nih.gov/articles/PMC6294880) open with "mega-jams that last tens of hours or even days", then model several cities with a cellular automaton. Above a critical load, outflow stays very low for a long time. They report that the system still unloads completely "due to the rerouting possibilities". Modelled, read through a fetch summary.

**Inference.**

- Every documented lock has an outside trigger: snow, ice, a blocked motorway, a strike, or everyone leaving at once.
- Each lasted hours to a day and needed either inflow to stop or cars to physically leave. So **real removal exists**, by tow truck and by people walking away, but only at that scale.
- I found no documented real gridlock on a normal day in a German or Nordic city with no outside trigger. Absence from what I read isn't proof.

### 2.6 What this says about Berlin

**Inference.**

- By DGG, a rigid-route grid at 2-5 cars per lane-km should take far longer than 50 hours to collapse. We collapse in one to two.
- By Saberi and Zhang, seeds should die. Ours don't.
- By the Coffman analysis below, the state is absorbing unless something releases it.

So I read the lock as a **release failure, not a capacity failure**, with one caveat: give-way capacity at 57-66% of reference (report 23) does raise the seed rate, and it has its own fix on the physics branch. See mechanism 2.

## 3. Deadlock, formally

### 3.1 The four Coffman conditions

**Source.** [Coffman, Elphick, Shoshani 1971](https://dl.acm.org/doi/pdf/10.1145/356586.356588), read from a [mirror](https://carlstrom.com/stanford/quals/mirror/www-db.stanford.edu/~manku/quals/zpapers/71-deadlocks.pdf.gz). Deadlock needs all four: mutual exclusion, wait for, no preemption, circular wait. Their first figure is a traffic deadlock: four cars blocking the traffic at each corner of a block. So this analogy is 55 years old and the authors' own.

**The rest of this table is inference.** Evidence is in the last column.

| Condition | In a lane simulator with fixed routes | In real driving | What real drivers do to break it | Evidence |
|---|---|---|---|---|
| **Mutual exclusion**: a piece of road holds one car | Holds hard. A lane is a line, a zone a whole swept path | Holds for bodies. Softer for lanes and zones: others pass a blocker in the same width | Go round on a neighbouring lane, or over a marking | [Harris 2014](https://nctspm.gatech.edu/sites/default/files/u60/HARRIS-THESIS-2014.pdf): 74% of blocked time is partial. Report 20: side-by-side rare in Nordic queues (12 pair-seconds in 6,320), common in Athens |
| **Hold and wait**: keep your place while waiting for the next | Holds | Holds, nearly always | Leave the road: kerb, drive, side street, or abandon the car | Atlanta, I-95. No normal-day measure |
| **No preemption**: nobody can take your place | Holds, except teleports and a car being asked to slow | Holds by force, not by choice: a driver may give up a place | Waive priority, wave in, fall back, reverse, move aside | [StVO § 11(3)](https://www.gesetze-im-internet.de/stvo_2013/__11.html) requires it when traffic demands. Report 18: followers apply 39-68% of asked braking, 1 in 7 respond visibly. I-95 motorists "make a path" |
| **Circular wait**: A waits for B waits for … A | Every wait has one target, so any cycle is a deadlock | **The weakest of the four.** A driver waits for a way forward, not for one lane | Skip the turn, drive past, change plan | Dallas 1997, Aimsun's practice, DGG §5 |

### 3.2 Cycle versus knot, the formal difference

**Source.** [Barbosa and Benevides](https://cos.ufrj.br/uploadfile/1372173239.pdf), read in part, states the known results. Under the AND model, where a process needs all of its resources, a deadlock exists if and only if the wait-for graph has a cycle. Under the OR model, where any one of several is enough, the condition is a **knot**: a set whose every outgoing edge stays inside the set. The second result says a cycle isn't enough.

**Inference.** A fixed-route car in a fixed lane has out-degree 1. So a cycle is a deadlock, and the kernel can't get out. A human who will skip a turn has out-degree 2 or more. Then a deadlock needs a whole set of roads with no exit: a knot of many junctions in a grid. That is why DGG's rigid drivers are the worst case, and why the real thing needs snow.

A FIFO lane makes it worse. Only the head's wish counts, so one car's wish blocks everyone behind it, whatever they want. DGG's insensitivity to the turning share fits this.

### 3.3 Provable conditions, and whether a lane-and-signal network can meet them

| Result | Statement | Road meaning (inference) | Can we use it? |
|---|---|---|---|
| Kundu and Akyildiz 1989, Queueing Systems 4, second-hand via [Liebeherr and Akyildiz 1993](https://www.comm.utoronto.ca/~jorg/archive/papers/CS-93-65.pdf), read | Closed single-chain queueing network with blocking: deadlock-free if the job count is below the capacity of the smallest directed cycle | Fewer cars than the smallest ring holds | No. Our smallest rings hold about 20 cars. Good for a test scene |
| Liebeherr and Akyildiz, Theorem 1 | Several chains: deadlock-free iff for every buffer cycle at least one chain can't saturate it: Σ capacity + servers > its population | A ring is safe if too few cars route around it | Partly. Rings of FIFO lanes only need the heads to want it, so the theorem's chains don't map one to one |
| [Dally and Seitz 1987](https://resolver.caltech.edu/CaltechCSTR:5231-tr-86), via [Mendlovic and Matias 2025](https://arxiv.org/pdf/2503.04583), read | Deterministic routing is deadlock-free iff the channel dependency graph has no cycle | Lanes are channels, movements are dependencies. No ring of movements anywhere | No. See 3.4: 96.6% of used edges sit in one cycle-rich component |
| Glass and Ni 1992, turn model, ISCA, second-hand from a search snippet | In a mesh, banning some turns breaks all cycles | Banning movements in a grid would remove ring locks | As theory only. Real streets don't ban them |
| Duato 1993, IEEE TPDS, second-hand from a search snippet; [a 2026 paper](https://arxiv.org/pdf/2609.17057) uses it the same way | Adaptive routing may have cycles if a connected routing subfunction with an acyclic extended dependency graph exists: an escape network | **The nearest to human driving:** any route may form cycles, as long as an always-available fallback exists. Inference: "carry on, reroute" is the fallback | The right design idea. A real network has no strictly acyclic subnet, so this is an analogy, not a proof |
| [Bubble flow control](https://www.eecg.utoronto.ca/~enright/fbfc-pp.pdf), read in part | Forbid new injection into a ring when it would use the last free slot; one free slot keeps a ring moving | Keep one free car length on every ring | Metering a ring is an unusual rule for drivers. Exit-clear alone doesn't do this, see below |
| [Push and Rotate, de Wilde et al. 2014](https://jair.org/index.php/jair/article/download/10913/26020), read abstract; [diBOX, Botea, Bonusi, Surynek 2018](https://jair.org/index.php/jair/article/download/11212/26423/20783), abstract | Multi-agent path finding is complete with at least 2 empty vertices; diBOX extends this to strongly biconnected digraphs, except a degenerate cyclic class | **Locks are not necessary.** With full cooperation, any arrangement can be undone with two holes. Reversible moves aside, it covers directed roads | Tells you real locks are coordination failures, not space failures. Humans and police do this by hand at small scale |
| [Perronnet et al. 2019](https://i-cirena.ubfc.fr/node/10534), abstract | Sufficient condition for deadlock-free traffic with specified routes, using road reservation in a network of intersections | Needs a reservation server | AV only. Relevant to D8, not human traffic |
| [A-DRIVE, Aoki and Rajkumar 2022](https://arxiv.org/pdf/2204.04910), read in part | Detect and recover by a waiting-time threshold, then back up or yield. "These deadlocks happen even for human drivers" | Bounded wait is the established AV method too | Same principle as ours |
| [Wongpiromsarn et al. 2012](https://arxiv.org/pdf/1205.5938), read in part; Varaiya max pressure, second-hand | Max-throughput signal control, relying on "the assumption that all the queues have infinite buffer storage space" | No statement on real finite streets | No |
| [Gregoire et al. 2015](https://arxiv.org/pdf/1309.6484), read in part | Back-pressure loses work conservation under finite queues, and "in worst-case scenario, such congestion propagation can lead to deadlocks". Their normalised pressure is proven work-conserving and "mitigates" propagation | Signals can make it worse; a fix exists for one kind of it | Not deadlock-free in what I read |
| Le Boudec | Nothing on road deadlock found. [Thomas, Le Boudec, Mifdaoui](https://infoscience.epfl.ch/record/280256?ln=en) treat cyclic dependencies in time-sensitive networks: cycles can give "global instability", and regulators can break them | Same shape, different field | No |

**So: I found no condition under which a lane-and-signal network with fixed routes and FIFO lanes is provably free of deadlock, other than an acyclic dependency graph or fewer cars than the smallest ring. A real city meets neither.** Real networks are safe only in the probabilistic sense of 2.2.

**Two things that sound like fixes but aren't (inference, with a calculable check in scene S2).**

- *Keep-clear doesn't prevent a ring.* If every driver stops at the line with the exit full, four full links with heads wanting the next still lock. Their waits are at the stop lines instead of in the box. Keep-clear removes the coupling between crossing streams, not the ring.
- *Signals don't break a ring.* A link's green serves nothing while its exit is full.

### 3.4 What our files show

**Ours: the dependency graph.** Reading net `m12` and `routes_f05.rou.gz` (881,180 route entries): 8,725 edges and 17,254 movements used. **The largest strongly connected component holds 8,432 edges, 96.6%.** The smallest ring through an edge, by storage at 7.5 m a car, is 21 cars at p1, 54 at p10 and 103 at the median. 21 edges sit on a ring under 10 cars, 80 under 20, 342 under 40. These count all lanes of each edge, so a single-lane ring is smaller still. So Dally and Seitz's condition fails everywhere, and the smallest rings need about 0.1% of the 50% accumulation to close.

**Ours: the seeds.** Saved `cars-data/berlin2019/runs/*/jam/seeds.json`, top 15 seeds per run, sampled at 15 min, in the six runs `whya1`, `whyp`, `whyp2`, `why2`, `diag12`, `hunt_s5_s0`. Builds and drivers differ. `whya1` is report 23's assigned-routes run.

| Root held by | Vehicle-hours behind it | Share | Roots | Median first-to-last | Max | Held 30 min or more |
|---|---:|---:|---:|---:|---:|---:|
| Lane change | 3,042 | 44% | 26 | 30 min | 240 min | 65% |
| Signal | 2,207 | 32% | 43 | 30 min | 135 min | 53% |
| Yield | 1,502 | 21% | 17 | 60 min | 105 min | 82% |
| Leader | 121 | 2% | 2 | 15 min | 15 min | 0 |
| Exit full | 116 | 2% | 2 | 0 | 0 | 0 |

- **`jam.py` marks waiting rings. Across 12 saved runs, the share of top-seed vehicle-hours flagged as a cycle is 0 in nine runs, 4% in two and 5% in one.** Taken at face value, the formal deadlock is rare and a long-held head is the normal case.
- **That count is a lower bound.** Reading `jam.py` (`_from_why`), wait-for edges exist for leader, tail, junction foe and for a car at the very end of a lane. A car stopped mid-lane for a lane change (kind `accel`, decider `lane_change`), a yield and a signal end the chain as a root. A ring passing through one of those can't be seen. So the census should get edges through lane-change and yield waits before anyone concludes rings don't matter.
- **A signal root held 135 min isn't a human waiting.** Either that connection never gets a green, or the label hides something else. Report 23's worst edge lost 118 s per pass on a joined controller. This one is probably input, not driver.

**Inference: the arithmetic of why a hold spreads.**

Spill time: a head held for D seconds fills an edge of length L when D > L / (7.5 × q).

| Edge length | At 300 veh/h | At 600 veh/h | At 900 veh/h |
|---|---:|---:|---:|
| 56 m (p25) | 90 s | 45 s | 30 s |
| 98 m (median) | 157 s | 78 s | 52 s |
| 158 m (p75) | 253 s | 126 s | 84 s |

Little's law: active seeds N = λ × D. Cutting D from over 30 min to about 1.5 min cuts concurrent seeds about 20 times at the same seed rate λ, and most holds then end before spilling.

R0 at street scale: with k = 2-3 upstream movements, contagion dies if the share of holds longer than spill time is below 1/k. Absorbing holds have share 1.

**So the release time we need sits right at 1-3 minutes, and real waits measured so far sit below that.** I-80: median 22.6, p99 72.7, max 79 s, 0 of 610 failed in a 204 m view. Lankershim and Peachtree urban turners: about 4-5, 27, 33 s. Report 14, measured. These are window-limited, and from places where cars do get in.

## 4. Mechanisms, ranked

Rank is by how much I expect a mechanism to affect a lock at 50% and 100%. It is my judgement from section 3 and report 23's rounds, not a measurement. Each row's last column is what `grep` shows on `main` at 97ff609, with branches named.

| # | Mechanism | Real size, best source | Status | Plausible network effect | In `cars` |
|---:|---|---|---|---|---|
| 1 | Give up the lane or turn, go on | No share found. Miss costs about 2 min. 0 of 610 at I-80 | Behaviour established, size unknown | **Large for release.** 44% of root hours. Alone not enough: `lost60` on physics at 10% was the best of its batch but still 1.83 × healthy | Main: no. `lost_after` removes, off. Branches: partly |
| 2 | Waits at yields end: gap falls, forcing, being let in | Gap −0.015 s per s waited (Polus). Followers yield 39-68% | Established at long waits | **Large for release.** 21% of root hours, the longest holds | Partly. Wait term in gap test, scaled at 180 s |
| 3 | Forced and cooperative lane changes in dense queues | 32-41% start overlapped; ours 0 | Established | **Medium to large.** Lowers how often mechanism 1 is needed | Partly. On branches, no sideways start |
| 4 | Routes that fit lanes, avoid hard moves | Removing U-turns moved a lock to a finish (ours). No left-turn coefficient found | Established here | **Large, mostly done for U-turns.** Left turns and road hierarchy remain | Router has `turnaround_s`; no left-turn or hierarchy term found |
| 5 | Junction blocking is common and porous | Enter blocked box at 55-89%, 74% of blocked time partial | Measured, 6 US sites, sign unclear | **Unknown sign.** Could be large | 100% on main, 90% physical. No bypass inside junction |
| 6 | Change route on the way | Up to 50% in major accidents. About 20% off plan. Google under 2% | Established for incidents, small on normal days | **Large in recovery, small on normal days.** Theory: raises the critical density | Main: no. `cars-assign` at 300 s pauses, off by default |
| 7 | Demand adapts between days | Median −11% when capacity is cut; peak shift 3-4 min | Established, wide range | **None at 50%.** Some at 100%. Boundary of what a day test means | `cars-assign` only |
| 8 | Finishing on yellow, entering on red | 3-5 per 1,000 vehicles; no spillback figure | Measured for normal traffic | **Small** | Yellow yes, physical only. Red only when it can't stop |
| 9 | Driving over markings, turn lane to pass | No field measure found | Speculative | **Unknown**, likely local | No |
| 10 | Leaving the road, backing, waving through, police | Only event reports | Speculative on normal days | **Small on normal days** | No |

### Mechanism 1. Give up the lane or turn, and go on

**What it is.** A driver who can't get into the lane for a turn stays in their lane, drives past and finds another way. It turns a wait for one target into a wait for any way forward.

**Measured.**

- Report 14, measured: at I-80 all 610 cars got in, wait max 79 s. Missed turns aren't visible in urban tracks.
- [Wei et al. 2024](https://transportlab.sydney.edu.au/wp-content/uploads/2024/07/JW-MR-DL-TRB-2024.pdf), via report 14: a missed exit costs about 2 minutes on Twin Cities trips.
- Bounds, not shares: [Seoul navigation logs](https://wctrs-society.com/wp-content/uploads/abstracts/lisbon/general/03376.pdf), read in part: route deviation 6-22% on weekdays, 5-13% at weekends, including deliberate deviations. [Papinski, Scott, Doherty 2009](https://experts.mcmaster.ca/scholarly-works/292020), abstract: about a fifth of 24-31 Ontario commuters left their planned route.
- I searched again for a measured share of missed turns or exits per trip. **I found none, and report 14 didn't either.**

**Status.** Behaviour established; size unknown.

**Network effect, and how I know.**

- Source: [Rickert and Nagel 1997](https://arxiv.org/pdf/adap-org/9705002), read: the heads forced into blocked lanes form a ring and this "cannot be seen in real-world traffic". Report 15: every tool I read that handles this lets the car lose its turn.
- Ours: 44% of root hours. `sw_p_lost60` in `rounds.csv` (remove after 60 s at lane end, physical, 10%) gave 2,562 cars at 07:30, the lowest in that batch, still 1.83 × healthy.
- So it matters and isn't enough. No published network study isolates it.

**In our simulator.**

- `main`: `P.lost_after`, default 0 (`world.rs:812`), removes the car (`step.wgsl:1814`). With teleports off, a wrong-lane head waits for ever. `route.wgsl:pick_link` returns only a link to the wanted edge.
- `t3/1c6fee50` commit 104d433, today 18:15: `ph_reroute`. Patience 60 s × 0.5-1.5 per driver, needs `route_arena > 0`, a green and **`it.dist <= 15`**, no wait on lanes under 15 m. `t3/1b36c9cf`: `hu_reroute`, mean 120 s. No Berlin result yet in `research/physics-rounds.md`.
- **Check this now.** In the saved top seeds, 16 of 26 lane-change roots, 1,900 of 3,042 vehicle-hours, stand more than 15 m before the lane end. `lc.wgsl:959` keeps a blocker margin of 20 or 40 m (`getExtraReservation`) for cars needing two or more changes, and line 965 a car length for a neighbour. I didn't check which applies to each root. As written, the rule doesn't reach those cars. Those runs predate the rule and the driver has changed since, so this needs one count on a current trace.

**Smallest correct form.** Reuse `ph_reroute`, changing only the trigger: stopped with a lane-change wish as the reason, for longer than patience, anywhere in the last 100 m. Keep it a choice of continuing link, not a removal, and report lost cars per 1,000 trips. Start at 60-120 s because that's the spill time and just above real p99.

**Scene S3, wrong-lane head.** Two lanes in, lane 1 through only and lane 2 right turn only. Lane 1 is saturated with no gaps, no signal, h = 2 s. A share f of lane-2 cars wants through. Lane-2 flow = 3600 / (h + f·T̄).

| f | T̄ | Expected lane-2 flow |
|---:|---:|---:|
| 0 | | 1,800 |
| 0.05 | 60 s | 720 |
| 0.1 | 60 s | 450 |
| 0.1 | 120 s | 257 |
| 0.1 | never | **0** |

**Scene S4, held back from the end.** The same scene with `lc_blocker` holding the head 30 m before the end. It must give the same flows. Today's `it.dist` guard should fail this.

**Scene S4b.** A real lane drop has no through link, so nothing to skip. Rule must not fire there: 0 of 610 at I-80 failed.

### Mechanism 2. Waits at yields end

**What it is.** Drivers accept shorter gaps as they wait, eventually force the foe to brake, and get let in. Inside a junction, a left-turner clears when the opposing stream stops.

**Measured.**

| Source | Result | Read how |
|---|---|---|
| [Polus, Shiftan, Shmueli-Lazar 2005, EJTIR](https://journals.open.tudelft.nl/ejtir/article/download/4329/4227) | 7 Israeli roundabouts, 743 sampled gaps, `v = −10.34 + 0.03742·wait + 2.509·gap`. A 3 s gap accepted 7%, 13%, 24% after 5, 25, 45 s. 6.7 s of waiting buys 0.1 s of gap. Gaps under 2 s not taken, over 5 s taken regardless. Wait includes queueing. They warn against extrapolating | Read |
| [Polus and Shmueli-Lazar 2003](https://ascelibrary.com/doi/10.1061/%28ASCE%290733-947X%282003%29129%3A5%28504%29) | S-shaped fall between a maximum and minimum critical gap. "Significant increase in entry capacity", especially at high circulating flow | Abstract |
| [Mahmassani and Sheffi 1981](https://ideas.repec.org/a/eee/transb/v15y1981i3p143-148.html) | The critical gap is "decreasing on the average" as drivers wait. Probit on gap sequences | Abstract; no number seen |
| [Daganzo 1981](https://trid.trb.org/View/168104) | Mean critical gap significantly smaller than mean critical lag (per Polus 2005). Not a direct wait law | Second-hand |
| [Kaysi and Abbany 2007](https://doi.org/10.1016/j.aap.2006.10.013) | Models minor-road drivers who force the major stream to slow. Keywords forcing, aggressive behaviour. **Numbers not seen** | Record |
| Report 14, measured | Swiss roundabouts, waits median 1.4 s, p99 11.4 s: accepted gaps don't fall under 20 s. I-80 merging: waiting has no effect once distance is known | Ours |

Consistent reading: nothing at short waits, a clear effect past about 25 s. Polus's elasticity starts at zero.

**Status.** Established at long waits on roundabouts; thin elsewhere.

**Inference, with numbers.** Polus's law gives `tc(w) = 4.12 − 0.0149·w`: 4.12 s, 3.75 s at 25 s, 3.23 s at 60 s. With tf = 3 s, Siegloch capacity rises 10%, 22%, 35%, 56% at major flows of 400, 800, 1,200, 1,800 if every head has waited 60 s. Counting only time at the head, a small Monte Carlo gives 0%, 0%, +1%, +8%. **The mean barely moves. The tail does.** Using HBS's tc 5.9 s with Poisson major flow:

| Major flow, veh/h | Mean wait, fixed gap | P(wait > 120 s), fixed | P(wait > 120 s), gap falling at Polus's rate, floor 2 s | P(wait > 300 s), fixed | Falling |
|---:|---:|---:|---:|---:|---:|
| 1,200 | 21 s | 0.4% | 0% | 0 | 0 |
| 1,800 | 38 s | 4.3% | 0.6% | 0.04% | 0 |
| 2,400 | 77 s | 21% | 4.9% | 2.0% | 0 |
| 3,000 | 164 s | 48% | 19% | 16% | 0 |

So this behaviour matters less for capacity than for ending the holds that spill.

**Network effect.** Ours: yields are 21% of root hours, the longest-held kind. Report 23: `impatience` 0.25 at 50%, −11%, the only yield test run. San Francisco (report 15): a 20% cut in gap acceptance or follow-up time cleared moderate gridlock, in a meso model.

**In our simulator.**

- `step.wgsl:846, 1259`: `impat = clamp(ty.impatience + wait / P.time_to_impatience, 0, 1)`, default 180 s, softens the foe's assumed braking in `foe_arrival` (1027-1048). So a wait term exists. Report 23's bug: for same-target merges it pushed the needed gap to 12 s; fixed for physical mode at 1063.
- Physical driver: fixed `tc` (`world.rs:1162`). Round 3 on the branch uses `tc_scale` × 0.7; minor flow now 693/526/300 against Siegloch 736/451/277 (`physics-rounds.md`).
- Tie-breaks: `CH_EQ` right-before-left backs out at random after 5 s (719-725); all-way `CH_w` lets the longer waiter go (1055-1057).
- **Saved yield roots still hold a median 60 min**, on Krauss and physical. Some are on internal lanes (`:cluster_…`, pos 26.9 of 27). So the wait term doesn't bound the hold. Why needs `cars why` on `whya1` rank 2 and 3. I didn't run it.

**Smallest correct form.** Keep `tc`, subtract Polus's slope after about 25 s of waiting, floor 2 s. After a further bound, the head may enter when the foe can brake at Vissim's 3 m/s² (report 18's B_F). That is the forced entry. Inside a junction, a left-turner clears on the phase end. Add a why probe for each.

**Scene S7.** Saturated minor approach, Poisson major at 1,200, 1,800, 2,400 veh/h. Expected capacity from Siegloch 277, 133, 64 (5.9, 3.0) in the fixed case, and the tail table above in the falling case. Pass means head wait p99 within ±20% of the table and no head over 300 s.

### Mechanism 3. Forced and cooperative lane changes in dense queues

**What it is.** In a queue, a gap is made by pressing into it. The car starts sideways before the room exists, and the follower gives way, partly.

**Measured** (report 18 and 14, ours). 32-41% start sideways with a target-lane car overlapping (13% at US-101, under 2% at the A39), **ours 0**. Gaps are half made when the car starts: lag median 4.4-7.4 m, p25 1.6-3.0 m against ours at 6.7 m. Followers apply 39-68% of asked braking, about 1 in 7 respond visibly. At I-80, 59.4% let in per chance, up to 5 pass.

**Sources.**

- [Hidas 2002, TR-C 10](https://doi.org/10.1016/s0968-090x(02)00026-8), second-hand: only the forced and cooperative models gave realistic flow-speed relations in congestion.
- [Hidas 2005, TR-C 13](https://doi.org/10.1016/j.trc.2004.12.003): **observed shares of free, forced and cooperative still not opened**, also in reports 15 and 18.
- [Laval and Daganzo 2006](https://doi.org/10.1016/j.trb.2005.04.003), via report 18: lane changers as particles with bounded acceleration leaving voids. It explains capacity drop, not locks. [Daganzo and Laval 2005](https://escholarship.org/uc/item/1hp588xx), record only, is the moving-bottleneck method behind it.
- "Wang et al." in the brief: I couldn't identify the paper meant.
- [Trafikverket Handbok p. 106](https://bransch.trafikverket.se/contentassets/32ce05ecc3ac458bb8ecb802e8e2da54/handbok_for_kapacitetsanalys_med_hjalp_av_simulering.pdf), via report 15: two cars with the same stop position lock the approach. Offset the stops by at least 7 m.
- Gomes and the look-back route: see [report A](A-how-simulations-are-built.md), finding 3.

**Status.** Established.

**Network effect.** Report 23 ranks "cars blocked abreast" third. Round 5 on the physical branch: the abreast rule "never fired on my fixtures or the Rahel-Hirsch cut". So it may be rarer now than the single-car lane-change hold. I can't size it further.

**In our simulator.** `lc.wgsl` LC2013: strategic, cooperative, speed-gain, keep-right. No swap on `main`. `t3/1c6fee50` 0cea2c0 `ph_abreast`: the one behind falls back. `check_blocked` and `inform_follower` do the asking. No sideways start before the gap exists on any branch I checked; report 18's B3 specifies it. Report 15 audit: swap and forced yield "have no source"; force-yield is ours alone.

**Smallest correct form.** Report 18's B3 (edge in, commit on anticipated gap) and B7 (follower takes a share, tapered). Nothing new here. Add offset stop points by hash, ≥7 m, as Trafikverket does, before any swap.

**Scene S5, abreast.** Two lanes, each head wanting the other's lane, both stopped, a queue behind each. With offsets ≥7 m, the rear head has room to move in once the front moves. Expected: both done within 30 s (I-80's median is 22.6 s). Both lanes back at saturation flow after. **Scene S6, lane drop.** 1,300 + 1,300 veh/h. Expected total 1,800 ± 10%, shares near 1:1, wait median about 20-25 s, max under 80 s, 0 failed (report 14's I-80).

### Mechanism 4. Routes that fit lanes and avoid hard movements

**What it is.** Real routes don't come from an edge-level shortest path. Drivers avoid U-turns and difficult left turns, and prefer main roads.

**Measured.**

- Ours, report 23: 29.3% of vehicles had a U-turn; removing them moved a lock from midday to a finish. `cars lanes`: 14.3% of trips can't be driven lane by lane at 3 s per change, 2% after feeds. Volume at 15 May: primary −22%, secondary +13%, tertiary +26%.
- Barcelona and San Francisco (report 15): time-only routes underload main roads; hierarchy preference improves fit.
- Left turns: [UPS-style software uses about 20 s per left turn](https://blog.route4me.com/?p=1071), [Waze offered left-free routes](https://www.mactrast.com/2016/06/popular-navigation-app-waze-working-put-end-left-turns/amp/). Operating values, not measurements. **No published coefficient opened.**
- [Elmegreen 2023](https://arxiv.org/pdf/2401.00882), modelled: gridlock tends to occur where a few long roads channel a large share.

**Status.** Established here for U-turns; hierarchy established; left-turn size unmeasured.

**Network effect.** The largest single change report 23 found. Report 23 also found 25 assignment iterations gave only −7%, so routes alone don't hold it.

**In our simulator.** `cars-assign`: `turnaround_s = 300`, per-class graphs. I found no left-turn or hierarchy cost term in `cars-assign` or `router.rs`.

**Smallest correct form.** Add a per-movement cost in `cars-assign`: left turn across traffic, turn from a lower-class road, and a lane-feasibility penalty from `cars lanes`. Fit on GPS if ever available; otherwise sweep and report.

**Scene.** Two routes of equal free time. One has one unsignalised left turn across 800 veh/h. Expected: the left-turn route's delay is the Siegloch wait (tc 5.9, tf 3.0: capacity 451, so at 100 veh/h about 10 s). A converged assignment should shift share until times match. Counted, no network needed.

### Mechanism 5. Junction blocking is common and porous

**What it is.** Law forbids entering a junction you can't leave. Drivers do it often anyway. When they do, others often go round.

**Law, read.**

- Germany [StVO § 11(1)](https://www.gesetze-im-internet.de/stvo_2013/__11.html): if traffic is stopped, despite priority or green nobody may enter the junction if they would have to wait in it. § 11(3): even someone with priority must waive it if the traffic situation requires, and "auf einen Verzicht darf man nur vertrauen, wenn man sich mit dem oder der Verzichtenden verständigt hat". § 11(2): form a free lane for emergency vehicles when stopped.
- Sweden [3 kap. 20 §](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/trafikforordning-19981276_sfs-1998-1276/): adapt so that no "onödigt hinder" arises for traffic on the crossing road if forced to stop.
- UK [Highway Code rule 174](https://www.gov.uk/guidance/the-highway-code/using-the-road-159-to-203): "You MUST NOT enter the box until your exit road or lane is clear", except waiting to turn right.

**Measured.**

| Source | Sites | Result |
|---|---|---|
| [Saroj et al., GDOT 14-43, poster](https://stride.ce.ufl.edu/wp-content/uploads/sites/153/2019/01/Saroj_Abhilasha_Poster.pdf), read; [full report](https://rosap.ntl.bts.gov/view/dot/36121) too large and blocked | 6 Atlanta sites, before and after signs, 4-10 h per period | **Propensity to block when a chance exists: 0.71, 0.68, 0.86, 0.83, 0.55, 0.73 before; 0.61, 0.89, 0.62, 0.67, 0.83 after.** Pooled 75% (my sum, 2,422 of 3,215, leaving out one period with too little data). Signs had no consistent effect |
| Same, microsimulation of one four-leg junction | Blocking likelihood 0-100% | Delay stable up to 20%, then rises fast; failing level by 40-50%, extreme at 80-100% |
| [Harris 2014, Georgia Tech thesis](https://nctspm.gatech.edu/sites/default/files/u60/HARRIS-THESIS-2014.pdf), read Tables and §4-5 | 6 Atlanta sites, 3-31 days | Share of green with blocking: 5.6, 2.5, 10.9, 17.2, 10.3, 43.6%. **Partial blocks, where others go round in another lane, are 67-92% of blocked time, 74% pooled** (my sum). His capacity weights (a full block passes half, a partial block 75% of saturation flow, on an assumed two-lane approach) are "based on judgment" |
| [Stringer 2006, via Streetsblog](https://nyc.streetsblog.org/2008/06/23/dont-block-the-box-bill-clears-albany) | 10 Manhattan sites, one period (accounts differ: 9 hours or 5 days) | Over 3,000 violations, no tickets |
| [Mataram, Indonesia 2025](https://scholar.unram.ac.id/papers/W4408073861), abstract | 1 site, motorcycle-heavy | 13.82% of vehicles violated. A different denominator |
| Germany, Sweden | | **No measure found.** |

**Status.** Blocking measured for US activity centres. No European number. The effect on locks isn't measured.

**The puzzle (inference).** Simulation of blocking fails at 40-50%, while real sites run at 55-89%. Those sites are congested, and blocked green reaches 44% at one site, but none reports a gridlock that needs police. Two readings: real boxes clear faster than modelled ones, or real blocks are mostly partial and modelled ones are mostly full. Harris's 74% partial favours the second. So what lets real traffic survive may be **porosity**, not compliance.

**In our simulator.**

- Krauss: `check_rewind` and `keep_clear` (`step.wgsl:837-952`) from SUMO. `keepClear` defaults true (`net.rs:445`), so every driver keeps clear on links with foes.
- Physical: `ty.exit_comply`, tune default **0.9** (`world.rs:613`), per driver by hash, with Vissim's "wants room plus 0.5 m" and a blocker test "under 5 m/s and under 75% of what it wants" (`step.wgsl:787`). Report 23: turning off `exit_clear` at 10% gave 3,228 against 2,947-3,918: no clear gain, one seed.
- Bypass: conflict zones come from swept paths (report 09), so a blocker in one lane's path doesn't block a path that misses it. But no lane change on internal lanes.
- `P.ignore_blocker` exists and is off by default (1e9).

**Smallest correct form.** First measure. Run `propensity = entered with no exit room / chances` on real drone data we already hold (DLR Urban Traffic, Helsinki, inD/SinD where queues exist). Then sweep `exit_comply` over the measured range and compare the jam-lifetime metric, not "lock or no lock". Don't build bypass until that sweep says it matters.

**Scene S8.** One signal, cross street with 30 s green in a 60 s cycle, s = 1,800 per lane, downstream hold that releases in τ = 10 s at the start of the cross green. Cross-street capacity = s·(g − b·τ)/C. For b = 0: 900 veh/h. b = 0.75: 675. b = 1: 600. On a two-lane cross street where every block is partial, the other lane keeps running, so the average per lane at b = 0.75 is s·(g − 0.5·b·τ)/C = 788. Pass means within 5%.

### Mechanism 6. Route changes on the way

**What it is.** Driver sees a jam, takes another way.

**Measured.**

- [Knoop, Hoogendoorn, van Zuylen 2010](https://doi.org/10.1016/j.proeng.2010.07.012), abstract, loop detectors on incident days: **"up to 50%" deviate for major accidents**, more for an accident than for the same delay without one.
- Report 06, measured: 13.5% of commutes follow the shortest-time path exactly; Google moved under 2% of trips by about 30 s.
- [Zhu et al. 2010](https://experts.umn.edu/en/publications/the-traffic-and-behavioral-effects-of-the-i-35w-mississippi-river/), abstract: I-35W collapse disturbed 140,000 daily trips; several weeks to re-equilibrate; most drivers found routes with no change in travel time.
- [Shapouri et al. 2025](https://repository.lsu.edu/civil_engineering_pubs/1210), abstract: 20 million Sydney GPS trips; experienced delay and remaining distance raise diversion, extra expected time lowers it. **Share not available**: full text removed. Dissertation has 90 events, logit misclassification 15.4%.
- [Chicago stated and reported surveys, Khattak et al.](https://trid.trb.org/View/378100), abstract: radio information raises diversion over self-observed. Shares not seen.

**Status.** Established for incidents; small on normal days.

**Network effect, and how I know.** DGG: critical density rises with α; Gayah and Daganzo: loops fade with adaptive drivers; Olmos: gridlock resolves "due to the rerouting possibilities". All modelled, and DGG's "real drivers adapt" reading of Yokohama carries a "probably". Report 06's toy: +1.3% on a normal day, 2.5 times in mean trip time in an incident, and reacting too hard is worse. Report 20 notes there is no field proof of the critical-density effect. So: **high value in recovery, low on a normal day below critical.** Since we lock below critical, it won't fix the seeds; it limits how far they spread.

**In our simulator.** `cars-assign/src/enroute.rs`: "En-route rerouting and incidents, at the 300 s pause between bins. Off for baseline days". Kernel: none, other than the branch reroute of mechanism 1. Note the unit difference: DGG's adaptive driver uses a local rule at each junction, "don't turn into the more congested link", not a global re-plan.

**Smallest correct form.** Mechanism 1's reroute plus: a share α of drivers, on reaching a junction whose next link is stopped, asks for a new route if an alternative exists. Rate-limited, as report 06. Reuse the same `route_patch` channel.

**Scene S1, two tangent rings (DGG).** Two 1 km one-lane rings touching at one point, closed, v = 50 km/h, w = 20 km/h, kj = 133/km, turn share 0.05, slow loading.

| | Expected |
|---|---|
| Rigid, below kc = 38/km (76 cars total) | Flow follows the fundamental diagram, about 1,900 veh/h at kc |
| Rigid, above kc | Rings unequal, flow below the diagram |
| Rigid, at kT ≥ kj/2 (133 cars total) | **One ring jammed, total flow near zero. Same for any turn share** |
| α = 0.3 | Bifurcation near 52/km |
| α = 0.8 (above α_c = 0.6) | No lower branch. Follows the diagram to kj/2 |

### Mechanism 7. Demand adapts between days

**What it is.** People leave earlier, go elsewhere, or don't go.

**Measured.**

- [Cairns, Atkins, Goodwin 2002](https://nacto.org/docs/usdg/disappearing_traffic_cairns.pdf): pdf blocked to me; numbers via [Nello-Deakin 2022](https://ddd.uab.cat/pub/artpub/2022/0aac865e4d2e/1_s2.0_S2213624X22002085_main.pdf), read: of 70 capacity-reduction schemes, 51 fell and 11 rose; **median −11%**, wide spread; partial capacity reductions in later work −5 to −25%. Barcelona's tactical schemes: −15.4% on the street itself, relative to control streets. Whether it holds at city scale is "poorly understood".
- [Duranton and Turner 2011](https://www.nber.org/papers/w15376.pdf), abstract: vehicle-km "increases in exact proportion to highways" in US metro areas, in the long run.
- Report 06: Bangalore experiment, peak charges shift departures 3-4 min. Report 15: Stockholm trial, observed cordon −18.1%, by price.
- [Anderson and Davis 2020](https://www.nber.org/papers/w24469.pdf), read in part: three California freeway bottlenecks, "no discernible capacity drop whatsoever" and no hypercongestion; "our results do not speak to" dense street networks.

**Status.** Established with a wide range; time scale is days to months.

**Network effect.** At 50%, none: real drivers at twice that load don't need it. At 100%, it matters in two ways. **Real demand is already shaped by real capacity**, so cities sit close below critical, and a model with capacity at 57% of reference at a junction faces a demand it can't serve, even at full fidelity. And [MATSim's demand](../23-berlin-2019-first-gate.md) was equilibrated on MATSim's own capacities (report 23 on 900+ veh/lane/h edges), not on these lanes. So this isn't a kernel question.

**In our simulator.** Departure-time stage in `cars-assign` per report 06. Near collapse it made a toy worse.

**Smallest correct form.** Don't add to the kernel. Fix capacity and routes, then apply report 06's capped loop. Report results as a function of demand.

**Scene.** Vickrey bottleneck: N = 3,600, s = 1,800/h, α = 1, β = 0.5, γ = 2. Rush length 2.0 h, peak delay N/s × βγ/(α(β+γ)) = 0.8 h. That is `cars-assign`'s test, not the driver's.

### Mechanism 8. Finishing on yellow, entering on red

**Measured.**

- [TTI report 4027](https://library.ctr.utexas.edu/hostedPDFs/tti/4027-S.pdf), search snippet: typical approach 3-5 red runners per 1,000 vehicles; flow explains about 58%. Melbourne 3.9, Puerto Rico 18.8 per 1,000 (snippets). Erbil: 51% within 2 s of red; violations rise with delay (snippet).
- Yellow: report 05, 1,357 decisions, logistic in time to line, 5.1 s scale 0.54.
- **No figure on red entry during spillback found.**

**Status.** Measured for normal traffic.

**Network effect (inference).** At 5 per 1,000 and 20 cars per cycle, one in ten cycles per approach. As a release from a lock, small. Inside a junction, cars already clear: no red there. **Small.**

**In our simulator.** `step.wgsl:117-128`: `ph_yellow_go` from report 05, `ph_goes_through` only when stopping would ask over 3 m/s². Physical mode only. Krauss follows SUMO's rule.

**Smallest correct form.** Leave it. Scene: a single approach, 1,357 decisions' curve, already in report 05's test set.

### Mechanism 9. Driving over markings, using a turn lane to pass

**Measured.** I searched for field shares twice and found none. UK self-report: 9.9% would cross a solid white line for slow vehicles, [insurer survey](https://www.quotezone.co.uk/car-insurance/guides/61-of-uk-drivers-would-fail-their-test-today), weak. Harris's partial blocks imply going round happens. Report 20: width factors small; two abreast rare in Nordic queues.

**Status.** Speculative.

**Network effect.** Unknown. DEBUGGING.md's `804669067`: a solid line split held 297 cars in 30 min of a cut. So markings in the *map* can seed a lock. Solid lines close to a junction also make Aimsun cars miss turns (TfL, report 15).

**In our simulator.** `lanes[...].pad0/pad1` hold change permissions; a solid line is absolute. `lc.wgsl:210-213`.

**Smallest correct form.** Measure first: count lane changes across solid lines in the last 30 m on pNEUMA, DLR Urban Traffic and Lankershim. If over a few percent, let the Mechanism 1 rule cross a marking when held past patience, at crawl speed.

**Scene.** Two-lane approach with a solid line over the last 40 m, a car wrong-laned behind it. With the crossing rule on: it crosses, flow returns. Off: S3's result.

### Mechanism 10. Leaving the road, backing, waving through, police

**Measured.** Only events: I-95 motorists "make a path", cars abandoned in Atlanta. Law supports waiving (§ 11(3)). No normal-day rate. A-DRIVE uses backing as a formal recovery step in AVs, and notes one-lane roads use turnouts. Report 20 row 15: narrow two-way streets can stand off here, because opposite driving is omitted (`lc.wgsl:3`).

**Status.** Real, unquantified.

**Network effect.** Small on a normal day. Could matter locally on narrow Berlin side streets, but those aren't the top seeds I saw.

**In our simulator.** None. Service roads and kerb trips are absent (report 20).

**Smallest correct form.** Nothing yet. If one-lane stand-offs show up in the census, report 20's bounded opposite-lane rule.

## 5. How other simulators handle it (facts, not references)

What each one stands in for is my reading. [Report A §4](A-how-simulations-are-built.md) has more on valves.

| Tool | Mechanism | Value | Stand-in for | Source |
|---|---|---|---|---|
| **Vissim** | `DiffusTm`: waited at emergency stop position for a needed lane change, then "removed" with a warning | **60 s** default per [hEART 2019 sensitivity](https://transp-or.epfl.ch/heart/2019/abstracts/hEART_2019_paper_150.pdf) (tested 10-120) and [Louisiana DOTD sheet](https://dotd.la.gov/media/ggmgprf1/vissim-calibration.pdf), snippet; PTV's own page shows no default | Missed turn | [PTV 2022](https://cgi.ptvgroup.com/vision-help/VISSIM_2022_ENG/Content/4_BasisdatenSim/FahrverhaltensparameterFahrstreifenwechsel_bearb.htm), read |
| Vissim | Emergency stop distance, lane change distance | 16.4 ft (5 m), 656 ft (200 m). [TxDOT](https://www.txdot.gov/manuals/des/tsp/chapter-13-microsimulation-analysis/13-5-calibration/13-5-3-calibration-parameters-and-best-practices/13-5-3-1-vissim-calibration/13-5-3-1-1-lane-change-parameters.html): default "may cause vehicles to switch lanes too late". Louisiana: arterial over 1,500 ft, freeway over 2,500 ft | Look-ahead | Read and snippet |
| Vissim | Conflict area "avoid blocking" share, gaps 0.5 s, cooperative braking −3 m/s² | Percent per conflict area | Keep-clear compliance | Report 15 |
| **Aimsun** | Zone 3: stop if needed, then after Maximum Give Way Time + Additional Waiting Time Before Missing Turn, carries on in lane and counted **Lost Inside/Outside** | Additional 0 s per [TfL p. 197](https://content.tfl.gov.uk/traffic-modelling-guidelines.pdf), range ±3600. Give way time, cars mean 10 s, dev 2.5, range 5-15; trucks 25, buses 35 ([Auckland project table](https://www.aucklandcouncil.govt.nz/ResourceConsentDocuments/Further%20s92%20response-Attach1-Updated%20ITA-AppJ-App%20A%20to%20I%20_3Mar23%20%281%29.pdf), not vendor text; arterial additional about 25 s, column alignment unclear) | Missed turn, the closest to reality of any | [Aimsun manual](https://docs.aimsun.com/next/latest/UsersManual/MicrosimulationModellingVehicleMovement.html), TfL, read |
| Aimsun | Gap falls from MaximumGap to MinimumGap between Initial and Final GW Time Factor × give way time | Per vehicle | Gap falling with wait | [Aimsun manual](https://docs.aimsun.com/next/latest/UsersManual/MicrosimulationModellingVehicleMovement.html), plus a local copy of its node editor page, read |
| Aimsun | "Imprudent lane changing": up to twice max decel. Yellow box flag. Meso queue jump | Option | Forced entry, keep-clear, teleport | Report 15, report A |
| **Paramics** | "Signposting" distance per link, aggression and awareness "abstract values" with "no measurable or recorded values"; no lost-vehicle concept; **no stuck rule established** | Normal distributions kept by RTA guidance | Look-ahead, driver spread | [RTA manual](https://www.aldridgetrafficcontrollers.com.au/ArticleDocuments/295/paramicsmanual_i.pdf.aspx), read in part; [Hidas 2005](https://www.witpress.com/Secure/elibrary/papers/UT05/UT05075FU.pdf), read |
| Paramics in practice | [Vectos for Stevenage, 2017](https://www.stevenage.gov.uk/documents/planning-policy/examination-of-our-local-plan-2011-2031/examination-documents/ed144-vectos-supplementary-paramic-modelling-overview-19-1-17.pdf): "results have been quoted from those model runs which did not experience gridlock", because "the gridlock effects are not entirely realistic". Also: "If the model does not lock up every time it can be concluded that the problem is not severe" | Run seeds, discard the locked ones | The whole question | Read |
| **MATSim** | `stuckTime`: front vehicle moved across junction despite full storage. `removeStuckVehicles` false "is probably the better choice" | **10 s** in code; a [Sioux Falls config](https://svn.vsp.tu-berlin.de/repos/public-svn/matsim/scenarios/countries/us/sioux-falls/output/output_config.xml) and a [2025 talk](https://matsim.org/conferences/mum2025/presentations/mersini.pdf) say 30 s; [the talk](https://matsim.org/conferences/mum2025/presentations/mersini.pdf) says usually not scaled with sampling | Squeezing, forcing, going round; lack of lanes | [Source](https://matsim.org/doxygen/_q_sim_config_group_8java_source.html), [book](https://depositonce.tu-berlin.de/items/2f32d929-adb9-4e73-9bf1-ee0f132ec1aa/full), via report 15; book's evidence is "unfortunately never published" |
| **TransModeler** | [Caliper on version 8](https://www.caliper.com/transmodeler/new-features-transmodeler-8.htm): drivers "more adept at maneuvering around incidents and queuing", "averting gridlock". Mandatory lane change parameters exist, no lane change on a connector ([NCDOT](https://connect.ncdot.gov/resources/safety/Congestion%20Mngmt%20and%20Signing/Congestion%20Management/NCDOT%20CONGESTION%20MANAGEMENT%20SIMULATION%20GUIDELINES%20-%20TransModeler.pdf)) | **No stuck or removal rule established**; manual not open | Unknown | Provider claim, read |
| **CORSIM / NETSIM** | "**Spillback probabilities**": a global parameter for vehicles in a queue joining a downstream queue and blocking the junction. Enter 0 for "no vehicles will block". Left-turn jumpers and laggers, stochastic | Calibrate to local conditions; default values not in what opened | Junction blocking, explicitly | [FHWA Toolbox vol. IV §5.7, FAQ](https://ops.fhwa.dot.gov/trafficanalysistools/tat_vol4/vol4_guidelines.pdf), read |
| **ARTEMiS** | Max Wait Time, then removed as lost. 5 s too short, 60 s fine | Hidas 2004 | Missed turn | Report 15, local copy |
| SUMO | Teleport after 300 s, optional ignore-blocker | 300 s, reasons logged | Everything | Report 15 |
| **`cars`** | Off by default in the gate. See mechanisms | | | Ours |

**Inference.** Every tool I could read has a stand-in, between 10 and 300 s. Most sit at or under the 1-3 minute spill time, with SUMO's 300 s above it. The tools differ in what happens next: removal (Vissim), carry on and be counted (Aimsun), push through full storage (MATSim), lift ahead along the route (SUMO). **Only Aimsun's matches what a driver does.** Guidelines treat all of them as errors to audit (report 15). A driver who goes past a turn isn't an error, so I would audit lost cars per 1,000 trips, rather than require zero.

## 6. Has a micro model run a real network at full demand with no removal?

**I found none.** Report 15 and report A reached the same answer by different reading.

| Model | Scale, demand | Release used | Note |
|---|---|---|---|
| Barcelona, SUMO, 2022 (report 15) | 182 km², 2.06 M trips, 24 h | About 5% of cars teleported | |
| BeST Berlin, SUMO | 2.25 M trips | 2,332 teleports (0.10%) | About 58% of counted traffic (report 03) |
| MoST Monaco, SUMO | 46,842 vehicles | 99 teleports (jam 29, yield 55, wrong lane 15) | Local run log in `most-github` |
| InTAS Ingolstadt, SUMO | City | `time-to-teleport` 300 s | Local copy |
| TAPAS Cologne, SUMO | 30% scale | Demand cut "to avoid network-wide traffic jams" | Report 06 |
| Munich hybrid | | "Stuck vehicles were removed from the simulation after 60 s" | Report 15 |
| Fremont, Aimsun, 2022 | 21 km², 130,000 cars, 6 h | **Closest candidate:** Aimsun's documented micro rule is to lose the turn, not to remove. I didn't see a lost count | Report 15 |
| Stevenage, Paramics | Town | Discards locked seeds | Above |
| San Francisco, Dynameq, 2012 | Meso | Cut effective car length 24 → 21 ft, cut gaps, minor-road penalty | Not micro. "0.5-1 ft moves downtown between light and heavy congestion" |
| Melbourne, Sydney, Zurich | Meso or queue | Aggregate | Not micro |

**What let them do it (inference).** One of: a teleport or removal, a give-up, a cut in demand or car length, or discarding seeds. Nobody has shown a human-only driver with none of those at full demand. So **our gate's "teleports off" is stricter than anything published**, as report A says. It should stay, but read as "no removal", with driver give-ups allowed and counted.

## 7. What to do differently

Ordered by what it costs and how much it decides. All CPU-capable unless noted.

1. **Run the DGG grid first (scene S0).** It tells you whether `cars`' junctions can hold a rigid-route network where theory says they should, with no lane choice to blame. If `cars` locks well below kj/4, stop map work and look at the junction kernel.
2. **Add a hold census to `cars jam`.** Per hold type: count, seed rate per hour, duration p50, p99, max. Target: the I-80 numbers and the spill-time table. Add wait-for edges through lane-change and yield roots so rings can't hide. This replaces a place list with a number that can fall.
3. **Change the seed-junction step in report 23's plan.** Fix a place only if it recurs in, say, half of 10 seeds. The overlap of 6-17% says most of the hazard is spread out. Hand fixes won't converge on it, though recurring map faults still need fixing.
4. **Extend the give-up rule to any lane-change hold,** not only within 15 m of the end. Check against saved traces in one count, then S3, S4.
5. **Add an end to yields:** Polus's slope after 25 s, then forced entry at 3 m/s². Check S7. Look at `whya1` rank 2 and 3 first, because being on an internal lane may mean something else is wrong.
6. **Check signal roots over 150 s.** List connections that are never green, or that have under a few seconds. A human who waits 135 min at a red light is an input fault.
7. **Measure junction blocking in Europe.** Propensity and partial share, on data we hold. Then sweep `exit_comply`. Currently a 0.9 with no source.
8. **Add two benchmark metrics from real probes:** jam-cluster duration and size distributions (Zhang), and β, μ, R0 (Saberi), on HERE Berlin and on simulated speeds. They measure recovery, which is the thing that differs. Our probe table is 15-minute medians (`step6_probes.py`), close to Saberi's 10 min and coarser than Zhang's 1 min, so Zhang's exponents aren't directly comparable. Compare real against simulated on the same bins.
9. **Keep demand work where it is.** Don't add day-scale effects until 50% holds.

### All scenes in one table

| Scene | What | Expected | Tests |
|---|---|---|---|
| **S0** | DGG grid: closed one-way alternating grid, single lanes, rigid random turns P_T 0.1 and 0.5, cars placed uniformly at k = 0.1, 0.2, 0.25, 0.3, 0.4 kj. 10 seeds, 50 h. Needs a torus or very long generated routes, since `cars` has no closed mode | No lock below kj/4; hours at kj/4; under 1 h above. Same for both P_T | Junction kernel, no lane choice |
| S1 | Two tangent rings | Table in mechanism 6 | Instability, adaptivity |
| **S2** | Ring: 4 links of 75 m, 1 lane, all around the block, at measured jam spacing s = 7.5 m | N = 39: moving, hole travels at w, flow = w/perimeter = 67 veh/h. **N = 40: zero flow for ever.** Exit-clear on or off: same | Coffman, Kundu-Akyildiz, keep-clear not enough |
| S3 | Wrong-lane head | 3600/(h + f·T̄) | Give-up |
| S4 | Same, held 30 m back | Same as S3 | Give-up reaches LC holds |
| S4b | Real lane drop | No give-up fires | Rule isn't too eager |
| S5 | Two abreast with offset stops | Both done under 30 s | Swap avoided |
| S6 | Lane drop, 1,300 + 1,300 | 1,800 total, 1:1, wait max under 80 s, 0 failed | Forced merging |
| S7 | Yield, Poisson major | Siegloch, tail table | Holds end |
| S8 | Cross street with hold | s(g − bτ)/C | Blocking cost |
| S9 | One held head, median edge, q = 600 | Queue reaches the upstream line at 78 s; no spill if D < 78 s | Spill arithmetic |
| S10 | Vickrey bottleneck | 2.0 h rush, 0.8 h peak delay | Departure stage |

DGG's two-bin and ring cases are unsignalised with equal priority at the merge. I couldn't tell from the working paper what control Fig. 9's grid uses, so run S0 both unsignalised and with fixed 60 s signals. `grep` finds no such grid or ring test in `scripts/` or `crates/`.

## 8. Limits and what I couldn't open

- **Not opened, closed access:** [Mahmassani, Saberi, Zockaie 2013](https://doi.org/10.1016/j.trc.2013.07.002) and its [Procedia version](https://doi.org/10.1016/j.sbspro.2013.05.007), listed open but ScienceDirect blocked me, Semantic Scholar rate limited, OpenAlex has no abstract. Its "recovery time" reading is only a [UNSW press line](https://www.unsw.edu.au/research/rciti). This one is worth getting: it is the brief's main source on gridlock dynamics. Daganzo 2007 journal version. Hidas 2002 and 2005. Kaysi and Abbany 2007. Mahmassani and Sheffi 1981 and Daganzo 1981 full texts. Cairns 2002 (via a paper that quotes it). Full GDOT report (poster read). Zhu 2010 full text. Khattak numbers. Paramics and TransModeler manuals.
- **Could not identify:** "Wang et al." on forced lane changes. Le Boudec on road deadlock: only the TSN cycles work.
- **No measure found, after searching:** missed turn share, red entry during spillback, driving over markings, using a turn lane to pass, junction blocking in Europe, real normal-day gridlock in Europe, how often cities lock.
- **The first-stop overlap (6-17%)** comes from the brief. I didn't find its computation on disk, so my reading of it stays qualitative.
- **Saved seeds** are top 15 of each run, 15-minute samples, from different builds; durations come in 15-minute steps and "first to last" isn't proof of unbroken holding. `jam.py` can't see rings through lane-change or yield roots. I read these files and did not rerun anything.
- **Loder scaling** is rough: regional detector networks, different lane-km definition, and I couldn't reconcile the flattened regression table. Use it as an order of magnitude.
- **DGG** is a homogeneous, redundant, closed grid, and the real district isn't. Its kj/4 is a reference line, not a prediction for Berlin. Scene S0 tests only the grid.
- **US box-blocking sites** are suburban activity centres with long signal cycles in Atlanta. They may not transfer to Berlin.
- **Spill-time and R0 arithmetic is mine,** and only as good as a single-lane, steady-flow picture. It is meant to say what size of release is needed, not to predict flows.

## Sources

Most are linked where used. Read means full text or the named sections.

**Read.** [DGG 2010](https://escholarship.org/uc/item/7qd590bv). [Gayah and Daganzo 2010](https://escholarship.org/uc/item/2x98k1x2). [Daganzo 2005](https://escholarship.org/uc/item/7w6232wq). [Daganzo 2010 slides](https://strc.ch/2010/Daganzo.pdf). [Geroliminis and Sun 2011](https://infoscience.epfl.ch/bitstreams/dd751200-cbac-421a-8f8c-9f3ad8877098/download). [Saberi 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7138808/). [Zhang 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6500150/). [Loder 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6841661). [Coffman 1971](https://dl.acm.org/doi/pdf/10.1145/356586.356588). [Liebeherr and Akyildiz 1993](https://www.comm.utoronto.ca/~jorg/archive/papers/CS-93-65.pdf). [Mendlovic and Matias 2025](https://arxiv.org/pdf/2503.04583). [Barbosa and Benevides on knots](https://cos.ufrj.br/uploadfile/1372173239.pdf). [Rickert and Nagel 1997](https://arxiv.org/pdf/adap-org/9705002). [Polus 2005](https://journals.open.tudelft.nl/ejtir/article/download/4329/4227). [Harris 2014](https://nctspm.gatech.edu/sites/default/files/u60/HARRIS-THESIS-2014.pdf). [Saroj poster](https://stride.ce.ufl.edu/wp-content/uploads/sites/153/2019/01/Saroj_Abhilasha_Poster.pdf). [StVO § 11](https://www.gesetze-im-internet.de/stvo_2013/__11.html). [Trafikförordningen](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/trafikforordning-19981276_sfs-1998-1276/). [Highway Code](https://www.gov.uk/guidance/the-highway-code/using-the-road-159-to-203). [CNA I-95 report](https://www.fairfaxcounty.gov/boardofsupervisors/sites/boardofsupervisors/files/assets/meeting-materials/2022/oct18-legislative-winter-weather-event-i-95-incident-after-action-report.pdf). [OSIG audit](https://www.osig.virginia.gov/media/governorvirginiagov/office-of-the-state-inspector-general/pdf/performance-audits/I-95-Snow-Incident-Report-FINAL-8-11-22.pdf). [FHWA Toolbox IV](https://ops.fhwa.dot.gov/trafficanalysistools/tat_vol4/vol4_guidelines.pdf). [RTA Paramics manual](https://www.aldridgetrafficcontrollers.com.au/ArticleDocuments/295/paramicsmanual_i.pdf.aspx). [Vectos 2017](https://www.stevenage.gov.uk/documents/planning-policy/examination-of-our-local-plan-2011-2031/examination-documents/ed144-vectos-supplementary-paramic-modelling-overview-19-1-17.pdf). [Hidas 2005 WIT](https://www.witpress.com/Secure/elibrary/papers/UT05/UT05075FU.pdf). Hidas 2004 ATRF, local copy. [hEART 2019](https://transp-or.epfl.ch/heart/2019/abstracts/hEART_2019_paper_150.pdf). [Nello-Deakin 2022](https://ddd.uab.cat/pub/artpub/2022/0aac865e4d2e/1_s2.0_S2213624X22002085_main.pdf).

**Read in part.** [Elmegreen 2023](https://arxiv.org/pdf/2401.00882). [A-DRIVE](https://arxiv.org/pdf/2204.04910). [Wongpiromsarn 2012](https://arxiv.org/pdf/1205.5938). [Gregoire 2015](https://arxiv.org/pdf/1309.6484). [Bubble flow control](https://www.eecg.utoronto.ca/~enright/fbfc-pp.pdf). [Push and Rotate](https://jair.org/index.php/jair/article/download/10913/26020). [Anderson and Davis](https://www.nber.org/papers/w24469.pdf). [Olmos 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC6294880), through a fetch summary. [Seoul navigation logs](https://wctrs-society.com/wp-content/uploads/abstracts/lisbon/general/03376.pdf). [TxDOT](https://www.txdot.gov/manuals/des/tsp/chapter-13-microsimulation-analysis/13-5-calibration/13-5-3-calibration-parameters-and-best-practices/13-5-3-1-vissim-calibration/13-5-3-1-1-lane-change-parameters.html). [PTV](https://cgi.ptvgroup.com/vision-help/VISSIM_2022_ENG/Content/4_BasisdatenSim/FahrverhaltensparameterFahrstreifenwechsel_bearb.htm). [Aimsun manual](https://docs.aimsun.com/next/latest/UsersManual/MicrosimulationModellingVehicleMovement.html). TfL guidelines, local copy. [NCDOT TransModeler guide](https://connect.ncdot.gov/resources/safety/Congestion%20Mngmt%20and%20Signing/Congestion%20Management/NCDOT%20CONGESTION%20MANAGEMENT%20SIMULATION%20GUIDELINES%20-%20TransModeler.pdf).

**Abstract or record only.** [Knoop 2010](https://doi.org/10.1016/j.proeng.2010.07.012). [Polus 2003](https://doi.org/10.1061/(asce)0733-947x(2003)129:5(504)). [Perronnet 2019](https://doi.org/10.1109/tits.2018.2886247). [Gayah and Daganzo 2011 TRR](https://doi.org/10.3141/2249-03). [Mahmassani and Sheffi 1981](https://ideas.repec.org/a/eee/transb/v15y1981i3p143-148.html). [Papinski 2009](https://experts.mcmaster.ca/scholarly-works/292020). [Zhu 2010](https://experts.umn.edu/en/publications/the-traffic-and-behavioral-effects-of-the-i-35w-mississippi-river/). [Shapouri 2025](https://repository.lsu.edu/civil_engineering_pubs/1210). [Botea 2018](https://jair.org/index.php/jair/article/download/11212/26423/20783). [Thomas, Le Boudec, Mifdaoui](https://infoscience.epfl.ch/record/280256?ln=en). [Saroj 2017 TRB](https://trid.trb.org/View/1439541).

**Second-hand, search snippet or news.** Dally and Seitz, Duato, Glass and Ni, Kundu and Akyildiz as stated in the papers above. Red-light rates. UPS and Waze on left turns. Atlanta and Beijing events. Manhattan's count. Louisiana DOTD's table. Wei et al. 2024 via report 14.

**Our reports and files.** Reports [14](../14-human-courtesy.md), [15](../15-how-the-best-simulators-do-it.md), [18](../18-how-humans-merge.md), [23](../23-berlin-2019-first-gate.md), [06](../06-demand-and-route-choice.md), [data-hunt/20](../data-hunt/20-simulator-limits.md), [data-hunt/15](../data-hunt/15-how-to-match-reality.md), [foundations A](A-how-simulations-are-built.md). `crates/cars-core/src/shaders/step.wgsl`, `lc.wgsl`, `route.wgsl`, `world.rs`, `crates/cars-assign/src/enroute.rs`. `scripts/dbg/jam.py`. Branches `t3/1c6fee50`, `t3/1b36c9cf`. `cars-data/berlin2019/runs/*/jam/seeds.json`, `district/m12/`, `research/truth/berlin2019/rounds.csv` on the physics branch.
