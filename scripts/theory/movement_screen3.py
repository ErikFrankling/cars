#!/usr/bin/env python3
"""Static screen of MATSim's routes against this map's movement capacities. No simulation, nothing written outside /tmp.
usage: python3 -I movement_screen.py NET.net.xml ROUTES_F01.rou.gz MATSIM_NETWORK.xml.gz OUT.json

Movement capacity:
  signal, protected:   s * f_dir * green share (nominal durations of the program in the net)
  signal, permissive:  green share * Siegloch against opposing flow during that green
  priority, major:     s_free per lane
  priority, minor:     Siegloch against the flows the net's request table says it yields to
  right before left:   Siegloch with shorter gaps, screen only
Lane sharing: per incoming edge, find the split of each movement over its allowed lanes that minimises the worst lane's utilisation.
"""
import collections
import gzip
import json
import math
import re
import sys
from xml.etree.ElementTree import iterparse

net_f, routes_f, ms_f, out_f = sys.argv[1:5]
S_SETS = {'s1640': 1640.0, 's1900': 1900.0}
F_DIR = {'s': 1.0, 'r': 0.85, 'R': 0.85, 'l': 0.90, 'L': 0.90, 't': 0.7, 'T': 0.7}
S_FREE = 1900.0
HOURS = (6, 7, 8, 9, 12, 15, 16, 17, 18)
SCALE = 1.0
GW = 1.0
TG = {'m_right': (5.9, 3.0), 'm_cross': (6.5, 3.4), 'major_left': (5.5, 2.6), 'rbl': (4.5, 2.5), 'stop': (6.5, 3.5)}


def car_ok(a):
    al, dis = a.get('allow', ''), a.get('disallow', '')
    if al:
        return bool({'passenger', 'all'} & set(al.split()))
    return 'passenger' not in dis.split()


edges, conns, tl, junc = {}, [], {}, {}
for _, e in iterparse(net_f, events=('end',)):
    t = e.tag
    if t == 'edge':
        if e.get('function') != 'internal':
            ls = e.findall('lane')
            lanes = [dict(i=int(l.get('index')), speed=float(l.get('speed')), length=float(l.get('length')), car=car_ok(l.attrib)) for l in ls]
            edges[e.get('id')] = dict(frm=e.get('from'), to=e.get('to'), type=(e.get('type') or '').replace('highway.', ''), name=e.get('name', ''), lanes=lanes)
        e.clear()
    elif t == 'connection':
        if not e.get('from', '').startswith(':'):
            conns.append(dict(frm=e.get('from'), to=e.get('to'), fl=int(e.get('fromLane')), tl=int(e.get('toLane')), via=e.get('via', ''), ctrl=e.get('tl', ''), idx=int(e.get('linkIndex', -1)), dir=e.get('dir', ''), state=e.get('state', '')))
        e.clear()
    elif t == 'tlLogic':
        tl[e.get('id')] = [(float(p.get('duration')), p.get('state')) for p in e.findall('phase')]
        e.clear()
    elif t == 'junction':
        if e.get('type') != 'internal':
            junc[e.get('id')] = dict(type=e.get('type'), inc=(e.get('incLanes') or '').split(), intl=(e.get('intLanes') or '').split(), req={int(r.get('index')): r.get('response') for r in e.findall('request')}, foes={int(r.get('index')): r.get('foes') for r in e.findall('request')})
        e.clear()
print('edges', len(edges), 'connections', len(conns), 'controllers', len(tl), 'junctions', len(junc), flush=True)
car_edges = {k: v for k, v in edges.items() if any(l['car'] for l in v['lanes'])}


def n_lanes(k):
    return sum(1 for l in car_edges[k]['lanes'] if l['car'])


tt = {}
for k, v in car_edges.items():
    l = [x for x in v['lanes'] if x['car']][0]
    tt[k] = l['length'] / max(l['speed'], 1) * 1.3

