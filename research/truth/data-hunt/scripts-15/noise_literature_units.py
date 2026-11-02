#!/usr/bin/env python3
"""How does one real Berlin weekday score against another, in the units calibration papers publish?

Same detector archive and filter as research/truth/scripts/validity_berlin_noise.py (September 2024,
Tue-Thu, completeness >= 75, median flow >= 50 veh/h). Adds RMSN (= nRMSE), pooled R2 and slope, at lane
and whole-site level, hourly and daily, plus the day shape and the network total.
Reads only a local archive. One thread. No GPU.
"""
import json
import sys
import tarfile
from pathlib import Path

import numpy as np
import pandas as pd

D = Path('/home/erikf/projects/personal/cars-data/berlin-detectors/detektoren_2024_09.tgz')
out = Path(sys.argv[1])

frames = []
with tarfile.open(D) as tar:
    for m in tar.getmembers():
        if not m.isfile() or not m.name.endswith('.csv'):
            continue
        q = pd.read_csv(tar.extractfile(m), sep=';')
        q = q.rename(columns={q.columns[0]: 'date', q.columns[1]: 'hour'})
        q['det'] = Path(m.name).stem
        frames.append(q[['det', 'date', 'hour', 'Vollständigkeit', 'qkfz']])
raw = pd.concat(frames, ignore_index=True)
raw['date'] = pd.to_datetime(raw.date)
raw['site'] = raw.det.str.replace(r'(_Det\d+|D\d+)$', '', regex=True)
wd = raw[raw.date.dt.dayofweek.isin([1, 2, 3]) & raw['Vollständigkeit'].ge(75) & raw.qkfz.notna()].rename(columns={'qkfz': 'c'})
wd = wd[wd.groupby('det').c.transform('median') >= 50]


def fit(a, b):
    """a plays the model, b the observation."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    r = np.corrcoef(a, b)[0, 1]
    slope = np.polyfit(b, a, 1)[0]
    geh = np.sqrt(2 * (a - b) ** 2 / np.where(a + b > 0, a + b, np.nan))
    return dict(n=int(len(a)), rmsn=round(float(np.sqrt(np.mean((a - b) ** 2)) / b.mean()), 4),
                wape=round(float(np.abs(a - b).sum() / b.sum()), 4), r2=round(float(r * r), 4),
                slope=round(float(slope), 4), bias=round(float(a.sum() / b.sum() - 1), 4),
                geh_lt5=round(float(np.nanmean(geh < 5)), 4), median_geh=round(float(np.nanmedian(geh)), 3))


def pairs(q, key, by):
    q = q.sort_values([key] + by + ['date']).copy()
    q['wd'] = q.date.dt.dayofweek
    g = q.groupby([key, 'wd'] + by)
    q['prev'], q['prev_date'] = g.c.shift(), g.date.shift()
    return q[q.prev.notna() & ((q.date - q.prev_date).dt.days == 7)]


def suite(q, key):
    r = {}
    for label, f in {'07_18': q.hour.between(7, 18), 'all_hours': q.hour.between(0, 23)}.items():
        p = pairs(q[f], key, ['hour'])
        r['hourly_' + label] = fit(p.c, p.prev)
        per_date = [fit(s.c, s.prev)['rmsn'] for _, s in p.groupby('date') if len(s) > 100]
        r['hourly_' + label + '_rmsn_per_date_p10_p50_p90'] = [round(float(np.quantile(per_date, x)), 4) for x in (.1, .5, .9)]
    # one day against the mean of the other comparable days (what papers with averaged data compare to)
    h = q[q.hour.between(7, 18)].copy()
    h['wd'] = h.date.dt.dayofweek
    g = h.groupby([key, 'wd', 'hour']).c
    n, s = g.transform('count'), g.transform('sum')
    h = h[n >= 3]
    h = h.assign(loo=(s[n >= 3] - h.c) / (n[n >= 3] - 1))
    r['hourly_07_18_day_vs_mean_of_others'] = fit(h.c, h.loo)
    # whole-day counts
    full = q.groupby([key, 'date']).agg(c=('c', 'sum'), hours=('hour', 'nunique')).reset_index()
    full = full[full.hours == 24]
    p = pairs(full.assign(hour=0), key, ['hour'])
    r['daily_total'] = fit(p.c, p.prev)
    return r


res = dict(source=str(D), rows=int(len(raw)), days=[str(wd.date.min().date()), str(wd.date.max().date())],
           note='Same detector, same weekday, seven days apart. a=later day, b=earlier day. All vehicles (qkfz).')
res['lane'] = suite(wd, 'det')
n_lanes = wd.groupby(['site', 'date', 'hour']).det.transform('nunique')
full = wd[n_lanes == wd.groupby('site').det.transform('nunique')]
s = full.groupby(['site', 'date', 'hour'], as_index=False).c.sum()
res['site'] = suite(s, 'site')
res['sites_in_panel'] = int(s.site.nunique())

# day shape and network total over a balanced panel of sites present in every hour of every used day
days = sorted(s.date.unique())
counts = s.groupby('site').size()
panel = counts[counts >= 0.9 * counts.max()].index
b = s[s.site.isin(panel)]
# mean per reporting site, so a site missing an hour does not read as a traffic change
prof = b.pivot_table(index='date', columns='hour', values='c', aggfunc='mean')
prof = prof[prof.notna().all(axis=1)]
share = prof.div(prof.sum(axis=1), axis=0)
diffs = []
for i in range(len(prof.index)):
    for j in range(i + 1, len(prof.index)):
        if prof.index[i].dayofweek == prof.index[j].dayofweek:
            diffs.append(float((share.iloc[i] - share.iloc[j]).abs().mean() * 100))
tot = prof.sum(axis=1)
res['network'] = dict(sites=int(len(panel)), days=int(len(prof)),
                      daily_total_cv=round(float(tot.std() / tot.mean()), 4),
                      hourly_total_cv_median=round(float((prof.std() / prof.mean()).median()), 4),
                      hourly_total_cv_max=round(float((prof.std() / prof.mean()).max()), 4),
                      hourly_share_mean_abs_diff_pct_points_same_weekday=round(float(np.mean(diffs)), 4) if diffs else None,
                      peak_hour_by_day=[int(x) for x in prof.loc[:, 5:11].idxmax(axis=1)],
                      pm_peak_hour_by_day=[int(x) for x in prof.loc[:, 12:20].idxmax(axis=1)])
json.dump(res, open(out, 'w'), indent=1)
print(json.dumps(res, indent=1))
