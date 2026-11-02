#!/usr/bin/env python3
"""Signals on the map against OSM of January 2019: signal_audit.py NETDIR SIG_OPL [--radius R]. SIG_OPL is `osmium tags-filter ... n/highway=traffic_signals` as OPL.
A junction with a car road and an OSM signal assigned to it, or on one of its joined nodes, but no signal in the net, is missing one (three neighbours or more is a real crossing, two is a signal for pedestrians); a signal in the net with none near it in 2019 is extra.
Writes NETDIR/signal_audit.csv. OSM tags crossings for pedestrians too, so each finding shows what its nodes carry."""
import argparse
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from pyproj import Transformer

p = argparse.ArgumentParser()
p.add_argument('netdir')
p.add_argument('opl')
p.add_argument('--radius', type=float, default=25)
a = p.parse_args()
d = B19 / a.netdir
net = read_net(d / 'net.net.xml', d / 'net.pkl')
tr = Transformer.from_crs('EPSG:4326', net['location']['projParameter'], always_xy=True)
off = np.array(list(map(float, net['location']['netOffset'].split(','))))
rows = []
for line in open(a.opl):
    f = line.split(' ')
    lon = next(x[1:] for x in f if x.startswith('x'))
    lat = next(x[1:] for x in f if x.startswith('y'))
    tags = next((x[1:] for x in f if x.startswith('T')), '')
    x, y = tr.transform(float(lon), float(lat))
    rows.append((f[0][1:], x + off[0], y + off[1], tags))
sig = pd.DataFrame(rows, columns=['node', 'x', 'y', 'tags'])
xy = np.array([[v[1], v[2]] for v in net['junctions'].values()])
print('junction sample', list(net['junctions'].items())[0], 'signals total', len(sig))
out = []
keep = {e['start'] for e in net['edges'].values() if car_lanes(e)} | {e['end'] for e in net['edges'].values() if car_lanes(e)}
sxy = sig[['x', 'y']].values
degree, neighbours = {}, {}
for e in net['edges'].values():
    if car_lanes(e):
        degree[e['end']] = degree.get(e['end'], 0) + 1
        degree[e['start']] = degree.get(e['start'], 0) + 1
        neighbours.setdefault(e['end'], set()).add(e['start'])
        neighbours.setdefault(e['start'], set()).add(e['end'])
# a signal belongs to the junction it sits closest to, measured in that junction's own size: a joined junction spreads over tens of metres
ends = {}
for e in net['edges'].values():
    for l in car_lanes(e):
        ends.setdefault(e['end'], []).append(l['shape'][-1])
        ends.setdefault(e['start'], []).append(l['shape'][0])
names = [k for k in net['junctions'] if k in keep]
at = np.array([net['junctions'][k][1:3] for k in names])
radius = np.array([max(a.radius, 1.2 * max(np.hypot(*(np.array(q) - c)) for q in ends[k])) for k, c in zip(names, at)])
assigned = {}
for i, (x, y) in enumerate(sxy):
    r = np.hypot(at[:, 0] - x, at[:, 1] - y) / radius
    j = int(np.argmin(r))
    if r[j] < 1:
        assigned.setdefault(names[j], []).append(i)
ids = {str(n): i for i, n in enumerate(sig.node)}
for k, c in zip(names, at):
    v = net['junctions'][k]
    near = sorted(set(assigned.get(k, []) + [ids[m] for m in re.findall(r'\d+', k) if m in ids]))
    has = 'traffic_light' in v[0]
    if has and not near:
        out.append(dict(junction=k, type=v[0], kind='net_signal_none_in_2019', x=v[1], y=v[2], arms=degree.get(k, 0), neighbours=len(neighbours.get(k, ())), n=0, tags=''))
    elif not has and near and degree.get(k, 0) > 2:
        out.append(dict(junction=k, type=v[0], kind='osm_signal_not_on_net', x=v[1], y=v[2], arms=degree.get(k, 0), neighbours=len(neighbours.get(k, ())), n=len(near), tags=sig.tags.iloc[near[0]][:80]))
d2 = pd.DataFrame(out)
d2.to_csv(d / 'signal_audit.csv', index=False)
print(d2.groupby(['kind', 'type', 'neighbours']).size().to_string())
