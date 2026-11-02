#!/usr/bin/env bash
# How many junctions the coordinator takes on each net. One short run per net, one at a time. Usage: coord_check.sh (dev environment loaded)
W=/home/erikf/projects/personal/cars-data/truth/maps/net10; B=$(dirname "$(readlink -f "$0")")/hv
export CARS_ADAPTER=llvmpipe LP_NUM_THREADS=1
for t in n7 v5 r12m r25m; do
  head -c 2000 "$B/rou/${t}_s0.5.rou.xml" | grep -q routes || true
  timeout 120 "$B/../../../target/release/cars" av --net "$B/nets/$t.net.xml" --routes "$B/rou/${t}_s0.5.rou.xml" --end 2 --cj all --capacity 9000 --json /tmp/net10_av_$t.json 2>&1 | grep -E "junctions coordinated" | cut -c1-140 | sed "s/^/$t: /"
  python3 -c "
import json,sys;d=json.load(open('/tmp/net10_av_$t.json'));print('  refused',d.get('refused'))" 2>/dev/null
done
