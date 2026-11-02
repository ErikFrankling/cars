#!/usr/bin/env python3
"""Real-against-real noise floors at tick and junction level, from the caches of report 05 only.
Blocks: a TGSIM run, or 15 min of one recording. Within site means block against block on the same
road. Between site means the pooled road against another pooled road.
    python3 -I noise_micro.py <cache_dir> <out.json>
"""
import itertools
import json
import os
import resource
import sys

os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
resource.setrlimit(resource.RLIMIT_AS, (8000 * 1024 ** 2, 8000 * 1024 ** 2))
import numpy as np

cache, out = sys.argv[1:3]
BANDS = [(1, 5), (5, 10), (10, 15), (15, 25), (25, 40)]
P = np.linspace(.01, .99, 99)
Q = (.05, .5, .95)


def w1q(a, b):
    return float(np.abs(a - b).mean())


def load(site):
    """Whole segments only, one in four on the A39, so a block still holds unbroken tracks."""
    d = np.load(f'{cache}/pairs_{site}.npz')
    seg = d['seg'].astype('i4')
    keep = seg % 4 == 0 if site == 'HT' else np.ones(seg.shape, bool)
    r = dict(seg=seg[keep])
    for k, ty in (('vf', 'f4'), ('cc', 'f4'), ('run', 'i4'), ('t', 'i4')):
        r[k] = d[k][keep].astype(ty)
    d.close()
    print(site, 'rows', keep.sum(), 'median tick', float(np.median(np.diff(r['t'][:200000])[np.diff(r['seg'][:200000]) == 0])), 'runs', len(np.unique(r['run'])), flush=True)
    return r


def per_site(site, hz, blockfn):
    r = load(site)
    v, t, seg, cc = r['vf'], r['t'], r['seg'], r['cc']
    h = int(round(.5 * hz))
    a = np.full(v.shape, np.nan, 'f4')
    ok = (seg[2 * h:] == seg[:-2 * h]) & (t[2 * h:] - t[:-2 * h] == 2 * h)
    a[h:-h][ok] = (v[2 * h:] - v[:-2 * h])[ok]  # speed change over 1 s, so already m/s^2
    j = np.full(v.shape, np.nan, 'f4')
    ok2 = np.isfinite(a[2 * h:]) & np.isfinite(a[:-2 * h]) & (seg[2 * h:] == seg[:-2 * h])
    j[h:-h][ok2] = (a[2 * h:] - a[:-2 * h])[ok2]
    T = (cc - 5) / np.maximum(v, .1)
    T[(cc > 100) | (v < 1)] = np.nan
    block = blockfn(r)
    res = {}
    for lo, hi in BANDS:
        m = (v >= lo) & (v < hi)
        if m.sum() < 20000:
            continue
        name = f'{lo}-{hi}'
        rows = {}
        for b in np.unique(block[m]):
            mb = m & (block == b)
            if mb.sum() < 5000:
                continue
            rows[int(b)] = dict(a=np.nanquantile(a[mb], P), j=np.nanquantile(j[mb], P), T=np.nanquantile(T[mb], P))
        pool = dict(a=np.nanquantile(a[m], P), j=np.nanquantile(j[m], P), T=np.nanquantile(T[m], P))
        bw = {}
        for k in ('a', 'j', 'T'):
            x = [w1q(rows[p][k], rows[q][k]) for p, q in itertools.combinations(rows, 2)]
            bw[k] = dict(pairs=len(x), p50=float(np.median(x)), p90=float(np.quantile(x, .9)), max=float(max(x))) if x else None
        res[name] = dict(n=int(m.sum()), blocks=len(rows), within=bw,
                         pooled=dict(a_q=np.nanquantile(a[m], Q).tolist(), j_abs_p95=float(np.nanquantile(np.abs(j[m]), .95)), T_q=np.nanquantile(T[m], Q).tolist()),
                         cdf=pool)
    del a, j, T, block, r, v, t, seg, cc
    return res


def run_block(r):
    return r['run']


