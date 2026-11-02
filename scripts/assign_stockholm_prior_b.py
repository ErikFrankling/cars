#!/usr/bin/env python3
"""A second Stockholm prior that shares nothing with the old route file: trip ends by road length, a distance
kernel, and departures shaped by the training rows of the count file. No test row is read.
usage: assign_stockholm_prior_b.py NET COUNTS.csv TRIPS KERNEL_KM OUT.csv.gz"""
import csv, gzip, sys
import xml.etree.ElementTree as ET
import numpy as np

NET, COUNTS, TRIPS, KM, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
ids, xy, length, heads = [], [], [], set()
for ev, el in ET.iterparse(NET, events=("end",)):
    if el.tag == "edge":
        if el.get("function") is None:
            ls = [l for l in el.findall("lane") if "passenger" in (l.get("allow") or "passenger") and "passenger" not in (l.get("disallow") or "")]
            if ls:
                p = ls[0].get("shape").split()
                ids.append(el.get("id"))
                xy.append([float(v) for v in p[len(p) // 2].split(",")[:2]])
                length.append(float(ls[0].get("length")))
        el.clear()
    elif el.tag == "connection":
        heads.add(el.get("from"))
        el.clear()
    elif el.tag in ("junction", "tlLogic", "roundabout"):
        el.clear()
keep = [i for i, e in enumerate(ids) if e in heads and length[i] > 20]
ids = [ids[i] for i in keep]
xy = np.array([xy[i] for i in keep])
w = np.array([length[i] for i in keep])
w = w / w.sum()
shape = np.zeros(24)
with open(COUNTS, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["role"] == "train":
            shape[int(float(r["t0_s"])) // 3600] += float(r["vehicles"])
shape /= shape.sum()
rng = np.random.default_rng(11)
od = []
while sum(len(a) for a, _ in od) < TRIPS:
    a, b = rng.choice(len(ids), 400000, p=w), rng.choice(len(ids), 400000, p=w)
    d = np.hypot(*(xy[a] - xy[b]).T)
    ok = (d > 800) & (rng.random(400000) < np.exp(-d / (KM * 1000)))
    od.append((a[ok], b[ok]))
a = np.concatenate([x[0] for x in od])[:TRIPS]
b = np.concatenate([x[1] for x in od])[:TRIPS]
hour = rng.choice(24, TRIPS, p=shape)
dep = np.sort(hour * 3600 + rng.random(TRIPS) * 3600)
print("straight-line mean km", float(np.hypot(*(xy[a] - xy[b]).T).mean()) / 1000)
with gzip.open(OUT, "wt") as f:
    w = csv.writer(f)
    w.writerow("id,class,o_edge,d_edge,desired_arrival_s,depart_s,earliest_s,latest_s,tour,tour_seq,vtype".split(","))
    for i in range(TRIPS):
        t = float(dep[i])
        w.writerow([i, 0, ids[a[i]], ids[b[i]], "nan", f"{t:.1f}", f"{max(0, t - 3600):.1f}", f"{t + 900:.1f}", i, 0, "passenger"])
