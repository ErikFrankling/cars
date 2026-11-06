#!/bin/bash
# On the homelab through `heavy`: model B, whole day in 30 min periods (F069-F071).
set -e
cargo build --release -p cars-macro 2>&1 | tail -1
mkdir -p .macro-data/runs
target/release/macro .macro-data/${PREP:-prep_ft} .macro-data/runs/bday --model b --period 1800 --iters 30 --reroute 3 --threads ${THREADS:-4} 2>&1 | awk 'NR%3==0'
echo finished bday
