# Debugging a run

One loop an agent can run alone: trace a run with reasons, find the seed, explain the car, look at the road, compare with reality. Every tool prints text and writes a PNG you can open. Add `--json` for data where listed, `--out DIR` to choose the folder, and `--help` for every option.

```sh
# Simulate once, keeping a window with reasons. Off without --why, and then the kernels are byte for byte the normal ones.
flock /tmp/cars-gpu.lock cars run --net n.xml --routes r.gz --dt 1 --begin 21600 --end 25200 --time-to-teleport 0 \
  --trace f.trace --trace-begin 21600 --why
```

This writes `f.trace` (as in RECORDING.md), `f.trace.why` (136 bytes per vehicle per frame) and `f.trace.net.json`. `--trace-bbox` and `--trace-stride` cut the size. Without `--why` the tools still run on a plain trace, with what can be inferred: `cars jam` follows same-lane leaders only, and `cars why` shows state but no reasons.

## The tools

| Question | Command |
|---|---|
| Why did this car do that? | `cars why --trace f.trace --car 12345 --at 22000` |
| Its story over time, as table and chart | `cars why --trace f.trace --car 12345 --begin 21900 --end 22100` |
| What does this road do, metre by metre? | `cars tsd --trace f.trace --route E1,E2 --begin 21900 --end 22500` |
| Same, beside real tracks | `cars tsd --trace f.trace --edge E1 --real I395` |
| Who is this car waiting for, and what started it? | `cars jam --trace f.trace --car 12345 --at 22000` |
| Same, from a congested road | `cars jam --trace f.trace --edge E1 --at 22000` |
| Which seeds held up the city? | `cars jam --trace f.trace --seeds --stride 10` |
| Real against simulated | `cars compare --sim edges.csv --ref ref.csv --net n.xml` |
| How does this junction behave? | `cars junction --trace f.trace --junction J1` |
| How do junctions of a type compare? | `cars junction --trace f.trace --type traffic_light --top 12` |
| How far apart are two runs, or a run and reality? | `cars dist --a f.trace --b real:I395` |

## The limits `cars why` names

Each tick, `decided by` is the limit that set the car's speed, and `planned by` is what the plan said when something later in the step changed it. All values are next-step speeds in m/s; a limit that did not speak is left out.

| Kind | Meaning |
|---|---|
| `accel` | what the engine gives from this speed |
| `free` | speed limit of this lane times the driver's factor |
| `next_limit`, `curve` | slowing for a lower limit on the next road, or for a junction lane |
| `leader`, `leader_ahead`, `tail` | a car on this lane, on a lane ahead, or the tail of one hanging onto a lane ahead |
| `signal` | stopping at red or yellow |
| `yield` | stopping for a link it may not take yet; `link closed` says why and which foe |
| `exit_full` | no room past the junction, and it names that lane |
| `junction` | a car inside the junction |
| `lane_end` | the route needs another lane; `lane change` says who blocks it |
| `arrival`, `zipper`, `coordinator` | its destination, a zipper merge, `--cj` |
| `lane_change` | lane changing asked for this speed (it blocks, or it helps someone) |
| `dawdle` | a value only, never the decider: the speed after driver noise took some off what the limit allowed |
| `brake_limit` | wanted to slow more than the brakes allow; `planned by` is the reason it wanted to |
| `committed` | past the point of stopping for a minor link |
| `power` | the final speed step capped it below the plan |

A tick's reasons, gaps and leader are from the plan at the start of that tick, and position, speed and acceleration are the result at its end. So a leader can show as already on the next lane, and a gap as what the car saw before moving.

`lane change right: strategic urgent blocked_by_follower` is the wish and what stops it, with the gaps and cars on that side. `lost the space to another changer` means it chose to go and another car won the claim.

## How the reasons are exact, and stay out of the way

`crates/cars-core/src/why.rs` holds probes: text anchors in `step.wgsl` and `lc.wgsl` and the call to place at each. They are patched into the shader source only for `Sim::with_why`. A normal run compiles the same bytes as before, so there is no cost and no way for it to differ. The kernels carry no debugging code, so merges never conflict over it.

A probe whose anchor has gone stops `cars run --why` at start up and names the line; `cargo test -p cars-core why` checks them all. New limits added by a branch need one probe each: a line in `PROBES`, and a `K_*` in `why.wgsl`.

The buffer is at binding 63, above anything the main layout will reach. Probes only write it. To check after a kernel change: run a small scene with `--trace a.trace`, then `--trace b.trace --why`, and `cmp a.trace b.trace`. They must be the same bytes. On llvmpipe `--why` runs at 128-bit vectors, because its 256-bit code miscompiles kernels this size and the run comes out different.

## `.why` file

`CARSWHY1`, a u32 byte count and JSON (`record`, `kinds`), then frames parallel to the trace's: `WHYF`, step, count, 0 (u32 each), then that many records, in the same order as that frame's trace records. A vehicle with no reason this tick (teleported, or just inserted) is all zero. The record is `WhyRecord` in `why.rs`, read by `scripts/dbg/run.py`.

| Field | Meaning |
|---|---|
| `decider`, `plan`, `item`, `closed` | u8: kinds as in `KINDS`, which plan item it came from (255 none), `CLOSED` reason |
| `blame` | u32: a trip; top bit set, a lane; next bit set, a link; all ones, nothing |
| `blame_gap`, `v_safe` | metres to what it blames, the speed the plan allowed |
| `leader`, `leader_gap`, `leader_speed` | nearest vehicle ahead in its plan |
| `first_link`, `first_dist` | next link and metres to it |
| `foe_trip`, `foe_link`, `foe_gap` | the foe that closed the link, its link, seconds it arrives after this car would. With `closed` 0 and no next link, `foe_link` is the edge its route asks for |
| `lc_right`, `lc_left`, `lc_chosen` | LCA flags of each side, and the side taken |
| `*_gap`, `*_leader`, `*_follower` | gaps and cars on each side |
| `limits` | u16 × 22: value of each kind, m/s × 128, 0xffff for silent |

## Reference data for `cars compare`

`--ref-format site_hours --ref out/site_hours.csv` reads what `scripts/reference_day.py --out out` wrote: real and simulated per matched site and hour, with the spread of normal days, so no `--sim`. This is the route for the gate's measured days in `cars-data/datasets/reference-days/`.

Otherwise `--ref` is a long CSV: `sensor,edge,time,flow_vph[,speed_kmh]`, with `time` the seconds from midnight of an hour's start, or `-1` for a whole-day figure, and `--sim` is `cars run --edge-csv` output. `--ref-format stockholm` reads `truth/stockholm/factorial/count_clean.csv`, which is annual estimates and not a measured day. `--scale` scales simulated flows when demand was thinned.

## Real tracks

`cars tsd --real` and `cars dist --b real:NAME` read report 05's TGSIM (`I395`, `I90stat`, `I90mov`, `I294L1`, `I294L2`, `Foggy`) and DRaT (`drat`), or a CSV of `time,track,pos,speed[,lane]`. The first read takes minutes; a cache stays in `~/.cache/cars-dbg`. Report 05 lists each dataset's flaws. `dist` reads real acceleration over one second, so it compares with a dt 1 run on equal terms.
