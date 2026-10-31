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
default. `--color speed|type|wait` controls the palette. Type mode treats ACC/CACC
models as automated vehicles. Waiting color reaches red after 60 seconds.

The warmup runs without rendering. Each frame advances up to `steps-per-frame`
steps, stopping at the end bound (rounded up to a simulation step). Video duration
is `ceil((end_step - begin_step) / steps_per_frame) / fps`. HUD speed averages
nonremoved replica-0 vehicles; clock is simulation time modulo 24 hours.

Rendering uses cumulative polyline lengths and a GPU binary search to map lane
position to geometry, respecting differences between lane and geometric lengths.
Static lane-width segment quads fade at subpixel scales, with subdued internal
lanes and brighter fast roads. Vehicle lengths come from their type; width is
1.8 m. Vehicles become additive soft dots as scale increases. Signals are visible
below 2 metres per pixel and use the live TLS phase. 4x MSAA resolves into an HDR
rgba16float target before a small highlight halo and exponential tone map.
Only RGBA pixels and two reduced statistics are read back; vehicle state stays
on GPU. Replica 0 is rendered. Renderer memory is linear in geometry and capacity.

Output dimensions must be even and at most 1920 on either axis. GPU submissions
use `Sim::run`'s short adaptive batches; rendering is a separate submission.
CPU libx264 uses two threads, CRF 20, veryfast preset, yuv420p; hardware encoders
are never used. The `.ass` sidecar is retained for editing. The silent intermediate
is deleted after a successful libass burn-in and retained on failure.

Validated on RX 7900 XT with ring and Bologna captures at 1280x720. Large-city
300k-vehicle performance has not been benchmarked. Run only one GPU job at a time.

For large demand files, `--capacity` bounds the active vehicle buffers (default 0
allocates for every trip). `--time-to-teleport` and `--ignore-junction-blocker`
accept the same settings as `cars run`, so recordings can use matching dynamics.

Intersection inspection (all GPU commands must hold the shared lock):

```sh
RUSTC_WRAPPER= nix develop --command cargo build --release
flock /tmp/cars-gpu.lock target/release/cars record --net net.xml --routes routes.xml \
  --dt .1 --begin 60 --end 72 --junction c --metres-per-pixel .08 \
  --realtime --out intersection.mp4
flock /tmp/cars-gpu.lock target/release/cars record --net net.xml --routes routes.xml \
  --dt .1 --begin 66 --junction c --shot --out intersection.png
flock /tmp/cars-gpu.lock target/release/cars record --net net.xml --routes routes.xml \
  --dt .1 --begin 60 --end 72 --follow f0.0 --realtime \
  --overlay speed,leader,braking,state,foes,events --out debug.mp4
python3 scripts/junctions.py --net net.xml --edge-csv edges.csv --type signal
python3 scripts/intersection_gallery.py
python3 scripts/intersection_gallery.py --only signal berlin
flock /tmp/cars-gpu.lock target/release/cars run --net net.xml --routes routes.xml \
  --dt .1 --end 90 --fcd trajectories.csv --fcd-interval .1
python3 scripts/physics_qa.py --net net.xml --fcd trajectories.csv --out qa
```

Run these inside `nix develop` for Python, ffmpeg, SUMO and Vulkan libraries.
`record --shot` is the still-image command: it writes one PNG directly from the
renderer, with no video encode. `--begin` is the snapshot time. `--follow` takes
the demand trip id; an absent or arrived vehicle falls back to the scripted,
junction or fit camera. `--junction` uses SUMO junction ids and network coordinates.
Default close-up scale is .12 m/pixel; an explicit scale controls both camera modes.
At close scale the default speed palette becomes a stable per-trip palette.
Vehicles use type length and a 1.8 m width (width is not represented by the engine).
Windscreens, deceleration brake lights and directional lane/turn indicators appear
below .3 m/pixel. Three-second lateral easing is rendering history keyed by trip;
no vehicle buffers or dynamics are modified. Headings use the front-to-rear chord,
including the previous lane at junction connectors.

`--realtime` writes exactly one simulation second per video second, repeating a
simulation snapshot between dt boundaries. Use dt .1 for ten motion updates per
second; output can still be 30 fps. Lane-change easing is sampled at those same
boundaries. Camera JSON `frame` keyframes retain the historical dt*steps-per-frame
timing; use `time` keyframes with realtime recordings.

Overlay colours: cyan links the current-lane leader; amber shows the stopping
range v²/(2*decel), clipped to the lane; white digits are km/h. State bars are
orange for HAVE_TO_WAIT, green for WILL_PASS and blue otherwise. Purple bent
connections show static request foes. Red crosses last one simulated second for
observed dummy-lane teleports or sampled negative same-lane gaps. Overlays read
vehicle snapshots back to the CPU and are slower on large maps. They show raw
physics positions, so a lane-changing car can differ from its eased drawing.
Event detection is sampled and does not replace engine collision counters.
Yield triangles and yellow priority markers are schematic approach markings;
signals are separate live-colour heads for each link, stacked back from the line.
Junction polygon fans can overfill a concave polygon; the renderer is diagnostic,
not a road-survey reconstruction.

The gallery creates all seven small fixtures, plus Berlin and Stockholm cameras
for each available signal/priority/roundabout/zipper/ramp category. It chooses the
busiest departure quarter-hour and warms the city for 300 s; this is a bounded
warmup, not an all-day equilibrium replay. Junction ranking uses an existing
`cars.edges.csv` when available and incoming lane count otherwise. It records
12-second 1920x1080 clips and extracts three PNGs from each. Completed clips and
PNGs are skipped, videos are atomically renamed after encoding. Metadata is in
each camera.json. Unavailable junction categories produce no clip.

Physics QA writes report.md, summary.json, per-vehicle distributions in
vehicles.csv, attributed events.csv and distributions.png. Negative gaps and
rectangle overlaps are sampled observations, not unique incidents. Turn
curvature from short polyline segments can give enormous estimates; inspect
those lanes before interpreting them as actual physical acceleration. Teleport
and missing-interval exclusion is heuristic; prefer dense FCD and compare the
engine's counters. Never infer a clean full run from a short window.
