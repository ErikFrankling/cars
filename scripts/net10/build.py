#!/usr/bin/env python3
"""Register-first net: signals come from the city's installations, junctions are contracted so no link is shorter than a car.
Usage: build.py S1_DIR OUT_DIR --join M [--iters N] [--cluster-max M] [--split-over S]
Reads stage 1 plain files, writes OUT_DIR/net.xml and OUT_DIR/report.json. Report data-hunt/10."""
import sys, os, argparse, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from scipy.spatial import cKDTree
CAR = 7.5
ap = argparse.ArgumentParser()
ap.add_argument('s1'); ap.add_argument('out')
ap.add_argument('--join', type=float, default=12.0, help='contract links whose built lanes are shorter than this')
ap.add_argument('--cluster-max', type=float, default=70.0)
ap.add_argument('--iters', type=int, default=5)
ap.add_argument('--split-over', type=float, default=120.0)
ap.add_argument('--signal-reach', type=float, default=45.0)
ap.add_argument('--stopline-reach', type=float, default=40.0)
ap.add_argument('--lantern-reach', type=float, default=30.0)
ap.add_argument('--no-promote', action='store_true')
ap.add_argument('--per-node', action='store_true', help='one generated program per node; merge_tls.py makes them one controller')
ap.add_argument('--extra', default='', help='extra netconvert flags for the final pass')
A = ap.parse_args()
out = Path(A.out); out.mkdir(parents=True, exist_ok=True); s1 = Path(A.s1)
tree = E.parse(str(s1 / 's1.nod.xml')); root = tree.getroot()
fwd, back = tf_from_location(dict(root.find('location').attrib))
nodes = {n.get('id'): n for n in root.findall('node')}
xy = {k: (float(n.get('x')), float(n.get('y'))) for k, n in nodes.items()}
er = E.parse(str(s1 / 's1.edg.xml')).getroot()
edges = {}; ins, outs = collections.defaultdict(list), collections.defaultdict(list)
for e in er.findall('edge'):
    f, t = e.get('from'), e.get('to')
    sh = parse_shape(e.get('shape')) if e.get('shape') else [xy[f], xy[t]]
    edges[e.get('id')] = dict(frm=f, to=t, len=plen(sh), speed=float(e.get('speed', 13.9)))
    outs[f].append(e.get('id')); ins[t].append(e.get('id'))
round_nodes, round_edges = set(), set()
for r in er.findall('roundabout'):
    round_nodes |= set(r.get('nodes').split()); round_edges |= set(r.get('edges').split())
nbrs = {k: {edges[x]['frm'] for x in ins[k]} | {edges[x]['to'] for x in outs[k]} for k in nodes}
crossing = {k for k in nodes if len(nbrs[k]) >= 3}
isig = lambda n: 'traffic_light' in (n.get('type') or '')
rep = dict(stage1_nodes=len(nodes), stage1_edges=len(edges), stage1_tl_nodes=sum(isig(n) for n in nodes.values()), args=vars(A))

# 1. Which installation does each OSM signal node belong to? Same evidence as report 07.
reg = register()
pts, pid = [], []
for k, v in reg.items():
    for p in v['all']:
        pts.append(fwd(*p)); pid.append(k)
Tp = cKDTree(np.array(pts))
vreg = {k: [fwd(*p) for p in v['veh']] for k, v in reg.items() if v['veh']}
allreg = {k: [fwd(*p) for p in v['all']] for k, v in reg.items()}
rep['register_all'] = len(reg); rep['register_vehicle'] = len(vreg)
nv = [fwd(*p) for p in nvdb_signal()]; Tn = cKDTree(np.array(nv))
stat = collections.Counter(); raw = {}
nvs = []
for k, n in nodes.items():
    if not isig(n):
        continue
    d, i = Tp.query(xy[k])
    if d <= A.signal_reach:
        raw[k] = pid[i]; stat['osm signal with register point near'] += 1
    elif Tn.query(xy[k])[0] <= 60:
        nvs.append(k); stat['osm signal with NVDB only'] += 1
    else:
        stat['osm signal with no evidence: removed'] += 1
if nvs:
    par = {k: k for k in nvs}
    def fd(a):
        while par[a] != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    for a, b in cKDTree(np.array([xy[k] for k in nvs])).query_pairs(60):
        par[fd(nvs[a])] = fd(nvs[b])
    for k in nvs:
        raw[k] = 'N' + re.sub(r'\W', '', fd(k))[:20]

# 2. A signal on a stretch of road is a stop line of the crossing beside it, unless nothing says so; then it is a real mid-block signal.
def road_walk(k, reach):
    seen = {k: 0.0}; q = [k]; found = []
    while q:
        c = q.pop()
        for e in ins[c] + outs[c]:
            o = edges[e]['frm'] if edges[e]['to'] == c else edges[e]['to']
            dd = seen[c] + edges[e]['len']
            if dd > reach or (o in seen and seen[o] <= dd):
                continue
            seen[o] = dd
            if o in crossing:
                found.append((dd, o))
            else:
                q.append(o)
    return sorted(found)
