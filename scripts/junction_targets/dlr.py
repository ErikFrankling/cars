"""DLR Urban Traffic, Braunschweig, Sunday 24 Sep 2023, the one junction with controller states. Signal group 7 is held out and is removed everywhere."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
import pandas as pd
from common import OUT, Rows, q, spread_of
import jx
import sig

C = '/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-cache/'
SRC = 'DLR Urban Traffic https://zenodo.org/records/20919480'
IDS = dict(flow='JS7', stops='JS7', delay='JS7', speed='JS9', lane='JS10', sat='JS2')
OX, OY = 604625, 5792650
SID7 = [(604780.221 - OX, 5792775.418 - OY), (604775.881 - OX, 5792774.066 - OY)]
CENTRE = (604770.0 - OX, 5792795.0 - OY)
BLOCK = 3600


def main():
    z = np.load(C + 'ut_veh.npz')
    tr = jx.make_tracks(z['id'], z['truck'], z['t'].astype('f8'), z['x'].astype('f8'), z['y'].astype('f8'), z['v'].astype('f8'))
    print('tracks', len(tr), flush=True)
    d7 = []
    for a in tr:
        m = min(np.hypot(a['x'] - x, a['y'] - y).min() for x, y in SID7)
        if m < 2.2:
            d7.append(a['id'])
    drop = set(d7)
    tr = [a for a in tr if a['id'] not in drop]
    print('removed for held-out group 7:', len(drop), flush=True)
    df, P = jx.per_vehicle(tr, *CENTRE, R=22., U=60., label='')
    df['flight'] = (df['tin'] // BLOCK).astype(int).map(lambda b: f'h{b}')
    spans = {f: float(BLOCK) for f in df['flight'].unique()}
    rw = Rows('dlr')
    sig.rows(rw, jx.lane_clusters(df), None, 'dlr_ut', 'signal', SRC, 'tune', spans, IDS, core=22)
    print('dlr', len(df), df.groupby('move').size().to_dict(), 'stop %.2f' % df['stop'].mean(), flush=True)
    R = np.load(C + 'ut_queue.npz')['R']
    n = 'sid pt tg pos h t_front start_delay start_lag L W truck turn v_cross dist'.split()
    Q = pd.DataFrame(R, columns=n)
    Q = Q[(Q['sid'] != 7) & (Q['truck'] == 0)]
    Q['move'] = np.where(Q['turn'].abs() < 35, 'through', np.where(Q['turn'] > 0, 'left', 'right'))
    Q['hour'] = (Q['tg'] // 3600).astype(int)
    add = lambda m, v, sp, u, nn, kind, **k: rw.add(m, 'signal', 'dlr_ut', v, sp, SRC, 'tune', u, nn, kind, **k)
    for p in range(1, 8):
        g = Q[Q['pos'] == p]
        if len(g) < 5:
            continue
        bg = g.groupby('sid')['h'].agg(['median', 'size'])
        bg = bg[bg['size'] >= 10]['median']
        add('queue_headway_by_position', g['h'].median(), spread_of(bg) if len(bg) > 2 else None, 's', len(g), 'between_signal_groups', lo=q(g['h'], 25), hi=q(g['h'], 75), movement=f'pos{p}', bench_id='JS1', note='from controller green for position 1; lo and hi are p25 and p75')
    for m, g in Q.groupby('move'):
        for p, lab in ((1, 'pos1'), (2, 'pos2')):
            x = g[g['pos'] == p]
            if len(x) >= 10:
                add('queue_headway_by_position', x['h'].median(), None, 's', len(x), 'none', lo=q(x['h'], 25), hi=q(x['h'], 75), movement=f'{m}_{lab}', bench_id='JS1')
        x = g[g['pos'] >= 3]
        if len(x) >= 10:
            add('discharge_headway_pos3plus', x['h'].median(), None, 's', len(x), 'none', lo=q(x['h'], 25), hi=q(x['h'], 75), movement=m, bench_id='JS2', note='by turn; few long queues on a Sunday')
    sat = Q[Q['pos'] >= 5]
    add('saturation_headway', sat['h'].median(), None, 's', len(sat), 'none', lo=q(sat['h'], 25), hi=q(sat['h'], 75), bench_id='JS2', note='Sunday. Report 05 used this as a fit target, so it is tuning only')
    add('saturation_flow', 3600 / sat['h'].median(), None, 'veh/h/lane', len(sat), 'none', bench_id='JS2')
    f = Q[Q['pos'] == 1]
    bg = f.groupby('sid')['start_delay'].agg(['median', 'size'])
    bg = bg[bg['size'] >= 30]['median']
    add('first_car_start_after_green', f['start_delay'].median(), spread_of(bg), 's', len(f), 'between_signal_groups', lo=q(f['start_delay'], 10), hi=q(f['start_delay'], 90), bench_id='JS4')
    byh = Q[Q['pos'].between(2, 4)].groupby('hour')['h'].agg(['median', 'size'])
    byh = byh[byh['size'] >= 15]['median']
    add('queue_headway_pos2to4_hour_spread', byh.median(), spread_of(byh), 's', len(byh), 'hour_to_hour', lo=byh.min(), hi=byh.max(), bench_id='JS1', note='one Sunday, by hour: the nearest thing to day-to-day here')
    # queue length at green, from position counts
    ql = Q.groupby(['sid', 'tg'])['pos'].max()
    add('queue_length_at_green_median', ql.median(), None, 'veh', len(ql), 'none', lo=q(ql, 50), hi=q(ql, 95), bench_id='JS8', note='per lane group and green; hi is p95')
    rw.write()


if __name__ == '__main__':
    main()
