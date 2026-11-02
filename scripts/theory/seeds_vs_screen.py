# Do jam roots from saved runs sit where the static screen says movements are over capacity? No simulation.
# seeds_vs_screen.py net.net.xml screen.json key run_dir...
import sys, json, re, os, collections
import xml.etree.ElementTree as ET
net, screen, key = sys.argv[1:4]
nxt = collections.defaultdict(set); prv = collections.defaultdict(set)
for ev, el in ET.iterparse(net, events=('end',)):
    if el.tag == 'connection' and not el.get('from', ':').startswith(':') and not el.get('to', ':').startswith(':'):
        nxt[el.get('from')].add(el.get('to')); prv[el.get('to')].add(el.get('from'))
    if el.tag in ('edge', 'junction', 'connection', 'tlLogic'): el.clear()
rows = json.load(open(screen))[key]
q = {r['edge']: r['q'] for r in rows}; tq = sum(q.values())
def grow(s, hops):
    s = set(s)
    for _ in range(hops):
        s |= {b for a in s for b in nxt[a]} | {b for a in s for b in prv[a]}
    return s
over = {r['edge'] for r in rows if r['x'] > 1}
near = {r['edge'] for r in rows if r['x'] > .85}
sets = {'x>1': over, 'x>1 +1 hop': grow(over, 1), 'x>1 +2 hops': grow(over, 2), 'x>.85': near, 'x>.85 +1 hop': grow(near, 1)}
print('sets, with chance level = share of all route flow through them:')
for k, s in sets.items(): print(f'  {k:14} edges {len(s):5}  chance {100*sum(q.get(e,0) for e in s)/tq:5.1f}%')
def edge(lane):
    m = re.match(r'(.*)_\d+$', lane); return m.group(1) if m else lane
for d in sys.argv[4:]:
    s = json.load(open(d + '/jam/seeds.json'))
    tops = s['top']; tot = sum(t['vehicle_hours'] for t in tops) or 1
    out = []
    for k, st in sets.items():
        vh = sum(t['vehicle_hours'] for t in tops if edge(t['where']['lane']) in st)
        out.append(f'{k} {100*vh/tot:3.0f}%')
    early = [t for t in tops if t['first'] < 8 * 3600]
    ev = sum(t['vehicle_hours'] for t in early) or 1
    eo = sum(t['vehicle_hours'] for t in early if edge(t['where']['lane']) in sets['x>1 +1 hop'])
    known = sum(1 for t in tops if edge(t['where']['lane']) in q)
    print(f"{os.path.basename(d):13} roots {s['seeds']:5} top {len(tops):3} on-screen {known:3} veh-h {tot:6.0f} | " + ' | '.join(out) + f" | before 08:00, x>1 +1 hop {100*eo/ev:3.0f}%")
    kinds = collections.Counter()
    for t in tops:
        kinds[t['where'].get('decider') or max(t['kinds'], key=t['kinds'].get)] += t['vehicle_hours']
    print('              held by ' + ', '.join(f'{k} {100*v/tot:.0f}%' for k, v in kinds.most_common(4)))
