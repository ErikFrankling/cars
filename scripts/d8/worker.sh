#!/bin/sh
# Inside `heavy`: the worker has no Vulkan driver of its own, so bring Mesa's CPU one.
set -e
for p in $(nix build --no-link --print-out-paths nixpkgs#mesa 2>/dev/null); do
  f=$(ls "$p"/share/vulkan/icd.d/lvp_icd.*.json 2>/dev/null | head -1 || true)
  [ -n "$f" ] && export VK_DRIVER_FILES="$f"
done
echo "driver: $VK_DRIVER_FILES"
export CARS_ADAPTER=llvmpipe
export LP_NUM_THREADS=${LP_NUM_THREADS:-1}
RUSTC_WRAPPER= cargo build --release 2>&1 | tail -1
exec "$@"
