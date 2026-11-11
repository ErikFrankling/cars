# The measured driver, round 5: why open gaps stay open, then a law that ships

7 November 2026 (held-out runs finished and written up 11 November). Branch `t3/open-gap-causes-measured-law`. Forecasts F830-F863 in `foundations/forecasts.csv`, each committed before its run. Scripts: `scripts/measure/opengap.py` (part 1), `ship.py` (fit), `xian.py`, `cutin.py`; `scripts/replay/heldout_r5.sh`. Numbers: [opengap.json](opengap.json), [ship_jw.json](ship_jw.json) (and `ship_f`, `ship_e`, `ship_j`), [xian.json](xian.json), [cutin.json](cutin.json), `replay/f101*.json`, `f109_r5*.json`, `classifier.json`, `md_twin_r5.json`.

**Result.** Part 1 found that open gaps stay open mostly because drivers watch the second car ahead, and on the free-flowing motorway also because the follower already drives at its own desired speed. Leader pairing is not a cause. The conflict did not dissolve on all four tables, so the decision rule's second branch applied. Law (j) ships behind `--tune measured=1`. It passes every system-scale pattern in its twin and in the T0 realism rows, and the next second on all three held-out recordings. Its misses are below. It is **not** the default (last section).

## Part 1: three causes, measured on P2's open windows

Windows: P2's selection (same leader 30 s, v over 2 m/s, gap under 100 m, at least 1 s over T(v)), every 5 s start. Counts: DLR HT 06-14 UTC 10,530; I-90/94 st. 5,346; I-294 L1 1,190; I-395 1,365. Recorded closed share in 30 s: 0.32 / 0.28 / 0.25 / 0.41. Intervals: 95%, bootstrap by driver.

### Cause 1, free speed (F830)

Each follower's desired speed is the median of its own earlier free driving: nothing on its line within 150 m and at least 150 m of road in view. Where it has no past, the site's free speeds above its current speed are used. d is that speed minus the leader's mean speed over the window.

| Closed in 30 s, by d (m/s) | under 0.5 | 0.5-1.5 | 1.5-3 | over 3 |
|---|---|---|---|---|
| DLR HT, all windows | **-0.33** (-0.40 to -0.28) | 0.20 | 0.29 | 0.56 (0.53-0.60), τ 37 s |
| DLR HT, own free past only (71%) | -0.33 | 0.25 | 0.38 | **0.72** (0.68-0.75), τ 24 s |

- **On DLR HT, P2 is largely a free-speed pattern.** A follower whose desired speed is no faster than its leader lets the gap open, and one that wants 3 m/s more closes with a time constant of about 24 s.
- **The congested tables have almost no free past**: I-294 L1 8%, I-90/94 st. 0.2%, I-395 0%. Their leaders drive at 4-9 m/s, so every window has d over 3 m/s. Free speed cannot explain those tables, and with I-294 L1's congestion it explains less there than forecast.

### Cause 2, the second leader (F831, F833)

Split on its own, the second leader is confounded with the leader's speed (F831). On DLR HT, a free second leader means a free leader, often faster than the follower wants. So the test is in the twin. Round 4's strongest-pull law (f) gets a second constraint: the same law evaluated behind the leader's leader, at distance g + 5 + g₂, with desired distance g\*(v) + 5 + g\*(v₁). No new number.

| Law (f) minus recorded, closed in 30 s | DLR HT | I-90/94 st. | I-294 L1 | I-395 |
|---|---|---|---|---|
| Baseline | +0.16 | +0.35 | +0.27 | +0.20 |
| (1) own free speed | +0.11 | +0.35 | +0.25 | +0.19 |
| (2) second leader | +0.07 | **-0.24** | +0.01 | +0.02 |
| (3) certain pairs only | +0.13 | +0.34 | +0.30 | +0.21 |
| (4) all three | **+0.00** | **-0.23** | **+0.01** | **+0.02** |
| Share of the conflict explained by (1) | 0.27 (0.22-0.31) | 0.00 | 0.06 (0.01-0.10) | 0.01 |
| by (2) | 0.57 (0.48-0.71) | 1.67 (1.52-1.84) | 0.97 (0.70-1.60) | 0.91 (0.69-1.57) |
| by (3) | 0.15 (0.07-0.24) | 0.02 | -0.13 | -0.06 |

The second leader explains most of P2 on three tables, and together with free speed all of it on DLR HT. On I-90/94 st. it overshoots: it holds open gaps open when real followers close 0.28 of them. Round 2 (F835) tested three explanations and none holds:

