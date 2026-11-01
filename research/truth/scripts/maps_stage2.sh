#!/usr/bin/env bash
# Rebuilds a net from plain files with a patched node file; every signal program is regenerated. Usage: maps_stage2.sh STAGE1_DIR OUT_DIR PATCHED.nod.xml [extra options]
set -euo pipefail
s=$1;o=$2;n=$3;shift 3;mkdir -p "$o"
netconvert --node-files "$n" --edge-files "$s/plain.edg.xml" --connection-files "$s/plain.con.xml" --type-files "$s/plain.typ.xml" \
 --output.street-names true --tls.default-type actuated --junctions.corner-detail 3 --offset.disable-normalization true -o "$o/net.xml" "$@" > "$o/netconvert.log" 2>&1
tail -n 1 "$o/netconvert.log" | cut -c1-200
