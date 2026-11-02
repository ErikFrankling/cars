#!/usr/bin/env bash
# Fetches public US DOT trajectory data as inert files. Run once per fresh directory.
set -u
B=/home/erikf/projects/personal/cars-data/truth/trajectories
T=$B/opus-20261031-tgsim; N=$B/opus-20261031-ngsim
mkdir "$T" "$N" || exit 1
UA='cars-research/1.0'
get(){ curl -sS -L --fail -A "$UA" --retry 3 --max-filesize 3000000000 -o "$1" "$2" && echo "ok $1 $(stat -c %s "$1")" || echo "FAILED $1"; }
for p in 97n2-kuqi:I395 7zjf-a4zf:I294L1 tpsq-zrwa:I294L2 9uas-hf8b:I90stat 6a6e-vfvi:I90mov brzy-6zfh:Foggy; do
  id=${p%%:*}; name=${p##*:}
  get "$T/$name.csv" "https://data.transportation.gov/api/views/$id/rows.csv?accessType=DOWNLOAD"
done
get "$T/report.pdf" "https://rosap.ntl.bts.gov/view/dot/74647/dot_74647_DS1.pdf"
get "$N/lankershim.csv" "https://data.transportation.gov/resource/8ect-6jqj.csv?\$limit=2000000&location=lankershim"
get "$N/peachtree.csv" "https://data.transportation.gov/resource/8ect-6jqj.csv?\$limit=1000000&location=peachtree"
get "$N/Lankershim-doc.zip" "https://data.transportation.gov/api/views/8ect-6jqj/files/62273322-a1e9-48fc-8692-b4c576bafc20?filename=Lankershim-Boulevard-LosAngeles-CA.zip"
get "$N/Peachtree-doc.zip" "https://data.transportation.gov/api/views/8ect-6jqj/files/7244a8b5-077f-4851-bc06-3cfc7a75f0b0?filename=Peachtree-Street-Atlanta-GA.zip"
get "$N/Lankershim_meta.pdf" "https://data.transportation.gov/api/views/8ect-6jqj/files/38de7132-edbb-44ea-b9c5-c53b33317ee5?filename=Lankershim_Blvd_Metadata_Documentation.pdf"
du -sh "$T" "$N"; echo FETCH_DONE
