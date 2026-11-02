#!/usr/bin/env bash
# Stockholm net build, end to end. Run from the repo root: nix develop --command research/truth/scripts/maps_recipe.sh NAME
set -euo pipefail
name=${1:-recipe}
C=/home/erikf/projects/personal/cars-data/stockholm
M=/home/erikf/projects/personal/cars-data/truth/maps
B=$M/builds; O=$B/osm; W=$M/wfs-20261031; S=research/truth/scripts
mkdir -p "$O" "$W"
[ -s "$W/Signallykta.geojson" ] || python3 -I $S/maps_wfs_fetch.py "$W" Signallykta Signalstolpe Tryckknapp NVDB_Korsning NVDB_Forbjuden_svang NVDB_Kollektivkorfalt NVDB_Cirkulationsplats
[ -s "$O/highway.osm.xml" ] || { osmium tags-filter --overwrite -o "$O/highway.osm.pbf" "$C/clip.osm.pbf" w/highway n/highway n/crossing n/traffic_signals; osmium cat --overwrite -o "$O/highway.osm.xml" "$O/highway.osm.pbf"; }
[ -s "$O/kommun.json" ] || { osmium getid -r --overwrite -o "$O/kommun.osm.xml" "$C/clip.osm.pbf" r398021; python3 -I $S/maps_kommun.py "$O/kommun.osm.xml" "$O/kommun.json"; }
s1=${name}_stage1; s2=$B/$name
$S/maps_build.sh "$s1" --osm.turn-lanes --osm.lane-access --tls.join --plain-output-prefix "$B/$s1/plain"
mkdir -p "$s2"
python3 -I $S/maps_patch_tls.py "$B/$s1/plain" "$s2/patched.nod.xml" "$s2/patch-report.json"
$S/maps_stage2.sh "$B/$s1" "$s2" "$s2/patched.nod.xml"
for d in 30 12 5; do
 python3 -I $S/maps_split_tls.py "$s2/patched.nod.xml" "$s2/net.xml" "$s2/next.nod.xml" $d
 mv "$s2/next.nod.xml" "$s2/patched.nod.xml"
 $S/maps_stage2.sh "$B/$s1" "$s2" "$s2/patched.nod.xml"
done
python3 -I $S/maps_sanity.py "$s2/net.xml" "$name" "$C/stockholm.net.xml" "$C/stockholm.rou.gz" | cut -c1-400
