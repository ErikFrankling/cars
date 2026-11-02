#!/usr/bin/env python3
"""A bus-only lane between two car lanes walls the lanes off: a car cannot legally reach the turn lane beyond it. Opens such lanes to cars, only on those edges.
It is a stand-in for the break in the bus lane that the real street has before the junction. Usage: open_islands.py IN.net.xml OUT.net.xml"""
import sys
from lxml import etree as E
t = E.parse(sys.argv[1]); r = t.getroot(); n = 0; edges = []
def car(l):
    a, d = l.get('allow'), l.get('disallow')
    if a is not None:
        return 'passenger' in a.split()
    return d is None or 'passenger' not in d.split()
for e in r.findall('edge'):
    if e.get('function') == 'internal':
        continue
    ls = sorted(e.findall('lane'), key=lambda l: int(l.get('index')))
    fl = [car(l) for l in ls]
    idx = [i for i, f in enumerate(fl) if f]
    if len(idx) < 2:
        continue
    hit = False
    for i in range(idx[0], idx[-1]):
        if not fl[i] and 'bus' in (ls[i].get('allow') or ''):
            del ls[i].attrib['allow']; ls[i].attrib.pop('disallow', None); n += 1; hit = True
    if hit:
        edges.append(e.get('id'))
t.write(sys.argv[2], encoding='UTF-8', xml_declaration=True)
print('bus lanes between car lanes opened', n, 'on edges', len(edges), edges[:12])
