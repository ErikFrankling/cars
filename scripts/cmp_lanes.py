#!/usr/bin/env python3
"""Per lane occupancy, speed and lane-change location on selected edges: SUMO FCD against cars FCD."""
import sys
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd

sumo_xml, cars_csv, t0, t1 = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
edges = sys.argv[5].split(",")
rows = []
for _, el in ET.iterparse(sumo_xml):
    if el.tag == "timestep":
        t = float(el.get("time"))
        if t >= t0:
            for v in el.findall("vehicle"):
                rows.append((t, v.get("id"), v.get("lane"), float(v.get("pos")), float(v.get("speed"))))
        el.clear()
s = pd.DataFrame(rows, columns=["time", "trip", "lane", "pos", "speed"])
g = pd.read_csv(cars_csv)
g = g[g.time >= t0]
pd.set_option("display.width", 200)
pd.set_option("display.max_rows", 200)


def table(d):
    d = d[d.lane.str.rsplit("_", n=1).str[0].isin(edges)]
    return d.groupby("lane").agg(n=("speed", "size"), speed=("speed", "mean"), slow=("speed", lambda x: (x < 5).mean()))


def changes(d):
    d = d.sort_values(["trip", "time"])
    same = d.trip == d.trip.shift(1)
    el = d.lane.str.rsplit("_", n=1).str[0]
    pel = el.shift(1)
    lc = d[same & (el == pel) & (d.lane != d.lane.shift(1))]
    return lc.groupby(lc.lane.str.rsplit("_", n=1).str[0]).size()


a = table(s).join(table(g), lsuffix="_s", rsuffix="_g", how="outer").fillna(0).round(2)
print(a)
print("lane changes (sumo, cars) in window:")
print(pd.concat([changes(s), changes(g)], axis=1, keys=["s", "g"]).fillna(0).astype(int).sort_values("s", ascending=False).head(14))
