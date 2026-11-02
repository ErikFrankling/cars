#!/usr/bin/env python3
"""Green share per signal link by controller size, and what is at the worst edges of a run. Usage: greens.py NET.xml [EDGES.csv]"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
n = load_net(sys.argv[1]); E_ = n['edges']
nodes = collections.defaultdict(set); links = collections.defaultdict(dict)
for c in n['conns']:
    if c['tls'] and c['frm'] in E_:
        nodes[c['tls']].add(E_[c['frm']]['to']); links[c['tls']][c['li']] = c
by = collections.defaultdict(list); ph = collections.defaultdict(list); thru = collections.defaultdict(list)
for t, v in n['tls'].items():
    cy = sum(p[0] for p in v['phases']); k = min(len(nodes[t]), 4)
    ph[k].append(len(v['phases']))
    for li, c in links[t].items():
        g = sum(p[0] for p in v['phases'] if li < len(p[1]) and p[1][li] in 'Gg') / cy
        by[k].append(g)
        if c['dir'] == 's':
            thru[k].append(g)
print('controller nodes: controllers, phases mean, green share of all links mean, straight links mean / p10')
for k in sorted(by):
    print(k, len(ph[k]), round(float(np.mean(ph[k])), 1), round(float(np.mean(by[k])), 3), round(float(np.mean(thru[k])), 3) if thru[k] else '-', round(float(np.percentile(thru[k], 10)), 3) if thru[k] else '-')
if len(sys.argv) > 2:
    c = collections.Counter()
    for l in open(sys.argv[2]):
        a = l.strip().split(',')
        if a[0] != 'begin' and len(a) > 5:
            c[a[1]] += int(float(a[5]))
    out = collections.defaultdict(list)
    for x in n['conns']:
        out[x['frm']].append(x)
    for e, k in c.most_common(10):
        if e.startswith(':') or e not in E_:
            print(k, e, 'internal'); continue
        d = E_[e]
        print(k, e, repr(d['name']), 'to', d['to'][:30], J if (J := n['junctions'].get(d['to'], {}).get('type')) else '', 'len', round(d['lanes'][0]['length'], 1))
        for l in d['lanes']:
            cs = [x for x in out[e] if x['fl'] == l['i']]
            print('    lane', l['i'], 'allow', (l['allow'] or '-')[:20], 'to', [(x['to'][:18], x['tl'], x['dir'], x['state'], x['tls'] or '') for x in cs][:5])
