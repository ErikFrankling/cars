#!/bin/sh
# A short time window on the urban-speed net, on this PC's CPU Vulkan.
# usage: run_window.sh SCENARIO_URBAN_DIR ROUTES OUT_DIR BEGIN END TELEPORT
s="$1"; routes="$2"; run="$3"; begin="$4"; end="$5"; tele="$6"
for p in $(nix build --no-link --print-out-paths nixpkgs#mesa 2>/dev/null); do
  f=$(ls "$p"/share/vulkan/icd.d/lvp_icd.*.json 2>/dev/null | head -1 || true)
  [ -n "$f" ] && export VK_DRIVER_FILES="$f"
done
export CARS_ADAPTER=llvmpipe LP_NUM_THREADS=${LP_NUM_THREADS:-3}
mkdir -p "$run"
start=$(date +%s)
target/release/cars run --net "$s/jinan.net.xml" --routes "$routes" --dt 1 --begin "$begin" --end "$end" --seed 1 \
  --time-to-teleport "$tele" --edge-csv "$run/edges.csv" --edge-interval 3600 --trip-csv "$run/trips.csv" --summary-csv "$run/summary.csv" \
  > "$run/stdout.txt" 2> "$run/stderr.txt"
echo "exit $? wall $(( $(date +%s) - start )) s" | tee "$run/wall.txt"
tail -n 2 "$run/stderr.txt" | cut -c1-220
tail -n 1 "$run/stdout.txt" | cut -c1-220
