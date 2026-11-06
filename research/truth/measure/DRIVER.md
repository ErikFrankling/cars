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

## What changes for the driver

1. **Time gap depends on speed.** It is 1.6 s in slow traffic and 1.0 s at 30 m/s, with a 1.7 m standstill gap. Each driver keeps a personal factor (log-SD about 0.27) for the whole trip, correlated with their desired speed (r −0.41). On top of that comes a slower part tied to the car ahead.
2. **The gap response has a one-sided indifference band.** No response from 0.5 s too close to 1.75 s too far; braking only when well too close. Closing speed is answered linearly, with no dead zone. The leader's acceleration is followed directly.
3. **The response lag is a filter of about 0.5-0.7 s, not 1 s.**
4. **Desired speed spread is a CV of about 0.15-0.2,** drawn per driver and persistent over kilometres.
5. **At give-way, the follow-up times are 2.7-3.2 s** (left turns 4.9 s), not 4.4 s. Drivers do not grow impatient.
6. **Merges happen at mid-lane, into lags as short as 0.45 s.** The car behind barely brakes.