- I-90/94's leaders are not tighter than T(v): their median excess is +0.78 s, against DLR HT's +0.91 s.
- Mispaired second leaders are not the cause: the overshoot stays on windows where both pairs are certain (-0.20).
- No single-term form passes all four tables: a closing-only constraint over-restrains everywhere, and a band-only one under-restrains.

Part 1's two rounds were used up, so this stays open.

### Cause 3, leader pairing (F832)

The lateral check differs by site:

- **DLR HT:** the road frame of `dlrht.py`.
- **TGSIM:** frame-free. Is the follower on the path its leader drove, and does any other car sit on that path between them? The TGSIM sites curve, and I-90/94 has two roadways in one direction. On I-395 the two methods agree (77% and 78% certain).

| | DLR HT | I-90/94 st. | I-294 L1 | I-395 |
|---|---|---|---|---|
| Leader's offset from the follower's line, median / p90 (m) | 0.30 / 0.74 | 0.33 / 1.04 | 0.26 / 0.69 | 0.28 / 0.74 |
| Windows with another car between them | 4% | 10% | 3% | 1% |
| Closed in 30 s, certain pairs against all | 0.35 / 0.32 | 0.27 / 0.28 | 0.23 / 0.25 | 0.37 / 0.41 |

On highD, the table leader is the car on the follower's line in 98.1% of samples. **I-395's flat closing gain is not mispairing.** On certain pairs it is still 0.06-0.14 /s from 1.5 to 70 m, against I-90/94's 0.5-0.7 at short gaps. Pairing explains nothing of P2.

## Part 2: which branch, and the law

**Branch.** F833's rule, written first: the conflict dissolves only if all three causes bring law (f) within ±0.15 of P2 on all four tables. I-90/94 st. stays at -0.23, so the second branch applies. Choose the law that passes every system-scale pattern (P5, P6, P7, P8, P9, P12 at 50 km/h), and among those the best P1.

**Candidates (F836).** Each was fitted on P1 + P6 with each driver's past factor. P2 was left out of the fit: under this branch it is a known miss.

| | Fitted numbers | System-scale misses |
|---|---|---|
| (f) K/(g + g₁) | 5 | German launches +0.96 / +0.77 m at 4 s |
| (e) two regimes | 5 | P6 inD and SinD, P7 0.91 s, P8 position 2 2.15 s, L1 1,623 |
| (j) (f) with a launch gain K₁ | 6 | P6 inD 4 s +0.52 m (interval -0.33 to 1.43, 23 launches) |

(j)'s one miss was explained before the refit. Its launch regime (under 6.5 m/s, leader pulling away) also covers congested following in the next-second tables, and those pull K₁ below what German launches need. SinD at -0.04 m left room to move every site by -0.1 m.

**One refit (F837):** the launch sets weighted as heavily as the five next-second tables together, which is how the decision rule ranks them. Intervals were unchanged. With each driver's past factor there is no system-scale miss.

**The random-factor check (F838):** with random personal factors, one draw of 42 factors put rounD 4 s at +0.52 m. Plan rule 6 says one seed is no result, so it was rescored over 20 draws: mean +0.44 m, 85% of draws inside. Every cell is inside on the mean.

### The law (MODEL.md, round 5)

a = K₁ min(Δv, 1.5)/(g + g₁) below 6.5 m/s while the leader pulls away; otherwise K min(Δv, 1.5)/(g + g₁) + c_a a_l. Then + k_p max(e, 0) − k_g max(−e − 0.5 s, 0).

