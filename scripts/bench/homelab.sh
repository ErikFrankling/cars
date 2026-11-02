#!/usr/bin/env bash
# Full-mode runs on the homelab. On this PC: scripts/bench/homelab.sh DRIVER [MODE]. Packs that driver's pinned commit
# next to the repo copy, runs through heavy, then pulls the result into the bench store.
set -e
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
drv=$1; mode=${2:-full}
STORE=${BENCH_HOME:-/home/erikf/projects/personal/cars-data/bench}
commit=$(cat "$STORE/pins/$drv")
mkdir -p .bench-heavy
git archive --format=tar -o ".bench-heavy/$drv.tar" "$commit" crates Cargo.toml Cargo.lock
echo "$commit" > ".bench-heavy/$drv.commit"
heavy --big -- scripts/d8/worker.sh bash scripts/bench/homelab_job.sh "$drv" "$mode"
heavy pull ".bench-heavy/store/results" && cp -n .bench-heavy/store/results/*.json "$STORE/results/"
