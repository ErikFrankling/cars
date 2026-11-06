#!/bin/bash
# On the homelab through `heavy`: sensitivity runs of model A at 08 h and 16 h (F074). sweep.sh
set -e
cargo build --release -p cars-macro 2>&1 | tail -1
mkdir -p .macro-data/runs
run() { name=$1; shift; target/release/macro .macro-data/prep_region .macro-data/runs/$name --iters 45 --reroute 3 --threads ${THREADS:-4} "$@" 2>&1 | tail -1; echo finished $name; }
for h in 8 16; do
  run sw_s1640_$h --hours $h --s 1640
  run sw_s1900_$h --hours $h --s 1900
  run sw_c75_$h --hours $h --cycle 75
  run sw_c110_$h --hours $h --cycle 110
  run sw_sat_$h --hours $h --split sat
  run sw_main_$h --hours $h --split main
  run sw_sig05_$h --hours $h --sigma .05
  run sw_sig30_$h --hours $h --sigma .30
  run sw_b0_$h --hours $h --beta-mult 0
  run sw_b2_$h --hours $h --beta-mult 2
done
