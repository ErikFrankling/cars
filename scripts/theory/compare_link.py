#!/usr/bin/env python3
"""Hourly and daily load on chosen edges: MATSim's legs (x10) against our district route file (x10). python3 -I compare_link.py LEGS ROUTES EDGE..."""
import collections
import gzip
import re
import sys

legs, routes = sys.argv[1:3]
want = set(sys.argv[3:])
a = collections.Counter()
ad = collections.Counter()
with gzip.open(legs, 'rt') as f:
    next(f)
    for line in f:
        p = line.rstrip('\n').split('\t')
        ls = p[6].split()
        hit = want & set(ls)
        if hit:
            dep = int(p[3])
            trav = int(p[4])
            n = max(len(ls), 1)
            for i, l in enumerate(ls):
                if l in want:
                    h = int((dep + trav * i / n) // 3600)
                    a[(l, h)] += 10
                    ad[l] += 10
b = collections.Counter()
bd = collections.Counter()
pat = re.compile(r'depart="([^"]+)".*edges="([^"]+)"')
with gzip.open(routes, 'rt') as f:
    for line in f:
        m = pat.search(line)
        if not m or not (want & set(m[2].split())):
            continue
        t = float(m[1])
        r = m[2].split()
        for i, l in enumerate(r):
            if l in want:
                b[(l, int(t // 3600))] += 10
                bd[l] += 10
for w in sorted(want):
    print(w, 'day: MATSim', ad[w], 'routes', bd[w])
    print('  hour  MATSim  routes(depart hour)')
    for h in (5, 6, 7, 8, 9, 12, 15, 16, 17, 18):
        print('  ', h, a[(w, h)], b[(w, h)])
