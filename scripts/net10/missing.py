#!/usr/bin/env python3
"""Why does a vehicle-lantern installation have no controller? Usage: missing.py NET.xml AUDIT.json"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from scipy.spatial import cKDTree
n = load_net(sys.argv[1]); fwd, back = tf_from_location(n['location']); reg = register()
S, O = [], []
for e, d in n['edges'].items():
    for l in d['lanes']:
        if passenger(l):
            s = l['shape']
            for a, b in zip(s, s[1:]):
                k = max(1, int(math.dist(a, b) / 4))
                for q in range(k + 1):
                    S.append((a[0] + (b[0] - a[0]) * q / k, a[1] + (b[1] - a[1]) * q / k)); O.append(e)
T = cKDTree(np.array(S))
J = [(j['x'], j['y']) for k, j in n['junctions'].items() if j['type'].startswith('traffic_light')]
TJ = cKDTree(np.array(J))
for i in json.loads(Path(sys.argv[2]).read_text())['installations_no_controller']:
    v = reg[i]; c = np.mean([fwd(*p) for p in v['veh']], axis=0)
    d, ix = T.query(c); dj, _ = TJ.query(c); lo, la = back(*c)
    print(i, 'lanterns', len(v['veh']), 'groups', sorted(v['groups'])[:6], f'{la:.5f},{lo:.5f}', 'car lane at', round(float(d), 1), n['edges'][O[ix]]['name'][:22], O[ix][:20], 'nearest signal node', round(float(dj), 1))
