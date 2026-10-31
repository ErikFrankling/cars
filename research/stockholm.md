# Stockholm weekday scenario

This is an estimated demand fitted to traffic counts, not observed origin–destination
journeys. It is runnable in SUMO and cars. It is not a validated reconstruction of
Stockholm traffic. Local data and outputs live under
`/home/erikf/projects/personal/cars-data/stockholm`; videos are in the sibling
`videos` directory. Reproduction commands are in `scripts/stockholm/README.md`.

## Sources and licence

The BBBike Stockholm OSM extract was downloaded on 2026-10-31 from
https://download.bbbike.org/osm/bbbike/Stockholm/Stockholm.osm.pbf.
© OpenStreetMap contributors, ODbL: https://www.openstreetmap.org/copyright.
Stockholms stad Trafikkontoret provides Trafikflöde Motorfordon via its open
geoservice. The city states that service data may be freely reused and is
provided licence-free unless otherwise specified:
https://openstreetgs.stockholm.se/home/ . This is not an assertion of CC0.
The local WFS response has 16,698 features in EPSG:4326. Values are heterogeneous
annual average weekdays, including estimated traffic; measurement dates vary.
Downloaded XML, PBF and GeoJSON are treated as data, never executable scripts.

## Network and matching

`build_net.sh` rebuilds the clipped OSM extract with passenger filtering, ramps
and roundabouts guessed, joined junctions, guessed actuated signals and one
weak connected component. Service roads and pedestrian/cycle types are removed.
Conversion warnings remain in `netconvert.log`, including malformed OSM layers,
restrictions and junction geometry. The resulting 76,609 passenger edges have
1,922 signal programs; these include guessed signals, not a measured inventory.
The connection-permission-aware audit finds 76,295 edges (99.59%) in the largest
strong component, with 256 components overall. Boundary stubs remain.
All named Södra länken, Norra länken, Västerbron, Centralbron and Essingeleden
edges are in the main component. E4/E20 references were not preserved as street
names, so the name audit cannot independently establish their continuity.
The rendered road-class map was visually inspected; it shows the motorway
corridors and central crossings, but cannot verify every ramp or tunnel layer.

`map_counts.py` transforms lon/lat through SUMO's projection and offset, samples
edge geometry at approximately 15 m, and searches nearby segments with matching
bearing. Reject distance >60 m or angle >35 degrees. There are 31,654 directional
matches. The source explicitly reports all-direction counts; split equally
between two matched directions, otherwise assign the total to the one match.
This fallback can overstate a direction when its opposite was missed. Parallel
roads and grade-separated crossings need manual review. Match quality, source
date and method are retained in `count_matches.csv`. Repeated edge observations
are averaged, not summed.

## Demand

A fixed seed (42) creates four route candidates per matched edge, extending
randomly upstream and downstream without loops, checking lane AND turn-level
passenger permissions. Stop at roughly 3–12 km or 60 extensions per side.
The pool contains about 79,000 routes. Three hundred multiplicative balancing
iterations fit nonnegative route weights against each source time band, with
stochastic rounding to integer vehicles. This lightweight alternative to
routeSampler avoids an expensive underdetermined least-squares solve. It does
not infer observed OD. The trip total depends strongly on the route pool.

The fitted day has 2,919,242 trips. Expected passage totals match the aggregate
mapped targets, while individual-edge route-fit GEH<5 shares are 62.20% (06–18),
78.68% (18–22), and 87.55% (22–06). These are fitting residuals, not simulation
results. Hours are uniform within each band because the input has no finer
hourly profile. The discontinuities at band boundaries are an explicit modelling
limitation. Passenger proxies include all motor vehicles, including trucks.
Parameters: accel 1.5, decel 4.5, sigma 0.5, tau 1, length 5, minGap 2;
departLane=best, departSpeed=max. Gzipped routes are sorted by depart time.

## Validation

SUMO uses dt=1, teleport 120 s, ignore-junction-blocker 20 s, with edge passage
and trip outputs. Morning validation starts empty at 07:00; it lacks warmup and
cannot be directly interpreted as a stationary count comparison. A five-minute
smoke test passed after fixing turn restrictions. Its GEH<5 share was 93.4%,
which is inflated by the short comparison window and is not an acceptance test.

