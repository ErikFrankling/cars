`cars run` preserves the former simulation flags. `cars record` runs a headless
simulation and produces H.264 MP4 with burned-in titles, captions and statistics.
Run from the development shell (`nix develop --command cargo run -p cars-cli -- …`).

```sh
cars record --net network.net.xml --routes demand.rou.xml \
  --additional vtypes.xml,signals.add.xml --dt 1 --begin 300 --end 600 \
  --steps-per-frame 2 --fps 30 --width 1920 --height 1080 \
  --camera camera.json --out traffic.mp4 --title 'A city in motion' \
  --subtitle 'Every light is a driver'
```

Camera JSON (coordinates in network metres, `time` in absolute simulation seconds):

```json
{
  "keyframes": [
    {"time":300,"center":[1000,900],"metres_per_pixel":4},
    {"time":600,"center":[1200,800],"metres_per_pixel":0.3}
  ],
  "captions": [{"from":400,"to":500,"text":"The evening rush begins"}]
}
```

Use `frame` instead of `time` for a keyframe indexed from the first recorded frame.
Center uses smoothstep easing; scale interpolates exponentially. Captions always
use simulation seconds. `--fit` overrides keyframes; without a camera, fit is the
default. `--color speed|type|wait|paint` controls the palette. Type mode treats
ACC/CACC models as automated vehicles. Waiting color reaches red after 60 seconds.

The warmup runs without rendering. Each frame advances up to `steps-per-frame`
steps, stopping at the end bound (rounded up to a simulation step). Video duration
is `ceil((end_step - begin_step) / steps_per_frame) / fps`. HUD speed averages
nonremoved replica-0 vehicles; clock is simulation time modulo 24 hours.

Rendering uses cumulative polyline lengths and a GPU binary search to map lane
position to geometry, respecting differences between lane and geometric lengths.
Static lane-width segment quads fade at subpixel scales, with subdued internal
lanes and brighter fast roads. Vehicles become additive soft dots as scale
increases. Signals are visible below 2 metres per pixel and use the live TLS phase.
4x MSAA resolves into an HDR rgba16float target before a small highlight halo and
exponential tone map. Only RGBA pixels and small statistics are read back, unless
an overlay asks for vehicle state; replica 0 is rendered. Renderer memory is linear
in geometry and capacity.

Output dimensions must be even and at most 1920 on either axis. GPU submissions
use `Sim::run`'s short adaptive batches; rendering is a separate submission.
CPU libx264 uses two threads, CRF 20, veryfast preset, yuv420p; hardware encoders
are never used. The `.ass` sidecar is retained for editing. The silent intermediate
is deleted after a successful libass burn-in and retained on failure.

Validated on RX 7900 XT with ring and Bologna captures at 1280x720. Run only one
GPU job at a time, through `flock /tmp/cars-gpu.lock`.

For large demand files, `--capacity` bounds the active vehicle buffers (default 0
allocates for every trip). `--time-to-teleport` and `--ignore-junction-blocker`
accept the same settings as `cars run`, so recordings can use matching dynamics.

## Looking closely at intersections

```sh
# The busiest junctions of each kind, ranked by vehicles entering if given an edge CSV.
cars junctions --net net.xml --edge-csv edges.csv --window 25200,28800 --type signal,roundabout --limit 5
# A clip of one junction, real time, with everything the engine thinks drawn on it.
cars record --net net.xml --routes routes.xml --dt .1 --begin 60 --end 75 --junction c \
  --overlay all --out debug.mp4
# Follow one vehicle, in slow motion. The id is a trip id, or a flow vehicle like f4.6.
cars record --net net.xml --routes routes.xml --dt .1 --begin 60 --end 75 --follow f4.6 --speed .5 --out f.mp4
# A still at a chosen time and camera, without making a video.
cars shot --net net.xml --routes routes.xml --dt .1 --at 60,70 --junction c --out c.png
# Everything at once for a gallery, then a physics report.
python3 scripts/intersection_gallery.py --only signal berlin
python3 scripts/physics_qa.py --net net.xml --fcd f.csv --log run.log --out qa/
```

Cameras take `--junction <id>` (zooming to fit its size and approaches), `--follow <trip>`,
or a script; `--metres-per-pixel` overrides the zoom. The HUD is drawn straight on the frames
with a scale bar, so close recordings need no second encode.

Below 0.6 m/pixel the far-away view fades into a close-up one, fully below 0.35: ground,
verges, kerbs, asphalt, and markings derived from each lane's connections.

- Lanes: dashed white between lanes of one direction, solid at the road edges and for the
  last 22 m before a contested junction. Turn arrows come from the lane's connections.
- Stop lines: solid for signals and stop links, shark's teeth for yield links, dashed for
  equal rank, amber teeth for zipper links. Priority links have none.
- Signs on the driver's right: yellow diamond for priority, red triangle for yield, octagon
  for stop. A lane with mixed links shows the priority one, as its driver has right of way.
