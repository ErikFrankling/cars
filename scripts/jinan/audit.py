#!/usr/bin/env python3
"""Audit of the Jinan camera trajectories (Yu et al. 2023). Run with python3 -I from outside the data folder.

usage: audit.py RAW_DIR OUT_DIR
Writes audit.json, edge_hour.npz (per-edge per-hour counts) and traj.npz (flat arrays for the other scripts).
"""
import json
import os
import sys
from array import array

import numpy as np
import pandas as pd

raw, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

nodes = pd.read_csv(f"{raw}/node_jinan.csv")
edges = pd.read_csv(f"{raw}/edge_jinan.csv")
n = len(nodes)
has_cam = nodes.HasCamera.values.astype(bool)
key = edges.Origin.values.astype(np.int64) * n + edges.Destination.values
if len(np.unique(key)) != len(key):
    print("duplicate node pairs in edges:", len(key) - len(np.unique(key)))
order = np.argsort(key)
skey = key[order]

veh = array("i")
trip = array("i")
dep = array("f")
dur = array("f")
leng = array("f")
offs = array("q", [0])
pn = array("i")
pt = array("d")
bad_lines = 0
with open(f"{raw}/traj_jinan.csv") as f:
    f.readline()
    for line in f:
        p = line.rstrip("\n").split(",")
        if len(p) != 6:
            bad_lines += 1
            continue
        veh.append(int(p[0]))
        trip.append(int(p[1]))
        dep.append(float(p[3]))
        dur.append(float(p[4]))
        leng.append(float(p[5]))
        for tok in p[2].split("_"):
            a, b = tok.split("-", 1)
            pn.append(int(a))
            pt.append(float(b))
        offs.append(len(pn))

veh = np.frombuffer(veh, dtype=np.int32)
trip = np.frombuffer(trip, dtype=np.int32)
dep = np.frombuffer(dep, dtype=np.float32)
dur = np.frombuffer(dur, dtype=np.float32)
leng = np.frombuffer(leng, dtype=np.float32)
offs = np.frombuffer(offs, dtype=np.int64)
pn = np.frombuffer(pn, dtype=np.int32)
pt = np.frombuffer(pt, dtype=np.float64)
N = len(veh)
np_per = np.diff(offs)

# consecutive-point edges
is_step = np.ones(len(pn), dtype=bool)
is_step[offs[1:] - 1] = False
is_step[-1] = False
si = np.nonzero(is_step)[0]
step_key = pn[si].astype(np.int64) * n + pn[si + 1]
pos = np.searchsorted(skey, step_key)
pos[pos >= len(skey)] = len(skey) - 1
found = skey[pos] == step_key
edge_of_step = np.where(found, order[pos], -1)
dt = pt[si + 1] - pt[si]
step_traj = np.searchsorted(offs, si, side="right") - 1

res = {}
res["rows"] = int(N)
res["bad_lines"] = bad_lines
res["vehicles"] = int(len(np.unique(veh)))
res["max_vehicle_id"] = int(veh.max())
res["points"] = int(len(pn))
res["points_per_traj_median"] = float(np.median(np_per))
res["single_point_traj"] = int((np_per == 1).sum())
res["nodes"] = int(n)
res["edges"] = int(len(edges))
res["camera_nodes"] = int(has_cam.sum())
res["camera_node_share"] = float(has_cam.mean())

# Trips per vehicle
tv = np.bincount(np.unique(veh, return_inverse=True)[1])
res["trips_per_vehicle_mean"] = float(tv.mean())
res["trips_per_vehicle_hist"] = {str(i): int((tv == i).sum()) for i in range(1, 6)}
res["trips_per_vehicle_6plus"] = int((tv >= 6).sum())

# Road-network connectivity
res["steps"] = int(len(si))
res["steps_on_a_published_edge"] = int(found.sum())
res["steps_on_a_published_edge_share"] = float(found.mean())
res["traj_fully_connected_share"] = float(1 - len(np.unique(step_traj[~found])) / N)
res["self_steps"] = int((pn[si] == pn[si + 1]).sum())
res["nonmonotonic_steps"] = int((dt < 0).sum())
res["zero_time_steps"] = int((dt == 0).sum())

# Recorded length and duration against the geometry
elen = edges.Length.values
lsum = np.bincount(step_traj[found], weights=elen[edge_of_step[found]], minlength=N)
ok = np_per > 1
res["length_vs_edge_sum_median_ratio"] = float(np.median(leng[ok] / np.maximum(lsum[ok], 1)))
res["length_vs_edge_sum_p01_p99"] = [float(x) for x in np.percentile(leng[ok] / np.maximum(lsum[ok], 1), [1, 99])]
first = pt[offs[:-1]]
last = pt[offs[1:] - 1]
res["departure_equals_first_point_share"] = float((np.abs(first - dep) < 0.51).mean())
res["duration_equals_span_median_abs_diff"] = float(np.median(np.abs(last - first - dur)))

