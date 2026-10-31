#!/usr/bin/env bash
# Every thesis sweep on the GPU: tiers x 21 penetrations x 3 seeds. Writes results/thesis/*.csv and wall times.
cd "$(dirname "$0")/.." || exit 1
BIN=${1:-target/release/sweep}
mkdir -p results/thesis
P=0,0.05,0.1,0.15,0.2,0.25,0.3,0.35,0.4,0.45,0.5,0.55,0.6,0.65,0.7,0.75,0.8,0.85,0.9,0.95,1
: > results/thesis/wall.txt
for s in ring:krauss,idm,acc,cacc glosa_two_signal:krauss,idm,acc,cacc,glosa i80_vsl:krauss,idm,acc,cacc bologna:krauss,idm,acc,cacc,glosa; do
  n=${s%%:*}; t=${s##*:}
  flock /tmp/cars-gpu.lock "$BIN" --scenario "$n" --tiers "$t" --penetrations $P --seeds 0,1,2 --out "results/thesis/$n.csv" 2>&1 | tail -2 | tee -a results/thesis/wall.txt
  echo "scenario $n" >> results/thesis/wall.txt
done
