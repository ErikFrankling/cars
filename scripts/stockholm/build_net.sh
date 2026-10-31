#!/usr/bin/env bash
set -euo pipefail
data=${1:-/home/erikf/projects/personal/cars-data/stockholm}
osmium cat "$data/clip.osm.pbf" -o "$data/clip.osm.xml" --overwrite
netconvert --osm-files "$data/clip.osm.xml" -o "$data/stockholm.net.xml" \
 --keep-edges.by-vclass passenger --remove-edges.by-type highway.footway,highway.path,highway.cycleway,highway.steps,highway.pedestrian,highway.service \
 --output.street-names true --tls.guess-signals --tls.default-type actuated --ramps.guess --junctions.join \
 --roundabouts.guess --geometry.remove --remove-edges.isolated \
 --keep-edges.components 1 --junctions.corner-detail 3 --proj.utm \
 > "$data/netconvert.log" 2>&1
