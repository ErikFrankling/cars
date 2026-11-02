#!/usr/bin/env python3
"""Lists what is left under a car length, and checks the known bad sites. Usage: stubs.py NET.xml S1_DIR"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
n = load_net(sys.argv[1]); E_ = n['edges']; J = n['junctions']
er = E.parse(sys.argv[2] + '/s1.edg.xml').getroot(); rb = set()
for r in er.findall('roundabout'):
    rb |= {x.split('#')[0] for x in r.get('edges').split()}
rows = collections.Counter(); ex = []
for e, d in E_.items():
    l = [x for x in d['lanes'] if passenger(x)]
    if not l or min(x['length'] for x in l) >= 7.5:
        continue
    round_ = any(x.lstrip('-').split('#')[0] in rb or x.split('#')[0] in rb for x in e.split('+'))
    s = J.get(d['frm'], {}).get('type', ''), J.get(d['to'], {}).get('type', '')
    sig = sum(t.startswith('traffic_light') for t in s)
    fast = max(x['speed'] for x in l) > 19.5
    k = 'roundabout' if round_ else 'fast road' if fast else f'{sig} signal ends'
    rows[k] += 1
    if not round_:
        ex.append((round(min(x['length'] for x in l), 1), e[:26], d['name'][:22], s, k))
print(dict(rows))
for x in sorted(ex)[:30]:
    print(x)
