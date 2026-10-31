#!/usr/bin/env python3
"""SUMO comparisons: single-lane trajectories, multi-lane aggregates and --i80.

Multi-lane discharge flow uses arrivals in [60, 180) seconds (veh/h).
The aggregate gates intentionally fail until the requested tolerances are met.
"""

import argparse
import csv
import math
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARS = ROOT / "target/release/cars"

VTYPES = """
<vType id="krauss0" vClass="passenger" carFollowModel="Krauss" sigma="0" length="5" minGap="2.5" accel="2.6" decel="4.5" tau="1" speedDev="0"/>
<vType id="krauss" vClass="passenger" carFollowModel="Krauss" sigma="0.5" length="5" minGap="2.5" accel="2.6" decel="4.5" tau="1" speedDev="0"/>
<vType id="idm" vClass="passenger" carFollowModel="IDM" length="5" minGap="2.5" accel="2.6" decel="2.0" emergencyDecel="4.5" tau="1" speedDev="0"/>
<vType id="acc" vClass="passenger" carFollowModel="ACC" length="5" minGap="2" accel="1" tau="1.5" maxSpeed="33.33" speedDev="0"/>
<vType id="cacc" vClass="passenger" carFollowModel="CACC" length="5" minGap="1" accel="1" tau="0.6" maxSpeed="33.33" speedDev="0"><param key="headwayTimeACC" value="1.5"/></vType>
"""


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"failed: {' '.join(map(str, cmd))}\n{r.stdout}\n{r.stderr}")
    return r


def straight(d, length=2000, lanes=1, speed=13.89):
    nodes = '<nodes><node id="a" x="0" y="0"/><node id="b" x="%f" y="0"/><node id="c" x="%f" y="0"/></nodes>' % (length, length * 2)
    edges = (
        '<edges><edge id="ab" from="a" to="b" numLanes="%d" speed="%f"/>'
        '<edge id="bc" from="b" to="c" numLanes="%d" speed="%f"/></edges>' % (lanes, speed, lanes, speed)
    )
    (d / "n.nod.xml").write_text(nodes)
    (d / "n.edg.xml").write_text(edges)
    run(["netconvert", "-n", d / "n.nod.xml", "-e", d / "n.edg.xml", "-o", d / "net.xml", "--no-turnarounds"])


def cross(d, tls=False, arm=500, speed=13.89, jtype=None):
    jt = jtype or ("traffic_light" if tls else "priority")
    nodes = (
        '<nodes><node id="c" x="0" y="0" type="%s"/><node id="w" x="%d" y="0"/><node id="e" x="%d" y="0"/>'
        '<node id="s" x="0" y="%d"/><node id="n" x="0" y="%d"/></nodes>' % (jt, -arm, arm, -arm, arm)
    )
    edges = "<edges>"
    for a, b, pr in [("w", "c", 2), ("c", "e", 2), ("e", "c", 2), ("c", "w", 2), ("s", "c", 1), ("c", "n", 1), ("n", "c", 1), ("c", "s", 1)]:
        edges += '<edge id="%s%s" from="%s" to="%s" priority="%d" numLanes="1" speed="%f"/>' % (a, b, a, b, pr, speed)
    edges += "</edges>"
    (d / "n.nod.xml").write_text(nodes)
    (d / "n.edg.xml").write_text(edges)
    run(["netconvert", "-n", d / "n.nod.xml", "-e", d / "n.edg.xml", "-o", d / "net.xml", "--no-turnarounds"])


def routes(d, body):
    (d / "r.rou.xml").write_text("<routes>" + VTYPES + body + "</routes>")


SCENARIOS = {}


def scenario(f):
    SCENARIOS[f.__name__] = f
    return f


def platoon(d, vtype, dt, lead_stop=False):
    straight(d)
    body = '<route id="r" edges="ab bc"/>'
    for i in range(6):
        body += f'<vehicle id="v{i}" type="{vtype}" route="r" depart="{i * 4}" departSpeed="0"/>'
    routes(d, body)
    return dt, 300


