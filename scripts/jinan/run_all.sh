#!/bin/sh
# The whole ladder on the homelab, small to big, teleports on and off, one job at a time.
# Run through: heavy --big -e LP_NUM_THREADS=4 -- sh scripts/d8/worker.sh sh scripts/jinan/run_all.sh [STAGE...]
# Needs raw/, derived/ and scenario/ copied to scripts/jinan/.data first; never commit that folder.
data=scripts/jinan/.data
mkdir -p "$data/runs"
[ $# = 0 ] && set -- behaviour p001 p010 p030 p100
for stage in "$@"; do
  case "$stage" in
    behaviour) python3 -I scripts/jinan/behaviour.py "$data/raw" "$data/derived" 200000 > "$data/runs/behaviour.txt" 2>&1; tail -n 40 "$data/runs/behaviour.txt"; cp "$data/derived/behaviour.json" "$data/runs/" ;;
    p001) f=0.01 ;;
    p010) f=0.10 ;;
    p030) f=0.30 ;;
    p100) f=1.0 ;;
    *) echo "unknown stage $stage"; continue ;;
  esac
  if [ "$stage" != behaviour ]; then
    for tele in 300 0; do
      echo "=== $stage teleport $tele $(date)"
      sh scripts/jinan/run_one.sh "$data" "$stage" "$f" "$tele"
    done
  fi
done
echo "=== all done $(date)"
