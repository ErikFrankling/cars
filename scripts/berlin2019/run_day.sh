#!/usr/bin/env bash
# One day of the district. run_day.sh NAME FACTOR BINARY [extra cars run flags]. Teleports off unless the flags say otherwise.
# GPU through the shared lock; CARS_ADAPTER=llvmpipe runs on the CPU without the lock.
set -u
B=/home/erikf/projects/personal/cars-data/berlin2019
name=$1; factor=$2; bin=$3; shift 3
out=$B/runs/$name; mkdir -p "$out"
NET=${NET:-$B/district/net.net.xml}; ROUTES=${ROUTES:-$B/district/routes_f$factor.rou.gz}; SENSORS=${SENSORS:-$B/district/sensors.csv}
cap=$(( ${factor#0} * 4000 + 4000 ))
cmd=("$bin" run --net "$NET" --routes "$ROUTES" --dt "${DT:-1}" --begin 0 --end "${END:-93600}" --time-to-teleport 0 --capacity "$cap" --sensors "$SENSORS" --sensor-csv "$out/sensors.csv" --edge-csv "$out/edges.csv" --edge-interval 900 --summary-csv "$out/summary.csv" --trip-csv "$out/trips.csv" --trusted "$@")
echo "${cmd[*]}" > "$out/cmd.txt"
if [ "${CARS_ADAPTER:-}" = llvmpipe ]; then
  "${cmd[@]}" > "$out/stdout.txt" 2> "$out/stderr.txt"
else
  flock /tmp/cars-gpu.lock "${cmd[@]}" > "$out/stdout.txt" 2> "$out/stderr.txt"
fi
echo "exit $?" >> "$out/stdout.txt"
tail -2 "$out/stdout.txt"; tail -3 "$out/stderr.txt" | cut -c1-200
