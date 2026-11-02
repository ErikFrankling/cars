"""Runs the give-way analysis on the chosen pNEUMA crossings and on Peachtree at 13th St, and asks of each unsigned crossing whether the car from the right goes first."""
import glob
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
import pandas as pd
from scipy.ndimage import uniform_filter1d
from common import OUT, Rows, q, spread_of
import jx
import priority as pr
import pneuma_scan as ps
import sig

PN = 'pNEUMA https://zenodo.org/records/10491409'
PT = 'NGSIM Peachtree https://data.transportation.gov/api/views/8ect-6jqj.json'
# label, type, drone, x, y, minor heading, note
SITES = [('athens_stop_d5', 'priority_stop', 'd5', -619.6, 407.9, 1.03, 'OSM stop node 9 m away, no signal within 54 m. Cross traffic confirmed in the tracks'),
         ('athens_slip_d7', 'priority_giveway', 'd7', -380., 1103., None, 'OSM give_way on a slip road beside a signal 14 m away, so the major flow arrives in platoons'),
         ('athens_unsigned_d10a', 'unsigned_candidate', 'd10', -708.5, 475.7, 2.92, 'No signal within 71 m, no sign tag within 113 m. Not seen on the ground, so its rule is UNVERIFIED'),
         ('athens_unsigned_d10b', 'unsigned_candidate', 'd10', -729.8, 396.5, -1.22, 'No signal within 58 m, no sign tag within 105 m. Not seen on the ground, so its rule is UNVERIFIED')]
IDS = dict(flow='JP3', stops='JP4', delay='JP3', speed='JP6', lane='JP6', sat='JP2')


def right_first(df, rw, site, jt, src):
    """Pairs arriving from crossing arms within 3 s. Does the car from the right enter first?"""
    d = df[(df['arm'] >= 0) & df['complete']].sort_values('tin')
    h = d.groupby('arm')['hin'].apply(lambda s: np.angle(np.exp(1j * s.dropna()).mean()))
    a = d[['arm', 'tin', 'tout', 'flight']].values
    right, left = 0, 0
    for i in range(len(a)):
        for j in range(i + 1, min(i + 8, len(a))):
            if a[j][3] != a[i][3] or a[j][1] - a[i][1] > 3:
                break
            if a[i][0] == a[j][0]:
                continue
            rel = jx.wrap(h[a[j][0]] - h[a[i][0]])
            if abs(abs(rel) - np.pi / 2) > np.deg2rad(40):
                continue
            # first entered is i. j comes from i's right when j's heading is i's turned left by 90 degrees
            if rel > 0:
                left += 1   # the car from the right (j) went second
            else:
                right += 1  # the car from the left (j) went second, so the right-hand car went first
    n = right + left
    if n >= 8:
        se = np.sqrt(.25 / n)
        rw.add('car_from_right_entered_first_share', jt, site, right / n, se, src, 'tune', 'share', n, 'standard_error', movement='pairs_within_3s', bench_id='JB1', note='0.5 means the rule of the right plays no part; near 1 means right-before-left')
    print(site, 'right-first', right, left, flush=True)
    st = d.groupby('arm')['stop'].mean()
    for arm, v in st.items():
        rw.add('stop_share_by_arm', jt, site, v, None, src, 'tune', 'share', int((d['arm'] == arm).sum()), 'none', movement=f'arm{arm}', bench_id='JP4')
    if len(st) > 1:
        rw.add('stop_share_ratio_high_to_low_arm', jt, site, st.max() / max(st.min(), .01), None, src, 'tune', 'ratio', len(d), 'none', bench_id='JB1', note='about 1 suggests no priority road; large suggests a signed minor road')


