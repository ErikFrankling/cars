#!/usr/bin/env bash
# Runs on the worker, inside scripts/d8/worker.sh, which brings Mesa's CPU Vulkan driver.
set -e
drv=$1; mode=$2
ROOT=$(pwd)
export BENCH_HOME=$ROOT/.bench-heavy/store
mkdir -p "$BENCH_HOME/bin" "$BENCH_HOME/pins" "$ROOT/.bench-heavy/src/$drv"
commit=$(cat ".bench-heavy/$drv.commit")
echo "$commit" > "$BENCH_HOME/pins/$drv"
patch_file=$(sed -n 's/^patch = "\(.*\)"/\1/p' "scripts/bench/configs/$drv.toml")
psha=$(sha256sum "scripts/bench/$patch_file" | cut -c1-8)
out=$BENCH_HOME/bin/$drv-${commit:0:8}-$psha
if [ ! -x "$out" ]; then
  cd ".bench-heavy/src/$drv"
  rm -rf crates; tar xf "$ROOT/.bench-heavy/$drv.tar"
  patch -p1 < "$ROOT/scripts/bench/$patch_file"
  CARGO_TARGET_DIR=$ROOT/.bench-heavy/target RUSTC_WRAPPER= cargo build --release -p cars-cli --bin cars 2>&1 | tail -1
  cp -f "$ROOT/.bench-heavy/target/release/cars" "$out"
  cd "$ROOT"
fi
export BENCH_COMMIT=$(cat .bench-heavy/bench.commit 2>/dev/null || echo unknown)
python3 -I scripts/bench/bench.py run --driver "$drv" --mode "$mode" --no-dashboard
