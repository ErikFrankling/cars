<img src="assets/icon.svg" width="64" height="64" alt="">

# cars

A GPU reimplementation of SUMO's microscopic traffic simulation, in Rust and WGSL compute shaders. It reads SUMO networks and demand files and produces the same flows, statistically: same trip durations, same queues, same lane use, 100 times faster or more on city-sized jobs and large ensembles.

**Status.** This is the SUMO parity baseline, tagged `sumo-parity`. Matching SUMO says nothing about matching reality. The current Berlin and Stockholm scenarios are not true to life: Berlin's demand has no morning rush and half the measured volume, and Stockholm's demand and network are defective. The move to real data, physically based vehicles and communicating self-driving cars is in progress; the findings are in [research/truth](research/truth).

The summary with charts is [report/index.html](report/index.html). Figures are in [report/figures](report/figures), raw numbers in [results](results).

## Results

| Job | SUMO | cars |
|---|---|---|
| Berlin 05:00-10:00, mean trip duration | 789.0 s | 788.1 s |
| Berlin 05:00-10:00, 95th percentile trip | 1882 s | 1883 s |
| Berlin 05:00-10:00, mean waiting / time loss | 67.6 / 181.2 s | 66.4 / 179.2 s |
| Mitte cutout, 24 h, mean trip duration | 414.3 s | 414.3 s |
| Charlottenburg cutout, 24 h, mean trip duration | 293.9 s | 292.9 s |
| Berlin, 24 h, wall clock | about 7 h (published with BeST) | 148 s |
| Whole thesis sweep, 1,134 runs | 8.2 h on the same PC | 341 s |

Hardware: Ryzen 7800X3D and Radeon RX 7900 XT. SUMO is 1.28, single thread unless noted.

Throughput levels off around 58 million vehicle updates per second with 830,000 vehicles in one world. SUMO does 0.15 to 0.8 million on this PC depending on network size. A single small scenario is about even: ring 200 cars takes 2.3 s against 1.5 s. The gain comes from big networks and from running hundreds of replicas in one GPU world.

## What differs from SUMO, known gaps

- Bologna human traffic is too fast: 3% mean speed error across the sweep, and 5.4 m/s against 5.1 in the seed 42 rush run. A few priority junctions queue less than in SUMO. With IDM drivers, delays at minor links and right-before-left junctions are off by 20 to 160% in isolated tests, while Krauss matches.
- I-80 with CACC has a 23% time loss error and ACC 2.6%, speed within 3%. Lane drop discharge is close over the long run (1,768 SUMO, about 1,900 cars veh/h with IDM) but differs in the first minutes after breakdown. A ring packed to 0.19 m bumper gaps fails to insert all cars.
- Evening Berlin: 23,700 teleports over the day, against 2,332 published for BeST, most of them between 18:00 and 22:00. There is no SUMO evening baseline here, because a SUMO day takes many hours. The morning matches: 231 SUMO, 200 cars by 10:00. The failures are spread over many edges; the worst single edge has 1.3% of them. The scenario's departures stay flat until 18:00 on fixed routes, which is the likely cause.
- Runs are not bit reproducible. GPU atomics race between runs, so a chaotic scenario differs from run to run, as SUMO does between seeds.
- Buses, stops, pedestrians, sublanes and opposite driving are not implemented.
- Real detector comparison: at 103 Berlin sites both simulators sit around 16% GEH<5, with volumes near half of measured. This says more about the BeST demand and the site matching than about either simulator.
- Stockholm: a preliminary scenario with demand fitted to the city's counts, not observed journeys. See [research/stockholm.md](research/stockholm.md).

## Running

```sh
nix develop --command cargo build --release
target/release/cars run --net city.net.xml --routes city.rou.gz --dt 1 --end 86400 \
  --time-to-teleport 120 --ignore-junction-blocker 20 --capacity 300000 --trusted \
  --summary-csv summary.csv --edge-csv edges.csv --edge-interval 900 --trip-csv trips.csv
target/release/cars record --net city.net.xml --routes city.rou.gz --dt 1 --begin 0 --end 86400 \
  --steps-per-frame 48 --fit --out day.mp4 --title 'A day'
target/release/sweep --scenario bologna --tiers krauss,idm,acc,cacc,glosa \
  --penetrations 0,0.25,0.5,0.75,1 --seeds 0,1,2 --out sweep.csv
```

`scripts/final_runs.sh` reruns the city and thesis results, `scripts/report.py` and `scripts/report_html.py` rebuild the report, `scripts/bench.py` the speed numbers, `scripts/phenomena.py` the phenomena. Data paths are under `/home/erikf/projects/personal/cars-data`; the [data inventory](research/data-inventory.md) says where each dataset came from.

Created in [T3 Code](https://t3.codes).