Cars uses the same network and demand, dt=1 and the same teleport/blocker settings,
capacity 200,000. Every GPU invocation uses `/tmp/cars-gpu.lock`; GPU buffers for
the whole day use about 797 MB, leaving more than 3 GB free. A release build passed.
The initial hour reported 180 teleports, six collisions and 16,695 insertion
overflow events (events can repeat; they are not unique lost trips). Simulator
kernels were not modified. These are unresolved quality concerns.

Final measured metrics are recorded in `results/stockholm/metrics.json` when
available, with raw logs and CSV/XML outputs outside git. Figures distinguish
route fit from simulated counts. No calibrated signal timings, observed OD,
congestion feedback assignment, measured within-band rush profile or heavy-vehicle
fleet is available. These limitations preclude a claim of statistically comparable
real Stockholm flows without further calibration.

The completed cars day ran in 189.30 s with peak running 137,985. At midnight,
2,160,838 had inserted, 2,057,847 arrived, 102,985 remained running, and 758,404
scheduled trips had not inserted. There were 1,265,167 teleport events,
281,193 collision events, and 113,990,707 repeated insertion-overflow events.
Simulated GEH<5 shares were 51.22% (06–18), 65.69% (18–22), and 78.24% (22–06).
This fails traffic-quality validation. Do not use the scenario to claim realistic
Stockholm flows or agreement with SUMO. The simulator's collision and insertion
diagnostics need investigation independently of demand calibration. Recording
now accepts explicit capacity and teleport/blocker settings and limits each
libx264 pass to two threads.

The SUMO 07:00–08:00 run completed in approximately 522 s: 167,920 inserted,
139,015 arrived, 28,905 still running and 15,517 waiting to insert. There were
9,269 teleports, including 126 collision teleports. GEH<5 was 81.69% across
19,953 matched edges for this window (targets scaled from the 06–18 band).
No SUMO validation exists for 18–22 or 22–06. This one-hour, empty-start SUMO
comparison is not equivalent to the whole-day cars comparison.

## Videos and figures

`cars-data/videos/stockholm_day.mp4` covers 00:00–24:00 in 40 seconds at 1080p,
30 fps, 72 simulation seconds per frame, with the city fitted to view.
`cars-data/videos/stockholm_slussen.mp4` covers 07:00–07:20 in 40 seconds,
with a camera centred on Slussen at 18.072 E, 59.320 N. Both have burned-in titles
and captions, and are qualitative views of an uncalibrated estimate. They
re-simulate the scenario rather than replay the measured CSV; do not read
precise validation numbers from their HUD. libx264 is restricted to two threads.
PNG figures are in `results/stockholm`: network, hourly departures, running
vehicles and flow-vs-count scatters with GEH=5 contours. SUMO's running trace
covers 07:00–08:00 only; cars covers 24 hours.

Both final MP4s were probed as 1920×1080, 30 fps, exactly 40 seconds. Frames
at 20 seconds were extracted and visually inspected: readable titles/captions,
city-wide congestion in the timelapse and visible Slussen approaches in the zoom.

## Demand scale used for the report

With the final engine the fitted 2.9M trips overload the network from 06:00 on: over 110,000 cars running and a million teleports. `scripts/stockholm/retime.py` keeps 60% of the trips and spreads each source band over a typical weekday profile instead of uniform hours, which removes the jump at 06:00. That profile is an assumption, the source has only three bands. At 60%, 82% of the 10,013 matched edges have daily GEH below 5 and r² is 0.61, against 70% and 0.50 at full demand. The scale was picked for this fit, so the fit is not independent validation. Teleports stay high, about 285,000, and the guessed signals and random route pool are the first things to replace.

Latest figures at 60%, final engine: 1.63M trips inserted, 1.61M completed, peak 51,214 running, 302,180 teleports. Daily GEH<5 is 82%, r² 0.61, slope 0.49 at 10,013 matched edges. Per source band the GEH<5 share is lower, 38% for 06-18, 55% for 18-22, 71% for 22-06, because the retimed profile and the 60% scale were not fitted per band. The day took 172 s.
