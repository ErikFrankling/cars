#!/usr/bin/env bash
# sthlm_run.sh NAME NET ROUTES BEGIN END [extra cars flags]. One GPU job through the shared lock.
set -euo pipefail
name=$1; net=$2; routes=$3; begin=$4; end=$5; shift 5
out=/home/erikf/projects/personal/cars-data/truth/stockholm/factorial/$name
mkdir -p "$out"
echo "net=$net routes=$routes begin=$begin end=$end extra=$* binary=$(sha256sum /tmp/cars-sthlm | cut -c1-16)" > "$out/config.txt"
free -g | sed -n 2p >> "$out/config.txt"
flock /tmp/cars-gpu.lock /tmp/cars-sthlm run --net "$net" --routes "$routes" --dt 1 --begin "$begin" --end "$end" \
  --time-to-teleport 120 --ignore-junction-blocker 20 --capacity 300000 --trusted \
  --summary-csv "$out/summary.csv" --edge-csv "$out/edges.csv" --edge-interval ${EDGE_INTERVAL:-900} --trip-csv "$out/trips.csv" "$@" > "$out/log.txt" 2>&1
tail -3 "$out/log.txt" | cut -c1-240
