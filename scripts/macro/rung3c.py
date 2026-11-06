#!/usr/bin/env python3
"""Rung 3, third part. One look per priority-coded main-road through movement; two-way test along the corridor; min cuts in a band on the table. No simulation. Tuning sites only.
    rung3c.py NETDIR BASE ROUTES_DEMAND.tsv
Min cut: split the district in 2, 4 and 8 by bisection. Source: edges over BAND m inside one side; sink: edges over BAND m inside the other. Trips from source to sink must pass the min cut, whatever the route."""
import collections
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_flow

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mtable as mt
from rung3 import DATA, SAT, edge_cap

netdir, base, demand = sys.argv[1:4]
T = mt.read(DATA / 'district' / netdir / 'net.net.xml')
mt.repair(T, mt.read(DATA / 'district' / base / 'net.net.xml'), [], None, mt.read_none_lanes(DATA / 'district' / netdir / 'lane_tags.csv'))
mt.index_lanes(T)
mt.lane_groups(T)
out = DATA / 'macro' / netdir

# one look: what each urban give-way through movement yields to, and whether OSM 2019 has a signal at that junction
audit = pd.read_csv(DATA / 'district/m12/signal_audit.csv')
au = {r.junction: r for r in audit.itertuples()}
rows = []
for m in T['moves']:
    e = T['edges'][m['frm']]
    if m['dir'] == 's' and set(m['kinds']) & {'minor', 'stop', 'rbl'} and e['type'] in mt.MAIN[:8] and e['type'] not in mt.RAMPS:
        foes = sorted({x for c in m['conns'] for x in c['foe_m']})
        names = sorted({(T['edges'][T['moves'][f]['frm']]['name'] or T['edges'][T['moves'][f]['frm']]['type'], T['moves'][f]['dir']) for f in foes})
        a = au.get(m['j'])
        rows.append(dict(name=e['name'], frm=m['frm'], to=m['to'], type=e['type'], to_type=T['edges'][m['to']]['type'], j=m['j'], jtype=T['junc'][m['j']]['type'], lanes=len(m['lanes']), yields_to='; '.join(f'{a_} {b}' for a_, b in names), osm=(a.kind if a is not None else ''), osm_tags=(a.tags if a is not None else '')))
pd.DataFrame(rows).to_csv(out / 'audit_prio_look.csv', index=False)
print('urban give-way through movements on main roads:', len(rows))
for r in rows:
    print(' ', r['name'], r['frm'], '->', r['to_type'], 'j', r['j'], r['jtype'], '| yields to', r['yields_to'][:90], '| OSM', r['osm'])

# two-way along the corridor: from the site follow the way straight on up to 400 m, to the first signal
freeze = json.load(open(DATA / 'step1/freeze.json'))
tuning = set(freeze['tuning_sites'])
real = pd.read_csv(DATA / 'step1/real_days.csv.gz')
real = real[real.site.isin(tuning)]
sensors = {}
for r in csv.reader(open(DATA / 'district/m12/sensors.csv')):
    if r[0] in tuning:
        e, l = r[1].rsplit('_', 1)
        sensors.setdefault(r[0], (e, []))[1].append(int(l))
free = real.dropna(subset=['speed']).groupby('site').speed.quantile(.9)
q = real.assign(free=real.site.map(free))
q['ratio'] = q.speed / q.free
sites = pd.read_csv(DATA / 'step0/sites.csv')
sites = sites[sites.site.isin(tuning)].set_index('site')


def corridor(e, s, limit=400.0):
    """Lowest capacity on the way straight on, and where it is. Whole-edge capacity with lanes of through movements and the rest."""
    best, where, L = 1e9, e, 0.0
    cur = e
    seen = {e}
    n0 = len(T['edges'][e]['car'])
    while True:
        ms = T['out'].get(cur, [])
        if not ms:
            break
        c = next((c for m in ms for c in m['conns'] if c['ctrl']), None)
        cap, _ = edge_cap(T, cur, len(T['edges'][cur]['car']), s)
        if cap < best:
            best, where = cap, cur
        if c is not None and cur != e:
            break
        st = [m for m in ms if m['dir'] == 's']
        nxt = st[0]['to'] if st else (ms[0]['to'] if len(ms) == 1 else None)
        if nxt is None or nxt in seen:
            break
        seen.add(nxt)
        L += T['edges'][cur]['L']
        if L > limit:
            break
        cur = nxt
    return best, where, L


tw = []
for site, g in real.groupby('site'):
    if site not in sensors:
        continue
    e, ls = sensors[site]
    n = min(len(ls), len(T['edges'][e]['car']))
    qh = q[(q.site == site) & (q.ratio < .7) & (q.flow >= 50)]
    if not len(qh):
        continue
    frac = n / max(len(T['edges'][e]['car']), 1)
    cap, where, L = corridor(e, 1640.0)
    own, _ = edge_cap(T, e, n, 1640.0)
    c = min(cap * frac if frac < 1 else cap, own)
    ed = T['edges'][where]
    cc = next((x for m in T['out'].get(where, []) for x in m['conns'] if x['ctrl']), None)
    tw.append(dict(site=site, street=sites.street.get(site, ''), road_class=sites.road_class.get(site, ''), lanes=n, queue_hours=len(qh), slowest=round(float(qh.ratio.min()), 2), real_max_queue=float(qh.flow.max()), real_per_lane=round(float(qh.flow.max()) / n), cap=round(c), ratio=round(float(qh.flow.max()) / c, 2), bind=where, bind_street=ed['name'], gc=round((cc['gp'] + cc['gq']) / cc['C'], 2) if cc else None, dist=round(L)))
