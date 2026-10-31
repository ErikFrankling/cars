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
CPU libx264 uses three threads, CRF 20, medium preset, yuv420p; hardware encoders
are never used. The `.ass` sidecar is retained for editing. The silent intermediate
is deleted after a successful libass burn-in and retained on failure.

Validated on RX 7900 XT with ring and Bologna captures at 1280x720. Large-city
300k-vehicle performance has not been benchmarked. Run only one GPU job at a time.
