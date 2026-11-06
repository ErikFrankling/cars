#!/bin/bash
# Model A hour by hour, each hour on its own as model A defines it, so one run per hour costs the same as the whole day. ahours.sh PREP OUT H...
prep=$1; out=$2; shift 2
for h in "$@"; do
  grep -q "^done" $out/h$h.log 2>/dev/null && continue
  target/release/macro $prep $out/h$h --model a --hours $h --iters 40 --threads ${THREADS:-2} --reroute 3 > $out/h$h.log 2>&1
  tail -1 $out/h$h/iters.tsv
done
