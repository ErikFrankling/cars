#!/usr/bin/env python3
"""Where a run jams first: edges nearly stopped with real load for an hour or more, earliest first.  seeds.py RUN NETDIR"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

run, nd = sys.argv[1], sys.argv[2]
net = read_net(DISTRICT / nd / 'net.net.xml', DISTRICT / nd / 'net.pkl')
e = pd.read_csv(B19 / 'runs' / run / 'edges.csv', on_bad_lines='skip')
e = e[e.samples > 0]
e = e[e.begin < e.begin.max()]
e['v'] = e.distance / e.samples
rows = []
for k, q in e.groupby('edge'):
    b = np.sort(q[(q.v < .8) & (q.samples >= 300)].begin.values)
    if len(b) < 4:
        continue
    g = max(np.split(b, np.where(np.diff(b) != 900)[0] + 1), key=len)
    x = net['edges'].get(k)
    if len(g) >= 4 and x:
        rows.append((g[0] / 3600, len(g) / 4, k, x['name'][:22], x['type'].replace('highway.', ''), len(car_lanes(x)), round(car_lanes(x)[0]['length']), x['end'][:30], net['junctions'].get(x['end'], ('?',))[0]))
d = pd.DataFrame(rows, columns='start_h dur_h edge name type lanes len end jt'.split()).sort_values('start_h')
print('through hour', e.begin.max() / 3600, 'persistent edges', len(d))
print(d.head(int(sys.argv[3]) if len(sys.argv) > 3 else 30).to_string())
print(d.jt.value_counts().to_dict(), d.type.value_counts().to_dict())
h = e.assign(h=(e.begin // 3600).astype(int), stopped=(e.v < .8) & (e.samples >= 300)).groupby('h').agg(stopped=('stopped', 'sum'), vs=('samples', 'sum'))
print((h.stopped / 4).round().astype(int).to_dict())
