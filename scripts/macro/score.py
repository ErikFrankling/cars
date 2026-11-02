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
