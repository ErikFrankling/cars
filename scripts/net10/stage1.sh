#!/usr/bin/env bash
# Stage 1 of the register-first net: OSM to plain files, with real lanes and bus lanes. Usage: stage1.sh OSM OUT_DIR
set -euo pipefail
o=$1; d=$2; mkdir -p "$d"
netconvert --osm-files "$o" -o "$d/stage1.net.xml" --plain-output-prefix "$d/s1" \
  --keep-edges.in-geo-boundary 18.018,59.322,18.085,59.350 \
  --keep-edges.by-vclass passenger \
  --remove-edges.by-type highway.footway,highway.path,highway.cycleway,highway.steps,highway.pedestrian,highway.service \
  --output.street-names true --tls.guess-signals --tls.default-type actuated \
  --ramps.guess --ramps.min-highway-speed 16.6 --ramps.ramp-length 200 \
  --junctions.join --junctions.join-dist 15 --roundabouts.guess --geometry.remove --remove-edges.isolated \
  --keep-edges.components 1 --junctions.corner-detail 3 --proj.utm --osm.turn-lanes --osm.lane-access --no-warnings true
