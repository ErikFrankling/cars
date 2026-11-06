# The measured driver, round 3: which structure of the following law

7 November 2026. Branch `md3-structure`. Forecasts F800-F809 in `foundations/forecasts.csv`, each committed before its run. Script `scripts/measure/structure.py`, numbers in [structure.json](structure.json). No held-out recording was read ([HOLDOUT.md](HOLDOUT.md)).

**Result: no structure survives.** Seven structures were each fitted on all the non-held-out patterns jointly and scored on every pattern. Every one misses at least seven patterns beyond the intervals written in F800. By the brief's stop rule, nothing went into the kernel, the held-out set stays closed and the measured driver stays off by default.

## Why this round

Rounds 1 and 2 built a = K·min(Δv, 1.5)/g + c_a·a_l + k_p·max(e, 0) − k_g·max(−e − 0.5 s, 0) from measured parts. It answers the next second like real drivers on held-out recordings, but lane capacity is 1,104 veh/h against 1,640-1,900, and followers fall 1.5-2 m behind real ones in the first 4 s of a launch. The rule was not to attack this a third time by measuring another part, but to question the structure (report 22 §2: filter, don't fit).

## 1. The pattern list (F800)

Every number is from recordings not held out. "Filter" means a candidate that misses the interval is rejected. "Report" means the pattern is scored but rejects nothing.

| | Pattern | Measured | Interval | Source | Role |
|---|---|---|---|---|---|
| P1 | Next-second speed change, CRPS with the frozen noise, five tables | the round 2 law: 0.134 / 0.175 / 0.192 / 0.200 / 0.161 (highD, DLR HT, I-90/94 st., I-294 L1, I-395); constant speed 0.29-0.44 | under constant speed, at most 10% over round 2 | follow.py tables; round 2 passed the held-out CRPS | filter |
| P2 | Open gaps (1 s or more above T(v)) behind the same leader: share of the median excess closed in 30 s | DLR HT 0.35, I-90/94 st. 0.27, I-294 L1 0.25, I-395 0.41 | recorded ± 0.15; and 30 s spacing RMSE at most 5% over round 2's per table | gapclose.py windows, shrunk own reference | filter |
| P3 | Steady time gap by speed | T(v): 1.6 s at 6.5 m/s to 0.95 at 30 | | DRIVER.md (selected followers, ROUND2 §2) | report |
| P4 | Quasi-steady gap at 1 / 2 / 3 / 5 m/s | 2.7-3.9 / 4.0-4.8 / 5.1-5.9 / 6.1-8.6 m over five sites | site range ± 0.3 m | queues.json F611 | filter |
| P5 | Standstill gap after stopping behind a stopped leader | rounD 1.83 (1.74-1.89), inD 1.83-1.96 | 1.6-2.0 m | queues.json F609 | filter |
| P6 | Queue launches, 8 s from the follower's motion onset behind its recorded leader: median gap error at 2 / 4 / 8 s | 0 by definition (42 rounD, 23 inD, 168 SinD Changchun launches) | ± 0.5 / 0.5 / 1.0 m per site | queues.py launch series | filter (Lankershim, Tianjin, Chongqing: report) |
| P7 | Start delay, the car ahead passes 1 m/s to this car passes 1 m/s, positions 2-6 | rounD 1.20, inD 1.37, Lankershim 1.08, flat | 1.0-1.45 s, trend under 0.1 s per position | queues.json F612 | filter |
| P8 | Headway at the line by queue position | Lankershim 2.99 / 2.34 / 1.97 s at positions 2 / 3 / 6 | ± 0.35 s | queues.json F613 | filter (SinD Changchun 4.1-2.4 s: report, its starts are 1.6 s) |
| P9 | Start wave | (s0 + L)/start delay, 18-25 km/h | 17-26 km/h | P5 and P7 | filter, derived |
| P10 | Wave growth along a platoon | no non-held-out recording on disk shows one | | | not scored |
| P11 | Command noise | 0.38 m/s² over 0.75 s | | noise2.json F615 | the same part in every candidate |
| P12 | L1 capacity at 50 and 100 km/h; S1 discharge headway from car 10 | 1,640-1,900 veh/h (R §2); 2.0 s (DLR UT, Lankershim position 6) | 1,640-1,900; 1.8-2.2 s | | filter, derived, never fitted |

The platoon patterns (P4, P5, P7-P9, P12) come from the twin of a queue on one lane (scenes' dt 0.25, the kernel's noise and personal gap factor, the kernel's start rule of 1.0 s after the car ahead moves). The others are rollouts of the kernel's equations (md_twin.py order: command, free driving, 0.5 s response, stop law, certificate, start hold) from the recorded state behind the recorded leader.

**Tensions in the list before any fit.** P2 asks for a weak pull at speed (0.025-0.044 m/s² per s of time gap). P5 and P6 ask a follower to close up near standstill and during a launch. P8 at position 2 (2.99 s) asks for a late second car, while P6 asks it to keep up once moving. P1 on I-395 has a closing gain that rises with gap (F801), against every other table.

## 2. Before the candidates: the closing gain against gap (F801)

The command gain on closing speed was fitted per gap bin, through the 0.5 s response, one second ahead (`structure.py gain`):

| Gap, m | 1.5-3 | 3-6 | 6-10 | 10-15 | 15-25 | 25-40 | 40-70 |
|---|---|---|---|---|---|---|---|
| I-90/94 st., gain /s | 0.70 | 0.62 | 0.52 | 0.41 | 0.30 | 0.18 | 0.10 |
| highD | | | | 0.15 | 0.14 | 0.09 | 0.05 |
| Launches, rounD | 1.09 | 0.87 | 0.58 | | | | |
| Launches, SinD Changchun | 0.79 | 0.65 | 0.54 | 0.35 | 0.15 | 0.09 | |

- Inside a table, gain × gap rises with gap (I-90/94 st. 1.7 → 5.5; I-395 0.15 → 5.1). The gain decays more slowly than 1/g, roughly like K/(g + g_1) with g_1 3-8 m. Only highD is near 1/g.
- At the same gap, launches have the gain of congested following on I-90/94 st. They are not a different regime in Δv. But the share of the leader's acceleration on launches is −0.09 to 0.21, against 0.1-0.8 in following.
- At the same gap, highD's gain is a third of I-90/94 st.'s (12-13 m: 0.15 against 0.41). Speed matters too.

So the round 1-2 form 1/g is too steep: at 6-15 m it gives 0.2-0.4 /s where launches show 0.35-0.6. That is the measured part behind round 2's launch miss. Candidates (f) and (g) carry it.

## 3. Candidates

Each was fitted on P1 + P2 (30 s windows, errors at 10 and 30 s) + P6 (errors at 2, 4, 6, 8 s): 12 data sets, each scaled by the round 2 law's RMS on it and weighted equally, with a soft-L1 loss. Fixed in all: T(v), s0 1.7 m, the 0.5 s response, the 1.5 m/s cap where Δv is capped, the noise, the start rule, the stop law and the certificate.

| | Structure | Free numbers, fitted |
|---|---|---|
| round 2 | K min(Δv,1.5)/g + c_a a_l + one-sided band | K 2.69, c_a 0.51, k_g 0.28, k_p 0.025 (frozen, not refitted) |
| (a) | same, refitted on every pattern | K 4.87, c_a 0.35, k_g 0.31, k_p 0.067 |
| (b) | Newell-anchored (Laval and Leclercq 2010; Chen, Laval, Zheng 2012): K min(v_l(t−τ) − v, 1.5)/g + c_a a_l + k_N (g − s0 − D_τ)/max(v,1); τ(v) = f(T(v') − s0/v'), which is 1.34 s below 6.5 m/s; D_τ the leader's distance over the last τ (true history in the twin) | K 6.69, c_a 0.77, k_N 0.092 |
| (c) | Full velocity difference (Jiang, Wu, Zhu 2001): κ(V(g) − v) + λΔv + c_a a_l, V the inverse of the round 2 desired gap | κ 0.0094, λ 0.29, c_a 0.52 |
| (d) | IDM (Treiber, Hennecke, Helbing 2000) with the measured desired gap: a_m(1 − (v/v0)⁴ − (s*/g)²), s* = g*(v) + vΔv/(2√(a_m b)) | a_m 0.74, b 2.24 |
| (e) | Two regimes (after Wiedemann 1974): below 6.5 m/s with the leader pulling away, K_1 min(Δv,1.5)/g and no c_a; otherwise (a) | K 4.49, c_a 0.45, k_g 0.31, k_p 0.049, K_1 8.0 |
| (f) | Saturating closing gain (F801): K min(Δv,1.5)/(g + g_1) + c_a a_l + band | K 6.79, g_1 3.50 m, c_a 0.33, k_g 0.21, k_p 0.075 |
| (g) | Speed-scaled closing gain: K min(Δv,1.5)/(g + t_1 v) + c_a a_l + band | K 6.42, t_1 0.64 s, c_a 0.36, k_g 0.26, k_p 0.061 |
| (f'), (e') | (f) and (e) with k_p held at 0.025 (F809) | f: K 6.59, g_1 2.61, c_a 0.35, k_g 0.24; e: K 4.49, c_a 0.43, k_g 0.32, K_1 8.24 |

## 4. Scores on every pattern

| Pattern | round 2 | a | b | c | d | e | f | g | f' | e' |
|---|---|---|---|---|---|---|---|---|---|---|
| P1 CRPS highD | 0.134 | 0.136 | 0.150 | **0.200** | **0.361** | 0.135 | 0.139 | 0.135 | 0.138 | 0.135 |
| P1 CRPS DLR HT | 0.175 | 0.174 | 0.193 | **0.266** | **0.384** | 0.175 | 0.177 | 0.173 | 0.176 | 0.174 |
| P1 CRPS I-90/94 st. | 0.192 | 0.190 | 0.203 | 0.199 | **0.328** | 0.196 | 0.187 | 0.189 | 0.189 | 0.197 |
| P1 CRPS I-294 L1 | 0.200 | 0.211 | 0.214 | **0.233** | **0.433** | 0.208 | 0.215 | 0.212 | 0.213 | 0.209 |
| P1 CRPS I-395 (bound 0.177) | 0.161 | 0.175 | **0.204** | **0.186** | **0.412** | **0.178** | **0.179** | 0.175 | **0.178** | **0.179** |
| P2 closed in 30 s, DLR HT (rec. 0.35) | 0.40 | 0.52 | 0.51 | 0.25 | **0.67** | 0.44 | 0.47 | 0.48 | 0.25 | 0.31 |
| P2 I-90/94 st. (0.27) | **0.47** | **0.64** | **0.48** | 0.41 | **0.75** | 0.40 | **0.64** | **0.57** | 0.28 | 0.20 |
| P2 I-294 L1 (0.25) | 0.33 | **0.53** | **0.49** | 0.35 | **0.61** | 0.39 | **0.52** | **0.48** | 0.20 | 0.21 |
| P2 I-395 (0.41) | 0.53 | 0.60 | **0.62** | **0.63** | **0.81** | 0.48 | 0.60 | 0.55 | 0.31 | 0.32 |
| P2 30 s RMSE DLR HT / I-90 / I-294 / I-395, m | 19.8 / 5.7 / 15.4 / 8.7 | 19.4 / 5.2 / 13.4 / 8.8 | 20.7 / 4.9 / 14.5 / 8.8 | **22.1** / 4.6 / 14.2 / 8.9 | **24.2 / 6.9 / 17.1 / 9.7** | 18.7 / 4.8 / 12.9 / 8.8 | 19.4 / 5.1 / 13.2 / 8.8 | 19.6 / 5.0 / 13.3 / 8.7 | 18.0 / 4.6 / 12.8 / 8.9 | 18.2 / 4.8 / 13.3 / 8.9 |
| P4 gap at 1 / 2 / 3 / 5 m/s, m | 2.9 / 4.2 / 5.5 / 8.8 | 3.0 / 4.2 / 5.4 / 7.9 | 3.1 / 4.5 / 6.0 / **9.0** | 3.3 / 5.0 / **6.6 / 9.7** | 3.0 / 4.4 / 5.7 / 8.5 | 2.8 / 4.0 / 5.2 / 7.2 | 2.9 / 4.1 / 5.4 / 8.0 | 3.0 / 4.1 / 5.4 / 7.9 | 2.9 / 4.1 / 5.4 / 7.9 | 2.8 / 4.0 / 5.2 / 7.2 |
| P5 standstill gap, m | **2.51** | **2.46** | 1.75 | 1.73 | 1.74 | **2.77** | **2.07** | **2.64** | **2.95** | **3.22** |
| P6 rounD 2 / 4 / 8 s, m | +0.48 / **+1.50 / +1.72** | −0.03 / **+0.77 / +1.09** | **+1.33 / +2.26 / +1.56** | **+0.96 / +2.60 / +2.95** | **+1.25 / +1.87** / +0.59 | −0.41 / +0.41 / +0.88 | +0.27 / **+1.01 / +1.23** | −0.18 / **+0.65 / +1.10** | +0.23 / **+1.06 / +1.45** | −0.45 / +0.35 / +0.83 |
| P6 inD | **+0.53 / +1.75 / +1.44** | −0.12 / **+0.70** / +0.88 | **+1.16 / +2.65 / +1.74** | **+0.81 / +1.86 / +2.49** | **+1.37 / +3.49 / +2.47** | −0.45 / +0.36 / +0.41 | +0.31 / **+0.96** / +0.64 | −0.23 / +0.33 / +0.78 | +0.19 / **+1.15 / +1.19** | **−0.57** / +0.27 / +0.32 |
| P6 SinD Changchun | +0.25 / **+1.60 / +2.77** | −0.28 / −0.10 / +0.45 | **+0.81 / +1.84 / +2.59** | +0.50 / **+1.82 / +3.46** | **+1.35 / +4.89 / +9.29** | −0.48 / **−0.66** / +0.05 | +0.03 / +0.45 / +0.94 | **−0.51 / −0.53** / +0.01 | −0.01 / +0.41 / +0.87 | **−0.55 / −0.80** / −0.13 |
| P6 Lankershim (report) | −0.04 / +1.36 / +6.61 | −0.49 / −0.15 / +2.10 | +1.24 / +3.93 / +7.75 | +0.38 / +2.14 / +4.50 | +2.00 / +8.83 / +25.4 | −0.62 / −0.15 / +2.14 | −0.03 / +1.19 / +4.15 | −0.67 / −0.55 / +1.85 | −0.16 / +0.59 / +3.48 | −0.71 / −0.37 / +1.85 |
| P7 start delay, positions 2-6, s | 1.13-1.27 | **0.97**-1.29 | 1.37-**1.69** | 1.34-1.38 | **1.85-2.45** | **0.91**-1.33 | 1.14-1.26 | **0.92**-1.28 | 1.10-1.26 | **0.91**-1.32 |
| P8 line headway positions 2 / 3 / 6, s | 3.06 / 2.66 / **2.42** | 2.70 / 2.59 / 2.17 | **3.47** / 2.91 / **2.55** | **3.37** / 2.73 / **2.47** | **5.12 / 4.06 / 3.39** | **2.56 / 2.70** / 2.02 | 3.06 / 2.45 / 2.17 | **2.61** / 2.55 / 2.18 | 2.95 / 2.45 / 2.12 | **2.54** / 2.65 / 2.00 |
| P9 start wave, km/h | 19 | 19 | **16** | 17 | **11** | 19 | 19 | 19 | 19 | 19 |
| P12 L1 50 km/h, veh/h | **1,201** | 1,691 | **1,611** | **1,593** | **1,316** | 1,671 | 1,776 | 1,663 | **1,620** | **1,538** |
| P12 L1 100 km/h | **1,084** | **1,518** | 1,754 | **2,045** | **1,442** | **1,499** | **1,639** | **1,483** | **1,446** | **1,313** |
| P12 S1 headway, s | **2.56** | 2.11 | 2.32 | 2.15 | **2.90** | 2.06 | 2.06 | 2.12 | 2.07 | 2.09 |
| Patterns missed | 13 | 10 | 24 | 21 | 33 | 7 | 9 | 10 | 8 | 9 |

Bold is a miss. P3 (report): every band law keeps T(v) behind a steady leader for 120 s (1.48 / 1.15 / 0.95 s at 10 / 20 / 30 m/s); IDM drifts to 1.84 / 1.76 / 1.68 s.

## 5. Why each was rejected

- **Round 2**, not refitted: launches (P6 at 4 and 8 s on every site), capacity and discharge (P12), standstill gap (P5), and P2 on I-90/94 st.
- **(a)** refitted: K rises from 2.69 to 4.87 and k_p from 0.025 to 0.067. That fixes SinD Changchun and P12 at 50 km/h. German launches stay 0.7-1.1 m behind, open gaps close twice as fast as recorded (P2, all four tables), position 2 starts in 0.97 s, and L1 at 100 km/h is 1,518.
- **(b) Newell-anchored**: answering the leader's speed τ ago responds later than answering its speed now, so launches fall further behind (+1.8-2.7 m at 4 s). The anchor pull, at 0.092, closes open gaps at speed too fast and still does not hold launches. It is worse than (a) on the next second (I-395 0.204).
- **(c) FVDM**: one gain on Δv cannot be 0.6-1 /s at 3-8 m and 0.05-0.15 /s at motorway gaps (F801). The fit picks 0.29, which loses the next second on four tables and the launches on every site. Its pull κ 0.0094 /s gives too much spacing at 3-5 m/s, while L1 at 100 km/h is 2,045.
- **(d) IDM**: rejected everywhere. Its closing response vanishes near standstill and its gap term closes open gaps 2-3 times as fast as recorded. A fit that keeps launches near its a_m gives a_m 0.74, so launches and starts are slow (start delay 1.9-2.5 s, line headway 5.1 s).
- **(e) Two regimes**: the best count (7 misses). The launch regime (K_1 8.0) makes position 2 start in 0.91 s and cross the line 0.4 s early (P8 2.56 against 2.99 ± 0.35). It runs ahead on SinD Changchun (−0.66 m at 4 s) while fitting rounD and inD. It misses P5 (2.77 m), L1 at 100 km/h (1,499) and I-395's CRPS by 0.3%.
- **(f) Saturating gain**: the best on launches and P12 at 50 km/h (1,776) with P7, P8 and P9 inside. The joint fit raises k_p to 0.075. With it, open gaps close in 30 s by 0.52-0.64 against 0.25-0.27 on I-90/94 st. and I-294 L1, and German launches stay 1.0-1.2 m behind at 4-8 s. It misses P5 (2.07 m), L1 at 100 km/h by 1 veh/h (1,639) and I-395's CRPS by 1%. Held at k_p 0.025 (f', F809), P2 passes on all four tables, but launches fall further behind (+1.06 / +1.15 m at 4 s) and L1 at 50 km/h drops to 1,620.
- **(g) Speed-scaled gain**: like (a) and (f). Open gaps close too fast on I-90/94 st. and I-294 L1, rounD stays +0.65 m behind at 4 s while SinD runs ahead, position 2 starts in 0.92 s, and L1 at 100 km/h is 1,483.

## 6. Which patterns conflict, in every structure

1. **The pull: gap closing at speed (P2) against launches and capacity (P6, P12).** Wherever the joint fit lets k_p rise (a, e, f, g: 0.049-0.075), it buys launches and capacity, and open gaps at speed close 0.1-0.4 faster than recorded. Held at 0.025 (F809), P2 passes and German launches and L1 fall back. Making the closing gain itself stronger at small gaps, as F801 measured (f), moves the conflict but does not remove it.
2. **Standstill (P5) against the closing term.** Every structure with a closing response that brakes in proportion to Δv/g and a weak pull (round 2, a, e, f, g, f', e') stops 2.1-3.2 m behind a stopped leader, against 1.7-1.9 m recorded. The stronger the pull, the closer the stop (f 2.07 at k_p 0.075, f' 2.95 at 0.025): this is the same pull at the other end of the speed range. Only structures with a strong spacing pull at low speed (b, c, d) stop at 1.73-1.75 m, and those miss the next second and the launches. Real queues compact as cars stop, not after (ROUND2 §3), so a near-standstill rule cannot rest on creep.
3. **The second car (P7, P8) against keeping up (P6).** A launch gain strong enough to hold rounD and inD (e, g, a) starts position 2 in 0.91-0.97 s and brings it to the line 0.4 s early (2.54-2.70 s against 2.99). The same gain runs ahead on SinD Changchun. The sites differ: SinD's launches want less than the German ones at the same gap.
4. **L1 at 100 km/h (P12).** Every structure that passes the next second gives 1,446-1,639 veh/h, below 1,640. L1 at 50 km/h passes for a, e, f and g (1,663-1,776). The 100 km/h interval is the urban saturation flow of R §2, written into F800 for both speeds. Whether motorway queue discharge belongs in the same interval was not checked against a recording.
5. **I-395 (P1).** Every five-number structure is 9-11% over round 2's CRPS on I-395. I-395 is the one table whose closing gain rises with gap (F801). Round 2's frozen numbers sit nearer I-395 because the next-second fit alone weighted it a fifth; here launches and 30 s windows pull the numbers away.

Conflicts 1 and 2 are one fact seen twice: real drivers close up near standstill and keep up during a launch, yet barely pull an open gap closed at speed. Every structure tested here has one pull for both, measured in seconds of time gap. Two hypotheses, neither tested here: a pull that acts in metres below a few m/s (closing the last metre in a fixed time); or a pull that depends on whether the gap is opening (the leader pulling away) or merely open.

## What was not done, and why

- Step 4 (kernel) and step 5 (held out) were not done: no survivor. `--tune measured=1` and `measured=0` are unchanged. HOLDOUT.md is unchanged; no held-out recording was read.
- No parameter was tuned to a scene, to capacity or to held-out data. P12 entered no fit.
- The marginal misses (f on I-395 by 1%, on L1 at 100 km/h by 1 veh/h; e on I-395 by 0.3%) were not relaxed after the fact. With them waived, (f) still misses P2, P5 and P6, and (e) still misses P5, P6, P7, P8 and P12.
- No new behaviour was measured. Per rule 9, the structure question is now at its third round on the same misses (capacity and launch). The next step is a measurement of the near-standstill and opening-gap pull (conflicts 1 and 2), not another candidate.

Reproduce: `python3 -I scripts/measure/structure.py data`, `gain`, `filter a b c d e f g`, `profile` (each a few minutes; the filter about 25).
