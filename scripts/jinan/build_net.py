#!/usr/bin/env python3
"""Plain SUMO network from the paper's own graph, with lanes, speeds and signals looked up in OSM.

The paper's graph is a simplified OSMnx graph (merged junctions, cut at cameras). Keeping it means every
trajectory step is an edge, with no map matching. OSM contributes only attributes. Nothing here looks at
the trajectories, so no attribute is tuned against the data the simulation is compared with.

usage: build_net.py RAW_DIR OSM_JSON OUT_DIR
Writes jinan.nod.xml, jinan.edg.xml, net_attrs.csv, net_join.json.
"""
import json
import math
import os
import sys
from collections import Counter, defaultdict
from xml.sax.saxutils import quoteattr

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

raw, osm_json, out = sys.argv[1:4]
# Sensitivity only: the typemap gives urban primary and secondary roads 100 km/h. "urban" uses usual Chinese urban
# design speeds instead (from memory of CJJ 37, not opened), in m/s, where OSM has no maxspeed.
URBAN = {"motorway": 27.78, "motorway_link": 16.67, "trunk": 22.22, "trunk_link": 13.89, "primary": 16.67, "primary_link": 11.11, "secondary": 13.89, "secondary_link": 11.11, "tertiary": 11.11, "tertiary_link": 8.33, "residential": 8.33, "unclassified": 8.33, "living_street": 5.56}
urban = len(sys.argv) > 4 and sys.argv[4] == "urban"
os.makedirs(out, exist_ok=True)
nodes = pd.read_csv(f"{raw}/node_jinan.csv")
edges = pd.read_csv(f"{raw}/edge_jinan.csv")
tr = Transformer.from_crs(4326, 32650, always_xy=True)

els = json.load(open(osm_json))["elements"]
ways = [e for e in els if e["type"] == "way"]
sig = [e for e in els if e["type"] == "node"]


def k(lon, lat):
    return (round(lon, 5), round(lat, 5))


seg = {}
for w in ways:
    g = w["geometry"]
    t = w.get("tags", {})
    for a, b in zip(g, g[1:]):
        ka, kb = k(a["lon"], a["lat"]), k(b["lon"], b["lat"])
        seg[(ka, kb)] = (w["id"], False)
        seg[(kb, ka)] = (w["id"], True)
wtags = {w["id"]: w.get("tags", {}) for w in ways}


def parse_speed(v):
    if not v:
        return None
    try:
        s = v.strip().lower()
        if "mph" in s:
            return float(s.split()[0]) * 1.609 / 3.6
        return float(s.split()[0]) / 3.6
    except ValueError:
        return None


