#!/usr/bin/env bash
# Sweep DataCite (Zenodo, figshare, Dryad, Dataverse, Mendeley Data, DANS, etc.) with traffic queries. Writes one TSV.
out=${1:-/home/erikf/projects/personal/cars-data/datasets/13-sweep/datacite.tsv}
: > "$out"
while IFS= read -r q; do
  [ -z "$q" ] && continue
  enc=$(jq -rn --arg q "$q" '$q|@uri')
  curl -s --max-time 40 "https://api.datacite.org/dois?query=${enc}&resource-type-id=dataset&page%5Bsize%5D=60&sort=relevance" \
  | jq -r --arg q "$q" '.data[]? | .attributes | [$q, (.titles[0].title // ""), (.publisher|if type=="object" then .name else . end), (.publicationYear|tostring), .doi, ((.sizes//[])|join(";")), ((.rightsList//[])|map(.rightsIdentifier // .rights // "")|join(";")), (((.descriptions//[])[0].description // "")[0:260]|gsub("[\t\n\r]";" "))] | @tsv' >> "$out"
  sleep 0.4
done <<'Q'
"vehicle trajectory" city
"vehicle trajectories" dataset urban
"floating car data"
"probe vehicle" data
"GPS trajectories" taxi
"taxi GPS"
"license plate recognition" traffic
"automatic number plate recognition"
"traffic camera" vehicle trajectories
"electronic toll" trips
"origin-destination" road traffic matrix
"origin-destination" vehicle GPS
"loop detector" traffic data
"traffic signal" timing data
"signal phase" timing dataset
"high-resolution" controller event data signal
"turning movement" counts
"bluetooth" travel time traffic
"drone" vehicle trajectories
"aerial" vehicle trajectories intersection
"connected vehicle" trajectory data
"lane-level" map dataset
"HD map" dataset city
Stockholm traffic
Stockholm GPS vehicles
Stockholm taxi
Sweden road traffic data
Gothenburg traffic
"travel time" urban GPS dataset
"road network" speed dataset city-scale
"traffic speed" dataset city
"mobile phone" origin-destination matrix
"route choice" GPS observed
"map-matched" trajectories
"traffic4cast"
"city brain" traffic
"Didi" trajectories
"Amap" OR "Gaode" traffic
"Baidu" traffic dataset
"ride-hailing" trajectories
"truck" GPS trajectories
"bus" GPS trajectories city
"trajectory" "city-scale" vehicles
"轨迹" 车辆
"交通流" 数据集
"Verkehrsdaten" Trajektorien
"données de trafic" routier
"datos de tráfico"
"verkeersdata"
"trafikdata" OR "trafikflöde"
"プローブ" 交通
Q
wc -l "$out"
cut -f2-5 "$out" | sort -u | wc -l
