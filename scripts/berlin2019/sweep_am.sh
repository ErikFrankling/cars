#!/usr/bin/env bash
# Quick controlled tests: sweep_am.sh FACTOR NETDIR BIN "name|flags" ... Runs 04:00 to 07:30 and prints cars running at 06:00, 07:00, 07:30.
B=/home/erikf/projects/personal/cars-data/berlin2019
f=$1; nd=$2; bin=$3; shift 3
for spec in "$@"; do
  n=${spec%%|*}; flags=${spec#*|}
  o=$B/runs/sw_$n; mkdir -p "$o"
  "$bin" run --net ${NETF:-$B/district/$nd/net.net.xml} --routes $B/district/m10/routes_f$f.rou.gz --dt ${DT:-1} --begin 14400 --end 27000 --capacity 60000 --time-to-teleport 0 --trusted --summary-csv $o/summary.csv $flags > $o/stdout.txt 2> $o/stderr.txt
  echo "$n: $(awk -F, '$1==21600||$1==25200||$1==27000{printf "%s ",$2}' $o/summary.csv) | $(grep -E '^physics:' $o/stderr.txt | sed -E 's/.*collisions ([0-9]+) incidents.*denied bids ([0-9]+).*/collisions \1 denied \2/') wall $(tail -n1 $o/stdout.txt | cut -d, -f1)"
done