def time_block(hz, minutes=15):
    def f(r):
        return r['run'].astype('i8') * 100000 + (r['t'].astype('i8') // int(hz * 60 * minutes))
    return f


SITES = {'I90stat': (10, run_block), 'I90mov': (10, run_block), 'I395': (10, time_block(10)), 'I294L1': (10, run_block), 'HT': (10, time_block(10))}
out_sites = {}
for s, (hz, fn) in SITES.items():
    print(s, flush=True)
    out_sites[s] = per_site(s, hz, fn)
between = {}
for (s1, r1), (s2, r2) in itertools.combinations(out_sites.items(), 2):
    for b in r1:
        if b in r2:
            between[f'{s1}|{s2}|{b}'] = {k: w1q(r1[b]['cdf'][k], r2[b]['cdf'][k]) for k in ('a', 'j', 'T')}
for s in out_sites:
    for b in out_sites[s]:
        del out_sites[s][b]['cdf']

# queues at signals, DLR UT: by signal group and by quarter of the day's queues
d = np.load(f'{cache}/ut_queue.npz')['R']
n = 'sid pt tg pos h t_front start_delay start_lag L W truck turn v_cross dist'.split()
ix = {k: i for i, k in enumerate(n)}
sid, pos, h, sd = d[:, ix['sid']], d[:, ix['pos']], d[:, ix['h']], d[:, ix['start_delay']]
cars = d[:, ix['truck']] == 0
tg = d[:, ix['tg']]
q = {}
for p in (1, 2, 3, 4):
    m = (pos == p) & cars
    byg = {int(g): float(np.median(h[m & (sid == g)])) for g in np.unique(sid[m]) if (m & (sid == g)).sum() >= 30}
    qs = np.quantile(tg[m], [.25, .5, .75])
    bt = np.digitize(tg, qs)
    byt = [float(np.median(h[m & (bt == k)])) for k in range(4) if (m & (bt == k)).sum() >= 20]
    q[f'pos{p}'] = dict(n=int(m.sum()), median=float(np.median(h[m])), by_group=byg, group_range=[min(byg.values()), max(byg.values())] if byg else None, by_time_quarter=byt)
m = (pos >= 3) & cars
bs = np.random.default_rng(1)
q['sat_headway_pos3plus'] = dict(n=int(m.sum()), median=float(np.median(h[m])), boot95=np.quantile([np.median(bs.choice(h[m], m.sum())) for _ in range(500)], [.025, .975]).tolist())
m = (pos == 1) & cars
q['first_car_start_delay'] = dict(n=int(m.sum()), median=float(np.median(sd[m])), by_group={int(g): float(np.median(sd[m & (sid == g)])) for g in np.unique(sid[m]) if (m & (sid == g)).sum() >= 30})

# roundabouts: censored lognormal critical gap per session, the method of report 05
import csv
rows = list(csv.DictReader(open(f'{cache}/roundabout_decisions.csv')))
from scipy.optimize import minimize
from scipy.stats import norm


def mle(acc, rmax):
    lg, lr = np.log(np.maximum(acc, .05)), np.log(np.maximum(rmax, .05))

    def nll(x):
        mu, s = x[0], np.exp(x[1])
        return -np.log(np.maximum(norm.cdf((lg - mu) / s) - norm.cdf((lr - mu) / s), 1e-9)).sum()
    r = minimize(nll, [1.1, -1.3], method='Nelder-Mead', options=dict(maxiter=300))
    return float(np.exp(r.x[0]))


sess = {}
for x in rows:
    sess.setdefault((x['site'], x['file']), []).append(x)
ses = {}
for k, v in sess.items():
    acc = np.array([float(x['acc']) for x in v])
    rm = np.array([float(x['rmax']) if x['rmax'] else 0 for x in v])
    ok = (acc > rm) & (acc > 0)
    if ok.sum() >= 100:
        ses[f'{k[0]} {k[1]}'] = dict(n=int(ok.sum()), crit=mle(acc[ok], rm[ok]), accepted_q=np.quantile(acc[ok], Q).tolist())
crit = {}
for s in ('F1', 'F2', 'L1'):
    x = [v['crit'] for k, v in ses.items() if k.startswith(s)]
    crit[s] = dict(sessions=len(x), min=min(x) if x else None, median=float(np.median(x)) if x else None, max=max(x) if x else None)

# lane changes on the A39 by hour
lc = {}
for x in csv.DictReader(open(f'{cache}/ht_lc.csv')):
    try:
        if x['truck'] in ('0', '0.0', 'False'):
            lc.setdefault(int(float(x['hour'])), []).append((float(x['d1090']), float(x['peak'])))
    except ValueError:
        pass
lc_h = {h: dict(n=len(v), d1090=float(np.median([a for a, _ in v])), peak=float(np.median([b for _, b in v]))) for h, v in sorted(lc.items()) if len(v) >= 200}

json.dump(dict(sites=out_sites, between=between, queue=q, roundabout_sessions=ses, roundabout=crit, lane_change_by_hour=lc_h), open(out, 'w'), indent=1)
print('done')
