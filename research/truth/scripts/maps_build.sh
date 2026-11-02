#!/usr/bin/env bash
# Usage: maps_build.sh NAME [extra netconvert options]. Runs the Stockholm build of scripts/stockholm/build_net.sh plus the extras.
set -euo pipefail
name=$1; shift
data=/home/erikf/projects/personal/cars-data/stockholm
out=/home/erikf/projects/personal/cars-data/truth/maps/builds/$name
mkdir -p "$out"
/nix/store/6vrl8gs1971k9p913mq5y041mpscvbss-time-1.10/bin/time -v netconvert --osm-files "$data/clip.osm.xml" -o "$out/net.xml" \
 --keep-edges.by-vclass passenger --remove-edges.by-type highway.footway,highway.path,highway.cycleway,highway.steps,highway.pedestrian,highway.service \
 --output.street-names true --tls.guess-signals --tls.default-type actuated --ramps.guess --junctions.join \
 --roundabouts.guess --geometry.remove --remove-edges.isolated \
 --keep-edges.components 1 --junctions.corner-detail 3 --proj.utm "$@" > "$out/netconvert.log" 2>&1
grep -E 'Maximum resident|Elapsed' "$out/netconvert.log" || true
tail -n 3 "$out/netconvert.log" | cut -c1-200
