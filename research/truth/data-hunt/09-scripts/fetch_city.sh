#!/usr/bin/env bash
# Open Stockholm WFS layers used by report 09. Writes into $1. No key needed.
set -eu
O=$1; mkdir -p "$O"
B="https://apigw.stockholm.se/Open/VirtialOpenDataGeoServerDMZ.svc/Rest/api/wfs"
get() { curl -sS -m 500 -G "$B" --data-urlencode service=WFS --data-urlencode version=1.1.0 --data-urlencode request=GetFeature \
  --data-urlencode "typeName=$1" --data-urlencode outputFormat=application/json ${3:+--data-urlencode "CQL_FILTER=$3"} -o "$O/$2.geojson"; ls -la "$O/$2.geojson"; }
Q="VALID_TO IS NULL AND (TITLE LIKE '%enkelriktad%' OR TITLE LIKE '%körfält%' OR TITLE LIKE '%körbana%' OR TITLE LIKE '%körriktning%' OR TITLE LIKE '%sväng%' OR TITLE LIKE '%infart%' OR TITLE LIKE '%förbud mot trafik%' OR TITLE LIKE '%gågata%' OR TITLE LIKE '%väjningsplikt%' OR TITLE LIKE '%cirkulationsplats%' OR TITLE LIKE '%cykelgata%')"
get ltfr:LTFR_FORESKRIFT ltfr_rules "$Q"
BB="BBOX(GEOMETRY,146000,6574000,158000,6586000)"
get od_gis:NVDB_Vagbredd nvdb_width "$BB"
get od_gis:NVDB_Hastighetsgrans nvdb_speed "$BB"
get od_gis:NVDB_Gatutyp nvdb_gatutyp "$BB"
get od_gis:NVDB_Kollektivkorfalt nvdb_bus
get od_gis:NVDB_Forbjuden_svang nvdb_turnban
get od_gis:NVDB_Cirkulationsplats nvdb_ring
