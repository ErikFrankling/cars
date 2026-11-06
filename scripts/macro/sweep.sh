#!/bin/bash
# Sensitivity of model A (F074), never a search. sweep.sh PREP OUT
prep=${1:-.macro-data/prep_ft}; out=${2:-.macro-data/runs}
run() { name=$1; shift; grep -q "^done" $out/$name.log 2>/dev/null && return; target/release/macro $prep $out/$name --iters 30 --reroute 3 --threads ${THREADS:-2} "$@" > $out/$name.log 2>&1; echo "$name $(tail -1 $out/$name/iters.tsv)"; }
for a in "s1640 --s 1640" "s1900 --s 1900" "c75 --cycle 75" "c110 --cycle 110" "sat --split sat" "main --split main" "sig05 --sigma .05" "sig30 --sigma .30" "b0 --beta-mult 0" "b2 --beta-mult 2" "base"; do
  set -- $a; n=$1; shift; run sw_${n}_8 --hours 8 "$@"
done
for a in "s1640 --s 1640" "s1900 --s 1900" "b0 --beta-mult 0" "b2 --beta-mult 2" "base"; do
  set -- $a; n=$1; shift; run sw_${n}_16 --hours 16 "$@"
done
