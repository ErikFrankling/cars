#!/usr/bin/env python3
"""F068. Short links between two signals, under 50 m, on the map's programs: what each connection into the link feeds while the through
connection out of it is red, against what the link stores. Then R 6's rule on the opposed through pairs (overlap .2 or less): downstream green
starts 2 s after upstream and overlaps .65 of it. Turns into the link keep the map's program. No simulation.
    short_links.py NETDIR"""
import collections
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd


B19 = Path('/home/erikf/projects/personal/cars-data/berlin2019')
NET = B19 / 'district' / sys.argv[1] / 'net.net.xml'
tls, conns, edges = {}, collections.defaultdict(list), {}
for ev, el in ET.iterparse(NET, events=('end',)):
    if el.tag == 'tlLogic':
        tls[el.get('id')] = dict(ph=[(float(p.get('duration')), p.get('state')) for p in el.findall('phase')])
        el.clear()
    elif el.tag == 'edge' and el.get('function') != 'internal':
        ls = el.findall('lane')
        car = [l for l in ls if 'passenger' not in (l.get('disallow') or '').split() and (not l.get('allow') or {'passenger', 'all'} & set(l.get('allow').split()))]
        edges[el.get('id')] = dict(L=float(ls[0].get('length')), n=max(len(car), 1), type=el.get('type', ''))
        el.clear()
    elif el.tag == 'connection':
        if el.get('tl') and not el.get('from', '').startswith(':'):
            conns[el.get('from')].append((el.get('to'), el.get('tl'), int(el.get('linkIndex')), el.get('dir'), el.get('fromLane')))
        el.clear()
ins = collections.defaultdict(list)
for e, cl in conns.items():
    for c in cl:
        ins[c[0]].append((e,) + c)
def greens(t, i):
    """Green windows of link i over one cycle, and the cycle."""
    tot, out, on = 0.0, [], None
    for d, st in t['ph']:
        g = st[i] in 'Gg'
        if g and on is None:
            on = tot
        if not g and on is not None:
            out.append((on, tot))
            on = None
        tot += d
    if on is not None:
        if out and out[0][0] == 0:
            out[0] = (on - tot, out[0][1])
        else:
            out.append((on, tot))
    return out, tot


def gmask(w, C, res=1.0):
    n = int(C)
    m = np.zeros(n, bool)
    for a, b in w:
        m[np.arange(int(a), int(b)) % n] = True
    return m


SAT = .5  # cars per second per lane, R 6
rows = []
for link, cin in ins.items():
    if link not in edges or link not in conns or edges[link]['L'] >= 50:
        continue
    L, n = edges[link]['L'], edges[link]['n']
    store = max(L / 7.5, 1.0) * n
    outs = [c for c in conns[link] if c[3] == 's' and c[1] in tls]
    if not outs:
        continue
    for frm, to, tl, li, d, fl in cin:
        if tl not in tls:
            continue
        ga, Ca = greens(tls[tl], li)
        if not ga or Ca < 10:
            continue
        ma = gmask(ga, Ca)
        best = None
        for _, tl2, li2, _, _ in outs:
            gb, Cb = greens(tls[tl2], li2)
            if not gb or abs(Ca - Cb) > 1:
                continue
            mb = gmask(gb, Ca)
            ov = (ma & mb).sum() / max(ma.sum(), 1)
            if best is None or ov > best[0]:
                best = (ov, (ma & ~mb).sum(), ma.sum())
        if best is None:
            continue
        ov, feed, g = best
        kind = 'through' if d == 's' else 'turn'
        rule_feed = feed
        if kind == 'through' and ov <= .2:
            rule_feed = .35 * g
        rows.append(dict(link=link, L=L, lanes=n, frm=frm, lane=fl, kind=kind, overlap=round(ov, 2), green=g, feed=feed, fed=feed * SAT, store=store, rule_feed=rule_feed))
a = pd.DataFrame(rows)
# per lane in: each connection is one entering lane, so a link fed by k lanes gets k feeds into one store
per = a.groupby(['link', 'kind']).agg(fed=('fed', 'sum'), rule=('rule_feed', lambda x: x.sum() * SAT), store=('store', 'first'), n=('fed', 'size')).reset_index()
out = {}
for k, g in per.groupby('kind'):
    out[k] = dict(links=len(g), overfed_map=int((g.fed > g.store).sum()), excess_cars_map=round(float((g.fed - g.store).clip(lower=0).sum()), 1), overfed_rule=int((g.rule > g.store).sum()), excess_cars_rule=round(float((g.rule - g.store).clip(lower=0).sum()), 1))
both = a.assign(f_map=a.fed, f_rule=a.rule_feed * SAT).groupby('link').agg(f_map=('f_map', 'sum'), f_rule=('f_rule', 'sum'), store=('store', 'first'))
out['all'] = dict(links=len(both), overfed_map=int((both.f_map > both.store).sum()), excess_cars_map=round(float((both.f_map - both.store).clip(lower=0).sum()), 1), overfed_rule=int((both.f_rule > both.store).sum()), excess_cars_rule=round(float((both.f_rule - both.store).clip(lower=0).sum()), 1))
out['opposed_through_conns'] = int(((a.kind == 'through') & (a.overlap <= .2)).sum())
out['turn_conns_opposed'] = int(((a.kind == 'turn') & (a.overlap <= .2)).sum())
out['conns'] = a.kind.value_counts().to_dict()
print(out)
a.to_csv(B19 / 'macro' / sys.argv[1] / 'short_links.csv', index=False)
