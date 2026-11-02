#!/usr/bin/env python3
"""Compare runs on the inner 49 km2 only: inner.py RUN[:DISTRICT/NETDIR] ...
Cars inside the box per 15 minutes (vehicle-seconds on edges with their middle in the box, over 900 s), and flow entering the box per hour on edges that cross its edge.
Cars that start at the cut are planned to a fixed schedule; a larger cut lets congestion upstream meter them. That difference is the boundary effect."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

box = json.load(open(B19 / 'step0/district.json'))['box']
ins = lambda p: box[0] <= p[0] < box[2] and box[1] <= p[1] < box[3]
T = [21600, 23400, 25200, 27000, 28800]
for arg in sys.argv[1:]:
    run, _, nd = arg.partition(':')
    nd = nd or 'district/m12'
    net = read_net(B19 / nd / 'net.net.xml', B19 / nd / 'net.pkl')
    inner, cross = set(), set()
    for k, e in net['edges'].items():
        cl = car_lanes(e)
        if not cl:
            continue
        sh = cl[0]['shape']
        if ins(sh[len(sh) // 2]):
            inner.add(k)
        if not ins(sh[0]) and ins(sh[-1]):
            cross.add(k)
    e = pd.read_csv(B19 / 'runs' / run / 'edges.csv', on_bad_lines='skip')
    a = e[e.edge.isin(inner)].groupby('begin').samples.sum() / 900
    # the bin ending at T
    inside = {t: int(a.get(t - 900, 0)) for t in T}
    c = e[e.edge.isin(cross)].groupby('begin').entered.sum() * 4
    flow = {int(t / 900): int(c.get(t, 0)) for t in range(18000, 28800, 1800)}
    s = pd.read_csv(B19 / 'runs' / run / 'summary.csv')
    print(run, 'edges inner', len(inner), 'crossing', len(cross), '| cars inside at 06:00 06:30 07:00 07:30 08:00:', list(inside.values()), '| all net at 07:30', int(s[s.time == 27000].running.iloc[0]) if (s.time == 27000).any() else '', '| entering per h by quarter 20=05:00:', flow)
