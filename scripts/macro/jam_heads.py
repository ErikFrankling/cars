#!/usr/bin/env python3
"""F045, F067. Real jam heads (tier A, in the district, no parallel-road rows) against the table: real flow at a tuning loop within two edges of
the head, over the head's table capacity from a model A run (am heads at 08 h, pm at 16 h). Real flow: the highest hour inside the head's median
jam window, median over the 8 days. Capacity: the head edge's lane groups at the run's flows (turn split and foes included).
    jam_heads.py PREP RUN_AM RUN_PM OUT.csv"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
B19 = Path('/home/erikf/projects/personal/cars-data/berlin2019')
prep, am, pm, out = (Path(x) for x in sys.argv[1:5])
meta = pd.read_csv(prep / 'edge_meta.csv', dtype={'id': str}, keep_default_na=False)
pos = {k: i for i, k in enumerate(meta.id)}
arcs = pd.read_csv(prep / 'arcs.tsv', sep='\t')
succ, pred = {}, {}
for a, b in zip(arcs['from'], arcs['to']):
    succ.setdefault(a, set()).add(b)
    pred.setdefault(b, set()).add(a)
info = pd.read_csv(prep / 'arcs_info.csv', keep_default_na=False, dtype=str)
info['arc'] = info.arc.astype(int)
sites = pd.read_csv(prep / 'sites.tsv', sep='\t', dtype={'edge': str})
freeze = json.load(open(B19 / 'step1/freeze.json'))
tuning = set(freeze['tuning_sites'])
sites = sites[sites.site.isin(tuning)]
site_at = {}
for s in sites.itertuples():
    if s.edge in pos:
        site_at.setdefault(pos[s.edge], []).append(s.site)
real = pd.read_csv(B19 / 'step1/real_days.csv.gz')
real = real[real.site.isin(tuning) & real.date.isin(freeze['tuning_days'])]
runs = {}
for name, run, h in (('am', am, 8), ('pm', pm, 16)):
    r = pd.read_csv(run / 'arcs.tsv', sep='\t')
    r = r[r.hour == h].merge(info[['arc', 'frm']], on='arc')
    runs[name] = r
grp = dict(zip(arcs.id, arcs.group))
J = pd.read_csv(REPO / 'research/truth/berlin2019/real_jams.csv', low_memory=False, dtype={'head_edge': str})
J = J[(J.source == 'probe') & (J.tier == 'A') & J.in_district.astype(bool) & ~J.flag_parallel_road.fillna(False).astype(bool)]


def find(e):
    if e in pos:
        return pos[e]
    c = [k for k in pos if k.split('#')[0] == e.split('#')[0]]
    return pos[c[0]] if len(c) == 1 else None


rows = []
for j in J.itertuples():
    h = find(j.head_edge)
    if h is None:
        rows.append(dict(threshold=j.threshold, period=j.period, place=j.place, head=j.head_edge, status='head not on the macro map'))
        continue
    near = {h: 0}
    front = [h]
    for d in (1, 2):
        nxt = []
        for x in front:
            for y in succ.get(x, set()) | pred.get(x, set()):
                if y not in near:
                    near[y] = d
                    nxt.append(y)
        front = nxt
    ss = sorted(((near[e], s) for e in near for s in site_at.get(e, [])))
    r = runs[j.period]
    g = r[r.frm == meta.id[h]]
    cap = float(g.drop_duplicates('arc').assign(gr=lambda x: x.arc.map(grp)).drop_duplicates('gr').cap.sum()) if len(g) else np.nan
    flow_m = float(g.o.sum()) if len(g) else 0.0
    xmax = float(g.x.max()) if len(g) else np.nan
    base = dict(threshold=j.threshold, period=j.period, place=j.place, head=j.head_edge, road_class=j.road_class, days=j.days_of_8, window=f'{j.head_start_median}-{j.head_end_median}', cap=round(cap) if cap == cap else None, macro_flow=round(flow_m), macro_x=round(xmax, 2) if xmax == xmax else None, cause=j.cause if isinstance(j.cause, str) else '')
    if not ss:
        rows.append(dict(base, status='no tuning loop within two edges'))
        continue
    dist, site = ss[0]
    h0 = int(str(j.head_start_median)[:2])
    h1 = int(str(j.head_end_median)[:2])
    q = real[(real.site == site) & real.hour.between(h0, max(h0, h1))]
    qf = float(q.groupby('date').flow.max().median()) if len(q) else np.nan
    rows.append(dict(base, status='loop', site=site, loop_edges_away=dist, real_flow=round(qf) if qf == qf else None, ratio=round(qf / cap, 2) if cap > 0 and qf == qf else np.nan))
t = pd.DataFrame(rows)
t.to_csv(out, index=False)
pd.set_option('display.width', 250)
print(t.status.value_counts().to_string())
for th, g in t[t.status == 'loop'].groupby('threshold'):
    print(th, 'heads with a loop', len(g), 'median real/capacity', round(g.ratio.median(), 2), 'p25-p75', round(g.ratio.quantile(.25), 2), round(g.ratio.quantile(.75), 2), 'over 1.1', int((g.ratio > 1.1).sum()), 'under .6', int((g.ratio < .6).sum()))
print(t[t.status == 'loop'].sort_values('ratio').to_string())
