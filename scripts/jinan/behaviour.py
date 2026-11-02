#!/usr/bin/env python3
"""Route choice in the Jinan trajectories: how close to shortest time, and how cars share routes.

Only first/last points and whole-second camera points are observations. Everything between them comes from
the paper's model, whose prior is Amap's transition counts, so inferred routes are reported apart from the
camera-waypoint bound, which uses observed points only.

usage: behaviour.py RAW_DIR DERIVED_DIR [SAMPLE_TRAJECTORIES]
"""
import json
import sys

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

raw, d = sys.argv[1], sys.argv[2]
SAMPLE = int(sys.argv[3]) if len(sys.argv) > 3 else 200000
z = np.load(f"{d}/traj.npz")
veh, dep, dur, leng, offs, pn, pt = (z[k] for k in ("veh", "dep", "dur", "leng", "offs", "pn", "pt"))
nodes = pd.read_csv(f"{raw}/node_jinan.csv")
edges = pd.read_csv(f"{raw}/edge_jinan.csv")
n = len(nodes)
cam = nodes.HasCamera.values.astype(bool)
elen = edges.Length.values
key = edges.Origin.values.astype(np.int64) * n + edges.Destination.values
order = np.argsort(key)
skey = key[order]


def edge_ids(a, b):
    k = a.astype(np.int64) * n + b
    p = np.searchsorted(skey, k).clip(0, len(skey) - 1)
    return np.where(skey[p] == k, order[p], -1)


PERIODS = {"night_00_06": (0, 6), "am_07_09": (7, 9), "mid_10_16": (10, 16), "pm_17_19": (17, 19), "eve_20_23": (20, 24)}


def period_of(h):
    for name, (a, b) in PERIODS.items():
        if a <= h < b:
            return name
    return "am_07_09" if h == 6 else "pm_17_19"


pnames = list(PERIODS)
phour = np.array([pnames.index(period_of(h)) for h in range(24)])

# Edge times per period from the trajectories themselves. Inferred times inherit the camera-to-camera time.
step = np.ones(len(pn), dtype=bool)
step[offs[1:] - 1] = False
si = np.nonzero(step)[0]
se = edge_ids(pn[si], pn[si + 1])
ok = se >= 0
si, se = si[ok], se[ok]
sdt = pt[si + 1] - pt[si]
sper = phour[np.floor(pt[si] / 3600).astype(int).clip(0, 23)]
ecost = np.zeros((len(pnames), len(edges)), dtype=np.float32)
freeflow = np.full(len(edges), np.nan, dtype=np.float32)
cls_sp = {}
for p in range(len(pnames)):
    m = sper == p
    df = pd.DataFrame({"e": se[m], "dt": sdt[m]})
    df = df[df.dt > 0]
    med = df.groupby("e").dt.median()
    cnt = df.groupby("e").dt.size()
    # class-level space-mean speed for thin edges
    ss = pd.DataFrame({"cls": edges.Class.values[df.e.values], "l": elen[df.e.values], "dt": df.dt.values}).groupby("cls").agg(l=("l", "sum"), dt=("dt", "sum"))
    v = (ss.l / ss.dt).to_dict()
    base = elen / np.array([v.get(c, 5.0) for c in edges.Class])
    c = base.astype(np.float32).copy()
    good = cnt[cnt >= 10].index.values
    c[good] = med.loc[good].values
    ecost[p] = np.maximum(c, 0.5)
    cls_sp[pnames[p]] = {k: round(val * 3.6, 1) for k, val in v.items()}

rng = np.random.default_rng(7)
N = len(dep)
speed = np.where(dur > 0, leng / np.maximum(dur, 1), 0) * 3.6
eligible = np.nonzero((np.diff(offs) >= 3) & (speed <= 130) & (leng >= 500))[0]
samp = rng.choice(eligible, size=min(SAMPLE, len(eligible)), replace=False)
samp.sort()
print("eligible", len(eligible), "sample", len(samp), flush=True)
s_per = phour[np.floor(dep[samp] / 3600).astype(int).clip(0, 23)]

# All-pairs shortest time per period, kept in float32 and only for the origins needed.
results = {k: np.full(len(samp), np.nan, dtype=np.float32) for k in ("c_obs", "c_sp", "c_wp", "l_obs", "l_sp", "n_obs")}
g_len = csr_matrix((elen, (edges.Origin, edges.Destination)), shape=(n, n))


