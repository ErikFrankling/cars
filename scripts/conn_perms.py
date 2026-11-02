#!/usr/bin/env python3
"""allow/disallow on <connection>, against SUMO, on one junction.

wc has two lanes. wc_0 -> ce_0 bans passenger, wc_1 -> ce_1 is free, wc_1 -> cn_0 is bus only.
Passenger cars must reach ce from lane 1, must lose the explicit route wc cn, and must route
wc to nx around the ban through ce en. Buses may use all of it.
"""

import csv
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARS = ROOT / "target/release/cars"

NODES = """<nodes><node id="w" x="-300" y="0"/><node id="c" x="0" y="0" type="priority"/><node id="e" x="300" y="0"/>
<node id="n" x="0" y="300"/><node id="x" x="0" y="600"/></nodes>"""
EDGES = """<edges><edge id="wc" from="w" to="c" numLanes="2" speed="13.89"/><edge id="ce" from="c" to="e" numLanes="2" speed="13.89"/>
<edge id="cn" from="c" to="n" speed="13.89"/><edge id="en" from="e" to="n" speed="13.89"/><edge id="nx" from="n" to="x" speed="13.89"/></edges>"""
CONS = """<connections><connection from="wc" to="ce" fromLane="0" toLane="0" disallow="passenger"/>
<connection from="wc" to="ce" fromLane="1" toLane="1"/>
<connection from="wc" to="cn" fromLane="1" toLane="0" allow="bus"/></connections>"""
ROUTES = """<routes>
<vType id="car" vClass="passenger" sigma="0" length="5" speedDev="0"/>
<vType id="bus" vClass="bus" sigma="0" length="5" speedDev="0"/>
<route id="straight" edges="wc ce"/>
<route id="banned" edges="wc cn nx"/>
<flow id="car_lane0" type="car" route="straight" departLane="0" departSpeed="0" begin="0" end="100" number="5"/>
<flow id="car_best" type="car" route="straight" departLane="best" departSpeed="0" begin="200" end="300" number="5"/>
<flow id="bus_lane0" type="bus" route="straight" departLane="0" departSpeed="0" begin="400" end="500" number="5"/>
<flow id="car_banned" type="car" route="banned" departLane="best" departSpeed="0" begin="600" end="700" number="5"/>
<flow id="bus_banned" type="bus" route="banned" departLane="best" departSpeed="0" begin="800" end="900" number="5"/>
<flow id="car_trip" type="car" from="wc" to="nx" departLane="best" departSpeed="0" begin="1000" end="1100" number="5"/>
<flow id="bus_trip" type="bus" from="wc" to="nx" departLane="best" departSpeed="0" begin="1200" end="1300" number="5"/>
</routes>"""
END = "1800"


def run(cmd, check=True):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"failed: {cmd}\n{r.stdout}\n{r.stderr}")
    return r.stdout + r.stderr


def flow(vehicle):
    return vehicle.rsplit(".", 1)[0]


def collapse(lanes):
    # One second samples can skip a short internal lane, so paths compare on normal lanes.
    return " ".join(l for l in lanes if not l.startswith(":"))


def sumo(d):
    # SUMO refuses the whole run on a route it finds disconnected, so that flow goes on its own.
    # --ignore-route-errors is no help: it turns the check off and the car teleports across.
    rejected = run(["sumo", "-n", d / "net.xml", "-r", d / "banned.rou.xml", "--end", END, "--no-step-log", "true"], check=False)
    out = run(["sumo", "-n", d / "net.xml", "-r", d / "s.rou.xml", "--end", END, "--no-step-log", "true",
               "--fcd-output", d / "s.xml", "--seed", "1"])
    seen = defaultdict(list)
    for step in ET.parse(d / "s.xml").getroot():
        for v in step:
            path = seen[v.get("id")]
            if not path or path[-1] != v.get("lane"):
                path.append(v.get("lane"))
    return seen, rejected


def cars(d):
    out = run([CARS, "run", "--net", d / "net.xml", "--routes", d / "r.rou.xml", "--dt", "1", "--end", END, "--seed", "1",
               "--fcd", d / "g.csv", "--fcd-interval", "1"])
    seen = defaultdict(list)
    with open(d / "g.csv") as f:
        for row in csv.DictReader(f):
            path = seen[row["trip"]]
            if not path or path[-1] != row["lane"]:
                path.append(row["lane"])
    return seen, out


def summarize(seen):
    result = defaultdict(lambda: defaultdict(int))
    for vehicle, path in seen.items():
        result[flow(vehicle)][tuple(path)] += 1
    return result


def main():
    d = Path(tempfile.mkdtemp(prefix="conn-perms-"))
    for name, body in [("n.nod.xml", NODES), ("n.edg.xml", EDGES), ("n.con.xml", CONS), ("r.rou.xml", ROUTES)]:
        (d / name).write_text(body)
    run(["netconvert", "-n", d / "n.nod.xml", "-e", d / "n.edg.xml", "-x", d / "n.con.xml", "-o", d / "net.xml", "--no-turnarounds"])
    lines = ROUTES.splitlines()
    (d / "s.rou.xml").write_text("\n".join(l for l in lines if 'id="car_banned"' not in l))
    (d / "banned.rou.xml").write_text("\n".join(l for l in lines if 'type=' not in l or 'id="car_banned"' in l))
    s, rejected = sumo(d)
    g, g_log = cars(d)
    ss, gs = summarize(s), summarize(g)
    bad = []
    for f in ["car_lane0", "car_best", "bus_lane0", "car_banned", "bus_banned", "car_trip", "bus_trip"]:
        sp, gp = defaultdict(int), defaultdict(int)
        for k, v in ss[f].items():
            sp[collapse(k)] += v
        for k, v in gs[f].items():
            gp[collapse(k)] += v
        sp, gp = dict(sp), dict(gp)
        print(f"{f}\n  sumo {sp}\n  cars {gp}")
        if sp != gp:
            bad.append(f)
    # A banned way as passenger, in either simulator, is the failure this script exists for.
    for label, runs in (("sumo", ss), ("cars", gs)):
        for f in ("car_lane0", "car_best", "car_banned", "car_trip"):
            for path in runs[f]:
                text = collapse(path)
                if "wc_0 ce_0" in text or "wc_1 cn_0" in text or "wc_0 cn_0" in text:
                    bad.append(f"{label}:{f} drove a ban: {text}")
    if gs["car_banned"]:
        bad.append("cars drove car_banned")
    if "No connection between edge 'wc' and edge 'cn'" not in rejected:
        bad.append(f"sumo accepted car_banned: {rejected}")
    m = re.search(r"dropped (DropCounts \{[^}]*\})", g_log)
    print("cars", m.group(1) if m else "no drop line")
    print("sumo on car_banned:", next(l for l in rejected.splitlines() if "No connection" in l or "rror" in l))
    if "banned_connection: 5" not in g_log:
        bad.append("drop counter")
    print(f"dir {d}")
    print("FAILED:" if bad else "ALL OK", bad)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
