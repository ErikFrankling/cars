#!/usr/bin/env bash
# Every city and thesis run behind the report, with one binary. GPU jobs queue on the lock.
cd "$(dirname "$0")/.." || exit 1
BIN=/tmp/cars-final
cp target/release/cars $BIN; cp target/release/sweep /tmp/sweep-final
D=/home/erikf/projects/personal/cars-data
F="--dt 1 --time-to-teleport 120 --ignore-junction-blocker 20 --trusted"
run() { name=$1; shift; echo "== $name"; flock /tmp/cars-gpu.lock "$BIN" run "$@" 2>&1 | grep -E '^lane changes|^time:|^wall|panic' | cut -c1-240; }
run charlottenburg --net $D/charlottenburg/charlottenburg.net.xml --routes $D/charlottenburg/charlottenburg.rou.gz --begin 0 --end 86400 --capacity 200000 $F --summary-csv runs/char/summary.csv --edge-csv runs/char/edges.csv --edge-interval 900 --trip-csv runs/char/trips.csv
run berlin_morning --net $D/best/berlin.net.xml --routes $D/best/berlin.rou.gz --begin 18000 --end 36000 --capacity 300000 $F --summary-csv runs/berlin/morning_summary.csv --edge-csv runs/berlin/morning_edges.csv --edge-interval 900 --trip-csv runs/berlin/morning_trips.csv
run berlin_day --net $D/best/berlin.net.xml --routes $D/best/berlin.rou.gz --begin 0 --end 86400 --capacity 600000 $F --summary-csv runs/berlin/day_summary.csv --edge-csv runs/berlin/day_edges.csv --edge-interval 3600 --trip-csv runs/berlin/day_trips.csv
scripts/thesis_sweeps.sh /tmp/sweep-final