sig = {k: v for k, v in raw.items() if k in crossing}
mid = {}
def near_lantern(o, inst, r):
    return inst in allreg and min(math.dist(xy[o], p) for p in allreg[inst]) <= r
for k, inst in raw.items():
    if k in crossing:
        continue
    f = road_walk(k, A.stopline_reach)
    pick = next((o for _, o in f if sig.get(o) == inst), None)
    if pick is None:
        pick = next((o for _, o in f if o not in sig and o not in round_nodes and near_lantern(o, inst, A.lantern_reach)), None)
    if pick is None:
        mid[k] = inst; stat['mid-block signal kept'] += 1
    else:
        sig[pick] = inst; stat['stop-line node moved to its crossing'] += 1
# 3. Installations with vehicle lanterns that OSM did not mark.
promoted = []
if not A.no_promote:
    have = set(sig.values()) | set(mid.values())
    cand = [k for k in crossing if k not in sig and k not in round_nodes]
    Tc = cKDTree(np.array([xy[k] for k in cand]))
    for inst, ls in vreg.items():
        if inst in have:
            continue
        c = np.mean(np.array(ls), axis=0)
        d, i = Tc.query(c)
        if d <= 35:
            sig[cand[i]] = inst; promoted.append((inst, cand[i], round(float(d), 1))); stat['installation with no OSM signal: promoted'] += 1
        else:
            # A spread-out installation: the crossing nearest any of its lanterns.
            dd, ii = Tc.query(np.array(ls))
            b = int(np.argmin(dd))
            if dd[b] <= 30 and cand[ii[b]] not in sig:
                sig[cand[ii[b]]] = inst; promoted.append((inst, cand[ii[b]], round(float(dd[b]), 1))); stat['installation with no OSM signal: promoted by a lantern'] += 1
            else:
                stat['installation with no OSM signal: no crossing within 30 m of a lantern'] += 1
rep['stat'] = dict(stat); rep['promoted'] = promoted

# 4. Contract, measuring the lanes netconvert actually builds, since junction shapes eat road length.
parent = {k: k for k in nodes}
def find(a):
    while parent[a] != a:
        parent[a] = parent[parent[a]]; a = parent[a]
    return a
def members():
    m = collections.defaultdict(list)
    for k in nodes:
        m[find(k)].append(k)
    return m
def run(cmd, log):
    p = subprocess.run(cmd, capture_output=True, text=True)
    (out / log).write_text(p.stdout + p.stderr)
    if p.returncode:
        sys.exit(f'netconvert failed: {log}\n' + p.stderr[-1500:])
BASE = ['netconvert', '--output.street-names', 'true', '--tls.default-type', 'actuated', '--junctions.corner-detail', '3', '--offset.disable-normalization', 'true', '--no-turnarounds', 'false', '--no-warnings', 'false']
def write_a():
    t2 = E.parse(str(s1 / 's1.nod.xml')); r2 = t2.getroot()
    for n in r2.findall('node'):
        k = n.get('id')
        for a in ('tl', 'tlType', 'tlLayout', 'controlledInner'):
            if a in n.attrib:
                del n.attrib[a]
        if isig(n):
            n.set('type', 'priority')
        if k in mid:
            n.set('type', 'traffic_light'); n.set('tl', 'S' + mid[k] if mid[k][0] != 'N' else mid[k]); n.set('tlType', 'actuated')
    cid = {}
    for root_, ms in members().items():
        if len(ms) > 1:
            j = E.SubElement(r2, 'join'); cid[root_] = 'C' + re.sub(r'\W', '', root_)[:30]
            j.set('id', cid[root_]); j.set('nodes', ' '.join(sorted(ms)))
            # A joined node can look like plain road; a signal on it must survive geometry removal.
            if any(k in sig or k in mid for k in ms):
                j.set('type', 'traffic_light')
    t2.write(str(out / 'a.nod.xml'))
    return cid
