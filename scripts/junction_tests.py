#!/usr/bin/env python3
"""Junction behaviour against SUMO, route by route, on small networks."""

import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CARS = ROOT / "target/release/cars"
TYPES = """
<vType id="k" vClass="passenger" carFollowModel="Krauss" sigma="0" length="5" minGap="2.5" accel="2.6" decel="4.5" tau="1" speedDev="0"/>
<vType id="i" vClass="passenger" carFollowModel="IDM" length="5" minGap="2.5" accel="2.6" decel="2.0" emergencyDecel="4.5" tau="1" speedDev="0.1"/>
"""


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"failed: {cmd}\n{r.stdout}\n{r.stderr}")
    return r.stdout + r.stderr


def cross(d, jt, lanes=1, major=True, arm=400, speed=13.89):
    tls_type = []
    if jt == "actuated":
        jt = "traffic_light"
        tls_type = ["--tls.default-type", "actuated"]
    nodes = f'<nodes><node id="c" x="0" y="0" type="{jt}"/><node id="w" x="{-arm}" y="0"/><node id="e" x="{arm}" y="0"/><node id="s" x="0" y="{-arm}"/><node id="n" x="0" y="{arm}"/></nodes>'
    edges = "<edges>"
    for a, b, pr in [("w", "c", 2), ("c", "e", 2), ("e", "c", 2), ("c", "w", 2), ("s", "c", 1), ("c", "n", 1), ("n", "c", 1), ("c", "s", 1)]:
        if not major:
            pr = 1
        edges += f'<edge id="{a}{b}" from="{a}" to="{b}" priority="{pr}" numLanes="{lanes}" speed="{speed}"/>'
    edges += "</edges>"
    (d / "n.nod.xml").write_text(nodes)
    (d / "n.edg.xml").write_text(edges)
    run(["netconvert", "-n", d / "n.nod.xml", "-e", d / "n.edg.xml", "-o", d / "net.xml", "--no-turnarounds"] + tls_type)


def flows(d, spec, vt, end=900):
    body = TYPES
    for name, route, rate in spec:
        body += f'<flow id="{name}" type="{vt}" route="{name}R" begin="0" end="{end}" vehsPerHour="{rate}" departSpeed="max" departLane="best"/>'
        body = f'<route id="{name}R" edges="{route}"/>' + body
    (d / "r.rou.xml").write_text("<routes>" + body + "</routes>")


CASES = {
    "actuated_light": ("actuated", 1, [("we", "wc ce", 300), ("sn", "sc cn", 100), ("ew", "ec cw", 300)]),
    "actuated_heavy": ("actuated", 2, [("we", "wc ce", 1000), ("sn", "sc cn", 600), ("ew", "ec cw", 1000), ("ns", "nc cs", 600), ("wn", "wc cn", 100)]),
    "tls_permissive_left": ("traffic_light", 1, [("we", "wc ce", 500), ("en", "ec cn", 150), ("ew", "ec cw", 400), ("ns", "nc cs", 300)]),
    "tls_left_2lane": ("traffic_light", 2, [("we", "wc ce", 900), ("wn", "wc cn", 200), ("ew", "ec cw", 900), ("es", "ec cs", 200), ("sn", "sc cn", 400)]),
    "prio_major_left": ("priority", 1, [("we", "wc ce", 500), ("wn", "wc cn", 150), ("ew", "ec cw", 500)]),
    "prio_minor_cross": ("priority", 1, [("we", "wc ce", 500), ("ew", "ec cw", 500), ("sn", "sc cn", 200), ("se", "sc ce", 100), ("sw", "sc cw", 100)]),
    "prio_heavy": ("priority", 1, [("we", "wc ce", 900), ("ew", "ec cw", 900), ("sn", "sc cn", 500), ("ns", "nc cs", 500)]),
    "rbl": ("right_before_left", 1, [("we", "wc ce", 300), ("sn", "sc cn", 300), ("ew", "ec cw", 300), ("ns", "nc cs", 300)]),
    "rbl_heavy": ("right_before_left", 1, [("we", "wc ce", 700), ("sn", "sc cn", 700), ("ew", "ec cw", 700), ("ns", "nc cs", 700)]),
    "allway": ("allway_stop", 1, [("we", "wc ce", 400), ("sn", "sc cn", 400), ("ew", "ec cw", 400)]),
    "stop_minor": ("priority_stop", 1, [("we", "wc ce", 500), ("sn", "sc cn", 300)]),
    "zipper": ("zipper", 1, [("we", "wc ce", 500), ("sn", "sc cn", 300)]),
}


def one(name, vt, keep=False):
    jt, lanes, spec = CASES[name]
    d = Path(tempfile.mkdtemp(prefix=f"junc-{name}-"))
    cross(d, jt, lanes)
    flows(d, spec, vt)
    trip = d / "t.xml"
    run(["sumo", "-n", d / "net.xml", "-r", d / "r.rou.xml", "--end", "1500", "--no-step-log", "true", "--no-warnings", "true", "--tripinfo-output", trip, "--seed", "1"])
    rows = [(t.get("id").split(".")[0], float(t.get("duration")), float(t.get("waitingTime")), float(t.get("timeLoss"))) for t in ET.parse(trip).getroot().findall("tripinfo")]
    s = pd.DataFrame(rows, columns=["r", "dur", "wait", "loss"])
    run([CARS, "run", "--net", d / "net.xml", "--routes", d / "r.rou.xml", "--dt", "1", "--end", "1500", "--trip-csv", d / "g.csv", "--seed", "1"])
    g = pd.read_csv(d / "g.csv").rename(columns={"duration": "dur", "waiting": "wait", "time_loss": "loss"})
    g["r"] = g.trip.str.split(".").str[0]
    a = s.groupby("r").agg(n=("dur", "size"), dur=("dur", "mean"), wait=("wait", "mean"), loss=("loss", "mean"))
    b = g.groupby("r").agg(n=("dur", "size"), dur=("dur", "mean"), wait=("wait", "mean"), loss=("loss", "mean"))
    j = a.join(b, lsuffix="_s", rsuffix="_g", how="outer").round(1)
    err = (j.loss_g - j.loss_s).abs() / j.loss_s.clip(lower=3)
    print(f"--- {name} {vt}: worst loss error {err.max():.0%}  dir {d}")
    print(j.to_string())
    return err.max()


def main():
    names = sys.argv[1:] or list(CASES)
    worst = {}
    for n in names:
        for vt in ("k", "i"):
            worst[f"{n}/{vt}"] = one(n, vt)
    print({k: round(float(v), 2) for k, v in worst.items()})


if __name__ == "__main__":
    main()
