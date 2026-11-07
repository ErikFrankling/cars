# The measured driver, round 4: is a slow open gap just a personal preference?

7 November 2026. Forecasts F810-F821 in `foundations/forecasts.csv`, each committed before its run. Scripts `scripts/measure/patterns.py` (step 1) and `scripts/measure/personal.py` (steps 2-4). Numbers in [patterns.json](patterns.json) and [personal.json](personal.json). No held-out recording was read ([HOLDOUT.md](HOLDOUT.md)). DLR HT blocks 24-29 (14-16 UTC) sit on disk and were not opened. No kernel change and no GPU.

**Result: the hypothesis fails, and no structure survives.** Each driver's own preferred gap, read from its past, explains only 12-24% of an open gap. The rest closes with a time constant of 45-60 s, which is a weak pull. Two candidates from round 3 and two new ideas were refitted with a strong or free pull towards that personal gap and scored on every pattern. All miss 7 or more patterns. Two patterns changed in step 1, each for a reason written before any score.

## The hypothesis

Drivers keep a personal time gap for kilometres (DRIVER.md: log-SD 0.27). In ROUND2.md, k_p rose to 0.084-0.139 when each driver's target was read from its own future track. So most open gaps in P2 might be preference, not error. If so, a strong pull towards a personal gap would pass P5, P6 and P12, and P2 would pass once each simulated follower carries its own preference, estimated from its past only.

## Step 1: the patterns, checked before reuse