log = []
for it in range(A.iters + 1):
    cid = write_a()
    run(BASE + ['--node-files', str(out / 'a.nod.xml'), '--edge-files', str(s1 / 's1.edg.xml'), '--connection-files', str(s1 / 's1.con.xml'), '--type-files', str(s1 / 's1.typ.xml'),
                '--geometry.remove', '--roundabouts.guess', 'false', '-o', str(out / 'a.net.xml'), '--plain-output-prefix', str(out / 'a')], 'a.log')
    n = load_net(out / 'a.net.xml')
    back_id = {v: k for k, v in cid.items()}
    def rep_of(j):
        return find(back_id.get(j, j)) if back_id.get(j, j) in parent else None
    sh = []
    for e, d in n['edges'].items():
        if not d['lanes']:
            continue
        m = min(l['length'] for l in d['lanes'])
        if m < A.join:
            sh.append((m, e, d))
    sh.sort(key=lambda s: s[0])
    did = 0; sk = collections.Counter()
    ms = members()
    def inst_of(root_):
        return {sig[k] for k in ms[root_] if k in sig} | {mid[k] for k in ms[root_] if k in mid}
    for m, e, d in sh:
        a, b = rep_of(d['frm']), rep_of(d['to'])
        if a is None or b is None or a == b:
            sk['unmapped or same'] += 1; continue
        if max(l['speed'] for l in d['lanes']) > 19.5:
            sk['fast road'] += 1; continue
        if any(x.split('#')[0] in {r.split('#')[0] for r in round_edges} for x in e.split('+')) or set(ms[a]) & round_nodes or set(ms[b]) & round_nodes:
            sk['roundabout'] += 1; continue
        ia, ib = inst_of(a), inst_of(b)
        if ia and ib and not (ia & ib) and m >= CAR:
            sk['two installations, link holds a car'] += 1; continue
        pp = np.array([xy[k] for k in ms[a] + ms[b]])
        if float(np.hypot(*(pp.max(0) - pp.min(0)))) > A.cluster_max:
            sk['cluster too big'] += 1; continue
        parent[a] = b; ms[b] = ms[a] + ms[b]; ms[a] = []
        did += 1
    log.append(dict(iter=it, short=len(sh), joined=did, skipped=dict(sk)))
    print(log[-1], flush=True)
    if did == 0:
        break
rep['contract'] = log
rep['clusters'] = sum(len(v) > 1 for v in members().values())

# 5. Controllers: every node of an installation shares one id. Merging two installations is recorded, not hidden.
def final_id(k):
    r = find(k)
    return cid.get(r, k)
ctrl = collections.defaultdict(set)
for k, inst in list(sig.items()) + list(mid.items()):
    ctrl[final_id(k)].add(inst)
merged = {j: sorted(v) for j, v in ctrl.items() if len(v) > 1}
rep['junctions_holding_two_installations'] = merged
def pick_inst(v):
    return sorted(v, key=lambda i: (-len(vreg.get(i, [])), i))[0]
tlname = lambda i: i if i[0] == 'N' else 'S' + i
tl_of = {j: tlname(pick_inst(v)) for j, v in ctrl.items()}
if A.per_node:
    seen_i = collections.Counter()
    for j in sorted(tl_of):
        seen_i[tl_of[j]] += 1
        tl_of[j] = f'{tl_of[j]}__{seen_i[tl_of[j]]}'
for split_round in range(4):
    t3 = E.parse(str(out / 'a.nod.xml')); r3 = t3.getroot()
    known = set()
    for n3 in r3.findall('node'):
        j = n3.get('id'); known.add(j)
        for a in ('tl', 'tlType', 'controlledInner'):
            if a in n3.attrib:
                del n3.attrib[a]
        if j in tl_of:
            n3.set('type', 'traffic_light'); n3.set('tl', tl_of[j]); n3.set('tlType', 'actuated')
        elif 'traffic_light' in (n3.get('type') or ''):
            n3.set('type', 'priority')
    rep['controller_nodes_lost'] = sorted(set(tl_of) - known)
    t3.write(str(out / 'b.nod.xml'))
    run(BASE + ['--node-files', str(out / 'b.nod.xml'), '--edge-files', str(out / 'a.edg.xml'), '--connection-files', str(out / 'a.con.xml'), '--type-files', str(out / 'a.typ.xml'),
                '-o', str(out / 'net.xml')] + A.extra.split(), 'b.log')
    n = load_net(out / 'net.xml')
    cyc = {k: sum(p[0] for p in v['phases']) for k, v in n['tls'].items()}
    big = {k for k, v in cyc.items() if v > A.split_over}
    print('round', split_round, 'controllers', len(cyc), 'over', A.split_over, sorted(cyc[k] for k in big), flush=True)
    if not big:
        break
    for t in big:
        js = [j for j, v in tl_of.items() if v == t]
        if len(js) < 2:
            continue
        arr = np.array([(n['junctions'][j]['x'], n['junctions'][j]['y']) for j in js if j in n['junctions']])
        # Keep the installation's name as prefix: same register id, same cycle, offset 0.
        far = int(np.argmax(np.hypot(*(arr - arr[0]).T)))
        for j, p in zip(js, arr):
            tl_of[j] = t + ('_a' if math.dist(p, arr[0]) <= math.dist(p, arr[far]) else '_b')
rep['tl_of'] = tl_of
rep['cycles'] = sorted(cyc.values())[-10:]
(out / 'report.json').write_text(json.dumps(rep, indent=1))
print({k: rep[k] for k in ('stat', 'clusters', 'controller_nodes_lost')}, 'two-install junctions', len(merged), 'promoted', len(promoted))
