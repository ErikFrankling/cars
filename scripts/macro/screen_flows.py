#!/usr/bin/env python3
"""Movement flows per hour from the old 10% route file x10, timed at departure + 1.3 x free flow. A screen only (D 4.1): foe flows for the table until macro's own flows exist.
    screen_flows.py NETDIR ROUTES.rou.gz OUT.csv.gz"""
import collections
import csv
import gzip
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mtable as mt

DATA = Path('/home/erikf/projects/personal/cars-data/berlin2019')
T = mt.read(DATA / 'district' / sys.argv[1] / 'net.net.xml')
tt = {k: e['L'] / max(e['v'], 1) * 1.3 for k, e in T['edges'].items()}
mv = collections.Counter()
pat = re.compile(r'depart="([^"]+)".*edges="([^"]+)"')
with gzip.open(sys.argv[2], 'rt') as f:
    for line in f:
        m = pat.search(line)
        if m:
            t = float(m[1])
            r = m[2].split()
            for a, b in zip(r, r[1:]):
                mv[(int(t // 3600) % 24, a, b)] += 10
                t += tt.get(a, 5.0)
with gzip.open(sys.argv[3], 'wt') as f:
    w = csv.writer(f)
    w.writerow(['hour', 'frm', 'to', 'q'])
    for (h, a, b), q in mv.items():
        w.writerow([h, a, b, q])
print('movement-hours', len(mv))
