#!/usr/bin/env python3
"""Compare a `cars run --edge-csv` day with a real measured reference day.

    nix develop --command python3 -I scripts/reference_day.py \
        --ref .../reference-days/berlin --net .../berlin.net.xml \
        --edges runs/berlin/day_edges.csv --summary runs/berlin/day_summary.csv --out /tmp/out

Prints the VALIDATION-GATE checks. The bar for each is a real day: the simulation must be at
least as close to the reference day as the least similar other normal weekday, on the same sites
and hours. Sites are matched to edges from real data and the net only, never from the simulated
flows, and a match that cannot be trusted is dropped and counted. See research/truth/data-hunt/17.
"""
import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from lxml import etree
from pyproj import Transformer
from scipy.spatial import cKDTree

EFFECTIVE_LENGTH_M = 6.0
MAX_ANGLE = 45.0


def geh(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    s = a + b
    return np.sqrt(np.divide(2 * (a - b) ** 2, s, out=np.zeros_like(s), where=s > 0))


def read_net(path, cache=None):
    if cache and cache.exists() and cache.stat().st_mtime > path.stat().st_mtime:
        return pickle.loads(cache.read_bytes())
    location, edges = None, []
    for _, e in etree.iterparse(str(path), events=('end',), tag=('location', 'edge'), resolve_entities=False, no_network=True):
        if e.tag == 'location':
            location = dict(e.attrib)
        elif e.get('function') != 'internal' and not e.get('id', '').startswith(':'):
            lanes = [l for l in e.findall('lane') if 'passenger' not in l.get('disallow', '').split() and (not l.get('allow') or {'passenger', 'all'} & set(l.get('allow').split()))]
            if lanes:
                shape = np.array([list(map(float, p.split(',')))[:2] for p in lanes[0].get('shape').split()])
                edges.append(dict(id=e.get('id'), lanes=len(lanes), length=float(lanes[0].get('length')), limit_kmh=float(lanes[0].get('speed')) * 3.6, type=e.get('type', ''), start=e.get('from'), end=e.get('to'), shape=shape))
        e.clear()
        while e.getprevious() is not None:
            del e.getparent()[0]
    if cache:
        cache.write_bytes(pickle.dumps((location, edges)))
    return location, edges


def match_sites(sites, location, edges, ref, a):
    transform = Transformer.from_crs('EPSG:4326', location['projParameter'], always_xy=True)
    offset = np.array(list(map(float, location['netOffset'].split(','))))
    starts, ends, ids = [], [], []
    for i, e in enumerate(edges):
        s = e['shape']
        for p, q in zip(s[:-1], s[1:]):
            n = max(1, int(np.ceil(np.linalg.norm(q - p) / 20)))
            for j in range(n):
                starts.append(p + (q - p) * j / n)
                ends.append(p + (q - p) * (j + 1) / n)
                ids.append(i)
    starts, ends = np.array(starts), np.array(ends)
    delta = ends - starts
    tree = cKDTree((starts + ends) / 2)
    bbox = (starts.min(0), starts.max(0))
    real = ref.groupby('site').agg(peak=('flow', 'max'))
    has_speed = 'speed' in ref and ref.speed.notna().any()
    if has_speed:
        real['free'] = ref.groupby('site').speed.quantile(.9)
    rows = []
    for r in sites.itertuples():
        xy = np.array(transform.transform(r.lon, r.lat)) + offset
        row = dict(site=r.site, x=xy[0], y=xy[1], edge='', quality='bad', why='outside_net')
        if not (bbox[0][0] <= xy[0] <= bbox[1][0] and bbox[0][1] <= xy[1] <= bbox[1][1]):
            rows.append(row)
            continue
        cands = {}
        known = r.bearing_deg == r.bearing_deg
        lanes = getattr(r, 'lanes', float('nan'))
        for j in tree.query_ball_point(xy, a.max_dist + 15):
            v = delta[j]
            pt = starts[j] + v * np.clip(np.dot(xy - starts[j], v) / max(np.dot(v, v), 1e-12), 0, 1)
            dist = float(np.linalg.norm(pt - xy))
            angle = abs((np.degrees(np.arctan2(v[0], v[1])) % 360 - r.bearing_deg + 180) % 360 - 180) if known else 0.0
            e = edges[ids[j]]
            miss = abs(e['lanes'] - lanes) if lanes == lanes else 0
            score = dist + angle * .5 + miss * 20
            k = ids[j]
            if k not in cands or score < cands[k][0]:
                cands[k] = (score, dist, angle, miss)
        ranked = sorted(cands.items(), key=lambda x: x[1][0])
        if not ranked:
            row['why'] = 'no_edge_within_distance'
            rows.append(row)
            continue
        k, (score, dist, angle, miss) = ranked[0]
        e = edges[k]
        margin = ranked[1][1][0] - score if len(ranked) > 1 else 999.0
        reverse = len(ranked) > 1 and edges[ranked[1][0]]['start'] == e['end'] and edges[ranked[1][0]]['end'] == e['start']
        row.update(edge=e['id'], distance_m=round(dist, 1), bearing_error_deg=round(angle, 1), edge_lanes=e['lanes'], site_lanes=lanes, score_margin=round(margin, 1), limit_kmh=round(e['limit_kmh']), edge_type=e['type'], edge_length_m=round(e['length'], 1))
        hard, soft = [], []
        if dist > a.max_dist:
            hard.append('too_far')
        if known and angle > MAX_ANGLE:
            hard.append('wrong_direction')
        if not known and reverse:
            hard.append('no_direction_on_two_way_road')
        elif not known:
            soft.append('no_direction')
        if dist > 25:
            soft.append('distance_over_25m')
        if miss:
            soft.append(f'lanes_{lanes:.0f}_vs_edge_{e["lanes"]}')
        if margin < 10:
            soft.append('close_runner_up')
        if r.site in real.index:
            v = real.loc[r.site]
            if v.peak / e['lanes'] > 2600:
                hard.append(f'real_peak_{v.peak / e["lanes"]:.0f}_per_lane_impossible_on_this_edge')
            if has_speed and v.free == v.free:
                if v.free > 1.3 * e['limit_kmh'] + 10:
                    soft.append(f'real_free_speed_{v.free:.0f}_over_limit_{e["limit_kmh"]:.0f}')
                elif v.free < .4 * e['limit_kmh']:
                    soft.append(f'real_free_speed_{v.free:.0f}_far_under_limit_{e["limit_kmh"]:.0f}')
        rc = str(getattr(r, 'road_class', ''))
        fast = any(w in e['type'] for w in ('motorway', 'trunk'))
        if rc == 'motorway' and e['type'] and not fast:
            soft.append('motorway_site_on_non_motorway_edge')
        if rc == 'urban' and 'motorway' in e['type']:
            soft.append('urban_site_on_motorway_edge')
        row['quality'] = 'bad' if hard else 'weak' if soft else 'good'
        row['why'] = ';'.join(hard + soft)
        rows.append(row)
    m = pd.DataFrame(rows)
    live = m.quality.isin(['good', 'weak'])
    dup = live & m[live].edge.duplicated(keep=False).reindex(m.index, fill_value=False)
    m.loc[dup & m.quality.eq('good'), 'quality'] = 'weak'
    m.loc[dup, 'why'] = m.loc[dup, 'why'].fillna('').astype(str) + ';shared_edge'
    return m


def read_edges(path, want):
    rows, totals = [], dict(distance_km=0.0, teleports=0.0, entered=0.0)
    hours, night = set(), []
    for c in pd.read_csv(path, chunksize=500000, dtype={'edge': str}):
        totals['distance_km'] += c.distance.sum() / 1000
        totals['teleports'] += c.teleports.sum()
        totals['entered'] += c.entered.sum()
        c['hour'] = (c.begin // 3600).astype(int)
        hours.update(c.hour.unique().tolist())
        q = c[c.hour.isin([2, 3, 4])]
        night.append(q.groupby('edge').agg(samples=('samples', 'sum'), distance=('distance', 'sum')))
        rows.append(c[c.edge.isin(want)].groupby(['edge', 'hour'], as_index=False).agg(samples=('samples', 'sum'), distance=('distance', 'sum'), entered=('entered', 'sum')))
    d = pd.concat(rows).groupby(['edge', 'hour'], as_index=False).sum()
    n = pd.concat(night).groupby(level=0).sum()
    stuck = n[(n.samples > 3 * 3600) & (n.distance / n.samples.replace(0, np.nan) < 5 / 3.6)]
    totals['hours'] = sorted(hours)
    totals['night_stuck_edges'] = int(len(stuck))
    return d, totals


def flow_metrics(s, r):
    ok = np.isfinite(s) & np.isfinite(r)
    s, r = s[ok], r[ok]
    g = geh(s, r)
    big = r >= 50
    den = ((r - r.mean()) ** 2).sum()
    return dict(n=int(len(s)), median_geh=float(np.median(g)), geh_lt5=float((g < 5).mean()), geh_lt3=float((g < 3).mean()), median_abs_pct=float(np.median(100 * abs(s[big] - r[big]) / r[big])) if big.any() else np.nan, ratio=float(s.sum() / r.sum()) if r.sum() else np.nan, r2=float(1 - ((s - r) ** 2).sum() / den) if den else np.nan, rmsn=float(np.sqrt(((s - r) ** 2).mean()) / r.mean()) if r.sum() else np.nan, wape=float(abs(s - r).sum() / r.sum()) if r.sum() else np.nan, slope=float(np.dot(r, s) / np.dot(r, r)) if r.sum() else np.nan)


def shape_metrics(t, sim, real):
    """t: site, hour, columns. Sites with all 24 hours in both only. Shares of the day per hour."""
    q = t.dropna(subset=[sim, real])
    n = q.groupby('site').hour.transform('nunique')
    q = q[n == 24]
    if q.empty:
        return None
    a, b = q.groupby('hour')[sim].sum(), q.groupby('hour')[real].sum()
    sa, sb = a / a.sum(), b / b.sum()
    peak = lambda s, lo, hi: int(s.loc[lo:hi].idxmax())
    return dict(sites=int(q.site.nunique()), mae_share=float((sa - sb).abs().mean()), rmse_share=float(np.sqrt(((sa - sb) ** 2).mean())), r=float(np.corrcoef(a, b)[0, 1]), am_sim=peak(sa, 5, 10), am_real=peak(sb, 5, 10), pm_sim=peak(sa, 14, 20), pm_real=peak(sb, 14, 20), night_sim=float(sa.loc[0:4].sum()), night_real=float(sb.loc[0:4].sum()), peak_sim=int(sa.idxmax()), peak_real=int(sb.idxmax()))


def jam_flags(t, col, kind):
    if kind == 'speed':
        free = t.groupby('site')[col].transform(lambda x: x.quantile(.9))
        return (t[col] < .7 * free) & t[col].notna()
    return (t[col] >= 15) & t[col].notna()


def f1(a, b):
    tp = (a & b).sum()
    p, r = tp / max(a.sum(), 1), tp / max(b.sum(), 1)
    return float(2 * p * r / (p + r)) if p + r else 0.0


def verdict(ok):
    return 'PASS' if ok else 'FAIL'


def tier(good, credible):
    """Report 15's bands, its own proposals; the real-day floor stays the binding bar."""
    return ' [report 15: good]' if good else ' [report 15: credible]' if credible else ' [report 15: below credible]'


def evaluate(t, others, out, a, meta, totals, summary):
    """t holds real flow/speed/occ and sim flow/speed/occ per site and hour for trusted sites."""
    lines, res = [], {}
    days = sorted(others.date.unique())
    keys = ['site', 'hour']
    has_speed = t.speed.notna().any() if 'speed' in t else False
    has_occ = t.occ.notna().any() if 'occ' in t else False
    wide = {}
    for d in days:
        o = others[others.date == d]
        wide[d] = t[keys + ['flow'] + [c for c in ('speed', 'occ') if c in t]].merge(o[keys + ['flow'] + [c for c in ('speed', 'occ') if c in o]], on=keys, suffixes=('', '_o'))

    # 1 nothing stuck
    tele = totals['teleports']
    run_end = summary.running.iloc[-1] if summary is not None else None
    run_max = summary.running.max() if summary is not None else None
    stuck_ok = tele == 0 and totals['night_stuck_edges'] == 0 and (run_end is None or run_end < .25 * run_max)
    res['nothing_stuck'] = dict(teleports=tele, night_stuck_edges=totals['night_stuck_edges'], running_end=run_end, running_max=run_max, verdict=verdict(stuck_ok))
    lines.append(('Nothing stuck', verdict(stuck_ok), f'teleports {tele:.0f}; edges still crawling at 02-05h {totals["night_stuck_edges"]}' + (f'; running at end {run_end:.0f} of peak {run_max:.0f}; teleports are {100 * tele / summary.inserted.iloc[-1]:.2f}% of trips. Only a run with teleports off can pass' if run_end is not None else '; no --summary, end state unknown')))

    # 2 day shape
    sh = shape_metrics(t, 'sim', 'flow')
    if sh:
        no = [shape_metrics(w, 'flow_o', 'flow') for w in wide.values()]
        no = [x for x in no if x]
        worst = max(x['rmse_share'] for x in no)
        peak_ok = abs(sh['am_sim'] - sh['am_real']) <= max(max(abs(x['am_sim'] - x['am_real']) for x in no), 1) and abs(sh['pm_sim'] - sh['pm_real']) <= max(max(abs(x['pm_sim'] - x['pm_real']) for x in no), 1)
        ok = sh['rmse_share'] <= worst and peak_ok
        res['day_shape'] = dict(sim=sh, noise_rmse_worst=worst, noise_rmse_median=float(np.median([x['rmse_share'] for x in no])), verdict=verdict(ok))
        lines.append(('Day shape', verdict(ok), f"{sh['sites']} sites with 24 h: hourly-share RMSE {100 * sh['rmse_share']:.2f} pts vs real-day worst {100 * worst:.2f}; r {sh['r']:.3f}; AM peak {sh['am_sim']:02}h vs {sh['am_real']:02}h, PM {sh['pm_sim']:02}h vs {sh['pm_real']:02}h; night share {100 * sh['night_sim']:.1f}% vs {100 * sh['night_real']:.1f}%; mean hourly-share gap {100 * sh['mae_share']:.2f} pts" + tier(sh['mae_share'] <= .003 and sh['am_sim'] == sh['am_real'] and sh['pm_sim'] == sh['pm_real'], sh['mae_share'] <= .005 and abs(sh['am_sim'] - sh['am_real']) <= 1 and abs(sh['pm_sim'] - sh['pm_real']) <= 1)))
        lag = {}
        q = t.dropna(subset=['sim', 'flow'])
        x, y = q.groupby('hour').sim.sum(), q.groupby('hour').flow.sum()
        for s in range(-3, 4):
            lag[s] = float(np.corrcoef(x.reindex(range(24)).fillna(0).shift(s).fillna(0), y.reindex(range(24)).fillna(0))[0, 1])
        res['day_shape']['clock_lag_r'] = lag
        best = max(lag, key=lag.get)
        if best != 0:
            lines.append(('', 'WARN', f'simulated hours fit best shifted by {best} h: check the clock before reading anything else'))
    else:
        lines.append(('Day shape', 'NOT TESTED', 'no site has all 24 hours'))

    # 3 volume
    fm = flow_metrics(t.sim.to_numpy(float), t.flow.to_numpy(float))
    fn = {d: flow_metrics(w.flow_o.to_numpy(float), w.flow.to_numpy(float)) for d, w in wide.items()}
    worst_geh = max(x['median_geh'] for x in fn.values())
    worst5 = min(x['geh_lt5'] for x in fn.values())
    rlo, rhi = min(x['ratio'] for x in fn.values()), max(x['ratio'] for x in fn.values())
    ok = fm['median_geh'] <= worst_geh and fm['geh_lt5'] >= worst5 and rlo <= fm['ratio'] <= rhi
    gate04 = fm['median_geh'] <= 2 and fm['geh_lt5'] >= .85 and fm['geh_lt3'] >= .7
    res['volume'] = dict(sim=fm, noise_by_day=fn, gate_04=gate04, verdict=verdict(ok))
    lines.append(('Volume, site by site', verdict(ok), f"{t.site.nunique()} sites, {fm['n']} site-hours: median GEH {fm['median_geh']:.2f} vs real-day worst {worst_geh:.2f}; GEH<5 {100 * fm['geh_lt5']:.1f}% vs {100 * worst5:.1f}%; median diff {fm['median_abs_pct']:.1f}%; sim/real total {fm['ratio']:.3f} vs real-day range {rlo:.3f}-{rhi:.3f}; report 04 gate {'met' if gate04 else 'not met'}; RMSN {fm['rmsn']:.2f}, WAPE {100 * fm['wape']:.0f}%, R2 {fm['r2']:.2f}, slope {fm['slope']:.2f}" + tier(fm['rmsn'] <= .3 and fm['r2'] >= .85 and .9 <= fm['slope'] <= 1.1 and fm['geh_lt5'] >= .75 and fm['wape'] <= .2, fm['rmsn'] <= .4 and fm['r2'] >= .75 and .85 <= fm['slope'] <= 1.15 and fm['geh_lt5'] >= .6 and fm['wape'] <= .35)))
    vkt = totals['distance_km']
    target = a.real_vkt_km or meta.get('real_vkt_km')
    if a.as_sim_day:
        lines.append(('Total distance', 'NOT TESTED', 'self-test'))
    elif target:
        res['vkt'] = dict(sim_km=vkt, real_km=target, ratio=vkt / target, source=meta.get('real_vkt_source', 'given on command line'))
        lines.append(('Total distance', verdict(abs(vkt / target - 1) <= .1), f'{vkt / 1e6:.2f} M km vs {target / 1e6:.2f} M km, ratio {vkt / target:.3f}; bar is 10%, this total is not a same-method measurement ({res["vkt"]["source"]})'))
    else:
        lines.append(('Total distance', 'NOT TESTED', f'sim {vkt / 1e6:.2f} M km; no measured total for this city, pass --real-vkt-km'))

    # 4 speed by hour, point detector against edge mean
    if has_speed:
        q = t.dropna(subset=['speed', 'sim_speed'])
        diff = q.sim_speed - q.speed
        nv = {d: float((w.speed_o - w.speed).abs().median()) for d, w in wide.items() if w.speed_o.notna().any()}
        worst_v = max(nv.values())

        def dip(x, col):
            g = x.dropna(subset=[col]).groupby('site')[col]
            night = g.quantile(.9)
            low = x[x.hour.between(6, 20)].dropna(subset=[col]).groupby('site')[col].min()
            return (low / night).dropna()
        dr, ds = dip(t, 'speed'), dip(t, 'sim_speed')
        both = pd.concat([dr, ds], axis=1, keys=['r', 's']).dropna()
        dn = {}
        for d, w in wide.items():
            b = pd.concat([dip(w, 'speed'), dip(w, 'speed_o')], axis=1, keys=['r', 'o']).dropna()
            if len(b):
                dn[d] = float((b.r - b.o).abs().median())
        worst_d = max(dn.values()) if dn else float('nan')
        dip_err = float((both.s - both.r).abs().median()) if len(both) else float('nan')
        ok = float(diff.abs().median()) <= worst_v and dip_err <= worst_d
        band = pd.cut(q.limit_kmh, [0, 55, 85, 500], labels=['to 50', '60-80', 'over 80'])
        table = []
        for b, g in q.groupby(band, observed=True):
            row = {'class': str(b), 'sites': int(g.site.nunique())}
            for name, hrs in (('night', (2, 4)), ('am', (7, 9)), ('midday', (11, 14)), ('pm', (16, 18))):
                h = g[g.hour.between(*hrs)]
                row[name] = (round(float(np.average(h.speed, weights=h.flow.clip(lower=1))), 1), round(float(np.average(h.sim_speed, weights=h.sim.clip(lower=1))), 1)) if len(h) else None
            table.append(row)
        # report 15's band, daytime only and only for classes with enough sites to mean anything
        busy = band.groupby(band, observed=True).transform('size').notna() & q.groupby(band, observed=True).site.transform('nunique').ge(20) & q.hour.between(6, 20)
        per = q[busy].assign(band=band[busy]).groupby(['band', 'hour'], observed=True).apply(lambda g: np.average(g.sim_speed, weights=g.sim.clip(lower=1)) / np.average(g.speed, weights=g.flow.clip(lower=1)) - 1, include_groups=False).abs().reset_index(name='err')
        fast = per.band.astype(str).eq('over 80')
        worst_art = float(per[~fast].err.max()) if (~fast).any() else None
        worst_mw = float(per[fast].err.max()) if fast.any() else None
        speed_tier = tier((worst_art or 0) <= .1 and (worst_mw or 0) <= .05, (worst_art or 0) <= .2 and (worst_mw or 0) <= .1) if per.size else ' [report 15: no class with 20 sites]'
        class_text = f"worst daytime class-hour error arterials {'n/a' if worst_art is None else f'{100 * worst_art:.0f}%'}, motorways {'n/a' if worst_mw is None else f'{100 * worst_mw:.0f}%'}"
        res['speed'] = dict(median_abs_kmh=float(diff.abs().median()), bias_kmh=float(diff.mean()), noise_worst_kmh=worst_v, dip_real=float(both.r.median()), dip_sim=float(both.s.median()), dip_error=dip_err, noise_dip_worst=worst_d, by_class=table, verdict=verdict(ok), caveat='point time-mean detector speed against edge space-mean speed; not probes')
        lines.append(('Speed by hour', verdict(ok) + ' (partial)', f"{q.site.nunique()} sites: median |diff| {res['speed']['median_abs_kmh']:.1f} km/h vs real-day worst {worst_v:.1f}; mean sim-real {res['speed']['bias_kmh']:+.1f}; rush-hour dip real {both.r.median():.2f}, sim {both.s.median():.2f} of free speed; {class_text}. Point detector vs edge mean, not probes" + speed_tier))
        for row in table:
            lines.append(('', '', f"  limit {row['class']:>7} km/h, {row['sites']:3} sites, real/sim km/h: " + ', '.join(f"{n} {row[n][0]:.0f}/{row[n][1]:.0f}" for n in ('night', 'am', 'midday', 'pm') if row[n])))
    else:
        lines.append(('Speed by hour', 'NOT TESTED', 'this city publishes no speed at these sites'))

    # 5 travel times
    lines.append(('Travel times', 'NOT TESTED', 'sensors measure points, not routes; needs a separate travel-time source'))

    # 6 where and when
    kind = 'speed' if has_speed else 'occ' if has_occ else None
    if kind:
        col = kind if kind == 'speed' else 'occ'
        scol = 'sim_speed' if kind == 'speed' else 'sim_occ'
        need = (t.flow >= 50) if kind == 'speed' else t.flow.notna()
        jr = jam_flags(t, col, kind) & need
        js = jam_flags(t, scol, kind) & (t.sim >= 50 if kind == 'speed' else True)
        score = f1(js, jr)
        caught = float((js & jr).sum() / max(jr.sum(), 1))
        false_alarm = float(1 - (js & jr).sum() / max(js.sum(), 1))
        nf = {}
        for d, w in wide.items():
            if w[col + '_o'].notna().any():
                nw = jam_flags(w, col, kind) & (w.flow >= 50 if kind == 'speed' else True)
                no = jam_flags(w, col + '_o', kind) & (w.flow_o >= 50 if kind == 'speed' else True)
                nf[d] = f1(no, nw)
        worst_f = min(nf.values()) if nf else float('nan')
        ok = score >= worst_f
        res['where_when'] = dict(kind=kind, real_jam_site_hours=int(jr.sum()), sim_jam_site_hours=int(js.sum()), f1=score, noise_f1_worst=worst_f, noise_f1_by_day=nf, verdict=verdict(ok))
        lines.append(('Where and when', verdict(ok) + ' (partial)', f"jam = {'speed under 70% of site free speed' if kind == 'speed' else 'occupancy over 15% (sim occupancy approximated)'}: real {jr.sum()} site-hours, sim {js.sum()}; overlap F1 {score:.2f} vs real-day worst {worst_f:.2f}; caught {100 * caught:.0f}% of real, false alarms {100 * false_alarm:.0f}%. Only at these sites" + tier(caught >= .75 and false_alarm <= .25, caught >= .6 and false_alarm <= .4)))
    else:
        lines.append(('Where and when', 'NOT TESTED', 'no speed or occupancy'))

    # 7 network curve
    if kind:
        def curve(x, qc, vc):
            y = x.dropna(subset=[qc, vc])
            if kind == 'speed':
                y = y[y[vc] > 0]
                k = y[qc] / y[vc]
            else:
                k = y[vc]
            g = pd.DataFrame({'q': y[qc], 'k': k, 'hour': y.hour}).groupby('hour').mean()
            return g
        cr = curve(t, 'flow', col)
        cs = curve(t, 'sim', scol)

        def curve_err(a1, b1):
            j = a1.join(b1, lsuffix='_a', rsuffix='_b', how='inner')
            return float(np.sqrt(((j.q_a - j.q_b) ** 2).mean()) / j.q_b.mean()), float(np.sqrt(((j.k_a - j.k_b) ** 2).mean()) / j.k_b.mean())
        eq, ek = curve_err(cs, cr)
        en = [curve_err(curve(w, 'flow_o', col + '_o'), curve(w, 'flow', col)) for w in wide.values() if w[col + '_o'].notna().any()]
        wq, wk = max(x[0] for x in en), max(x[1] for x in en)
        ok = eq <= wq and ek <= wk
        res['network_curve'] = dict(flow_nrmse=eq, density_nrmse=ek, noise_flow_worst=wq, noise_density_worst=wk, real=cr.round(3).to_dict(), sim=cs.round(3).to_dict(), verdict=verdict(ok))
        lines.append(('Network curve', verdict(ok) + ' (partial)', f"hourly mean over sites, sensors not the network: flow nRMSE {eq:.2f} vs real-day worst {wq:.2f}; {'density q/v' if kind == 'speed' else 'occupancy'} nRMSE {ek:.2f} vs {wk:.2f}; real peak flow {cr.q.max():.0f}/site/h, sim {cs.q.max():.0f}; density at peak flow real {cr.k[cr.q.idxmax()]:.1f}, sim {cs.k[cs.q.idxmax()]:.1f}" + tier(abs(cs.q.max() / cr.q.max() - 1) <= .1 and abs(cs.k[cs.q.idxmax()] / cr.k[cr.q.idxmax()] - 1) <= .1, abs(cs.q.max() / cr.q.max() - 1) <= .2 and abs(cs.k[cs.q.idxmax()] / cr.k[cr.q.idxmax()] - 1) <= .2)))
    else:
        lines.append(('Network curve', 'NOT TESTED', 'no speed or occupancy'))

    lines.append(('Trips', 'NOT TESTED', 'sites cannot see trips; needs a survey or trajectories'))
    return lines, res


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--ref', type=Path, required=True, help='reference-days/<city>')
    p.add_argument('--net', type=Path, required=True)
    p.add_argument('--edges', type=Path, help='cars run --edge-csv output, hours since local midnight')
    p.add_argument('--summary', type=Path)
    p.add_argument('--out', type=Path, default=Path('/tmp/reference_day'))
    p.add_argument('--max-dist', type=float, default=40)
    p.add_argument('--include-weak', action='store_true', help='also count weak matches in the headline')
    p.add_argument('--real-vkt-km', type=float)
    p.add_argument('--as-sim-day', help='self-test: use this real date as if it were the simulation')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    meta = json.loads((a.ref / 'noise.json').read_text())
    sites = pd.read_csv(a.ref / 'sites.csv', dtype={'site': str})
    ref = pd.read_csv(a.ref / 'reference_day.csv', dtype={'site': str})
    others = pd.read_csv(a.ref / 'other_days.csv.gz', dtype={'site': str, 'date': str})
    sites = sites[sites.qc == 'ok']
    location, edges = read_net(a.net, a.out / (a.net.name + '.pickle'))
    m = match_sites(sites, location, edges, ref, a)
    m.to_csv(a.out / 'matches.csv', index=False, float_format='%.3f')
    counts = m.quality.value_counts().to_dict()
    print(f"Reference: {meta['city']} {meta['reference_date']}, against {len(meta['normal_dates']) - 1} other normal weekdays. {meta.get('source', '')}")
    print(f"Sites with clean data: {len(sites)}. Matched to the net: good {counts.get('good', 0)}, weak {counts.get('weak', 0)}, rejected {counts.get('bad', 0)}.")
    why = m[m.quality != 'good'].why.fillna('').str.split(';').explode()
    why = why[why != ''].str.replace(r'[_0-9]*\d.*', '', regex=True).value_counts()
    print('Not good because: ' + ', '.join(f'{k} {v}' for k, v in why.items()))
    use = m[m.quality.isin(['good', 'weak'] if a.include_weak else ['good'])]
    want = set(use.edge)
    sim_day = a.as_sim_day
    if sim_day:
        o = others[others.date == sim_day].merge(use[['site', 'edge']], on='site')
        d = pd.DataFrame({'edge': o.edge, 'hour': o.hour, 'entered': o.flow})
        d['samples'] = d.entered * 3600 / 3600
        v = o.speed.fillna(50) if 'speed' in o else 50.0
        d['distance'] = d.samples * (v / 3.6)
        totals = dict(distance_km=0.0, teleports=0.0, entered=0.0, hours=list(range(24)), night_stuck_edges=0)
        others = others[others.date != sim_day]
        print(f'SELF-TEST: the simulation is real day {sim_day}.')
    else:
        d, totals = read_edges(a.edges, want)
    missing = sorted(set(range(24)) - set(totals['hours']))
    if missing:
        print(f'WARNING: simulation has no data for hours {missing}; those hours count as missing, not zero.')
    summary = pd.read_csv(a.summary) if a.summary else None
    t = ref.merge(use[['site', 'edge', 'limit_kmh', 'edge_lanes', 'edge_length_m']], on='site')
    t = t.merge(d, on=['edge', 'hour'], how='left')
    # an edge missing from the csv carried nothing; a site missing on a real day was not measured
    t['sim'] = t.entered if sim_day else t.entered.fillna(0.0)
    t.loc[t.hour.isin(missing), 'sim'] = np.nan
    t['sim_speed'] = (t.distance / t.samples.where(t.samples > 0)) * 3.6
    t['sim_occ'] = 100 * t.samples.fillna(0) * EFFECTIVE_LENGTH_M / (3600 * t.edge_length_m * t.edge_lanes)
    keep = set(use.site)
    others = others[others.site.isin(keep)]
    lines, res = evaluate(t, others, a.out, a, meta, totals, summary)
    z = t.dropna(subset=['sim']).groupby('site').agg(real=('flow', 'sum'), sim=('sim', 'sum'))
    zero = z[(z.sim < .02 * z.real) & (z.real > 500)]
    far = z[((z.sim > 5 * z.real) | (z.sim < .2 * z.real)) & (z.real > 500)]
    print()
    width = max(len(l[1]) for l in lines)
    for name, v, text in lines:
        print(f'{name:<22}{v:<{width + 2}}{text}')
    print()
    print('A check that says PASS means no worse than the least similar real weekday on these sites, nothing more. No overall validated label: Travel times and Trips are untested.')
    print('The bar is tight: a real weekday left out and treated as the simulation passes unless it is itself the outlier, so read a near miss as a near miss.')
    if len(zero):
        print(f'FLAG: {len(zero)} matched sites have almost no simulated traffic all day ({", ".join(zero.index[:8])}): a wrong match or missing demand, kept in the numbers.')
    if len(far):
        print(f'FLAG: {len(far)} matched sites are off by more than a factor of 5 over the day ({", ".join(far.index[:8])}): check by hand, kept in the numbers.')
    if counts.get('weak', 0) and not a.include_weak:
        print('Weak matches are excluded; rerun with --include-weak to see the sensitivity.')
    t.drop(columns=['entered'], errors='ignore').to_csv(a.out / 'site_hours.csv', index=False, float_format='%.3f')
    res['matches'] = counts
    res['flag_zero_sim'] = zero.index.tolist()
    res['flag_factor_5'] = far.index.tolist()
    (a.out / 'report.json').write_text(json.dumps(res, indent=1, default=float))
    print(f'Details: {a.out}/matches.csv, site_hours.csv, report.json')


if __name__ == '__main__':
    main()
