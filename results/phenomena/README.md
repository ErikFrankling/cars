# Traffic phenomena: fresh paired measurements

Reproduce inside `nix develop`: `cargo build --release`, `python scripts/phenomena_suite.py`, `python scripts/phenomena_videos.py`, `python scripts/phenomena_report.py`, then `python scripts/phenomena_accept.py`. Seeds 42, 43, 44. The phantom and one-driver IDM rings are deterministic across seeds; those repeats do not represent driver uncertainty. Stochastic cases use independent seeds in the two engines; the lane-drop case also uses IDM. No old measurements are used.

Headline values below are seed 42; seed 43 and 44 results have separate summaries and figures. Yes denotes the measured criterion below, not full simulator equivalence. Spillback blocked time uses 30 s bins with >8 vehicles in the short link and upstream speed <2 m/s. Gridlock requires late speed <0.5 m/s with teleport disabled; keep-clear can delay failure without preventing it under extreme overload. The lane drop uses IDM with accel 0.3 m/s² and decel 1.5 m/s² to expose breakdown and discharge loss. Brake-wave uses a single 20 s red pulse. Headway plots show the first green only; saturation uses median headway at queue positions 5–15. FD uses the last 300 s at each fixed density, with all vehicles admitted, through 120 veh/km. SUMO edge occupancy can double-count a vehicle spanning an edge boundary, so Edie accumulation can exceed the physical population. Capacity-drop preflow is the peak 90 s mean in the preceding 300 s; discharge is the following 600 s after a 60 s transition exclusion, truncated at the run end.

| Scenario | SUMO demonstrated; evidence | cars demonstrated; evidence |
|---|---|---|
| phantom_jam | Yes; stopped 53.3%, SD 2.73 m/s, wave -7.2 km/h | Yes; stopped 51.0%, SD 2.76 m/s, wave -7.2 km/h |
| one_av | Yes; SD human 2.73, smooth 0.0005 m/s | Yes; SD human 2.76, smooth 0.0232 m/s |
| brake_wave | Yes; 15 stopped trajectories, median minimum 3.45 m/s | Yes; 15 stopped trajectories, median minimum 3.53 m/s |
| capacity_drop | Yes; queue at 900 s; pre 3920, discharge 1758 veh/h; min speed 2.07 m/s (drop 55.2%) | Yes; queue at 930 s; pre 4040, discharge 2916 veh/h; min speed 4.70 m/s (drop 27.8%) |
| freeway_fd | Yes; peak 2757 veh/h at 30 veh/km; dense 352 veh/h, 0.81 m/s | Yes; peak 2737 veh/h at 30 veh/km; dense 325 veh/h, 0.75 m/s |
| signal_discharge | Yes; headway 1.20 s, saturation 3000 veh/h | Yes; headway 1.20 s, saturation 3000 veh/h |
| onramp_merge | Yes; ramp 19.93 to 0.00 m/s; mainline 33.27 to 27.85 m/s | Yes; ramp 19.87 to 0.00 m/s; mainline 33.21 to 27.78 m/s |
| spillback | Yes; blocked proxy 1680 s, peak link 13.0 veh, side exits 27 | Yes; blocked proxy 1680 s, peak link 13.0 veh, side exits 27 |
| gridlock | Yes; late speed off/on 0.00/0.02 m/s; arrivals 153/309 | Yes; late speed off/on 0.00/0.02 m/s; arrivals 144/322 |
| mfd | Yes; peak 224 veh, final/peak 0.20, mean speed 6.36 m/s | Yes; peak 219 veh, final/peak 0.20, mean speed 6.19 m/s |
| thesis_ring | Yes; mean speed 12.379 m/s, peak 219 veh | Yes; mean speed 12.364 m/s, peak 200 veh |
| bologna_rush | Yes; mean speed 5.067 m/s, peak 1060 veh | Yes; mean speed 5.471 m/s, peak 867 veh |
| i80_day | Yes; mean speed 24.625 m/s, peak 2121 veh | Yes; mean speed 25.111 m/s, peak 2047 veh |

Figures:

