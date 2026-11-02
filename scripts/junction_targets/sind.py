"""SinD public sample records: one recording in each of four Chinese cities, with signal states from the data. All tuning. Full set needs an application."""
import glob
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
import pandas as pd
from common import OUT, Rows, q, spread_of
import jx
import sig

D = '/home/erikf/projects/personal/cars-data/datasets/jt25-sind/'
SRC = 'SinD public samples https://github.com/SOTIF-AVLab/SinD'
IDS = dict(flow='JS7', stops='JS7', delay='JS7', speed='JS9', lane='JS10', sat='JS2')
SITES = {'sind_tianjin': ('Tianjin_8_2_1_Veh_smoothed_tracks.csv', 'Tianjin_8_2_1_TrafficLight_8_2_1.csv'),
         'sind_changchun': ('Changchun_changchun_pudong_507_009_Veh_smoothed_tracks.csv', 'Changchun_changchun_pudong_507_009_Traffic_Lights.csv'),
         'sind_chongqing': ('Chongqing_6_22_NR_1_Veh_smoothed_tracks.csv', 'Chongqing_6_22_NR_1_TrafficLight_06_22_NR1_add_plight.csv'),
         'sind_xian': ('Xi_an_Xi_an_412_m1_Veh_smoothed_tracks.csv', 'Xi_an_Xi_an_412_m1_Traffic_Lights.csv')}


def states(tl):
    """Per light: change times and states."""
    t = tl['timestamp(ms)'].values / 1000.
    out = {}
    for c in tl.columns[2:]:
        if 'Pedestrian' in c:
            continue
        out[c] = (t, tl[c].values)
    return out


def at(st, tq):
    t, s = st
    i = np.clip(np.searchsorted(t, tq, 'right') - 1, 0, len(t) - 1)
    return s[i]


