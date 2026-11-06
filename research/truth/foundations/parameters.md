# Driver parameters of the one driver: value, source, and the recording that could measure it

Physical motion (Krauss with the physics certificate, `mu > 0`) with decisions on top. Scenes in `scenes-log.md` verify that the code does what its equations say. They do not show the driver is human; the replay tier does. So every value here has a measured source, or is marked **provisional** with the reason. No value was moved to make a scene pass; where a scene was the only reason, it says so.

| Parameter | Value | Source | Status | Recording that measures it directly |
|---|---|---|---|---|
| `tau`, Newell T of the median driver | 1.4 s | B §1: real medians of report 19's congested pairs, gap minus 2.5 m / v, fit one T of 1.4 s at every speed | Measured | Following pairs in congestion: report 05's cached I-90, I-395, A39 pairs; highD, I-80 NGSIM. T = (spacing − s) / v per pair |
| `gap_spread`, lognormal sd of T between drivers | 0.3 | Report 19: real time gaps reach 0.4-0.9 s at p5 with a median near 1.6 s | Measured, loosely: fitted by eye to a p5, not to a distribution | Same pairs, per-driver median T over a stable following episode |
| s, jam spacing front to front | 7.5 m (length 5, minGap 2.5) | Report 19: Braunschweig 7.0 (6.2-8.1), Lankershim 6.8-7.4, I-90 8.1 | Measured, upper half of the range | DLR UT standing queues at the line (report 05 §4.4) |
| `start_react`, standing car after its leader moves | 1.0 s | Report 05 §4.3: DLR UT position 2 moves 1.0 s after its predecessor (IQR 0.6-1.6, n 1,140); Lankershim 1.0-1.2, Peachtree 0.9-1.7, Foggy Bottom 1.1-1.6 | Measured, German urban site | DLR UT queues with controller states: time from leader's start to follower's start |
| `first_react`, first car at a green | 1.62 s | Report 05 §4.3: DLR UT first car moves 1.62 s after green (p10-p90 0.82-2.83, n 3,884), after about 1 s of red-yellow | Measured | DLR UT, controller green onset to the first car's start |
| Launch acceleration a0 − a1 v, floor | 2.02 − 0.125 v, 0.7 m/s² | Physics table, Long 2000; report 19 first car peak 1.92 against real 1.80 | Measured source, adapted | DLR UT first-car launches (n 3,050) |
| `sigma`, dawdle | 0.2 | Set to bring 50 km/h saturation into report 04's band (world.rs comment) | **Provisional**: chosen by a capacity result, not measured. Now that T comes from a measurement, it is a noise term with no source | Speed noise of free and following drivers in any trajectory set: report 05's noise fit |
| `Link::tc`, critical gap by movement | right from minor 5.9 s, left from major 5.5, through 6.7, left from minor 6.5; +0.7 at a stop sign; +0.9 s towards a 70 km/h major | HBS 2015 S5, urban (KNOBEL form, foundations/B §3); stop and speed terms TRVMB Kapacitet table 3 | Measured norm values (German, from field gaps). Replaces TRVMB × 0.7 − 1.2 s, which had no source and existed to cancel a long follow-up | Gaps offered and taken at give-way approaches: Swiss roundabouts (report 05, 2.95 s at roundabouts), TGSIM Foggy Bottom turns, any drone set with a priority junction (inD, Aachen) |
| Give-way: first-car reaction | none at a give-way line; 1.62 s only at a light | HBS's critical gap is measured on drivers who watch the gap come, so their reaction is inside it | Consequence of the source above, not a fitted number | inD / Aachen priority junctions: time from the last major car passing to the minor car moving |
| Give-way: waiting head counts the gap from now | rule | HBS takes the gap from the waiting driver's departure | Definition, not a number | Same |
| Courtesy, share of followers who let a merger in | 0.4, with report 14's let-in logit | Report 14 / HUMAN.md: Aimsun's "cooperation creating a gap", value from the I-80 sweep against 59% let in per chance | **Provisional**: swept on I-80 for the human driver; on this driver's following it is untested | I-80 and US-101 merges (report 14, 18): share of followers that open a gap per chance |
| Merge start law (report 18 B1, B2): intercept 0.4, time-to-end −1.544 per 10 s, lag 0.133, lead 0.164, from 43 s, driver term 0.5 | as listed | Report 18 fits on I-80 and US-101; intercept 0.4 tuned in closed loop there; driver term invented (HUMAN.md) | Measured coefficients; intercept and driver term **provisional** | I-80, US-101 merges: start of the sideways motion against time to the lane end and gaps |
| Gate floor, certificate × 0.35 during a change | 0.35 | Report 18 / HUMAN.md: real p25 lags 1.6 m (I-80), 3 m (US-101); Vissim uses 0.6 | Fitted to measured lags | I-80, US-101: lag at the start of a merge |

