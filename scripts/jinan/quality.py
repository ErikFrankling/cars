#!/usr/bin/env python3
"""Tests of the trajectories that the paper's own metrics do not make: impossible same-vehicle overlaps,
revisited nodes, whether observed cameras agree with the most common inferred route, and day bands.

usage: quality.py RAW_DIR DERIVED_DIR
"""
import json
import sys
from collections import Counter

import numpy as np
import pandas as pd

raw, d = sys.argv[1], sys.argv[2]
z = np.load(f"{d}/traj.npz")
veh, dep, dur, leng, offs, pn, pt = (z[k] for k in ("veh", "dep", "dur", "leng", "offs", "pn", "pt"))
nodes = pd.read_csv(f"{raw}/node_jinan.csv")
cam = nodes.HasCamera.values.astype(bool)
N = len(dep)
res = {}

# One vehicle cannot be in two trajectories at the same time.
o = np.lexsort((dep, veh))
v2, d2, u2 = veh[o], dep[o].astype(np.float64), dur[o].astype(np.float64)
same = v2[1:] == v2[:-1]
gap = (d2[1:] - (d2[:-1] + u2[:-1]))[same]
res["same_vehicle_pairs"] = int(same.sum())
res["same_vehicle_overlap_share"] = float((gap < 0).mean())
res["same_vehicle_gap_under_5min_share"] = float(((gap >= 0) & (gap < 300)).mean())
vs, cnt = np.unique(veh, return_counts=True)
multi = vs[cnt > 1]
bad = np.unique(v2[1:][same][gap < 0])
res["vehicles_multi_trip"] = int(len(multi))
res["vehicles_with_overlap"] = int(len(bad))
res["trajectories_on_overlapping_vehicles_share"] = float(np.isin(veh, bad).mean())

# Revisited nodes and how far the two ends lie apart, by length: tours and false links show up here.
rng = np.random.default_rng(3)
idx = rng.choice(N, size=min(300000, N), replace=False)
lat, lon = nodes.Latitude.values, nodes.Longitude.values
rows = []
for r in idx:
    ns = pn[offs[r] : offs[r + 1]]
    a, b = ns[0], ns[-1]
    dx = (lon[a] - lon[b]) * 111320 * np.cos(np.radians(36.65))
    dy = (lat[a] - lat[b]) * 110540
    rows.append((leng[r], len(np.unique(ns)) < len(ns), np.hypot(dx, dy)))
t = pd.DataFrame(rows, columns=["l", "revisit", "crow"])
t["detour"] = t.l / t.crow.clip(lower=1)
res["by_length"] = []
for lo, hi in ((0, 1000), (1000, 2000), (2000, 5000), (5000, 10000), (10000, 20000), (20000, 1e9)):
    q = t[(t.l >= lo) & (t.l < hi)]
    res["by_length"].append(dict(km=f"{lo / 1000:g}-{hi / 1000:g}", share=float(len(q) / len(t)), revisit_share=float(q.revisit.mean()), detour_median=float(q.detour.median()), detour_over_2_share=float((q.detour > 2).mean())))

# Between camera pairs: do observed cameras lie on the pair's most common inferred route?
speed = np.where(dur > 0, leng / np.maximum(dur, 1), 0) * 3.6
good = np.nonzero((speed <= 130) & (leng >= 1000) & (np.diff(offs) >= 3))[0]
n = len(nodes)
od = pn[offs[good]].astype(np.int64) * n + pn[offs[good + 1] - 1]
uod, inv, c = np.unique(od, return_inverse=True, return_counts=True)
big = np.nonzero(c >= 30)[0]
order = np.argsort(inv, kind="stable")
starts = np.r_[0, np.cumsum(c)]
on_top = off_top = with_inner = total = 0
same_as_top = 0
for b in big:
    rows_b = good[order[starts[b] : starts[b + 1]]]
    seqs = [pn[offs[r] : offs[r + 1]] for r in rows_b]
    h = [x.tobytes() for x in seqs]
    top = Counter(h).most_common(1)[0][0]
    topset = set(np.frombuffer(top, dtype=pn.dtype).tolist())
    for r, s, key in zip(rows_b, seqs, h):
        ts = pt[offs[r] : offs[r + 1]]
        w = cam[s] & (np.abs(ts - np.round(ts)) < 1e-6)
        w[0] = w[-1] = False
        inner = s[w]
        total += 1
        same_as_top += key == top
        if len(inner) == 0:
            continue
        with_inner += 1
        if all(int(x) in topset for x in inner):
            on_top += 1
        else:
            off_top += 1
res["top_route_test"] = dict(trajectories=int(total), inferred_same_as_top_share=float(same_as_top / total), with_inner_camera_share=float(with_inner / total), inner_cameras_all_on_top_share=float(on_top / max(with_inner, 1)), some_inner_camera_off_top_share=float(off_top / max(with_inner, 1)))

# Passes through a camera node with and without a record
all_cam = cam[pn]
frac0 = np.abs(pt - np.round(pt)) < 1e-6
inner_mask = np.ones(len(pn), dtype=bool)
inner_mask[offs[:-1]] = False
inner_mask[offs[1:] - 1] = False
p = (frac0[inner_mask & all_cam].mean() - 0.1) / 0.9
res["inner_camera_pass_with_record_share_estimate"] = float(p)
res["inner_points"] = int(inner_mask.sum())
res["inner_points_with_record_estimate_share"] = float(p * (inner_mask & all_cam).sum() / inner_mask.sum())

# Day bands used by the Stockholm demand script, and peak ratios.
h = np.floor(dep / 3600).astype(int).clip(0, 23)
hist = np.bincount(h, minlength=24) / N
res["day_bands"] = dict(b06_18=float(hist[6:18].sum()), b18_22=float(hist[18:22].sum()), b22_06=float(hist[22:].sum() + hist[:6].sum()), peak_hour_over_06_18_mean=float(hist[6:18].max() / hist[6:18].mean()), min_over_max_07_18=float(hist[7:18].min() / hist[7:18].max()))
res["recorded_time_per_vehicle_km_per_day"] = float(leng.sum() / 1000 / len(vs))
print(json.dumps(res, indent=1))
json.dump(res, open(f"{d}/quality.json", "w"), indent=1)
