#!/usr/bin/env bash
set -euo pipefail
data=${1:-/home/erikf/projects/personal/cars-data/stockholm}
end=${2:-86400}
flock /tmp/cars-gpu.lock target/release/cars run --net "$data/stockholm.net.xml" \
 --routes "$data/stockholm.rou.gz" --dt 1 --begin 0 --end "$end" \
 --time-to-teleport 120 --ignore-junction-blocker 20 --capacity 200000 \
 --trusted --summary-csv "$data/cars.summary.csv" --edge-csv "$data/cars.edges.csv" \
 --edge-interval 3600 --trip-csv "$data/cars.trips.csv" > "$data/cars.log" 2>&1
