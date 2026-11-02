#!/bin/sh
# One Jinan run on CPU Vulkan, then its comparison with the data.
# usage: run_one.sh DATA_DIR NAME FRACTION TELEPORT_S [END_S]
#   DATA_DIR holds raw/, derived/, scenario/. NAME is p001, p010, p030, p100.
# Results go to DATA_DIR/runs/NAME_tTELEPORT/.
data="$1"; name="$2"; frac="$3"; tele="$4"; end="${5:-90000}"
run="$data/runs/${name}_t${tele}"
mkdir -p "$run"
start=$(date +%s)
target/release/cars run --net "$data/scenario/jinan.net.xml" --routes "$data/scenario/$name.rou.xml" \
  --dt 1 --begin 0 --end "$end" --seed 1 --time-to-teleport "$tele" \
  --edge-csv "$run/edges.csv" --edge-interval 3600 --trip-csv "$run/trips.csv" --summary-csv "$run/summary.csv" \
  > "$run/stdout.txt" 2> "$run/stderr.txt"
code=$?
echo "exit $code wall $(( $(date +%s) - start )) s threads ${LP_NUM_THREADS:-unset}" | tee "$run/wall.txt"
tail -n 12 "$run/stdout.txt"; tail -n 5 "$run/stderr.txt"
[ "$code" = 0 ] && python3 -I scripts/jinan/compare.py "$data/raw" "$data/derived" "$data/scenario" "$run" "$frac" > "$run/compare.txt" 2>&1
tail -c 600 "$run/compare.txt"
exit $code