def chunks(a, m):
    for i in range(0, len(a), m):
        yield a[i : i + m]


for p in range(len(pnames)):
    idx = np.nonzero(s_per == p)[0]
    if len(idx) == 0:
        continue
    g = csr_matrix((ecost[p], (edges.Origin, edges.Destination)), shape=(n, n))
    origins = set()
    route = {}
    for j in idx:
        row = samp[j]
        a, b = offs[row], offs[row + 1]
        ns, ts = pn[a:b], pt[a:b]
        keep = np.r_[True, ns[1:] != ns[:-1]]
        ns, ts = ns[keep], ts[keep]
        e = edge_ids(ns[:-1], ns[1:])
        if (e < 0).any():
            continue
        wp = (cam[ns] & (np.abs(ts - np.round(ts)) < 1e-6)).copy()
        wp[0] = wp[-1] = True
        w = ns[wp]
        route[j] = (e, w)
        origins.update(w[:-1].tolist())
    oarr = np.array(sorted(origins))
    opos = {int(o): i for i, o in enumerate(oarr)}
    D = np.zeros((len(oarr), n), dtype=np.float32)
    L = np.zeros((len(oarr), n), dtype=np.float32)
    done = 0
    for ch in chunks(oarr, 100):
        D[done : done + len(ch)] = dijkstra(g, directed=True, indices=ch)
        L[done : done + len(ch)] = dijkstra(g_len, directed=True, indices=ch)
        done += len(ch)
    for j, (e, w) in route.items():
        results["c_obs"][j] = ecost[p][e].sum()
        results["l_obs"][j] = elen[e].sum()
        results["c_sp"][j] = D[opos[int(w[0])], w[-1]]
        results["l_sp"][j] = L[opos[int(w[0])], w[-1]]
        results["c_wp"][j] = sum(D[opos[int(u)], v] for u, v in zip(w[:-1], w[1:]))
        results["n_obs"][j] = len(w)
    print("period", pnames[p], "trips", len(idx), "origins", len(oarr), flush=True)
    del D, L

m = np.isfinite(results["c_obs"]) & np.isfinite(results["c_sp"]) & (results["c_sp"] > 0)
c_obs, c_sp, c_wp, l_obs, l_sp, n_obs = (results[k][m] for k in ("c_obs", "c_sp", "c_wp", "l_obs", "l_sp", "n_obs"))
L = leng[samp][m]
x = c_obs - c_sp
xw = c_wp - c_sp


def table(mask, label):
    if mask.sum() == 0:
        return None
    a, b = x[mask], xw[mask]
    return dict(
        bin=label,
        trips=int(mask.sum()),
        exact_share=float((a < 0.5).mean()),
        within_30s=float((a < 30).mean()),
        within_5min=float((a < 300).mean()),
        excess_pct_median=float(np.median(a / c_sp[mask]) * 100),
        excess_pct_p90=float(np.percentile(a / c_sp[mask], 90) * 100),
        length_over_shortest_median=float(np.median(l_obs[mask] / np.maximum(l_sp[mask], 1))),
        waypoint_exact_share=float((b < 0.5).mean()),
        waypoint_within_30s=float((b < 30).mean()),
        waypoint_within_5min=float((b < 300).mean()),
        waypoint_excess_pct_median=float(np.median(b / c_sp[mask]) * 100),
        waypoint_excess_pct_p90=float(np.percentile(b / c_sp[mask], 90) * 100),
        observed_waypoints_median=float(np.median(n_obs[mask])),
    )


rows = [table(np.ones(len(x), dtype=bool), "all >=500 m")]
for lo, hi in ((500, 2000), (2000, 5000), (5000, 10000), (10000, 1e9)):
    rows.append(table((L >= lo) & (L < hi), f"{lo / 1000:g}-{hi / 1000:g} km"))
rows.append(table(n_obs >= 4, ">=4 observed waypoints"))
rows.append(table((n_obs >= 4) & (L >= 5000), ">=4 waypoints and >=5 km"))
res = {"route_vs_shortest": rows, "class_speed_kmh_by_period": cls_sp}
print(pd.DataFrame(rows).round(3).T.to_string(), flush=True)

