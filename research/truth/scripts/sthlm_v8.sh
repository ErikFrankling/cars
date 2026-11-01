#!/usr/bin/env bash
# The register-based net of report 07 (maps_recipe.sh) with one change: ramps guessed on 60 km/h motorways, 200 m lanes. usage: sthlm_v8.sh OUTDIR
set -euo pipefail
T=$1; C=/home/erikf/projects/personal/cars-data/stockholm; S=research/truth/scripts
s1=$T/v8_stage1; s2=$T/v8; mkdir -p "$s1" "$s2"
netconvert --osm-files "$C/clip.osm.xml" -o "$s1/net.xml" \
 --keep-edges.by-vclass passenger --remove-edges.by-type highway.footway,highway.path,highway.cycleway,highway.steps,highway.pedestrian,highway.service \
 --output.street-names true --tls.guess-signals --tls.default-type actuated --ramps.guess --junctions.join \
 --roundabouts.guess --geometry.remove --remove-edges.isolated --keep-edges.components 1 --junctions.corner-detail 3 --proj.utm \
 --osm.turn-lanes --osm.lane-access --tls.join --ramps.min-highway-speed 16.6 --ramps.ramp-length 200 \
 --plain-output-prefix "$s1/plain" --no-warnings > "$s1/netconvert.log" 2>&1
python3 -I $S/maps_patch_tls.py "$s1/plain" "$s2/patched.nod.xml" "$s2/patch-report.json"
$S/maps_stage2.sh "$s1" "$s2" "$s2/patched.nod.xml"
for d in 30 12 5; do
 python3 -I $S/maps_split_tls.py "$s2/patched.nod.xml" "$s2/net.xml" "$s2/next.nod.xml" $d
 mv "$s2/next.nod.xml" "$s2/patched.nod.xml"
 $S/maps_stage2.sh "$s1" "$s2" "$s2/patched.nod.xml"
done
