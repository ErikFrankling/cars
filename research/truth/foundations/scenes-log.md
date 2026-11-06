# Rung 2 scenes: log

`python3 -I scripts/theory/scenes.py --driver physical|human [--dt X] [--only ...]`, CPU (llvmpipe), 5 seeds unless said. Tables in `results/theory/<driver>_<dt>.csv`. Forecast lines in `forecasts.csv`; every change to a line says why in its own `formula_or_source`, marked CHANGED with the date.

## 1. Baseline, 6 November, after fixing scenes and forecasts

| Driver | Pass | Fail | Info rows |
|---|---:|---:|---:|
| Main's physical, dt 1 | 117 | 69 | 59 |
| Human, t3/1b36c9cf 11afb41, dt 1 | 104 | 83 | 59 |

The first baseline (2 November) read 74/98 and 79/99. Most of the gain is scenes that tested the wrong thing, not drivers getting better.

### Scenes or forecasts that were wrong, and what changed

| Line | What was wrong | Now |
|---|---|---|
| F011-F015, F285, F047, F291, F292, F266, F270 | Every signal consequence used S 1,800 and g = G, so one wrong saturation failed ten scenes, and 1,800 isn't the real best read (1,750, R §2) | Consequences use the driver's own S (S1), lost time (S3), s and w (L3, L4): one fault, one fail. Realism stays in F289 (L1 against 1,640-1,900) and F290 (S4 against 729-844) |
| F014 | Webster scored at x .9 where the driver's x was past its range | Scored only where x <= 0.9 |
| F015 | (q - c) T is fluid; at x 1.02 randomness rules | Scored only at x >= 1.1 |
| F017, F018 | Report 23's driver no longer exists; today's has t0 2.7 s at low major flow | Info rows; target is F016 |
| F020 | Wait formula at HBS's c, not the driver's | Kimber-Hollis at the driver's own c (G1) |
| F023 | B's stopped-gap formula is a floor at a real lane end that zips | One-sided; share F024 and holds F028 stay two-sided |
| F029, F271 | Storage at jam spacing measured as a mean over green and red; c 720 fixed although the link merges two lanes into one; time to spill moved 30% per 3% of c | Most cars in the cycle of the spill; c measured on the scene |
| F032 | 40 cars at exactly jam spacing can't be inserted; band on 301 m was 40x too wide | 300 m case unscored; band 1.5 x w/P x slack |
| F033, F034 | C's h 2 s against the scene's own 2.9 s; first S4 let heads change in gaps, so it wasn't C's scene | h from an f 0 cell; S4 rebuilt with a line and two changes needed; heads stand 43 m back |
| F039, F284 | 30% on an order-of-magnitude formula, Webster's third term missing; var/mean from 5 draws | Sizing row; 10 draws |
| F254, F296 | The scene sets a speed, not a flow | Shock at the scene's own c; c against Newell split off as F296 |
| F263 | Counting passes until a change counts the pass that triggers it, and changers on the target lane | k dv of target cars |
| F267, F268 | Plateau from plain cuts at fixed offsets, scene has random ones and a 0.95 rule; 130/km can't be placed | Granular cuts by the same rule, 44-71; bound w(kj - k) where the scene is |
| F287 | 30 cars over 30.2 cycles read 0.992 | Whole cycles |
| F025, F026, F264 | Insertion can't saturate a lane (1,516-1,622) | Released standing queues |
| F027 | Onset from a 2.5 km edge mean, 400 s late | Last 300 m, held 150 s |

### Fails of main's physical driver, by cause, smallest scale first

