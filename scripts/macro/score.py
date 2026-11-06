#!/usr/bin/env python3
"""Score a macro run with the frozen metrics.py and step6_probes.py, tuning sites and tuning days only. score.py PREP RUN NAME [--netdir m17]
Writes runs/macro_NAME/{site_hour.csv,edges.csv,score.json}. Site flow: leaving flow of each movement, by the share of its lanes the detectors cover, plus half of trips that start or end on the edge.
Site speed: the edge's free speed, slowed for vehicles whose queue (red-time plus residual) reaches the detector."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'berlin2019'))
import metrics
DATA = Path('/home/erikf/projects/personal/cars-data/berlin2019')


HOURS = range(6, 21)
CLASSES = {'motorway': ('motorway', 'motorway_link', 'trunk', 'trunk_link'), 'arterial': ('primary', 'primary_link', 'secondary', 'secondary_link'), 'local': ('tertiary', 'tertiary_link', 'residential', 'unclassified', 'living_street')}
MAIN = ('motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary', 'tertiary_link')


def blind_checks(prep, run, c, real, classes, edges, netdir, out):
    """Blind first: speed by class and hour against v_hm, dip, real jam list at a third and at half (R 1, tier A, no parallel-road rows). Then timing as R 4 reports it."""
    meta = pd.read_csv(prep / 'edge_meta.csv', keep_default_na=False, dtype={'id': str})
    box = json.load(open(DATA / 'step0/district.json'))['box']
    inbox = (meta.x >= box[0]) & (meta.x < box[2]) & (meta.y >= box[1]) & (meta.y < box[3])
    z = np.load(DATA / 'probes/edge_15min.npz', allow_pickle=True)
    keys = {str(k): i for i, k in enumerate(z['keys'])}
    res = {}
    pn, ne, period = open(run / 'shape.txt').read().split()
    pn, ne, period = int(pn), int(ne), float(period)
    vs = np.fromfile(run / 'vs.bin', np.float32).reshape(pn, ne)
    vm = np.fromfile(run / 'vm.bin', np.float32).reshape(pn, ne)
    pph = int(round(3600 / period))
    Lm = meta.L.values
    for cl, ts in CLASSES.items():
        idx = np.where(meta.type.isin(ts) & inbox)[0]
        ki = [keys[meta.id[i]] for i in idx if meta.id[i] in keys]
        vol = np.nan_to_num(z['vol'][ki])
        hm = np.nan_to_num(z['hm'][ki])
        med = np.nan_to_num(z['med'][ki])
        rows = {}
        for h in HOURS:
            q = slice(h * 4, h * 4 + 4)
            w = vol[:, :, q]
            rh = float((w * hm[:, :, q]).sum() / max(w.sum(), 1))
            rm = float((w * med[:, :, q]).sum() / max(w.sum(), 1))
            ps = range(h * pph, (h + 1) * pph)
            t = vs[np.ix_(list(ps), idx)].sum(axis=0)
            d = vm[np.ix_(list(ps), idx)].sum(axis=0)
            good = t > 0
            k = 3.6 * d[good] / t[good]
            mk = float(np.average(k, weights=t[good])) if good.any() else float('nan')
            rows[h] = (round(rh, 1), round(rm, 1), round(mk, 1))
        r = pd.DataFrame(rows, index=['hm', 'med', 'model']).T.dropna()
        res[cl] = dict(mean_abs_pct_hm=round(float(((r.model - r.hm).abs() / r.hm).mean() * 100), 1), bias_pct_hm=round(float(((r.model - r.hm) / r.hm).mean() * 100), 1), dip_model=round(float(r.model.min() / r.model.max()), 2) if len(r) else None, dip_real_med=round(float(r.med.min() / r.med.max()), 2), by_hour={int(h): tuple(x) for h, x in r.iterrows() if h in (6, 8, 12, 16, 17, 20)})
    # jam list
    jams = pd.read_csv(HERE.parents[1] / 'research/truth/berlin2019/real_jams.csv', low_memory=False, dtype={'head_edge': str})
    jams = jams[(jams.source == 'probe') & (jams.tier == 'A') & jams.in_district.astype(bool) & ~jams.flag_parallel_road.fillna(False).astype(bool)]
    je = pd.read_csv(DATA / 'macro/real_jam_edges.csv', dtype=str)[['threshold', 'period', 'head_edge', 'edge_ids']]
    jams = jams.merge(je, on=['threshold', 'period', 'head_edge'])
    pos = {k: i for i, k in enumerate(meta.id)}
    base = {}
    for k, i in pos.items():
        base.setdefault(k.split('#')[0], []).append(i)
    def mapped(e):
        if e in pos:
            return [pos[e]]
        b = base.get(e.split('#')[0], [])
        return b if len(b) <= 3 else []
    arcs = pd.read_csv(prep / 'arcs.tsv', sep='\t')
    succ = {}
    for a_, b_ in zip(arcs['from'], arcs['to']):
        succ.setdefault(a_, []).append(b_)
    with np.errstate(invalid='ignore', divide='ignore'):
        v = np.where(vs > 0, vm / vs, np.nan)
        flow = np.where(Lm > 0, vm / np.maximum(Lm, 1), 0) * pph
    loaded = int((vs.sum(axis=1) > 0).sum())
    if loaded >= 12 * pph:
        free = np.nanpercentile(np.where(flow > 10, v, np.nan), 90, axis=0)
    else:
        # one or two hours: free is the edge's 05-06 h probe speed, the same reference the list uses
        ev = pd.read_csv(prep / 'edges.tsv', sep='\t', keep_default_na=False, dtype={'id': str}).v.values
        free = ev.astype(float)
    res['jam_free_reference'] = 'model p90 over the day' if loaded >= 12 * pph else 'edge free speed, single-hour run'
    ismain = meta.type.isin(MAIN).values & inbox.values
    out_j = {}
    for name, frac in (('third', 1 / 3), ('half', .5)):
        lst = jams[jams.threshold == name]
        for per, (h0, h1) in dict(am=(5, 11), pm=(12, 21)).items():
            ps = list(range(h0 * pph, h1 * pph))
            with np.errstate(invalid='ignore'):
                mask = (v[ps] < free * frac) & (flow[ps] >= 50)
            hit = np.where(mask.any(axis=0) & ismain)[0]
            s = set(hit.tolist())
            seen, places = set(), []
            for i in hit:
                if i in seen:
                    continue
                st, comp = [int(i)], []
                seen.add(int(i))
                while st:
                    x = st.pop()
                    comp.append(x)
                    for y in succ.get(x, []):
                        if y in s and y not in seen:
                            seen.add(y)
                            st.append(y)
                if Lm[comp].sum() >= 200:
                    places.append(set(comp))
            pl = lst[lst.period == per]
            list_edges = [set(i for e in str(r).split() for i in mapped(e)) for r in pl.edge_ids]
            lu = set().union(*list_edges) if list_edges else set()
            mu = set().union(*places) if places else set()
            caught = float(np.mean([bool(x & mu) for x in list_edges])) if list_edges else None
            false = float(np.mean([not (x & lu) for x in places])) if places else None
            out_j[f'{name}_{per}'] = dict(list_places=len(pl), list_unmapped=sum(1 for x in list_edges if not x), model_places=len(places), caught=round(caught, 3) if caught is not None else None, false=round(false, 3) if false is not None else None)
    res['jams'] = out_j
    # timing, as R 4
    merged = real.groupby(['site', 'hour']).flow.median().reset_index().merge(c[['site', 'hour', 'flow']], on=['site', 'hour'], suffixes=('_r', '_m'))
    merged['cl'] = merged.site.map(classes)
    art = merged[merged.cl.isin(['primary', 'secondary'])].groupby('hour')[['flow_r', 'flow_m']].sum()
    res['real_over_model_arterial_by_hour'] = {int(h): round(float(x.flow_r / max(x.flow_m, 1)), 2) for h, x in art.iterrows() if h in (6, 7, 8, 9, 10, 11, 12, 15, 16, 17, 18)}
    res['real_over_model_24h'] = {k: round(float(g.flow_r.sum() / max(g.flow_m.sum(), 1)), 2) for k, g in merged.groupby('cl')}
    (out / 'blind.json').write_text(json.dumps(res, indent=1, default=float))
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument('prep')
    p.add_argument('run')
    p.add_argument('name')
    p.add_argument('--netdir', default='m17')
    p.add_argument('--hours', default='')
    a = p.parse_args()
    prep, run = Path(a.prep), Path(a.run)
    edges = pd.read_csv(prep / 'edges.tsv', sep='\t', keep_default_na=False)
    info = pd.read_csv(prep / 'arcs_info.csv', keep_default_na=False, dtype=str)
    arcs = pd.read_csv(run / 'arcs.tsv', sep='\t')
    eh = pd.read_csv(run / 'edge_hour.tsv', sep='\t')
    sites = pd.read_csv(prep / 'sites.tsv', sep='\t', dtype={'edge': str})
    eid = edges.id.values
    eh['id'] = eid[eh.edge.values]
    out = DATA / 'runs' / f'macro_{a.name}'
    out.mkdir(parents=True, exist_ok=True)
    # edges.csv in the form step6_probes.py reads
    e = pd.DataFrame(dict(begin=eh.hour * 3600, edge=eh.id, distance=eh.vm, samples=eh.vs))
    e = e[(e.samples > 0) & (e.begin < 86400)]
    e.to_csv(out / 'edges.csv', index=False)
    info['arc'] = info.arc.astype(int)
    arcs = arcs.merge(info, on='arc')
    by_from = {k: g for k, g in arcs.groupby('frm')}
    L = dict(zip(edges.id, edges.L))
    V = dict(zip(edges.id, edges.v))
    LN = dict(zip(edges.id, edges.lanes))
    eh2 = {k: g.set_index('hour') for k, g in eh[eh.id.isin(set(sites.edge))].groupby('id')}
    rows = []
    for s in sites.itertuples():
        e0 = s.edge
        if e0 not in by_from and e0 not in eh2:
            continue
        ls = {int(x) for x in str(s.lanes).split()}
        g = by_from.get(e0)
        nl = LN.get(e0, 1)
        whole = len(ls) >= nl
        d = eh2.get(e0)
        hours = sorted(set(g.hour) if g is not None else set()) if d is None else sorted(set(d.index) | (set(g.hour) if g is not None else set()))
        for h in hours:
            if h > 23:
                continue
            q, res, red, xv = 0.0, 0.0, 0.0, 0.0
            if g is not None:
                gh = g[g.hour == h]
                per_lane = {}
                for r in gh.itertuples():
                    ml = r.lanes.split()
                    for x in ml:
                        per_lane[x] = per_lane.get(x, 0.0) + r.o / len(ml)
                    res = max(res, r.res)
                    xv = max(xv, r.x)
                    if r.gc > 0:
                        red = max(red, r.n / max(nl, 1) * (1 - r.gc) * 90 / 3600)
            if g is not None:
                # which lanes a detector stands on is known as rightmost, second from right; a closed bus lane or a pocket shifts it. So: the busiest n lanes.
                q = sum(sorted(per_lane.values(), reverse=True)[:len(ls)]) if not whole else sum(per_lane.values())
            if d is not None and h in d.index:
                q += .5 * (d.starts[h] + d.ends[h]) * min(len(ls) / max(nl, 1), 1.0)
            if q <= 0:
                continue
            vf = V.get(e0, 13.0) * 3.6
            dist = max(L.get(e0, 50.0) - s.pos, 0.0)
            ql = (res / max(nl, 1) + red) * 7.5
            v = vf
            if ql >= dist:
                per = q / max(len(ls), 1)
                k = max(133 - per / 18, 20)
                vc = max(min(per / k, vf), 5.0)
                ph = 1.0 if res > 0 else min(1.0, (ql - dist) / max(ql, 1.0) + .3)
                v = 1 / ((1 - ph) / vf + ph / vc)
            rows.append((s.site, int(h), round(q), round(v)))
    sh = pd.DataFrame(rows, columns=['site', 'hour', 'flow', 'speed'])
    sh.to_csv(out / 'site_hour.csv', index=False)
    freeze = json.load(open(DATA / 'step1/freeze.json'))
    tuning = set(freeze['tuning_sites'])
    real = pd.read_csv(DATA / 'step1/real_days.csv.gz')
    real = real[real.site.isin(tuning)]
    classes = dict(zip(*(lambda d: (d.site, d.road_class))(pd.read_csv(DATA / 'step0/sites.csv'))))
    c = sh[sh.site.isin(tuning)]
    hh = [int(x) for x in a.hours.split(',') if x]
    res = {}
    for dd in freeze['tuning_days']:
        r = real[real.date == dd][['site', 'hour', 'flow', 'speed']]
        if hh:
            r = r[r.hour.isin(hh)]
        res[dd] = metrics.score(c, r, classes)
    (out / 'score.json').write_text(json.dumps(res, indent=1, default=float))
    blind = blind_checks(prep, run, c, real, classes, edges, a.netdir, out)
    print(json.dumps(blind))

    def med(*path):
        v = []
        for day in res.values():
            x = day
            for k in path:
                x = x.get(k, {}) if isinstance(x, dict) else {}
            if isinstance(x, (int, float)):
                v.append(x)
        return float(np.median(v)) if v else float('nan')
    S = {k: round(med('volume_07_18', k), 3) for k in ('rmsn', 'r2', 'slope', 'geh_lt5', 'wape', 'bias')}
    print('flows, tuning sites, 8 days, median:', S)
    print('jam caught', round(med('where_when', 'caught'), 3), 'false', round(med('where_when', 'false_alarm'), 3), 'speed abs median', round(med('speed_site_median_abs_kmh'), 1), 'shape pts', round(med('day_shape', 'mean_abs_share_points'), 2))
    cls = {c_: {k: round(med('volume_by_class', c_, k), 3) for k in ('bias', 'rmsn', 'r2')} for c_ in ('primary', 'secondary', 'tertiary')}
    print('class', cls)
    out2 = subprocess.run([sys.executable, '-I', str(HERE.parent / 'berlin2019/step6_probes.py'), out.name, a.netdir], capture_output=True, text=True)
    try:
        pj = json.loads((out / 'probe_score.json').read_text())
        for k in pj:
            s = pj[k]
            print('probes', k, 'mean abs %', round(s['mean_abs_pct'], 1), 'bias %', round(s['bias_pct'], 1), 'dip', round(s['dip_sim'], 2), 'real', round(s['dip_real'], 2), {h: s['sim_kmh_by_hour'].get(str(h)) for h in (6, 8, 12, 16, 20)})
    except Exception as ex:
        print('probes failed', ex, out2.stderr[-400:])


if __name__ == '__main__':
    main()
