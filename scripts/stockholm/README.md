Run commands from the repo root inside `nix develop`. Inputs and outputs default
to `/home/erikf/projects/personal/cars-data/stockholm`.

- `bash scripts/stockholm/prepare.sh` rebuilds, audits, maps and fits demand.
- `bash scripts/stockholm/sumo_window.sh` validates 07:00–08:00.
- `bash scripts/stockholm/run_cars.sh PATH 300` starts GPU validation small;
  omit 300 for the whole day after checking resource use and logs.
- `bash scripts/stockholm/record.sh` records the city and Slussen.

Use `python3 -I` for every data-reading script. Geometry is transformed from
EPSG:4326 through SUMO's projParameter and netOffset. Count rows are two-way
all-direction counts; divide equally across matched directions, or assign all
to a single matched direction. Matches beyond 60 m or 35 degrees are rejected.
Parallel roads, grade separation and failed reverse matches remain uncertain.
Averages combine overlapping observations; they are not independent counts.

Daily edge passages cannot identify daily trips. The route pool and trip lengths
are assumptions. Hourly departures are uniform inside the three source bands;
no observed rush-hour shape is available in this source. Passenger proxies include
heavy-vehicle counts. Route fit GEH is not simulated GEH.
