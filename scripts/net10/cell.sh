#!/usr/bin/env bash
# One net at one scale: trips, routes (same rule on every net), cars on llvmpipe. Usage: cell.sh NET_TAG SCALE [SEED]
set -uo pipefail
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 CARS_ADAPTER=llvmpipe
W=/home/erikf/projects/personal/cars-data/truth/maps/net10
d=$(dirname "$(readlink -f "$0")"); tag=$1; sc=$2; seed=${3:-1}
net=$W/$tag/net.xml; [ -f "$net" ] || net=$W/$tag.net.xml
o=$W/runs/${tag}_s${sc}_$seed; mkdir -p "$o"
python3 "$d/demand.py" trips $W/od.json "$net" "$o/trips.xml" "$sc" "$seed"
duarouter -n "$net" --route-files "$o/trips.xml" -o "$o/rou.xml" --ignore-errors --no-warnings --no-step-log \
  --weights.random-factor 1.5 --seed "$seed" --routing-threads 1 2> "$o/dua.err"
echo "routed $(grep -c '<vehicle ' "$o/rou.xml") of $(grep -c '<trip ' "$o/trips.xml")"
s=$(date +%s)
timeout ${MAXS:-1500} "$d/../../target/release/cars" run --net "$net" --routes "$o/rou.xml" --dt 1 --begin 0 --end ${END:-4200} --time-to-teleport 120 --ignore-junction-blocker 20 \
  --seed "$seed" --capacity ${CAP:-40000} --summary-csv "$o/summary.csv" --edge-csv "$o/edges.csv" --edge-interval 900 --trip-csv "$o/trips.csv" > "$o/log.txt" 2>&1
echo "exit $? wall $(( $(date +%s)-s )) s"; tail -2 "$o/log.txt" | cut -c1-400
