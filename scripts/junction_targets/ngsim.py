"""NGSIM Lankershim and Peachtree: signal targets by turn, using NGSIM's own intersection, direction, movement and lane labels.
Only positions, crossing times and stops are used: report 05 found the published accelerations are not credible."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
import pandas as pd
from scipy.ndimage import uniform_filter1d
from common import OUT, Rows, gap_mle, q, spread_of
import jx
import sig

ROOT = '/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-ngsim/'
FT = .3048
MOVE = {1: 'through', 2: 'left', 3: 'right'}
SRC = {'lankershim': 'NGSIM Lankershim https://data.transportation.gov/api/views/8ect-6jqj.json', 'peachtree': 'NGSIM Peachtree https://data.transportation.gov/api/views/8ect-6jqj.json'}
IDS = dict(flow='JS7', stops='JS7', delay='JS7', speed='JS9', lane='JS10', sat='JS2')


def table(d, loc):
    d = d.drop_duplicates(['vehicle_id', 'total_frames', 'global_time']).sort_values(['vehicle_id', 'total_frames', 'global_time'])
    rows = []
    for (vid, _), g in d.groupby(['vehicle_id', 'total_frames'], sort=False):
        t = g['global_time'].values / 1000.
        if len(t) < 30:
            continue
        ints = g['int_id'].values
        x = uniform_filter1d(g['global_x'].values * FT, 11)
        y = uniform_filter1d(g['global_y'].values * FT, 11)
        s = np.r_[0, np.cumsum(np.hypot(np.diff(x), np.diff(y)))]
        v = uniform_filter1d(np.gradient(s, t), 11)
        change = np.flatnonzero((ints[1:] > 0) & (ints[:-1] != ints[1:]))
        seen = set()
        for k in change + 1:
            I = ints[k]
            if I in seen:
                continue
            seen.add(I)
            e = k + int(np.argmax(ints[k:] != I)) if (ints[k:] != I).any() else len(ints) - 1
            up = np.searchsorted(s, s[k] - 60)
            if s[k] < 15:
                continue
            vup = v[up:k + 1]
            st = vup < 1.0
            kl = up + len(st) - 1 - int(np.argmax(st[::-1])) if st.any() else -1
            kf = up + int(np.argmax(st)) if st.any() else -1
            rows.append(dict(flight=f'{loc}_{I}_{int(t[0] // 300)}', loc=loc, int=I, id=vid, cls=g['v_class'].iloc[0], arm=int(g['direction'].iloc[k]), move=MOVE.get(int(g['movement'].iloc[k]), 'unknown'), lane=int(g['lane_id'].iloc[max(k - 2, 0)]),
                             tin=t[k], tout=t[e], stop=bool(st.any()), tstop=t[kf] if kf >= 0 else np.nan, tgo=t[kl] if kl >= 0 else np.nan, sstop=s[k] - s[kl] if kl >= 0 else np.nan, vin=v[k], vout=v[e], vmed_core=np.median(v[k:e + 1]), vmin_core=v[k:e + 1].min(),
                             up_full=s[k] - s[up] >= 55, t_up=t[k] - t[up], complete=e < len(t) - 1))
    return pd.DataFrame(rows)


def main():
    rw = Rows('ngsim')
    for loc in ('lankershim', 'peachtree'):
        d = pd.read_csv(ROOT + loc + '.csv', usecols=['vehicle_id', 'total_frames', 'global_time', 'global_x', 'global_y', 'v_class', 'lane_id', 'int_id', 'direction', 'movement'])
        d = d[d['v_class'] != 1]
        t0, t1 = d['global_time'].min() / 1000, d['global_time'].max() / 1000
        print(loc, 'minutes', (t1 - t0) / 60, flush=True)
        T = table(d, loc)
        del d
        T.to_csv(OUT / f'ngsim_{loc}.csv.gz', index=False)
        for I, g in T.groupby('int'):
            if loc == 'peachtree' and I == 4:
                continue
            g = g.copy()
            g['flight'] = g['tin'].map(lambda x: f'b{int((x - t0) // 300)}')
            spans = {f: 300. for f in g['flight'].unique()}
            D = jx.discharge(g.assign(arm=g['arm'], lane=g['lane']), nearline=15)
            site = f'{loc}_int{I}'
            sig.rows(rw, g, D, site, 'signal', SRC[loc], 'tune', spans, IDS)
            sat = D[(D['pos'] >= 5) & (D['h'] > .8) & (D['h'] < 8)]
            print(site, len(g), 'stop %.2f' % g['stop'].mean(), 'sat', round(sat['h'].median(), 2) if len(sat) else None, len(sat), flush=True)
    rw.write()


if __name__ == '__main__':
    main()
