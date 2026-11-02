#!/usr/bin/env python3
"""Turns that cross other turns of the same road at the stop line: crossing_links.py NETDIR [ROUTES].
Order of directions from the right: R r s L l t. A link from lane i to a turn further right than a link from a lane right of i forces drivers to weave across a queue, and no marking would ever ask for it.
Writes NETDIR/crossing_links.csv, with the trips over each link when routes are given."""
import collections
import gzip
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

ORDER = {'r': 0, 'R': 1, 's': 2, 'L': 3, 'l': 4, 't': 5}
d = B19 / sys.argv[1]
net = read_net(d / 'net.net.xml', d / 'net.pkl')
trips = collections.Counter()
if len(sys.argv) > 2:
    with gzip.open(sys.argv[2], 'rt') as f:
        for line in f:
            m = re.search(r'edges="([^"]+)"', line)
            if m:
                r = m[1].split()
                trips.update(zip(r, r[1:]))
by = collections.defaultdict(list)
for c in net['conns']:
    if car_lanes(net['edges'].get(c[0], {'lanes': []})):
        by[c[0]].append(c)
rows = []
for k, cs in by.items():
    for a in cs:
        for b in cs:
            if a[2] < b[2] and a[1] != b[1] and ORDER.get(a[5], 2) > ORDER.get(b[5], 2):
                e = net['edges'][k]
                rows.append(dict(edge=k, name=e['name'], lanes=len(e['lanes']), length=round(e['lanes'][0]['length'], 1), right_lane=a[2], right_lane_to=a[1], right_lane_dir=a[5], left_lane=b[2], left_lane_to=b[1], left_lane_dir=b[5], trips=trips[(k, b[1])], tl=bool(b[4])))
x = pd.DataFrame(rows)
x.to_csv(d / 'crossing_links.csv', index=False)
print('roads with crossing turns', x.edge.nunique() if len(x) else 0, 'of', len(by), 'pairs', len(x))
if len(x):
    print(x.groupby(['right_lane_dir', 'left_lane_dir']).size().sort_values(ascending=False).head(10).to_string())
    print(x.sort_values('trips', ascending=False).drop_duplicates('edge').head(14)[['edge', 'name', 'lanes', 'length', 'right_lane', 'right_lane_to', 'right_lane_dir', 'left_lane', 'left_lane_to', 'left_lane_dir', 'trips']].to_string())
