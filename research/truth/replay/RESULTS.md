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

# Third round, 7 November: area entry, two-wheelers, stitching, signals, F520-F526

The job: make area entry work (F515 had failed it), then check the harness again on whole areas and measure the T3 noise floor. Forecasts F520-F526 were written before each run; results in `foundations/forecasts.csv` and the JSON files next to this one. Design notes are in README.md ("Insertion blocked at the entry", "Vehicles off the car path", "Stitching and lane connections") and the scene changes in PNEUMA.md. The driver, junction and lane-change code are main's (the junction-fault fixes merged at ce55b16 included); plain runs without `--replay` are byte-identical to main's binary (below).

| | Forecast | Result | Verdict |
|---|---|---|---|
| F520 checked boundary entries, then replayed (drone 8) | p50 0, p95 under 1; over 2 where a recorded queue stands at the view edge; none waiting | p50 **0.0 s**, p95 **0.4 s** of 1,704 entries; queue approaches p95 0.0-1.9 s; 1 waiting | overall pass; the queue split misses (the entry is upstream of the view edge); 1 waiting |
| F521 two-wheelers off the car path | (a) 20-30 % of motorcycle time off; (b) holds down 25-50 % | (a) **20.9 %**; (b) car-seconds held **-27 %** | pass |
| F522 stitching | 40-70 % joined, error under 5 m, under 2 of 30 false | **59.6 %**, median **3.6 m**, **0 of 30** | pass |
| F523 signals | 35-55 of 87 links; under 20 % of new reads off-cycle | **70 of 95** (62 of 87 before connections were added); 2 of 12 off-cycle | links miss above; off-cycle pass |
| F524 drone 8, every car simulated | 98 % enter, travel time MAE 5-20 s | **39-41 %** enter, 59-61 % still waiting, travel time MAE **106-134 s** | **miss**, two rounds, stopped |
| F525 drone 6, every car simulated | 95 % enter, travel time MAE 10-40 s | **43-45 %** enter, 54-57 % still waiting, travel time MAE **138-188 s** | **miss** |
| F526 T3 noise floor, drone 8 09:00 | halves under days | halves: delay **1.5 s**, travel time **7.6 s**; mornings: 1.5-2.3 s and 9.8-10.9 s (24 Oct 10.4 s and 55.6 s) | bracket measured; delay floor lower than forecast |

## Step 1: boundary entry (F520)

A simulated car now enters at the start of its first edge, its front at min(length + 0.1 m, where it was first seen). The time is carried back at its first-seen speed; the lane and speed are recorded. The speed is lowered to the insertion-safe one if the leader asks for it. The entry is refused only when the spot is taken, and the car then waits in a FIFO of its own lane (`depart_speed_mode` 8, one case label in `try_insert`; per-lane queues in `replay.rs`). The view's edge comes from the recording itself: an entry is at the boundary when a point up to 30 m behind it, along its heading, was never driven on by anyone in the file. On drone 8, of 1,846 simulated cars: 142 start in view (forced at their recorded state, as before), 1,455 enter at the boundary, 2 are first seen under 1 m/s (a recorded queue at the view edge), 234 were seen off the net first (side streets missing from OSM's car net), and 13 appear mid-view.

The harness check runs every car through this entry and then replays it, so only the recording itself can hold an entry. The entry delay is p50 0, p95 0.4 s, max 19 s. The forecast named the approaches where a recorded car stands within 12 m of the view edge (Mavromataion 59 % of the time, Gkyilfordou 35 %, Patision south 27 %, Patision north 14 %) and expected p95 over 2 s there. It is 0.0-1.9 s. The premise was wrong: the entry is the edge start, which on Mavromataion and Gkyilfordou lies 15-97 m before the view edge, so a queue standing at the view edge does not reach it. On the two Patision edges, whose start is the view edge, the queues do reach it, but hold entries under 2 s.

The first run had 32 cars still waiting and a longest delay of 197 s, all on the Patision kerb lane. The cause was a taxi and a motorcycle parked 4.1 m and 4.9 m right of that lane's centre, on the kerb, which the 6 m matching had put on the lane. Cars in the recording drove past them. That is the case for the next rule; with it, one car is still waiting: an interior entry that appears mid-queue on a 22 m edge and never finds 2.5 m.

## Step 2: vehicles off the car path (F521)

A replayed vehicle is in the simulation only while its body overlaps the path of a car centred on its lane (|offset| under 0.9 m plus half its width), with runs under 1 s merged. That removes 20.9 % of motorcycle samples (filtering) and 8.5 % of the other replayed classes (parked at the kerb). It is all in the scene builder. In the all-cars run, simulated car-seconds held by a two-wheeler leader fall from 7,056-7,804 to 5,356-5,598 per run (-27 %, pre-merge driver; after the merge 5,188-5,496 against 7,304-7,684, -29 %). Replayed vehicles running into simulated cars fall 20 %. What it can't do: a simulated car changing lanes through a filtering motorcycle doesn't see it.

