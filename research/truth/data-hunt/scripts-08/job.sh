#!/bin/sh
set -x
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
mkdir -p out
PY="python3 -I"
A=https://data.mendeley.com/public-files/datasets/9n29p7rmn5/files/753acc25-93f0-4af3-89e7-78b9296139f5/file_downloaded
P=https://data.mendeley.com/public-files/datasets/9n29p7rmn5/files/86cbb09b-76e7-43ca-942a-ab436d257277/file_downloaded
[ -s in/cal.csv ] || $PY arstrafik_cal.py in/arstrafik.body in/holdout.csv in/cal.csv
if [ ! -s out/sysmo.npz.json ]; then
  curl -sL --retry 3 -o in/Person.csv "$P"
  curl -sL --retry 3 "$A" | $PY sysmo_extract.py /dev/stdin in/Person.csv out/sysmo.npz || exit 1
  rm -f in/Person.csv
fi
$PY build_demands.py in/ out/sysmo.npz.json out || exit 2
$PY sysmo_to_d.py
for r in in/v2_full.rou.gz in/v8_full.rou.gz in/stockholm.rou.gz; do n=$(basename $r .rou.gz); $PY routes_flow.py net.npz $r out/flow_$n.npz; done
$PY run_od.py net.npz out/d_S.npz S msa > out/log_S.txt 2>&1
$PY run_od.py net.npz out/d_G1.npz G1 msa > out/log_G1.txt 2>&1
$PY run_od.py net.npz out/d_G0.npz G0 > out/log_G0.txt 2>&1
$PY run_od.py net.npz out/d_G1W.npz G1W > out/log_G1W.txt 2>&1
$PY run_od.py net.npz out/d_W.npz W > out/log_W.txt 2>&1
cat out/log_*.txt
$PY score.py net.npz screens.npz out/flow_*.npz
cp screens.npz.scores.json out/scores.json
$PY cmp_counts.py net.npz in/cal.csv out/flow_*.npz
echo JOB-DONE
