#!/usr/bin/env bash
# The Stockholm that does not lock up, step by step. Run inside nix develop from the repo root.
# usage: sthlm_recipe.sh OUTDIR [SCALE, default 0.6]. Uses /tmp/cars-sthlm and the shared GPU lock.
set -euo pipefail
D=/home/erikf/projects/personal/cars-data/stockholm
T=${1:?outdir}; SCALE=${2:-0.6}
S=research/truth/scripts
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
mkdir -p "$T"
run() { name=$1; routes=$2; end=$3; mkdir -p "$T/$name"
  flock /tmp/cars-gpu.lock /tmp/cars-sthlm run --net "$T/net.xml" --routes "$routes" --dt 1 --begin 0 --end "$end" \
    --time-to-teleport 120 --ignore-junction-blocker 20 --capacity 300000 --trusted \
    --summary-csv "$T/$name/summary.csv" --edge-csv "$T/$name/edges.csv" --edge-interval 900 --trip-csv "$T/$name/trips.csv" > "$T/$name/log.txt" 2>&1
  tail -3 "$T/$name/log.txt" | cut -c1-220; }

# 1. Net: the original flags plus SUMO's recommended signal flags, larger junction join, ramps on 70 km/h motorways.
#    Deliberately without --osm.turn-lanes and --no-turnarounds: both made things worse here.
netconvert --osm-files "$D/clip.osm.xml" -o "$T/net.xml" \
  --keep-edges.by-vclass passenger \
  --remove-edges.by-type highway.footway,highway.path,highway.cycleway,highway.steps,highway.pedestrian,highway.service \
  --output.street-names true --tls.guess-signals --tls.default-type actuated --ramps.guess --junctions.join \
  --roundabouts.guess --geometry.remove --remove-edges.isolated --keep-edges.components 1 --junctions.corner-detail 3 --proj.utm \
  --tls.discard-simple --tls.join --junctions.join-dist 15 --ramps.min-highway-speed 16.6 --ramps.ramp-length 200 --no-warnings
python3 -I $S/sthlm_netindex.py "$T/net.xml" "$T/net.idx.pkl"

# 2. Demand: real paths between far-apart ends, fitted to the counts with side-street matches removed. No random walks.
python3 -I $S/sthlm_assign.py pool "$T/net.idx.pkl" 6 6000 10 6 "$T/pool.txt"
python3 -I $S/sthlm_pool.py fit "$T/net.idx.pkl" "$D/count_matches.csv" "$D/trafikflode_motorfordon.geojson" "$T/pool.txt" "$T/full.rou.gz" "$T/fit.json" 1.0 | cut -c1-300

# 3. Drivers: SUMO's default acceleration instead of 1.5 m/s2.
zcat "$T/full.rou.gz" | sed 's/accel="1.5"/accel="2.6"/' | gzip -3 > "$T/full26.rou.gz"

# 4. Scale, then route feedback from an unjammed state. Feedback measured in a jam only moves the jam.
python3 -I $S/sthlm_thin.py "$T/full26.rou.gz" "$T/it0.rou.gz" "$SCALE"
run it0 "$T/it0.rou.gz" 36000
for k in 1 2 3; do
  p=$((k-1)); share=$(python3 -c "print(round(1/($k+1),3))")
  python3 -I $S/sthlm_assign.py reroute "$T/net.idx.pkl" "$T/it$p.rou.gz" "$T/it$p/edges.csv" "$share" "$k" "$T/it$k.rou.gz" 21600 36000
  run "it$k" "$T/it$k.rou.gz" 36000
done

# 5. The day.
run day "$T/it3.rou.gz" 86400

# 6. One more round with full-day times, then the final day.
python3 -I $S/sthlm_assign.py reroute "$T/net.idx.pkl" "$T/it3.rou.gz" "$T/day/edges.csv" 0.25 41 "$T/it4.rou.gz" 21600 75600
run day2 "$T/it4.rou.gz" 86400
