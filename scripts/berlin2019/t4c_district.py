#!/usr/bin/env python3
"""HERE probe speeds on the sim's own edges, for the district and May 2019 only. Report 22's locks stay: no other month is unpacked.

The join, median and trust filter are MeTS-10's code and thresholds (data_pipeline/data_helpers.py, dp06). Free flow is simpler
here: each edge's 90th percentile of 15-minute medians, not dp02's speed clusters, which need the whole city in memory.
Run with h5py, shapely and geographiclib, and PYTHONPATH=<mets10 data_pipeline>. Writes probes/edge_hour.csv.gz.
"""
import ast
import csv
import gzip
import json
import os
import sys
from pathlib import Path

import h5py
import numpy as np
from shapely import wkt

from data_helpers import get_intersecting_grid_cells, get_latlon_bounds

DATA = Path('/home/erikf/projects/personal/cars-data')
B19 = DATA / 'berlin2019'
MOVIES = DATA / 'here-t4c/movie_may2019'
DAYS = ['2019-05-07', '2019-05-14', '2019-05-15', '2019-05-16', '2019-05-21', '2019-05-22', '2019-05-23', '2019-05-28']


def main():
    maxk = 120  # dp06: MOVIE_MAXSPEED_KPH
    (lat_min, lat_max, lon_min, lon_max), rotate = get_latlon_bounds('berlin')
    box = json.load(open(B19 / 'step0/district.json'))['box']
    # district in degrees with a margin, from the edge file itself
    rows = list(csv.DictReader(gzip.open(B19 / 't4c_job/edges.csv.gz', 'rt')))
    off = (648737.88, 5697623.04)
    from pyproj import Transformer
    tr = Transformer.from_crs('+proj=utm +zone=32 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs', 'EPSG:4326', always_xy=True)
    lo0, la0 = tr.transform(box[0] + off[0] - 600, box[1] + off[1] - 600)
    lo1, la1 = tr.transform(box[2] + off[0] + 600, box[3] + off[1] + 600)
    cells = {}
    for r in rows:
        g = wkt.loads(r['wkt'])
        c = g.centroid
        if not (min(lo0, lo1) <= c.x <= max(lo0, lo1) and min(la0, la1) <= c.y <= max(la0, la1)):
            continue
        ic = get_intersecting_grid_cells(g, lon_min, lat_min, reverse=False, rotate=rotate)
        if ic:
            cells[r['gkey']] = [(int(a[0]), int(a[1]), int(a[2])) for a in ic]
    print('edges', len(cells), flush=True)
    rr = [x[0] for v in cells.values() for x in v]
    cc = [x[1] for v in cells.values() for x in v]
    r0, r1, c0, c1 = min(rr), max(rr) + 1, min(cc), max(cc) + 1
    print('crop', r0, r1, c0, c1, flush=True)
    med = {}
    vol = {}
    for day in DAYS:
        fn = next(MOVIES.glob(f'{day}_*8ch.h5'), None)
        if fn is None:
            print('missing', day, flush=True)
            continue
        with h5py.File(fn, 'r') as f:
            a = f['array'][:, r0:r1, c0:c1, :8].astype(np.float32)
        print(day, a.shape, flush=True)
        a = a.reshape(96, 3, r1 - r0, c1 - c0, 8)
        v = a[..., [0, 2, 4, 6]].sum(axis=1)
        s = a[..., [1, 3, 5, 7]].copy()
        s[a[..., [0, 2, 4, 6]] <= 0] = np.nan
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', category=RuntimeWarning)
            s = np.nanmean(s, axis=1)
        for k, ic in cells.items():
            idx = np.array(ic)
            ss = s[:, idx[:, 0] - r0, idx[:, 1] - c0, idx[:, 2]]
            vv = v[:, idx[:, 0] - r0, idx[:, 1] - c0, idx[:, 2]]
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', category=RuntimeWarning)
                med.setdefault(k, {})[day] = np.nanmedian(ss, axis=1) / 255 * maxk
            vol.setdefault(k, {})[day] = vv.sum(axis=1)
    out = gzip.open(B19 / 'probes/edge_hour.csv.gz', 'wt')
    w = csv.writer(out)
    w.writerow(['edge', 'day', 'hour', 'kmh', 'volume', 'free_flow', 'n'])
    n = 0
    for k, by in med.items():
        allv = np.concatenate(list(by.values()))
        if not np.isfinite(allv).any():
            continue
        ff = float(np.nanpercentile(allv, 90))
        if ff <= 0:
            continue
        for day, m in by.items():
            v = vol[k][day]
            cf = m / ff
            # dp06's filter: a jam needs more probes to be believed
            keep = np.isfinite(m) & (m > 0) & (v >= 1) & ~((v < 5) & (cf < .4)) & ~((v < 3) & (cf < .8))
            for h in range(24):
                q = keep[h * 4:h * 4 + 4]
                if q.sum() >= 2:
                    wgt = v[h * 4:h * 4 + 4][q]
                    w.writerow([k, day, h, round(float(np.average(m[h * 4:h * 4 + 4][q], weights=wgt)), 1), int(wgt.sum()), round(ff, 1), int(q.sum())])
                    n += 1
    out.close()
    print('rows', n)


if __name__ == '__main__':
    main()