## Step 3: stitching, lane connections, signals (F522, F523)

**Stitching.** pNEUMA's raw tracks are whole per drone file: 2,784 tracks for 2,781 vehicles, and only 2 end-start pairs of different IDs agree within 3 m and 10 s. So the 1.56 pieces per vehicle are map matching's (off-net gaps, movements the net lacks), and a stitch only re-routes one vehicle. 59.6 % of later pieces join (median error 3.6 m, p90 11 m). Thirty joins plotted against the raw tracks were all right; 29 resume on the same edge after a short gap and one runs through a junction. 190 do not join because the distance disagrees (median 37 m: off the net and back), and 149 because there is no path within 4 edges.

**Lane connections.** 4.9 % of recorded car movements left an edge from a lane with no connection to their exit. They were concentrated on a few movements: on Patision 259806440#1 → #2, 204 of 432 cars use the lane netconvert dropped; on the left into 758432181#0, 30 of 47 come from lanes 0-1. The 12 connections that 3 or more cars use are added, and the scene is matched again: 0.9 % are left. The F100 replay on the new net is still exact: 99.1 % of samples present, lane coordinates p99 2.1 cm, front 2D median 0.11 m, p99 1.79 m.

**Signals.** Every incoming edge of a signalised junction of the scene's net is now offered to the unchanged reader. Edges under 60 m get their straight-on predecessor put in front. A read off its controller's cycle by more than 1 s is fitted again at the controller's cycle (the longest read there; a shorter one is a harmonic). The 7 approaches read before come out identical, and 13 more are read, with 70 of 95 links read. The other 25: 11 have no traffic; 3 have no conflicting vehicle movement and nobody stops; 11 are unreadable (cars stop, but there are too few heads or no periodic fit), and these stay green. Six approaches with no conflicting vehicle movement read periodic at R 0.96-1.0 (pedestrian phases, or a joined junction's second stop line); the forecast had not counted them, hence the miss above its band. Read signals carry SIGNALS.md's band: onset ±0.6 s, end ±2.6 s median.

## Step 4: every car simulated again (F524, F525)

Drone 8, 5 seeds, main's driver after the merge (pre-merge runs in parentheses, numbers alike):

| | Simulation | Recording |
|---|---|---|
| Entered | 712-751 of 1,846 (676-746) | 1,846 |
| Still waiting to enter at the end | 1,095-1,134 | 0 |
| Entry delay p50 / p95 | 0.5-2.8 s / 490-626 s | |
| Reached their recorded exit point | 292-317 | 1,721 |
| On the net at the end | 232-260 | 125 |
| Travel time error, cars that finished: MAE / bias | 106-134 s / +93 to +124 s (n 161-187) | mean 56-62 s |
| Same, cars before their first overlap with a replayed vehicle | **19-35 s / -6 to -12 s** (n 48-62; pre-merge 12-21 s / -5 to -10 s) | |
| Approach delay, 5-minute bins: MAE / bias | 77-94 s / +76 to +94 s; by bin 26-32, 93-106, 132-143 s | mean 5.5 s |
| Per-approach mean delay over the run (as the floor) | MAE 89-112 s | floor 1.5-2.3 s |
| Per-route mean travel time (as the floor) | MAE 92-142 s | floor 7.6-10.9 s |
| Simulated cars meeting a replayed vehicle | 523-566 (72-77 % of those that entered) | |

The entry is not what fails. F520 holds no car when traffic moves as recorded, and the cars scored before they meet a replayed vehicle come out within 20-35 s, early. The area locks up within the first five minutes, and from then on entries wait behind the simulated queues. The jam's roots (`cars jam --seeds` on seed 0) move as the scene is corrected, but always sit in the joined junction clusters of Patision and Alexandras:
- first, cars on Alexandras westbound yielding into a full box, and 314 cars missing a turn they had to change lanes for in a standing queue. The missing lane connections were part of that; with them added, 198-231 cars still miss a turn;
- then two stop lines 10 m apart on Patision southbound read at 45 s and 90 s; refitting the 45 s read at the controller's 90 s fixed that pair;
- then a start-snapshot car placed on the bus lane, with no car link out, stuck for 995 s; moved to the nearest car lane;
- what remains: a side street yielding into Patision (1445619556) never served for 992 s, full junction exits (`junction lane occupied or exit full`) and right of way at the clusters' internal links (`next lane or right of way`). That is junction and lane-change behaviour, which is being rewritten elsewhere.

Two rounds of scene corrections without a pass, so stopped (rule 9).

