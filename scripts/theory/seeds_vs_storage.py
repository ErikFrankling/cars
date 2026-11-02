# Do jam roots sit on signal approaches too short to hold one red's arrivals? No simulation. seeds_vs_storage.py screen.json key red_s run_dir...
import sys, json, re, os
screen, key, red = sys.argv[1], sys.argv[2], float(sys.argv[3])
rows = json.load(open(screen))[key]
def short(r, f): return r['kind'] == 'signal' and r['q'] / r['lanes'] * red / 3600 >= f * r['storage'] / r['lanes']
tq = sum(r['q'] for r in rows)
sets = {'x>1': {r['edge'] for r in rows if r['x'] > 1}}
for f in (1.0, .7, .5):
    sets[f'red queue>={f:g} store'] = {r['edge'] for r in rows if short(r, f)}
sets['signal L<50'] = {r['edge'] for r in rows if r['kind'] == 'signal' and r['L'] < 50}
sets['signal L<30'] = {r['edge'] for r in rows if r['kind'] == 'signal' and r['L'] < 30}
Q = {r['edge']: r['q'] for r in rows}
print('chance = share of route flow:')
for k, s in sets.items(): print(f'  {k:22} approaches {len(s):5} chance {100*sum(Q[e] for e in s)/tq:5.1f}%')
def edge(l):
    m = re.match(r'(.*)_\d+$', l); return m.group(1) if m else l
for d in sys.argv[4:]:
    t = json.load(open(d + '/jam/seeds.json'))['top']; tot = sum(x['vehicle_hours'] for x in t) or 1
    inner = sum(x['vehicle_hours'] for x in t if x['where']['lane'].startswith(':'))
    print(os.path.basename(d), f'veh-h {tot:.0f}, inside a junction {100*inner/tot:.0f}% | ' + ' | '.join(f"{k} {100*sum(x['vehicle_hours'] for x in t if edge(x['where']['lane']) in s)/tot:.0f}%" for k, s in sets.items()))
