"""DLR HT (A39, Monday 7 October 2024) as long tracks with a road coordinate, lane and leader, for persistence (part 3),
free speed (part 8) and the cross-checks of parts 2 and 4.

Road frame, lane centres and lane labels follow report 05's opus_ht.py (research/truth/scripts), copied here so the
held-out block is never read: files 96-119 (14:00-16:00 UTC) are held out (HOLDOUT.md). Blocks are 20 minutes (four
5-minute files); a track crossing a block boundary is cut there.

    python3 -I scripts/measure/dlrht.py 0 12        # blocks 0..11 (06:00-10:00 UTC) -> cars-data/measure/dlrht/b<k>.npz
"""
import os, sys, zipfile
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter1d, median_filter

ZIP = '/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-dlrht/DLR-Highway-Traffic-dataset_v1-2-0.zip'
OUT = '/home/erikf/projects/personal/cars-data/measure/dlrht'
HELD_FIRST_FILE = 96
LW = 3.75
COLS = ['timestamp', 'id', 'center_easting', 'center_northing', 'velocity_magnitude', 'dimension_length', 'dimension_width',
        'classifications_car', 'classifications_van', 'classifications_truck']


def files():
    z = zipfile.ZipFile(ZIP)
    return z, sorted(n for n in z.namelist() if '/trajectories/' in n and n.endswith('.csv'))


def secs(s):
    s = s.str.slice(11, -6)
    return s.str.slice(0, 2).astype(int) * 3600 + s.str.slice(3, 5).astype(int) * 60 + s.str.slice(6).astype(float)


def read(z, n):
    with z.open(n) as f:
        d = pd.read_csv(f, usecols=COLS)
    d['t'] = secs(d['timestamp'])
    d = d[(np.round(d['t'] * 20).astype(int) % 4) == 0]
    veh = d['classifications_car'] + d['classifications_van'] + d['classifications_truck']
    d = d[veh > .5]
    return pd.DataFrame(dict(id=d['id'].values, ti=np.round(d['t'].values * 5).astype('i4'),
                             x=(d['center_easting'].values - 600000).astype('f4'), y=(d['center_northing'].values - 5790000).astype('f4'),
                             v=d['velocity_magnitude'].values.astype('f4'), L=d['dimension_length'].values.astype('f4'),
                             tr=(d['classifications_truck'].values > .5).astype('i1')))


def mkrefs(d):
    g = d.groupby('id'); ends = g.agg(x0=('x', 'first'), y0=('y', 'first'), x1=('x', 'last'), y1=('y', 'last'))
    ends['len'] = np.hypot(ends.x1 - ends.x0, ends.y1 - ends.y0)
    pts = d[['x', 'y']].values[::50]; c = pts.mean(0); _, _, vt = np.linalg.svd(pts - c, full_matrices=False); ax = vt[0]
    ends['dir'] = np.sign((ends.x1 - ends.x0) * ax[0] + (ends.y1 - ends.y0) * ax[1])
    R = {}
    for sg in (-1, 1):
        best = ends[ends['dir'] == sg].sort_values('len').index[-1]
        t = d[d['id'] == best].sort_values('ti'); xy = t[['x', 'y']].values.astype('f8')
        seg = np.r_[0, np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]; ss = np.arange(0, seg[-1], 2.0)
        rx = gaussian_filter1d(np.interp(ss, seg, xy[:, 0]), 100, mode='nearest'); ry = gaussian_filter1d(np.interp(ss, seg, xy[:, 1]), 100, mode='nearest')
        tx = np.gradient(rx); ty = np.gradient(ry); n = np.hypot(tx, ty)
        R[sg] = dict(x=rx, y=ry, tx=tx / n, ty=ty / n, tree=cKDTree(np.c_[rx, ry]), len=seg[-1])
    return R


def frame(d, refs):
    o = np.lexsort((d['ti'].values, d['id'].values)); d = d.iloc[o].reset_index(drop=True)
    ub = np.r_[0, np.where(np.diff(d['id'].values) != 0)[0] + 1, len(d)]
    S = np.full(len(d), np.nan, 'f4'); DD = np.full(len(d), np.nan, 'f4'); DIR = np.zeros(len(d), 'i1')
    X, Y = d['x'].values, d['y'].values
    for a, b in zip(ub[:-1], ub[1:]):
        if b - a < 25:
            continue
        best = None
        for sg, r in refs.items():
            dist, idx = r['tree'].query(np.c_[X[a:b], Y[a:b]], k=1)
            dx = X[b - 1] - X[a]; dy = Y[b - 1] - Y[a]; k = len(idx) // 2
            if dx * r['tx'][idx[k]] + dy * r['ty'][idx[k]] > 0 and np.median(dist) < 15:
                best = (sg, idx, r)
        if best is None:
            continue
        sg, idx, r = best
        rx = X[a:b] - r['x'][idx]; ry = Y[a:b] - r['y'][idx]
        S[a:b] = idx * 2.0 + rx * r['tx'][idx] + ry * r['ty'][idx]
        DD[a:b] = rx * -r['ty'][idx] + ry * r['tx'][idx]; DIR[a:b] = sg
    d['s'] = S; d['dd'] = DD; d['dir'] = DIR
    return d[d['dir'] != 0].reset_index(drop=True)


