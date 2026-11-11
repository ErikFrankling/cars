# The driver, measured

7 November 2026. Every number below was measured on recordings of that behaviour alone, with no simulator and no fitting to waves or capacity. Forecasts F130-F147 were written first. Details, methods and misses are in [RESULTS.md](RESULTS.md); held-out recordings are in [HOLDOUT.md](HOLDOUT.md) and were never read.

Confidence:

- **High**: thousands of events, sites agree.
- **Medium**: hundreds of events, or sites disagree a little.
- **Low**: few events, or the estimate moves with the method.

Intervals are 95% over vehicles or events. "Report 05" means [05-real-human-driving.md](../05-real-human-driving.md), section 8.

| Behaviour parameter | Value or distribution | Source recordings | n | Held out for the replay test | Confidence | Report 05's number |
|---|---|---|---:|---|---|---|
| Tracker jitter | Under 1 cm of position, under 0.07 m/s of speed. It limits nothing here. Slow bias is unmeasured | highD, inD, rounD, exiD, DLR HT, TGSIM | 17,000 tracks | none | High | No number before |
| Time gap, steady following, motorway speed | Median 0.98 s (0.97-0.99) at 25-35 m/s; p5 0.47, p95 2.22 s | highD, 57 recordings, 5 sites, 4 weekdays | 12,245 | highD location 6 | High | **Does not stand.** 1.30 s was fitted, and 1.6-1.8 s came from a broad definition |
| Time gap against speed | 1.6 s at 3-10 m/s, 1.4 at 10-15, 1.2 at 15-20, 1.1 at 20-25, 0.95 at 25-35, 0.8 above 35 m/s. A constant time gap does not fit | highD, DLR HT, TGSIM (3 sites) | 35,700 windows | as above, plus DLR HT 14-16 UTC, TGSIM I-90/94 moving | High | New. Report 05 used one T for all speeds |
| Time gap between drivers (persistent part) | Log-SD about 0.27: a third of the 0.47 window-to-window spread. It holds over at least 5 km | DLR HT 06-10 UTC, pairs with different leaders | 939 pairs, 7,070 tracks | DLR HT 14-16 UTC | Medium | **Stands**: log-SD 0.25 |
| Time gap that belongs to the leader pair | Correlation 0.72 at 0.5-1 km, decaying with an e-folding length of 1.2 km | DLR HT; HIGH-SIM agrees (0.82, 0.67, 0.38 over 0-1 km) | 5,495 windows | DLR HT 14-16 UTC | Medium | New |
| Standstill bumper gap | Median 1.7 m (rounD 1.73, 1.63-1.85; inD 1.52); p10 1.0, p90 2.6 m | rounD, inD queues, real box lengths | 295 cars | rounD location 0 Wednesday, inD location 3 | Medium | **Does not stand.** 2.8 m came from 5 m assumed lengths |
| Response to closing speed, next second | Linear through zero with **no dead zone**. 0.11-0.2 m/s² per m/s on motorways, 0.3-0.4 in US congestion; it flattens above +1.5 m/s | highD, DLR HT, TGSIM ×3 | 3.2 M samples, 39,000 followers | as for time gap | High | k2 is not directly comparable (a different model). The finding that drivers follow speed holds |
| Response to the leader's acceleration | 0.25-0.65 of it appears in the follower's next second | same | same | same | High | New |
| Response to gap error | **One-sided band**: under 0.05 m/s² from 0.5 s too close to 1.75 s too far; braking at 0.2-0.5 m/s² per s once 0.75 s or more too close | same | same | same | High | k1 0.011 /s² ("tiny") **stands inside the band**. A symmetric linear gap term does not |
| Perception threshold (Wiedemann action points) | None visible: closing speed at action points equals closing speed at random moments | same | 245,000 action points | same | High | New |
| Response lag | First-order time constant 0.48-0.56 s plus a dead time under 0.3 s. A pure delay is not identifiable from smoothed tracks | highD, DLR HT, TGSIM I-90/94, I-294 | 3.2 M samples | as above | Medium | **0.66 s free fit stands; 1.0 s does not** (no free fit supports it) |
| Free (desired) speed, motorway | No limit 34.5 m/s (124 km/h); 130 km/h limit 34.5; 120 km/h 32.2 (highD) and 30.7 (exiD); 100 km/h 28.3 m/s | highD, exiD, DLR HT | 80,000 cars | highD location 6, exiD location 5 | High | Report 05's A39 33-36 m/s stands |
| Free speed spread between drivers | CV 0.12-0.20 (SD 3.5-6.3 m/s) | same | same | same | High | **SUMO speedDev 0.1 is too narrow** |
| Free speed persistence | Correlation 0.75 at 0.5-1 km, 0.5 at 3 km, 0.26 at 5-6.5 km; e-folding length 4.9 km | DLR HT 06-10 UTC | 12,643 windows | DLR HT 14-16 UTC | Medium | New |
| Fast drivers follow closer | r = −0.41 between a track's free speed and its log time gap | DLR HT | 770 tracks | DLR HT 14-16 UTC | Medium | New |
| Free speed, urban | **Not measured**: inD sees only junctions (4.1 m/s at a right-before-left junction) | inD | 178 | inD location 3 | none | No number before |
| Critical gap, minor road left turn | 6.9 s (6.4-7.5), log-SD 0.2 | inD Bendplatz | 279 (73 with a refusal) | inD location 3 | Medium | New |
| Critical gap, minor road straight | 6.6 s (4.9-7.9) | inD Bendplatz | 58 (11) | inD location 3 | Low | New |
| Critical gap, left off the priority road | 3.9 s (3.3-4.6) | inD Bendplatz | 137 (38) | inD location 3 | Medium | New |
| Critical gap, right-before-left | 3.9 s (3.1-4.9) | inD Frankenburg | 345 (15) | none at this site | Low | New |
| Critical gap, roundabout entry | 3.0 s (2.7-3.4) where the arrival is seen; 2.1-5.0 s by subset, 1.5-3.4 s by day | rounD | 1,144 (96) | rounD location 0 Wednesday | Low | Swiss 2.95 s **agrees, weakly** |
| Follow-up time, give-way | Straight 2.7 s, right 3.2 s, left 4.9 s; all minor 2.88 s (2.78-3.00) | inD | 508 | inD location 3 | High (straight), Medium | **2.3-3.1 s stands** for straight and right. Our physical driver's 4.41 s is too long |
| Follow-up time, roundabout | 2.76 s (2.68-2.84) | rounD | 1,172 | rounD location 0 Wednesday | High | **Stands** (Swiss 3.04 s) |
| Impatience at give-way | None: 2-4% of drivers take a gap shorter than one they refused; no waiting effect within a movement | inD, rounD | 351 drivers with a refusal | as above | Medium | New. Report 14 found the same at lane ends |
| Lane change accepted gaps, motorway | Lag p5/p50 0.45/1.2-1.7 s; lead 0.30-0.38/1.5-1.7 s | highD, exiD | 24,900 | highD location 6, exiD location 5 | High | DLR HT's 0.70/0.61 s p5 **does not stand** for busier German traffic; TGSIM 0.56/0.33 s is close |
| Merge accepted gaps (on-ramp) | Lag p5/p50 0.45/1.81 s; lead 0.39/1.66 s | exiD, 5 sites | 4,088 | exiD location 5 | High | New |
| Lane change duration, 10-90% | Merge 5.4 s; motorway 5.0 s (exiD) and 4.4 s (highD). These are lower bounds (5 s windows) | exiD, highD | 8,500 | as above | High | **5.1-5.6 s stands** |
| Where on-ramp drivers merge | Median 49% along the acceleration lane, 109 m before its end; 4.7% in the last tenth | exiD | 4,088 | exiD location 5 | High | Report 18's "merge early, not at the end" stands |
| Car behind a merger yields | 10.3% slow 0.3 m/s² or more beyond matched followers, against a 6.3% baseline: 4 points more | exiD | 2,139 | exiD location 5 | Medium | Report 18's "about 1 in 7" is close; most courtesy is not braking (report 14) |
| First car's start after green | 2.0 s (1.7-2.2) to 1.5 m/s, with no red-yellow | SinD Tianjin, Chongqing (weekdays) | 57 | SinD Xi'an | Medium | DLR UT 1.62 s with red-yellow; t_start 0.6 s **not contradicted** |
| Launch peak acceleration | 1.77 m/s² (1.66-1.88), p5-p95 0.54-3.01 | SinD, 3 cities | 154 | SinD Xi'an | High | **amax 1.80 stands**, now on weekdays |
| Saturation headway | 2.6 s (2.45-3.2) in Chinese mixed traffic | SinD Changchun | 30 | SinD Xi'an | Low | 2.0 s stays **Sunday-only**: no weekday German site with signal states |
| **Round 2, 7 November** ([ROUND2.md](ROUND2.md), F600-F633) | | | | | | |
| Closing an open gap over 10-30 s | Slow: followers 1 s or more above T(v) keep 60-72% of the excess after 30 s (median excess 1.44-1.65 s falls to 0.93-1.23 s); none halves within 30 s. Pull k_p 0.035 (0.028-0.042) on 10 s rollouts and 0.044 (0.039-0.049) on 30 s, with each driver's own gap taken from other leaders and shrunk by its reliability; 0.025 (0.023-0.029) on one second. 0.08-0.14 only when the driver's target is read from its own future track | DLR HT 06-14, TGSIM I-90/94 st., I-294 L1, I-395; highD for 10 s | 2,000 windows per table and horizon; 17,083 open-gap windows | as time gap | Medium | Report 05 §4.9's "10-25 s" was the upper bound it said it was; the recordings close open gaps no faster than the round 1 law |
| Steady windows select tight followers | All following at the same speed sits 0.24-0.50 s above the steady-window median (highD 1.23 against 0.96, DLR HT 1.60 against 1.10 s at 25-35 m/s). On highD the time gap with zero mean drift over 10 s is 1.09-1.15 s. On DLR HT pairs that stay together 10 s drift apart at every gap (faster followers overtake), so no attractor can be read there | highD, DLR HT, TGSIM ×3 | 9,035 / 7,098 steady windows; 43,743 / 19,284 segments | as time gap | Medium | The time gap table above is the coupled followers' |
| Standstill bumper gap, more sites | rounD 1.83 m (1.74-1.89); inD queue positions 2-4 1.83-1.96; Lankershim 2.72 (2.58-2.85); SinD Changchun 2.32 (2.22-2.45). Flat with queue position | rounD, inD, Lankershim, SinD | 596, 1,018, 426 stops | rounD loc. 0 Wed, inD loc. 3, SinD Xi'an | High (German), Medium | 1.7 m stands for German queues; US and Chinese queues stand 0.6-1 m further apart |
| Creep while the leader stands | 16-23% of stopped cars move 0.5 m or more before their leader moves, by about 1 m; the share rises with the gap (Lankershim 11% under 1 m, 42% at 6-7 m). Queues compact when cars stop, not after | rounD, Lankershim, SinD Changchun, TGSIM I-90/94 st. | 818 stops | as above | Medium | New |
| Spacing at low speed | Bumper gap s0 + 1.0-1.3 s × v from standstill: 2.7-3.9 m at 1 m/s, 4.0-4.8 at 2, 5.1-5.9 at 3, 6.1-8.6 at 5 m/s. Not max(s0, T v) | rounD, inD, SinD Changchun, Lankershim, TGSIM I-90/94 st. | 9,000 samples | as above | High | New |
| Start delay down a queue | Car ahead passes 1 m/s, this car passes 1 m/s: rounD 1.20 s (1.14-1.25), inD 1.37, Lankershim 1.08 (1.03-1.15), flat over positions 1-6; SinD Changchun 1.62 and TGSIM jams 1.60 | same | 2,520 starts | as above | Medium | DLR UT 1.0 s stands for German and US urban queues |
| Launch of followers | Peak 1.76-2.10 m/s² within 10 s (rounD, inD, SinD); bumper gap when it passes 5 m/s 6.5-12 m, 8 m/s 13-17 m | same | 1,100 starts | as above | Medium | New: followers fall back while they accelerate |
| Headway at the line by queue position | Lankershim 3.0, 2.3 s at positions 2, 3 and 2.0 s at position 6; SinD Changchun 4.1, 3.3, 2.8, 3.3, 2.6, 2.4 s at positions 2-7 (line 1 m past the head's standing front) | Lankershim, SinD | 117 + 272 | SinD Xi'an | Low | Report 05's Lankershim 2.4, 2.1, 2.0, 1.9 by another method |
| Critical gap, roundabout entry, drivers who stopped at the line | 4.97 s (4.40-5.60), log-SD 0.33 | rounD | 398 (73 with a refusal) | rounD loc. 0 Wed | Medium | Used for roundabout entries since round 2: the code's give-way rule counts gaps for a head standing at its line |
| Command noise, driver's part | sigma 0.24-0.41 m/s², correlation time 0.5-2 s on all five tables (median 0.38 m/s², 0.75 s) once the trackers' speed error is split off. TGSIM speeds carry a white error worth 36-52% of the next-second residual variance; highD and DLR HT none | highD, DLR HT, TGSIM ×3 | round 1's residuals | as time gap | Medium | Round 1's 0.97 m/s² white was TGSIM's tracker |

## What changes for the driver

1. **Time gap depends on speed.** It is 1.6 s in slow traffic and 1.0 s at 30 m/s, with a 1.7 m standstill gap. Each driver keeps a personal factor (log-SD about 0.27) for the whole trip, correlated with their desired speed (r −0.41). On top of that comes a slower part tied to the car ahead.
2. **The gap response has a one-sided indifference band.** No response from 0.5 s too close to 1.75 s too far; braking only when well too close. Closing speed is answered linearly, with no dead zone. The leader's acceleration is followed directly.
3. **The response lag is a filter of about 0.5-0.7 s, not 1 s.**
4. **Desired speed spread is a CV of about 0.15-0.2,** drawn per driver and persistent over kilometres.
5. **At give-way, the follow-up times are 2.7-3.2 s** (left turns 4.9 s), not 4.4 s. Drivers do not grow impatient.
6. **Merges happen at mid-lane, into lags as short as 0.45 s.** The car behind barely brakes.
7. **Round 2: an open gap closes over minutes, not seconds.** The pull measured over 1, 10 and 30 s is the same small number (0.025-0.044 m/s² per s). What looked like a stronger pull on 30 s rollouts was each driver's own preferred gap, read from its future.
8. **Round 2: from standstill the spacing grows as s0 + T v**, with T about 1.0-1.3 s; cars stop at their standstill gap and rarely creep after. Followers start about 1.1-1.4 s after the car ahead and fall back while they accelerate.
9. **Round 2: the command noise is about 0.4 m/s² over 0.75 s**; the white part of round 1 was the tracker.
10. **Round 4: an open gap is mostly not preference.** Read from the driver's past, the personal part is 12-24% of an open gap's excess. The rest closes with a time constant of 45-60 s ([PERSONAL.md](PERSONAL.md)). Lankershim's stop-line headways are 2.55 / 2.25 / 1.90 s at positions 2 / 3 / 5+ for queues with a signal head. No non-held-out motorway recording shows a queue discharging; the busiest sustained lane flow is 2,188 veh/h (highD location 1).
11. **Round 5: open gaps stay open because drivers watch further ahead, and on free motorways because they are at their own speed** ([OPENGAP.md](OPENGAP.md)). Measured on P2's windows:
    - A parameter-free second-leader constraint explains 0.6-1.0 of the gap between a strong-pull law and the recordings on DLR HT, I-294 L1 and I-395. On I-90/94 st. it overshoots, unexplained.
    - Own desired speed, read from each driver's past free driving, sorts DLR HT's open gaps: if the leader is faster than the follower wants, the gap opens (-0.33 in 30 s); if the follower wants 3 m/s more, it closes 0.72 (τ 24 s).
    - Leaders are paired correctly on every table (median 0.26-0.33 m off the follower's line; I-395 too). I-395's flat closing gain is its own.
    - After a cut-in, real followers apply about all of the shipped law's asked braking (w 0.88-1.17).

