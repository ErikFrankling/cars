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
and Stockholm morning peak. It takes vehicles entering in the warmup hour from its own edge CSV,
cached with the junction lists and view files under `cache/`. Finished files are skipped;
delete one to redo it. City clips warm up for one hour from 07:00, not from a whole day, so
queues can be shorter than in a full run.

`scripts/physics_qa.py` writes `report.md`, `summary.json`, `distributions.png`, `vehicles.csv`
and a CSV per finding. It reports, it does not judge: thresholds are the graded ones from
`research/truth/11-vehicle-physics.md`. Curvature is the heading change over a 5 m window of
lane polyline, so read a single lane's peak as a place to go and look.

Reproducing what a report found: `--overlay events` prints `event <time> <kind> at <x>,<y>` to
stderr, so a debug clip tells where to look in itself. Frames carry the FCD's time labels, and
`--sim-end` takes the `--end` of a `cars run`, because demand is cut at the end time and changing it
changes the simulation. Small nets then replay the same run. City runs do not repeat: two identical
`cars run` commands on Stockholm differed by about 200 vehicles an hour in, so an incident in an FCD
file will not be there in a later clip of the same command. Record with `--overlay events` and read
that run's log instead.

## Coordinated junctions

`--cj <ids|all|box:x0,y0,x1,y1>` runs those junctions with the signal-free coordinator (`cars av --help` lists the
fault flags, which work here too). Overlays `grants` (firm slots, speed advice, lost grants, the slot chart and, for
`--cj-mode signal`, stop bars from the coordinator's own phase), `paths` (planned paths, wide where a crossing foe also
needs the road) and `channel` (the coordinator and who talks to it). `scripts/d8/film.py` makes the clips.