tw = pd.DataFrame(tw).sort_values('ratio')
tw.to_csv(out / 'two_way_corridor.csv', index=False)
for lim in (1, 5, 20):
    S = tw[tw.queue_hours >= lim]
    print(f'two-way, at least {lim} queue site-hours: {len(S)} sites, ratio p10 {S.ratio.quantile(.1):.2f} p50 {S.ratio.median():.2f} p90 {S.ratio.quantile(.9):.2f}, under .85: {(S.ratio < .85).sum()}, over 1.1: {(S.ratio > 1.1).sum()}; per lane flow with a queue p50 {S.real_per_lane.median():.0f}')
S = tw[(tw.queue_hours >= 5) & tw.gc.notna()]
print(f'signal-bound with at least 5 queue site-hours: {len(S)}, table s*g/C per lane implied by real flow = per-lane flow: p50 {S.real_per_lane.median():.0f}; with s 1640 that means g/C {S.real_per_lane.median() / 1640:.2f}; map g/C p50 {S.gc.median():.2f}')

# min cuts
ids = [k for k, e in T['edges'].items() if e['car']]
idx = {k: i for i, k in enumerate(ids)}
xy = np.array([T['edges'][k]['xy'] for k in ids])
BAND = 400.0
dem = pd.read_csv(demand, sep='\t')
dem = dem[dem.o.isin(idx) & dem.d.isin(idx)]
oi, di = dem.o.map(idx).values, dem.d.map(idx).values
t = dem.depart.values


def split(ix, level):
    if level == 0:
        return [ix]
    a = 0 if np.ptp(xy[ix, 0]) >= np.ptp(xy[ix, 1]) else 1
    o = ix[np.argsort(xy[ix, a])]
    return split(o[:len(o) // 2], level - 1) + split(o[len(o) // 2:], level - 1)


def peak_hour(mask):
    d = np.sort(t[mask])
    if not len(d):
        return 0
    j = np.searchsorted(d, d + 3600)
    return int((j - np.arange(len(d))).max())


res = []
for s in SAT:
    rate = {}
    for k in ids:
        c, _ = edge_cap(T, k, len(T['edges'][k]['car']), s)
        rate[k] = int(round(min(c if k in T['out'] else 1e6, len(T['edges'][k]['car']) * mt.midblock(T['edges'][k]['v']))))
    n = len(ids)
    SRC, SNK = 2 * n, 2 * n + 1
    for level in (1, 2, 3):
        parts = split(np.arange(n), level)
        for pi, P in enumerate(parts):
            side = np.zeros(n, bool)
            side[P] = True
            from scipy.spatial import cKDTree
            ti, to = cKDTree(xy[side]), cKDTree(xy[~side])
            core_in = side & (to.query(xy, k=1)[0] > BAND)
            core_out = (~side) & (ti.query(xy, k=1)[0] > BAND)
            for dirn, a_, b_ in (('out', core_in, core_out), ('in', core_out, core_in)):
                if a_.sum() < 10 or b_.sum() < 10:
                    continue
                r, c, v = [], [], []
                for k in ids:
                    i = idx[k]
                    r.append(2 * i); c.append(2 * i + 1); v.append(rate[k])
                    for m in T['out'].get(k, []):
                        if m['to'] in idx:
                            r.append(2 * i + 1); c.append(2 * idx[m['to']]); v.append(10 ** 7)
                for i in np.where(a_)[0]:
                    r.append(SRC); c.append(2 * i); v.append(10 ** 7)
                for i in np.where(b_)[0]:
                    r.append(2 * i + 1); c.append(SNK); v.append(10 ** 7)
                g = csr_matrix((np.array(v, dtype=np.int32), (r, c)), shape=(2 * n + 2, 2 * n + 2))
                mf = maximum_flow(g, SRC, SNK).flow_value
                pk = peak_hour(a_[oi] & b_[di])
                res.append(dict(s=int(s), k=2 ** level, part=pi, dir=dirn, min_cut=int(mf), peak_1h=pk, vc=round(pk / max(mf, 1), 2)))
    if s == 1640.0:
        pd.DataFrame(res).to_csv(out / 'mincuts.csv', index=False)
R = pd.DataFrame(res)
R.to_csv(out / 'mincuts.csv', index=False)
print(R.groupby('s').agg(cuts=('vc', 'size'), over=('vc', lambda v: int((v > 1).sum())), max_vc=('vc', 'max'), median_vc=('vc', 'median')))
print(R.sort_values('vc', ascending=False).head(8).to_string())
