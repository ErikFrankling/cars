#!/usr/bin/env bash
# One round of seed hunting: hunt.sh NAME FACTOR BEGIN END [flags]. Traces with reasons, then lists the first and the largest roots and why each stopped.
B=/home/erikf/projects/personal/cars-data/berlin2019
n=$1; f=$2; b=$3; e=$4; shift 4
bin=${BIN:-$B/build/cars-main7}; o=$B/runs/hunt_$n; mkdir -p "$o"; cd "$o" || exit 1
"$bin" run --net "${NETF:-$B/district/m12/net.net.xml}" --routes "${ROUTES:-$B/district/m10/routes_f$f.rou.gz}" --dt "${DT:-1}" --begin "$b" --end "$e" --capacity 70000 --trusted --time-to-teleport 0 --trace f.trace --trace-stride 30 --why --summary-csv s.csv --edge-csv edges.csv --edge-interval 900 "$@" > o.txt 2> e.txt
awk -F, 'NR>1 && $1%1800==0{printf "%d:%s ",$1/3600*10,$2}' s.csv; echo
grep -E "^physics:" e.txt | tail -n1 | cut -c1-210
"$bin" jam --trace f.trace --seeds --stride 30 2>&1 | grep -E "first blocked|seeds with" | cut -c1-170
python3 -I - <<'PY'
import json,collections
d=json.load(open("jam/seeds.json"))
c=collections.Counter();e=collections.Counter()
for x in d["top"]:
    k=x["where"].get("decider") or max(x["kinds"],key=x["kinds"].get)
    c[k]+=round(x["vehicle_hours"]);e[k]+=x["eventual"]
print("roots",d["seeds"],"veh-h",c.most_common(),"cars held",e.most_common())
top=sorted(d["top"],key=lambda x:x["first"])[:3]+d["top"][:3]
seen=set()
with open("cars.txt","w") as f:
    for x in top:
        if x["car"] not in seen:
            seen.add(x["car"]); f.write(f'{x["car"]} {int(x["first"])}\n')
PY
while read -r c t; do "$bin" why --trace f.trace --car "$c" --at "$t" 2>&1 | grep -vE "limits,|^$|chart|table" | cut -c1-175 | sed -n 1,6p; echo; done < cars.txt