@scenario
def platoon_krauss0_1(d):
    return platoon(d, "krauss0", 1.0)
@scenario
def platoon_krauss0_01(d):
    return platoon(d, "krauss0", 0.1)
@scenario
def platoon_idm_1(d):
    return platoon(d, "idm", 1.0)
@scenario
def platoon_idm_01(d):
    return platoon(d, "idm", 0.1)
@scenario
def platoon_acc_1(d):
    return platoon(d, "acc", 1.0)
@scenario
def platoon_acc_01(d):
    return platoon(d, "acc", 0.1)
@scenario
def platoon_cacc_01(d):
    return platoon(d, "cacc", 0.1)


def red_light(d, vtype, dt):
    cross(d, tls=True)
    body = '<route id="we" edges="wc ce"/><route id="ns" edges="nc cs"/>'
    for i in range(5):
        body += f'<vehicle id="we{i}" type="{vtype}" route="we" depart="{i * 3}" departSpeed="max"/>'
    for i in range(3):
        body += f'<vehicle id="ns{i}" type="{vtype}" route="ns" depart="{40 + i * 3}" departSpeed="max"/>'
    routes(d, body)
    return dt, 200


@scenario
def tls_krauss0_1(d):
    return red_light(d, "krauss0", 1.0)
@scenario
def tls_idm_01(d):
    return red_light(d, "idm", 0.1)


def yield_minor(d, vtype, dt):
    cross(d)
    body = '<route id="we" edges="wc ce"/><route id="sn" edges="sc cn"/>'
    for i in range(10):
        body += f'<vehicle id="we{i}" type="{vtype}" route="we" depart="{i * 6}" departSpeed="max"/>'
    for i in range(4):
        body += f'<vehicle id="sn{i}" type="{vtype}" route="sn" depart="{5 + i * 2}" departSpeed="max"/>'
    routes(d, body)
    return dt, 200


@scenario
def priority_krauss0_1(d):
    return yield_minor(d, "krauss0", 1.0)
@scenario
def priority_idm_01(d):
    return yield_minor(d, "idm", 0.1)



MACRO = set()


def macro(f):
    MACRO.add(f.__name__)
    return scenario(f)


def multilane_net(d, nodes, edges, connections=""):
    (d / "n.nod.xml").write_text("<nodes>" + nodes + "</nodes>")
    (d / "n.edg.xml").write_text("<edges>" + edges + "</edges>")
    cmd = ["netconvert", "-n", d / "n.nod.xml", "-e", d / "n.edg.xml", "-o", d / "net.xml", "--no-turnarounds"]
    if connections:
        (d / "n.con.xml").write_text("<connections>" + connections + "</connections>")
        cmd += ["-x", d / "n.con.xml"]
    run(cmd)


@macro
def multi_overtake(d):
    straight(d, length=800, lanes=2, speed=25)
    body = '<vType id="slow" carFollowModel="IDM" maxSpeed="10" speedDev="0"/>'
    body += '<route id="r" edges="ab bc"/>'
    body += '<vehicle id="slow" type="slow" route="r" depart="0" departLane="0" departSpeed="max"/>'
    for i in range(12):
        body += f'<vehicle id="v{i}" type="idm" route="r" depart="{2+i*3}" departLane="0" departSpeed="max"/>'
    routes(d, body)
    return 1, 250


@macro
def multi_drop(d):
    multilane_net(d, '<node id="a" x="0" y="0"/><node id="b" x="600" y="0"/><node id="c" x="1200" y="0"/>',
                   '<edge id="ab" from="a" to="b" numLanes="3" speed="25"/><edge id="bc" from="b" to="c" numLanes="2" speed="25"/>')
    routes(d, '<route id="r" edges="ab bc"/><flow id="f" type="idm" route="r" begin="0" end="180" period="0.7" departLane="free" departSpeed="max"/>')
    return 1, 400


