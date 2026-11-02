#!/usr/bin/env bash
# build_driver.sh <driver>: builds that driver's commit with the instrument patch, one job, into the bench store.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
STORE=${BENCH_HOME:-/home/erikf/projects/personal/cars-data/bench}
cfg=$HERE/configs/$1.toml
branch=$(sed -n 's/^branch = "\(.*\)"/\1/p' "$cfg")
patch=$HERE/$(sed -n 's/^patch = "\(.*\)"/\1/p' "$cfg")
commit=$(git -C "$HERE" rev-parse "$branch")
psha=$(sha256sum "$patch" | cut -c1-8)
out=$STORE/bin/$1-${commit:0:8}-$psha
if [ -x "$out" ]; then echo "$out"; exit 0; fi
src=$STORE/src/$1
mkdir -p "$STORE/bin" "$STORE/src"
if [ ! -e "$src/.git" ]; then git -C "$HERE" worktree add --detach "$src" "$commit" >&2; fi
git -C "$src" checkout -q --force --detach "$commit"
git -C "$src" clean -qfd
git -C "$src" apply "$patch"
cd "$src"
CARGO_TARGET_DIR=$STORE/target nice -n 15 cargo build --release -j2 -p cars-cli --bin cars >&2
cp -f "$STORE/target/release/cars" "$out"
echo "$out"
