#!/usr/bin/env bash
# build_driver.sh <driver> [commit]: builds the branch head or that commit with the instrument patch, into the bench store, and pins the driver to it.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
STORE=${BENCH_HOME:-/home/erikf/projects/personal/cars-data/bench}
cfg=$HERE/configs/$1.toml
branch=$(sed -n 's/^branch = "\(.*\)"/\1/p' "$cfg")
patch=$HERE/$(sed -n 's/^patch = "\(.*\)"/\1/p' "$cfg")
commit=$(git -C "$HERE" rev-parse "${2:-$branch}")
mkdir -p "$STORE/pins"
psha=$(sha256sum "$patch" | cut -c1-8)
out=$STORE/bin/$1-${commit:0:8}-$psha
if [ -x "$out" ]; then echo "$commit" > "$STORE/pins/$1"; echo "$out"; exit 0; fi
src=$STORE/src/$1
mkdir -p "$STORE/bin" "$STORE/src"
if [ ! -e "$src/.git" ]; then git -C "$HERE" worktree add --detach "$src" "$commit" >&2; fi
git -C "$src" checkout -q --force --detach "$commit"
git -C "$src" clean -qfd
git -C "$src" apply --allow-empty "$patch"
cd "$src"
CARGO_TARGET_DIR=$STORE/target nice -n 15 cargo build --release -j2 -p cars-cli --bin cars >&2
cp -f "$STORE/target/release/cars" "$out"
echo "$commit" > "$STORE/pins/$1"
echo "$out"
