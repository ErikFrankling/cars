#!/usr/bin/env python3
"""Turn Jinan trajectories into nested SUMO route files.

Each vehicle departs on its first edge at the time of its first camera record and leaves at the end of its
last edge, at its last camera record. So the first and last mile are left out, not invented. Trajectories
that imply over 130 km/h end to end are dropped as false re-ID links, since their route joins two vehicles.

usage: build_routes.py RAW_DIR DERIVED_DIR SCENARIO_DIR
"""
import json
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

raw, d, sc = sys.argv[1:4]
z = np.load(f"{d}/traj.npz")
veh, trip, dep, dur, leng, offs, pn, pt = (z[k] for k in ("veh", "trip", "dep", "dur", "leng", "offs", "pn", "pt"))
nodes_n = len(pd.read_csv(f"{raw}/node_jinan.csv"))
edges = pd.read_csv(f"{raw}/edge_jinan.csv")
key = edges.Origin.values.astype(np.int64) * nodes_n + edges.Destination.values
emap = {int(k): i for i, k in enumerate(key)}

# Valid movements from the built net
conn = set()
valid_edges = set()
for _, el in ET.iterparse(f"{sc}/jinan.net.xml", events=("end",)):
    if el.tag == "connection":
        f, t = el.get("from"), el.get("to")
        if f[0] != ":" and t[0] != ":":
            conn.add((int(f[1:]), int(t[1:])))
    elif el.tag == "edge" and el.get("function") != "internal" and el.get("id"):
        if el.get("id")[0] == "e":
            valid_edges.add(int(el.get("id")[1:]))
    el.clear()
print("connections", len(conn), "edges in net", len(valid_edges))

rng = np.random.default_rng(20261102)
nv = int(veh.max()) + 1
vrand = rng.random(nv)  # nested samples: 1% is inside 10% is inside 30%

speed = np.where(dur > 0, leng / np.maximum(dur, 1), 0) * 3.6
stats = dict(trajectories=len(dep), dropped_fast=0, dropped_empty=0, dropped_no_edge=0, routes=0, split_routes=0, broken_movements=0, movements=0, self_steps=0)
order = np.argsort(dep, kind="stable")
scales = {"p001": 0.01, "p010": 0.10, "p030": 0.30, "p100": 1.0}
files = {}
for name in scales:
    files[name] = open(f"{sc}/{name}.rou.xml", "w")
    files[name].write('<routes>\n  <vType id="car" vClass="passenger"/>\n')
index = open(f"{sc}/route_index.csv", "w")
index.write("id,row,part,depart,real_duration,real_length,n_edges,first_time,last_time,vrand\n")
for row in order:
    row = int(row)
    if speed[row] > 130:
        stats["dropped_fast"] += 1
        continue
    a, b = int(offs[row]), int(offs[row + 1])
    ns = pn[a:b]
    ts = pt[a:b]
    parts = []
    cur = []
    start_t = ts[0]
    for i in range(len(ns) - 1):
        if ns[i] == ns[i + 1]:
            stats["self_steps"] += 1
            continue
        e = emap.get(int(ns[i]) * nodes_n + int(ns[i + 1]))
        if e is None or e not in valid_edges:
            stats["dropped_no_edge"] += 1
            if cur:
                parts.append((start_t, ts[i], cur))
            cur = []
            start_t = ts[i + 1]
            continue
        if cur:
            stats["movements"] += 1
            if (cur[-1], e) not in conn:
                stats["broken_movements"] += 1
                parts.append((start_t, ts[i], cur))
                cur = []
                start_t = ts[i]
        cur.append(e)
    if cur:
        parts.append((start_t, ts[-1], cur))
    if not parts:
        stats["dropped_empty"] += 1
        continue
    if len(parts) > 1:
        stats["split_routes"] += 1
    r = vrand[int(veh[row])]
    for pi, (t0, t1, es) in enumerate(parts):
        vid = f"v{row}_{pi}"
        s = f'  <vehicle id="{vid}" type="car" depart="{t0:.1f}" departLane="best" departPos="base" departSpeed="max"><route edges="{" ".join("e" + str(x) for x in es)}"/></vehicle>\n'
        stats["routes"] += 1
        whole = len(parts) == 1
        index.write(f"{vid},{row},{pi},{t0:.1f},{t1 - t0:.1f},{leng[row] if whole else -1:.1f},{len(es)},{t0:.1f},{t1:.1f},{r:.6f}\n")
        for name, sc_f in scales.items():
            if r < sc_f:
                files[name].write(s)
for f in files.values():
    f.write("</routes>\n")
    f.close()
print(json.dumps(stats, indent=1))
json.dump(stats, open(f"{sc}/route_stats.json", "w"), indent=1)