# Which points are camera observations?
frac0 = np.abs(pt - np.round(pt)) < 1e-6
on_cam = has_cam[pn]
res["points_on_camera_node_share"] = float(on_cam.mean())
res["points_whole_second_share"] = float(frac0.mean())
res["camera_points_whole_second_share"] = float(frac0[on_cam].mean())
res["noncamera_points_whole_second_share"] = float(frac0[~on_cam].mean())
res["whole_second_points_on_camera_share"] = float(on_cam[frac0].mean())
# observed = on a camera node AND at a whole-second timestamp; 10% of interpolated times round to .0 by chance
obs = on_cam & frac0
res["observed_points"] = int(obs.sum())
res["observed_points_per_traj_median"] = float(np.median(np.add.reduceat(obs.astype(np.int32), offs[:-1])))
res["first_point_on_camera_share"] = float(has_cam[pn[offs[:-1]]].mean())
res["last_point_on_camera_share"] = float(has_cam[pn[offs[1:] - 1]].mean())
res["first_point_whole_second_share"] = float(frac0[offs[:-1]].mean())
res["last_point_whole_second_share"] = float(frac0[offs[1:] - 1].mean())

# Distributions
hours = np.floor(dep / 3600).astype(int).clip(0, 24)
res["departures_by_hour"] = np.bincount(hours, minlength=24).tolist()
res["span_seconds"] = [float(first.min()), float(last.max())]
q = [1, 5, 10, 25, 50, 75, 90, 95, 99]
res["length_m_pct"] = dict(zip(map(str, q), np.percentile(leng, q).round(1).tolist()))
res["duration_s_pct"] = dict(zip(map(str, q), np.percentile(dur, q).round(1).tolist()))
res["length_mean_m"] = float(leng.mean())
res["duration_mean_s"] = float(dur.mean())
sp = leng[dur > 0] / dur[dur > 0] * 3.6
res["speed_kmh_pct"] = dict(zip(map(str, q), np.percentile(sp, q).round(1).tolist()))
res["trip_under_1km_share"] = float((leng < 1000).mean())
res["trip_under_500m_share"] = float((leng < 500).mean())
res["trip_over_10km_share"] = float((leng > 10000).mean())
res["veh_km_total"] = float(leng.sum() / 1000)
res["veh_hours_total"] = float(dur.sum() / 3600)

# Network connectivity (strongly connected)
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

g = csr_matrix((np.ones(len(edges)), (edges.Origin, edges.Destination)), shape=(n, n))
nc, lab = connected_components(g, directed=True, connection="strong")
big = np.bincount(lab).argmax()
res["scc_count"] = int(nc)
res["largest_scc_nodes_share"] = float((lab == big).mean())
res["traj_points_in_largest_scc_share"] = float((lab[pn] == big).mean())

# Per-road counts
valid = edge_of_step >= 0
ecount = np.bincount(edge_of_step[valid], minlength=len(edges))
edges["count"] = ecount
hour_of_step = np.floor(pt[si][valid] / 3600).astype(np.int32).clip(0, 23)
eh = np.zeros((len(edges), 24), dtype=np.int32)
np.add.at(eh, (edge_of_step[valid], hour_of_step), 1)
res["edges_with_zero_count_share"] = float((ecount == 0).mean())
by = edges.groupby("Class").agg(edges=("count", "size"), km=("Length", lambda s: s.sum() / 1000), passes_median=("count", "median"), passes_p90=("count", lambda s: s.quantile(0.9)), passes_max=("count", "max"), passes_total=("count", "sum"))
by["veh_km"] = (edges["count"] * edges.Length / 1000).groupby(edges.Class).sum()
by["zero_share"] = (edges["count"] == 0).groupby(edges.Class).mean()
peak = eh.max(axis=1)
by["peak_hour_flow_p50"] = pd.Series(peak).groupby(edges.Class).median()
by["peak_hour_flow_p90"] = pd.Series(peak).groupby(edges.Class).quantile(0.9)
by["peak_hour_flow_max"] = pd.Series(peak).groupby(edges.Class).max()
by = by.sort_values("veh_km", ascending=False)
res["by_class"] = json.loads(by.round(3).to_json(orient="index"))
top = np.argsort(-peak)[:15]
res["top_peak_edges"] = [
    {"origin": int(edges.Origin[i]), "dest": int(edges.Destination[i]), "class": edges.Class[i], "len": float(edges.Length[i]), "peak_veh_h": int(peak[i]), "total": int(ecount[i])}
    for i in top
]
res["hourly_passes_total"] = eh.sum(axis=0).tolist()

# Camera-to-camera speeds and stops: the only timing not produced by the path model
oi = np.nonzero(obs)[0]
same = np.searchsorted(offs, oi, side="right")[:-1] == np.searchsorted(offs, oi, side="right")[1:]
gap = (pt[oi[1:]] - pt[oi[:-1]])[same]
hops = (oi[1:] - oi[:-1])[same]
res["camera_gap_s_pct"] = dict(zip(map(str, q), np.percentile(gap, q).round(1).tolist()))
res["camera_gap_hops_median"] = float(np.median(hops))
res["camera_gap_over_10min_share"] = float((gap > 600).mean())
res["gaps"] = int(len(gap))

print(json.dumps(res, indent=1))
json.dump(res, open(f"{out}/audit.json", "w"), indent=1)
np.savez_compressed(f"{out}/edge_hour.npz", eh=eh, count=ecount)
np.savez(f"{out}/traj.npz", veh=veh, trip=trip, dep=dep, dur=dur, leng=leng, offs=offs, pn=pn, pt=pt, edge_of_step=edge_of_step.astype(np.int32), si=si.astype(np.int64))
