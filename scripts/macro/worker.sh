#!/bin/bash
# On the homelab through `heavy`: build the engine, run it on tables under .macro-data. worker.sh NAME ARGS...
set -e
name=$1; shift
cargo build --release -p cars-macro 2>&1 | tail -1
mkdir -p .macro-data/runs
target/release/macro .macro-data/${PREP:-prep_ft} .macro-data/runs/$name "$@" 2>&1 | awk 'NR%5==0' 
echo finished $name