Drone 6 (Marni, 29 Oct 09:00), the second check, built the same way, with an exact replay (F100: 99.0 % of samples, lane coordinates p99 1.7 cm, front 2D median 0.19 m, p99 2.7 m). 86 of 166 links are read; 32 where cars stop are unreadable; 15 observed connections are added. Five seeds after the merge: 791-835 of 1,838 enter, 1,001-1,045 are still waiting, 249-274 reach their exit against 1,735 recorded. Travel time MAE is 138-188 s (bias +117 to +173 s); cars before their first overlap 19-37 s (bias -8 to +1 s, n 34-45). Approach delay MAE is 104-141 s, and 76-77 % of entered cars meet a replayed vehicle. Here only 8-9 cars miss a turn, so turns are not what locks the area: the stuck heads are held by right of way and full junction exits (`10971766#0`, 872 s).

## Step 5: the T3 noise floor (F526)

The recording against itself, measured with the code the runs are scored with (`t3_metrics.py`, `t3_floor.py`). Approaches and their free speeds come from 29 Oct; per-approach mean delay is over approaches with 30+ cars on both sides, per-route mean travel time over routes (first edge to exit edge) with 5+ cars on both sides.

| Drone 8, 09:00 | Approach delay MAE (bias) | Route travel time MAE (bias) |
|---|---|---|
| Two halves of 29 Oct (8 minutes each) | **1.48 s** (+0.05), 21 approaches | **7.6 s** (-2.8), 20 routes |
| 29 Oct against 30 Oct | 2.29 s (+1.4) | 10.9 s (+8.4) |
| 29 Oct against 1 Nov | 1.53 s (+0.7) | 9.8 s (+7.6) |
| 29 Oct against 24 Oct | 10.4 s (+10.4) | 55.6 s (+54.8) |

Halves are under days on both metrics, as PLAN expects. The approach sections are only the last 60 m before the line, where the mean delay is 5.5 s, so their floor is small. 24 Oct is a different morning: its mean approach delay is 15.7 s against 5.5-6.9 s on the others. A T3 score on drone 8 at 09:00 therefore has the bracket: approach delay 1.5-2.3 s, route travel time 7.6-10.9 s (10.4 s and 55.6 s if a congested morning counts as the same condition). Today's all-cars run is 40-60 times outside it.

## Plain runs

Main's binary (26e674d, after the measured driver's round 2) against this branch, no `--replay`: the FCDs are byte-identical on the DLR UT approach (llvmpipe, 900 s) and on exiD 00 all simulated (llvmpipe and GPU). The drone 8 scene run as a plain run on the GPU is not deterministic with either binary. Over four runs each, both binaries gave the same two outputs (`3a36bc…` and `f9020d…`), in different proportions. The area runs above are at main ce55b16; the later merge changed only the measured driver (off by default) and roundabout entries, and these areas have none.

## What still blocks area scoring

- **The simulated stream locks the joined junction clusters** in both areas, with main's driver before and after the junction-fault merge: boxes fill, side streets are never served, and 25-34 % of drone 8's trips miss a turn. Until those boxes clear, no T3 number is scored. The quickest localisation would be T2-style runs of one corridor at a time (Alexandras westbound, Patision southbound) with the rest replayed.
- **Signals.** 11 links on drone 8 and 32 on drone 6 where cars stop stay green. Two-greens-a-cycle approaches are folded into one long green.
- **The harness's own limits.** A vehicle off the car path is invisible to a car changing lanes through it. 40 % of later pieces are not stitched. 234 entries on drone 8 come from side streets missing from the net. Exits beyond the view have no replayed leader yet (PLAN, "Queues from outside the view"). Replayed vehicles don't react, so in a jam 72-77 % of simulated cars meet one.

## Rerun (third round)

```sh
source /home/erikf/projects/personal/cars-data/dev-env.sh; cargo build --release -p cars-cli
# PNEUMA.md "Rerun", third round: build (with --signals), f100, entry (F520), mix (F524, F521 with --name=mix_keep2w), drone 6 (F525), t3_floor.py (F526)
```

# Fourth round, 7-11 November: why the areas lock, F900-F915

`LOCK.md`. Four lock chains traced with new arbiter probes, each starting somewhere else: the net's lane mapping (J54), a replayed vehicle standing where real cars passed it (J60; Omonoia on drone 6), and on Patision south a corridor that cannot carry its flow even alone on an empty net (F913: 62 %). Kept: signal programs written right (a rounding bug gave 9-20 s yellows and lost greens), recorded lane mapping and lanes opened where recorded cars drive, keep-clear only on links with foes, a tie for a zone kept by the standing car that won it. F524 again (F914): 52-55 % enter (was 39-41 %), approach delay MAE 68-78 s (89-112), route travel time MAE 72-100 s (92-142); F525 again (F915): 49 % (43-45 %). Still 30-50 times the floor.
