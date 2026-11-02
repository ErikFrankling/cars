#!/usr/bin/env python3
"""A lane-level route check. On an edge, lanes a car can change between form groups; a bus-only lane splits them.
Counts movements leaving a group that no incoming connection enters, and how many route steps need one. Streams, so it also works on the whole city. Usage: walls.py NET.xml [ROUTES.xml[.gz]]"""
import sys, gzip, re, collections
from lxml import etree as E
def car(a, d):
    if a is not None:
        return 'passenger' in a.split()
    return d is None or 'passenger' not in d.split()
lanes = {}; conns = []; intern = set()
for ev, el in E.iterparse(sys.argv[1], events=('end',), tag=('edge', 'connection')):
    if el.tag == 'edge':
        if el.get('function') != 'internal':
            lanes[el.get('id')] = sorted((int(l.get('index')), car(l.get('allow'), l.get('disallow')), l.get('allow') or '') for l in el.findall('lane'))
    elif not el.get('from').startswith(':'):
        conns.append((el.get('from'), int(el.get('fromLane')), el.get('to'), int(el.get('toLane')), el.get('allow'), el.get('disallow')))
    el.clear()
    while el.getprevious() is not None:
        del el.getparent()[0]
def groups(e):
    g = {}; k = 0
    for i, c, a in lanes[e]:
        if not c:
            k += 1; continue
        g[i] = k
    return g
G = {e: groups(e) for e in lanes}
walled = {e for e, g in G.items() if len(set(g.values())) > 1}
into = collections.defaultdict(set); outof = collections.defaultdict(lambda: collections.defaultdict(set))
for f, fl, t, tl, a, d in conns:
    if f in G and t in G and fl in G[f] and tl in G[t]:
        into[t].add(G[t][tl]); outof[f][t].add(G[f][fl])
bad = {}
for e in walled:
    reach = into[e]
    if not reach:
        continue
    for t, gs in outof[e].items():
        if not (gs & reach):
            bad[(e, t)] = sorted(gs)
print('edges split by a closed lane', len(walled), 'bus lanes between car lanes', sum(1 for e in walled for i, c, a in lanes[e] if not c and min(G[e]) < i < max(G[e])))
print('edge pairs a route can use but a car cannot reach by lane', len(bad), list(bad)[:8])
for e in sorted(walled)[:8]:
    print(' ', e, [(i, 'car' if c else a[:12]) for i, c, a in lanes[e]], 'entered groups', sorted(into[e]), {t[:18]: g for t, g in list(outof[e].items())[:4]})
if len(sys.argv) > 2:
    op = gzip.open if sys.argv[2].endswith('.gz') else open; n = hit = 0; routes = {}
    with op(sys.argv[2], 'rt') as f:
        for line in f:
            m = re.search(r'<route [^>]*edges="([^"]+)"', line)
            if m:
                n += 1; ed = m.group(1).split()
                hit += any((a, b) in bad for a, b in zip(ed, ed[1:]))
    print('route lines', n, 'using an unreachable step', hit)
