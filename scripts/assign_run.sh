#!/usr/bin/env bash
# assign_run.sh SCENARIO OUT ITERS CHUNK [loop flags]. Takes the GPU lock per chunk, so that other jobs get a turn,
# and retries after a kill: the loop resumes from its checkpoint.
set -u
scenario=$1; out=$2; iters=$3; chunk=$4; shift 4
bin=${ASSIGN_BIN:-target/release/assign}
fails=0
while :; do
    if ! msg=$(flock /tmp/cars-gpu.lock "$bin" --scenario "$scenario" --out "$out" loop --iters "$iters" --chunk "$chunk" "$@" 2>>"$out.log"); then
        fails=$((fails + 1))
        echo "attempt failed ($fails), see $out.log" >&2
        [ "$fails" -ge 8 ] && exit 1
        sleep 60
        continue
    fi
    fails=0
    [ "$msg" = "done" ] && break
    sleep 2
done
tail -1 "$out/iters.csv"
