"""Weekday signal targets in Athens from pNEUMA: real saturating traffic with no signal states. Sites come from the scan; held-out drones are absent."""
import glob
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
import pandas as pd
from common import OUT, Rows, q, spread_of
import jx
import pneuma_scan as ps
import sig

SRC = 'pNEUMA https://zenodo.org/records/10491409'
IDS = dict(flow='JS7', stops='JS7', delay='JS7', speed='JS9', lane='JS10', sat='JS2')


def choose():
    c = [x for x in json.load(open(OUT / 'pneuma_candidates.json')) if x['kind'] == 'signal' and x['drone'] in ('d5', 'd7', 'd9', 'd10') and x.get('arms', 0) >= 2 and x['vmin_p50'] >= .25 and x['n_minor'] >= 250]
    c.sort(key=lambda x: -x['n_minor'])
    out = []
    for x in c:
        if all(np.hypot(x['x'] - y['x'], x['y'] - y['y']) > 60 for y in out):
            out.append(x)
    per = {}
    keep = []
    for x in out:
        if per.get(x['drone'], 0) < 3:
            keep.append(x)
            per[x['drone']] = per.get(x['drone'], 0) + 1
    return keep


def main():
    rw = Rows('pneuma_signals')
    S = choose()
    for x in S:
        print(x['drone'], round(x['x']), round(x['y']), x['n_minor'], x.get('arms'), flush=True)
    for x in S:
        site = f"athens_signal_{x['drone']}_{round(x['x'])}_{round(x['y'])}"
        dfs, ds, spans = [], [], {}
        for f in sorted(glob.glob(str(OUT / 'pneuma' / f"*_{x['drone']}_*.npz"))):
            nm = pathlib.Path(f).stem
            day, _, w = nm.split('_')[:3]
            fl = f'{day}_{w}'
            tr = ps.load(f)
            df, P = jx.per_vehicle(tr, x['x'], x['y'], R=18., U=60., label=fl)
            if not len(df):
                continue
            df = jx.lane_clusters(df)
            dfs.append(df)
            spans[fl] = 1800.
            d = jx.discharge(df)
            if len(d):
                ds.append(d)
        D = pd.concat(dfs)
        Q = pd.concat(ds) if ds else pd.DataFrame()
        sig.rows(rw, D, Q, site, 'signal', SRC, 'tune', spans, IDS, core=18)
        D['day'] = D['flight'].str[:8]
        per = D.groupby('day').agg(n=('stop', 'size'), stop=('stop', 'mean'), sessions=('flight', 'nunique'))
        per['flow'] = per['n'] * 3600 / (per['sessions'] * 1800)
        rw.add('junction_flow_total', 'signal', site, per['flow'].median(), (per['flow'].max() - per['flow'].min()) / 2, SRC, 'tune', 'veh/h', int(per['n'].sum()), 'day_to_day', lo=per['flow'].min(), hi=per['flow'].max(), bench_id='JS7', note='3 weekdays. spread is half the range of the daily values')
        rw.add('stop_share', 'signal', site, per['stop'].median(), (per['stop'].max() - per['stop'].min()) / 2, SRC, 'tune', 'share', int(per['n'].sum()), 'day_to_day', lo=per['stop'].min(), hi=per['stop'].max(), bench_id='JS7')
        if len(Q):
            Q['day'] = Q['flight'].str[:8]
            g = Q[(Q['pos'] >= 4) & (Q['h'] > .8) & (Q['h'] < 8)].groupby('day')['h'].agg(['median', 'size'])
            g = g[g['size'] >= 10]['median']
            if len(g) > 1:
                rw.add('discharge_headway_pos4plus', 'signal', site, g.median(), (g.max() - g.min()) / 2, SRC, 'tune', 's', int(len(Q)), 'day_to_day', lo=g.min(), hi=g.max(), bench_id='JS2')
        sat = Q[(Q['pos'] >= 5) & (Q['h'] > .8) & (Q['h'] < 8)] if len(Q) else Q
        print(site, len(D), 'stop %.2f' % D['stop'].mean(), 'sat', sat['h'].median() if len(sat) else None, len(sat), D.groupby('move').size().to_dict(), flush=True)
    rw.write()


if __name__ == '__main__':
    main()