def merge(d, period):
    # An acceleration lane followed by a lane drop; the ramp joins without
    # crossing the mainline, then negotiates into it using lane changing.
    multilane_net(d, '<node id="a" x="0" y="0"/><node id="r" x="300" y="-200"/><node id="b" x="600" y="0"/><node id="c" x="1000" y="0"/><node id="d" x="1600" y="0"/>',
                   '<edge id="ab" from="a" to="b" numLanes="2" speed="25" priority="2"/><edge id="rb" from="r" to="b" numLanes="1" speed="20" priority="1"/><edge id="bc" from="b" to="c" numLanes="3" speed="25"/><edge id="cd" from="c" to="d" numLanes="2" speed="25"/>',
                   '<connection from="ab" to="bc" fromLane="0" toLane="1"/><connection from="ab" to="bc" fromLane="1" toLane="2"/><connection from="rb" to="bc" fromLane="0" toLane="0"/><connection from="bc" to="cd" fromLane="1" toLane="0"/><connection from="bc" to="cd" fromLane="2" toLane="1"/>')
    routes(d, f'<route id="m" edges="ab bc cd"/><route id="r" edges="rb bc cd"/><flow id="m" type="idm" route="m" begin="0" end="150" period="{period}" departLane="free" departSpeed="max"/><flow id="r" type="idm" route="r" begin="0" end="150" period="4" departSpeed="max"/>')
    return 1, 400


@macro
def multi_merge_low(d):
    return merge(d, 3)


@macro
def multi_merge_high(d):
    return merge(d, 1)