def lanes_for(t, reverse):
    """Lanes in this direction of travel, or None when OSM does not say."""
    oneway = t.get("oneway") in ("yes", "1", "-1") or t.get("junction") == "roundabout" or t.get("highway") in ("motorway", "motorway_link")
    fw, bw = t.get("lanes:forward"), t.get("lanes:backward")
    try:
        if not oneway and fw and not reverse:
            return int(fw)
        if not oneway and bw and reverse:
            return int(bw)
        if t.get("lanes"):
            n = int(float(t["lanes"].split(";")[0]))
            return n if oneway else max(1, n // 2)
    except ValueError:
        return None
    return None


rows = []
matched_edges = 0
for i, r in enumerate(edges.itertuples(index=False)):
    pts = [tuple(map(float, p.split("-"))) for p in r.Geometry.split("_")]
    votes = Counter()
    hits = 0
    for a, b in zip(pts, pts[1:]):
        m = seg.get((k(*a), k(*b)))
        if m:
            hits += 1
            votes[m] += 1
    lanes = speed = name = None
    wid = None
    if votes:
        (wid, rev), _ = votes.most_common(1)[0]
        t = wtags[wid]
        lanes = lanes_for(t, rev)
        speed = parse_speed(t.get("maxspeed"))
        name = t.get("name")
    rows.append((i, r.Class, r.Length, len(pts) - 1, hits, wid, lanes, speed, name))
a = pd.DataFrame(rows, columns=["edge", "cls", "len", "segs", "hits", "way", "osm_lanes", "osm_speed", "name"])
a["cls"] = a.cls.astype(str)

# Fill missing lanes from the tagged ways of the same class in this city.
tagged = a[a.osm_lanes.notna()]
lane_default = tagged.groupby("cls").osm_lanes.median().to_dict()
fallback = {"trunk": 2, "trunk_link": 1, "motorway": 2, "motorway_link": 1, "primary": 2, "primary_link": 1, "secondary": 2, "secondary_link": 1, "tertiary": 1, "tertiary_link": 1, "residential": 1, "living_street": 1, "unclassified": 1}
a["lanes"] = [int(l) if pd.notna(l) and l >= 1 else int(lane_default.get(c, fallback.get(c, 1))) for l, c in zip(a.osm_lanes, a.cls)]
a["lanes"] = a.lanes.clip(1, 8)

# Signals: OSM tag within 30 m of a junction, the paper merged junctions within 20 m.
nx, ny = tr.transform(nodes.Longitude.values, nodes.Latitude.values)
sx, sy = tr.transform([s["lon"] for s in sig], [s["lat"] for s in sig])
tree = cKDTree(np.c_[nx, ny])
hits = tree.query_ball_point(np.c_[sx, sy], 30)
is_sig = np.zeros(len(nodes), dtype=bool)
for h in hits:
    if h:
        c = np.array(h)
        is_sig[c] = True
osm_sig = is_sig.copy()

# Cameras in this dataset stand at signalled junctions on main roads, and OSM's signal tags are sparse in China.
major = {"motorway", "trunk", "primary", "secondary", "tertiary", "trunk_link", "primary_link", "secondary_link"}
inc = defaultdict(int)
arms = defaultdict(set)
for r in edges.itertuples(index=False):
    if str(r.Class) in major:
        inc[r.Destination] += 1
    arms[r.Destination].add(r.Origin)
    arms[r.Origin].add(r.Destination)
cam = nodes.HasCamera.values.astype(bool)
cam_sig = np.array([cam[i] and len(arms[i]) >= 3 and inc[i] >= 3 for i in range(len(nodes))])
is_sig |= cam_sig

# The paper moved merged junctions up to about 20 m off the road and ran each edge out to that point and back,
# so a straight road shows a spike at the junction. Cut those stubs and put the junction back on the road.
def turn_deg(p, q, r):
    a = math.atan2(q[1] - p[1], q[0] - p[0])
    b = math.atan2(r[1] - q[1], r[0] - q[0])
    return abs((math.degrees(b - a) + 180) % 360 - 180)


STUB_M = 45.0
STUB_DEG = 60.0
shapes = {}
ends = defaultdict(list)
trimmed = defaultdict(int)
for i, r in enumerate(edges.itertuples(index=False)):
    if r.Origin == r.Destination:
        continue
    pts = [tuple(map(float, p.split("-"))) for p in r.Geometry.split("_")]
    xs, ys = tr.transform([p[0] for p in pts], [p[1] for p in pts])
    sh = list(zip(xs, ys))
    if len(sh) >= 3 and math.dist(sh[0], sh[1]) <= STUB_M and turn_deg(sh[0], sh[1], sh[2]) >= STUB_DEG:
        sh = sh[1:]
        trimmed[r.Origin] += 1
    if len(sh) >= 3 and math.dist(sh[-1], sh[-2]) <= STUB_M and turn_deg(sh[-3], sh[-2], sh[-1]) >= STUB_DEG:
        sh = sh[:-1]
        trimmed[r.Destination] += 1
    shapes[i] = sh
    ends[r.Origin].append(sh[0])
    ends[r.Destination].append(sh[-1])

with open(f"{out}/jinan.nod.xml", "w") as f:
    f.write("<nodes>\n")
    for i in range(len(nodes)):
        t = "traffic_light" if is_sig[i] else "priority"
        x, y = nx[i], ny[i]
        if trimmed[i] and ends[i]:
            x = sum(p[0] for p in ends[i]) / len(ends[i])
            y = sum(p[1] for p in ends[i]) / len(ends[i])
        f.write(f'  <node id="n{i}" x="{x:.2f}" y="{y:.2f}" type="{t}"/>\n')
    f.write("</nodes>\n")

# Types carry the osm typemap's speed for each class, as an a priori default.
with open(f"{out}/jinan.edg.xml", "w") as f:
    f.write("<edges>\n")
    for i, r in enumerate(edges.itertuples(index=False)):
        if i not in shapes:
            continue
        shape = " ".join(f"{x:.2f},{y:.2f}" for x, y in shapes[i])
        row = a.iloc[i]
        cls = "highway." + row.cls
        attrs = f'id="e{i}" from="n{r.Origin}" to="n{r.Destination}" type="{cls}" numLanes="{row.lanes}"'
        if pd.notna(row.osm_speed) and row.osm_speed > 1:
            attrs += f' speed="{row.osm_speed:.2f}"'
        elif urban:
            attrs += f' speed="{URBAN.get(row.cls, 11.11):.2f}"'
        f.write(f"  <edge {attrs} shape={quoteattr(shape)}/>\n")
    f.write("</edges>\n")

a.to_csv(f"{out}/net_attrs.csv", index=False)
res = {
    "edges": len(a),
    "vertices_found_in_osm_share": float(a.hits.sum() / a.segs.sum()),
    "edges_with_any_osm_match": int((a.hits > 0).sum()),
    "edges_with_any_osm_match_share": float((a.hits > 0).mean()),
    "edges_with_osm_lanes_share": float(a.osm_lanes.notna().mean()),
    "edges_with_osm_lanes_share_veh_km_classes": {c: float(g.osm_lanes.notna().mean()) for c, g in a.groupby("cls")},
    "edges_with_osm_speed_share": float(a.osm_speed.notna().mean()),
    "lane_default_from_osm": {k: float(v) for k, v in lane_default.items()},
    "lanes_used_median_by_class": {c: float(g.lanes.median()) for c, g in a.groupby("cls")},
    "signal_nodes_osm_ways": len(sig),
    "signal_nodes_from_osm": int(osm_sig.sum()),
    "signal_nodes_from_camera_rule_added": int((cam_sig & ~osm_sig).sum()),
    "signal_nodes_total": int(is_sig.sum()),
    "nodes_with_trimmed_stub": int(sum(1 for v in trimmed.values() if v)),
    "edge_ends_trimmed": int(sum(trimmed.values())),
    "camera_nodes": int(cam.sum()),
    "camera_nodes_with_osm_signal": int((cam & osm_sig).sum()),
}
print(json.dumps(res, indent=1))
json.dump(res, open(f"{out}/net_join.json", "w"), indent=1)
