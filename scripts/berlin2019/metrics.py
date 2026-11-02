"""Recipe step 1: the metric code, frozen before any simulated day exists.

One function, score(), compares a candidate day with a reference day in the same form:
columns site, hour, flow, speed. It is run real against real to get the floor and sim against real
for a result, with no difference between the two calls. Report 15's acceptance table names the checks.
"""
import numpy as np
import pandas as pd

HOURS_DAY = range(7, 19)
JAM_FRACTION = 0.7
TOP_N = 20
ARTERIAL = ('primary', 'secondary', 'tertiary', 'trunk', 'unclassified', 'residential', 'living_street')
MOTORWAY = ('motorway',)


def _geh(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    s = a + b
    return np.sqrt(np.divide(2 * (a - b) ** 2, s, out=np.zeros_like(s), where=s > 0))


def flow_fit(a, b):
    """a plays the model, b the observation. Same formulas as report 15's table."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or b.sum() == 0:
        return dict(n=int(len(a)))
    r = np.corrcoef(a, b)[0, 1] if a.std() > 0 else 0.0
    g = _geh(a, b)
    return dict(n=int(len(a)), rmsn=float(np.sqrt(np.mean((a - b) ** 2)) / b.mean()), wape=float(np.abs(a - b).sum() / b.sum()), r2=float(r * r), slope=float(np.polyfit(b, a, 1)[0]), bias=float(a.sum() / b.sum() - 1), geh_lt5=float((g < 5).mean()), geh_lt3=float((g < 3).mean()), median_geh=float(np.median(g)))


def free_speed(d):
    """A site's free speed: its 90th percentile hour, from the reference alone."""
    return d.dropna(subset=['speed']).groupby('site').speed.quantile(.9)


def jam_flags(d, free, min_flow=50):
    f = d.site.map(free)
    return (d.speed < JAM_FRACTION * f) & (d.flow >= min_flow) & d.speed.notna()


def peak(tot, lo, hi):
    w = tot[(tot.index >= lo) & (tot.index <= hi)]
    return int(w.idxmax()) if len(w) and w.max() > 0 else None


def onset_clear(flags):
    """First and last congested hour per site and period, from a boolean series indexed by (site, hour)."""
    rows = {}
    q = flags[flags].reset_index()
    for label, lo, hi in (('am', 5, 11), ('pm', 12, 21)):
        g = q[q.hour.between(lo, hi)].groupby('site').hour
        rows[label] = pd.DataFrame({'on': g.min(), 'off': g.max() + 1})
    return rows


def score(cand, ref, classes):
    """cand and ref: site, hour, flow, speed. classes: site -> road class. Only site-hours in both count."""
    keys = ['site', 'hour']
    j = ref.rename(columns={'flow': 'flow_r', 'speed': 'speed_r'}).merge(cand.rename(columns={'flow': 'flow_c', 'speed': 'speed_c'}), on=keys)
    j = j.dropna(subset=['flow_r', 'flow_c'])
    out = dict(sites=int(j.site.nunique()), site_hours=int(len(j)))

    # day shape, network of sites with all 24 hours in both
    full = j.groupby('site').hour.nunique()
    full = j[j.site.isin(full[full == 24].index)]
    if len(full):
        tr, tc = full.groupby('hour').flow_r.sum(), full.groupby('hour').flow_c.sum()
        sr, sc = tr / tr.sum(), tc / tc.sum()
        out['day_shape'] = dict(sites=int(full.site.nunique()), mean_abs_share_points=float(100 * (sr - sc).abs().mean()), peak_am_ref=peak(tr, 5, 11), peak_am_cand=peak(tc, 5, 11), peak_pm_ref=peak(tr, 12, 20), peak_pm_cand=peak(tc, 12, 20), night_share_ref=float(sr[sr.index < 5].sum()), night_share_cand=float(sc[sc.index < 5].sum()), total_ratio=float(tc.sum() / tr.sum()))

    # volume
    day = j[j.hour.isin(HOURS_DAY)]
    out['volume_07_18'] = flow_fit(day.flow_c, day.flow_r)
    out['volume_all_hours'] = flow_fit(j.flow_c, j.flow_r)
    d = full.groupby('site')[['flow_c', 'flow_r']].sum() if len(full) else None
    out['volume_daily'] = flow_fit(d.flow_c, d.flow_r) if d is not None and len(d) else {}
    by = {}
    cl = j.site.map(classes).fillna('unknown')
    for c, g in day.groupby(cl.loc[day.index]):
        by[c] = flow_fit(g.flow_c, g.flow_r)
    out['volume_by_class'] = by

    # speed by class and hour; flow-weighted harmonic at network level is not used: sites are sensors
    v = j.dropna(subset=['speed_r', 'speed_c'])
    v = v[(v.flow_r >= 10) & (v.flow_c >= 10)]
    if len(v):
        rows = []
        cl = v.site.map(classes).fillna('unknown')
        for c, g in v.groupby(cl):
            gt = g.groupby('hour').apply(lambda x: pd.Series(dict(r=np.average(x.speed_r, weights=x.flow_r), c=np.average(x.speed_c, weights=x.flow_c))), include_groups=False)
            rows.append(dict(road_class=c, sites=int(g.site.nunique()), mean_abs_pct_by_hour=float(100 * ((gt.c - gt.r).abs() / gt.r).mean()), worst_hour_pct=float(100 * ((gt.c - gt.r).abs() / gt.r).max()), by_hour={int(h): (round(float(x.r), 1), round(float(x.c), 1)) for h, x in gt.iterrows()}))
        out['speed_by_class'] = rows
        out['speed_site_median_abs_kmh'] = float((v.speed_c - v.speed_r).abs().median())
        out['speed_bias_kmh'] = float((v.speed_c - v.speed_r).mean())
        r2 = {}
        for s, g in v.groupby('site'):
            if len(g) >= 12 and g.speed_r.std() > 0 and g.speed_c.std() > 0:
                r2[s] = float(np.corrcoef(g.speed_r, g.speed_c)[0, 1] ** 2)
        s = pd.Series(r2)
        cs = s.index.map(classes).fillna('unknown') if len(s) else []
        out['speed_r2_gt04_share'] = {c: float((g > .4).mean()) for c, g in s.groupby(cs)} if len(s) else {}

    # where and when
    free = free_speed(ref)
    fr = jam_flags(j.rename(columns={'flow_r': 'flow', 'speed_r': 'speed'}), free)
    fc = jam_flags(j.rename(columns={'flow_c': 'flow', 'speed_c': 'speed'}), free)
    tp = int((fr & fc).sum())
    out['where_when'] = dict(ref_jam_site_hours=int(fr.sum()), cand_jam_site_hours=int(fc.sum()), caught=float(tp / fr.sum()) if fr.sum() else None, false_alarm=float(1 - tp / fc.sum()) if fc.sum() else None)
    ni = j.set_index(keys)
    fri = pd.Series(fr.values, index=ni.index)
    fci = pd.Series(fc.values, index=ni.index)
    tr = fri.groupby('site').sum().sort_values(ascending=False)
    tc = fci.groupby('site').sum().sort_values(ascending=False)
    n = min(TOP_N, int((tr > 0).sum()))
    if n:
        out['where_when']['top_bottlenecks'] = dict(n=n, shared=float(len(set(tr.index[:n]) & set(tc[tc > 0].index[:n])) / n))
    oc_r, oc_c = onset_clear(fri), onset_clear(fci)
    err = {}
    for p in ('am', 'pm'):
        k = oc_r[p].join(oc_c[p], lsuffix='_r', rsuffix='_c', how='inner')
        err[p] = dict(sites=int(len(k)), onset_median_abs_min=float(60 * (k.on_r - k.on_c).abs().median()) if len(k) else None, clear_median_abs_min=float(60 * (k.off_r - k.off_c).abs().median()) if len(k) else None)
    out['where_when']['onset_clear_hourly_resolution'] = err

    # network curve at the sensors
    w = j.dropna(subset=['speed_r', 'speed_c'])
    w = w[(w.speed_r > 0) & (w.speed_c > 0)]
    if len(w):
        cr = pd.DataFrame({'q': w.flow_r, 'k': w.flow_r / w.speed_r, 'hour': w.hour}).groupby('hour').mean()
        cc = pd.DataFrame({'q': w.flow_c, 'k': w.flow_c / w.speed_c, 'hour': w.hour}).groupby('hour').mean()
        pr, pc = cr.q.idxmax(), cc.q.idxmax()
        out['network_curve'] = dict(peak_flow_ref=float(cr.q.max()), peak_flow_cand=float(cc.q.max()), peak_flow_err=float(cc.q.max() / cr.q.max() - 1), critical_k_ref=float(cr.k[pr]), critical_k_cand=float(cc.k[pc]), critical_k_err=float(cc.k[pc] / cr.k[pr] - 1), k_nrmse=float(np.sqrt(((cc.k - cr.k) ** 2).mean()) / cr.k.mean()))
    return out
