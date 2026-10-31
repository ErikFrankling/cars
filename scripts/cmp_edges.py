#!/usr/bin/env python3
"""Compare edge speeds and flows from SUMO edgeData against a cars --edge-csv file."""
import sys
import xml.etree.ElementTree as ET
import pandas as pd

rows = []
begin = None
for _, el in ET.iterparse(sys.argv[1], events=("start", "end")):
    pass
root = ET.parse(sys.argv[1]).getroot()
for iv in root.findall("interval"):
    b = float(iv.get("begin"))
    for e in iv.findall("edge"):
        rows.append((b, e.get("id"), float(e.get("sampledSeconds", 0)), float(e.get("speed", "nan")), float(e.get("entered", 0)), float(e.get("laneChangedFrom", 0)), float(e.get("waitingTime", 0))))
s = pd.DataFrame(rows, columns=["begin", "edge", "s_samples", "s_speed", "s_entered", "s_lcfrom", "s_wait"])
g = pd.read_csv(sys.argv[2])
g["g_speed"] = g.distance / g.samples.clip(lower=1e-3)
g = g.rename(columns={"samples": "g_samples", "entered": "g_entered"})
m = s.merge(g[["begin", "edge", "g_samples", "g_speed", "g_entered"]], on=["begin", "edge"], how="outer").fillna(0)
m = m[~m.edge.str.startswith(":")]
a = m.groupby("edge").agg(s_samples=("s_samples", "sum"), g_samples=("g_samples", "sum"), s_entered=("s_entered", "sum"), g_entered=("g_entered", "sum"), s_lcfrom=("s_lcfrom", "sum"), s_speed=("s_speed", "mean"), g_speed=("g_speed", "mean"))
a["excess"] = a.g_samples - a.s_samples
pd.set_option("display.width", 200)
pd.set_option("display.max_rows", 60)
print(a.sort_values("excess", ascending=False).head(int(sys.argv[3]) if len(sys.argv) > 3 else 16).round(1))
print("samples sumo", a.s_samples.sum(), "cars", a.g_samples.sum())
