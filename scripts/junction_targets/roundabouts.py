"""Roundabout targets. OpenDD (tuning: rdb1, 5, 6, 7) and Swiss (tuning: F1, F2). Held-out sites are refused here.
python3 -I roundabouts.py <opendd|swiss> <site> [max_flights]"""
import glob
import itertools
import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
import pandas as pd
from common import OUT, gap_mle, raff, boot_gap, q, spread_of, Rows
import rb
from rb_geom import refine

LOCKED = {'rdb2', 'rdb3', 'rdb4', 'L1'}
D = '/home/erikf/projects/personal/cars-data/datasets/jt25-opendd/x'
SW = '/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-swiss'
GUESS = {'rdb1': (619303.6, 5809149.1, 13.), 'rdb6': (674606.7, 5407008.5, 16.), 'rdb5': (617382.8, 5806792.2, 14.), 'rdb7': (673958.0, 5410628.6, 15.), 'F2': (4., -1., 8.), 'F1': (-9., 5., 8.)}
GUESS.update(json.load(open(OUT / 'guess.json')) if (OUT / 'guess.json').exists() else {})
VEH = {'Car', 'Medium Vehicle', 'Heavy Vehicle', 'Bus', 'Motorcycle', 'Truck'}


def opendd_flights(site):
    c = sqlite3.connect(f'{D}/{site}/trajectories_{site}_v3.sqlite')
    T = sorted((r[0] for r in c.execute("select name from sqlite_master where type='table'")), key=lambda s: int(s.split('_')[1]))
    for name in T:
        d = pd.read_sql(f'select TIMESTAMP t,OBJID id,UTM_X x,UTM_Y y,V v,CLASS cls from "{name}" where ID%6=1', c)
        yield name, d


def swiss_flights(site):
    lat0 = lon0 = None
    for f in sorted(glob.glob(f'{SW}/*_{site}.csv')):
        d = pd.read_csv(f)
        if lat0 is None:
            ref = {'F2': 'D1_AM1_F2.csv', 'F1': 'D1_AM2_F1.csv'}[site]
            e = pd.read_csv(f'{SW}/{ref}', usecols=['lat', 'lon'])
            lat0, lon0 = e['lat'].mean(), e['lon'].mean()
        t = d['time'].str.slice(0, 2).astype(int) * 3600 + d['time'].str.slice(3, 5).astype(int) * 60 + d['time'].str.slice(6).astype(float)
        out = pd.DataFrame(dict(t=t, id=d['track_id'], x=(d['lon'] - lon0) * 111320 * np.cos(np.deg2rad(lat0)), y=(d['lat'] - lat0) * 110574, cls=d['type']))
        yield pathlib.Path(f).stem, out.iloc[::6]


def tracks(d):
    tr = []
    for i, g in d.groupby('id', sort=False):
        if g['cls'].iloc[0] not in VEH or len(g) < 8:
            continue
        g = g.sort_values('t')
        t = g['t'].values
        x = rb.uniform_filter1d(g['x'].values, 3)
        y = rb.uniform_filter1d(g['y'].values, 3)
        v = g['v'].values if 'v' in g else np.hypot(np.gradient(x, t), np.gradient(y, t))
        if 'v' not in g:
            v = np.hypot(np.gradient(x, t), np.gradient(y, t))
        tr.append((i, g['cls'].iloc[0], t, x, y, v))
    return tr


def main(kind, site, maxf=10**6):
    if site in LOCKED:
        raise SystemExit(f'{site} is held out: see splits.toml')
    fl = opendd_flights(site) if kind == 'opendd' else swiss_flights(site)
    rec, fus, flows = [], [], []
    geom = None
    src = {'opendd': 'OpenDD v3 https://l3pilot.eu/data/opendd.html', 'swiss': 'Swiss roundabouts https://zenodo.org/records/15077435'}[kind]
    first = list(itertools.islice(fl, 8))
    tr0 = [tracks(d) for _, d in first]
    X = np.concatenate([a[3] for t in tr0 for a in t])
    Y = np.concatenate([a[4] for t in tr0 for a in t])
    cx, cy, R = refine(X, Y, *GUESS[site])
    Ry = R + 3.
    E = [a for t in tr0 for a in rb.mark(rb.polar(t, cx, cy), Ry)[0]]
    sgn = rb.sense(E)
    arms = rb.arm_angles(np.array([a['ang'] for a in E]))
    geom = dict(cx=cx, cy=cy, R=R, Ry=Ry, sgn=sgn, arms=arms)
    prof = np.histogram(np.concatenate([np.hypot(a[3] - cx, a[4] - cy) for t in tr0 for a in t]), bins=np.arange(0, 40, 1))[0]
    print(site, geom, 'radial', prof.tolist(), flush=True)
    del tr0
    for nf, (name, d) in enumerate(itertools.chain(first, fl)):
        if nf >= maxf:
            break
        tr = tracks(d)
        r, f, fl2, info = rb.analyse(tr, geom['cx'], geom['cy'], geom['Ry'], geom['arms'], geom['sgn'], None, name)
        rec += r
        fus += f
        flows.append(fl2)
        if nf % 20 == 0:
            print(nf, name, info, len(rec), flush=True)
    R = pd.DataFrame(rec)
    R.to_csv(OUT / f'rb_{site}_entries.csv.gz', index=False)
    F = pd.DataFrame(fus)
    F.to_csv(OUT / f'rb_{site}_followup.csv.gz', index=False)
    # capacity pairs: 60 s bins with a queue on the arm for at least 80% of the seconds
    pairs = []
    for i, fl2 in enumerate(flows):
        if not fl2:
            continue
        g = fl2['grid']
        for j in fl2['Q']:
            for b0 in np.arange(g[0], g[-1] - 60, 60):
                m = (g >= b0) & (g < b0 + 60)
                qs = fl2['Q'][j][m] > 0
                pe = fl2['entries'][j]
                pc = fl2['passes'][j]
                pairs.append((i, j, qs.mean(), ((pe >= b0) & (pe < b0 + 60)).sum(), ((pc >= b0) & (pc < b0 + 60)).sum(), fl2['Q'][j][m].max()))
    P = pd.DataFrame(pairs, columns=['flight', 'arm', 'qshare', 'qe', 'qc', 'qmax'])
    P.to_csv(OUT / f'rb_{site}_minutes.csv.gz', index=False)
    (OUT / f'rb_{site}_geom.json').write_text(json.dumps(geom, default=float))
    print(site, 'entries', len(R), 'first', int(R['first'].sum()), 'fu', len(F), 'flights', R['flight'].nunique())
    return R


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 10**6)
