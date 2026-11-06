#!/usr/bin/env python3
"""Free time on every edge from probes at 05-06 h, R 3: L over v_hm, the time a crossing car spends, signal stops at low flow included.
Edges with under 40 probes or under 30 m: the median probe-over-table ratio of their road class, apart for edges that end at a signal.
Adds column sig_free (1 when the edge ends at a signal), so the engine adds only delay above Webster's zero-flow value. MEASURED, HERE May 2019.
    free_time.py PREP_IN PREP_OUT"""
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path('/home/erikf/projects/personal/cars-data/berlin2019')
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
dst.mkdir(parents=True, exist_ok=True)
for f in src.iterdir():
    if f.name != 'edges.tsv' and f.is_file():
        t = dst / f.name
        if not t.exists():
            t.symlink_to(f.resolve())
ed = pd.read_csv(src / 'edges.tsv', sep='\t', keep_default_na=False, dtype={'id': str})
meta = pd.read_csv(src / 'edge_meta.csv', keep_default_na=False, dtype={'id': str})
conns = pd.read_csv(src / 'conns.tsv', sep='\t', keep_default_na=False, usecols=['arc', 'kind'])
arcs = pd.read_csv(src / 'arcs.tsv', sep='\t', usecols=['id', 'from'])
sig = np.zeros(len(ed), bool)
sig[arcs.set_index('id').loc[conns[conns.kind == 1].arc.unique(), 'from'].values] = True
z = np.load(DATA / 'probes/edge_15min.npz', allow_pickle=True)
keys = {str(k): i for i, k in enumerate(z['keys'])}
ki = np.array([keys.get(k, -1) for k in ed.id])
has = ki >= 0
w = np.nan_to_num(z['vol'][ki[has]][:, :, 20:24])
hm = np.nan_to_num(z['hm'][ki[has]][:, :, 20:24])
n = w.sum(axis=(1, 2))
v = np.full(len(ed), np.nan)
v[np.where(has)[0]] = np.where(n >= 40, (w * hm).sum(axis=(1, 2)) / np.maximum(n, 1e-9) / 3.6, np.nan)
v[ed.L.values < 30] = np.nan
ok = np.isfinite(v) & (v > 1)
r = pd.DataFrame(dict(type=meta.type, sig=sig, ratio=np.where(ok, v / ed.v.values, np.nan)))
tab = r[ok].groupby(['type', 'sig']).ratio.agg(['median', 'size'])
tab = tab[tab['size'] >= 8]
print(tab.round(3).to_string())
gen = r[ok].groupby('sig').ratio.median()
new = ed.v.values.copy()
for i in range(len(ed)):
    if ok[i]:
        new[i] = v[i]
    else:
        key = (meta.type[i], sig[i])
        new[i] = ed.v.values[i] * (tab.loc[key, 'median'] if key in tab.index else gen[sig[i]])
print('edges from own probes', int(ok.sum()), 'of', len(ed), '; ending at a signal', int(sig.sum()))
ed['v'] = np.round(new, 3)
ed['sig_free'] = sig.astype(int)
ed.to_csv(dst / 'edges.tsv', sep='\t', index=False)
