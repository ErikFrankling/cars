# pNEUMA: what is on disk, the road map from the traffic, read signals, a replay scene

6-7 November 2026. Forecasts F508-F511 and F515 in `foundations/forecasts.csv`. Code `scripts/replay/pneuma.py` (reader, inventory, lanes, signals, oversaturation) and `scripts/replay/pneuma_scene.py` (scene, F100, mix). Numbers in [pneuma_inventory.json](pneuma_inventory.json), [pneuma_lanes.json](pneuma_lanes.json), [pneuma_oversaturation.json](pneuma_oversaturation.json), [f100_pneuma_d8_20181029_0900.json](f100_pneuma_d8_20181029_0900.json). Licence CC-BY 4.0. Nothing from the dataset is in the repo; intermediates are in `cars-data/replay/pneuma/`.

## On disk

`datasets/pneuma-full/pNEUMA_dataset.zip`: 15.8 GB, 98 GB unpacked. It is never unpacked: each file is streamed from the zip, resampled to 5 Hz and converted to metres (UTM 34N minus 738,000 / 4,206,000), about 30 minutes of one core for all of it.

| | |
|---|---|
| Days | 4 weekday mornings: Wed 24 Oct 2018 (08:30-11:00), Mon 29 Oct, Tue 30 Oct, Thu 1 Nov (08:00-10:30) |
| Drones | 10, each its own area of about 300-550 m × 300-650 m |
| Files | 199 per-drone half-hours (20181030 drone 2 has 4, not 5). Each half-hour holds about 15-17 minutes of flight. 21 more `dX` files merge all drones per half-hour; they hold the same tracks and are not read |
| Tracks | 455,597 vehicle tracks (per drone file: a vehicle seen by two drones counts twice). Car 187,867; taxi 78,834; motorcycle 155,329; medium 18,614; bus 10,420; heavy 4,530; "Undefined" 3. One malformed row (20181029 drone 4, 09:00) skipped |
| Positions | latitude and longitude to 6 decimals, about 0.1 m |

Motorcycles by area:

| Drone | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Share of vehicles | 29.8% | 34.3% | 37.2% | 30.5% | 38.1% | 35.0% | 31.1% | **29.2%** | 31.9% | 38.6% |
| Share of vehicle time | 24.1% | 27.7% | 31.4% | 23.0% | 30.2% | 26.6% | 22.8% | **20.7%** | 24.4% | 31.9% |

The share rises through the morning: 28% of vehicles at 08:00, 36% at 10:30.

## Road map from where vehicles drive (F509, F510)

Lane geometry is taken from where the cars drive, and OSM is the check on it. The skeleton is OSM's roads (Overpass, 6 November 2026), converted by netconvert in the same coordinates.

The method, per OSM edge in a drone's view:
1. Take the moving cars and taxis whose heading agrees with the edge within 30 degrees, from the 09:00 and 09:30 files of all four days.
2. Project them onto the edge's rightmost lane.
3. Their lateral density's peaks are the lanes.
4. The residual is each car's distance from its nearest lane.

| | Result |
|---|---|
| Edges with enough traffic | 314 in 10 areas |
| OSM's lane count agrees with the density's | **56.7%** of edges. The density finds fewer lanes on 108 edges (OSM counts bus lanes and parking lanes) and more on 28 |
| Car residual, median over edges | **0.38 m** about the density lanes; 0.89 m about OSM's lanes |
| Density lane centres against OSM's | 0.95-3.3 m apart per area (weighted) |
| Lane spacing | 2.8-3.3 m (area medians) |
| Moving samples on these edges | 29-48%. The rest are inside junctions, on short edges, or on edges mostly outside the view |

Motorcycle share of the time on each lane (area medians): kerb lane 20-26%, middle lanes 11-22%, median-side lane 8-25%. About half of motorcycle time (51%, median of edges) is more than 0.8 m from any car lane's centre, i.e. between lanes. A lane model sees those riders as somewhere they are not. Per-lane residuals and shares for every edge are in `cars-data/replay/pneuma/lanes/d*.json`.

## Signals read from crossings (F511)

The method:
1. Every incoming edge of an OSM signalised junction in view is read in each of the 199 files, with the reader of [SIGNALS.md](SIGNALS.md): stop line from queue heads, then the fixed-time fit with `d_start` 1.9 s and `d_end` −0.95 s.
2. 1,992 approach-files are read; 1,668 fits are kept (concentration R ≥ 0.8 and a green between 5 s and the cycle minus 5 s).
3. Median R is 0.975: the head starts are periodic, as pre-timed signals should be.
4. Cycle lengths: 90 s (773 fits, plus 152 at 89-93 s), 45 s (660), 180 s (10).
5. A 45 s fit can be a real 45 s cycle or two greens in one 90 s cycle; the reader can't tell which.

Error band, from [SIGNALS.md](SIGNALS.md): onset ±0.6 s median (p90 1.4 s), end ±2.6 s median (p90 5 s), cycle ±0.05 s. It was measured on German and Chinese traffic; Athens has no truth.

**Residual queues.** A read cycle has a residual queue when a car stood before the line from 5 s before the end of green until 2 s after the yellow, and then crossed within the next two cycles. That is, a later green served it. Parked cars and cars that turn off before the line never cross, so they don't count. A first version without the crossing condition counted parked and double-parked cars and gave higher shares; it was replaced.

