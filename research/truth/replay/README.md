# Replay with recorded boundaries: design

Written 6 November 2026, before the code. PLAN.md says why: in a recording that sees every vehicle, put the recorded entries, exits and signal states into the simulator at the edge of the recorded area, simulate only inside, and compare. Then only the driver, and the map, can differ.

## What a scene is

A replay scene is a normal `cars run` input (net, routes) plus one extra file, `--replay tracks.rpl`. The tracks file lists, per trip, a recorded track: lane and position along the lane, and speed, at a fixed key interval, and a **release time**. Before its release time a trip is *replayed*: its state is overwritten from the track every step. From the release time on it is *simulated*: the driver drives it. One number per trip decides which vehicles are simulated:

| Setting | Release time |
|---|---|
| All replayed (harness check, F100) | never (+inf) |
| T1, one vehicle | +inf for all but one; that one is released at the start of its window |
| T2, one lane or approach | at entry for the vehicles on it, +inf for the rest |
| T3, all | at entry for every class we model, +inf for motorcycles, bikes, buses |

A simulated vehicle that enters at the area edge needs no track: it is an ordinary trip with recorded `depart`, `departLane`, `departPos`, `departSpeed`, and a route that ends on its recorded exit edge.

## From a recording to a scene (`scripts/replay/`)

1. **Map.** The recording's own map where it has one (DLR UT: OpenDRIVE, converted with `netconvert`, used only as a format converter). Where it has only lane centrelines (TGSIM), a net is written from them: one edge, lanes in the recorded order, shapes from the provider's centrelines. The map is checked against the tracks before anything else: the lateral distance of every sample to its lane's centreline (the map-matching error) is reported with the scene.
2. **Map matching.** Each sample is projected onto the centreline of its recorded lane (TGSIM gives a lane label) or onto the nearest lane whose direction agrees within 45 degrees (DLR UT, which gives none). Position along the lane is the arc length of the projection. A track whose lane sequence is not a path in the net (a jump of two lanes in one sample, a lane the net does not have) is cut there; cuts are counted.
3. **Entries.** First sample of each track: time, lane, position, speed. Exits: last edge of its lane sequence. Both are facts of the recording.
4. **Replayed tracks.** Keys at the recording's own rate (TGSIM 10 Hz, DLR UT 5 Hz). The kernel interpolates linearly to the simulator's dt within a lane; across a lane change it takes the nearer key, since main has no lateral motion yet.
5. **Signals.** DLR UT logs every signal group at 1 Hz from the controller. Each change becomes a phase of one long fixed-time program (`tlLogic` with one phase per recorded interval), with link indices mapped to signal groups by the stop-line positions of the dataset documentation (Table 3). So the simulator sees exactly the recorded states, to the second. TGSIM has no signals.

## How replayed vehicles live on the GPU

A replayed vehicle is an ordinary `Veh`: it is inserted through the normal queue, sorted into its lane, and so it is the leader, the neighbour and the foe that simulated vehicles see, by the same code paths as any other vehicle. Three small things make it replayed:

- **Insertion is forced.** Its trip has `depart_speed_mode = 7` (recorded speed, no safety check), so a recorded entry is never refused or delayed because the driver model thinks it unsafe. That is the only change to `step.wgsl`: three conditions in `try_insert`. Replayed trips get their own insertion queue per lane, so a simulated entry that is blocked never holds a replayed one back.
- **Its own decisions are switched off where they would leave a trace.** Replayed trips get a vType with lane changing off (`lcStrategic=-1`, the other `lc*` 0), so they never start a lane change, claim cells or make a shadow.
- **A new pass overwrites its state.** `shaders/replay.wgsl`, entry `replay_apply`, runs after lane changing and before collision detection and insertion, over all active vehicles. For a vehicle whose trip has a track and whose release time has not come, it sets lane, position, speed, acceleration and route index to the track at this step's time, clears lateral motion bits, updates `tail` on a lane change like `lc_commit` does, and removes the vehicle when its track ends inside the area (a tracker fragment ends, or it leaves the field of view). A shadow of a replayed trip is removed and counted. It has its own bind group (group 1: tracks, keys, per-trip index, counters) like `keys` and `gather`, so it touches no struct in `common.wgsl`. Its structs `ReplayTrack` and `ReplayKey` have `#[repr(C)]` twins `GpuReplayTrack` and `GpuReplayKey` in `world.rs`. No function-local arrays. Without `--replay` the pass is not compiled into the module and not dispatched, so runs without it are bit for bit what they were.

The order inside a step is then: plan and exec move everyone (replayed vehicles too, by the driver), lane changes, `replay_apply` puts replayed vehicles where the recording has them at the end of this step, collision detection, insertion. The next step's plan sees replayed vehicles at their recorded places. A simulated follower therefore reacts to its recorded leader one step late, which is the same order as report 05's Python rollout.

## When a simulated and a replayed vehicle overlap

