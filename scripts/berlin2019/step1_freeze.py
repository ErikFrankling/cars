#!/usr/bin/env python3
"""Recipe step 1. Register the test, the held-out sites and the metric code, and compute the floor.

No simulated number is read here. Writes step1/{real_days.csv.gz,freeze.json,floor.json,floor.md}.
Rules follow report 22 section 9, which replaced the first version of this freeze before any score:
- May 2019 is tuning data, 15 May included: it has been read, so it is not blind. Other 2019 months are locked and not downloaded.
- Sites: 70% tuning by sha256(site + "cars-bench-v1") within each road class, 30% locked, plus every station over 200 m from a v6.4 calibration link, the only blind flow result.
- A site-day that looks faulty is dropped from real data alone (rules from reference_day_build.py).
"""
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
import metrics

OUT = B19 / 'step1'
SALT = 'cars-bench-v1'
DAYS = ['2019-05-07', '2019-05-14', '2019-05-15', '2019-05-16', '2019-05-21', '2019-05-22', '2019-05-23', '2019-05-28']
SELECTION_DAY = '2019-05-14'


def load_days():
    d = pd.read_csv(MQ, sep=';').rename(columns={'mq_name': 'site', 'stunde': 'hour', 'q_kfz_mq_hr': 'flow', 'v_kfz_mq_hr': 'speed', 'q_lkw_mq_hr': 'trucks', 'v_lkw_mq_hr': 'speed_trucks'})
    d['date'] = pd.to_datetime(d.tag, format='%d.%m.%Y').dt.strftime('%Y-%m-%d')
    d = d[d.date.isin(DAYS)][['site', 'date', 'hour', 'flow', 'speed', 'trucks']]
    d.loc[d.flow < 0, 'flow'] = np.nan
    d.loc[(d.speed <= 0) | (d.flow <= 0), 'speed'] = np.nan
    return d


def faulty(d):
    """Site-days that do not look like their own site's other days. Real data only."""
    wide = d.pivot_table(index=['site', 'date'], columns='hour', values='flow', aggfunc='first').reindex(columns=range(24))
    n = wide.notna().sum(axis=1)
    med = wide.groupby('site').transform('median')
    ratio = wide.sum(axis=1) / med.where(wide.notna()).sum(axis=1).replace(0, np.nan)
    corr = wide.T.corrwith(med.T)
    same = (wide.diff(axis=1) == 0) & (wide > 0)
    run = same.astype(int).T.apply(lambda c: (c.groupby((c == 0).cumsum()).cumsum()).max())
    bad = (n < 18) | (ratio < .5) | (ratio > 1.5) | (corr < .7) | (run >= 5) | ratio.isna()
    return bad


