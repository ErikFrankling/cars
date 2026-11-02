#!/bin/sh
# Build the Jinan net from the plain files that build_net.py writes. Defaults only: fixed-time signals of
# netconvert's generated 90 s program, because the paper has no signal data.
# usage: build_net.sh SCENARIO_DIR [with-observed]   (with-observed adds the movements the first pass missed)
set -e
s="$1"
con=""
[ "$2" = "with-observed" ] && con="--connection-files $s/observed.con.xml"
netconvert --node-files "$s/jinan.nod.xml" --edge-files "$s/jinan.edg.xml" $con \
  --type-files "$SUMO_HOME/data/typemap/osmNetconvert.typ.xml" \
  --output.street-names false --tls.default-type static --junctions.corner-detail 3 \
  --ignore-errors --no-warnings -o "$s/jinan.net.xml" > "$s/netconvert.log" 2>&1
tail -n 5 "$s/netconvert.log"
ls -la "$s/jinan.net.xml"
