#!/usr/bin/env bash
# Trips and routes with the same rule on every net; variants of a net share its routes. Usage: routes.sh (dev environment loaded)
set -uo pipefail
W=/home/erikf/projects/personal/cars-data/truth/maps/net10; d=$(dirname "$(readlink -f "$0")"); B=$W/hv
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
mkdir -p "$B/rou"
for t in n7 v5 r12 r25m; do for sc in 0.5 1.0 1.07 1.67; do
  o=$B/rou/${t}_s$sc.rou.xml; [ -s "$o" ] && continue
  python3 "$d/demand.py" trips $W/od.json "$B/nets/$t.net.xml" /tmp/net10_tr.xml $sc 1
  duarouter -n "$B/nets/$t.net.xml" --route-files /tmp/net10_tr.xml -o "$o" --ignore-errors --no-warnings --no-step-log --weights.random-factor 1.5 --seed 1 --routing-threads 1 2>/dev/null
done; done
rm -f "$B"/rou/*.alt.xml
for sc in 0.5 1.0 1.07 1.67; do
  for t in r12b r12p r12pb r12m r12mb; do cp "$B/rou/r12_s$sc.rou.xml" "$B/rou/${t}_s$sc.rou.xml"; done
  cp "$B/rou/r25m_s$sc.rou.xml" "$B/rou/r25mb_s$sc.rou.xml"; cp "$B/rou/v5_s$sc.rou.xml" "$B/rou/v5b_s$sc.rou.xml"
done
