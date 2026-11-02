#!/usr/bin/env python3
"""Why are trajectory movements missing from the built net? Prints a census and writes observed.con.xml.

usage: broken_moves.py RAW_DIR DERIVED_DIR SCENARIO_DIR
"""
import math
import sys
import xml.etree.ElementTree as ET
from collections import Counter

import numpy as np
import pandas as pd

raw, d, sc = sys.argv[1:4]
z = np.load(f"{d}/traj.npz")
offs, pn = z["offs"], z["pn"]
nodes = pd.read_csv(f"{raw}/node_jinan.csv")
edges = pd.read_csv(f"{raw}/edge_jinan.csv")
n = len(nodes)
key = edges.Origin.values.astype(np.int64) * n + edges.Destination.values
order = np.argsort(key)
skey = key[order]


def edge_of(a, b):
    k = a.astype(np.int64) * n + b
    p = np.searchsorted(skey, k).clip(0, len(skey) - 1)
    return np.where(skey[p] == k, order[p], -1)


# Consecutive edges over all trajectories, ignoring repeated nodes
keep = np.ones(len(pn), dtype=bool)
same = pn[1:] == pn[:-1]
first = np.zeros(len(pn), dtype=bool)
first[offs[:-1]] = True
keep[1:] &= ~(same & ~first[1:])
pk, ofk = pn[keep], np.cumsum(keep)[offs[:-1]] - 1
fk = np.zeros(len(pk), dtype=bool)
fk[ofk] = True
e = edge_of(pk[:-1], pk[1:])
e[fk[1:]] = -1
valid = (e[:-1] >= 0) & (e[1:] >= 0)
pair = e[:-1][valid].astype(np.int64) * 100000 + e[1:][valid]
upair, cnt = np.unique(pair, return_counts=True)

conn = set()
tl = {}
for _, el in ET.iterparse(f"{sc}/jinan.net.xml", events=("end",)):
    if el.tag == "connection":
        f, t = el.get("from"), el.get("to")
        if f[0] != ":" and t[0] != ":":
            conn.add((int(f[1:]), int(t[1:])))
    el.clear()

geom = edges.Geometry.str.split("_")


def bearing(p, q):
    a = tuple(map(float, p.split("-")))
    b = tuple(map(float, q.split("-")))
    dx = (b[0] - a[0]) * math.cos(math.radians(a[1]))
    dy = b[1] - a[1]
    return math.degrees(math.atan2(dy, dx))


census = Counter()
census_n = Counter()
miss = []
for up, c in zip(upair, cnt):
    a, b = int(up // 100000), int(up % 100000)
    if (a, b) in conn:
        census_n["connected"] += int(c)
        continue
    o, m, dd = edges.Origin[a], edges.Destination[a], edges.Destination[b]
    if dd == o:
        kind = "uturn_same_node"
    else:
        ga, gb = geom[a], geom[b]
        ang = (bearing(ga[-2], ga[-1]) - bearing(gb[0], gb[1]) + 540) % 360 - 180
        if abs(ang) > 150:
            kind = "sharp_uturn_other_node"
        elif ang > 30:
            kind = "right"
        elif ang < -30:
            kind = "left"
        else:
            kind = "straight"
    census[kind] += int(c)
    census_n[kind] += 1
    miss.append((a, b, int(c), kind))
tot = int(cnt.sum())
print("movement passes", tot, "unique movements", len(upair))
print("passes on missing movements by kind:")
for k, v in census.most_common():
    print(" ", k, v, f"{v / tot:.3%}", "unique", census_n[k])
print("unique movements connected passes", census_n["connected"])
top = sorted(miss, key=lambda x: -x[2])[:12]
for a, b, c, kind in top:
    print(f"  e{a}({edges.Class[a]}) -> e{b}({edges.Class[b]}) passes {c} {kind} nodes {edges.Origin[a]}>{edges.Destination[a]}>{edges.Destination[b]}")
# netconvert stops guessing an edge's movements once one is given, so restate its guessed ones as well.
from_edges = {a for a, b, c, kind in miss}
with open(f"{sc}/observed.con.xml", "w") as f:
    f.write("<connections>\n")
    for a, b in sorted(c for c in conn if c[0] in from_edges):
        f.write(f'  <connection from="e{a}" to="e{b}"/>\n')
    for a, b, c, kind in miss:
        f.write(f'  <connection from="e{a}" to="e{b}"/>\n')
    f.write("</connections>\n")
print("wrote", len(miss), "connections")
