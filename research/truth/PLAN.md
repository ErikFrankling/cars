# Plan: a simulation that is actually useful

From Erik: "Don't stop until you are satisfied with us having a simulation that's actually useful." Self-driving work stays paused until then (VALIDATION-GATE.md).

The test is his: "In the same simulation, with the same settings and everything, can you get the different kinds of intersections and network-level traffic and a diverse set of trackers to all align real-world captured data with simulated data? If we have that, we have an accurate enough simulation that it's actually interesting to see what every model does." Throughput alone proves nothing, because it can look right for many wrong reasons.

## Track A: fix what we have
Go over the simulations and correct them. Physics within real limits and close to the average car (`data-hunt/19-physical-realism.md`). Lane changing and merging like real people (`18-how-humans-merge.md`). Maps and network building, signal programs, missing traffic such as buses and pedestrians, from `data-hunt/09`, `10`, `11`, `16`. Simulator limitations that block realism (`data-hunt/20-simulator-limits.md`).

## Track B: start from data
From large-scale real data to a model. Should the driver be a trained network, rules or a hybrid? See how everyone else does it (`data-hunt/21-learned-drivers.md`), then prototype and compare on the benchmark. Real all-vehicle days: Jinan (`data-hunt/02-jinan.md`). Every data source in `data-hunt/`.

## Track C: benchmark and hill climb
1. **Benchmark:** one fixed configuration, one command, one scorecard. Microscopic (car following, lane change, physics distributions), per junction type (signal, priority, roundabout, ramp, lane drop, zipper), corridor (queues, travel time), network (hourly flow, speed by hour, where and when jams form, network curve, trips). Real data only, split into tuning data and held-out data never looked at. History per commit, so progress shows as a climbing curve. Designed so a score can't be gamed: `data-hunt/22-what-true-to-life-means.md`.
2. **Debugging tools:** explain any car at any tick (which limit bound its speed, who blocked it, why it didn't change lane), any metre of road (real against simulated time-space diagrams), any jam back to its root cause, and any sensor's gap between real and simulated.
3. **Loop:** run the benchmark, take the largest gap, find out why with the tools, fix the cause rather than tune around it, re-run everything, keep only what improves without breaking anything else. Record each round. Never tune on held-out data.

## Stop when
Every level of the benchmark is within the real noise floor, or as close as the evidence says is possible, on held-out data, with a single configuration. Anything that can't get there is explained with its cause. Then the final report, then self-driving models.

## Queue
Launch these as running agents finish, because the PC is limited to about 4 cores and little free memory:
- [ ] Benchmark builder (needs reports 14, 15, 17, 22)
- [ ] Debugging tools builder
- [ ] Junction-type targets from open data (pNEUMA, SinD, OpenDD, CitySim, others)
- [ ] Learned-driver prototype on real tracks (after report 21)
- [ ] Network-level calibration methods with ML and differentiable simulation
- [ ] Merge physics and human drivers into main once the I-80 kernel spin is resolved
- [ ] Hill-climb loop (after the benchmark and tools exist)
- [ ] Rewrite the report around the benchmark, only at the end

## Where to test
From `data-hunt/12-where-everything-lines-up.md`: no place has everything. First gate: **Berlin, Wednesday 15 May 2019**. It has open dated flows and speeds through the day, probe speeds from the same months once Erik fills in the HERE form, and a ready demand (MATSim v6.4, 4.42 M trips). Note that MATSim v6.4 was fitted to the same sensors: only 24 of 266 cross-sections are clean, so speeds are the blind test, and report 12 explains the rest. Second, stricter: **Madrid, autumn 2021**, with survey demand independent of its loops. Hamburg's open per-second signals (797 junctions, kept about nine days) test how much results depend on estimated signal timing. Stockholm ranks 9th of 10 today: no open dated counts, speeds or measured OD. It comes back when the data requests in `05-sweden-kth.md` deliver.

## Order of work
Follow the recipe in `data-hunt/15-how-to-match-reality.md`, section "The recipe". District first (20-50 km²), then corridor, district, city. Freeze the test and compute the real-against-real noise floor before fitting anything. Fix the map at 50% demand with teleports off before touching demand. Check capacity per road class. Build demand from independent data. Assign routes until stable. Only then correct OD gently. Each step has an exit test, and later steps never hide faults in earlier ones. **Never scale demand to pass.**
