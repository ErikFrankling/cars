#!/usr/bin/env python3
"""What the net offers at the end of the worst edges: lanes, movements, signal share, and what their traffic wants.

usage: hotspot_detail.py RAW_DIR SCENARIO_DIR RUN_DIR [N]
"""
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

import pandas as pd

raw, sc, run = sys.argv[1:4]
n = int(sys.argv[4]) if len(sys.argv) > 4 else 8
h = pd.read_csv(f"{run}/hotspots.csv").head(n)
want = set(h.e.tolist())
conns = defaultdict(list)
tl_green = defaultdict(lambda: [0, 0])
tl_prog = {}
jt = {}
for _, el in ET.iterparse(f"{sc}/jinan.net.xml", events=("end",)):
    if el.tag == "connection":
        f = el.get("from")
        if f[0] == "e" and int(f[1:]) in want:
            conns[int(f[1:])].append((el.get("fromLane"), el.get("to"), el.get("toLane"), el.get("dir"), el.get("state"), el.get("tl"), el.get("linkIndex")))
    elif el.tag == "tlLogic":
        tl_prog[el.get("id")] = [(float(p.get("duration")), p.get("state")) for p in el.findall("phase")]
        el.clear()
    elif el.tag == "junction":
        jt[el.get("id")] = el.get("type")
        el.clear()
    elif el.tag == "edge":
        el.clear()
edges = pd.read_csv(f"{raw}/edge_jinan.csv", usecols=["Origin", "Destination", "Class"])
names = {f"e{i}": f"{c}" for i, c in enumerate(edges.Class)}

# Downstream demand of each worst edge, from the 30% route file
next_count = {e: Counter() for e in want}
import re

pat = re.compile(r'edges="([^"]+)"')
with open(f"{sc}/p030.rou.xml") as f:
    for line in f:
        m = pat.search(line)
        if not m:
            continue
        es = m.group(1).split()
        for a, b in zip(es, es[1:]):
            ai = int(a[1:])
            if ai in want:
                next_count[ai][b] += 1

for r in h.itertuples(index=False):
    node = int(edges.Destination[r.e])
    print(f"\n=== e{r.e} {r.cls} lanes {r.lanes} len {r.len:.0f} entered {r.entered} kmh {r.kmh:.1f} excess_h {r.excess_h:.0f} teleports {r.teleports} -> node n{node} type {jt.get(f'n{node}')}")
    by_to = defaultdict(list)
    for fl, to, tol, d, st, tl, li in conns[r.e]:
        by_to[to].append((fl, d, st, tl, li))
    tot = sum(next_count[r.e].values())
    for to, cnt in next_count[r.e].most_common(8):
        c = by_to.get(to, [])
        lanes = sorted({x[0] for x in c})
        dirs = {x[1] for x in c}
        green = None
        if c and c[0][3] and c[0][3] in tl_prog:
            prog = tl_prog[c[0][3]]
            li = int(c[0][4])
            cyc = sum(d for d, _ in prog)
            green = round(sum(d for d, s in prog if s[li] in "Gg") / cyc, 2)
            major = round(sum(d for d, s in prog if s[li] == "G") / cyc, 2)
            green = f"green {green} protected {major} of {cyc:.0f}s"
        print(f"   -> {to} ({names.get(to)}) next-edge share {cnt / max(tot, 1):.2f} from lanes {lanes} dir {dirs} state {[x[2] for x in c][:1]} {green}")
    missing = [to for to in next_count[r.e] if to not in by_to]
    if missing:
        print("   wanted but no connection:", missing[:5])
