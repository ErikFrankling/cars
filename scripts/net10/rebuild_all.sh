#!/usr/bin/env bash
# All prototype variants, one after another. Usage: rebuild_all.sh (dev environment loaded)
set -euo pipefail
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
W=/home/erikf/projects/personal/cars-data/truth/maps/net10; d=$(dirname "$(readlink -f "$0")"); B=$d/hv
python3 $d/build.py $W/s1 $W/r12 --join 12 | tail -1 | cut -c1-400
python3 $d/build.py $W/s1 $W/r12p --join 12 --per-node | tail -2 | head -1
mkdir -p $W/r12m $W/r12mb $W/r25m $W/r25mb
python3 $d/merge_tls.py $W/r12p/net.xml $W/r12m/net.xml
python3 $d/open_islands.py $W/r12m/net.xml $W/r12mb/net.xml | cut -c1-120
python3 $d/build.py $W/s1 $W/r25p --join 25 --cluster-max 80 --per-node | tail -2 | head -1
python3 $d/merge_tls.py $W/r25p/net.xml $W/r25m/net.xml
python3 $d/open_islands.py $W/r25m/net.xml $W/r25mb/net.xml | cut -c1-120
for t in r12 r12m r12mb r25m r25mb; do python3 $d/audit.py $W/$t/net.xml $t $W/$t/audit.json > $W/$t/audit.txt; done
python3 $d/missing.py $W/r12m/net.xml $W/r12m/audit.json | cut -c1-170
rm -f $B/rou/r12*.rou.xml $B/rou/r25*.rou.xml $B/nets/r*.net.xml
for t in r12 r12p r12m r12mb r25 r25m r25mb; do s=$W/$t/net.xml; [ -f "$s" ] && cp "$s" $B/nets/$t.net.xml || true; done
