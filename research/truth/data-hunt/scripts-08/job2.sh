#!/bin/sh
set -x
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY="python3 -I"
$PY build_demands.py in/ out/sysmo.npz.json out 2>&1 | grep -v -E "Warning|^  "
$PY run_od.py net.npz out/d_W.npz W
CELL=250 $PY run_od.py net.npz out/d_S.npz S250
$PY score.py net.npz screens.npz out/flow_W_ff.npz out/flow_S250_ff.npz
cp screens.npz.scores.json out/scores2.json
$PY cmp_counts.py net.npz in/cal.csv out/flow_W_ff.npz out/flow_S250_ff.npz
cp out/counts_cmp.json out/counts_cmp2.json
mkdir -p zen
curl -sL --retry 2 -m 200 -o zen/plans0.parquet https://zenodo.org/api/records/10648078/files/2_plans_0.parquet/content
curl -sL --retry 2 -m 200 -o zen/pop.parquet https://zenodo.org/api/records/10648078/files/1_syn_pop_all.parquet/content
$PY zen_peek.py zen/plans0.parquet zen/pop.parquet
rm -rf zen
echo JOB2-DONE
