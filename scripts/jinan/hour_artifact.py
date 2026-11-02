#!/usr/bin/env python3
"""Does the data change character at a clock hour? Inferred step speeds against observed camera-leg speeds by hour.

usage: hour_artifact.py RAW_DIR DERIVED_DIR
"""
import sys

import numpy as np
import pandas as pd

raw, d = sys.argv[1], sys.argv[2]
z = np.load(f"{d}/traj.npz")
offs, pn, pt = z["offs"], z["pn"], z["pt"]
nodes = pd.read_csv(f"{raw}/node_jinan.csv")
edges = pd.read_csv(f"{raw}/edge_jinan.csv", usecols=["Origin", "Destination", "Length"])
n = len(nodes)
key = edges.Origin.values.astype(np.int64) * n + edges.Destination.values
order = np.argsort(key)
skey = key[order]
cam = nodes.HasCamera.values.astype(bool)
step = np.ones(len(pn), dtype=bool)
step[offs[1:] - 1] = False
si = np.nonzero(step)[0]
k = pn[si].astype(np.int64) * n + pn[si + 1]
p = np.searchsorted(skey, k).clip(0, len(skey) - 1)
e = np.where(skey[p] == k, order[p], -1)
slen = np.zeros(len(pn))
slen[si[e >= 0]] = edges.Length.values[e[e >= 0]]
dt = pt[si + 1] - pt[si]
ok = (e >= 0) & (dt > 0)
hour = np.floor(pt[si] / 3600).astype(int).clip(0, 23)
sp = 3.6 * slen[si] / np.maximum(dt, 0.1)

obs = cam[pn] & (np.abs(pt - np.round(pt)) < 1e-6)
obs[offs[:-1]] = True
obs[offs[1:] - 1] = True
cum = np.cumsum(slen)
oi = np.nonzero(obs)[0]
tr = np.searchsorted(offs, oi, side="right") - 1
same = tr[1:] == tr[:-1]
a, b = oi[:-1][same], oi[1:][same]
ldt = pt[b] - pt[a]
llen = cum[b - 1] - np.where(a > 0, cum[a - 1], 0)
lsp = 3.6 * llen / np.maximum(ldt, 1)
lhour = np.floor(pt[a] / 3600).astype(int).clip(0, 23)
print("hour step_median_kmh step_frac_under5 leg_median_kmh leg_frac_under5 legs steps_per_leg recorded_per_100_points")
ph = np.floor(pt / 3600).astype(int).clip(0, 23)
for h in range(24):
    m = ok & (hour == h)
    l = (lhour == h) & (ldt > 0)
    print(h, round(float(np.median(sp[m])), 1), round(float((sp[m] < 5).mean()), 3), round(float(np.median(lsp[l])), 1), round(float((lsp[l] < 5).mean()), 3), int(l.sum()), round(float(m.sum() / max(l.sum(), 1)), 2), round(float(100 * obs[ph == h].mean()), 1))