### Notes from the orchestrator, 6 November

- **Report 05's response lag of 1.0 s is provisional.** Its free fit gave 0.66 s; 1.0 was chosen because it made realistic waves. It belongs to the human driver's car following (`tau_a`), which this driver does not use. `start_react` is a different number: the measured lag from a leader's start to its follower's start, not a fitted response.
- **DLR UT discharge is a calibration target, not a source.** Report 05 raised its gain k2 to hit DLR UT's 2.05 s headway. No parameter here takes its value from DLR UT's discharge headway. S1's forecast (T + s/v) and S3's 2.74 s lost time stay tests of this driver, which wasn't fitted to them; Lankershim's 1.9 s median (report 05 §4.3, unused there) is the independent check of discharge.
- `start_react` and `first_react` come from DLR UT's start lags, which are timings, not the fitted discharge. Lankershim 1.0-1.2 s and Peachtree 0.9-1.7 s agree with the 1.0 s.

### Rules dropped from the human driver, and why

| Rule | Why dropped | Scene that would have to show a gap |
|---|---|---|
| Human car following (k1 k2 feedback, noise, T × 0.7, Gipps limits, launch rule) | Fails L1 (flat capacity 1,741-1,759), L3 (jam spacing 5.79 m) and L6 (280 veh/h at 1.63 m/s); the physical Krauss with a measured T and start reaction passes them | L1, L2, L3 |
| Response lag 1.0 s (report 05) | Provisional there: free fit 0.66 s, chosen for waves. Part of the dropped car following | W1 |
| Follower response B7, speed match B5, steering B6, edging B3 | Ride on the human car following (`hu_target`); not ported. LC3's merge share is the scene that would show whether one is needed | LC3 F024, C-S6 |
| Missed turns `hu_reroute` (mean 120 s) | Main's `ph_reroute` (60 s) passes C-S3 and C-S4, also 43-60 m back | C-S3, C-S4 |
| Offset stop points (Trafikverket) | C-S5 passes without them (worst swap 13 s) | C-S5 |
| Yellow decision `hu_can_stop` | Physical's `ph_yellow_go` uses the same report 05 logistic | none |
| Corner speed `hu_corner` | Physical's curve limit gives 2.9 m/s at the 5.6 m corner of G1, report 19 measures 2.8 at 5-8 m | G1 F234 |
| Swedish free speed table | Region only | none |

### Provisional values and the levelX / SinD measurement that would replace each

