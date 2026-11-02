"""DRaT, Fort Worth: 140 m of a three-lane freeway where a short extra lane ends. Thin: under 50 forced merges. Also the only open record here with a clear free and congested split on the same site."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
import pandas as pd
from common import OUT, Rows, q, spread_of

F = '/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-drat/drone_GT.csv'
SRC = 'DRaT https://zenodo.org/records/20171110'
BLOCK = 300.
EDGES = (-6.2, -2., 2.)   # read from the side-offset histogram: an extra lane, then three lanes


def main():
    d = pd.read_csv(F, usecols=['track_id', 'timestamp', 'utm_x', 'utm_y', 'speed_mps', 'vehicle_class'])
    A = np.c_[d['utm_x'] - d['utm_x'].mean(), d['utm_y'] - d['utm_y'].mean()]
    _, _, vt = np.linalg.svd(A[::5], full_matrices=False)
    p = A @ vt.T
    d['x'], d['y'] = p[:, 0], p[:, 1]
    d = d.sort_values(['track_id', 'timestamp'])
    g = d.groupby('track_id')
    sgn = np.sign((g['x'].last() - g['x'].first()).median())
    d['x'] *= sgn
    d['y'] *= sgn
    d['t'] = d['timestamp'] - d['timestamp'].min()
    d['lane'] = np.searchsorted(EDGES, d['y'])
    rw = Rows('drat')
    add = lambda m, v, sp, u, n, kind, jt='lane_drop', **k: rw.add(m, jt, 'drat_fort_worth', v, sp, SRC, 'tune', u, n, kind, **k)
    rec = []
    for i, c in d.groupby('track_id'):
        l = c['lane'].values
        for k in np.flatnonzero(np.diff(l)) + 1:
            if k >= 4 and len(l) - k >= 4 and (l[k - 4:k] == l[k - 1]).all() and (l[k:k + 4] == l[k]).all():
                rec.append((i, c['t'].iloc[k], c['x'].iloc[k], l[k - 1], l[k], c['speed_mps'].iloc[k]))
    E = pd.DataFrame(rec, columns=['id', 't', 'x', 'old', 'new', 'v'])
    m = E[(E['old'] == 0) & (E['new'] == 1)]
    # the congested part of the record is plain in the speeds
    cross = d[(d['x'] > -5) & (d['x'] < 5)].groupby('track_id').agg(t=('t', 'first'), v=('speed_mps', 'median'), lane=('lane', 'first'))
    cross['block'] = (cross['t'] // BLOCK).astype(int)
    bl = cross.groupby('block').agg(n=('v', 'size'), v=('v', 'median'), span=('t', lambda s: s.max() - s.min()))
    bl = bl[bl['span'] > BLOCK * .7]
    bl['q'] = bl['n'] * 3600 / bl['span'] / 3
    bl['state'] = np.where(bl['v'] < 15, 'congested', 'free')
    state = bl['state'].to_dict()
    add('merge_events', len(m), None, 'count', len(m), 'none', bench_id='JL1', note='THIN. The lane fades over the first half of the view')
    add('merge_position_median', m['x'].median(), None, 'm', len(m), 'none', lo=q(m['x'], 10), hi=q(m['x'], 90), bench_id='JL1', note='in the frame of the 150 m view; lane ends near x = 0 to 20')
    add('merge_speed_median', m['v'].median(), None, 'm/s', len(m), 'none', lo=q(m['v'], 10), hi=q(m['v'], 90), bench_id='JL1')
    for s, b in bl.groupby('state'):
        add('flow_per_lane', b['q'].median(), spread_of(b['q']), 'veh/h/lane', int(b['n'].sum()), 'block_to_block', lo=b['q'].min(), hi=b['q'].max(), movement=s, bench_id='JL2', note=f'three lanes at mid view, {len(b)} blocks of 5 min, median block speed {b["v"].median():.1f} m/s')
        add('speed_median', b['v'].median(), spread_of(b['v']), 'm/s', int(b['n'].sum()), 'block_to_block', movement=s, bench_id='JL2')
    for l, c in cross.groupby('lane'):
        if l > 0:
            add('lane_use_share', len(c) / len(cross), None, 'share', len(c), 'none', movement=f'lane{l}', bench_id='JL2')
    other = E[(E['old'] > 0) & (E['new'] > 0)]
    km = d.groupby('track_id')['x'].agg(lambda s: s.max() - s.min()).sum() / 1000
    add('discretionary_changes_per_veh_km', len(other) / km, None, 'per veh-km', len(other), 'none', jt='lane_drop', bench_id='JL3', note='section just downstream of a lane end')
    rw.write()
    print(len(m), m['x'].median(), bl[['q', 'v', 'state']].round(1).to_string())


if __name__ == '__main__':
    main()
