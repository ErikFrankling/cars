#!/usr/bin/env bash
# Controlled morning tests: sweep_am.sh FACTOR NETDIR BIN "name|flags[|routes]" ... Runs 04:00 to 08:00 and prints cars running at 06:00, 06:30, 07:00, 07:30, 08:00.
# GPU through the lock, run by run; CARS_ADAPTER=llvmpipe for CPU. Lockup is chaotic: repeat with --seed.
B=/home/erikf/projects/personal/cars-data/berlin2019
f=$1; nd=$2; bin=$3; shift 3
for spec in "$@"; do
  IFS='|' read -r n flags routes <<< "$spec"
  routes=${routes:-$B/district/m10/routes_f$f.rou.gz}
  o=$B/runs/sw_$n; mkdir -p "$o"
  cmd=("$bin" run --net "${NETF:-$B/district/$nd/net.net.xml}" --routes "$routes" --dt "${DT:-1}" --begin 14400 --end 28800 --capacity 70000 --time-to-teleport 0 --trusted --summary-csv "$o/summary.csv" --report-json "$o/report.json" $flags)
  if [ "${CARS_ADAPTER:-}" = llvmpipe ]; then "${cmd[@]}" > "$o/stdout.txt" 2> "$o/stderr.txt"; else flock /tmp/cars-gpu.lock "${cmd[@]}" > "$o/stdout.txt" 2> "$o/stderr.txt"; fi
  echo "$n: $(awk -F, '$1==21600||$1==23400||$1==25200||$1==27000||$1==28800{printf "%s ",$2}' "$o/summary.csv") | wall $(tail -n1 "$o/summary.csv" | cut -d, -f6)"
done
