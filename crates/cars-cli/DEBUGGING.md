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
| Can these routes be driven at all, lane by lane? | `cars lanes --net f.trace.net.json --routes r.gz --edge-csv edges.csv` |
| A seed of a city, small enough for llvmpipe | `cars cut --net n.xml --routes r.gz --center x,y --begin T0 --end T1 --out d/` |

## The limits `cars why` names

Each tick, `decided by` is the limit that set the car's speed, and `planned by` is what the plan said when something later in the step changed it. All values are next-step speeds in m/s; a limit that did not speak is left out.

| Kind | Meaning |
|---|---|
| `accel` | what the engine gives from this speed |
| `free` | speed limit of this lane times the driver's factor |
| `next_limit`, `curve` | slowing for a lower limit on the next road, or for a junction lane |
| `leader`, `leader_ahead`, `tail` | a car on this lane, on a lane ahead, or the tail of one hanging onto a lane ahead |
| `signal` | stopping at red or yellow |
| `yield` | stopping for a link it may not take yet; `link closed` says why and which foe, or `arbiter held it` gives the physical arbiter's reason: a zone taken by a foe lane, the onward zone of a stub, no room past the box, or a bid lost to a zone foe |
| `exit_full` | no room past the junction, and it names that lane |
| `junction` | a car inside the junction |
| `lane_end` | the route needs another lane; `lane change` says who blocks it |
| `arrival`, `zipper`, `coordinator` | its destination, a zipper merge, `--cj` |
| `abreast` | two cars side by side each want the other's lane: this one falls behind |
| `missed_turn` | it could not get its lane and is waiting for another way |
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

The buffer is at binding 63, above anything the main layout will reach. Probes only write it. To check after a kernel change: run a small scene with `--trace a.trace`, then `--trace b.trace --why`, and `cmp a.trace b.trace`. Plain runs themselves differ now and then on llvmpipe (about one in four on the small scene in `scripts/test_debug_tools.py`), so repeat the plain run: one of them must be the same bytes. On llvmpipe `--why` runs at 128-bit vectors, because its 256-bit code miscompiles kernels this size and the run comes out different. Not yet run on the real GPU: the lock was taken throughout.

## `.why` file

`CARSWHY1`, a u32 byte count and JSON (`record`, `kinds`), then frames parallel to the trace's: `WHYF`, step, count, 0 (u32 each), then that many records, in the same order as that frame's trace records. A vehicle with no reason this tick (teleported, or just inserted) is all zero. The record is `WhyRecord` in `why.rs`, read by `scripts/dbg/run.py`.

| Field | Meaning |
|---|---|
| `decider`, `plan`, `item`, `closed` | u8: kinds as in `KINDS`, which plan item it came from (255 none), `CLOSED` reason |
| `blame` | u32: a trip; top bit set, a lane; next bit set, a link; all ones, nothing |
| `blame_gap`, `v_safe` | metres to what it blames, the speed the plan allowed |
| `leader`, `leader_gap`, `leader_speed` | nearest vehicle ahead in its plan |
| `first_link`, `first_dist` | next link and metres to it |
| `foe_trip`, `foe_link`, `foe_gap` | the foe that closed the link, its link, seconds it arrives after this car would. With `closed` 0 and no next link, `foe_link` is the edge its route asks for; with `closed` 0 and a code in its top 3 bits, the arbiter held it (1 zone taken, 2 onward zone, 3 no room past it, 4 bid lost) and the low bits are the lane |
| `lc_right`, `lc_left`, `lc_chosen` | LCA flags of each side, and the side taken |
| `*_gap`, `*_leader`, `*_follower` | gaps and cars on each side |
| `limits` | u16 × 22: value of each kind, m/s × 128, 0xffff for silent |

## Reference data for `cars compare`

`--ref-format site_hours --ref out/site_hours.csv` reads what `scripts/reference_day.py --out out` wrote: real and simulated per matched site and hour, with the spread of normal days, so no `--sim`. This is the route for the gate's measured days in `cars-data/datasets/reference-days/`.

