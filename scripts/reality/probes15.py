#!/usr/bin/env python3
"""HERE probes at 15 minutes on v6.4 edges, 8 tuning days. MeTS-10 join and trust filter, as t4c_district.py, plus a harmonic speed over cells.

Needs h5py, shapely, geographiclib and PYTHONPATH=<mets10 data_pipeline>. Writes probes/edge_15min.npz outside the repo.
"""
import csv
import gzip
import json
import sys
import warnings
from pathlib import Path

import h5py
import numpy as np
from shapely import wkt

sys.path.insert(0, '/home/erikf/projects/personal/cars-data/berlin2019/t4c_job/mets10_src/data_pipeline')
from data_helpers import get_intersecting_grid_cells, get_latlon_bounds

B19 = Path('/home/erikf/projects/personal/cars-data/berlin2019')
MOVIES = B19.parent / 'here-t4c/movie_may2019'
DAYS = json.load(open(B19 / 'step1/freeze.json'))['tuning_days']
MAXK = 120

(lat_min, lat_max, lon_min, lon_max), rotate = get_latlon_bounds('berlin')
keys, cells = [], []
for r in csv.DictReader(gzip.open(B19 / 't4c_job/edges.csv.gz', 'rt')):
    ic = get_intersecting_grid_cells(wkt.loads(r['wkt']), lon_min, lat_min, reverse=False, rotate=rotate)
    if ic:
        keys.append(r['gkey'])
        cells.append(np.array([(int(a[0]), int(a[1]), int(a[2])) for a in ic]))
print('edges', len(keys), flush=True)
ptr = np.cumsum([0] + [len(c) for c in cells])
flat = np.concatenate(cells)
group = np.repeat(np.arange(len(keys)), [len(c) for c in cells])
E, D = len(keys), len(DAYS)
med = np.full((E, D, 96), np.nan, np.float32)
hm = np.full((E, D, 96), np.nan, np.float32)
vol = np.zeros((E, D, 96), np.int32)
zero, total = np.zeros(D, np.int64), np.zeros(D, np.int64)
warnings.simplefilter('ignore', category=RuntimeWarning)
for d, day in enumerate(DAYS):
    with h5py.File(next(MOVIES.glob(f'{day}_*8ch.h5')), 'r') as f:
        a = f['array'][()]
    assert a.shape[0] == 288
    for q in range(96):
        w = a[q * 3:q * 3 + 3]
        v = w[:, flat[:, 0], flat[:, 1], flat[:, 2] * 2].astype(np.float32)
        s = w[:, flat[:, 0], flat[:, 1], flat[:, 2] * 2 + 1].astype(np.float32)
        s[v <= 0] = np.nan
        sc = np.nanmean(s, axis=0) / 255 * MAXK
        vol[:, d, q] = np.add.reduceat(v.sum(axis=0), ptr[:-1])
        ok = np.isfinite(sc)
        n = np.add.reduceat(ok.astype(np.int64), ptr[:-1])
        o = np.lexsort((np.where(ok, sc, np.inf), group))
        ss = sc[o]
        has = n > 0
        med[has, d, q] = (ss[ptr[:-1][has] + (n[has] - 1) // 2] + ss[ptr[:-1][has] + n[has] // 2]) / 2
        inv = np.where(ok, 1 / np.maximum(np.nan_to_num(sc), 1.0), 0.0)
        hm[has, d, q] = n[has] / np.add.reduceat(inv, ptr[:-1])[has]
        zero[d] += int((sc[ok] == 0).sum())
        total[d] += int(ok.sum())
    del a
    print(day, 'share of live cells at speed 0:', zero[d] / total[d], flush=True)
ff = np.nanpercentile(med.reshape(E, -1), 90, axis=1)
cf = med / ff[:, None, None]
bad = ~(np.isfinite(med) & (med > 0) & (vol >= 1)) | ((vol < 5) & (cf < .4)) | ((vol < 3) & (cf < .8))
med[bad] = np.nan
hm[bad] = np.nan
np.savez_compressed(B19 / 'probes/edge_15min.npz', keys=np.array(keys), days=np.array(DAYS), med=med, hm=hm, vol=vol, free=ff.astype(np.float32))
print('done', int(np.isfinite(med).sum()))
