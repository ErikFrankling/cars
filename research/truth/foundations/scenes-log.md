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
