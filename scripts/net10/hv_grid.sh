#!/bin/sh
# On the worker, inside scripts/d8/worker.sh. One run at a time, most useful first. Usage: hv_grid.sh [net:scale ...]
cd "$(dirname "$0")/hv"; mkdir -p out
for c in "$@"; do
  t=${c%%:*}; sc=${c##*:}; o=out/${t}_s$sc; mkdir -p "$o"; [ -s "$o/done" ] && continue
  s=$(date +%s)
  timeout 3000 ../../../target/release/cars run --net nets/$t.net.xml --routes rou/${t}_s$sc.rou.xml --dt 1 --begin 0 --end 4200 --time-to-teleport 120 --ignore-junction-blocker 20 --seed 1 --capacity 40000 \
    --summary-csv "$o/summary.csv" --edge-csv "$o/edges.csv" --edge-interval 900 --trip-csv "$o/trips.csv" > "$o/log.txt" 2>&1
  r=$?; echo "$t $sc exit $r wall $(( $(date +%s)-s )) s: $(tail -1 "$o/summary.csv")  $(tail -1 "$o/log.txt" | cut -c1-150)"
  [ $r = 0 ] && echo ok > "$o/done"
done
