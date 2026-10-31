#!/usr/bin/env python3
"""Compare trajectories from cars against SUMO on tiny scenarios, one vehicle at a time."""

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()
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
        run([CARS, "--net", d / "net.xml", "--routes", d / "r.rou.xml", "--dt", str(dt), "--end", str(end), "--fcd", cars_csv])
        ok = compare(name, read_fcd(fcd), read_cars(cars_csv), dt)
        print(f"  dir {d}")
        if not ok:
            bad.append(name)
    print("FAILED:" if bad else "ALL OK", " ".join(bad))


if __name__ == "__main__":
    main()
