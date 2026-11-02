#!/usr/bin/env bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
set -euo pipefail
W=/home/erikf/projects/personal/cars-data/truth/maps/net10
d=$(dirname "$(readlink -f "$0")")
tag=$1; shift
python3 "$d/build.py" $W/s1 $W/$tag "$@"
python3 "$d/audit.py" $W/$tag/net.xml $tag $W/$tag/audit.json
