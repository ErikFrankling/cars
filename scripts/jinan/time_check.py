#!/usr/bin/env python3
"""Time-of-day structure of Jinan points: observed camera records against inferred points, by 15 minutes.

usage: time_check.py RAW_DIR DERIVED_DIR
"""
import json
import sys

import numpy as np
import pandas as pd

raw, d = sys.argv[1], sys.argv[2]
z = np.load(f"{d}/traj.npz")
pn, pt, offs = z["pn"], z["pt"], z["offs"]
nodes = pd.read_csv(f"{raw}/node_jinan.csv")
cam = nodes.HasCamera.values.astype(bool)
obs = cam[pn] & (np.abs(pt - np.round(pt)) < 1e-6)
q = np.floor(pt / 900).astype(int).clip(0, 95)
allp = np.bincount(q, minlength=96)
obsp = np.bincount(q[obs], minlength=96)
active = np.zeros(96, dtype=int)
for b in range(96):
    active[b] = len(np.unique(pn[obs & (q == b)]))
tdf = pd.DataFrame({"hhmm": [f"{i//4:02d}:{(i%4)*15:02d}" for i in range(96)], "points": allp, "observed": obsp, "cameras_seen": active})
pd.set_option("display.width", 200)
pd.set_option("display.max_rows", 120)
print(tdf.iloc[20:96:2].to_string())

# Trajectories that run through 19:00-20:00
dep = z["dep"]
dur = z["dur"]
print("h19 passes by departure hour of the trajectory")
tr = np.repeat(np.arange(len(dep)), np.diff(offs))
h = np.floor(pt / 3600).astype(int).clip(0, 23)
depH = np.floor(dep / 3600).astype(int).clip(0, 23)
print(np.bincount(depH[tr[h == 19]], minlength=24))
print("h18 passes by departure hour")
print(np.bincount(depH[tr[h == 18]], minlength=24))

# Busiest nodes in 19:00-20:00 compared with 18:00-19:00
a = np.bincount(pn[h == 19], minlength=len(nodes))
b = np.bincount(pn[h == 18], minlength=len(nodes))
diff = np.argsort(-(a - b))[:8]
print("largest rises at 19h", [(int(i), int(a[i]), int(b[i]), bool(cam[i])) for i in diff])
print("sum of the rise on the top 100 nodes", int(np.sort(a - b)[-100:].sum()), "total rise", int(a.sum() - b.sum()))
print("share of passes at 19h on nodes that rose over 50%:", float(a[a > 1.5 * b + 20].sum() / a.sum()))

# Camera uptime
nb = np.zeros((len(nodes), 96), dtype=np.int32)
np.add.at(nb, (pn[obs], q[obs]), 1)
seen = nb > 0
day = seen[:, 28:84]  # 07:00 to 21:00
cams = np.nonzero(cam)[0]
act = day[cams].mean(axis=1)
print("camera nodes never observed:", int((nb[cams].sum(axis=1) == 0).sum()), "of", len(cams))
print("share of 07-21 quarter hours a camera node records anything, pctl 10,25,50,75,90:", np.percentile(act, [10, 25, 50, 75, 90]).round(2).tolist())
print("observed points per camera node, pctl 10,50,90,99:", np.percentile(nb[cams].sum(axis=1), [10, 50, 90, 99]).tolist())
top = np.sort(nb[cams].sum(axis=1))[::-1]
print("share of observed points on top 10% of camera nodes:", float(top[: len(top) // 10].sum() / top.sum()))
tdf.to_csv(f"{d}/time_check.csv", index=False)
