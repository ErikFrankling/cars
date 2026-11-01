# Working in this repo

A GPU reimplementation of SUMO's microscopic traffic simulation, in Rust and WGSL. Goal: flows statistically comparable to SUMO at far higher speed.

The GPU also drives Erik's desktop. Scale every experiment from small to big, keep GPU submissions short (Sim::run does this), keep 3 GB of VRAM spare, run one GPU job at a time, leave nothing running. CPU jobs over about 10 minutes go to the homelab with `heavy`.

- `crates/cars-core/src/shaders/`: `common.wgsl` structs and car following, `step.wgsl` the step kernels, `lc.wgsl` lane changing, `control.wgsl`, `sort.wgsl`, `render.wgsl`. Every struct has a `#[repr(C)]` twin in `world.rs`.
- `scripts/golden.py` compares trajectories with SUMO. `scripts/junction_tests.py` compares junctions route by route. `scripts/cmp_thesis.py`, `cmp_edges.py`, `cmp_lanes.py` compare runs. `target/release/sweep` runs a thesis sweep as replicas in one GPU world; thesis SUMO results are in `/home/erikf/projects/personal/thesis-src/bachelor/results/processed/metrics.csv`.
- `research/sumo-0*.md` are the implementation specs, transcribed from SUMO 1.28. The SUMO source is at `/home/erikf/projects/personal/thesis-src/sumo/src`.

- `cars record`, `cars shot` and `cars junctions` look at intersections up close, `scripts/intersection_gallery.py` and `scripts/physics_qa.py` build on them; see `crates/cars-cli/RECORDING.md`.

No GPU kernel may use function-local arrays outside `lc_best`. Comments stay sparse.
