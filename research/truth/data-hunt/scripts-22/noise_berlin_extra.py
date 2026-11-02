#!/usr/bin/env python3
"""Fills the cells report 15 left as "compute", and scores null models that know no site.
    python3 -I noise_berlin_extra.py <mq_hr.csv.gz> <sites.csv> <out.json>
"""
import csv
import gzip
import json
import sys

import numpy as np

mq, sites_csv, out = sys.argv[1:4]
DAYS = ['07.05.2019', '14.05.2019', '15.05.2019', '16.05.2019', '21.05.2019', '22.05.2019', '23.05.2019', '28.05.2019']
rows = {}
with gzip.open(mq, 'rt', errors='replace') as f:
    for x in csv.DictReader(f, delimiter=';'):
        if x['tag'] in DAYS:
            try:
                rows[(x['mq_name'], x['tag'], int(x['stunde']))] = (float(x['q_kfz_mq_hr']), float(x['v_kfz_mq_hr']))
            except ValueError:
                pass
sites = sorted({k[0] for k in rows})
sites = [s for s in sites if all((s, d, h) in rows for d in DAYS for h in range(24))]
S, D = len(sites), len(DAYS)
Q, V = np.zeros((D, S, 24)), np.zeros((D, S, 24))
for i, d in enumerate(DAYS):
    for j, s in enumerate(sites):
        for h in range(24):
            Q[i, j, h], V[i, j, h] = rows[(s, d, h)]
V[V <= 0] = np.nan
reg = {x['site']: x for x in csv.DictReader(open(sites_csv))}
free = np.nanquantile(V, .9, axis=(0, 2))
CLS = np.array([2 if reg.get(s, {}).get('road_class') == 'motorway' else 1 if f >= 50 else 0 for s, f in zip(sites, free)])
DAY = np.arange(6, 21)


def geh(a, b):
    s = a + b
    return np.sqrt(np.divide(2 * (a - b) ** 2, s, out=np.zeros_like(s), where=s > 0))


def jam(v, vfree):
    return np.nan_to_num(v, nan=1e9) < .7 * vfree[:, None]


def score(qa, va, qr, vr):
    fr = np.nanquantile(vr, .9, axis=1)
    ja, jr = jam(va, fr)[:, DAY], jam(vr, fr)[:, DAY]
    tp = (ja & jr).sum()
    deficit = lambda v: np.nansum(np.maximum(fr[:, None] - v[:, DAY], 0), axis=1)
    top = lambda x: set(np.argsort(-x)[:20])
    g = geh(qa[:, DAY], qr[:, DAY])
    d = qa[:, DAY] - qr[:, DAY]
    r, c = (qa.sum(1)), (qr.sum(1))
    rk = lambda x: np.argsort(np.argsort(x))
    ssr, sst = (d ** 2).sum(), ((qr[:, DAY] - qr[:, DAY].mean()) ** 2).sum()
    return dict(hit=tp / max(jr.sum(), 1), false_alarm=1 - tp / max(ja.sum(), 1), top20_bottlenecks=len(top(deficit(va)) & top(deficit(vr))) / 20,
                rmsn=np.sqrt((d ** 2).mean()) / qr[:, DAY].mean(), r2=1 - ssr / sst, median_geh=np.median(g), geh_lt5=(g < 5).mean(),
                wape=np.abs(d).sum() / qr[:, DAY].sum(), site_day_spearman=np.corrcoef(rk(r), rk(c))[0, 1],
                jam_sitehours_real=int(jr.sum()), jam_sites_real=int(jr.any(1).sum()))


pairs = [(a, b) for a in range(D) for b in range(D) if a != b]
real = [score(Q[a], V[a], Q[b], V[b]) for a, b in pairs]
keys = list(real[0])
floor = {k: dict(p10=float(np.quantile([r[k] for r in real], .1)), p50=float(np.median([r[k] for r in real])), p90=float(np.quantile([r[k] for r in real], .9))) for k in keys}

# Null models: built from other days, and knowing only the road class of a site.
null = {}
for name in ('class mean profile', 'class mean flow, speed free all day', 'network mean profile'):
    out_rows = []
    for b in range(D):
        others = [i for i in range(D) if i != b]
        mq_ = Q[others].mean(0)
        mv_ = np.nanmean(V[others], axis=0)
        qa, va = np.zeros_like(mq_), np.zeros_like(mv_)
        groups = [np.arange(S)] if name.startswith('network') else [np.where(CLS == k)[0] for k in range(3)]
        for i in groups:
            if len(i):
                qa[i] = mq_[i].mean(0)
                va[i] = np.nanmean(mv_[i], axis=0)
        if 'free' in name:
            va = np.repeat(np.nanquantile(mv_, .9, axis=1, keepdims=True), 24, axis=1)
        out_rows.append(score(qa, va, Q[b], V[b]))
    null[name] = {k: float(np.nanmedian([r[k] for r in out_rows])) for k in keys}

# Best a site-aware null can do: the mean of the other days at the same site.
out_rows = [score(Q[[i for i in range(D) if i != b]].mean(0), np.nanmean(V[[i for i in range(D) if i != b]], axis=0), Q[b], V[b]) for b in range(D)]
null['same site, mean of other days'] = {k: float(np.nanmedian([r[k] for r in out_rows])) for k in keys}

json.dump(dict(days=DAYS, sites=S, classes=np.bincount(CLS, minlength=3).tolist(), floor=floor, null=null), open(out, 'w'), indent=1)
print('done')