The recorded vehicle is never moved: it is a fact. The overlap is detected after the run, from the trajectory output, as a negative bumper gap between a simulated vehicle and a replayed one on the same lane (and from physical mode's 2D contact log, which already records both trip ids). It is counted, and the comparison window of that simulated vehicle ends at the step before it: what follows is no longer a comparison of the same situation. This is what Waymo's Sim Agents challenge does with its log-replay agents (Montali et al. 2023): log agents do not react, and collisions with them are scored, not resolved. Overlap counts are a result in their own right, reported next to every number.

## Downstream boundary

A recorded queue beyond the area's exit must still hold simulated vehicles back. The scene keeps a **replayed exit zone**: the exit edges are kept for as far as the recording sees, and every vehicle on them that is not simulated is replayed there, including vehicles that came from other approaches. A simulated vehicle leaving the approach thus meets the recorded queue on its exit. It arrives at the end of the exit edge, where the recording loses sight of it. Beyond the recording's field of view nothing is known, so a queue that spills into the area from beyond the field of view shows up only through the recorded vehicles at the far end of the exit zone. On TGSIM I-90/94 the exit zone is the downstream part of the one edge; on DLR UT it is the exit edges inside the drone's view.

## Insertion blocked at the entry

A simulated vehicle that cannot enter at its recorded time (its entry is occupied by a simulated vehicle that is slower than the recorded one was) waits in its queue as SUMO-family simulators do. Its delay, actual minus recorded entry, is written per trip and reported: it is a result, a sign that the simulated stream upstream is slower than reality. It is never hidden by scaling or removal.

## What each experiment needs from this

- **F100.** All vehicles replayed; output equals the recording. Errors: the harness (timing, interpolation, insertion), measured in lane coordinates, which should be zero at key times; and the map, measured as distance in metres between the simulated position drawn on the net and the recorded point.
- **F101.** One simulated follower per window behind its replayed leader. Report 05's windows (I-90/94 moving day, 4,955) and spacing definition (centre to centre). Each window is its own one-lane edge so windows run side by side in one GPU world, as report 05's windows were separate rollouts. In the full multi-lane scene the follower would also be free to change lanes; that is a lane-change question for later.
- **F102, F103.** Trajectory output of F101 cut into 10 s windows, after passing the simulated tracks through the recording's instrument.
- **F104.** DLR UT, one approach, every car on it simulated from its recorded upstream entry, the rest of the junction replayed, the recorded signal states.

## Limits known before starting

- No lateral motion: a recorded lane change is a jump at the key nearer in time. Main's driver jumps too.
- TGSIM ramps: the one-edge net carries ramp lanes over their whole length. Replay is unaffected; a simulated vehicle on a ramp lane would not see its end. F101 does not use ramp lanes.
- Tracker fragments: a track that ends inside the area and a new track that starts nearby may be the same vehicle. Replayed, both are kept as recorded; simulated, a fragment's end is an exit that did not happen. Counted per scene.

## After the review (PLAN.md at 7d2065b)

- **Overlaps are a harness artefact.** A replayed vehicle never reacts, so a simulated car that runs into one has met something no real driver meets. Overlaps are counted per run and end that vehicle's comparison; they are never scored as behaviour. Passes are judged at the second and third settings, where every car on the scored part reacts.
- **Start from the recorded snapshot, discard a warm-up, never re-initialise.** A scene's run starts at `--begin` with every vehicle that is in view at that moment inserted at its recorded state (replayed or simulated), runs without interruption to the end, and is scored only after a warm-up as long as the longest trip in the scene. Error is reported against elapsed time (per half hour on DLR UT). F101's 30 s windows are the one exception, kept on purpose so that F101 compares with report 05; they are re-initialised by design and say nothing about drift past 30 s.
- **Times are relative to `--begin` on the GPU.** A track's `t0` and `release` are stored as seconds after `--begin`, computed in f64 on the CPU. In f32, seconds of the day (50,000 s) are only good to 4 ms, which cost the first DLR UT replay 4 cm and dropped the last key of 813 pieces.

## Loading other recordings as scenes

A loader's job is the same for every dataset: a net (or the dataset's own map, converted), map-matched tracks as lane and position, one `.rpl`, one routes file, and `matched.csv.gz` with the recorded samples for scoring. `scripts/replay/rpl.py` holds the shared parts (writer, `Polyline` projection, netconvert call, FCD reading). Loaders on disk: `tgsim_scene.py` (lane labels and provider centrelines), `dlrut_approach.py` (one approach built from the tracks, controller states as a fixed program), `f101.py` and `f109.py` (one edge per window).

**highD, exiD, inD, rounD** (`datasets/levelx/<name>/<name>.zip`, non-commercial, no redistribution; read with `python3 -I`, nothing executed). Each recording has `*_tracks.csv` (25 Hz, positions of the bounding box, lane ids on highD), `*_tracksMeta.csv` (class, size, frames) and `*_recordingMeta.csv` (frame rate, speed limit, lane markings on highD). inD, rounD and exiD also ship each location's map as Lanelet2 (`maps/lanelets/*.osm`, exiD `maps/lanelet2/`) and as OpenDRIVE (`.xodr`); highD has none.
- *highD, one follower on a German motorway:* lanes are straight and given by the marking positions in `recordingMeta`, so the net is one edge per driving direction with those lane widths, written like the TGSIM net. `laneId`, `precedingId` and `frame` give the leader-follower windows directly; cut them with report 05's rules (`opus_windows.py`) and run them through `f101.py`'s one-edge-per-window build. Keys at 25 Hz, so `key_dt` 0.04.
- *inD and rounD, gap acceptance:* convert the location's `.xodr` with `netconvert --opendrive`, and check its junction before use: DLR UT's came out as overlapping fragments. Where it does, write the lanelets' centrelines (Lanelet2 `.osm`, plain XML) to plain edges, as `dlrut_approach.py` does from tracks. The simulated vehicle is the one entering from the minor approach, released when it reaches a fixed distance before the yield line; every other road user stays replayed, including pedestrians and bicycles as replayed vehicles of their class. Score accepted and rejected gaps against the recording.
- *exiD, merges:* as highD, with the ramp as its own edge joining the main road.
