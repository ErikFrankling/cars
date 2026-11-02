#!/usr/bin/env python3
"""Build reference days from raw city downloads. Run from the repo root with python3 -I.

    reference_day_build.py {berlin,berlin-2019,madrid,madrid-2021,paris,helsinki}

Output per city in datasets/reference-days/<city>/: sites.csv, reference_day.csv,
other_days.csv.gz, noise.json. The reference day is picked from real data alone.
"""
import io
import os
import json
import math
import sys
import tarfile
import zipfile
import glob
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(os.environ.get('RD_ROOT', '/home/erikf/projects/personal/cars-data'))
OUT = ROOT / 'datasets/reference-days'
COMPASS = dict(zip(['Nord', 'Nordost', 'Ost', 'Südost', 'Süd', 'Südwest', 'West', 'Nordwest'], range(0, 360, 45)))
LETTER = {'N': 0, 'E': 90, 'S': 180, 'O': 270}


def geh(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    s = a + b
    return np.sqrt(np.divide(2 * (a - b) ** 2, s, out=np.zeros_like(s), where=s > 0))


def tag_band(sim, real):
    """TAG/FHWA flow bands, real flow first."""
    return np.where(real < 700, abs(sim - real) <= 100, np.where(real <= 2700, abs(sim - real) <= .15 * real, abs(sim - real) <= 400))


def pair_stats(a, b, hours=None, min_flow=50):
    """Report 04's table for two aligned flow arrays, b being the reference."""
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    g = geh(a, b)
    big = b >= min_flow
    pct = 100 * abs(a[big] - b[big]) / b[big]
    return dict(pairs=int(len(a)), median_abs_pct=round(float(np.median(pct)), 2) if len(pct) else None,
                p95_abs_pct=round(float(np.percentile(pct, 95)), 2) if len(pct) else None,
                median_geh=round(float(np.median(g)), 3), p95_geh=round(float(np.percentile(g, 95)), 3),
                share_geh_lt5=round(float((g < 5).mean()), 4), share_geh_lt3=round(float((g < 3).mean()), 4),
                share_tag_band=round(float(tag_band(a, b).mean()), 4))


def qc_sites(d, lanes):
    """Return (clean rows, per-site reasons). Real data only, never the simulator."""
    reasons = {}
    d = d[(d.flow >= 0) | d.flow.isna()].copy()
    dates = d.date.nunique()
    # near-complete days only: at most 6 missing hours
    n = d.dropna(subset=['flow']).groupby(['site', 'date']).hour.nunique()
    full = n[n >= 18].reset_index()[['site', 'date']]
    d = d.merge(full, on=['site', 'date'])
    wide = d.pivot_table(index=['site', 'date'], columns='hour', values='flow', aggfunc='first')
    wide = wide.reindex(columns=range(24))
    med = wide.groupby('site').transform('median')
    total = wide.sum(axis=1)
    med_total = med.sum(axis=1)
    a = wide.to_numpy(float)
    m = med.to_numpy(float)
    ok = np.isfinite(a) & np.isfinite(m)
    a0 = np.where(ok, a, 0.0)
    m0 = np.where(ok, m, 0.0)
    c = ok.sum(1).clip(min=1)
    da = a0 - a0.sum(1, keepdims=True) / c[:, None]
    dm = m0 - m0.sum(1, keepdims=True) / c[:, None]
    da[~ok] = 0
    dm[~ok] = 0
    den = np.sqrt((da ** 2).sum(1) * (dm ** 2).sum(1))
    r = np.divide((da * dm).sum(1), den, out=np.zeros(len(den)), where=den > 0)
    ratio = (total / med_total.replace(0, np.nan)).to_numpy()
    # stuck: six equal non-zero hours in a row
    same = (np.diff(a, axis=1) == 0) & (a[:, :-1] > 0)
    run = np.zeros(len(a), int)
    cur = np.zeros(len(a), int)
    for j in range(same.shape[1]):
        cur = np.where(same[:, j], cur + 1, 0)
        run = np.maximum(run, cur)
    bad_day = (r < .7) | (ratio < .5) | (ratio > 1.5) | (run >= 5) | ~np.isfinite(ratio)
    flags = pd.DataFrame({'bad': bad_day}, index=wide.index).reset_index()
    fault = flags.groupby('site').bad.mean()
    per = flags[~flags.bad].groupby('site').date.nunique()
    for s in d.site.unique():
        if s not in per.index or per[s] < 5:
            reasons[s] = f'too_few_clean_days({int(per.get(s, 0))}/{dates})'
    day = wide.groupby('site').median().sum(axis=1)
    for s, v in day.items():
        if v < 100:
            reasons[s] = reasons.get(s, '') or f'nearly_empty({v:.0f}/day)'
    peak = wide.groupby('site').median().max(axis=1)
    for s, v in peak.items():
        L = lanes.get(s)
        if L and L == L and v / L > 2600:
            reasons[s] = f'implausible_flow({v / L:.0f}/lane/h)'
    keep = flags[~flags.bad][['site', 'date']]
    clean = d.merge(keep, on=['site', 'date'])
    clean = clean[~clean.site.isin(reasons)]
    return clean, reasons, d, fault


def noise(c, ref, cols):
    """Day-to-day floor. Report 04: same site and hour, seven days apart, Tue-Thu, and all days against the reference."""
    out = {}
    w = c.pivot_table(index=['site', 'hour'], columns='date', values='flow', aggfunc='first')
    dates = sorted(w.columns)
    pa, pb, ph = [], [], []
    for d1 in dates:
        d2 = str((pd.Timestamp(d1) + pd.Timedelta(days=7)).date())
        if d2 in w.columns:
            q = w[[d1, d2]].dropna()
            pa.append(q[d1].to_numpy())
            pb.append(q[d2].to_numpy())
            ph.append(q.index.get_level_values('hour').to_numpy())
    if pa:
        a, b, h = map(np.concatenate, (pa, pb, ph))
        out['seven_days_apart_all_hours'] = pair_stats(a, b)
        day = (h >= 7) & (h <= 18)
        out['seven_days_apart_07_18_as_report_04'] = pair_stats(a[day], b[day])
    r = w[ref]
    oa, ob = [], []
    for d in dates:
        if d != ref:
            q = pd.concat([w[d], r], axis=1, keys=['o', 'r']).dropna()
            oa.append(q.o.to_numpy())
            ob.append(q.r.to_numpy())
    out['other_days_vs_reference'] = pair_stats(np.concatenate(oa), np.concatenate(ob))
    by = {}
    for d in dates:
        if d != ref:
            q = pd.concat([w[d], r], axis=1, keys=['o', 'r']).dropna()
            by[d] = pair_stats(q.o.to_numpy(), q.r.to_numpy())
    out['each_other_day_vs_reference'] = by
    for col, name in (('speed', 'kmh'), ('occ', 'pct')):
        if col in cols and c[col].notna().any():
            v = c.pivot_table(index=['site', 'hour'], columns='date', values=col, aggfunc='first')
            rr = v[ref]
            diffs = []
            for d in v.columns:
                if d != ref:
                    diffs.append((v[d] - rr).dropna().to_numpy())
            x = np.abs(np.concatenate(diffs))
            out[f'{col}_other_days_vs_reference'] = dict(pairs=int(len(x)), median_abs=round(float(np.median(x)), 2), p95_abs=round(float(np.percentile(x, 95)), 2), unit=name)
    # network hourly total on a fixed panel of site-hours present on every date
    full = w.dropna()
    tot = full.sum()
    hourly = full.groupby('hour').sum()
    out['fixed_panel'] = dict(site_hours=int(len(full)), sites=int(full.index.get_level_values('site').nunique()), daily_total_by_date={k: float(v) for k, v in tot.items()}, daily_total_cv=round(float(tot.std() / tot.mean()), 4))
    share = hourly / hourly.sum()
    out['hourly_share_spread_rmse_vs_reference'] = {d: round(float(np.sqrt(((share[d] - share[ref]) ** 2).mean())), 5) for d in dates if d != ref}
    out['hourly_total_cv_median'] = round(float((hourly.std(axis=1) / hourly.mean(axis=1)).median()), 4)
    return out


def finish(city, long, sites, normal, meta, pin=None):
    out = OUT / city
    out.mkdir(parents=True, exist_ok=True)
    cols = [c for c in ('speed', 'occ') if c in long]
    long = long[long.date.isin(normal)]
    lanes = sites.set_index('site').lanes.to_dict() if 'lanes' in sites else {}
    clean, reasons, raw, fault = qc_sites(long, lanes)
    if 'qc_prior' in sites:
        for s, why in zip(sites.site, sites.qc_prior):
            if isinstance(why, str) and why:
                reasons.setdefault(s, why)
        clean = clean[~clean.site.isin(reasons)]
    # reference day: the date closest to all the others over the clean panel, with coverage
    w = clean.pivot_table(index=['site', 'hour'], columns='date', values='flow', aggfunc='first')
    med = w.median(axis=1)
    cover = w.notna().mean()
    score = {d: float(np.nanmean(geh(w[d].where(w[d].notna(), med).to_numpy(), med.to_numpy()))) + 5 * (1 - cover[d]) for d in w.columns}
    medoid = min(score, key=score.get)
    ref = pin or medoid
    meta = dict(meta, medoid_date=medoid)
    g = clean.groupby(['site', 'hour'])
    t = pd.DataFrame({'n_days': g.flow.count(), 'flow_median': g.flow.median(), 'flow_sd': g.flow.std(), 'flow_p10': g.flow.quantile(.1), 'flow_p90': g.flow.quantile(.9)})
    for c in cols:
        t[f'{c}_median'] = g[c].median()
        t[f'{c}_sd'] = g[c].std()
    day = clean[clean.date == ref].set_index(['site', 'hour'])[['flow'] + cols]
    t = day.join(t, how='inner').reset_index()
    others = clean[clean.date != ref].copy()
    o = others.pivot_table(index=['site', 'hour'], columns='date', values='flow', aggfunc='first')
    ref_f = t.set_index(['site', 'hour']).flow.reindex(o.index)
    gg = o.apply(lambda col: pd.Series(np.where(col.notna() & ref_f.notna(), geh(col.fillna(0).to_numpy(), ref_f.fillna(0).to_numpy()), np.nan), index=o.index))
    t['geh_noise'] = t.set_index(['site', 'hour']).index.map(gg.median(axis=1).to_dict())
    t = t.sort_values(['site', 'hour'])
    t.to_csv(out / 'reference_day.csv', index=False, float_format='%.3f')
    others[['site', 'date', 'hour', 'flow'] + cols].sort_values(['site', 'date', 'hour']).to_csv(out / 'other_days.csv.gz', index=False, float_format='%.2f')
    sites = sites.copy()
    sites['clean_days'] = sites.site.map(clean.groupby('site').date.nunique()).fillna(0).astype(int)
    on_ref = set(t.site)
    sites['qc'] = [reasons.get(s, 'ok' if s in on_ref else 'not_on_reference_day' if n else 'no_usable_data') for s, n in zip(sites.site, sites.clean_days)]
    sites['fault_day_share'] = sites.site.map(fault).round(3)
    sites['flow_per_day'] = sites.site.map(t.groupby('site').flow.sum()).round(0)
    sites.drop(columns=[c for c in ('qc_prior',) if c in sites]).to_csv(out / 'sites.csv', index=False)
    n = noise(clean, ref, cols)
    rawn = noise(raw[raw.site.isin(set(raw.site) - set(reasons))], ref, cols) if ref in set(raw.date) else {}
    n['same_without_day_filter'] = {k: v for k, v in rawn.items() if k in ('seven_days_apart_07_18_as_report_04', 'other_days_vs_reference')}
    meta = dict(meta, city=city, reference_date=ref, normal_dates=sorted(set(clean.date)), day_scores={k: round(v, 3) for k, v in score.items()}, sites_total=int(sites.site.nunique()), sites_ok=int(t.site.nunique()), site_hours=int(len(t)), qc_counts=sites.qc.str.replace(r'\(.*', '', regex=True).value_counts().to_dict(), noise=n)
    (out / 'noise.json').write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print(city, 'ref', ref, 'sites ok', t.site.nunique(), 'of', sites.site.nunique(), 'site-hours', len(t))
    print(' qc', meta['qc_counts'])
    for k in ('seven_days_apart_07_18_as_report_04', 'other_days_vs_reference'):
        print(' ', k, n.get(k))
    print('  raw', n['same_without_day_filter'].get('seven_days_apart_07_18_as_report_04'))
    for c in cols:
        print(' ', c, n.get(f'{c}_other_days_vs_reference'))
    print('  panel', {k: v for k, v in n['fixed_panel'].items() if k != 'daily_total_by_date'})
    print('  scores', sorted(score.items(), key=lambda x: x[1])[:4])


def berlin_meta():
    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    path = ROOT / 'berlin-detectors/Stammdaten_Verkehrsdetektion_2022_07_20.xlsx'
    with zipfile.ZipFile(path) as z:
        strings = [''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rows = []
        for row in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('m:sheetData/m:row', ns):
            rows.append({c.get('r').rstrip('0123456789'): strings[int(c.find('m:v', ns).text)] if c.get('t') == 's' else c.findtext('m:v', default='', namespaces=ns) for c in row})
    m = pd.DataFrame(rows[1:])
    m = m.rename(columns={'A': 'site', 'B': 'detector', 'F': 'road', 'G': 'from', 'H': 'to', 'I': 'direction', 'J': 'lane_code', 'L': 'lon', 'M': 'lat'})
    return m


def berlin_sites(m):
    g = m.groupby('site')
    r = g.first()
    return pd.DataFrame({'site': r.index, 'lat': r.lat.astype(float).values, 'lon': r.lon.astype(float).values, 'bearing_deg': r.direction.map(COMPASS).values, 'direction': r.direction.values, 'lanes': g.size().values, 'name': (r.road + ' ' + r['from'] + ' > ' + r.to).values, 'road_class': np.where(r.road.str.match(r'^A\d'), 'motorway', 'urban'), 'sensor': 'loop/lane detector'})


def berlin():
    m = berlin_meta()
    lookup = m.set_index('detector').site.to_dict()
    normal = ['2024-09-%02d' % d for d in (3, 4, 5, 10, 11, 12, 17, 18, 19, 24, 25, 26)]
    frames = []
    with tarfile.open(ROOT / 'berlin-detectors/detektoren_2024_09.tgz') as tar:
        for mem in tar:
            stem = Path(mem.name).stem
            if not mem.isfile() or stem not in lookup:
                continue
            d = pd.read_csv(tar.extractfile(mem), sep=';')
            d = d.rename(columns={d.columns[0]: 'date', d.columns[1]: 'hour'})
            d = d[d.date.isin(normal) & (d['Vollständigkeit'] >= 75) & d.qkfz.notna()]
            d = d.assign(site=lookup[stem], det=stem)
            frames.append(d[['site', 'det', 'date', 'hour', 'qkfz', 'vkfz']])
    d = pd.concat(frames)
    d['qv'] = d.qkfz * d.vkfz.where(d.vkfz > 0)
    d['qok'] = d.qkfz.where(d.vkfz > 0)
    a = d.groupby(['site', 'date', 'hour']).agg(flow=('qkfz', 'sum'), n=('det', 'nunique'), qv=('qv', 'sum'), qok=('qok', 'sum')).reset_index()
    counts = m.groupby('site').size()
    a = a[a.n == a.site.map(counts)]
    a['speed'] = a.qv / a.qok.replace(0, np.nan)
    long = a[['site', 'date', 'hour', 'flow', 'speed']]
    s = berlin_sites(m)
    finish('berlin', long, s, normal, dict(source='Digitale Plattform Stadtverkehr Berlin, detektoren_2024_09.tgz', licence='dl-de-by-2.0', flow='qkfz, all motor vehicles, sum of all lanes in a cross-section', speed='vkfz, arithmetic mean at the detector, flow-weighted over lanes (time-mean, point)', hour='local clock hour start', bearing_precision_deg=22.5, real_vkt_km=41.3e6, real_vkt_source='SVZ 2019, working day, Berlin total: 28.72 M km counted network plus 12.6 M km authority estimate on uncounted streets (report 03). Not September 2024.'))


def berlin2019():
    m = berlin_meta()
    d = pd.read_csv(ROOT / 'datasets/berlin-2019-detectors/mq_hr_2019_05.csv.gz', sep=';', encoding='latin1')
    d = d[d.qualitaet >= .75].copy()
    d['date'] = pd.to_datetime(d.tag, format='%d.%m.%Y').dt.strftime('%Y-%m-%d')
    # Tue-Thu, without the days beside 1 May and Ascension (30 May)
    normal = ['2019-05-%02d' % x for x in (7, 8, 9, 14, 15, 16, 21, 22, 23, 28)]
    long = pd.DataFrame({'site': d.mq_name, 'date': d.date, 'hour': d.stunde, 'flow': d.q_kfz_mq_hr.astype(float), 'speed': d.v_kfz_mq_hr.where(d.v_kfz_mq_hr > 0).astype(float)})
    s = berlin_sites(m)
    hold = json.load(open(ROOT / 'datasets/berlin-2019-detectors/holdout_match.json'))
    s['matsim_count_station_m'] = s.site.map({x[0]: x[3] for x in hold})
    finish('berlin-2019', long, s, normal, dict(source='Digitale Plattform Stadtverkehr Berlin, mq_hr_2019_05.csv.gz, old quality control', licence='dl-de-by-2.0', flow='q_kfz_mq_hr, all motor vehicles, cross-section', speed='v_kfz_mq_hr, cross-section mean (time-mean, point)', hour='local clock hour start', bearing_precision_deg=22.5, real_vkt_km=41.3e6, real_vkt_source='SVZ 2019, working day, Berlin total: 28.72 M km counted network plus 12.6 M km authority estimate on uncounted streets (report 03).', pinned_by='report 12: same months as MeTS-10 Berlin'), pin='2019-05-15')


def madrid():
    madrid_month('madrid', OUT / 'madrid/raw/hist_161.zip', ['2026-09-%02d' % d for d in (15, 16, 17, 22, 23, 24, 29, 30)], 'September 2026')


def madrid2021():
    # 12 October is a national holiday, so the 11th to 14th are out
    madrid_month('madrid-2021', OUT / 'madrid-2021/raw/hist_oct2021.zip', ['2021-10-%02d' % d for d in (5, 6, 7, 19, 20, 21, 26, 27, 28)], 'October 2021')


def madrid_month(city, archive, normal, label):
    raw = OUT / 'madrid/raw'
    keys = tuple(('"%s ' % d).encode() for d in normal)
    names = ['id', 'fecha', 'tipo', 'q', 'o', 'carga', 'v', 'err', 'per']
    frames = []

    def flush(lines):
        c = pd.read_csv(io.BytesIO(b''.join(lines)), sep=';', header=None, names=names, usecols=['id', 'fecha', 'q', 'o', 'v', 'err'], quotechar='"')
        c = c[c.err.fillna('N') == 'N']
        c = c.assign(date=c.fecha.str[:10], hour=c.fecha.str[11:13].astype(int), q=pd.to_numeric(c.q, errors='coerce'), o=pd.to_numeric(c.o, errors='coerce'), v=pd.to_numeric(c.v, errors='coerce'))
        c = c[c.q >= 0]
        c['qv'] = c.q * c.v.where(c.v > 0)
        c['qok'] = c.q.where(c.v > 0)
        c['ook'] = c.o.where(c.o >= 0)
        frames.append(c.groupby(['id', 'date', 'hour']).agg(q=('q', 'sum'), n=('q', 'size'), qv=('qv', 'sum'), qok=('qok', 'sum'), o=('ook', 'mean')).reset_index())

    with zipfile.ZipFile(archive) as z, z.open(z.namelist()[0]) as f:
        buf = []
        for line in f:
            if line[line.find(b';') + 1:line.find(b';') + 13].startswith(keys):
                buf.append(line)
                if len(buf) >= 800000:
                    flush(buf)
                    buf = []
        if buf:
            flush(buf)
    d = pd.concat(frames)
    d = d.groupby(['id', 'date', 'hour']).agg(q=('q', 'sum'), n=('n', 'sum'), qv=('qv', 'sum'), qok=('qok', 'sum'), o=('o', 'mean')).reset_index()
    d = d[d.n == 4]
    # official schema: intensidad is veh/h over a 15 min period
    d['flow'] = d.q / 4
    d['speed'] = d.qv / d.qok.replace(0, np.nan)
    d['occ'] = d.o
    d = d.rename(columns={'id': 'site'})
    long = d[['site', 'date', 'hour', 'flow', 'speed', 'occ']]
    loc = pd.read_csv(raw / 'loc_306.csv', sep=';', encoding='latin1', quotechar='"')
    bearings = []
    labels = []
    prior = []
    import re
    for n, tipo in zip(loc.nombre.fillna(''), loc.tipo_elem):
        m = re.search(r'\b([NSEO])-([NSEO])\b', n)
        if m and m.group(1) != m.group(2):
            a, b = LETTER[m.group(1)], LETTER[m.group(2)]
            bearings.append(float(b if abs(a - b) == 180 else np.nan))
            labels.append(m.group(0))
        else:
            bearings.append(np.nan)
            labels.append('')
        why = ''
        up = n.upper()
        if 'GIRO' in up:
            why = 'turning_movement_only'
        elif 'TACTICO' in up or 'TÁCTICO' in up:
            why = 'tactical_detector'
        elif tipo == 'other':
            why = 'other_type'
        prior.append(why)
    s = pd.DataFrame({'site': loc.id, 'lat': loc.latitud, 'lon': loc.longitud, 'bearing_deg': bearings, 'direction': labels, 'lanes': np.nan, 'name': loc.nombre, 'road_class': loc.tipo_elem, 'sensor': 'loop', 'qc_prior': prior})
    s = s.drop_duplicates('site')
    finish(city, long, s, normal, dict(source=f'datos.madrid.es dataset 208627, {label} archive; locations 202468 latest', licence='CC BY 4.0', flow='intensidad, veh/h over 15 min, averaged to hourly count', speed='vmed, M30/C30 only, flow-weighted', occ='ocupacion %, mean of 15 min', hour='local clock hour start', bearing_precision_deg=45))


def paris():
    raw = OUT / 'paris/raw'
    normal = ['2026-09-15', '2026-09-16', '2026-09-17', '2026-09-22', '2026-09-23', '2026-09-24', '2026-09-29', '2026-09-30', '2026-10-01', '2026-10-06', '2026-10-07', '2026-10-08', '2026-10-13', '2026-10-14', '2026-10-15']
    frames = []
    for f in sorted(glob.glob(str(raw / 'q_*.csv.gz'))):
        d = pd.read_csv(f, sep=';', encoding='utf-8-sig')
        frames.append(d)
    d = pd.concat(frames).drop_duplicates(['iu_ac', 't_1h'])
    d['ts'] = pd.to_datetime(d.t_1h.str[:19])
    # the portal labels each hour by its end (checked on the night minimum, see README)
    d['start'] = d.ts - pd.Timedelta(hours=1)
    d['date'] = d.start.dt.strftime('%Y-%m-%d')
    d['hour'] = d.start.dt.hour
    d = d[d.etat_barre.eq('Ouvert') & d.q.notna()]
    d = d.rename(columns={'iu_ac': 'site', 'q': 'flow', 'k': 'occ'})
    long = d[['site', 'date', 'hour', 'flow', 'occ']]
    a = pd.read_csv(raw / 'arcs_all_fields.csv', sep=';', encoding='utf-8-sig').drop_duplicates('iu_ac')
    rows = []
    for r in a.itertuples():
        if not isinstance(r.geo_point_2d, str) or not isinstance(r.geo_shape, str):
            continue
        lat, lon = map(float, r.geo_point_2d.split(','))
        c = json.loads(r.geo_shape)
        c = c['coordinates'] if 'coordinates' in c else c['geometry']['coordinates']
        (x0, y0), (x1, y1) = c[0], c[-1]
        b = math.degrees(math.atan2((x1 - x0) * math.cos(math.radians(y0)), y1 - y0)) % 360
        rows.append(dict(site=r.iu_ac, lat=lat, lon=lon, bearing_deg=round(b, 1), direction='geometry', lanes=np.nan, name=f'{r.libelle} {r.libelle_nd_amont} > {r.libelle_nd_aval}', road_class='urban', sensor='loop', node_up=r.iu_nd_amont, node_down=r.iu_nd_aval, x0=x0, y0=y0, x1=x1, y1=y1))
    s = pd.DataFrame(rows)
    finish('paris', long, s, normal, dict(source='opendata.paris.fr comptages-routiers-permanents', licence='ODbL', flow='q, veh/h', occ='k, taux occupation %', hour='local clock hour start, shifted from end label', bearing_precision_deg=10))


def helsinki():
    raw = OUT / 'helsinki/raw'
    normal = ['2026-09-15', '2026-09-16', '2026-09-17', '2026-09-22', '2026-09-23', '2026-09-24', '2026-09-29', '2026-09-30', '2026-10-01', '2026-10-06', '2026-10-07', '2026-10-08']
    frames = [pd.read_csv(f) for f in glob.glob(str(raw / 'agg/*.csv'))]
    a = pd.concat(frames)
    a['date'] = a.date.astype(str)
    a = a[a.date.isin(normal)]
    g = a.groupby(['station', 'dir', 'date', 'hour']).agg(n=('n', 'sum'), ss=('sum_speed', 'sum'), si=('sum_inv_speed', 'sum'), heavy=('heavy', 'sum')).reset_index()
    g['site'] = g.station.astype(str) + '_' + g.dir.astype(str)
    g['flow'] = g.n.astype(float)
    g['speed'] = g.ss / g.n
    g['speed_harmonic'] = g.n / g.si
    long = g[['site', 'date', 'hour', 'flow', 'speed']]
    metas = json.load(open(raw / 'stations_helsinki.json'))
    lanes = a.groupby(['station', 'dir']).lane.nunique()
    rows = []
    for m in metas:
        p = m['properties']
        lon, lat = m['geometry']['coordinates'][:2]
        for di in (1, 2):
            b = p.get('bearing')
            b = float(b) if di == 1 and b is not None else ((float(b) + 180) % 360 if b is not None else np.nan)
            ff = p.get(f'freeFlowSpeed{di}')
            rows.append(dict(site=f"{p['tmsNumber']}_{di}", lat=lat, lon=lon, bearing_deg=b, direction=f"to {p.get(f'direction{di}Municipality')}", lanes=lanes.get((p['tmsNumber'], di), np.nan), name=p['names'].get('en', p['name']), road_class=f"road {p['roadAddress']['roadNumber']}", sensor=p.get('stationType') or 'TMS loop', free_flow_kmh=ff))
    s = pd.DataFrame(rows)
    finish('helsinki', long, s, normal, dict(source='Fintraffic Digitraffic lamraw raw vehicle records, aggregated', licence='CC BY 4.0', flow='vehicles with faulty=0, sum of all lanes per direction', speed='arithmetic mean of individual vehicle speeds at the station (time-mean, point)', hour='local clock hour start', bearing_precision_deg=10))


if __name__ == '__main__':
    {'berlin': berlin, 'berlin-2019': berlin2019, 'madrid': madrid, 'madrid-2021': madrid2021, 'paris': paris, 'helsinki': helsinki}[sys.argv[1]]()