- Signal heads, one per link, sit just past the stop line with a coloured bar over it. Live
  colour from the TLS state, an arrow for the link direction. Green `g` is paler than `G`.
- Vehicles are oriented rectangles of type length and width. Width is not in the engine; it
  comes from `width` or the SUMO default for the vClass, and only drawing uses it. Windows,
  headlamps, brake lamps below -0.5 m/s² or at a stand, and indicators for a lane change wish
  (`lc_own`), a lateral transition, or the next link's turn within 60 m and through the junction.
- Heading comes from a chord front to rear through lane geometry, following `prev_lane` when
  that lane really meets this one.
- Lane changes are drawn over 3 s with a smoothstep and a little yaw. This is drawing only:
  the engine's car is already on the new lane, and overlays show the drawn position.

Close cameras run in real time: one simulated second per video second, with `--speed` to
change that. Poses are interpolated between steps so dt 1 runs do not jump once a second,
which delays the picture by one step; `--raw-steps` shows steps as they are. Pose history is
keyed by trip, held in a render-only GPU buffer, and fed the last 5 s before the first frame.

`--overlay` takes `speed,leader,braking,state,foes,events` or `all`, drawn on the frame:

- `speed`: km/h for moving vehicles.
- `leader`: cyan from the front bumper to the next vehicle on the planned links within 60 m,
  with the bumper to bumper gap. Red if the gap is negative.
- `braking`: amber band along the planned links, as long as v²/(2·decel) + minGap, turning red
  when the leader is well inside it. The red tick is where an emergency stop ends.
- `state`: `WAIT`, `GO` or `APPR`, the link's state letter and metres to the link, from
  `HAVE_TO_WAIT` and `WILL_PASS`. `IN` on a junction. `wants L/R` is a lane change wish.
- `foes`: for vehicles inside a junction or asked to pass within 40 m: the link's path, magenta
  lines through the crossing point to foes on foe lanes, fainter arcs to foe lane heads asked
  to pass.
- `events`: flashes a red marker for 3 simulated seconds at teleports, collisions, negative
  gaps and overlapping bodies in a junction. Teleports and collisions come from vehicles moved
  to the dummy lane and the engine's counter; the HUD counts them over the clip. Overlaps are
  sampled from what is on screen, so this does not replace `--check-overlaps`.

Overlays read vehicle state back to the CPU each step, which on a big map is a large copy.

`--views file.json` writes many cameras over one simulation run, so a city only warms up once:

```json
{"views":[
  {"junction":"123","out":"a.mp4","title":"A","subtitle":"…"},
  {"junction":"123","overlay":["all"],"out":"a-debug.mp4"},
  {"follow":"t42","mpp":0.09,"out":"f.mp4"},
  {"center":[100,200],"mpp":0.1,"png":"p.png","shots":[28805,28810]}
]}
```

A video appears under its name only when finished. `png` with several `shots` gets the time in
each file name. All cameras share `--begin`, `--end`, dt and speed.

`cars run` gains `--fcd-begin` and `--fcd-bbox x0,y0,x1,y1`, and its FCD gains length, width,
flags, prev_lane and depart_step. A bbox keeps lanes touching it, so leaving it looks like a
gap in the trajectory, which the physics report treats as it does a teleport.

`scripts/intersection_gallery.py` writes small generated junctions and real ones at the Berlin
and Stockholm morning peak. Each place is one traced run, drawn afterwards. It takes vehicles
entering in the warmup hour from that run's edge CSV, cached with the trace, junction lists and
view files under `cache/`. Finished files are skipped; delete one to redo it. City clips warm up
for one hour from 07:00, not from a whole day, so queues can be shorter than in a full run.

`scripts/physics_qa.py` reads a trace (`--trace f.trace`, optionally `--begin`, `--end`) or an FCD
(`--fcd f.csv`), and writes `report.md`, `summary.json`, `distributions.png`, `vehicles.csv`
and a CSV per finding. It reports, it does not judge: thresholds are the graded ones from
`research/truth/11-vehicle-physics.md`. Curvature is the heading change over a 5 m window of
lane polyline, so read a single lane's peak as a place to go and look.

Reproducing what a report found: use a trace, below. City runs do not repeat: two identical
`cars run` commands on Stockholm differed by about 200 vehicles an hour in, so an incident in an FCD
file will not be there in a later clip of the same command. `cars record` still simulates while
drawing: `--overlay events` prints `event <time> <kind> at <x>,<y>` to stderr, frames carry the FCD's
time labels, and `--sim-end` takes the `--end` of a `cars run`, because demand is cut at the end
time and changing it changes the simulation.

## Traces: simulate once, look afterwards