Otherwise `--ref` is a long CSV: `sensor,edge,time,flow_vph[,speed_kmh]`, with `time` the seconds from midnight of an hour's start, or `-1` for a whole-day figure, and `--sim` is `cars run --edge-csv` output. `--ref-format stockholm` reads `truth/stockholm/factorial/count_clean.csv`, which is annual estimates and not a measured day. `--scale` scales simulated flows when demand was thinned.

## Real tracks

`cars tsd --real` and `cars dist --b real:NAME` read report 05's TGSIM (`I395`, `I90stat`, `I90mov`, `I294L1`, `I294L2`, `Foggy`) and DRaT (`drat`), or a CSV of `time,track,pos,speed[,lane]`. The first read takes minutes; a cache stays in `~/.cache/cars-dbg`. Report 05 lists each dataset's flaws. `dist` reads real acceleration over one second, so it compares with a dt 1 run on equal terms.

## A worked case: Stockholm's stuck seeds

Net `truth/stockholm/factorial/n7_ramps.net.xml`, demand `v2_c4.rou.gz`, main's Krauss driver. Everything is under `cars-data/truth/dbg/`. A city needs the GPU; when the lock is taken, cut a scene and run it on llvmpipe. A cut shows mechanisms, not city totals.

```sh
# 1. Where did the city get stuck? The full-day edge CSV has teleports per road: the top three of 149 roads were 804598780, 26992780#1 and 804669067.
# 2. Cut the place at the time it happens, run it with reasons and teleports off.
cars cut --net n7_ramps.net.xml --routes v2_c4.rou.gz --center 19348,21160 --radius 900 --begin 21600 --end 23400 --out fork/
cars run --net fork/net.xml --routes fork/routes.xml --dt 1 --end 1800 --time-to-teleport 0 --ignore-junction-blocker 20 --trace fork/f.trace --why
# 3. The seed, why it stopped, and how it looks.
cars jam --trace fork/f.trace --seeds --stride 5 --out fork/jam
cars why --trace fork/f.trace --car v36 --at 500
cars replay --net fork/net.xml --trace fork/f.trace --at 499,500 --center 19326,21149 --metres-per-pixel .1 --overlay all --out fork/v36.png
# 4. How much of the city is this? Walk every route lane by lane.
cars lanes --net city.net.json --routes v2_c4.rou.gz --edge-csv v2_day2/edges.csv --change-seconds 1
```

What it found, of 2,449 teleports in the full day, 1,359 of them counted as wrong lane by the engine:

| Road | Teleports | Mechanism | How the tools showed it |
|---|---:|---|---|
| `804598780` | 470 | Route needs lane 0. The ramp feeds lanes 1-3, lane 0 opens on a 15.8 m road crossed inside one tick on junction lanes, then a solid line closes it | `decided by: lane_end`, `may change to [1, 2, 3]`, `impossible`, and no right wish at all |
| `26992780#1` | 275 | 3.5 m two-lane road. Two cars side by side each want the other's lane, and each body blocks the other | a ring of 2 cars, `blocked_by_leader` at -6 m |
| `804669067` | 186 | Lanes 0-2 and 3-4 split by a solid line on a 36 m road. Entering on lane 0, the route needs 3 or 4. `cars lanes` finds 185 such trips against 186 teleports | same `impossible` line; held 297 cars in 30 min of the cut |
| `43054916`, `161451894` | 117 | Opposite 0.2 m stubs carrying a U-turn: one car's tail blocks the junction path of a car whose exit it waits for | a ring through both stubs, picture in `dbg/dist1/lock-1300.0.png` |

Those four places hold 43% of the day's teleports. Edges under 7.5 m are 6.1% of the net and took 31.8%. 1.01% of trips turn around through a pair of edges under 1 m. Demand comes from an edge-level router that does not look at lane markings, so these are map and demand faults, not driver faults. `cars lanes` at `--change-seconds 1` flags 52 places holding 47% of teleports, but most of them have none: without a solid line a car can stop and change. Read it as a list of places to look at.