# flows from the 10% routes, x10, per movement and hour, and per edge
mv = collections.Counter()
ed = collections.Counter()
n_veh = 0
pat = re.compile(r'depart="([^"]+)".*edges="([^"]+)"')
with gzip.open(routes_f, 'rt') as f:
    for line in f:
        m = pat.search(line)
        if not m:
            continue
        n_veh += 1
        t = float(m[1])
        r = m[2].split()
        for a, b in zip(r, r[1:] + [None]):
            h = int(t // 3600) % 24
            if h in HOURS:
                ed[(a, h)] += 10
                if b is not None:
                    mv[(a, b, h)] += 10
            t += tt.get(a, 5.0)
print('vehicles in the 10% file', n_veh, flush=True)

# connections grouped by incoming edge -> movement -> lanes
by_edge = collections.defaultdict(lambda: collections.defaultdict(dict))
via_of = {}
for c in conns:
    if c['frm'] in car_edges and c['to'] in car_edges:
        l = by_edge[c['frm']][c['to']]
        cur = l.get(c['fl'])
        if cur is None:
            l[c['fl']] = c
        via_of.setdefault(c['via'], c)


def green_share(ctrl, idx):
    ph = tl.get(ctrl)
    if not ph or idx < 0:
        return 0.0, 0.0
    cyc = sum(d for d, _ in ph)
    prot = sum(d for d, s in ph if idx < len(s) and s[idx] == 'G')
    perm = sum(d for d, s in ph if idx < len(s) and s[idx] == 'g')
    return prot / max(cyc, 1), perm / max(cyc, 1)


def siegloch(qp, tg, tf):
    return math.exp(-(qp / 3600.0) * (tg - tf / 2)) * 3600.0 / tf


def conflict_flow(c, h):
    """Flow of the movements this connection yields to, from the junction's request table."""
    j = junc.get(car_edges[c['frm']]['to'])
    if not j or not c['via'] or c['via'] not in j['intl']:
        return None
    i = j['intl'].index(c['via'])
    resp = j['req'].get(i)
    if resp is None:
        return None
    q = 0.0
    seen = set()
    n = len(resp)
    for bit in range(n):
        if resp[n - 1 - bit] == '1' and bit < len(j['intl']):
            o = via_of.get(j['intl'][bit])
            if o and (o['frm'], o['to']) not in seen:
                seen.add((o['frm'], o['to']))
                q += mv.get((o['frm'], o['to'], h), 0) * SCALE
    return q


def capacity(c, h, s):
    """veh/h for this connection's lane if it served only this movement."""
    f = F_DIR.get(c['dir'], 1.0)
    if c['ctrl']:
        prot, perm = green_share(c['ctrl'], c['idx'])
        cap = s * f * prot
        if perm > 0:
            qp = conflict_flow(c, h) or 0.0
            qg = qp / max(perm + prot, .05)
            cap += perm * min(s * f, siegloch(qg, 5.0, 2.5))
        return cap, 'signal'
    st = c['state']
    kind = 'major'
    if st in ('M', 'O', 'o'):
        return S_FREE * f if st == 'M' else S_FREE * f, 'major'
    qp = conflict_flow(c, h) or 0.0
    if st == 'm':
        key = 'major_left' if c['dir'] in ('l', 'L') and car_edges[c['frm']]['type'] in ('primary', 'secondary', 'trunk', 'motorway', 'tertiary') else ('m_right' if c['dir'] in ('r', 'R') else 'm_cross')
        kind = 'minor'
    elif st == '=':
        key, kind = 'rbl', 'rbl'
    elif st in ('s', 'w'):
        key, kind = 'stop', 'stop'
    else:
        key, kind = 'm_cross', 'minor'
    tg, tf = TG[key]
    return min(S_FREE * f, GW * siegloch(qp, tg, tf)), kind


def approach_vc(edge, h, s):
    """Min-max lane utilisation over the split of movements across lanes. Returns (vc, kind of the tightest movement, worst movement)."""
    moves = by_edge.get(edge)
    if not moves:
        return None
    dem = {}
    kinds = {}
    lane_cap = collections.defaultdict(dict)
    for b, lanes in moves.items():
        q = mv.get((edge, b, h), 0) * SCALE
        if q <= 0:
            continue
        dem[b] = q
        for fl, c in lanes.items():
            cap, kind = capacity(c, h, s)
            lane_cap[fl][b] = max(cap, 1.0)
            kinds[b] = kind
    if not dem:
        return None
    # start: equal split over allowed lanes, then shift from the most used lane to the least used, 60 passes
    x = {b: {fl: dem[b] / sum(1 for f in lane_cap if b in lane_cap[f]) for fl in lane_cap if b in lane_cap[fl]} for b in dem}
    def util():
        return {fl: sum(x[b].get(fl, 0) / lane_cap[fl][b] for b in lane_cap[fl] if b in x) for fl in lane_cap}
    for _ in range(60):
        u = util()
        moved = False
        for b in x:
            if len(x[b]) < 2:
                continue
            hi = max(x[b], key=lambda f: u[f])
            lo = min(x[b], key=lambda f: u[f])
            if u[hi] - u[lo] > 1e-3 and x[b][hi] > 0:
                d = min(x[b][hi], (u[hi] - u[lo]) / (1 / lane_cap[hi][b] + 1 / lane_cap[lo][b]) / 2)
                x[b][hi] -= d
                x[b][lo] += d
                u[hi] -= d / lane_cap[hi][b]
                u[lo] += d / lane_cap[lo][b]
                moved = True
        if not moved:
            break
    u = util()
    worst = max(u, key=u.get)
    bm = max((b for b in lane_cap[worst] if b in x), key=lambda b: x[b].get(worst, 0) / lane_cap[worst][b])
    return u[worst], kinds[bm], bm, dem[bm], sum(dem.values())


# MATSim's own capacity and lanes on the same edge ids
ms = {}
lp = re.compile(r'<link id="([^"]+)" from="[^"]+" to="[^"]+" length="[^"]+" freespeed="([^"]+)" capacity="([^"]+)" permlanes="([^"]+)"')
aq = re.compile(r'name="(allowed_speed|maxInflowUsedInQsim)"[^>]*>([^<]*)<')
cur = None
with gzip.open(ms_f, 'rt') as f:
    for line in f:
        m = lp.search(line)
        if m:
            cur = m[1]
            ms[cur] = dict(fs=float(m[2]), cap=float(m[3]), lanes=float(m[4]))
        elif cur:
            a = aq.search(line)
            if a:
                ms[cur][a[1]] = float(a[2])
            elif '</link>' in line:
                cur = None
print('matsim links', len(ms), flush=True)

res = {'vehicles_10pct': n_veh, 'edges_car': len(car_edges), 'controllers': len(tl)}
sig_end = {k for k, v in car_edges.items() if junc.get(v['to'], {}).get('type', '').startswith('traffic_light')}
res['edges_ending_at_signal'] = len(sig_end)

# what MATSim's capacity says on signal approaches and elsewhere, per lane, by road class
tab = collections.defaultdict(list)
for k, v in car_edges.items():
    if k in ms:
        tab[(v['type'], 'signal' if k in sig_end else 'other')].append(ms[k]['cap'] / max(ms[k]['lanes'], 1))
def q(v, p):
    v = sorted(v)
    return round(v[min(len(v) - 1, int(p * len(v)))])
res['matsim_cap_per_lane'] = {f'{a}|{b}': dict(n=len(v), p10=q(v, .1), p50=q(v, .5), p90=q(v, .9)) for (a, b), v in sorted(tab.items()) if len(v) >= 10}
# speed factor by class, signal or not
tab = collections.defaultdict(list)
for k, v in car_edges.items():
    if k in ms and ms[k].get('allowed_speed'):
        tab[(v['type'], 'signal' if k in sig_end else 'other')].append(ms[k]['fs'] / ms[k]['allowed_speed'])
res['matsim_speed_factor'] = {f'{a}|{b}': dict(n=len(v), p50=round(sorted(v)[len(v) // 2], 2)) for (a, b), v in sorted(tab.items()) if len(v) >= 10}


def sweep(h, s, scale, gw):
    global SCALE, GW
    SCALE, GW = scale, gw
    cnt, tot, excess, worst = collections.Counter(), collections.Counter(), collections.Counter(), []
    for k in car_edges:
        r = approach_vc(k, h, s)
        if r is None:
            continue
        vc, kind, bm, qm, qa = r
        tot[kind] += 1
        if vc > 1:
            cnt[kind] += 1
            excess[kind] += qa * (1 - 1 / vc)
            worst.append((round(vc, 2), kind, k, car_edges[k]['name'], car_edges[k]['type'], bm, round(qm), round(qa), n_lanes(k), car_edges[k]['to']))
    SCALE, GW = 1.0, 1.0
    worst.sort(reverse=True)
    return dict(approaches=dict(tot), vc_gt_1=dict(cnt), excess_veh_h={a: round(b) for a, b in excess.items()}, worst=worst)


def storage_check(h, scale):
    """Signal approaches whose queue at the end of red does not fit on the edge: arrivals in red against lanes x length / 7.5 m."""
    bad, tot, excess = 0, 0, []
    for k in car_edges:
        moves = by_edge.get(k)
        if not moves:
            continue
        ctrl = None
        lanes = n_lanes(k)
        L = [x for x in car_edges[k]['lanes'] if x['car']][0]['length']
        worst_red = 0.0
        for b, ll in moves.items():
            q = mv.get((k, b, h), 0) * scale
            if q <= 0:
                continue
            for fl, c in ll.items():
                if c['ctrl']:
                    ctrl = c['ctrl']
                    ph = tl[c['ctrl']]
                    cyc = sum(d for d, _ in ph)
                    prot, perm = green_share(c['ctrl'], c['idx'])
                    red = cyc * (1 - prot - perm)
                    worst_red = max(worst_red, q / len(ll) * red / 3600)   # vehicles per lane for this movement
        if ctrl is None or worst_red == 0:
            continue
        tot += 1
        store = L / 7.5
        if worst_red > store:
            bad += 1
            excess.append((round(worst_red / store, 1), k, car_edges[k]['name'], round(L), lanes))
    excess.sort(reverse=True)
    return tot, bad, excess[:12]

for h in (8, 16):
    row = {}
    for scale in (1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1):
        r = sweep(h, 1640.0, scale, 1.0)
        near = 0
        # near capacity
        global_SCALE = scale
        SCALE = scale
        vcs = []
        for k in car_edges:
            x = approach_vc(k, h, 1640.0)
            if x is not None:
                vcs.append((x[0], x[1]))
        SCALE = 1.0
        n85 = collections.Counter(kd for v, kd in vcs if v > .85)
        n100 = collections.Counter(kd for v, kd in vcs if v > 1.0)
        n120 = collections.Counter(kd for v, kd in vcs if v > 1.2)
        tot, bad, ex = storage_check(h, scale)
        row[f'x{scale}'] = dict(over85=dict(n85), over100=dict(n100), over120=dict(n120), excess=r['excess_veh_h'], signal_approaches=tot, red_queue_over_storage=bad, sample=ex[:8])
        print(h, scale, {a: b for a, b in row[f'x{scale}'].items() if a != 'sample'}, flush=True)
        if scale in (1.0, 0.5):
            row[f'worst_x{scale}'] = r['worst'][:80]
    res[f'h{h:02}'] = row
json.dump(res, open(out_f, 'w'), indent=1)
