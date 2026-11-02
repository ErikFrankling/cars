#!/usr/bin/env bash
# One run on this machine, for the short ones. Usage: local_cell.sh NET SCALE (dev environment loaded)
W=/home/erikf/projects/personal/cars-data/truth/maps/net10; B=$W/hv; R=$(dirname "$(readlink -f "$0")")/../..; t=$1; sc=$2; o=$W/runs/${t}_s${sc}_f${SEED:-}; mkdir -p "$o"
export CARS_ADAPTER=llvmpipe LP_NUM_THREADS=${LP_NUM_THREADS:-4}; s=$(date +%s)
timeout ${MAXS:-560} "$R/target/release/cars" run --net "$B/nets/$t.net.xml" --routes "$B/rou/${t}_s$sc.rou.xml" --dt 1 --begin 0 --end 4200 --time-to-teleport 120 --ignore-junction-blocker 20 --seed ${SEED:-1} --capacity 40000 \
  --summary-csv "$o/summary.csv" --edge-csv "$o/edges.csv" --edge-interval 900 --trip-csv "$o/trips.csv" > "$o/log.txt" 2>&1
echo "$t $sc exit $? wall $(( $(date +%s)-s )) s: $(tail -1 "$o/summary.csv")"