def main():
    rw = Rows('sind')
    for site, (vf, lf) in SITES.items():
        d = pd.read_csv(D + vf, usecols=['track_id', 'timestamp_ms', 'agent_type', 'x', 'y', 'v_lon'])
        d = d[d['agent_type'].isin(['car', 'truck', 'bus'])]
        d = d[(d['timestamp_ms'] / 100.1).round().astype('int64') % 2 == 0]
        tr = jx.make_tracks(d['track_id'].values, d['agent_type'].values, d['timestamp_ms'].values / 1000., d['x'].values, d['y'].values, np.abs(d['v_lon'].values))
        c = d[d['agent_type'] == 'car']
        cx = (c['x'].quantile(.02) + c['x'].quantile(.98)) / 2
        cy = (c['y'].quantile(.02) + c['y'].quantile(.98)) / 2
        df, P = jx.per_vehicle(tr, cx, cy, R=18., U=50., label='b0')
        T = float(d['timestamp_ms'].max() / 1000.)
        df['flight'] = (df['tin'] // 300).astype(int).map(lambda b: f'b{b}')
        spans = {f: 300. for f in df['flight'].unique()}
        df = jx.lane_clusters(df)
        Q = jx.discharge(df)
        sig.rows(rw, df, Q, site, 'signal', SRC, 'tune', spans, IDS, core=18)
        tl = pd.read_csv(D + lf)
        S = states(tl)
        add = lambda m, v, sp, u, n, kind, **k: rw.add(m, 'signal', site, v, sp, SRC, 'tune', u, n, kind, **k)
        pos1, pos = [], []
        viol = []
        for (arm, mv), g in df[(df['arm'] >= 0) & df['move'].isin(['through', 'left', 'right'])].groupby(['arm', 'move']):
            if len(g) < 8:
                continue
            best = max(S, key=lambda L: np.isin(at(S[L], g['tin'].values), [1, 3]).mean())
            share = np.isin(at(S[best], g['tin'].values), [1, 3]).mean()
            state_at = at(S[best], g['tin'].values)
            if mv != 'right':
                viol.append((mv, (state_at == 0).sum(), (state_at == 3).sum(), len(g)))
            if share < .7:
                continue
            t, s = S[best]
            on = t[1:][(s[1:] == 1) & (s[:-1] != 1)]
            for o in on:
                q0 = g[g['stop'] & (g['tstop'] < o) & (g['tin'] > o) & (g['tin'] < o + 60)]
                for lane, h in q0.groupby('lane'):
                    h = h.sort_values('tin')
                    prev = o
                    for n, (_, x) in enumerate(h.iterrows(), 1):
                        pos.append((mv, n, x['tin'] - prev, x['tgo'] - o, o))
                        prev = x['tin']
        Pq = pd.DataFrame(pos, columns=['mv', 'pos', 'h', 'start', 'on'])
        if len(Pq):
            # position 1 is left out: its time to the 18 m circle depends on how far the stop line is from it. first_car_start_after_green does not
            for p in (2, 3, 4, 5):
                g = Pq[Pq['pos'] == p]
                if len(g) >= 8:
                    add('queue_headway_by_position', g['h'].median(), None, 's', len(g), 'none', lo=q(g['h'], 25), hi=q(g['h'], 75), movement=f'pos{p}', bench_id='JS1', note='from recorded green; lo and hi are p25 and p75')
            f = Pq[Pq['pos'] == 1]
            add('first_car_start_after_green', f['start'].median(), None, 's', len(f), 'none', lo=q(f['start'], 10), hi=q(f['start'], 90), bench_id='JS4')
        cy_all = []
        gn = []
        for L, (t, s) in S.items():
            on = t[1:][(s[1:] == 1) & (s[:-1] != 1)]
            off = t[1:][(s[1:] != 1) & (s[:-1] == 1)]
            if len(on) > 2:
                cy_all.append(np.median(np.diff(on)))
                gs = [off[off > a][0] - a for a in on if (off > a).any()]
                if gs:
                    gn.append(np.median(gs))
        if cy_all:
            add('cycle_length_median', np.median(cy_all), None, 's', len(cy_all), 'none', lo=min(cy_all), hi=max(cy_all), bench_id='JS7', note='input, not a target: the scene takes it from the record')
            add('green_length_median', np.median(gn), None, 's', len(gn), 'none', lo=min(gn), hi=max(gn), bench_id='JS7', note='input, not a target')
        if viol:
            V = pd.DataFrame(viol, columns=['mv', 'red', 'yel', 'n'])
            for mv, g in V.groupby('mv'):
                add('entered_on_red_share', g['red'].sum() / g['n'].sum(), None, 'share', int(g['n'].sum()), 'none', movement=mv, bench_id='JS6', note='entered the 18 m circle while the matched light was red, so late clearers count')
                add('entered_on_yellow_share', g['yel'].sum() / g['n'].sum(), None, 'share', int(g['n'].sum()), 'none', movement=mv, bench_id='JS6')
        sat = Q[(Q['pos'] >= 5) & (Q['h'] > .8) & (Q['h'] < 8)] if len(Q) else Q
        print(site, 'centre %.0f %.0f' % (cx, cy), 'T', round(T), 'veh', len(df), 'arms', df[df['arm'] >= 0]['arm'].nunique(), df.groupby('move').size().to_dict(), 'stop %.2f' % df['stop'].mean(), 'sat', sat['h'].median() if len(sat) else None, len(sat), 'pos', Pq.groupby('pos')['h'].median().round(2).head(5).to_dict() if len(Pq) else None, flush=True)
    # With only two lights for four arms the phase is not known per movement, and Xi'an's light file has one long gap. Phase-relative rows go.
    bad = {('sind_changchun', 'first_car_start_after_green'), ('sind_xian', 'first_car_start_after_green'), ('sind_xian', 'cycle_length_median'), ('sind_xian', 'green_length_median'), ('sind_xian', 'entered_on_red_share'), ('sind_xian', 'entered_on_yellow_share'), ('sind_changchun', 'entered_on_red_share'), ('sind_changchun', 'entered_on_yellow_share')}
    rw.r = [r for r in rw.r if (r['site'], r['metric']) not in bad and not (r['metric'] == 'queue_headway_by_position' and r['site'] in ('sind_changchun', 'sind_xian'))]
    rw.write()


if __name__ == '__main__':
    main()
