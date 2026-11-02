#!/usr/bin/env python3
"""Day-to-day noise floor: how well does one real Berlin weekday predict another?

Hourly lane detector counts, September 2024, new quality assurance. Tue-Thu, 07-18 h.
A pair is the same detector and hour seven days apart. Both quality variants are reported.
Writes research/truth/04-berlin-noise-floor.json. CPU only, one thread, no GPU.
"""
import json, tarfile
from pathlib import Path
import numpy as np
import pandas as pd

D = Path('/home/erikf/projects/personal/cars-data/berlin-detectors/detektoren_2024_09.tgz')
out = Path(__file__).resolve().parents[1] / '04-berlin-noise-floor.json'
frames = []
with tarfile.open(D) as tar:
    for m in tar.getmembers():
        if not m.isfile() or not m.name.endswith('.csv'):
            continue
        q = pd.read_csv(tar.extractfile(m), sep=';')
        q = q.rename(columns={q.columns[0]: 'date', q.columns[1]: 'hour'})
        q['det'] = Path(m.name).stem
        frames.append(q[['det', 'date', 'hour', 'Vollständigkeit', 'hist_cor', 'qkfz']])
raw = pd.concat(frames, ignore_index=True)
raw['date'] = pd.to_datetime(raw.date)
raw['site'] = raw.det.str.replace(r'(_Det\d+|D\d+)$', '', regex=True)


def band(c, m):
    if c < 700: return abs(c - m) <= 100
    if c <= 2700: return abs(c - m) <= .15 * c
    return abs(c - m) <= 400


def noise(q, key):
    q = q.sort_values([key, 'hour', 'date']).copy()
    q['wd'] = q.date.dt.dayofweek
    g = q.groupby([key, 'wd', 'hour'])
    q['prev'] = g.c.shift()
    q['prev_date'] = g.date.shift()
    p = q[q.prev.notna() & ((q.date - q.prev_date).dt.days == 7)].copy()
    p['geh'] = np.sqrt(2 * (p.c - p.prev) ** 2 / (p.c + p.prev).replace(0, np.nan))
    p['abs_pct'] = 100 * (p.c - p.prev).abs() / p.prev.replace(0, np.nan)
    p['tag_ok'] = [band(a, b) for a, b in zip(p.prev, p.c)]
    by = []
    bins = [50, 200, 500, 1000, 1500, 5000]
    for lo, hi in zip(bins[:-1], bins[1:]):
        s = p[(p.prev >= lo) & (p.prev < hi)]
        if len(s):
            by.append(dict(flow_lo=lo, flow_hi=hi, pairs=int(len(s)), median_abs_pct=round(float(s.abs_pct.median()), 2),
                           p95_abs_pct=round(float(s.abs_pct.quantile(.95)), 2), share_geh_lt5=round(float((s.geh < 5).mean()), 4),
                           median_geh=round(float(s.geh.median()), 3)))
    per = p.groupby(key).geh.apply(lambda s: float((s < 5).mean()))
    net = p.groupby(['date', 'hour']).geh.apply(lambda s: float((s < 5).mean()))
    return dict(units=int(p[key].nunique()), pairs=int(len(p)), dates=[str(p.date.min().date()), str(p.date.max().date())],
                median_abs_pct=round(float(p.abs_pct.median()), 2), p95_abs_pct=round(float(p.abs_pct.quantile(.95)), 2),
                median_geh=round(float(p.geh.median()), 3), p95_geh=round(float(p.geh.quantile(.95)), 3),
                share_geh_lt5=round(float((p.geh < 5).mean()), 4), share_geh_lt3=round(float((p.geh < 3).mean()), 4),
                share_tag_flow_band=round(float(p.tag_ok.mean()), 4),
                units_over_85pct_geh5=round(float((per > .85).mean()), 4),
                network_hour_share_geh5_p05_median_p95=[round(float(net.quantile(x)), 4) for x in (.05, .5, .95)],
                by_flow=by)


res = dict(source=str(D), rows=int(len(raw)), detector_files=int(raw.det.nunique()))
wd = raw[raw.date.dt.dayofweek.isin([1, 2, 3]) & raw.hour.between(7, 18) & raw.qkfz.notna()]
for name, f in {'completeness_ge75': wd['Vollständigkeit'] >= 75,
                'completeness_ge75_hist_cor_ge05': (wd['Vollständigkeit'] >= 75) & (wd.hist_cor >= .5)}.items():
    q = wd[f].rename(columns={'qkfz': 'c'})
    q = q[q.groupby('det').c.transform('median') >= 50]
    entry = dict(lane=noise(q, 'det'))
    n_lanes = q.groupby(['site', 'date', 'hour']).det.transform('nunique')
    full = q[n_lanes == q.groupby('site').det.transform('nunique')]
    s = full.groupby(['site', 'date', 'hour'], as_index=False).c.sum()
    entry['site_all_lanes'] = noise(s, 'site')
    top = q.groupby('det').c.max()
    entry['lane_max_hourly_p50_p95_p99_max'] = [float(top.quantile(x)) for x in (.5, .95, .99, 1)]
    res[name] = entry
json.dump(res, open(out, 'w'), indent=1)
print(json.dumps(res, indent=1))
