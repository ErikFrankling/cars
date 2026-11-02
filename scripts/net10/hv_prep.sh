#!/usr/bin/env bash
# Trips and routes for the homelab grid, with the same rule on every net; the sims themselves run on the worker.
set -uo pipefail
W=/home/erikf/projects/personal/cars-data/truth/maps/net10; d=$(dirname "$(readlink -f "$0")"); B=$d/hv
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
mkdir -p "$B/nets" "$B/rou"
for t in n7 v5 r12 r25m; do for sc in 0.5 1.0; do
  o=$B/rou/${t}_s$sc.rou.xml; [ -s "$o" ] && continue
  python3 "$d/demand.py" trips $W/od.json "$B/nets/$t.net.xml" /tmp/net10_tr.xml $sc 1
  duarouter -n "$B/nets/$t.net.xml" --route-files /tmp/net10_tr.xml -o "$o" --ignore-errors --no-warnings --no-step-log --weights.random-factor 1.5 --seed 1 --routing-threads 1 2>/dev/null
  echo "$t $sc routed $(grep -c '<vehicle ' "$o") of $(grep -c '<trip ' /tmp/net10_tr.xml)"
done; done
for sc in 0.5 1.0; do for t in r12p r12m r12mb; do cp "$B/rou/r12_s$sc.rou.xml" "$B/rou/${t}_s$sc.rou.xml"; done; cp "$B/rou/r25m_s$sc.rou.xml" "$B/rou/r25mb_s$sc.rou.xml"; done
