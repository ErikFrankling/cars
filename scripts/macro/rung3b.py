#!/usr/bin/env python3
"""Rung 3, second part. Inputs for `cuttable`, the two-way capacity test, and signal pairs under 50 m. No simulation. Tuning sites only.

    rung3b.py NETDIR BASE ROUTES_F10.rou.gz
Writes macro/NETDIR/{discharge_s*.csv, cut_demand.tsv, cut_real.csv, two_way.csv, signal_pairs.csv}.
Queue present (own first version until real_capacity.csv): hourly speed under .7 of the site's free speed with flow of at least 50, as in metrics.jam_flags.
"""
import collections
import csv
import gzip
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mtable as mt
from rung3 import DATA, SAT, downstream_bound, upstream_bound

netdir, base, routes = sys.argv[1:4]
T = mt.read(DATA / 'district' / netdir / 'net.net.xml')
mt.repair(T, mt.read(DATA / 'district' / base / 'net.net.xml'), [], None, mt.read_none_lanes(DATA / 'district' / netdir / 'lane_tags.csv'))
mt.index_lanes(T)
mt.lane_groups(T)
out = DATA / 'macro' / netdir

for s in SAT:
    with open(out / f'discharge_s{int(s)}.csv', 'w') as f:
        f.write('edge,rate\n')
        for k, e in T['edges'].items():
            if not e['car'] or k not in T['out']:
                continue
            best = {}
            for m in T['out'][k]:
                for c in m['conns']:
                    best[c['fl']] = max(best.get(c['fl'], 0.0), mt.conn_capacity(c, e, s))
            f.write(f'{k},{min(sum(best.values()), len(e["car"]) * mt.midblock(e["v"])) / 3600:.4f}\n')

pat = re.compile(r'depart="([^"]+)".*edges="([^"]+)"')
n = 0
with gzip.open(routes, 'rt') as f, open(out / 'cut_demand.tsv', 'w') as w:
    w.write('o\td\tdepart\n')
    for line in f:
        m = pat.search(line)
        if m:
            r = m[2].split()
            w.write(f'{r[0]}\t{r[-1]}\t{m[1]}\n')
            n += 1
print('trip pieces', n)

freeze = json.load(open(DATA / 'step1/freeze.json'))
tuning = set(freeze['tuning_sites'])
real = pd.read_csv(DATA / 'step1/real_days.csv.gz')
real = real[real.site.isin(tuning)]
sensors = {}
for r in csv.reader(open(DATA / 'district/m12/sensors.csv')):
    if r[0] in tuning:
        e, l = r[1].rsplit('_', 1)
        sensors.setdefault(r[0], (e, []))[1].append(int(l))
rows = [dict(edge=sensors[s][0], hour=int(h), flow=float(g.flow.max())) for (s, h), g in real.groupby(['site', 'hour']) if s in sensors]
pd.DataFrame(rows).to_csv(out / 'cut_real.csv', index=False)

free = real.dropna(subset=['speed']).groupby('site').speed.quantile(.9)
q = real.assign(free=real.site.map(free))
q['ratio'] = q.speed / q.free
sites = pd.read_csv(DATA / 'step0/sites.csv')
sites = sites[sites.site.isin(tuning)].set_index('site')
tw = []
for site, g in real.groupby('site'):
    if site not in sensors:
        continue
    e, ls = sensors[site]
    n = min(len(ls), len(T['edges'][e]['car']))
    qh = q[(q.site == site) & (q.ratio < .7) & (q.flow >= 50)]
    caps = {}
    for s in SAT:
        d, cs, where = downstream_bound(T, e, n, s)
        u = upstream_bound(T, e, s) if n == len(T['edges'][e]['car']) else None
        caps[s] = min(x for x in (d, u, n * mt.midblock(T['edges'][e]['v'])) if x is not None)
    kinds = sorted({mt.kind(c) for c in cs if c})
    sh = sorted({round((c['gp'] + c['gq']) / c['C'], 2) for c in cs if c and c['ctrl']})
    row = dict(site=site, street=sites.street.get(site, ''), road_class=sites.road_class.get(site, ''), edge=e, lanes=n, kinds='+'.join(kinds), gc=';'.join(map(str, sh)), queue_hours=len(qh), real_max_any=float(g.flow.max()), cap_1285=round(caps[1285.0]), cap_1640=round(caps[1640.0]), cap_1895=round(caps[1895.0]))
    if len(qh):
        row.update(real_max_queue=float(qh.flow.max()), real_p90_queue=float(qh.flow.quantile(.9)), ratio_1640=round(float(qh.flow.max()) / caps[1640.0], 2), slowest=round(float(qh.ratio.min()), 2))
    tw.append(row)
tw = pd.DataFrame(tw)
tw.to_csv(out / 'two_way.csv', index=False)
Q = tw.dropna(subset=['ratio_1640'])
print(f"sites {len(tw)}, with a real queue at any hour {len(Q)}; largest flow with a queue / table capacity at s 1640: p10 {Q.ratio_1640.quantile(.1):.2f} p50 {Q.ratio_1640.median():.2f} p90 {Q.ratio_1640.quantile(.9):.2f}; under .85: {(Q.ratio_1640 < .85).sum()}, over 1.1: {(Q.ratio_1640 > 1.1).sum()}")
for lim in (5, 20):
    S = Q[Q.queue_hours >= lim]
    print(f"  with at least {lim} queue site-hours: {len(S)} sites, median {S.ratio_1640.median():.2f}, under .85 {(S.ratio_1640 < .85).sum()}")

# signal pairs: a signal junction, a short way, the next signal junction, with nothing but plain chain junctions between
sig = {k for k, j in T['junc'].items() if j['type'].startswith('traffic_light')}
pairs = []
for k, e in T['edges'].items():
    if not e['car'] or e['frm'] not in sig:
        continue
    L, cur, path = e['L'], k, [k]
    for _ in range(4):
        if T['edges'][cur]['to'] in sig or L >= 50:
            break
        out_ = T['out'].get(cur, [])
        if len(out_) != 1:
            break
        cur = out_[0]['to']
        L += T['edges'][cur]['L']
        path.append(cur)
    if T['edges'][cur]['to'] in sig and L < 50 and T['edges'][cur]['to'] != e['frm']:
        down = T['out'].get(cur, [])
        c0 = next((c for m in down for c in m['conns'] if c['ctrl']), None)
        up = next((c for m in T['inc'].get(k, []) for c in m['conns'] if c['ctrl']), None)
        pairs.append(dict(edges=' '.join(path), name=e['name'], type=e['type'], L=round(L, 1), lanes=len(T['edges'][cur]['car']), storage=round(L * len(T['edges'][cur]['car']) / mt.SPACING, 1), j_up=e['frm'], j_down=T['edges'][cur]['to'], same_controller=bool(up and c0 and up['ctrl'] == c0['ctrl']), ctrl_up=up['ctrl'] if up else '', ctrl_down=c0['ctrl'] if c0 else '', C=c0['C'] if c0 else None, g_down=round((c0['gp'] + c0['gq']) / c0['C'], 2) if c0 else None))
pp = pd.DataFrame(pairs)
pp.to_csv(out / 'signal_pairs.csv', index=False)
print(f"signal pairs under 50 m: {len(pp)}, main road {pp.type.isin(mt.MAIN).sum()}, under 30 m {(pp.L < 30).sum()}, same controller {pp.same_controller.sum()}, storage p50 {pp.storage.median():.1f} cars")
