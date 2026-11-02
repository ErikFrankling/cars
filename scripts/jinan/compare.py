#!/usr/bin/env python3
"""Compare a cars run on Jinan with the camera data: road counts, speeds by class and hour, paired trip times.

Counts come from the same routes that the simulation drives, so they mainly test whether the net can carry them.
Speeds and trip times are the independent test. The data side is limited to the sampled vehicles.

usage: compare.py RAW_DIR DERIVED_DIR SCENARIO_DIR RUN_DIR SCALE [END_HOUR [BEGIN_HOUR]]
Writes RUN_DIR/compare.json. RUN_DIR holds edges.csv, trips.csv, summary.csv.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

raw, d, sc, run, scale = sys.argv[1:6]
scale = float(scale)
end_h = int(sys.argv[6]) if len(sys.argv) > 6 else 24  # for runs stopped early, hours from this on are left out
begin_h = int(sys.argv[7]) if len(sys.argv) > 7 else 0  # for runs over a window of the day
z = np.load(f"{d}/traj.npz")
offs, pn, pt, leng, dur = (z[k] for k in ("offs", "pn", "pt", "leng", "dur"))
nodes_n = len(pd.read_csv(f"{raw}/node_jinan.csv", usecols=[0]))
edges = pd.read_csv(f"{raw}/edge_jinan.csv", usecols=["Origin", "Destination", "Class", "Length"])
key = edges.Origin.values.astype(np.int64) * nodes_n + edges.Destination.values
order = np.argsort(key)
skey = key[order]

idx = pd.read_csv(f"{sc}/route_index.csv")
idx = idx[idx.vrand < scale]
rows = np.sort(idx.row.unique())
tmask = np.zeros(len(leng), dtype=bool)
tmask[rows] = True

# Data side: passes and time per edge-hour for the sampled trajectories
step = np.ones(len(pn), dtype=bool)
step[offs[1:] - 1] = False
si = np.nonzero(step)[0]
t_of = np.searchsorted(offs, si, side="right") - 1
si = si[tmask[t_of]]
k = pn[si].astype(np.int64) * nodes_n + pn[si + 1]
p = np.searchsorted(skey, k).clip(0, len(skey) - 1)
e = np.where(skey[p] == k, order[p], -1)
ok = e >= 0
si, e = si[ok], e[ok]
is_first = np.isin(si, offs[:-1])  # cars does not count an inserted vehicle as entering its first edge
hr = np.floor(pt[si] / 3600).astype(int).clip(0, 23)
dt = pt[si + 1] - pt[si]
data = pd.DataFrame({"edge": e, "hour": hr, "dt": dt, "nf": (~is_first).astype(np.int32)})
data["len"] = edges.Length.values[e]
data["kmh"] = 3.6 * data.len / data.dt.clip(lower=0.5)
# data_kmh_med follows the paper: a robust speed per road, so parked cars and false links do not dominate
dg = data.groupby(["edge", "hour"]).agg(data_n=("nf", "sum"), data_all=("nf", "size"), data_t=("dt", "sum"), data_d=("len", "sum"), data_med=("kmh", "median")).reset_index()

sim = pd.read_csv(f"{run}/edges.csv")
sim = sim[sim.edge.str.startswith("e")].copy()
sim["e"] = sim.edge.str[1:].astype(int)
sim["hour"] = (sim.begin / 3600).astype(int).clip(0, 23)
sg = sim.groupby(["e", "hour"]).agg(sim_n=("entered", "sum"), sim_t=("samples", "sum"), sim_d=("distance", "sum"), teleports=("teleports", "sum")).reset_index().rename(columns={"e": "edge"})
m = dg.merge(sg, on=["edge", "hour"], how="outer").fillna(0)
m = m[(m.hour < end_h) & (m.hour >= begin_h)].copy()
m["cls"] = edges.Class.values[m.edge.astype(int)]
res = {"scale": scale, "routes_in_sample": int(len(idx))}


def geh(a, b):
    return np.sqrt(2 * (a - b) ** 2 / np.maximum(a + b, 1e-9))


def count_stats(df):
    a, b = df.data_n.values, df.sim_n.values
    r = float(np.corrcoef(a, b)[0, 1]) if len(a) > 2 and a.std() > 0 and b.std() > 0 else None
    return dict(cells=int(len(df)), data=float(a.sum()), sim=float(b.sum()), sim_over_data=float(b.sum() / max(a.sum(), 1)), r2=None if r is None else r * r, geh5_share=float((geh(a, b) < 5).mean()), mae=float(np.abs(a - b).mean()))


res["counts_edge_hour"] = count_stats(m)
daily = m.groupby("edge").agg(data_n=("data_n", "sum"), sim_n=("sim_n", "sum")).reset_index()
daily["cls"] = edges.Class.values[daily.edge.astype(int)]
res["counts_edge_day"] = count_stats(daily)
res["counts_edge_day_by_class"] = {c: count_stats(g) for c, g in daily.groupby("cls") if len(g) >= 50}
res["teleports"] = float(m.teleports.sum())
res["simulated_share_of_data_passes_by_hour"] = (m.groupby("hour").sim_n.sum() / m.groupby("hour").data_n.sum().clip(lower=1)).round(3).tolist()

# Speeds: space-mean from distance over time, weighted by the traffic each side carries.
speeds = []
for (c, h), g in m.groupby(["cls", "hour"]):
    if g.data_t.sum() > 0 and g.sim_t.sum() > 0:
        speeds.append((c, h, 3.6 * g.data_d.sum() / g.data_t.sum(), 3.6 * g.sim_d.sum() / g.sim_t.sum(), g.data_n.sum(), g.sim_n.sum()))
m["sim_kmh"] = 3.6 * m.sim_d / m.sim_t.replace(0, np.nan)
v = m[(m.data_all > 0) & (m.sim_t > 0)]
wm = lambda g, c: float((g[c] * g.data_all).sum() / max(g.data_all.sum(), 1))
res["speed_robust_by_hour_kmh"] = {"data_median": [round(wm(g, "data_med"), 1) for _, g in v.groupby("hour")], "sim": [round(wm(g, "sim_kmh"), 1) for _, g in v.groupby("hour")]}
day = v[(v.hour >= 8) & (v.hour <= 18)]
res["speed_robust_by_class_8_19_kmh"] = {c: dict(data_median=wm(g, "data_med"), sim=wm(g, "sim_kmh"), passes=int(g.data_all.sum())) for c, g in day.groupby("cls") if g.data_all.sum() > 100}
big_cells = v[v.data_all >= max(20, 2000 * scale)]
if len(big_cells) > 5:
    res["speed_robust_edge_hour"] = dict(cells=int(len(big_cells)), threshold=float(max(20, 2000 * scale)), mae_kmh=float((big_cells.sim_kmh - big_cells.data_med).abs().mean()), bias_kmh=float((big_cells.sim_kmh - big_cells.data_med).mean()), r=float(np.corrcoef(big_cells.sim_kmh, big_cells.data_med)[0, 1]))
sp = pd.DataFrame(speeds, columns=["cls", "hour", "data_kmh", "sim_kmh", "data_n", "sim_n"])
sp.to_csv(f"{run}/speed_class_hour.csv", index=False)
byh = m.groupby("hour").agg(dd=("data_d", "sum"), dt=("data_t", "sum"), sd=("sim_d", "sum"), st=("sim_t", "sum"))
res["speed_by_hour_kmh"] = {"data": (3.6 * byh.dd / byh.dt.clip(lower=1)).round(1).tolist(), "sim": (3.6 * byh.sd / byh.st.clip(lower=1)).round(1).tolist()}
byc = m[(m.hour >= 8) & (m.hour <= 18)].groupby("cls").agg(dd=("data_d", "sum"), dt=("data_t", "sum"), sd=("sim_d", "sum"), st=("sim_t", "sum"), n=("data_n", "sum"))
res["speed_by_class_8_19_kmh"] = {c: dict(data=float(3.6 * r["dd"] / max(r["dt"], 1)), sim=float(3.6 * r["sd"] / max(r["st"], 1)), passes=int(r.n)) for c, r in byc.iterrows() if r.n > 100}
big = sp[sp.data_n > 200]
if len(big):
    res["speed_class_hour_table"] = dict(cells=int(len(big)), mae_kmh=float((big.sim_kmh - big.data_kmh).abs().mean()), bias_kmh=float((big.sim_kmh - big.data_kmh).mean()), r=float(np.corrcoef(big.sim_kmh, big.data_kmh)[0, 1]) if len(big) > 2 else None)

# Per-edge speed in the busy day, for edges with enough traffic
pe = m[(m.hour >= 8) & (m.hour <= 18)].groupby("edge").agg(dd=("data_d", "sum"), dt=("data_t", "sum"), sd=("sim_d", "sum"), st=("sim_t", "sum"), n=("data_n", "sum"))
thresh = max(30, 1000 * scale)
pe = pe[(pe.n >= thresh) & (pe.dt > 0) & (pe.st > 0)]
if len(pe) > 5:
    a, b = 3.6 * pe.dd / pe.dt, 3.6 * pe.sd / pe.st
    res["speed_per_edge_8_19"] = dict(edges=int(len(pe)), threshold_passes=float(thresh), mae_kmh=float((a - b).abs().mean()), bias_kmh=float((b - a).mean()), r=float(np.corrcoef(a, b)[0, 1]), data_median=float(a.median()), sim_median=float(b.median()))

# Paired trips
tr = pd.read_csv(f"{run}/trips.csv").rename(columns={"trip": "id"})
tj = idx[(idx.last_time < end_h * 3600) & (idx.first_time >= begin_h * 3600)].merge(tr, on="id", how="left")
res["trips_arrived"] = int(tj.duration.notna().sum())
res["trips_arrived_share"] = float(tj.duration.notna().mean())
pair = tj[tj.duration.notna() & (tj.real_length > 0) & (tj.real_duration >= 20)].copy()
pair["real_kmh"] = 3.6 * pair.real_length / pair.real_duration
pair = pair[(pair.real_kmh >= 3) & (pair.real_kmh <= 130)]
res["paired_trips"] = int(len(pair))


def paired(df):
    if len(df) < 20:
        return None
    r = df.duration / df.real_duration
    return dict(trips=int(len(df)), real_median_s=float(df.real_duration.median()), sim_median_s=float(df.duration.median()), ratio_median=float(r.median()), ratio_p10=float(r.quantile(0.1)), ratio_p90=float(r.quantile(0.9)), mae_s=float((df.duration - df.real_duration).abs().mean()), r=float(np.corrcoef(df.duration, df.real_duration)[0, 1]), real_kmh=float(3.6 * df.real_length.sum() / df.real_duration.sum()), sim_kmh=float(3.6 * df.real_length.sum() / df.duration.sum()), sim_waiting_share=float(df.waiting.sum() / df.duration.sum()))


# Trajectories run on through any stop under 30 minutes, so also keep only those with no stop-like camera leg.
# Thresholds chosen before any run above 1%: every leg between observed points at 5 to 130 km/h.
cam = pd.read_csv(f"{raw}/node_jinan.csv").HasCamera.values.astype(bool)
obs = cam[pn] & (np.abs(pt - np.round(pt)) < 1e-6)
obs[offs[:-1]] = True
obs[offs[1:] - 1] = True
step_len = np.zeros(len(pn))
sa = np.nonzero(step)[0]
ka = pn[sa].astype(np.int64) * nodes_n + pn[sa + 1]
pa = np.searchsorted(skey, ka).clip(0, len(skey) - 1)
ea = np.where(skey[pa] == ka, order[pa], -1)
step_len[sa[ea >= 0]] = edges.Length.values[ea[ea >= 0]]
cum = np.cumsum(step_len)
oi = np.nonzero(obs)[0]
tr_of = np.searchsorted(offs, oi, side="right") - 1
same = tr_of[1:] == tr_of[:-1]
dlen = (cum[oi[1:] - 1] - np.where(oi[:-1] > 0, cum[oi[:-1] - 1], 0))[same]
dtim = (pt[oi[1:]] - pt[oi[:-1]])[same]
vleg = 3.6 * dlen / np.maximum(dtim, 1)
clean = np.ones(len(leng), dtype=bool)
clean[tr_of[:-1][same][(vleg < 5) | (vleg > 130)]] = False
res["clean_trajectory_share"] = float(clean.mean())
res["leg_speed_kmh_pct"] = {str(q): float(np.percentile(vleg, q)) for q in (5, 25, 50, 75, 95)}
res["paired_clean"] = paired(pair[clean[pair.row.values]])
res["paired_clean_by_hour"] = {int(h): paired(g) for h, g in pair[clean[pair.row.values]].assign(h=(pair.first_time / 3600).astype(int).clip(0, 23)).groupby("h")}
res["paired_clean_by_length"] = {f"{a}-{b} km": paired(pair[clean[pair.row.values] & (pair.real_length >= a * 1000) & (pair.real_length < b * 1000)]) for a, b in ((0, 2), (2, 5), (5, 10), (10, 100))}
res["paired_all"] = paired(pair)
res["paired_by_length"] = {f"{a}-{b} km": paired(pair[(pair.real_length >= a * 1000) & (pair.real_length < b * 1000)]) for a, b in ((0, 2), (2, 5), (5, 10), (10, 100))}
pair["h"] = (pair.first_time / 3600).astype(int).clip(0, 23)
res["paired_by_hour"] = {int(h): paired(g) for h, g in pair.groupby("h")}

s = pd.read_csv(f"{run}/summary.csv") if os.path.exists(f"{run}/summary.csv") else None
if s is not None and len(s):
    res["summary_tail"] = s.tail(1).to_dict(orient="records")[0]
    res["max_running"] = float(s.running.max()) if "running" in s else None
    res["summary_cols"] = list(s.columns)

json.dump(res, open(f"{run}/compare.json", "w"), indent=1)
keep = {k: res[k] for k in res if k not in ("paired_by_hour", "counts_edge_day_by_class", "summary_cols")}
print(json.dumps(keep, indent=0)[:6000])