| Parameter | Provisional because | Replaced by |
|---|---|---|
| `sigma` 0.2 (dawdle) | set for a capacity band, no source | highD: speed noise of free drivers and of steady followers (residual about a smooth speed profile); exiD the same at lower speeds |
| `gap_spread` 0.3 | fitted by eye to a p5 of report 19 | highD: per-driver median time gap over stable following episodes, its spread across drivers (and with it a second check of `tau` 1.4 against the 2.3 s median F109 measured on I-90/94) |
| `start_react` 1.0 s, `first_react` 1.62 s | measured at one German site on a Sunday (DLR UT) | SinD: four signalised intersections with signal logs, leader-start to follower-start and green to first start; inD for give-way starts (no signals) |
| HBS critical gaps 5.9 / 5.5 / 6.7 / 6.5 s | norm values, not measured on our data | inD (Aachen priority junctions): gaps offered and taken per movement, maximum likelihood (the estimator G4 uses); rounD for roundabout entry (report 05's 2.95 s from Swiss sites to be checked) |
| Give-way follow-up (now 3.8 s from following at a 4 m corner) | follows from T and corner speed; HBS 3.0 is a norm | inD: headway between successive minor cars entering in one major gap, and their speed in the corner |
| Courtesy share 0.4, report 14 let-in model | swept on I-80 for the human driver | exiD and highD on-ramps: share of target-lane followers that open a gap per merge chance, braking they apply |
| Merge start law intercept 0.4, driver term 0.5 | intercept tuned in closed loop on I-80/US-101, driver term invented | exiD entries and lane drops: start of sideways motion against time to the lane end and gaps, refit on held-out sites |
| Gate floor, certificate x 0.35 | fitted to I-80 / US-101 p25 lags | exiD and highD: lag and lead at the start of a mandatory change |
| Launch a0 2.02 - 0.125 v | Long 2000, adapted; replay found main launching at 2.6 against DLR UT's 1.8 | SinD: first-car peak acceleration and time to 5 and 10 m/s after green |
| Corner speed: physical curve limit with lateral median 2.2 m/s2 | report 19's turning set | inD and rounD: speed against radius through the junction |

## Final table, with the measured driver (main aadf8f7, `measure/DRIVER.md`)

This driver was not moved towards DRIVER.md in this job (orchestrator). The last column is what the next job sets it from.

| Parameter | Value in this driver | Source | Status | Recording that measures it | DRIVER.md value |
|---|---|---|---|---|---|
| `tau`, time gap T of the median driver | 1.4 s, all speeds | B §1, report 19 pairs | Measured, but one T for all speeds | highD, DLR HT, TGSIM | 1.6 s at 3-10 m/s, 1.4 at 10-15, 1.2 at 15-20, 1.1 at 20-25, 0.95 at 25-35, 0.8 above 35 m/s; motorway median 0.98 s |
| `gap_spread`, log-SD of T between drivers | 0.3 | report 19 p5, by eye | Provisional | highD, DLR HT | persistent log-SD 0.27; correlated with free speed r −0.41; a further part tied to the leader pair (e-folding 1.2 km) |
| Standstill gap (minGap) | 2.5 m (jam spacing 7.5 m with a 5 m car) | report 19 | Measured on assumed 5 m lengths | rounD, inD queues | 1.7 m bumper gap (p10 1.0, p90 2.6) |
| Response to gap and closing speed | Krauss safe speed towards its T (steers to the gap) | SUMO / Gipps | No measured source; F113 shows the bias | highD, DLR HT, TGSIM | closing speed linear, 0.11-0.2 m/s² per m/s (motorway); leader acceleration 0.25-0.65 passed on; gap error one-sided band, none from 0.5 s too close to 1.75 s too far |
| Response lag | none beyond the step (Krauss) | – | Missing | highD, DLR HT, TGSIM | first-order time constant 0.48-0.56 s, dead time under 0.3 s |
| `sigma`, dawdle | 0.2 | capacity band | Provisional, no source | highD free drivers | no perception threshold; noise not given as a sigma |
| `start_react` | 1.0 s | report 05 DLR UT, leader start to follower start | Measured, one Sunday site | SinD | not given; first-car start 2.0 s (1.7-2.2) without red-yellow |
| `first_react` | 1.62 s | report 05 DLR UT, with about 1 s of red-yellow | Measured | SinD | 2.0 s (1.7-2.2) to 1.5 m/s, no red-yellow |
| Launch a0 − a1 v | 2.02 − 0.125 v m/s² | Long 2000 | Adapted | SinD | peak 1.77 m/s² (1.66-1.88), p5-p95 0.54-3.01 |
| Free speed spread | speedDev 0.1 (scenes use 0) | SUMO default | No source | highD, exiD, DLR HT | CV 0.12-0.20 per driver, persistent over km (e-folding 4.9 km) |
| `Link::tc` critical gap | HBS: right 5.9, left from major 5.5, through 6.7, left from minor 6.5 s | HBS 2015 S5 | Norm values | inD, rounD | minor left 6.9 s (6.4-7.5), minor straight 6.6, left off the priority road 3.9, right-before-left 3.9, roundabout entry 3.0 s |
| Give-way follow-up | 3.8 s, from E[T] + s/v at the scene's 4 m corner | follows from T and corner speed | Consequence, not set | inD, rounD | straight 2.7, right 3.2, left 4.9 s; roundabout 2.76 s |
| Impatience at give-way | none in this driver (SUMO's impatience term off in physical mode) | – | – | inD, rounD | none: no waiting effect |
| Courtesy share | 0.4 with report 14's model | I-80 sweep | Provisional | exiD | 4 points over baseline (10.3% against 6.3%) slow for a merger |
| Merge start law (report 18 B1 B2) | intercept 0.4, time-to-end −1.544, lag .133, lead .164 | report 18, I-80 US-101 | Coefficients measured; intercept and driver term provisional | exiD | merge at a median 49% of the acceleration lane, 4.7% in the last tenth |
| Gate floor during a change | certificate × 0.35 | report 18 lags | Fitted to p25 lags | highD, exiD | accepted lag p5/p50 0.45/1.2-1.7 s, lead 0.30-0.38/1.5-1.7 s; on-ramp lag 0.45/1.81, lead 0.39/1.66 s |
| Lane change duration | from the physics lateral speed 0.6 m/s | physics table | Adapted | exiD, highD | 10-90%: merge 5.4 s, motorway 4.4-5.0 s |
| Free speed, motorway | lane limit × speedFactor | SUMO | – | highD, exiD | no limit 34.5 m/s; 120 km/h 30.7-32.2; 100 km/h 28.3 m/s |

## Lane changes measured (7 November, `measure/LANECHANGE.md`, `--tune lc_measured=1`, off by default)

| Parameter | Old value | Measured rules | Source | Status |
|---|---|---|---|---|
| Merge start law | report 18 B2: intercept 0.4 (closed-loop tuned), driver term 0.5 (invented), tte −1.544, lag 0.133, lead 0.164 | per 0.5 s sigmoid(−0.601 − 1.119 tte/10) × acceptance | I-80 + US-101 must-change cohorts with refusals (959 cars), moved to the start by the measured 2.0 s | Measured; exiD does not identify it (starts come at once) and starts 2.3× as often |
| Gap floor during a change | certificate × 0.35 (fitted) | lognormal critical time gaps: lag median 0.40 s, log-SD 1.68, ln +0.551 per m/s closing; lead 0.14 s, 1.37, +0.453 | same fit | Measured; medians weakly determined |
| Discretionary gaps behind a physical follower | 0.6 × its desired gap; Ahmed's published lead gap | the same acceptance | same fit; transfers to highD left changes (lag p50 1.65 against 1.72 s) | Measured; right changes not reproduced |
| Courtesy share | 0.4 | 0.4 | report 14 I-80 sweep | Provisional. F707 (5.5 points per merge, exiD) is another quantity; 0.055 tripled lane-end waits |
| Sideways speed | 0.6 m/s (adapted) | 0.71 m/s | exiD merges and highD: start to crossing 1.96 s, start to clear 3.2 s | Measured; DLR HT 0.47-0.52 |
| Change over a lane end | must finish first | runs on over links with no junction box | harness: the old rule stopped every exiD merger at the end of its sectioned lane | Fix |
| SUMO follower/leader holds for a changer | on | off for measured drivers | F707: no measurable response before the start | Dropped |