| Drone | Approaches (30+ cycles) | Cycles with a residual queue, all approaches | Worst approach: street, lanes, cycles, share with residual, mean / max queue at green |
|---|---|---|---|
| 6 | 23 | 24.5% | Marni, 3, 179, **74.3%**, 7.0 / 21 |
| 3 | 10 | 38.0% | Dragatsaniou, 4, 158, **63.9%**, 4.5 / 20; Ippokratous 63.5%; Panepistimiou 61.4% |
| 9 | 12 | 23.3% | Kamaterou, 2, 200, **63.5%**, 5.3 / 18 |
| 5 | 10 | 26.8% | Omonia square, 3, 82, **63.4%**, 5.7 / 18; Panepistimiou 50.3% |
| 7 | 9 | 32.3% | Patision, 3, 171, **62.6%**, 3.9 / 11; Ioulianou 48.2% |
| 8 | 8 | 28.8% | Alexandras, 2, 148, **62.2%**, 4.6 / 17; Patision 52.6% |
| 10 | 11 | 30.2% | Panepistimiou, 5, 155, **56.8%**, 8.5 / 23 |
| 2 | 10 | 34.4% | Amerikis, 3, 143, **54.5%**, 10.0 / 19; Vasileos Georgiou A 50.5% |
| 4 | 13 | 19.5% | Solonos, 2, 266, **42.9%**, 2.3 / 11; Charilaou Trikoupi 39.7% |
| 1 | 6 | 17.4% | Amerikis, 2, 315, **31.7%**, 6.2 / 14 |

- Every area has an approach that fails in at least 32% of its cycles. So T3b has material everywhere; drones 6, 3, 9, 5, 7 and 8 have the worst approaches.
- The share hardly changes with the hour: 23% of cycles at 08:00, 27-29% from 09:00 on.
- The 25 cycles with the largest residual queue (15-18 cars) are listed in `pneuma_oversaturation.json`, by day, drone, half-hour, edge and green onset. Per-cycle rows for all approaches are in `cars-data/replay/pneuma/signals_cycles.csv`.
- A residual of a few cars at the end of green is within the end band (±2.6 s is one or two cars at saturation flow). The worst approaches, failing in most cycles with residuals of up to 18 cars, are not.

## A replay scene: drone 8, Monday 29 October, 09:00 (F508)

Drone 8 has the lowest motorcycle share (29.2% of vehicles, 20.7% of time). It covers Alexandras avenue at Patision with Ioulianou and Mavromataion; 11 signalised junctions. The 09:00 file holds 996 s of flight.

**Net.**
- The OSM net is cut to the view, and the lanes of its 44 edges with enough traffic are replaced by the density lanes: their number, width and place.
- Junctions keep their internal lanes.
- Signals: one long program per junction from the read approaches of this file. 17 of 87 links have a read approach; the others stay green and are counted, since their approaches had too few standing cars to read.

**Tracks.**
- Every sample goes to the nearest lane (internal lanes too) whose direction agrees within 45 degrees and within 3 m; what is left goes within 6 m and 70 degrees.
- The key is the front's projection. A front past the end of its lane goes onto the next lane the track takes.
- The lateral offset is the centre's.
- A track is cut where it leaves the net, or where its edges are not a path of the net within three hops. Up to two edges it skipped are put into its route (1,705 times).
- 11% of samples are off the net: side streets missing from OSM's car net, parking, and motorcycles on pedestrian streets.

| | |
|---|---|
| Vehicles | 2,781; 4,349 pieces, 1.56 per vehicle (2.42 before the relaxed matching and bridging) |
| Cuts | 1,068 not a path (mostly a junction crossing to an edge with no connection from the one before), the rest gaps off the net |
| 'mix' | 1,848 cars, taxis, medium and heavy vehicles simulated from their first piece's entry to its exit (1,202 later pieces of theirs dropped: the driver has the car, but its route ends where the piece ended); buses and motorcycles replayed |

**F100**, everything replayed, dt 0.2 s:

| | |
|---|---|
| Samples present | 963,795 of 972,250 (99.1%); the rest are each trip's insertion step and its last key |
| Lane coordinates against the keys | p99 2.1 cm, max 5.9 cm; lateral p99 0.3 cm |
| Front, 2D, against the recording | median **0.11 m**, p90 0.66 m, p99 **1.81 m**; on edges 0.10 / 0.57 / 1.62 m; inside junctions 0.13 / 0.96 / 2.34 m |

The harness is within 2 cm. The 2D tail is the scene's representation:
- The lateral offset is the centre's, and moves the whole body. A vehicle angled to its lane (turning, changing lanes, a motorcycle weaving) has its front off by up to half its length times the angle.
- The relaxed matching inside junctions adds to it.

F508's p99 under 1.0 m misses for these reasons.

Three fixes were needed before this, each found by F100:
- Keys clamped at the lane end made a vehicle "arrive" on its last edge.
- Fronts past the end of their lane had to move onto the next lane.
- A piece that ends inside a junction needs its route to go on to that connection's exit.

**F515**, a first all-cars-simulated run: see RESULTS.md.

## Rerun

```sh
python3 -I scripts/replay/pneuma.py convert                     # agent-job; 30 min of one core
python3 -I scripts/replay/pneuma.py osmnet                      # needs cars-data/replay/pneuma/osm.osm (Overpass, bbox 37.962,23.712,37.998,23.752)
python3 -I scripts/replay/pneuma.py inventory
python3 -I scripts/replay/pneuma.py lanes 1,2,3,4,5,6,7,8,9,10 && python3 -I scripts/replay/pneuma.py lanes_summary
python3 -I scripts/replay/pneuma.py signals 1,2,3,4,5,6,7,8,9,10   # agent-job, about 25 min
python3 -I scripts/replay/pneuma.py oversaturation
python3 -I scripts/replay/pneuma_scene.py build 8 20181029 0900
python3 -I scripts/replay/pneuma_scene.py f100 8 20181029 0900 --gpu
python3 -I scripts/replay/pneuma_scene.py mix 8 20181029 0900
```