# Route shares between camera pairs: inferred full routes and observed camera sequences.
good = np.nonzero((speed <= 130) & (leng >= 1000) & (np.diff(offs) >= 3))[0]
oi = pn[offs[good]].astype(np.int64)
di = pn[offs[good + 1] - 1].astype(np.int64)
od = oi * n + di
uod, inv, cnt = np.unique(od, return_inverse=True, return_counts=True)
big = np.nonzero(cnt >= 30)[0]
res["od_camera_pairs_ge30"] = int(len(big))
res["trajectories_in_those_pairs"] = int(cnt[big].sum())
res["all_trajectories_in_analysis"] = int(len(good))
inv_order = np.argsort(inv, kind="stable")
starts = np.r_[0, np.cumsum(cnt)]
out = []
for b in big:
    rows_b = good[inv_order[starts[b] : starts[b + 1]]]
    full, wp = [], []
    lens = leng[rows_b]
    for row in rows_b:
        ns = pn[offs[row] : offs[row + 1]]
        ts = pt[offs[row] : offs[row + 1]]
        full.append(hash(ns.tobytes()))
        w = cam[ns] & (np.abs(ts - np.round(ts)) < 1e-6)
        w[0] = w[-1] = True
        wp.append(hash(ns[w].tobytes()))
    def shares(v):
        _, c = np.unique(v, return_counts=True)
        p = np.sort(c / c.sum())[::-1]
        return p
    pf, pw = shares(full), shares(wp)
    out.append((len(rows_b), float(np.median(lens)), pf[0], (pf >= 0.05).sum(), 1 / (pf**2).sum(), pw[0], (pw >= 0.05).sum(), 1 / (pw**2).sum()))
o = pd.DataFrame(out, columns=["n", "len", "top", "routes5", "eff", "wtop", "wroutes5", "weff"])
for label, q in (("all", o), ("1-5 km", o[(o.len >= 1000) & (o.len < 5000)]), ("5-10 km", o[(o.len >= 5000) & (o.len < 10000)]), (">=10 km", o[o.len >= 10000])):
    if len(q) == 0:
        continue
    w = q.n / q.n.sum()
    res.setdefault("route_shares", []).append(
        dict(bin=label, od_pairs=int(len(q)), trajectories=int(q.n.sum()), top_route_share_median=float(q.top.median()), top_route_share_weighted=float((q.top * w).sum()), routes_over_5pct_median=float(q.routes5.median()), effective_routes_median=float(q.eff.median()), waypoint_top_share_median=float(q.wtop.median()), waypoint_top_share_weighted=float((q.wtop * w).sum()), waypoint_routes_over_5pct_median=float(q.wroutes5.median()), waypoint_effective_median=float(q.weff.median()))
    )
print(pd.DataFrame(res["route_shares"]).round(3).T.to_string(), flush=True)

# Day shape
h = np.floor(dep / 3600).astype(int).clip(0, 23)
hist = np.bincount(h, minlength=24).astype(float)
res["day_shape"] = {
    "share_by_hour": (hist / hist.sum()).round(4).tolist(),
    "busiest_hour": int(hist.argmax()),
    "busiest_hour_share": float(hist.max() / hist.sum()),
    "am_07_09_share": float(hist[7:9].sum() / hist.sum()),
    "pm_16_18_share": float(hist[16:18].sum() / hist.sum()),
    "midday_10_16_mean_over_am_peak": float(hist[10:16].mean() / hist[7:9].mean()),
    "night_00_05_share": float(hist[0:5].sum() / hist.sum()),
}
print(json.dumps(res["day_shape"]), flush=True)

# Repeat trajectories on one vehicle: gap between its trajectories, a fingerprint of split trips.
ord2 = np.lexsort((dep, veh))
v2, d2, u2 = veh[ord2], dep[ord2], dur[ord2]
same = v2[1:] == v2[:-1]
gaps = (d2[1:] - (d2[:-1] + u2[:-1]))[same]
res["same_vehicle_gap_s_pct"] = {str(q): float(np.percentile(gaps, q)) for q in (10, 25, 50, 75, 90)}
res["same_vehicle_gap_under_30min_share"] = float((gaps < 1800).mean())
json.dump(res, open(f"{d}/behaviour.json", "w"), indent=1)
print(json.dumps({k: res[k] for k in ("same_vehicle_gap_s_pct", "same_vehicle_gap_under_30min_share", "od_camera_pairs_ge30", "trajectories_in_those_pairs", "all_trajectories_in_analysis")}))
