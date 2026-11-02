#!/usr/bin/env bash
# Fetches open Zenodo trajectory datasets as inert files into fresh directories.
set -u
B=/home/erikf/projects/personal/cars-data/truth/trajectories
get(){ curl -sS -L --fail -A cars-research/1.0 --retry 3 --max-filesize 3900000000 -o "$1" "$2" && echo "ok $1 $(stat -c %s "$1")" || echo "FAILED $1"; }
U=$B/opus-20261031-dlrut; H=$B/opus-20261031-dlrht; S=$B/opus-20261031-swiss; R=$B/opus-20261031-drat
mkdir "$U" "$H" "$S" "$R" || exit 1
for f in README.md DLR-Urban-Traffic-dataset_v1-3-1_documentation.pdf DLR-Urban-Traffic-dataset_v1-3-1.zip; do get "$U/$f" "https://zenodo.org/api/records/20919480/files/$f/content"; done
for f in LICENSE README.md drone_GT.csv; do get "$R/$f" "https://zenodo.org/api/records/20171110/files/$f/content"; done
for f in LICENSE.txt README.md D1_AM1_F2.csv D1_AM3_F2.csv D1_AM5_F2.csv D1_AM7_F2.csv D1_PM1_F2.csv D1_PM3_F2.csv D1_AM2_F1.csv D1_AM4_F1.csv D1_AM6_F1.csv D1_PM2_F1.csv D1_PM4_F1.csv D1_PM5_F1.csv D1_PM6_F1.csv D1_PM7_F1.csv D2_AM1_L1.csv D2_AM2_L1.csv D2_PM1_L1.csv D2_PM2_L1.csv; do get "$S/$f" "https://zenodo.org/api/records/15077435/files/$f/content"; done
for f in DLR-Highway-Traffic-dataset_v1-2-0_documentation.pdf DLR-Highway-Traffic-dataset_v1-2-0.zip; do get "$H/$f" "https://zenodo.org/api/records/18540070/files/$f/content"; done
du -sh "$U" "$H" "$S" "$R"; echo FETCH_DONE
