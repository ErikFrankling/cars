# Working in this repo

A GPU reimplementation of SUMO's microscopic traffic simulation, in Rust and WGSL. Goal: flows statistically comparable to SUMO at far higher speed.

The GPU also drives Erik's desktop. Scale every experiment from small to big, keep GPU submissions short (Sim::run does this), keep 3 GB of VRAM spare, run one GPU job at a time, leave nothing running. CPU jobs over about 10 minutes go to the homelab with `heavy`.

- `crates/cars-core/src/shaders/`: `common.wgsl` structs and car following, `step.wgsl` the step kernels, `lc.wgsl` lane changing, `control.wgsl`, `sort.wgsl`, `render.wgsl`. Every struct has a `#[repr(C)]` twin in `world.rs`.
- `scripts/golden.py` compares trajectories with SUMO. `scripts/junction_tests.py` compares junctions route by route. `scripts/cmp_thesis.py`, `cmp_edges.py`, `cmp_lanes.py` compare runs. `target/release/sweep` runs a thesis sweep as replicas in one GPU world; thesis SUMO results are in `/home/erikf/projects/personal/thesis-src/bachelor/results/processed/metrics.csv`.
- `research/sumo-0*.md` are the implementation specs, transcribed from SUMO 1.28. The SUMO source is at `/home/erikf/projects/personal/thesis-src/sumo/src`.

- `shaders/av_junction.wgsl` and `coord.rs` are the signal-free coordinator (D8, research/truth/09). `cars av` runs it and prints JSON; `scripts/d8/` holds demand, sweeps, plots and clips; `--cj` works on `cars record` too. `--cj-plan off|profile|stable|full|cubic|dr|route` switches the planned approach (research/truth/09d, 09e); `route` is the design and adds storage credit across junctions, `off` stays bit-identical to the D8 baseline. `--cj-plan-peak` caps peak lateral acceleration. `scripts/d8/brake.py` is the braking metric, `plan_runs.py` the sweeps, `stockholm2.py` the Stockholm district on the corrected demand; on the homelab run them through `heavy --big -- scripts/d8/worker.sh ...`, which brings Mesa's CPU Vulkan driver. Set `CARS_ADAPTER=llvmpipe` for debugging without the GPU lock, `CARS_SHADER_DIR` to load shaders without rebuilding.
- `cars run --trace` writes trajectories and `cars replay` draws them with no simulation, so an incident stays in the run that had it. `cars record`, `cars shot` and `cars junctions` also look at intersections up close. `scripts/intersection_gallery.py`, `scripts/physics_qa.py` and `scripts/cars_trace.py` build on them; see `crates/cars-cli/RECORDING.md`.

`CARS_ADAPTER=llvmpipe` runs kernels on the CPU, for what might hang and for small scenes when the GPU queue is long. It forces 128-bit code: LLVM 21's 256-bit code miscompiled `lc_ahead_load` silently. A cut of a real net with `randomTrips.py` runs in seconds this way. Over seeds: lockup is chaotic, one seed says nothing.

No GPU kernel may use function-local arrays outside `lc_best`. Comments stay sparse.
