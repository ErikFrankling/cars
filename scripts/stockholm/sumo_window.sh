#!/usr/bin/env bash
set -euo pipefail
data=${1:-/home/erikf/projects/personal/cars-data/stockholm}
begin=${2:-25200}
end=${3:-28800}
cat > "$data/sumo.add.xml" <<XML
<additional><edgeData id="counts" file="$data/sumo.edges.xml" period="3600" excludeEmpty="false"/></additional>
XML
sumo --net-file "$data/stockholm.net.xml" --route-files "$data/stockholm.rou.gz" \
 --additional-files "$data/sumo.add.xml" --begin "$begin" --end "$end" \
 --time-to-teleport 120 --ignore-junction-blocker 20 --step-length 1 \
 --summary-output "$data/sumo.summary.xml" --tripinfo-output "$data/sumo.trips.xml" \
 --duration-log.statistics --no-step-log > "$data/sumo.log" 2>&1
python3 -I scripts/stockholm/validate.py "$data" sumo
