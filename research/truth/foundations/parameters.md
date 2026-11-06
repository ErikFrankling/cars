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

### Notes from the orchestrator, 6 November

- **Report 05's response lag of 1.0 s is provisional.** Its free fit gave 0.66 s; 1.0 was chosen because it made realistic waves. It belongs to the human driver's car following (`tau_a`), which this driver does not use. `start_react` is a different number: the measured lag from a leader's start to its follower's start, not a fitted response.
- **DLR UT discharge is a calibration target, not a source.** Report 05 raised its gain k2 to hit DLR UT's 2.05 s headway. No parameter here takes its value from DLR UT's discharge headway. S1's forecast (T + s/v) and S3's 2.74 s lost time stay tests of this driver, which wasn't fitted to them; Lankershim's 1.9 s median (report 05 §4.3, unused there) is the independent check of discharge.
- `start_react` and `first_react` come from DLR UT's start lags, which are timings, not the fitted discharge. Lankershim 1.0-1.2 s and Peachtree 0.9-1.7 s agree with the 1.0 s.