def main():
    rw = Rows('priority')
    for label, jt, drone, x, y, hd, note in SITES:
        files = sorted(glob.glob(str(OUT / 'pneuma' / f'*_{drone}_*.npz')))
        recs, fus, dfs = [], [], []
        spans = {}
        ln = None
        for f in files:
            name = pathlib.Path(f).stem
            day, _, w = name.split('_')[:3]
            tr = ps.load(f)
            if ln is None:
                m = pr.minor_heading(tr, x, y)
                print(label, 'refined line', m, flush=True)
                h0 = hd if hd is not None else m[0]
                lx, ly = (m[1], m[2]) if m else (x, y)
                ln = (lx, ly, h0)
            fl = f'{day}_{w}'
            r, fu, n = pr.events(tr, ln[0], ln[1], ln[2], fl)
            recs += r
            fus += fu
            spans[fl] = 1800.
            df, P = jx.per_vehicle(tr, x, y, R=12., U=45., label=fl)
            if len(df):
                dfs.append(df)
            print(fl, n, len(r), flush=True)
        R, F = pd.DataFrame(recs), pd.DataFrame(fus, columns=['flight', 'h'])
        R.to_csv(OUT / f'prio_{label}.csv.gz', index=False)
        pr.rows(rw, R, F, label, jt, PN, 'tune', spans)
        # the same site treated as a plain junction, for arm flows and speeds
        if dfs:
            D = pd.concat(dfs)
            arms_all = jx.arms_of(D['ang_in'].values)
            D['arm'] = jx.assign(D['ang_in'].values, arms_all)
            sig.rows(rw, D, None, label, jt, PN, 'tune', spans, IDS, core=12)
            right_first(D, rw, label, jt, PN)
        if len(R):
            dec = R[R['first'] & R['acc'].notna() & ((R['nrej'] > 0) | (R['acc'] < 25))]
            print(label, note, 'minor', len(R), 'dec', len(dec), 'nrej>0', int((dec['nrej'] > 0).sum()), flush=True)
    rw.write()


def peachtree(rw):
    d = pd.read_csv('/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-ngsim/peachtree.csv', usecols=['vehicle_id', 'total_frames', 'global_time', 'global_x', 'global_y', 'v_class', 'int_id', 'direction'])
    d = d[d['v_class'] != 1].drop_duplicates(['vehicle_id', 'total_frames', 'global_time']).sort_values(['vehicle_id', 'total_frames', 'global_time'])
    d['t'] = d['global_time'] / 1000.
    t0 = d['t'].min()
    tr = []
    for (v, _), g in d.groupby(['vehicle_id', 'total_frames'], sort=False):
        g = g.iloc[::2]
        if len(g) < 12:
            continue
        x = uniform_filter1d(g['global_x'].values * .3048, 5)
        y = uniform_filter1d(g['global_y'].values * .3048, 5)
        t = g['t'].values - t0
        tr.append(dict(id=int(v) * 10 + int(g['total_frames'].iloc[0] % 7), cls=0, t=t, x=x, y=y, v=uniform_filter1d(np.hypot(np.gradient(x, t), np.gradient(y, t)), 5), dirn=int(g['direction'].iloc[0])))
    i4 = d[d['int_id'] == 4]
    cx, cy = i4['global_x'].mean() * .3048, i4['global_y'].mean() * .3048
    recs, fus = [], []
    for dirn in (1, 3):
        sub = [a for a in tr if a['dirn'] == dirn and np.hypot(a['x'] - cx, a['y'] - cy).min() < 25]
        if len(sub) < 5:
            continue
        P, H = [], []
        for a in sub:
            near = np.flatnonzero(np.hypot(a['x'] - cx, a['y'] - cy) < 30)
            k = near[int(a['v'][near].argmin())]
            if k < 3:
                continue
            P.append((a['x'][k], a['y'][k]))
            H.append(jx.heading(a['x'], a['y'], max(k - 15, 0), k))
        if len(P) < 5:
            continue
        P = np.array(P)
        hd = float(np.angle(np.exp(1j * np.array(H)).mean()))
        r, fu, n = pr.events(tr, float(np.median(P[:, 0])), float(np.median(P[:, 1])), hd, f'dir{dirn}')
        recs += r
        fus += fu
        print('peachtree 13th dir', dirn, n, len(r), flush=True)
    R, F = pd.DataFrame(recs), pd.DataFrame(fus, columns=['flight', 'h'])
    span = (d['t'].max() - t0)
    R['flight'] = 'all'
    if len(F):
        F['flight'] = 'all'
    pr.rows(rw, R, F, 'peachtree_13th', 'priority_stop', PT, 'tune', {'all': span})


if __name__ == '__main__':
    if sys.argv[1:] == ['peachtree']:
        rw = Rows('peachtree13')
        peachtree(rw)
        rw.write()
    else:
        main()
