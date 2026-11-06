#!/usr/bin/env python3
"""How far can route choice alone take the site flows, with OD and departure times fixed? A diagnostic for the kill rule, never a calibration: its splits are thrown away.
    route_bound.py PREP RUN HOUR
Uses each leg's kept paths (macro run with --save-paths 1). Exponentiated gradient on each leg's split, starting from macro's, against the median real flow per tuning site in that hour.
For each step size, prints the fit and the share of the hour's vehicle-km that had to move. Little moved and a good fit: routes are the fault. No fit even with much moved: demand."""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

DATA = Path('/home/erikf/projects/personal/cars-data/berlin2019')
prep, run, hour = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
edges = pd.read_csv(prep / 'edges.tsv', sep='\t', keep_default_na=False, dtype={'id': str})
eidx = {k: i for i, k in enumerate(edges.id)}
arcs = pd.read_csv(prep / 'arcs.tsv', sep='\t')
afrom = arcs['from'].values
tuning = set(json.load(open(DATA / 'step1/freeze.json'))['tuning_sites'])
real = pd.read_csv(DATA / 'step1/real_days.csv.gz')
real = real[real.site.isin(tuning) & (real.hour == hour)].groupby('site').flow.median()
sites = pd.read_csv(prep / 'sites.tsv', sep='\t', dtype={'edge': str})
sites = sites[sites.site.isin(real.index)]
edge_sites = {}
for i, s in enumerate(sites.itertuples()):
    ls = len(str(s.lanes).split())
    share = min(ls / max(edges.lanes[eidx[s.edge]], 1), 1.0)
    edge_sites.setdefault(eidx[s.edge], []).append((i, share))
y = real.loc[sites.site].values.astype(float)
legs = pd.read_csv(prep / 'legs.tsv', sep='\t', keep_default_na=False, dtype={'o': str, 'd': str})
legs = legs[(legs.dep // 3600) == hour].reset_index(drop=True)
paths = [np.array(l.split(), dtype=np.int64) for l in open(run / 'paths.tsv')]
leg_paths = [l.split() for l in open(run / 'leg_paths.tsv')]
assert len(leg_paths) == len(legs), (len(leg_paths), len(legs))
Lm = edges.L.values
pid, leg_of, f0, km = [], [], [], []
ri, ci, vi = [], [], []
n = 0
w = legs.w.values
for i, lp in enumerate(leg_paths):
    for item in lp:
        p, fr = item.split(':')
        a = paths[int(p)]
        es = afrom[a] if len(a) else np.array([], dtype=np.int64)
        leg_of.append(i)
        f0.append(float(fr))
        km.append(w[i] * Lm[es].sum() / 1000 if len(es) else 0.0)
        for e in es:
            for s, sh in edge_sites.get(int(e), ()):
                ri.append(s)
                ci.append(n)
                vi.append(w[i] * sh)
        n += 1
leg_of, f0, km = np.array(leg_of), np.array(f0), np.array(km)
A = csr_matrix((vi, (ri, ci)), shape=(len(y), n))
print('legs', len(legs), 'kept paths', n, 'sites', len(y), 'mean paths per leg', round(n / max(len(legs), 1), 2), 'vkm', round(float((km * f0).sum())))


def fit(f):
    m = A @ f
    r = np.corrcoef(m, y)[0, 1] ** 2
    return dict(r2=round(float(r), 3), slope=round(float(np.polyfit(y, m, 1)[0]), 3), rmsn=round(float(np.sqrt(np.mean((m - y) ** 2)) / y.mean()), 3), bias=round(float(m.sum() / y.sum() - 1), 3), geh5=round(float(np.mean(np.sqrt(2 * (m - y) ** 2 / (m + y + 1e-9)) < 5)), 3))


print('start', fit(f0))
f = f0.copy()
lf = np.log(np.maximum(f0, 1e-6))
eta = 2e-6
for it in range(1, 401):
    g = A.T @ (A @ f - y)
    lf = lf - eta * g
    # renormalise per leg
    e = np.exp(lf)
    t = np.bincount(leg_of, e, minlength=len(legs))
    f = e / t[leg_of]
    lf = np.log(np.maximum(f, 1e-12))
    if it in (5, 10, 20, 40, 80, 160, 400):
        tv = float((np.abs(f - f0) * km).sum() / 2 / max((km * f0).sum(), 1))
        print('step', it, fit(f), 'vehicle-km moved', round(tv, 3))