1. **Time gap short and speed-dependent.** T 1.21 s from the start wave, 1.24 at 30 km/h, 1.48 at 100 against a constant 1.4 measured (B §1). L1 1,941/2,055/1,685 against 1,856/2,156/1,565, F289 1,941 over 1,900, L4 22.3 km/h, L2 kc 41 and speeds at 15-20 m, S4 884 over 844. One parameter family: Krauss tau and the certificate.
2. **No start reaction at a green.** The first car crosses 0.24 s after green (d0 1.5 m) against 2.49 closed form and 3.62 measured. S2 t1, S3 lost time 0.5 against 2.74, and through it S5 (queue clears early) and S6.
3. **Crawling flow.** 511 veh/h at 1.63 m/s against 600 (F296); one hole on a ring moves at 64% of s/T (C-S2). Krauss dawdling at low speed is the suspect.
4. **Give-way gap is half of HBS.** `Link::tc` = TRVMB × 0.7 − 1.2 s, about 2.3 s for a right turn. Minors take 2.4 s gaps and the major brakes for them: major delivered .91-.94 (F288), minor through across 800 veh/h 1,441 against 355, rank 3 and 4 lefts 983/973 against 555/564, C-S7 1,537 against 277, Tanner high. Follow-up 3.97 s against 3.0 (G1 912 at no major). The two errors cancel near major 400, which is why G1 looked close.
5. **Roundabout entry collapses** with circulating flow: 973/546/190/14 against 1,380/916/608/404. Not looked at yet.
6. **Lane end.** The merger gets 2/3 of a saturated zip (F024, C-S6), heads wait up to 338 s at a lane end (LC8), a 100 km/h lane drop breaks down below its own discharge (LC6, −9%: merging at speed, not a capacity drop), voids cost 3x theory with no Δv² shape (LC5).
7. **Network.** Merge 757/1,360 against 928/1,556 (N4), diverge 1,152 and 3,275 against 1,500 and 3,712 (N5), a two-lane link fills one lane first (N3 40 of 51 stored), two lanes with a lane wish on an opposed short link 8.2 per cycle against at least 13 (N9), `exit_comply` changes nothing in C-S8 (cause not found yet), priority grid locks at 0.2 kj in 5 of 6 runs while the signal grid doesn't lock at 0.3 (C-S0, to explain), N6 P/l 0.88 on both drivers.

Passing now that C expected to fail: C-S3 and C-S4 on main. Heads held 43-60 m back still give up after 60 s (274 rerouted), so `ph_reroute` no longer waits for the last 15 m.

### Human driver, where it differs

Jam spacing 5.79 m against 7.5 and capacity flat with speed (1,741 at 50, 1,759 at 100); 280 veh/h at 1.63 m/s; its gaps (0.65 × TRVMB × lognormal) give G1 476/222/103 against 736/451/277 and holds up to 585 s in C-S7; LC4 0.43; merges 700 per arm; 29 cars unaccounted in batch give2. Its lane end (LC3, LC8) and start wave pass where the physical driver fails.

## 2. Time step, main's physical driver, 6 November

L1-L4, S1-S3, G1 at dt 1, 0.5, 0.25, 0.1 (`--tag dtfreeze`, tables `results/theory/physical_<dt>_dtfreeze.csv`).

| Quantity | dt 1 | 0.5 | 0.25 | 0.1 | Forecast |
|---|---:|---:|---:|---:|---:|
| L1 capacity 50 / 100 / 30 km/h | 1,941 / 2,055 / 1,685 | 2,226 / 2,636 / 1,814 | 2,258 / 2,858 / 1,830 | 2,266 / 2,933 / 1,837 | 1,856 / 2,156 / 1,565 |
| L4 start wave, km/h (T from s/w) | 22.3 (1.21) | 30.6 (0.88) | 35.7 | 34.5 (0.78) | 19.3 (1.4) |
| S1 headway from car 10, s | 1.91 | 1.65 | 1.62 | 1.61 | 1.94 |
| S2 first car after green, s | 0.24 | 0.78 | 1.03 | 1.18 | 2.49 |
| S3 lost time, s | 0.50 | 0.76 | 0.90 | 0.95 | 2.74 |
| L2 peak ring flow | 1,808 | 2,083 | 2,133 | 2,142 | 1,856 |
| G1 minor at major 0 / 400 / 800 / 1,200 | 912 / 678 / 497 / 290 | 1,010 / 1,008 / 1,006 / 1,007 | 1,057 / 1,056 / 1,055 / 1,056 | 1,080 / 1,076 / 1,068 / 1,073 | 1,200 / 736 / 451 / 277 |
| G1 major delivered over offered | .91-.94 | 0 | 0 | .006-.013 | 1 |