| Check | Result | What changed |
|---|---|---|
| **(a) P8, Lankershim line headways** (F810) | NGSIM's front-bumper convention, unsmoothed positions and dropping crossings near a tracking jump each move positions 2 / 3 / 6 by 0.05 s or less. But position 2 depends on the line: 4.60 / 2.99 / 2.59 / 2.45 s with the line 0 / 1 / 3 / 5 m past the head's front. Position errors of Coifman and Li's size (1 m per vehicle, plus 0.5 m over 2 s) move position 2 by **+0.46 s** at round 3's 1 m line and by +0.10 s at 4 m. Queue heads that stand at the signal sit a median 2.8 m (p10-p90 0.6-6.9) behind the real stop line (NGSIM's intersection entry). There the headway is 2.55 (2.40-2.75, n 30) / 2.25 (2.15-2.50, n 16) / 1.90 s at positions 5 and up (n 10). Over all queues at the stop line it is 2.40 / 2.20 / 1.90 / 2.05 / 2.00, which matches report 05's 2.4 / 2.1 / 2.0 / 1.9 | **P8 replaced**: real stop line, signal-head queues, 2.55 / 2.25 / 1.90 s ± 0.35. In the scene the head stands 2.8 m behind the line. A line 1 m past the head is inside the tracker's error, and round 3's 2.99 s came from it. Positions 3 and 6 held up in every variant |
| **(b) P12 at 100 km/h** (F811, F814) | DLR HT 06-14 UTC never comes near capacity. Its busiest 15 min carry 1,080 veh/h on the fast lane, with no breakdown and no congested minute. highD: busiest sustained flow 2,188 veh/h on location 1's median lane (trucks 0.5%), then 1,932 and 1,304 on the lanes further out. There is no breakdown and no jam head discharging into free flow. highD's only congestion (location 1, recordings 25, 26, 36, 46) is synchronized flow swinging between 15 and 60 km/h across the whole 400 m. One recovery fits F814's definition | **P12 at 100 km/h becomes report only.** No non-held-out recording shows a motorway queue discharging, so no interval can be measured. The urban 1,640-1,900 never applied there. Busiest sustained motorway flow, for context: 2,188 veh/h per lane |
| **(c) I-395** (F812) | Congested (70% of samples under 10 m/s, median 8.2), short tracks (median 36 s), oblique cameras, speed scatter 0.107 m/s (highD 0.003), 76% default lengths, and 106 of 2,255 lane changes passing screening (report 05). The CRPS ratio of round 3's (e) and (f) to round 2 is the same in both hours: (e) 1.106 / 1.100 (all 1.103, 1.095-1.114), (f) 1.104 / 1.121. Its closing gain is flat in gap at every speed: 0.07-0.08 /s from 6 to 70 m at 2-7 m/s, and 0.02-0.07 at 3-6 m where I-90/94 st. has 0.62-0.70 | **Stays a P1 filter**, by the rule written first: it is self-consistent. The flat gain suggests the paired leader is often not the car being followed (lane labels from oblique cameras). That is a hypothesis for a measurement (below). It was not used to drop the table |
| **(d) Fits and scorer** (F813) | (e) from 4 starts: objective 5.818-5.826 against round 3's 5.824, parameters within 5%. (f): 5.5315-5.5320 against 5.5315. Every start stopped on its tolerance in 17-45 evaluations. Code written separately from the scorer gives P5 2.512 m (scorer 2.51), and P2 on I-294 L1 recorded 0.248 and modelled 0.333 (scorer 0.248, 0.333) | Converged; the scorer is right |

## Step 2: open gaps split into a personal and a transient part (F815, F816)

The personal factor f_past is the driver's mean log of time gap over T(v), taken over steady samples (|Δv| under 1 m/s, v over 5 m/s) before the window starts. It is shrunk towards 1 by its reliability (0.27 persistent log-SD against 0.47 between 10 s windows). Window (A) uses other leaders only, the trait. Window (B) uses everything before release, current leader included.

| | highD | DLR HT | I-90/94 st. | I-294 L1 | I-395 |
|---|---|---|---|---|---|
| Open windows (P2's selection) | 400 | 12,591 | 2,915 | 1,031 | 2,174 |
| With a past, (A) / (B) | 0.5% / 26% | 25% / 53% | 6% / 48% | 26% / 70% | 0.4% / 17% |
| Persistent share of the median open excess, (A) | | **0.145** | **0.124** | **0.192** | |
| Same, (B) | 0.158 | 0.223 | 0.207 | 0.243 | 0.186 |
| Transient part closed in 30 s, open windows, (A) | | 0.37 | 0.63 (n 173) | 0.52 | |
| Coefficient of the transient part on the change over 10 / 30 s, (A) | | 0.16 / **0.48** (0.44-0.52) | 0.39 / 0.36 (0.07-0.68) | 0.29 / 0.55 (0.35-0.82) | |
| Coefficient of the persistent part, 30 s, (A) | | −0.06 | −1.2 (wide) | −1.0 (wide) | |

- **The premise fails.** The personal part is 12-24% of an open gap's excess, 0.21-0.37 s of 1.42-1.98 s. DRIVER.md's variances predict this even with the trait known exactly. The persistent log-SD of 0.27 is a third of the 0.47 window variance, so a gap 1.45 s open carries about 0.35 s of preference.
- **The transient part closes slowly too.** It has a time constant of 45-60 s (0.48 in 30 s on DLR HT, the largest sample). That is faster than the whole excess, but nowhere near the 0.7 the strong pull needs. In the model's terms it is k_p ≈ 0.025-0.06, round 2's range. The persistent part does not close, as the hypothesis assumes.
- highD and I-395 tracks are too short to give a past (11 and 36 s median).

## Step 3: the twin with each driver's past (F817-F819)

Pattern list, fixed before any score: F800 with step 1's P8 and with P12 at 100 km/h reported only. Personal factor in P1 and P2: f_past, window (B), the whole track before release. Launch followers have no steady past, so f = 1. Random mode uses f = exp(0.27 z), as a city run draws it, with the past-fitted numbers frozen. The platoon scenes draw f as in round 3 in both modes. The round 2 reference for the P1 and P2 ratios is the round 2 law with the same f. Each law was fitted on P1 + P2 + P6 as in round 3.

Scores with f_past. Bold is a miss.

| Pattern | round 2 | (e) | (f) | (e) k_p 0.084 | (e) k_p 0.139 | (f) k_p 0.084 | (f) k_p 0.139 | (h) metre pull | (i) opening pull |
|---|---|---|---|---|---|---|---|---|---|
| P1 CRPS highD | 0.140 | 0.142 | 0.147 | 0.143 | 0.148 | 0.146 | 0.151 | 0.144 | 0.147 |
| P1 CRPS DLR HT | 0.181 | 0.181 | 0.185 | 0.182 | 0.185 | 0.185 | 0.188 | 0.182 | 0.186 |
| P1 CRPS I-90/94 st. | 0.183 | 0.191 | 0.180 | 0.190 | 0.192 | 0.180 | 0.184 | 0.187 | 0.182 |
| P1 CRPS I-294 L1 | 0.190 | 0.199 | 0.203 | 0.199 | 0.204 | 0.203 | 0.209 | 0.204 | 0.204 |
| P1 CRPS I-395 (bound 0.175) | 0.159 | **0.176** | **0.178** | **0.176** | **0.182** | **0.178** | **0.185** | **0.177** | **0.179** |
| P2 closed in 30 s, DLR HT (rec. 0.31) | 0.38 | 0.45 | **0.48** | **0.55** | **0.69** | **0.47** | **0.61** | 0.35 | 0.36 |
| P2 I-90/94 st. (0.28) | 0.42 | 0.40 | **0.63** | **0.52** | **0.64** | **0.62** | **0.75** | **0.72** | **0.53** |
| P2 I-294 L1 (0.25) | 0.34 | 0.40 | **0.52** | **0.53** | **0.64** | **0.51** | **0.64** | **0.47** | **0.45** |
| P2 I-395 (0.41) | 0.50 | 0.48 | **0.60** | **0.59** | **0.70** | **0.60** | **0.73** | 0.51 | 0.52 |
| P2, only windows with a past (rec. 0.20 / 0.25 / 0.21 / 0.27; report) | 0.22 / 0.37 / 0.28 / 0.34 | 0.33 / 0.33 / 0.35 / 0.35 | 0.39 / 0.54 / 0.47 / 0.50 | 0.45 / 0.45 / 0.48 / 0.46 | 0.59 / 0.56 / 0.59 / 0.57 | 0.38 / 0.54 / 0.46 / 0.49 | 0.52 / 0.67 / 0.60 / 0.61 | 0.25 / 0.65 / 0.44 / 0.40 | 0.29 / 0.45 / 0.42 / 0.41 |
| P2 30 s RMSE DLR HT / I-90 / I-294 / I-395, m | 20.8 / 5.3 / 17.3 / 9.6 | 19.6 / 4.7 / 14.8 / 9.7 | 20.5 / 4.9 / 14.4 / 9.8 | 20.8 / 4.8 / 14.9 / 9.9 | **23.3** / 5.1 / 15.6 / **10.2** | 20.4 / 4.9 / 14.4 / 9.8 | **22.6** / 5.2 / 15.2 / **10.1** | 19.1 / 5.2 / 14.6 / 9.5 | 19.9 / 4.5 / 14.2 / 9.6 |
| P4 gap at 1 / 2 / 3 / 5 m/s, m | 2.9 / 4.2 / 5.5 / 8.8 | 2.8 / 4.0 / 5.2 / 7.2 | 2.9 / 4.1 / 5.4 / 8.1 | 2.8 / 4.0 / 5.2 / 7.3 | 2.9 / 4.1 / 5.2 / 7.3 | 2.9 / 4.1 / 5.4 / 8.1 | 2.9 / 4.1 / 5.4 / 8.2 | 2.9 / 4.1 / 5.4 / 8.3 | 2.9 / 4.1 / 5.4 / 8.2 |
| P5 standstill gap, m | **2.51** | **2.70** | 1.97 | **2.44** | **2.17** | 1.98 | 1.80 | 1.79 | **2.49** |
| P6 rounD 2 / 4 / 8 s, m | +0.48 / **+1.50 / +1.72** | −0.45 / +0.37 / +0.83 | +0.28 / **+1.03 / +1.17** | −0.39 / +0.44 / +0.91 | −0.38 / +0.47 / +0.99 | +0.28 / **+1.03 / +1.18** | +0.32 / **+0.98** / +0.95 | +0.28 / **+0.82** / +0.65 | +0.23 / **+0.99 / +1.28** |
| P6 inD | **+0.53 / +1.75 / +1.44** | **−0.55** / +0.30 / +0.32 | +0.35 / **+0.95** / +0.71 | −0.41 / +0.40 / +0.39 | −0.39 / +0.47 / +0.42 | +0.34 / **+0.97** / +0.70 | +0.30 / **+0.80** / +0.69 | +0.14 / **+0.51** / +0.28 | +0.23 / **+0.81** / +0.81 |
| P6 SinD Changchun | +0.25 / **+1.60 / +2.77** | **−0.54 / −0.76** / 0.00 | +0.04 / +0.42 / +0.95 | −0.46 / **−0.59** / +0.12 | −0.44 / **−0.53** / +0.15 | +0.04 / +0.44 / +0.97 | −0.06 / +0.24 / +0.77 | −0.22 / −0.10 / +0.56 | −0.13 / +0.05 / +0.74 |
| P6 Lankershim (report) | −0.04 / +1.36 / +6.61 | −0.70 / −0.33 / +1.84 | +0.03 / +1.26 / +4.79 | −0.59 / −0.08 / +2.23 | −0.57 / −0.02 / +2.29 | +0.03 / +1.26 / +4.78 | +0.10 / +1.53 / +5.60 | −0.02 / +1.39 / +5.52 | −0.03 / +1.17 / +5.20 |
| P7 start delay, positions 2-6, s | 1.13-1.27 | **0.91**-1.32 | 1.16-1.26 | **0.91**-1.34 | **0.91**-1.34 | 1.16-1.26 | 1.19-1.26 | 1.18-1.27 | 1.14-1.26 |
| P8 stop line, positions 2 / 3 / 6 (2.55 / 2.25 / 1.90), s | 2.72 / 2.57 / **2.42** | **2.15** / 2.58 / 1.99 | 2.72 / 2.36 / 2.14 | **2.16 / 2.63** / 2.02 | **2.17 / 2.64** / 2.02 | 2.71 / 2.36 / 2.14 | 2.80 / 2.39 / 2.16 | 2.76 / 2.39 / **2.25** | 2.71 / 2.40 / 2.22 |
| P9 start wave, km/h | 19.2 | 19.3 | 19.2 | 19.3 | 19.3 | 19.2 | 19.2 | 19.2 | 19.2 |
| P12 L1 50 km/h, veh/h | **1,201** | 1,657 | 1,777 | 1,759 | 1,847 | 1,774 | 1,822 | **1,596** | 1,720 |
| P12 L1 100 km/h (report) | 1,084 | 1,497 | 1,680 | 1,642 | 1,810 | 1,671 | 1,794 | 1,437 | 1,604 |
| P12 S1 headway, s | **2.56** | 2.07 | 2.06 | 2.05 | 2.01 | 2.06 | 2.05 | 2.16 | 2.12 |
| **Misses, f_past** | **11** | **7** | **8** | **10** | **12** | **8** | **9** | **7** | **7** |
| **Misses, random f** | 13 | 10 | 8 | 11 | 15 | 8 | 9 | 7 | 7 |

Fitted numbers, all with f_past:

| Law | Numbers |
|---|---|
| (e) two regimes | K 4.68, c_a 0.42, k_g 0.71, k_p 0.055, K_1 8.20 |
| (f) K/(g + g_1) | K 7.05, g_1 4.04 m, c_a 0.33, k_g 0.34, k_p 0.086 |
| (e), k_p held at 0.084 / 0.139 | K 4.79 / 5.34, c_a 0.42 / 0.37, k_g 0.66 / 0.67, K_1 7.92 / 7.86 |
| (f), k_p held at 0.084 / 0.139 | K 7.00 / 7.58, g_1 3.97 / 5.35, c_a 0.33 / 0.30, k_g 0.35 / 0.35 |
| (h) = (f) + k_m max(g − g\*, 0) max(0, 1 − v/5) | K 6.47, g_1 4.91, c_a 0.35, k_g 0.35, k_p 0.045, k_m 0.176 /s² |
| (i) = (f), k_p from k_p0 to k_p1 as Δv goes 0 → 0.5 m/s | K 5.48, g_1 2.50, c_a 0.33, k_g 0.37, k_p1 0.162, k_p0 0.025 |

- **A strong pull towards the driver's own gap closes open gaps too fast, even where that gap is known.** On windows with a past, the recordings close 0.20-0.27 in 30 s. (f) at k_p 0.139 closes 0.52-0.67, and (e) at 0.139 closes 0.56-0.59. The free fits pick k_p 0.055 and 0.086, not the 0.084-0.139 that came from the future.
- **The split is round 3's.** (e) holds open gaps and German launches, but stops 2.7 m behind a stopped car, starts the second car in 0.91 s and runs ahead on SinD. (f) holds standstill (1.97 m), the stop-line headways and capacity (1,777 veh/h), but closes open gaps twice as fast as recorded, and German launches trail by 0.8-1.0 m at 4 s whatever the pull.
- **The cost of random personal draws** (F819), across the nine laws: P1 CRPS +0.1 to +1.3% on highD and DLR HT and +0.5 to +4.0% on the TGSIM tables; P2's closed share +0.00 to +0.11 (I-294 L1 the most); P2 RMSE 0 to +7.5%; launches under 0.21 m. It changes verdicts only for (e), whose P2 fails on three tables with random f. Past-initialised f helps replay a little but is no fix, and a city run, which must draw f at random, loses even that.

## Step 4: the two other ideas (F820, F821)

- **(h) a pull in metres below 5 m/s** brings standstill to 1.79 m with k_p back at 0.045, and passes P2 on DLR HT and I-395. But it also closes I-90/94 st.'s slow open gaps (0.72 against 0.28), since most of those windows sit under 5 m/s. German launches still trail by 0.82 / 0.51 m at 4 s, and L1 at 50 km/h falls to 1,596. 7 misses.
- **(i) a strong pull only while the gap opens** (k_p1 0.16 against k_p0 0.025) passes P2 on DLR HT and I-395 and SinD launches. It misses standstill (2.49 m: a stopping follower's gap is closing, so the weak pull acts), German launches (+0.99 / +0.81 m at 4 s) and P2 on I-90/94 st. and I-294 L1. 7 misses.

Rule 9: this is the fourth round on the same conflict, and step 4 brought no gain. Stopped here.

## Which patterns conflict

Over all nine laws of this round:

1. **P2 on I-90/94 st. and I-294 L1 against P5 and L1 capacity.** Only round 2 and (e), with k_p ≤ 0.055 and no extra pull at low speed, hold open gaps on these two tables. Only laws with k_p ≥ 0.084, or a metre pull, stop at 1.6-2.0 m. Personal preference does not resolve this: it is under a quarter of an open gap.
2. **German launches (rounD, inD at 4 s) against SinD Changchun and the second car (P7, P8 position 2).** Only the two-regime law, with K_1 ≈ 8, keeps up with German launches. That same gain runs 0.5-0.8 m ahead on SinD and starts the second car 0.2 s early. No pull strength fixes German launches in (f), (h) or (i): the miss is not the pull.
3. **I-395's P1 against every refit.** Every law fitted on the joint set is 10-16% worse than round 2 on I-395 alone, and I-395's closing gain is flat in gap.

## What measurement would settle it

1. **Desired speed behind open gaps (for conflict 1).** The twin gives every table follower a desired speed at the table's 99th percentile, so any pull closes an open gap. A driver cruising at its own desired speed behind a leader of the same speed does not close, however strong its pull. On DLR HT the free speed has a CV of 0.12-0.2 and persists for kilometres (r 0.75 at 0.5-1 km). Measure each follower's desired speed from its past free driving, and the 30 s closing of open gaps against v_des,past − v_leader. If gaps with v_des ≈ v_l stay open and the others close with a time constant of 10-20 s, P2 is a free-speed pattern and the pull can be strong. This does not cover I-90/94 st., whose open gaps sit at 2-14 m/s in stop-and-go: split those by the leader's acceleration over the window.
2. **Launches on more sites (for conflict 2).** German and Chinese launches differ at the same gap. Measure follower launches on DLR UT (German, controller states) and SinD Tianjin and Chongqing with the same rollout. Then either treat the sites as two populations, or find the variable the law lacks. Candidates are the share of the leader's acceleration (−0.09 to 0.21 on launches against 0.1-0.8 in following) and the follower's own start delay.
3. **I-395's leaders (for conflict 3).** Check whether the table's leader is the car directly ahead in the follower's lane, using lateral positions (which report 05 found poor), and refit the next second on pairs whose leader is certain. If the flat gain disappears, I-395's P1 pattern measured mispaired leaders.

## What was not done

- No kernel change, no GPU run, no held-out read. `--tune measured=1` and `measured=0` are unchanged. HOLDOUT.md is unchanged.
- No interval was relaxed after scoring. P8 and P12 at 100 km/h changed in step 1, before any step 3 score, by rules written in F810, F811 and F814. I-395 stayed a filter by F812's rule, even though step 1 found reason to doubt its leaders.
- Nothing was tuned to capacity. P12 entered no fit.

Reproduce (each a few minutes):
`python3 -I scripts/measure/patterns.py p8 | p12 | p12w | i395 | p5p2 | fitcheck`;
`python3 -I scripts/measure/personal.py decompose | sets | twin e f | strong e f | ideas h i` (run from `scripts/measure`, since personal.py imports structure.py).
