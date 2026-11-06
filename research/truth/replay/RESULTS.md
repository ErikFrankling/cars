# Replay harness: first results, F100-F110

6 November 2026. Design: [README.md](README.md). Forecasts written before each run: `foundations/forecasts.csv` F100-F110. Driver: main as it is, physical mode, `carFollowModel="Krauss"` with SUMO's passenger defaults (tau 1 s, decel 4.5, minGap 2.5, sigma 0.5, speedDev 0.1), dt 0.1 s. Nothing in the driver was changed. Numbers in the JSON files next to this one.

## Verdicts

| | Forecast | Result | Verdict |
|---|---|---|---|
| F100 TGSIM I-90/94 moving, run 1, all 659 tracks replayed | equal within map matching; median under 0.5 m | all 426,829 samples present; lane coordinates within 1.1 mm (max); no lane mismatch; 2D error = the map's lateral error, median 0.27 m, p90 0.95, p99 2.6 m | **pass** |
| F100 DLR UT, signal group 6 lane, 14:00-17:00, all 1,674 pieces replayed | same | 128,822 of 129,047 samples present (the other 225: fronts past the end of the 81 m exit lane, which arrive); lane coordinates p99 2.3 cm, max 3.7 cm; no lane mismatch; 2D error median 0.18 m, p99 1.2 m | **pass** |
| F101 one follower, I-90/94 moving (4,955 windows) | 4.0-5.5 m | **6.30 m** over 5 seeds (6.25-6.35; 95% block interval of seed 0: 5.56-6.87). Speed 0.77 m/s. 5 s 2.15 m, 10 s 3.83 m | **miss**, explained below |
| F105 harness cross-check, `--sumo-compat` Krauss | 6.51 m ± 5% | 6.594 m on the 4,761 windows it completed; report 05's Python on exactly those: 6.594 m (mean spacing difference 2 cm). On all 4,955: Python 6.505 | **pass** |
| F102 real against real, two halves by vehicle | 0.50-0.55 | 0.47-0.51 over five random halvings (mean 0.494) | **pass** |
| F102 floors by pairing | above 0.5 for runs or days | two runs of one day: 0.64 (0.62-0.65); two days (I-90/94 moving against stationary run 6): 0.68 (0.67-0.69), MMD p 0.005 | measured |
| F103 main's driver against real, through the instrument | over 0.75 | **0.89** (0.886-0.895) | **pass**: the test has power, and the driver is told apart beyond the two-days floor |
| F106 same, no instrument | at least F103's | 0.93 (0.925-0.933) | **pass** |
| F108 MMD, paired permutation by vehicle; W1 | p under 0.01; largest W1 on acceleration and jerk | p = 0.005 (smallest possible with 200 permutations; MMD² 0.047 against a null p95 of 0.0006). Largest W1: correlation of acceleration with closing speed 0.62 sd, closing speed spread 0.55, time gap 0.46 | p **pass**; feature forecast **miss** |
| F109 next second, CRPS (10 seeds, 5,000 releases) | above the real floor, below constant speed | driver **0.68** m/s (0.65-0.70); real floor 0.17 (0.17-0.18); constant speed 0.37 (0.35-0.38) | **miss**: worse than the null |
| F110 T1 floor: real follower behind a matched leader | 3.0-5.0 m | 5.67 m (nearest match), 5.87 (five nearest); matched leaders still differ by 0.66 m/s RMS (median) | **miss**, an upper bound |
| F104 DLR UT discharge per saturated cycle | no worse than the point queue | 22 saturated cycles (queue of 4 or more at green), 7.3 cars each: driver off by **0.14-0.32** cars per cycle over 3 seeds; point queue 0.41 | **pass**, a harness check only (report 05 tuned on DLR UT) |
| F107 DLR UT per-vehicle stop-line delay | no worse than the point queue | per-car stop-line crossing (delay) error: driver **2.7-3.0 s** (bias −2.1 to −2.4 s, early); point queue 4.9 s (bias +4.2 s, late) | **pass** |

## F101: why 6.3 m and not 4.0-5.5

The forecast's band was drawn from report 05's *calibrated* models (Krauss 5.43, IDM 5.54) and its lagged model (4.00). Main's driver is not calibrated: it is Krauss with SUMO's default parameters. Report 05 scored exactly that driver at 6.16 m (1 s steps) and 6.51 m (0.1 s steps) on these windows, and F105 shows the harness reproduces the 0.1 s figure to the centimetre. So the forecast was wrong in its premise, not the code: main sits where uncalibrated Krauss sits, 0.2 m better than SUMO's own at 0.1 s (6.30 against 6.51 on all windows). The difference is physical mode's: from the same starting states, main's spacing differs from report 05's Python Krauss by 1.2 m on average, where `--sumo-compat` differs by 2 cm. Main also keeps the 194 followers that start closer than Krauss's 2.5 m minimum gap, which `--sumo-compat` removes as collisions. Report 05's lag (1 s) is not in main, so nothing here could reach 4.4 m.