@macro
def multi_turns(d):
    nodes = '<node id="c" x="0" y="0" type="traffic_light"/>'
    points = dict(w=(-400, 0), e=(400, 0), s=(0, -400), n=(0, 400))
    edges = ""
    for a, (x, y) in points.items():
        nodes += f'<node id="{a}" x="{x}" y="{y}"/>'
        edges += f'<edge id="{a}c" from="{a}" to="c" numLanes="3" speed="14"/><edge id="c{a}" from="c" to="{a}" numLanes="3" speed="14"/>'
    connections = ""
    body = ""
    for a, destinations in dict(w="sen", e="nws", s="enw", n="wse").items():
        for k, b in enumerate(destinations):
            connections += f'<connection from="{a}c" to="c{b}" fromLane="{k}" toLane="{k}"/>'
            body += f'<route id="{a}{b}" edges="{a}c c{b}"/>'
    multilane_net(d, nodes, edges, connections)
    for i in range(60):
        a = "wesn"[i % 4]
        b = dict(w="sen", e="nws", s="enw", n="wse")[a][(i // 4) % 3]
        body += f'<vehicle id="v{i}" type="idm" route="{a}{b}" depart="{i}" departLane="0" departSpeed="max"/>'
    routes(d, body)
    return 1, 400


@macro
def multi_weave(d):
    nodes = ''.join(f'<node id="{a}" x="{k*350}" y="0"/>' for k, a in enumerate("abcd"))
    edges = '<edge id="ab" from="a" to="b" numLanes="3" speed="22"/><edge id="bc" from="b" to="c" numLanes="3" speed="22"/><edge id="cd" from="c" to="d" numLanes="1" speed="22"/>'
    con = ''.join(f'<connection from="ab" to="bc" fromLane="{i}" toLane="{i}"/>' for i in range(3))
    con += '<connection from="bc" to="cd" fromLane="2" toLane="0"/>'
    multilane_net(d, nodes, edges, con)
    routes(d, '<route id="r" edges="ab bc cd"/><flow id="f" type="idm" route="r" begin="0" end="120" period="2" departLane="0" departSpeed="max"/>')
    return 1, 400


def macro_compare(name, sumo, cars, d, dt, end):
    from collections import Counter
    def stats(rows, trips):
        lanes, changes = Counter(), 0
        for track in rows.values():
            prev = None
            for _, (lane, pos, speed) in sorted(track.items()):
                if not lane.startswith(":"):
                    lanes[lane] += 1
                    if prev and prev.rsplit("_", 1)[0] == lane.rsplit("_", 1)[0] and prev != lane:
                        changes += 1
                prev = lane
        arrivals = Counter(int(t["arrival"] // 60) for t in trips)
        mean = lambda key: sum(t[key] for t in trips) / max(1, len(trips))
        share = {l: n / sum(v for k, v in lanes.items() if k.rsplit("_", 1)[0] == l.rsplit("_", 1)[0]) for l, n in lanes.items()}
        return dict(completed=len(trips), duration=mean("duration"), speed=mean("speed"), flow=sum(60 <= t["arrival"] < 180 for t in trips)*30, changes=changes/max(1,len(rows)), share=share, arrivals=dict(arrivals))
    st = []
    for t in ET.parse(d / "trip.xml").getroot().findall("tripinfo"):
        st.append({k: float(t.get(k)) for k in ("arrival", "duration") } | {"speed": float(t.get("routeLength"))/float(t.get("duration"))})
    with open(d / "trips.csv") as f:
        ct = [{k: float(v) for k, v in r.items() if k != "trip"} for r in csv.DictReader(f)]
    a, b = stats(sumo, st), stats(cars, ct)
    share_error = max((abs(a["share"].get(l, 0)-b["share"].get(l, 0)) for l in a["share"].keys() | b["share"].keys()), default=0)
    print("scenario | completed S/C | travel S/C | flow S/C | speed S/C | changes S/C | max lane share pp")
    print(f'{name} | {a["completed"]}/{b["completed"]} | {a["duration"]:.2f}/{b["duration"]:.2f} | {a["flow"]:.1f}/{b["flow"]:.1f} | {a["speed"]:.2f}/{b["speed"]:.2f} | {a["changes"]:.2f}/{b["changes"]:.2f} | {share_error*100:.1f}')
    print(f'  arrivals/60s SUMO={a["arrivals"]} cars={b["arrivals"]}')
    print(f'  lane shares SUMO={a["share"]} cars={b["share"]}')
    (d / "comparison.json").write_text(__import__("json").dumps(dict(sumo=a, cars=b, lane_share_error=share_error), indent=2))
    return (a["completed"] == b["completed"] and abs(b["duration"]/max(.001,a["duration"])-1) <= .05 and abs(b["flow"]/max(.001,a["flow"])-1) <= .03 and share_error <= .1 and (name != "multi_overtake" or b["changes"] > 0))

def read_fcd(path):
    rows = {}
    for _, el in ET.iterparse(path):
        if el.tag == "timestep":
            t = float(el.get("time"))
            for v in el.findall("vehicle"):
                rows.setdefault(v.get("id"), {})[round(t, 3)] = (v.get("lane"), float(v.get("pos")), float(v.get("speed")))
            el.clear()
    return rows


def read_cars(path):
    rows = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.setdefault(r["trip"], {})[round(float(r["time"]), 3)] = (r["lane"], float(r["pos"]), float(r["speed"]))
    return rows


def compare(name, sumo, cars, dt):
    worst = 0.0
    lines = []
    ok = True
    for vid in sorted(sumo, key=lambda s: (len(s), s)):
        s = sumo[vid]
        c = cars.get(vid)
        if c is None:
            lines.append(f"  {vid}: missing in cars")
            ok = False
            continue
        ds, dv, n = 0.0, 0.0, 0
        first = None
        common = sorted(set(s) & set(c))
        for t in common:
            a, b = s[t], c[t]
            ep = abs(a[1] - b[1]) if a[0] == b[0] else 0.0
            ev = abs(a[2] - b[2])
            ds += ep * ep
            dv += ev * ev
            n += 1
            if first is None and (ev > 0.05 or ep > 0.5):
                first = (t, a, b)
        n = max(n, 1)
        rs, rv = math.sqrt(ds / n), math.sqrt(dv / n)
        worst = max(worst, rv)
        span = (min(s), max(s), min(c) if c else 0, max(c) if c else 0)
        line = f"  {vid}: rmse pos {rs:.3f} speed {rv:.3f} n={n} sumo {span[0]:.1f}-{span[1]:.1f} cars {span[2]:.1f}-{span[3]:.1f}"
        if first:
            line += f" first@{first[0]} sumo={first[1]} cars={first[2]}"
        lines.append(line)
    print(f"{name}: worst speed rmse {worst:.3f}")
    for l in lines:
        print(l)
    return ok and worst < 0.5



def compare_i80(root):
    import json
    import re
    import statistics
    d = Path(tempfile.mkdtemp(prefix="golden-i80-"))
    config = root / "config"
    result = run([CARS, "--net", config / "networks/i80_vsl.net.xml", "--routes", config / "demand/i80_vsl.rou.xml",
                  "--additional", config / "vtypes.xml", "--dt", "1", "--end", "18000", "--trip-csv", d / "trips.csv"])
    print(result.stdout, result.stderr)
    with open(root / "results/processed/metrics.csv") as f:
        reference = [r for r in csv.DictReader(f) if r["scenario"] == "i80_vsl" and r["tier"] == "idm" and float(r["penetration"]) == 0]
    with open(d / "trips.csv") as f:
        trips = list(csv.DictReader(f))
    values = dict(completed=len(trips), travel_time=statistics.mean(float(t["duration"]) for t in trips),
                  waiting_time=statistics.mean(float(t["waiting"]) for t in trips), time_loss=statistics.mean(float(t["time_loss"]) for t in trips),
                  speed=float(re.search(r"speed ([0-9.]+), trips", result.stdout)[1]))
    baseline = {k: statistics.mean(float(r[k]) for r in reference) for k in values}
    print("metric | SUMO mean (3 seeds) | cars (seed 0) | difference %")
    for k, v in values.items():
        print(f"{k} | {baseline[k]:.3f} | {v:.3f} | {(v/baseline[k]-1)*100:+.2f}")
    (d / "comparison.json").write_text(json.dumps(dict(sumo=baseline, cars=values, stderr=result.stderr), indent=2))
    print(f"  dir {d}")
    return abs(values["travel_time"]/baseline["travel_time"]-1) <= .05 and abs(values["completed"]/baseline["completed"]-1) <= .03 and "teleports 0" in result.stderr

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--i80", action="store_true")
    ap.add_argument("--thesis-root", type=Path, default=Path("/home/erikf/projects/personal/thesis-src/bachelor"))
    args = ap.parse_args()
    if args.i80:
        sys.exit(not compare_i80(args.thesis_root))
    names = args.names or list(SCENARIOS)
    bad = []
    for name in names:
        d = Path(tempfile.mkdtemp(prefix=f"golden-{name}-"))
        dt, end = SCENARIOS[name](d)
        fcd = d / "fcd.xml"
        run(["sumo", "-n", d / "net.xml", "-r", d / "r.rou.xml", "--step-length", str(dt), "--end", str(end),
             "--fcd-output", fcd, "--no-step-log", "true", "--no-warnings", "true", "--seed", "1",
             "--tripinfo-output", d / "trip.xml"])
        cars_csv = d / "cars.csv"
        result = run([CARS, "--net", d / "net.xml", "--routes", d / "r.rou.xml", "--dt", str(dt), "--end", str(end), "--fcd", cars_csv, "--trip-csv", d / "trips.csv", "--check-overlaps", "--seed", "1"])
        print(result.stdout.strip(), result.stderr.strip().splitlines()[-1])
        ok = macro_compare(name, read_fcd(fcd), read_cars(cars_csv), d, dt, end) if name in MACRO else compare(name, read_fcd(fcd), read_cars(cars_csv), dt)
        if "teleports 0" not in result.stderr:
            ok = False
        print(f"  dir {d}")
        if not ok:
            bad.append(name)
    print("FAILED:" if bad else "ALL OK", " ".join(bad))
    sys.exit(bool(bad))


if __name__ == "__main__":
    main()