def centres(d):
    C = {}
    for sg in (-1, 1):
        m = (d['dir'].values == sg) & (np.abs(d['dd'].values) < 12)
        s = d['s'].values[m]; dd = d['dd'].values[m]
        bins = (s / 100).astype(int); nb = bins.max() + 1; c = np.full(nb, np.nan)
        for b in range(nb):
            z_ = dd[bins == b]
            if len(z_) < 300:
                continue
            h, e = np.histogram(z_, bins=np.arange(-12, 12.01, .25)); hs = gaussian_filter1d(h.astype(float), 2)
            c[b] = e[np.argmax(hs)] + .125
        v = np.where(np.isfinite(c))[0]
        cc = np.interp(np.arange(nb), v, c[v])
        for i in range(1, nb):
            while cc[i] - cc[i - 1] > LW / 2: cc[i] -= LW
            while cc[i] - cc[i - 1] < -LW / 2: cc[i] += LW
        C[sg] = gaussian_filter1d(median_filter(cc, 9), 1)
    return C


def lane_label(d, C):
    L = np.zeros(len(d), 'i1')
    for sg in (-1, 1):
        m = d['dir'].values == sg
        cs = np.interp(d['s'].values[m] / 100, np.arange(len(C[sg])), C[sg])
        L[m] = np.round((d['dd'].values[m] - cs) / LW).astype('i1')
    d['lane'] = L
    return d


def leaders(d):
    """Same-lane vehicle ahead at each 5 Hz sample: centre spacing, its speed, length and id (-1 if none in view)."""
    o = np.lexsort((d['s'].values, d['lane'].values, d['dir'].values, d['ti'].values)); e = d.iloc[o].reset_index(drop=True)
    ti, di, la = e['ti'].values, e['dir'].values, e['lane'].values
    same = np.r_[(ti[1:] == ti[:-1]) & (di[1:] == di[:-1]) & (la[1:] == la[:-1]), False]
    nxt = np.arange(len(e)) + 1
    # dir +1 drives towards larger s: leader is the next sample; dir -1 drives towards smaller s? frame() aligns s with
    # each reference's own direction, so in both directions the leader has the larger s.
    cc = np.where(same, np.r_[e['s'].values[1:], 0] - e['s'].values, np.nan)
    e['cc'] = cc.astype('f4')
    e['vl'] = np.where(same, np.r_[e['v'].values[1:], 0], np.nan).astype('f4')
    e['Ll'] = np.where(same, np.r_[e['L'].values[1:], 0], np.nan).astype('f4')
    e['lid'] = np.where(same, np.r_[e['id'].values[1:], 0], -1)
    return e


def block(z, fs, k, refs):
    names = fs[k * 4:k * 4 + 4]
    if any(fs.index(n) >= HELD_FIRST_FILE for n in names) and '--holdout' not in sys.argv:
        raise SystemExit('block reaches the held-out files (HOLDOUT.md)')
    d = pd.concat([read(z, n) for n in names], ignore_index=True)
    if refs is None:
        refs = mkrefs(d)
    d = frame(d, refs); d = lane_label(d, centres(d)); d = leaders(d)
    d = d.sort_values(['id', 'ti']).reset_index(drop=True)
    os.makedirs(OUT, exist_ok=True)
    np.savez(f'{OUT}/b{k:02d}.npz', **{c: d[c].to_numpy() for c in ('id', 'ti', 's', 'dd', 'dir', 'lane', 'v', 'L', 'tr', 'cc', 'vl', 'Ll', 'lid')})
    print(k, len(d), d.id.nunique(), flush=True)
    return refs


if __name__ == '__main__':
    z, fs = files()
    refs = None
    for k in range(int(sys.argv[1]), int(sys.argv[2])):
        refs = block(z, fs, k, refs)
    # python3 -I scripts/measure/dlrht.py 24 26 --holdout   reads the held-out 14:00-14:40 UTC, for the replay test only
