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
| Corner speed `hu_corner` | Physical's curve limit gives 2.9 m/s at the 5.6 m corner of G1, report 19 measures 2.8 at 5-8 m | G1 F134 |
| Swedish free speed table | Region only | none |