Reading:

- **dt 1 is not a coarse version of the same driver.** A step of 1 s acts as a reaction time of about 1 s: followers start one step after their leader, which is what put T at 1.21 s and saturation near 1,900. Below dt 0.5 the driver converges to T 0.78-0.88 s and 2,266 veh/h at 50 km/h, 20% over the real band.
- **Give-way breaks below dt 1.** The minor runs at its free turning flow and the major delivers nothing: once a major car has slowed for a minor that took a 2.3 s gap (`tc` = 0.7 × TRVMB − 1.2), it stands, its arrival from rest looks far off to the next minor, and minors go one after another. At dt 1 the coarse step leaves holes in that chain.
- **Converged:** 0.25 against 0.1 moves L1 by 0.4% at 50 km/h and 2.6% at 100, the start wave 3%, G1 1-2%, and the first car 0.15 s. 0.5 against 0.1 moves 100 km/h by 10% and the start wave by 11%. Cost for this set on 2 llvmpipe threads, contended: 60 s at 0.5, 106 s at 0.25, 145 s at 0.1.
- **So no dt is frozen yet.** The driver has to be fixed at a converged step, since today's dt-1 numbers borrow a reaction time from the step. Work goes on at dt 0.25, and the freeze is repeated on the final driver.

## 3. One driver and the fixes, 6-7 November

The human branch (t3/1b36c9cf) is merged next to the physical driver (a4640c1); both stay selectable, physical bit-identical, human within seed noise. The one driver is physical motion with these decisions, each from a measurement (table in `parameters.md`, with the value `measure/DRIVER.md` has for each):

- T 1.4 s median, spread 0.3 (B §1); start reaction 1.0 s after the car ahead moves, 1.62 s for the first car at a green (report 05 DLR UT), counted in part-steps so it holds at any dt; no added reaction at a give-way line, a 'g' green or inside a junction, where the critical gap holds it.
- Critical gaps from HBS S5 by movement (5.9 / 5.5 / 6.7 / 6.5 s), counted from now for a waiting head; zipper links take none.
- The human driver's lane-change decisions (report 18 B1 B2 start law, gate floor certificate × 0.35, report 14 courtesy 0.4).
- A first try set T 1.3 and start 1.4 s because the scenes passed with them. Withdrawn: values come from recordings, and scene forecasts were rewritten to check the code's own equations (mean T of the spread, own reactions).

