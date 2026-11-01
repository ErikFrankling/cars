#!/usr/bin/env bash
# Real SUMO 1.28 geometry for the coordinated-intersection model. Run inside `nix develop`.
set -eu
cd "$(dirname "$0")/../fig/09-nets"
common="--grid --default.speed 13.89 --default-junction-type traffic_light --no-turnarounds true --tls.default-type actuated"
for n in 1 2 3; do
  netgenerate $common --grid.x-number 3 --grid.y-number 3 --grid.length 300 --default.lanenumber $n --output-file j$n.net.xml
done
netgenerate $common --grid.x-number 5 --grid.y-number 5 --grid.length 150 --default.lanenumber 1 --output-file grid1.net.xml
netgenerate $common --grid.x-number 5 --grid.y-number 5 --grid.length 150 --default.lanenumber 2 --output-file grid2.net.xml
