#!/usr/bin/env bash
# The same net and routes in SUMO, for an independent reading of teleports. Usage: sumo_check.sh NET SCALE
W=/home/erikf/projects/personal/cars-data/truth/maps/net10; B=$W/hv; R=$(dirname "$(readlink -f "$0")")/../..; t=$1; sc=$2; o=$W/runs/sumo_${t}_s$sc; mkdir -p "$o"; s=$(date +%s)
timeout ${MAXS:-280} sumo -n "$B/nets/$t.net.xml" -r "$B/rou/${t}_s$sc.rou.xml" --begin 0 --end 4200 --step-length 1 --time-to-teleport 120 --ignore-junction-blocker 20 --seed 1 --no-step-log --duration-log.statistics --collision.action warn --log "$o/log.txt" --error-log "$o/err.txt" > "$o/out.txt" 2>&1
echo "$t $sc exit $? wall $(( $(date +%s)-s ))"; grep -E "Inserted|Running|Waiting|Teleports|Collisions|WaitingTime|TimeLoss|Duration" "$o/out.txt" "$o/log.txt" | sed 's/.*txt://' | sort -u | tr -s ' ' | tr '\n' ';' | cut -c1-300; echo; grep -c "wrong lane" "$o/err.txt"
