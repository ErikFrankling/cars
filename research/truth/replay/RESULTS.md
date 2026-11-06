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

# Second round, 6-7 November: data side and harness, F500-F515

The data side for area tests, and the harness extended so the drivers being rewritten in parallel can go onto whole areas. Forecasts were written before each run. Details: [SIGNALS.md](SIGNALS.md) (signals read from crossings, the error band) and [PNEUMA.md](PNEUMA.md) (inventory, lanes, motorcycles, oversaturation, the drone 8 scene). The driver and the junction and lane-change code are main's, unchanged. Plain runs without `--replay` are bit-identical to main's binary (a8cddaf): FCD md5 equal on the DLR UT approach (llvmpipe) and on exiD 00 all simulated (llvmpipe and GPU).

| | Forecast | Result | Verdict |
|---|---|---|---|
| F500 onset read from queue heads, DLR UT | median 0.5-1.2 s, p90 under 2.5 | **0.58 s, p90 1.38 s** (2,698 greens with a car standing) | pass |
| F501 end of green per cycle | saturated 0.8-2.0 s | 8.0 s: DLR UT gaps out after the queue clears, one oversaturated cycle in 24 h | miss: per-cycle ends unreadable on these sites; the fixed-time fit takes over |
| F502 missed / false greens | under 3% / under 5% | 7.7% / 0.3% | missed miss (head over 10 m back, track ends before the line, stood under 2 s); false pass |
| F503 SinD | onset 0.6-1.5 s | **0.59 s**, p90 2.26; missed 7.0%, false 0 | onset pass, missed miss |
| F504 fixed-time fit (SinD, 9 groups) | cycle 0.5 s, onset 1.0, end 1.5 | cycle **0.05 s**, onset **0.56 s**, end **2.64 s** (p90 5.1); from the next onset 1.06 s where every phase is read | end miss |
| F505 by queue at onset | no level over 1.5 s | 1-3 standing 0.58, 4+ 0.58, oversaturated 0.98 (n = 1) | pass, oversaturated untested |
| F506 highD 01 F100 with lateral keys | 2D median under 5 cm | centre 2.1 cm p99 3.1 cm; front max 7.7 mm; lane coordinates max 2.7 mm | pass |
| F507 exiD 00 on merged multi-lane edges | under 1.1 pieces per vehicle, 2D median under 10 cm | **1.00** piece per vehicle (was 1.39), front 2D median 1.1 cm, p99 25 cm | pass after three fixes to the scene builder |
| F508 pNEUMA drone 8 F100 | median under 0.15 m, p99 under 1.0 m | 99.1% of samples present; lane coordinates p99 2.1 cm; front 2D median **0.11 m**, p99 **1.81 m** | median pass, p99 miss (the centre's offset moves the whole body) |
| F509 lanes from density against OSM | agreement 40-70%, residual 0.25-0.5 m | **56.7%** of 314 edges; residual 0.38 m (0.89 m about OSM's lanes) | pass |
| F510 motorcycles | 25-45% per area, over 40% between lanes | 29-39% of vehicles, 21-32% of time; 51% between lanes | pass |
| F511 oversaturation | worst approach over 20% on 3+ areas | all 10 areas, 32-74% of cycles with a residual queue | pass |
| F512 SinD saturated cycles | 0-2 | **0** on Tianjin approach 2 (Tianjin and Chongqing have no car queue over 3) | pass: F120 as written can't be measured on SinD's two usable cities |
| F513 SinD Tianjin approach 2, crossing error | driver 1-3 s, no worse than the point queue | driver **3.57-4.10 s** (5 seeds), bias +0.0 to +0.7; point queue **1.33 s**; without two-wheelers 2.67-3.43 | **miss**, explained below |
| F514 discharge per queued cycle | driver no worse than the point queue | driver 0.10 cars, point queue 0.00 | miss by one car in ten cycles |
| F515 pNEUMA drone 8 mix (harness check) | 99% enter, delay p95 under 2 s | all forced: 100% enter, 60-65% still on the net at the end (boundary entries stacked onto full edges); snapshot forced only: **29-32%** enter, delay p95 607-660 s | **miss**, two rounds, stopped: boundary entries are the open problem (below) |

## F513: why the driver loses to a point queue on SinD

On SinD Tianjin approach 2, 22 crossings are scored. Most of the driver's crossings are within 2 s of the recorded ones; without its three largest errors its MAE is 0.9-1.3 s. Three cars per run carry the rest:
- One simulated car runs a yellow (it enters 16 m before the line at 7 m/s, 1.3 s into the yellow) where its real driver stopped. That costs −33 s, a whole cycle.
- Two cars on the left lane wait 7-15 s into green behind a replayed motorcycle standing in the junction box at the start of their exit lane. In reality they passed beside it; in a lane model a replayed motorcycle blocks the whole lane.
- One real car crossed 4.5 s before its green.

Removing two- and three-wheelers leaves the yellow-runner and gives 2.7-3.4 s. The point queue has no yellow decision and no motorcycles, so on a sample this small it wins.

What this says:
- Mixed traffic needs two-wheelers that don't occupy a whole lane before SinD (or Athens) can test a car driver at the line.
- The yellow decision is a measured behaviour (report 05: half stop at 5.1 s to the line) the driver should be checked against on its own.

The null's saturation headway is SinD's clock-free 2.6 s (other cities), because Tianjin's other approaches give one car-to-car headway; its first-car time, 1.91 s after green, is Tianjin's own.

## F515: cars simulated on a whole pNEUMA area

A harness check on drone 8, five seeds each way.
- **Every simulated car forced in** at its recorded state: all of them enter, but 60-65% are still there at the end. Cars entering at the boundary were put onto edges the simulated queue already filled: 431 cars on a 35 m three-lane edge of Patision, about 5,400 simulated-on-simulated overlap pairs.
- **Only the start snapshot forced**, later entries inserted normally: the stacking is gone (132-160 pairs), but only 29-32% of the cars get in, with entry delays to 660 s.

A car's recorded entry is where the tracker first sees it, often inside a queue at the edge of the view. If the simulated queue or a replayed motorcycle is there, it waits, and the per-edge insertion queue holds every later car on that edge.

Two rounds without a pass, so stopped (rule 9). Next:
- enter at the start of the boundary edge with the time carried back;
- per-lane insertion queues;
- two-wheelers that don't take a whole lane (also F513).

Until then no T3 number is scored on pNEUMA.

## What the harness can do now

Everything in the first round, plus:
- **Lateral replay** (`RPL2`): a replayed vehicle moves sideways as recorded, across lane changes on an edge, and is drawn and contact-checked where it is. The released driver starts on its lane's centre.
- **Multi-lane levelX scenes**: highD (one edge per carriageway); exiD (parallel lanelets merged, explicit lane-to-lane connections, junction radius 0, keys from the projected front, fronts moved onto the next lane).
- **SinD approaches with no map**: lanes and stop line from the tracks, the recorded light, two-wheelers replayed while over a car lane, a variant without them.
- **Signals without a log**: the reader with its error band (SinD, DLR UT scored), fixed-time programs for pre-timed sites, one long program per junction.
- **pNEUMA**: streaming reader; lanes from density checked against OSM; signals read at every OSM signalised approach in 199 files; residual queues per cycle; a T3 scene with internal lanes, path bridging, read signals, and simulated cars forced in at their recorded state and released at once (a recorded tight gap is never refused).
- **Insertion steps**: F100 scoring leaves each trip's insertion step out and reports how late it came.

Can't yet:
- Two-wheelers that share a lane with a car.
- Simulated entries at a pNEUMA area's boundary (F515): forced, they stack; unforced, two thirds never get in.
- Routes through cuts in pNEUMA: 1.56 pieces per vehicle; a simulated car's route ends where its first piece ended.
- Read signals on approaches with few standing cars: 70 of 87 links in drone 8 stay green.
- A saturated-cycle test on SinD (F120).
- Songdo: its 85 junction-day zips are on disk (the `fetch-drones` job finished), not started.

## Rerun (second round)

```sh
source /home/erikf/projects/personal/cars-data/dev-env.sh; cargo build --release -p cars-cli
python3 -I scripts/replay/signals.py dlrut && python3 -I scripts/replay/signals.py sind && python3 -I scripts/replay/signals.py score   # F500-F505
python3 -I scripts/measure/levelx_scene.py highD 1 && python3 -I scripts/replay/levelx_f100.py $D/levelx-highD-01        # F506
python3 -I scripts/measure/levelx_scene.py exiD 0 && python3 -I scripts/replay/levelx_f100.py $D/levelx-exiD-00-merged   # F507
python3 -I scripts/replay/sind_approach.py build && python3 -I scripts/replay/sind_approach.py f100
python3 -I scripts/replay/sind_approach.py run 0..4 mix && python3 -I scripts/replay/sind_approach.py run 0..4 mix_no2w && python3 -I scripts/replay/sind_approach.py score   # F512-F514
# pNEUMA, F508-F511, F515: PNEUMA.md "Rerun"
```
`$D` is `/home/erikf/projects/personal/cars-data/replay`.
