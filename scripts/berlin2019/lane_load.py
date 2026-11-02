#!/usr/bin/env python3
"""Static load by lane group: for each road and hour, the flow of each next road over the lanes that go there. lane_load.py NETDIR [ROUTES]
Compares with flow over all the road's lanes. If the group is far above the road, turn lane allocation is the limit, not the road."""
import collections
import gzip
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

nd = sys.argv[1]
d = DISTRICT / nd
routes = sys.argv[2] if len(sys.argv) > 2 else d / 'routes_f10.rou.gz'
n = read_net(d / 'net.net.xml', d / 'net.pkl')
e = {k: v for k, v in n['edges'].items() if car_lanes(v)}
lanes_to = collections.defaultdict(set)
for c in n['conns']:
    if c[0] in e:
        lanes_to[(c[0], c[1])].add(c[2])
tt = {k: car_lanes(v)[0]['length'] / max(car_lanes(v)[0]['speed'], 1) * 1.3 for k, v in e.items()}
mv = collections.Counter()
ed = collections.Counter()
HOURS = (7, 16)
with gzip.open(routes, 'rt') as f:
    for line in f:
        m = re.search(r'depart="([^"]+)".*edges="([^"]+)"', line)
        if not m:
            continue
        t = float(m[1])
        r = m[2].split()
        for a, b in zip(r[:-1], r[1:]):
            h = int(t // 3600)
            if h in HOURS:
                mv[(a, b, h)] += 1
                ed[(a, h)] += 1
            t += tt.get(a, 5)
rows = []
tls = {k for k, v in e.items() if n['junctions'].get(v['end'], ('',))[0] == 'traffic_light'}
for (a, b, h), q in mv.items():
    nl = max(1, len(lanes_to[(a, b)]))
    rows.append(dict(edge=a, next=b, h=h, q=q, lanes_for=nl, group=q / nl, road=ed[(a, h)] / len(car_lanes(e[a])), road_lanes=len(car_lanes(e[a])), tls=a in tls, kind=e[a]['type'].replace('highway.', ''), name=e[a]['name']))
r = pd.DataFrame(rows)
w = r.sort_values('group').groupby(['edge', 'h']).tail(1)
for cap in (450, 900, 1800):
    print(f'over {cap}/lane/h: signal approaches, lane group', int(((w.group > cap) & w.tls).sum()), ' road as a whole', int(((w.road > cap) & w.tls).sum()), 'of', int(w.tls.sum()))
print(w[w.tls].sort_values('group', ascending=False).head(14)[['edge', 'name', 'kind', 'h', 'q', 'lanes_for', 'road_lanes', 'group', 'road']].to_string())
r.to_csv(d / 'lane_load.csv.gz', index=False)