What the driver does wrong is visible in F109 and F108, below. The F110 floor says how much of the 6.3 m would be there anyway for another real driver: at most 5.67 m, and less, since the matched leaders are not identical. A floor without leader mismatch needs more data (highD's 110,000 vehicles are the next place to look).

## F109: the response, not the context

Given the same three seconds of history and the same leader in the next second, real followers barely change speed: −0.18 m/s at time gaps under 1 s, +0.13 m/s above 3 s, mean 0.00. Main's Krauss changes speed by −1.07 m/s under 1 s and +0.94 m/s above 3 s, mean +0.36: it steers the gap towards its own 1 s target, where real drivers on this road keep a median of 2.3 s and let it drift. Its one-second speed changes spread 0.86 m/s against a real 0.53, and its seeds barely differ (ensemble spread 0.01 m/s), so its CRPS is mostly bias. This is report 05 section 4.9's finding (drivers match the leader's speed and correct the gap over tens of seconds) seen inside the simulator. The release mechanism hands over exactly: the follower's speed at release equals the recording to 5e-5 m/s.

## F102, F103, F106, F108: what the classifier sees

Splits and permutations go by follower vehicle, never by window; five-fold CV over vehicles. TGSIM is Kalman-smoothed: the leftover position noise about a 1 s local quadratic is 2 mm, so the instrument (that noise added to simulated spacing, then the same 1 s local-quadratic smoother on both) mostly takes out 10 Hz content. It matters: without it accuracy is 0.93 and the top cue is high-frequency speed noise (Krauss's dawdling); with it 0.89, and the cues are the response. With the review's warning in mind: in this setting a window is mostly its recorded leader, so the classifier test says the scene is told apart, and F109 says why. Real against real by random vehicle halves sits at 0.49; across runs of one day 0.64, across days 0.68, both driven by speed level and jerk, i.e. traffic state and tracker, not drivers. A pass for a future driver means beating 0.64-0.68 on matched pairings, with an equivalence margin written first.

F108's feature forecast missed: acceleration and jerk are not where the driver differs most. After the instrument their Wasserstein distances are 0.18-0.24 real standard deviations, against 0.62 for the correlation of acceleration with closing speed, 0.55 for the spread of closing speed and 0.46 for the time gap. Krauss's dawdling (sigma 0.5) gives acceleration noise of about the right size; what it gets wrong is how acceleration follows the leader, the same thing F109 shows. The forecast assumed a driver without noise, and main's Krauss has noise, just not the right kind.

## F100: the harness and the maps

TGSIM: the provider's centrelines stop before the tracks do (9% of samples were past the end of the first net); the net now carries every lane 400 m on along its end tangents. Lateral map-matching error, median 0.27 m, p99 2.6 m, is the map's: the harness itself is exact (1.1 mm). 659 tracks for 657 vehicles: two tracks have a gap or a two-lane jump and are cut. Physical mode's detector logs 120 contacts among the replayed vehicles: the recording's own centre spacings under the assumed 5 m length, a reminder that bumper gaps aren't measurable on TGSIM (report 05).

DLR UT: the OpenDRIVE map converts, but its junction comes out as overlapping roads cut into edges as short as 0.2 m, with no signal program, so the approach of signal group 6 (one lane, straight on, northbound) is built from the tracks of the 610 cars that went straight through it: the median lateral offset per 2 m, smoothed. The first build was 1.5 m off: netconvert's default `spreadType="right"` puts a one-lane edge's lane beside its shape; `center` fixes it. With it, lateral error median 0.17 m, p99 1.2 m. The first replay also lost 4 cm and some last keys to f32 seconds of the day; track times are now relative to `--begin` (README). What remains, up to 3.7 cm, is the f32 step clock three hours in.

## F104, F107: one approach with recorded signals

Sunday 24 September 2023, 14:00-17:00 (the hours with the most long queues on this signal group), warm-up from 13:55, scored from 14:00, run without re-initialising. The 603 cars that went straight through signal group 6 are simulated from where the recording first sees them (its upstream edge, or wherever they are at 13:55), at their recorded speed; 53 cars that used the lane and turned, and every car on the exit, are replayed; 153 later tracker pieces of simulated cars are dropped (the driver has the car). The controller's states are one fixed program, change times on the 0.1 s grid. Signals are logged at 1 Hz, so a change is known to within a second.

| | Driver, 3 seeds | Point queue (2.0 s, 2.7 s) |
|---|---|---|
| Stop-line crossing error per car, s | 2.66, 2.88, 3.00 | 4.94 |
| Bias, s | −2.1 to −2.4 (early) | +4.2 (late) |
| Discharge per saturated cycle, error in cars | 0.14, 0.18, 0.32 | 0.41 |
| Per half hour, crossing error, s | 1.7-4.5, no growth over 3 h | 1.2-6.8 |
| Entry delays (blocked insertion) | p95 0.1 s, max 3.5 s | |
| Cars ending their comparison by meeting a replayed one | 7-9 of 603; no overlap between two simulated cars | |

The driver is early by about 2 s: it launches at SUMO's 2.6 m/s² from the first step after green, where DLR UT's first cars reach 1.8 m/s² and move 1.6 s after green (report 05 §4.3; main's own lost time was 1.38 s against a real 2.74 in report 05's acceptance table). The point queue is late by 4 s, mostly because its first car crosses 4.7 s after green where DLR UT's median is 3.6 s, and its free arrivals use the measured 9.9 m/s. A lenient variant (only cars that met red wait out the lost time) gives the same numbers. So F104 and F107 pass against this null, but the null is weak here, and DLR UT is not independent of report 05's numbers: F120 on SinD is the test that counts.

The first run of this scene had the signals wrong: the engine starts a static program at (begin − offset) mod cycle, and offset 0 put a three-hour program at the wrong place, so 22% of simulated crossings came on red and the error grew to 29 s by 17:00. That was the scene, not the driver; it is fixed and the numbers above are from the fixed scene.

## What the harness can and can't do yet

Can: replay any vehicle at its recorded lane, position and speed every step, interpolated from 5-25 Hz keys, seen by the driver as leader, neighbour and foe through the normal code paths; hand a vehicle to the driver at any moment (release); force recorded insertions while simulated entries insert normally and wait when blocked; run every window of a car-following set side by side; keep a recorded signal program to the second.

Can't yet: lateral motion of replayed vehicles (a recorded lane change is a jump at the nearer key); replayed vehicles inside a junction box on internal lanes (works through route indices but untested; F104's net has no internal lanes); the DLR UT OpenDRIVE map (netconvert makes the junction into overlapping fragments with edges 0.2 m long and no signal program, so the approach was built from the tracks); a T1 floor free of leader mismatch; seeds that spread (main's Krauss runs differ by 0.1 m in F101, 0.01 m/s in F109).

## Not reached

- **F120 on SinD.** The four SinD recordings on disk (`datasets/jt25-sind`, about 15 minutes each, Changchun, Chongqing, Tianjin, Xi'an) have tracks and signal logs but no map: stop lines and which light controls which approach have to be inferred from the tracks first, then headway and lost time measured on the other approaches for the null. `dlrut_approach.py` is the template.
- **highD, inD, rounD, exiD as scenes.** Designed in README.md; not built.

## Rerun

```sh
source /home/erikf/projects/personal/cars-data/dev-env.sh
cargo build --release -p cars-cli
python3 -I scripts/replay/tgsim_scene.py build I90mov 1 && python3 -I scripts/replay/tgsim_scene.py f100 I90mov 1   # F100 TGSIM
python3 -I scripts/replay/f101.py build
for s in 0 1 2 3 4; do python3 -I scripts/replay/f101.py run main $s; python3 -I scripts/replay/f101.py run sumo $s; done
python3 -I scripts/replay/f101.py score                       # F101 -> f101.json
python3 -I scripts/replay/f105_python.py                      # F105 -> f105.json
python3 -I scripts/replay/floor_t1.py                         # F110 -> f110.json
python3 -I scripts/replay/classifier.py                       # F102 F103 F106 F108 -> classifier.json
python3 -I scripts/replay/f109.py build && python3 -I scripts/replay/f109.py run main 0..9 && python3 -I scripts/replay/f109.py score
python3 -I scripts/replay/dlrut_approach.py build && python3 -I scripts/replay/dlrut_approach.py f100   # F100 DLR UT
python3 -I scripts/replay/dlrut_approach.py f104 0..2 && python3 -I scripts/replay/dlrut_approach.py score   # F104 F107
```

All runs use `CARS_ADAPTER=llvmpipe` (set by `rpl.run_cars`); pass `--gpu` where offered to go through `flock /tmp/cars-gpu.lock` instead. Scenes and outputs go to `/home/erikf/projects/personal/cars-data/replay/`.