```sh
# Simulate, keeping one window of it. Without --trace nothing is read back and nothing changes.
cars run --net n.xml --routes r.xml --dt 1 --begin 25200 --end 29000 \
  --trace f.trace --trace-begin 28800 --trace-end 29000 [--trace-bbox x0,y0,x1,y1] [--trace-stride 1]
# What happened in it, with places.
python3 scripts/cars_trace.py events f.trace --net n.xml
# Draw that exact moment, in that very run. No routes, no simulation, no simulation buffers.
cars replay --net n.xml --trace f.trace --at 28912 --center 1500,800 --metres-per-pixel .08 --overlay all --out incident.png
# All the camera, overlay and output options of `cars record` and `cars shot`.
cars replay --net n.xml --trace f.trace --begin 28900 --end 28920 --junction c --overlay all --out c.mp4
cars replay --net n.xml --trace f.trace --views views.json
# Check the physics of the same run the pictures show.
python3 scripts/physics_qa.py --net n.xml --trace f.trace --out qa/
```

`--begin` and `--end` of a replay default to the trace's window, and `--net` and `--additional` must
be those of the run: a hash in the file says so. Start a trace about 5 s before you want to look,
so a lane change in progress is drawn right. A bbox keeps lanes touching it, and only their signals:
others are drawn as off. The copy still covers the whole vehicle buffer, so a small bbox saves disk
but not much time. With a stride, a vehicle taken off and put back between two frames is not
flagged; the frame's counters still move.

Replay draws what `cars record` draws, from the same formulas on the CPU, and uploads the poses per
frame. What is different, because a trace does not hold the engine's plan:

- `leader`, `braking`, `foes` and `state` use the link the route asks for on the vehicle's lane, then
  on through links with no choice, ending at a red or yellow signal, or beyond braking distance once
  past the junction. The engine may have picked another link to the same edge, and it plans further,
  so a leader beyond the next choice is not found. A vehicle with no recorded link shows no plan.
- `state` metres are to the end of the lane at this step. `cars record` shows them from the plan made
  before the step moved the vehicle.
- A vehicle is drawn from the step it is inserted. `cars record` draws it one step later.
- Waiting time is in whole seconds, and saturates at 255.

An event in a frame labelled t flashes as the picture moves on from t, because pictures run one step
behind, and the vehicle is already gone from that frame.

Cost, RX 7900 XT, no other GPU work. Stockholm 07:00 to 07:30 is 3.00 s without a trace and 3.24 s
tracing its last 600 steps, full net, about 12 300 vehicles: 0.4 ms a frame, 152 MB, 20.7 bytes a
vehicle step. Charlottenburg 07:00 to 09:00 is 9.6 s without and 12.2 s tracing all 7200 steps: tracing
every step gives up batching several steps in a submission, so a small net pays relatively more. A
600 s bbox window on it costs 0.2 s. Stride 5 on Stockholm costs 0.04 s and 33 MB.

A trace file is `CARSTRC1`, a u32 byte count and a JSON header (`net_hash`, `dt`, `sim_begin`,
`stride`, window, `bbox`, `time_to_teleport`, `dummy_lane`, `vtypes`, `tls` with each signal's phase
state strings), space padded to 4 bytes. Then frames, nothing else, so a run cut short still reads
up to its last whole frame. All little endian:

| Frame part | Contents |
|---|---|
| head, 32 bytes | `TRFR`, step, records, name bytes, teleports, collisions, running (u32), mean speed (f32). The last four are for the whole net. A frame after `step` steps is labelled `sim_begin + (step-1)*dt`, as FCD. |
| names | Trips and lanes seen for the first time: u32 number, top bit set for a lane; u32 length; UTF-8; padded to 4. |
| phases | u16 per signal in `tls`, padded to 4. |
| records, 20 bytes each | below |

| Field | Bits |
|---|---|
| word 0 | trip number (24), flags (8): 1 lane changed, 2 teleport, 4 collision, 8 will pass, 16 have to wait, 32 wants left, 64 wants right, 128 on junction |
| word 1 | lane (24), vehicle type (8) |
| word 2 | previous lane (24, all ones for none), waiting seconds (8) |
| word 3 | position in 1/256 m (24), next link as an index into the lane's links (6, 63 for none) |
| word 4 | acceleration in 1/256 m/s² (i16), speed in 1/512 m/s (u16) |

A vehicle teleported or collided on this step keeps its last lane and position, with its flag and no
speed, for one frame. Teleport or collision comes from which engine counter moved; when both did in
one frame, from whether it had waited up to `time_to_teleport`. A collision on the last edge of a
route counts as an arrival, and only the counter sees it.

The GPU thread only asks for finished state to be copied between submissions, to staging buffers of
its own, and the next wait for the simulation delivers them. Reading them and writing the file happen
on the writer's thread.

## Coordinated junctions

`--cj <ids|all|box:x0,y0,x1,y1>` runs those junctions with the signal-free coordinator (`cars av --help` lists the
fault flags, which work here too). Overlays `grants` (firm slots, speed advice, lost grants, the slot chart and, for
`--cj-mode signal`, stop bars from the coordinator's own phase), `paths` (planned paths, wide where a crossing foe also
needs the road) and `channel` (the coordinator and who talks to it). `scripts/d8/film.py` makes the clips.
