#!/usr/bin/env python3
"""Where does a run lose its time? Excess vehicle-hours per edge, against the data's flow and the net's lanes.

usage: hotspots.py RAW_DIR SCENARIO_DIR RUN_DIR [TOP]
Writes RUN_DIR/hotspots.csv.
"""
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

raw, sc, run = sys.argv[1:4]
top = int(sys.argv[4]) if len(sys.argv) > 4 else 15
edges = pd.read_csv(f"{raw}/edge_jinan.csv", usecols=["Origin", "Destination", "Class", "Length"])
nodes = pd.read_csv(f"{raw}/node_jinan.csv")
attrs = pd.read_csv(f"{sc}/net_attrs.csv", usecols=["edge", "lanes", "osm_lanes", "name"])
s = pd.read_csv(f"{run}/edges.csv")
s = s[s.edge.str.startswith("e")].copy()
s["e"] = s.edge.str[1:].astype(int)
g = s.groupby("e").agg(samples=("samples", "sum"), distance=("distance", "sum"), entered=("entered", "sum"), teleports=("teleports", "sum")).reset_index()

speeds = {}
tl = set()
for _, el in ET.iterparse(f"{sc}/jinan.net.xml", events=("end",)):
    if el.tag == "edge" and (el.get("id") or "").startswith("e"):
        la = el.find("lane")
        speeds[int(el.get("id")[1:])] = float(la.get("speed"))
    elif el.tag == "junction" and el.get("type") == "traffic_light" and el.get("id", "").startswith("n"):
        tl.add(int(el.get("id")[1:]))
    if el.tag in ("edge", "junction"):
        el.clear()
g["vmax"] = g.e.map(speeds)
g["free_h"] = g.distance / g.vmax / 3600
g["hours"] = g.samples / 3600
g["excess_h"] = (g.hours - g.free_h).clip(lower=0)
g["kmh"] = 3.6 * g.distance / g.samples.clip(lower=1)
g["cls"] = edges.Class.values[g.e]
g["len"] = edges.Length.values[g.e]
g["to_node"] = edges.Destination.values[g.e]
g["to_signal"] = g.to_node.isin(tl)
g["to_camera"] = nodes.HasCamera.values[g.to_node].astype(bool)
g = g.merge(attrs, left_on="e", right_on="edge", how="left")
g = g.sort_values("excess_h", ascending=False)
tot = g.excess_h.sum()
g["cum_share"] = g.excess_h.cumsum() / tot
print(f"edges used {len(g)}, total hours {g.hours.sum():.0f}, excess {tot:.0f}")
for n in (10, 50, 100, 500, 1000):
    print(f"top {n} edges hold {g.excess_h.head(n).sum() / tot:.1%} of the excess hours")
print("excess share by class:", (g.groupby("cls").excess_h.sum() / tot).sort_values(ascending=False).round(3).to_dict())
print("share of excess on edges ending at a signal:", round(g[g.to_signal].excess_h.sum() / tot, 3))
print("share of excess on 1-lane edges:", round(g[g.lanes == 1].excess_h.sum() / tot, 3), " with lanes guessed:", round(g[g.osm_lanes.isna()].excess_h.sum() / tot, 3))
print("speed under 10 km/h, share of edges:", round((g.kmh < 10).mean(), 3), " of used km:", round(g[g.kmh < 10].len.sum() / g.len.sum(), 3))
cols = ["e", "cls", "lanes", "osm_lanes", "len", "entered", "kmh", "excess_h", "teleports", "to_signal", "to_camera", "name"]
print(g[cols].head(top).round(1).to_string(index=False))
g[cols + ["hours", "cum_share"]].to_csv(f"{run}/hotspots.csv", index=False)
