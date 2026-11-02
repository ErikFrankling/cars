"""TGSIM Foggy Bottom: three signals and one all-way stop (H St and 22nd St, named in the data dictionary). No signal states are published."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
import pandas as pd
from common import OUT, Rows, q, spread_of
import jx
import sig

F = '/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-tgsim/Foggy.csv'
SRC = 'TGSIM Foggy Bottom https://data.transportation.gov/api/views/brzy-6zfh.json'
PX = .0186613838586
CENTRES = {'I_23rd': ((1625 + 3090) / 2, (1633 + 2465) / 2), 'I_22nd': (9835, 2051), 'H_23rd': (2175, 10641), 'H_22nd': (9808, 10590)}
IDS = dict(flow='JS7', stops='JS7', delay='JS7', speed='JS9', lane='JS10', sat='JS2')
IDA = dict(flow='JA1', stops='JA2', delay='JA3', speed='JA4', lane='JA5', sat='JA6')
BLOCK = 900


def allway(rw, df, tr, P, cx, cy, spans, persons):
    add = lambda m, v, sp, u, n, kind, **k: rw.add(m, 'all_way_stop', 'foggy_H_22nd', v, sp, SRC, 'tune', u, n, kind, **k)
    d = df[df['arm'] >= 0].sort_values('tin').reset_index(drop=True)
    # how far each car really slowed in the last 20 m before the junction
    vmin = {}
    for p in P:
        a, s, k0 = p['a'], p['s'], p['k0']
        up = max(jx.index_arc(s, s[k0] - 20), 0)
        vmin[(a['id'], round(a['t'][k0], 1))] = a['v'][up:k0 + 1].min()
    d['vmin20'] = [vmin.get((i, round(t, 1)), np.nan) for i, t in zip(d['id'], d['tin'])]
    add('full_stop_share', (d['vmin20'] < 1.).mean(), spread_of((d['vmin20'] < 1.).groupby(d['flight']).mean()), 'share', len(d), 'block_to_block', bench_id='JA2', note='below 1 m/s in the last 20 m')
    add('rolling_stop_share', ((d['vmin20'] >= 1.) & (d['vmin20'] < 3.)).mean(), None, 'share', len(d), 'none', bench_id='JA2', note='1 to 3 m/s')
    add('no_stop_share', (d['vmin20'] >= 3.).mean(), None, 'share', len(d), 'none', bench_id='JA2', note='3 m/s or more')
    add('min_speed_before_entry_median', d['vmin20'].median(), spread_of(d.groupby('flight')['vmin20'].median()), 'm/s', len(d), 'block_to_block', lo=q(d['vmin20'], 10), hi=q(d['vmin20'], 90), bench_id='JA2')
    w = (d['tin'] - d['tgo']).where(d['stop'])
    hold = (d['tgo'] - d['tstop']).where(d['stop'])
    add('stopped_time_median', hold.median(), spread_of(hold.groupby(d['flight']).median()), 's', hold.notna().sum(), 'block_to_block', lo=q(hold, 10), hi=q(hold, 90), bench_id='JA3', note='first to last moment below 1 m/s on the approach')
    # who was at the front, and in what order they went
    front = {}
    for arm, g in d.groupby('arm'):
        prev = -1e9
        for i, c in g.iterrows():
            front[i] = max(c['tstop'] if c['stop'] else c['tin'] - 2, prev)
            prev = c['tin']
    d['front'] = pd.Series(front)
    ok, bad = 0, 0
    I = d.index.values
    for a in range(len(d)):
        for b in range(a + 1, min(a + 12, len(d))):
            x, y = d.iloc[a], d.iloc[b]
            if x['arm'] == y['arm']:
                continue
            if max(x['front'], y['front']) < min(x['tin'], y['tin']) and abs(x['front'] - y['front']) > .5:
                if (x['front'] < y['front']) == (x['tin'] < y['tin']):
                    ok += 1
                else:
                    bad += 1
    add('first_come_first_served_share', ok / max(ok + bad, 1), None, 'share', ok + bad, 'none', bench_id='JA6', note='pairs from different arms, both at the front together, arrival over 0.5 s apart')
    # service headways, between consecutive entries when the follower was already waiting
    h = []
    for a in range(1, len(d)):
        p, c = d.iloc[a - 1], d.iloc[a]
        if c['stop'] and c['front'] < p['tin'] and c['tin'] - p['tin'] < 20:
            h.append((c['flight'], c['arm'] == p['arm'], c['tin'] - p['tin'], c['tin'] - p['tout']))
    H = pd.DataFrame(h, columns=['flight', 'same', 'h', 'clear'])
    for name, g in (('same_arm', H[H['same']]), ('other_arm', H[~H['same']])):
        if len(g) >= 8:
            add('service_headway', g['h'].median(), spread_of(g.groupby('flight')['h'].median()), 's', len(g), 'block_to_block', lo=q(g['h'], 25), hi=q(g['h'], 75), movement=name, bench_id='JA6', note='follower already waiting; lo and hi are p25 and p75')
    if len(H):
        add('service_headway', H['h'].median(), spread_of(H.groupby('flight')['h'].median()), 's', len(H), 'block_to_block', lo=q(H['h'], 25), hi=q(H['h'], 75), movement='any', bench_id='JA6')
        add('departure_rate_when_queued', 3600 / H['h'].mean(), None, 'veh/h', len(H), 'none', bench_id='JA7', note='3600 over the mean service headway; an estimate of capacity, the junction is rarely queued on all arms')
        g = H[~H['same']]
        if len(g) >= 8:
            add('clearance_before_next_entry', g['clear'].median(), None, 's', len(g), 'none', lo=q(g['clear'], 5), hi=q(g['clear'], 95), bench_id='JA8', note='previous car left the 14 m circle to next car from another arm entering; negative means both inside')
    # both inside at once, from different arms
    inside = 0
    for a in range(1, len(d)):
        p, c = d.iloc[a - 1], d.iloc[a]
        if c['arm'] != p['arm'] and c['tin'] < p['tout']:
            inside += 1
    add('entered_while_other_arm_inside_share', inside / max(len(d) - 1, 1), None, 'share', len(d), 'none', bench_id='JA8')
    if len(persons):
        pt, px, py = persons
        rd = np.hypot(px - cx, py - cy) < 16
        pts = np.sort(pt[rd])
        near = np.array([np.searchsorted(pts, t + .2) - np.searchsorted(pts, t - 3.) for t in d['tin']])
        add('entries_with_person_within_16m_share', (near > 0).mean(), None, 'share', len(d), 'none', bench_id='JA8', note='in the 3 s before entry. Pedestrians are not simulated, so stopped time is inflated where this is high')


def main():
    d = pd.read_csv(F, usecols=['id', 'time', 'xloc_kf', 'yloc_kf', 'speed_kf_x', 'speed_kf_y', 'type_most_common'])
    d = d[(d['time'] * 10).round().astype('int64') % 2 == 0]
    print('rows', len(d), 'span', d['time'].min(), d['time'].max(), flush=True)
    pers = d[d['type_most_common'] == 0]
    persons = (pers['time'].values, pers['xloc_kf'].values, pers['yloc_kf'].values)
    v = np.hypot(d['speed_kf_x'].values, d['speed_kf_y'].values)
    keep = {3, 4, 6, 7}
    tr = jx.make_tracks(d['id'].values, d['type_most_common'].values, d['time'].values, d['xloc_kf'].values, d['yloc_kf'].values, v, keep=keep)
    print('tracks', len(tr), flush=True)
    rw = Rows('foggy')
    for name, (px, py) in CENTRES.items():
        cx, cy = px * PX, py * PX
        df, P = jx.per_vehicle(tr, cx, cy, R=14., U=50., label='')
        df['flight'] = (df['tin'] // BLOCK).astype(int).map(lambda b: f'b{b}')
        spans = {f: float(BLOCK) for f in df['flight'].unique()}
        df = jx.lane_clusters(df)
        D = jx.discharge(df)
        allw = name == 'H_22nd'
        site = f'foggy_{name}'
        sig.rows(rw, df, D, site, 'all_way_stop' if allw else 'signal', SRC, 'tune', spans, IDA if allw else IDS, core=14)
        print(site, len(df), 'stop %.2f' % df['stop'].mean(), df.groupby('arm').size().to_dict(), 'chains', len(D), flush=True)
        df.to_csv(OUT / f'foggy_{name}.csv.gz', index=False)
        if allw:
            allway(rw, df, tr, [p for p in P], cx, cy, spans, persons)
    rw.write()


if __name__ == '__main__':
    main()
