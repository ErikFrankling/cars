#!/usr/bin/env bash
set -euo pipefail
data=${1:-/home/erikf/projects/personal/cars-data/stockholm}
bash scripts/stockholm/build_net.sh "$data"
python3 -I scripts/stockholm/map_counts.py "$data"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -I scripts/stockholm/demand.py "$data"