- phantom_jam: [phantom_jam.png](phantom_jam.png)
- one_av: [one_av_comparison.png](one_av_comparison.png)
- brake_wave: [brake_wave.png](brake_wave.png), [brake_wave_minima.png](brake_wave_minima.png)
- capacity_drop: [capacity_drop_detector.png](capacity_drop_detector.png), [capacity_drop_upstream.png](capacity_drop_upstream.png)
- freeway_fd: [freeway_fd_flow_veh_h.png](freeway_fd_flow_veh_h.png), [freeway_fd_speed_m_s.png](freeway_fd_speed_m_s.png)
- signal_discharge: [signal_discharge_headways.png](signal_discharge_headways.png)
- onramp_merge: [onramp_merge_detector.png](onramp_merge_detector.png), [onramp_merge_upstream.png](onramp_merge_upstream.png)
- spillback: [spillback_arrivals.png](spillback_arrivals.png), [spillback_upstream.png](spillback_upstream.png)
- gridlock: [gridlock_arrivals.png](gridlock_arrivals.png)
- mfd: [mfd_loop.png](mfd_loop.png)
- thesis_ring: [thesis_ring_time_space.png](thesis_ring_time_space.png)
- bologna_rush: [bologna_rush.png](bologna_rush.png)
- i80_day: [i80_day.png](i80_day.png)

Videos (13 reviewed 1080p H.264 movies at 30 fps, 28–50 s; cars rendering with speed colors). Extracted frames were visually checked, including both one-driver configurations. Camera files are in `cameras/`:

- [bologna_rush](/home/erikf/projects/personal/cars-data/videos/bologna_rush.mp4)
- [brake_wave](/home/erikf/projects/personal/cars-data/videos/brake_wave.mp4)
- [capacity_drop](/home/erikf/projects/personal/cars-data/videos/capacity_drop.mp4)
- [freeway_fd](/home/erikf/projects/personal/cars-data/videos/freeway_fd.mp4)
- [gridlock](/home/erikf/projects/personal/cars-data/videos/gridlock.mp4)
- [i80_day](/home/erikf/projects/personal/cars-data/videos/i80_day.mp4)
- [mfd](/home/erikf/projects/personal/cars-data/videos/mfd.mp4)
- [one_av](/home/erikf/projects/personal/cars-data/videos/one_av.mp4)
- [onramp_merge](/home/erikf/projects/personal/cars-data/videos/onramp_merge.mp4)
- [phantom_jam](/home/erikf/projects/personal/cars-data/videos/phantom_jam.mp4)
- [signal_discharge](/home/erikf/projects/personal/cars-data/videos/signal_discharge.mp4)
- [spillback](/home/erikf/projects/personal/cars-data/videos/spillback.mp4)
- [thesis_ring](/home/erikf/projects/personal/cars-data/videos/thesis_ring.mp4)

The one_av movie compares 25 s human-only followed by 25 s with one smooth driver. Its human-only source movie is `one_av_human.mp4`, using the same human ring as phantom_jam. The thesis sweep uses `flock /tmp/cars-gpu.lock target/release/sweep --scenario ring --tiers idm --penetrations 0 --seeds 42,43,44 --out results/phenomena/thesis_ring_sweep.csv --edge-out results/phenomena/thesis_ring_sweep_edges.csv`; its scripted disturbance is shown separately from the matched baseline.

No simulator core files were modified. Raw trajectories and logs remain in `runs/phenomena/`. A queue at a lane drop establishes breakdown; a negative measured drop percentage means no capacity drop was demonstrated.

Simulator issues and reproducible diagnostics:


Nonzero simulator counters are retained as diagnostics; this pass does not establish their root cause. Reproduce any row with `python scripts/phenomena.py SCENARIO --measure --seed SEED` inside the dev shell.

| Run | Overflow counter | Collisions | Teleports |
|---|---:|---:|---:|
| bologna_rush | 2255565 | 0 | 0 |
| bologna_rush_seed43 | 2239595 | 0 | 0 |
| bologna_rush_seed44 | 2294405 | 0 | 0 |
| gridlock | 11698 | 0 | 0 |
| gridlock_clear | 57701 | 0 | 0 |
| gridlock_clear_seed43 | 43986 | 0 | 0 |
| gridlock_clear_seed44 | 46166 | 0 | 0 |
| gridlock_seed43 | 14566 | 0 | 0 |
| gridlock_seed44 | 17705 | 0 | 0 |
| i80_day | 0 | 4 | 0 |
| mfd | 154790 | 0 | 0 |
| mfd_seed43 | 155090 | 0 | 0 |
| mfd_seed44 | 155183 | 0 | 0 |
| onramp_merge | 547029 | 0 | 0 |
| onramp_merge_seed43 | 547086 | 0 | 0 |
| onramp_merge_seed44 | 547083 | 0 | 0 |
