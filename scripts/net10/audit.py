#!/usr/bin/env python3
"""Lane and signal sanity for one cut net. Usage: audit.py NET.xml TAG OUT.json"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from scipy.spatial import cKDTree
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
netp, tag, outp = sys.argv[1:4]
n = load_net(netp)
fwd, back = tf_from_location(n['location'])
E_, J_ = n['edges'], n['junctions']
R = dict(tag=tag, junctions=len(J_), edges=len(E_))
lanes = [(e, l) for e, d in E_.items() for l in d['lanes'] if passenger(l)]
L = np.array([l['length'] for _, l in lanes])
pe = {e for e, _ in lanes}
R['passenger_lanes'] = len(L); R['lane_km'] = round(float(L.sum()) / 1000, 1)
for th in (7.5, 12, 25):
    R[f'lanes_under_{th}'] = int((L < th).sum())
    R[f'edges_under_{th}'] = len({e for (e, l) in lanes if l['length'] < th})
R['lane_median_m'] = round(float(np.median(L)), 1)
tlnodes = collections.defaultdict(set); app = collections.defaultdict(set)
out = collections.defaultdict(list); into = collections.defaultdict(list)
for c in n['conns']:
    if c['frm'] in E_:
        out[c['frm']].append(c); into[c['to']].append(c)
        if c['tls']:
            tlnodes[c['tls']].add(E_[c['frm']]['to']); app[c['tls']].add(c['frm'])
sig_app = {c['frm'] for c in n['conns'] if c['tls']}
R['signal_approach_edges'] = len(sig_app)
R['signal_approach_edges_under_7.5'] = sum(1 for e in sig_app if E_[e]['lanes'] and min(l['length'] for l in E_[e]['lanes']) < 7.5)
R['signal_approach_edges_under_25'] = sum(1 for e in sig_app if E_[e]['lanes'] and min(l['length'] for l in E_[e]['lanes']) < 25)
# junction-to-junction links shorter than a car where both ends make a decision
R['signal_to_signal_links_under_25'] = sum(1 for e, d in E_.items() if d['lanes'] and min(l['length'] for l in d['lanes']) < 25 and J_.get(d['frm'], {}).get('type', '').startswith('traffic_light') and J_.get(d['to'], {}).get('type', '').startswith('traffic_light'))
R['signal_to_signal_links_under_7.5'] = sum(1 for e, d in E_.items() if d['lanes'] and min(l['length'] for l in d['lanes']) < 7.5 and J_.get(d['frm'], {}).get('type', '').startswith('traffic_light') and J_.get(d['to'], {}).get('type', '').startswith('traffic_light'))
cyc = {k: sum(p[0] for p in v['phases']) for k, v in n['tls'].items()}
R['controllers'] = len(n['tls']); R['tl_nodes'] = sum(j['type'].startswith('traffic_light') for j in J_.values())
R['cycle_max'] = max(cyc.values()) if cyc else 0
R['cycles_over_120'] = sum(v > 120 for v in cyc.values())
R['controllers_one_approach'] = sum(len(app[t]) == 1 for t in n['tls'])
R['controllers_two_approach'] = sum(len(app[t]) == 2 for t in n['tls'])
# Register: the 07 metric, controllers whose node lies within 40 m of a register point; vehicle-lantern installations are the ones that stop cars
reg = register()
nodes_by_tl = {t: [(J_[j]['x'], J_[j]['y']) for j in s if j in J_] for t, s in tlnodes.items()}
tid = [t for t, v in nodes_by_tl.items() if v]
pts = [p for t in tid for p in nodes_by_tl[t]]; own = [t for t in tid for _ in nodes_by_tl[t]]
Tt = cKDTree(np.array(pts)) if pts else None
def touching(points, r=40):
    s = set()
    for q in Tt.query_ball_point(np.array([fwd(*p) for p in points]), r):
        s.update(own[i] for i in q)
    return s
R['register_installations_in_box'] = len(reg)
vr = {k: v for k, v in reg.items() if v['veh']}
R['register_with_vehicle_lanterns'] = len(vr)
cnt = collections.Counter(); many = {}
matched = set(); zero = []
for k, v in vr.items():
    s = touching(v['veh']); matched |= s; cnt[min(len(s), 3)] += 1
    if len(s) >= 3: many[k] = len(s)
    if not s: zero.append(k)
R['vehicle_installations_with_0_1_2_3plus_controllers'] = [cnt[0], cnt[1], cnt[2], cnt[3]]
R['installations_no_controller'] = sorted(zero)
R['controllers_not_near_vehicle_lantern'] = sum(t not in matched for t in tid)
allm = set()
for v in reg.values():
    allm |= touching(v['all'])
R['controllers_not_near_any_register_point'] = sum(t not in allm for t in tid)
# Lane connectivity
st = 0; st_sig = 0; uonly = 0; uonly_sig = 0
for e, d in E_.items():
    if e not in pe or not out.get(e):
        continue
    used = collections.defaultdict(set)
    for c in out[e]:
        used[c['fl']].add(c['dir'])
    for l in d['lanes']:
        if not passenger(l):
            continue
        if l['i'] not in used:
            st += 1; st_sig += e in sig_app
        elif used[l['i']] <= {'t'}:
            uonly += 1; uonly_sig += e in sig_app
R['stranded_passenger_lanes'] = st; R['stranded_on_signal_approach'] = st_sig
R['uturn_only_lanes'] = uonly; R['uturn_only_on_signal_approach'] = uonly_sig
R['dead_end_passenger_edges'] = sum(1 for e in pe if not out.get(e))
R['source_passenger_edges'] = sum(1 for e in pe if not into.get(e))
idx = {e: i for i, e in enumerate(sorted(pe))}
a = [idx[c['frm']] for c in n['conns'] if c['frm'] in idx and c['to'] in idx]; b = [idx[c['to']] for c in n['conns'] if c['frm'] in idx and c['to'] in idx]
nc, lab = connected_components(csr_matrix((np.ones(len(a)), (a, b)), shape=(len(idx), len(idx))), directed=True, connection='strong')
R['largest_scc_share'] = round(float(np.bincount(lab).max()) / len(idx), 4)
R['movements_edge_pairs'] = len({(c['frm'], c['to']) for c in n['conns'] if c['frm'] in pe and c['to'] in pe})
R['uturn_edge_pairs'] = len({(c['frm'], c['to']) for c in n['conns'] if c['dir'] == 't' and c['frm'] in pe})
dia = []
for j in J_.values():
    if j['shape']:
        s = np.array(j['shape']); dia.append(float(np.hypot(*(s.max(0) - s.min(0)))))
R['junction_diag_p50_p99_max'] = [round(float(x), 1) for x in np.percentile(dia, [50, 99, 100])]
R['junctions_over_60m'] = sum(d > 60 for d in dia)
il = np.array(list(n['internal'].values())) if n['internal'] else np.zeros(1)
R['internal_lanes_over_60m'] = int((il > 60).sum())
R['bus_only_lanes'] = sum(1 for d in E_.values() for l in d['lanes'] if l['allow'] and 'bus' in l['allow'].split() and 'passenger' not in l['allow'].split())
Path(outp).write_text(json.dumps(R, indent=1))
for k in R:
    print(k, R[k] if not isinstance(R[k], list) or len(R[k]) < 8 else f'{len(R[k])} items')
