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
| F011-F015, F085, F047, F091, F092, F066, F070 | Every signal consequence used S 1,800 and g = G, so one wrong saturation failed ten scenes, and 1,800 isn't the real best read (1,750, R §2) | Consequences use the driver's own S (S1), lost time (S3), s and w (L3, L4): one fault, one fail. Realism stays in F089 (L1 against 1,640-1,900) and F090 (S4 against 729-844) |
| F014 | Webster scored at x .9 where the driver's x was past its range | Scored only where x <= 0.9 |
| F015 | (q - c) T is fluid; at x 1.02 randomness rules | Scored only at x >= 1.1 |
| F017, F018 | Report 23's driver no longer exists; today's has t0 2.7 s at low major flow | Info rows; target is F016 |
| F020 | Wait formula at HBS's c, not the driver's | Kimber-Hollis at the driver's own c (G1) |
| F023 | B's stopped-gap formula is a floor at a real lane end that zips | One-sided; share F024 and holds F028 stay two-sided |
| F029, F071 | Storage at jam spacing measured as a mean over green and red; c 720 fixed although the link merges two lanes into one; time to spill moved 30% per 3% of c | Most cars in the cycle of the spill; c measured on the scene |
| F032 | 40 cars at exactly jam spacing can't be inserted; band on 301 m was 40x too wide | 300 m case unscored; band 1.5 x w/P x slack |
| F033, F034 | C's h 2 s against the scene's own 2.9 s; first S4 let heads change in gaps, so it wasn't C's scene | h from an f 0 cell; S4 rebuilt with a line and two changes needed; heads stand 43 m back |
| F039, F084 | 30% on an order-of-magnitude formula, Webster's third term missing; var/mean from 5 draws | Sizing row; 10 draws |
| F054, F096 | The scene sets a speed, not a flow | Shock at the scene's own c; c against Newell split off as F096 |
| F063 | Counting passes until a change counts the pass that triggers it, and changers on the target lane | k dv of target cars |
| F067, F068 | Plateau from plain cuts at fixed offsets, scene has random ones and a 0.95 rule; 130/km can't be placed | Granular cuts by the same rule, 44-71; bound w(kj - k) where the scene is |
| F087 | 30 cars over 30.2 cycles read 0.992 | Whole cycles |
| F025, F026, F064 | Insertion can't saturate a lane (1,516-1,622) | Released standing queues |
| F027 | Onset from a 2.5 km edge mean, 400 s late | Last 300 m, held 150 s |

### Fails of main's physical driver, by cause, smallest scale first

1. **Time gap short and speed-dependent.** T 1.21 s from the start wave, 1.24 at 30 km/h, 1.48 at 100 against a constant 1.4 measured (B §1). L1 1,941/2,055/1,685 against 1,856/2,156/1,565, F089 1,941 over 1,900, L4 22.3 km/h, L2 kc 41 and speeds at 15-20 m, S4 884 over 844. One parameter family: Krauss tau and the certificate.
2. **No start reaction at a green.** The first car crosses 0.24 s after green (d0 1.5 m) against 2.49 closed form and 3.62 measured. S2 t1, S3 lost time 0.5 against 2.74, and through it S5 (queue clears early) and S6.
3. **Crawling flow.** 511 veh/h at 1.63 m/s against 600 (F096); one hole on a ring moves at 64% of s/T (C-S2). Krauss dawdling at low speed is the suspect.
4. **Give-way gap is half of HBS.** `Link::tc` = TRVMB × 0.7 − 1.2 s, about 2.3 s for a right turn. Minors take 2.4 s gaps and the major brakes for them: major delivered .91-.94 (F088), minor through across 800 veh/h 1,441 against 355, rank 3 and 4 lefts 983/973 against 555/564, C-S7 1,537 against 277, Tanner high. Follow-up 3.97 s against 3.0 (G1 912 at no major). The two errors cancel near major 400, which is why G1 looked close.
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