Code faults found and fixed on the way (each with its line): a light seen one step late at every dt (F238: `G.step` counts the step's end); the 1.62 s reaction at give-way lines making accepted gaps 9.9 s (F236); the waiting head adding its time to the line to tc (F239); HBS gaps on zippers and the reaction inside junctions (F240); a held car not creeping to its line, which locked the priority grid at 0.1 kj in two minutes, and a permitted left re-arming its reaction for good (F241, F242).

### Time step

With the wave scene W1 added (Hickert et al. 2026), on L1-L4, S1-S3, W1, G1 (`physical_<dt>_v2.csv`, before F238's fix):

| | dt 1 | 0.55 | 0.5 | 0.25 | 0.1 |
|---|---:|---:|---:|---:|---:|
| L1 50 / 100 / 30 km/h | 1,706 / 1,865 / 1,460 | 1,770 / 2,084 / 1,492 | 1,773 / 2,098 / 1,494 | 1,780 / 2,141 / 1,505 | 1,784 / 2,155 / 1,511 |
| L4 start wave, km/h | 20.4 | 22.5 | 22.8 | 24.3 | 25.2 |
| S1 headway from car 10, s | 2.14 | 2.05 | 2.04 | 2.02 | 2.00 |
| L2 peak ring flow | 1,650 | 1,731 | 1,735 | 1,742 | 1,746 |
| W1 wave speed upstream, km/h | 24.4 | 23.7 | 23.2 | 22.9 | 21.9 |
| W1 lowest speed of car 30, m/s (leader 3) | 6.7 | 7.5 | 7.6 | 8.0 | 8.2 |
| Wall time for this set, 2 llvmpipe threads | 135 s | 189 s | 198 s | 391 s | 499 s |

**dt 0.25 is the step**: against 0.1 it moves capacity 0.2-0.7%, the start wave 4%, the wave speed 5% and car 30's dip 0.2 m/s, all inside seed spread or close to it. 0.5 and 0.55 agree with each other to 1% on every row (no Hickert jump here), but sit 2-6% further from 0.1 on the start wave and W1. dt 1 is a different driver (capacity −4 to −13%). Cost: about 2× dt 0.5, 0.8× dt 0.1. F286 (the freeze) is answered: dt 0.25.

### State at dt 0.25 (`physical_0.25.csv`): 124 pass, 62 fail, 1 error

The error is batch miss60 killed by the desktop watchdog (disk IO), not a fault. Fails by cause, smallest scale first:

1. **Driver equations not yet the measured driver** (realism rows, for the next job from DRIVER.md): L1 100 km/h +3% (one T at all speeds), S3 lost time 2.1 against 2.74, S2 cars 4-9 0.2 s short, W1 wave 22.9 against s/E[T] 18.4 (Krauss's start rule, not Newell's), S4-S6 and S8 follow from those. G1 follow-up 3.8 s against HBS 3.0 and DRIVER.md's 2.7-3.2: the scene's 4 m corner caps the turn at 2.9 m/s.
2. **Give-way still about 2 s too careful.** Recovered critical gap 7.9 s against 5.9; capacity 489/231/87 against Siegloch at its own tc and tf 607/389/250 (F233), and C-S7 holds up to 531 s. Not the arbiter (same with it off). Two rounds spent (F236, F239); left for the next job, with DRIVER.md's measured gaps.
3. **Roundabout entry** collapses with circulating flow (1,006/319/67/0 against 1,380/916/608/404). Not looked at.
4. **Zipper** (N4): one arm takes all, the other 0, at every dt and with all of this job's changes off: a kernel fault in the zipper rule, not the driver. Also C-S6 and LC3's merge share 0.70 against 0.5.
5. **Lane drop at 100 km/h** (LC6) drops 28%, above the 5-15% band; LC5 voids 3× theory.
6. **Network**: N5 diverge 1,134 against 1,500; N9 two lanes opposed 8.1 against 13 per cycle; C-S8 `exit_comply` changes nothing (cause not found); C-S2's hole ring is 0, which is right for this driver (no one starts for 0.2 m of slack spread over 36 cars), so the scene, not the code, needs a real hole.
7. **Closed grid (C-S0)**: free at 0.1 kj, locks at 0.2 kj within an hour (DGG: hours at kj/4); signals lock at 0.4 kj, not at 0.3. To explain, not called a kernel fault.

### Replay of the one driver (F111-F113, `research/truth/replay/f101.json`, `f109_one.json`, `classifier_one.json`)

| | Forecast | One driver | Main's |
|---|---|---|---|
| F111 spacing RMSE 30 s, 5 seeds | 5.6-6.3 m | **5.75** (5.69-5.81) | 6.30 |
| F112 classifier, through the instrument | 0.80-0.90 | **0.866** | 0.89 |
| F113 next-second CRPS, 10 seeds | 0.45-0.70, above constant speed 0.37 | **0.649** | 0.68 |

All three pass their bands. The spacing error reaches the real-real floor (5.67); the response is still Krauss's, worse than constant speed, as DRIVER.md's gap band and 0.5 s lag say it must be.

## 4. The measured driver, 7 November

`scenes.py --driver measured --dt 0.25` (research/truth/measure/MODEL.md; `--driver physical` is now the one driver above, through `--tune measured=0`). Forecasts F312-F321 come from the driver's own equations: a platoon twin of the kernel (`scripts/theory/md_platoon.py`) and the band centre of its zero-force band. 91 pass, 95 fail of 186, against 124/62. L1 1,155 / 1,098 veh/h at 50 / 100 km/h, start wave 26.7 km/h, W1 damped (car 30 dips 2.6 m/s less than the leader). The new fails share one cause: the law closes an open gap at 0.025 m/s² per s of time gap, so placed queues, rings and discharge stay open. Details and what is left: `research/truth/measure/MODEL_RESULTS.md`.

## 5. Code faults in junctions, merges and lane changes, 7 November

Branch t3/f0bdfad3, dt 0.25, llvmpipe, 5 seeds unless said. Driver values (T, reactions, launch, critical-gap values) untouched: another job sets them from DRIVER.md. Each fault: reproduced on the smallest scene, traced with `cars run --trace --why`, `cars why`, `cars jam`, `cars junction`, then fixed and rerun. Forecast lines F400-F406.

### Zipper (N4): F400, pass

- **One arm took all.** `ph_bid` gave zipper links a zone bid like any junction lane. While an arm-a body was in the merge zone the arm-b head was denied; denied, it announced `will_pass` 0 (approach), so the next arm-a car's zipper rule no longer fell in behind it, committed, and won again. Arbiter off: 585/584.
- **Both arms stopped at their lines.** `zipper_speed` aimed to cross the line `tf + tau` after the foe, SUMO's `getZipperSpeed`, which leaves out the foe's body and minGap. At crawl speed heads reached their lines 5-6 m apart projected, under the 7.5 m jam spacing, and the junction-leader check then stopped every car (total 1,170).
- Fix: zipper links take no bid (their order is the zipper rule's); in physical mode the target is one own time gap (`ph_tau` times the driver's factor) after the foe's rear plus minGap has crossed.
- N4 880/879 (868-889, 872-885) against 898 per arm at the driver's own capacity; before 1,573/0. Share 0.50 at dt 0.1, 0.25, 0.5 and 1 (892/889, 880/879, 831/831, 731/730; dt 1 is another driver, F286). F272 1,519.
- **C-S6 and LC3's 0.70 share is not the zipper:** those scenes merge by lane change. Two rounds in `lc.wgsl`, no gain, both reverted: courtesy (`hu_request`) and SUMO's follower hold (`hold_follower_for_blocked`) only after the merger's start law (B2) has started it. Followers stood for unstarted mergers, but the share stayed 0.70/0.706 and stalls on the through lane went 31% to 33% of standing car-frames. Other sources of lane-change speed on standing through cars, not yet split: `updateBlockerLength` reservations, `informLeader/informFollower` (lc.wgsl 650-780), the cooperative help at 1086.

### Give-way gap (G1, G4): F401, partial

- **What added the 2 s.** A head standing at its line was held by the passing major's body for about 1 s (junction leader on the merge), then asked for tc from now: it accepted headways of tc plus that hold. And once it rolled, `wait` fell to 0 and the rule went back to counting from its arrival, so a head that took a 6.0 or 7.25 s gap dropped it a step later (traced, G1 major 800).
- Fix (`link_opened`): per link the step it was last crossed, in `last_detect` after the lanes, written in `approach` by the latest entrant of the junction lane. A head standing at its line (first on its lane, within 10 m) counts the gap from the later of that crossing and its own stop, no further back than that foe can hold it (its time over the link plus `timegap_minor`). A gap taken from the line holds while the car moves (`F_GAP_TAKEN`); foes that cannot stop still block.
- Tried and dropped: the same credit for followers in the queue. The minor then crawls through the 9 m junction lane at 2.9 m/s for 5 s, the arbiter denies the next major, it slows, its arrival looks far, and minors flood (major delivered 0.27-0.59).
- Result: the standing head misses a 6.0 s gap at the line by 0.0 s (instrumented). G1 553/312/153 against Siegloch 605/388/249 at own tc 5.9 and tf 3.82: 400 passes, 800 and 1,200 short. Before 489/231/87. F288 0.97-0.98. Recovered tc 6.59 on offered gaps seen whole (new estimator: majors timed 60 m upstream, only gaps that began while the driver stood at the line); old estimator 6.71; before 7.92.
- **What is left is the start, not the gap.** For a merge (`check_link_leader` passes `dist_cross` -1) a projected gap below 0 holds the head at 0 m/s until the major's rear plus minGap is past the merge point (0.65 s), then it launches from rest 0.6 m short of its line (0.7 s): the first car of a gap enters 1.7 s after the major crossed. With Poisson majors the code's rule gives `e^-q tc + e^-q(tc+d) e^-q tf / (1 - e^-q tf)` cars per gap: 326 at 800 against 312 measured, 377 with d = 0. The launch is the other job's.
- Same rule elsewhere: G2 Tanner 499/229/45 (before 420/120/8) against 712/384/172; G5 rank 3 504 pass (416), rank 4 452 (350) against 564; C-S7 219/88/34 (93/17/4) against 277/133/64, longest head waits 131/192/400 s (before up to 531). G9 right-before-left 525 (429) against a low-confidence 230.

### Roundabout entry (G8): F402, partial

- **Collapse to 0 at circulating 1,200.** A ring car slowed below its brakes by the 18 m ring's curve gets SUMO's `have_to_wait`. `lane_free_scan` then read the ring lane as ending in a queue (`FREE_LAST_WAITS`), and `ph_bid`'s keep-clear rule for roundabout targets ("nobody enters a full roundabout") denied every entry: 0 entries after 450 s while the ring carried 1,000/h (`exit_clear=0` and `arbiter=0` split it). Fix: on a roundabout lane the front car counts as waiting only below `queue_speed`.
- The forecast at the code's own values is Tanner, not Siegloch: the circulating stream reaches the entry bunched (tm = E[T] + s/v_ring = 3.1 s at 4.5 m/s) and near the ring's own capacity. At the flows the ring carried (374, 731, 991): 612/296/105 against 511/275/47. 800 passes; 400 16% short (the start delay above); 1,200 has seeds from 0 to 233. Before 1,006/319/67/0.
- F261 (HCM6) stays the realism row: `Link::tc` gives roundabout entries HBS's give-way values (5.9-6.7 s); DRIVER.md measures about 3.0 s on rounD. That value is the other job's.

### Lane drop at 100 km/h (LC6) and voids (LC5): F403, open

- **LC5's 3x is the forecast's acceleration.** B §4 takes a = 1.5 m/s²; this driver accelerates at max(2.02 - 0.125 v, 0.7), 0.7-0.9 at 9-14 m/s, so a changer 5 m/s slow leaves a 16.5 m void, not 8.3. At its own a(v): dv 5 0.110 against 0.099, pass; dv 10 0.466 against 0.282, fail (not traced). F264's dv² ratio 4.25, pass.
- **LC6 after breakdown** (one seed traced): closing-lane cars merge inside the queue (median 187 m before the end, 8.4 m/s), and 88 changes per 500 s go from lane 1 to lane 2 in the last 500 m. Cut-ins on both lanes keep the head at 6-8.5 m/s instead of discharging, and a lane at 7 m/s with spacing s + vT carries 1,424, against 1,465 per lane measured. 18.6% (-9.6 to 31.6 over seeds) on this run, 28.3% on the 0.25 baseline. No single line found; no code changed.

### Network: F404-F406

- **N5 diverge: the code is right, the forecast was not this scene's.** The exit link is 41.6 m and stores 5 cars; a green discharges 7.9, the rest must come from the blocked lane after the start wave has passed the stored cars, and one in five of those exits. Exit 223 against 237 at that storage, through over exit 3.99 against FIFO's 4: pass. F273's 1,500 assumed a longer exit.
- **N9 opposed, two lanes: the forecast was not this case's.** F295's floor of 13 was written for the Hamburg case (w, 16.1, pass); the scene also applied it to case x, fed at 9 a cycle with opposed lights. There a cycle carries what the link stores: 2 lanes x 4 on 27.7 m = 8, measured 8.14: pass.
- **C-S8 `exit_comply` changed nothing** because `check_rewind` (SUMO's `checkRewindLinkLanes`) held every driver out of a full exit; `exit_comply` only fed the arbiter's second test. Fix: a driver who does not comply skips `check_rewind` too, by the same draw. Its default 0.9 had no source (physics-provenance.md: invented) and never acted, so it is now 1.0, the behaviour traffic has had, until C §7's measurement. Cross capacity: b 0 930, b .75 558 against 571 at the code's own blocking time (hold release plus first_react plus the stored cars' start reactions plus the cross head's: 14.6 s): pass; b 1 380 against 461: open.

### Closed grid (C-S0): F407, explained, not a kernel fault

- Right-before-left at 0.2 kj: 2 of 6 free in 2 h, the others lock at 0.42-1.23 h (before 0 of 6, 0.47-0.73 h; the give-way fix moved it). Signals: free at 0.1-0.3 kj, lock at 0.4 after 0.65-1.37 h (unchanged), which is DGG's picture.
- **What a lock is here.** The run's gridlock detector names every one as a cycle, never a knot: the four links around one block (c0_3, r0_3, c0_4, r1_3), or the two links of a border oval (c0_5 with E0). Each head waits for room on, or right of way from, the next link of the ring. All four of Coffman's conditions hold: lane space is held, cars hold their link while they wait for the next, nothing is taken away (teleports off, no rerouting in a closed grid), and the wait is circular. No car stands in a junction box (check_rewind and keep-clear hold), no stand-off inside a junction.
- **Why sooner than DGG's hours at kj/4.** DGG's grids have signals with fair splits. A right-before-left node here has two incoming one-way streets and always serves the one from the right first; the other gets only its gaps (tc 6.7 s through, tf about 4 s). When the priority stream is dense the other queue grows, reaches back into the node upstream and holds the stream that node feeds. The border ovals are rings of two links (about 290 m), the shortest cycles in the scene; they lock first at turn share 0.1.
- Not called a kernel fault. Whether real drivers at right-before-left nodes break the order (courtesy, alternation) is a measurement for inD, and it is the one thing that would undo this.
- Contacts in the grids: 33 and 38 (baseline 26 and 38), all at junction diverges in locked cells.

### Whole suite at dt 0.25 after F400-F407 (`physical_0.25.csv`)

142 pass, 60 fail, 0 errors of 202 scored lines (before: 124, 62, 1 error of 187). The grid batches ran as their own job (`wipgrid`) and are merged into the table; everything else is one run.

- The rows the old table scored: 124 pass, 54 fail. Now passing: N4 both arms (883/881), G5 rank 3 (526), C-S7's longest wait at major 1800 (192 s), G7 at minor 400 (scored at the new own c), G1 F233 at major 400 (548), S2 cars 7 and 9. Now failing: S1's headway from car 10, 2.09 against 1.94. That is not this job: baseline shaders with exit_comply 0.9 give 2.09 on this binary too, and S1 reads 2.02 with only S1 and S2 in the batch, so it moves with the batch's composition (the per-trip draws), not with a rule.
- New lines: F402-F406 6 pass, 4 fail (G8 Tanner at 400 and 1200, LC5 dv 10, C-S8 b 1); signal grid 3 pass, 2 fail (F278 expects a lock under 1 h at 0.3 and 0.4 kj; it is free at 0.3 and locks after 0.65-1.37 h at 0.4); miss60 runs now, 9 pass.
- Which fixes change ordinary traffic: the give-way rule (F401) at every link with a critical gap (priority, stop, right-before-left, 'g' greens); the zipper rule (F400) at zipper nodes; the ring rule (F402) at roundabout entries; exit_comply (F406) only through the arbiter's keep-clear test, which now applies to the 10% of drivers the old 0.9 skipped (check_rewind holds them as before). Lanes and signals without such links are byte for byte the same as before (S1-S8 and L1-L4 traces compared, same binary).
- Open, with what was tried: lane-drop share 0.70 (C-S6, LC3; two rounds in lc.wgsl, reverted); LC6 drop 22% (friction at the queue head, no line found); LC5 dv 10; G1 and G8 capacity short by the 1.7 s start of the first car of a gap (merge hold plus launch, the launch is the other job's); C-S8 at b 1; G9 right-before-left 525 against 230.