| Number | Value | Source |
|---|---|---|
| K | 4.711 m/s | fitted, P1 + P6 (F837) |
| g₁ | 5.394 m | fitted, F801's saturating gain |
| c_a | 0.452 | fitted |
| k_g | 0.0789 m/s² per s | fitted; DRIVER.md measured 0.2-0.5, contradicted |
| k_p | 0.1516 m/s² per s | fitted; ROUND2 measured 0.025-0.044 on 1-30 s, contradicted (this is P2's miss) |
| K₁ | 10.956 m/s | fitted on launches |
| T(v), s0 1.7 m, τ_r 0.5 s, Δv cap 1.5 m/s, band edge 0.5 s, noise 0.38 m/s² over 0.75 s, start 1.0 s after the car ahead, r₁ 0.78 s, T_v 1.0 s, desired gap from standstill | unchanged | DRIVER.md, ROUND2.md |

Kernel: `md_cmd` in `common.wgsl`. g₁ and K₁ sit in `md_u.z` and `md_u.w`, the struct's spare slots, so no struct changed; constants are in `world.rs` (`MD_K` … `MD_K1`). Twin: `fit_driver.command_r5`.

**Kernel against twin (F839): 0.0026 m/s RMS (max 0.25), spacing 0.020 m; pass.**

### Scores

**System scale, in the twin (F837/F838).**

| Pattern | Result |
|---|---|
| P5 | 1.79 m |
| P6 at 2 / 4 / 8 s, rounD | +0.16 / +0.42 / +0.39 m |
| P6, inD | +0.10 / +0.44 / +0.01 m |
| P6, SinD Changchun | -0.18 / -0.09 / +0.37 m |
| P7 | 1.19-1.25 s |
| P8 | 2.80 / 2.40 / 2.16 s |
| P9 | 19.3 km/h |
| L1 | 1,848 veh/h |
| S1 | 2.07 s |

**T0 at dt 0.25 (F840-F851).** 126 pass, 74 fail of 200; round 2 100 / 99, main's one driver 142 / 60.

| Realism row | Result | Interval |
|---|---|---|
| L1 at 50 km/h | 1,874 veh/h | 1,640-1,900: pass |
| L1 at 100 km/h | 1,818 veh/h | reported |
| S1 | 1.93 s | 1.8-2.2: pass |
| W1 | car 30 dips 3.2 m/s less than the leader; damped, wave -15 km/h | reported |
| Start wave | 24 km/h | reported |

**Held out, opened once (HOLDOUT.md; F854-F862).**

| Recording | Test | Round 5 | Round 1 | One driver | Bound | Verdict |
|---|---|---|---|---|---|---|
| I-90/94 moving | 30 s spacing | 6.06 m (5.95-6.15) | 7.33 | 5.80 | 6.17 | **pass** |
| | next-second CRPS | 0.226 (0.215-0.238) | 0.211 | 0.648 | null 0.355-0.384 | **pass** |
| | classifier | 0.804 (0.798-0.811) | 0.827 | 0.865 | 0.70 | fail |
| DLR HT 14-16 UTC | 30 s spacing | 16.47 m (16.23-16.82) | 20.06 | 17.10 | 16.24 | fail by 0.23 m |
| | next-second CRPS | 0.234 (0.226-0.241) | 0.234 | 0.871 | null 0.334-0.354 | **pass** |
| highD location 6 | 10 s spacing | 4.23 m (4.13-4.27) | 4.33 | 7.94 | 6.60 | **pass** |
| | next-second CRPS | 0.158 (0.151-0.166) | 0.156 | 0.895 | null 0.246-0.268 | **pass** |
| SinD Xi'an | follower launches, 2 / 4 / 8 s | -0.66 / -1.58 / -2.49 m (17) | | | ±0.5 / 0.5 / 1.0 | fail: the law runs ahead |
| | first car to 1.5 m/s; peak | 1.8 s (1.2-2.0); 1.41 m/s² (1.28-1.77) against the law's 2.0 s, 1.77 | | | widened intervals | **pass**, at the edge |

**Cut-in, reported only (F853).** Report 18 asks what share w of the asked braking a follower applies after a cut-in. With this law as the "plain following", real followers' best w is:

| Site | Best w | Following the merger fully, RMSE over best w |
|---|---|---|
| I-80 | 1.13 | 1.004 |
| US-101 | 1.12 | 1.005 |
| I-395 | 0.88 | 1.013 |
| I-294 L1 | 1.17 | 1.053 |

So real followers take about all the braking this law asks for. Report 18's 0.39-0.68 was measured against report 05's law, whose gain grows as √(15/g) at short gaps; here the gain saturates at K/(g + 5.4 m).

**Lane-change rows with `--tune lc_measured=1` (F852).** 24 pass, 7 fail of 31 (off 22 / 8; the one driver with it 23 / 8). LANECHANGE.md's three regressions stay (LC3 F023, LC5 F264, LC5 F403 dv 5). LC4 falls to 0.67, and LC6 turns into a -9% "drop". The cut-in result above says these do not come from following the merger too hard.

## Known misses, written down

Individual scale (not filtered under branch 2):

1. **P2: open gaps close two to three times as fast as recorded.** 0.80 / 0.91 / 0.81 / 0.88 against 0.31 / 0.28 / 0.25 / 0.41. 30 s RMSE: DLR HT 24.9 m (round 2 20.8), I-90/94 st. 5.8 (5.3), I-395 10.6 (9.6). k_p is 0.15 against a measured 0.025-0.044. With the second leader and own free speed added (report only) the law still closes 0.45-0.74.
2. **P1 on I-395:** CRPS 0.181 against round 2's 0.159 (+14%, bound +10%). Its leaders are paired correctly, so this is I-395's own flat gain.
3. **P4 at 2 m/s:** 3.66 m against 3.7-5.1.
4. **k_g 0.079** against DRIVER.md's measured 0.2-0.5.
5. **Held out:** DLR HT 30 s spacing 0.23 m over its bound; the classifier at 0.80 (cue: jerk p95 0.32, then time gap and minimum spacing); SinD Xi'an follower launches run ahead by 1.6 m at 4 s. That last one is STRUCTURE.md's conflict 2 (sites launch differently at the same gap) seen on held-out data.

System scale, T0 rows forecast from the law's own equations:

| Row | Kernel | Twin forecast |
|---|---|---|
| F840 L1 at 30 km/h | 1,798 veh/h | 1,659 |
| F842 S1 | 1.93 s | 2.09 |
| F843 S2 cars 7, 9 | short by 0.26, 0.35 s | |
| F844 W1 | 3.2 m/s | 4.0 m/s |
| F847 ring peak | 1,886 veh/h | 2,413 |
| F848 congested speed at 10 / 12 m | 4.25 / 6.22 m/s | 2.92 / 4.69 |
| F849 L6 | 604 veh/h | 687 |

- **F848** follows from the law: with k_g 0.079 against noise of 0.38 m/s², drivers drift more than 0.5 s inside their gap before braking matters.
- **F849** passes without noise (665 veh/h).
- **F840 and F842 are not explained (F863).** With noise and spread off, kernel and twin agree at 50 km/h (2%) but differ at 30 km/h (8%) and at the signal (0.15 s), just past the launch regime. The single-follower check agrees at 0.003 m/s. The realism verdicts do not depend on it: both kernel and twin pass L1 and S1.

Against main's one driver, beyond the rows it fails too:

- N4, merge both saturated: 640 against 928 veh/h.
- N3 storage at spill.
- S4 F290.
- G5 F259.
- C-S8 at b 0.

The give-way, roundabout, lane-drop and grid locks fail for both drivers.

## Default: not changed

The brief's rule makes the law the default if the T0 system-scale rows and the held-out next-second response pass. Both do.

It stays off, because of the stop rule "a miss gets explained before anything else changes". Two misses are unexplained and touch the system scale: Xi'an's launches (F861) and the kernel-twin difference at low speed (F863). Also, the default suite would be this measured run: 126 / 74 against main's 142 / 60. `--tune measured=0` and `--sumo-compat` are unchanged.

The bench (`scripts/bench`, config `measured`) still measures round 2's law on main (F951: level 0 broke, with one collision and 25 cars lost). It was not rerun for round 5. It runs on main, so it measures round 5 once this branch is merged.

## For STATUS.md

T1 One driver: round 5 shipped law (j) behind `--tune measured=1` (`measure/OPENGAP.md`).

- Open gaps stay open mostly because drivers watch the second car ahead (0.6-1.0 of P2's conflict on three tables) and, on DLR HT, because the follower already drives at its own desired speed (0.27). Pairing is not a cause.
- I-90/94 st. stays unexplained, so the law ships by system-scale patterns: L1 1,874 veh/h at 50 km/h, S1 1.93 s; T0 126 / 74.
- Held out: next second passes on all three recordings; 30 s spacing passes on I-90/94 and highD, and fails DLR HT by 0.23 m.
- Known misses: P2 closing 2-3 times too fast, Xi'an launches 1.6 m ahead at 4 s, classifier 0.80.
- Not the default.

Reproduce:

- Part 1: `python3 -I scripts/measure/opengap.py build | free | second | pairing | explain | diagnose | shipped`
- Fit: `SHIP_W=1 SHIP_OUT=ship_jw.json python3 -I scripts/measure/ship.py fit j`, then `ship.py seeds`
- Twins and launches: `scripts/theory/md_platoon.py`, `F101_SITE=I294L1 F101_MAXN=1000 python3 -I scripts/replay/md_twin.py --gpu`
- T0: `scenes.py --driver measured --dt 0.25 --gpu`
- Held out: `scripts/replay/heldout_r5.sh`, `scripts/measure/xian.py`
- Cut-in: `scripts/measure/cutin.py`