def main():
    OUT.mkdir(exist_ok=True)
    sites = pd.read_csv(B19 / 'step0/sites.csv')
    district = json.load(open(B19 / 'step0/district.json'))
    x0, y0, x1, y1 = district['box']
    trusted = sites[sites.quality == 'trusted']
    inside = trusted[(trusted.x >= x0) & (trusted.x < x1) & (trusted.y >= y0) & (trusted.y < y1)].copy()
    match = json.load(open(DATA / 'datasets/berlin-2019-detectors/holdout_match.json'))
    far = {r[0] for r in match if r[3] is None or r[3] > 200}
    d = load_days()
    bad = faulty(d)
    keep = bad[~bad].reset_index()[['site', 'date']]
    clean = d.merge(keep, on=['site', 'date'])
    per = clean.groupby('site').date.nunique()
    daily = clean.groupby(['site', 'date']).flow.sum().groupby('site').median()
    usable = set(per[per >= 5].index) & set(daily[daily >= 100].index)
    print('sites with at least 5 clean days of 8:', len(usable), 'site-days dropped', int(bad.sum()), 'of', len(bad))
    clean = clean[clean.site.isin(usable)]
    clean.to_csv(OUT / 'real_days.csv.gz', index=False)
    inside = inside[inside.site.isin(usable)]

    # the split is registered for all of Berlin, so a grown district keeps it
    held_all = set(sites[sites.site.isin(far)].site)
    for c, g in sites[sites.quality == 'trusted'].groupby('road_class'):
        order = sorted(g.site, key=lambda x: hashlib.sha256((x + SALT).encode()).hexdigest())
        held_all |= set(order[:int(np.ceil(.3 * len(order)))])
    held = set(inside.site) & held_all
    selection = sorted(set(inside.site) - held)
    classes = dict(zip(sites.site, sites.road_class))
    code = hashlib.sha256((Path(__file__).parent / 'metrics.py').read_bytes()).hexdigest()
    freeze = dict(frozen_before_any_score=True, tuning_days=DAYS, read_day_of_report_12=TEST_DAY, district=district, district_sites=sorted(inside.site), tuning_sites=selection, locked_sites=sorted(held), locked_clean_200m=sorted(held & far), locked_sites_all_berlin=sorted(held_all), metrics_sha256=code, salt=SALT, rule='report 22 section 9: locked sites are never scored or read for a simulated day here; other 2019 months stay undownloaded; the benchmark reveals them')
    (OUT / 'freeze.json').write_text(json.dumps(freeze, indent=1))
    print(f'district sites {len(inside)}, tuning {len(selection)}, locked {len(held)}, of which clean {len(held & far)}; Berlin locked {len(held_all)}')

    res = {}
    groups = {'city, all usable': sorted(usable), 'district': sorted(inside.site), 'district tuning sites': selection, 'district locked sites': sorted(held)}
    for name, ss in groups.items():
        for ref_day in (TEST_DAY, SELECTION_DAY):
            q = clean[clean.site.isin(ss)]
            ref = q[q.date == ref_day][['site', 'hour', 'flow', 'speed']]
            res.setdefault(name, {})[ref_day] = {o: metrics.score(q[q.date == o][['site', 'hour', 'flow', 'speed']], ref, classes) for o in DAYS if o != ref_day}
    (OUT / 'floor.json').write_text(json.dumps(res, indent=1, default=float))

    def pick(s, *path):
        for p in path:
            if not isinstance(s, dict) or p not in s:
                return np.nan
            s = s[p]
        return np.nan if s is None else s
    rows = [('Hourly site RMSN, 07-18', ('volume_07_18', 'rmsn')), ('Hourly site R2', ('volume_07_18', 'r2')), ('Hourly slope', ('volume_07_18', 'slope')), ('Hourly GEH<5', ('volume_07_18', 'geh_lt5')), ('Hourly WAPE', ('volume_07_18', 'wape')), ('Total, sites, ratio-1', ('day_shape', 'total_ratio')), ('Day shape, mean abs share, points', ('day_shape', 'mean_abs_share_points')), ('Speed, site median abs, km/h', ('speed_site_median_abs_kmh',)), ('Jam site-hours caught', ('where_when', 'caught')), ('Jam false alarms', ('where_when', 'false_alarm')), ('Top bottlenecks shared', ('where_when', 'top_bottlenecks', 'shared')), ('Onset, AM, median abs min', ('where_when', 'onset_clear_hourly_resolution', 'am', 'onset_median_abs_min')), ('Clearance, PM, median abs min', ('where_when', 'onset_clear_hourly_resolution', 'pm', 'clear_median_abs_min')), ('Network curve, peak flow err', ('network_curve', 'peak_flow_err')), ('Network curve, critical k err', ('network_curve', 'critical_k_err'))]
    lines = ['# Real against real, frozen before any run', '', 'Each other normal day scored against the reference day with `metrics.score`. Median, with the worst day in brackets.', '']
    for name, by in res.items():
        for ref_day, tab in by.items():
            lines += [f'## {name}, against {ref_day}', '', '| Check | Median | Worst |', '|---|---:|---:|']
            for label, path in rows:
                v = np.array([pick(t, *path) for t in tab.values()], float)
                if label == 'Total, sites, ratio-1':
                    v = np.abs(v - 1)
                good_high = label in ('Hourly site R2', 'Hourly GEH<5', 'Jam site-hours caught', 'Top bottlenecks shared')
                worst = np.nanmin(v) if good_high and np.isfinite(v).any() else (np.nanmax(np.abs(v)) if np.isfinite(v).any() else np.nan)
                lines.append(f'| {label} | {np.nanmedian(v) if np.isfinite(v).any() else float("nan"):.3f} | {worst:.3f} |')
            lines.append('')
    (OUT / 'floor.md').write_text('\n'.join(lines))
    print('\n'.join(lines[:40]))


if __name__ == '__main__':
    main()
