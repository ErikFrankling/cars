#!/usr/bin/env python3
"""Recipe step 2 setup. Cut v6.4's own net and demand to the district; nothing is fitted or scaled.

    step2_cut.py net                       cut the net with netconvert, internal lanes on
    step2_cut.py demand --factors 1,5,10   cut every car and truck leg, repair routes, write route files
    step2_cut.py sensors                   virtual loops at the real sites and lanes

A 10% MATSim leg entering the cut starts on the first edge inside, at the time MATSim's own travel time
reaches it, spread over the route by free-flow time. Factor f = f copies of the 10% sample, with departures
spread +-150 s so copies do not start in the same second. Factor 10 is the demand; the others are map tests.
"""
import argparse
import collections
import gzip
import heapq
import json
import pickle
import random
import re
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

OUT = B19 / 'district'
BASE = B19 / 'district'
TRUCK_MODES = ('truck', 'freight')
# Estimated lengths by class, EU limits and common models. MATSim's own 7.5 and 15 m are road-space units, not bodies.
VTYPES = '''  <vType id="car" vClass="passenger" length="4.6" width="1.8"/>
  <vType id="van" vClass="delivery" length="6.0" width="2.0"/>
  <vType id="truck8t" vClass="truck" length="7.8" width="2.4" accel="1.2" decel="4.0" maxSpeed="25"/>
  <vType id="truck18t" vClass="truck" length="10.0" width="2.5" accel="1.0" decel="4.0" maxSpeed="25"/>
  <vType id="truck40t" vClass="trailer" length="16.5" width="2.55" accel="0.8" decel="4.0" maxSpeed="25"/>
'''


def vehicle_classes():
    """MATSim's own vehicle type per person and mode, from output_vehicles."""
    pat = re.compile(r'<vehicle id="(.+)_([^_"]+)" type="([^"]+)"')
    table = {'golf1.4': 'car', 'car': 'car', 'vwCaddy': 'van', 'mercedes313': 'van', 'light8t': 'truck8t', 'medium18t': 'truck18t', 'heavy40t': 'truck40t', 'truck': 'truck40t', 'freight': 'truck40t'}
    out = {}
    with gzip.open(RAW / 'berlin-v6.4.output_vehicles.xml.gz', 'rt') as f:
        for line in f:
            m = pat.search(line)
            if m and m[3] in table and not m[1].startswith(('berlin', 'bb_')):
                out[(m[1], m[2])] = table[m[3]]
    return out


def cut_net(box, buffer):
    x0, y0, x1, y1 = box
    OUT.mkdir(exist_ok=True)
    b = f'{x0 - buffer},{y0 - buffer},{x1 + buffer},{y1 + buffer}'
    cmd = ['netconvert', '--sumo-net-file', str(RAW / 'sumo.net.xml'), '--keep-edges.in-boundary', b, '--keep-edges.by-vclass', 'passenger,truck,delivery', '--no-internal-links', 'false', '--remove-edges.isolated', '--offset.disable-normalization', 'true', '--tls.discard-simple', 'false', '--no-turnarounds', 'false', '-o', str(OUT / 'net.net.xml')]
    print(' '.join(cmd))
    subprocess.run(cmd, check=True)
    subprocess.run(['gzip', '-kf', '-1', str(OUT / 'net.net.xml')], check=False)


def edge_remap(cut):
    """Old edge -> edge of the rebuilt net, for edges --geometry.remove merged away. By geometry and heading."""
    from scipy.spatial import cKDTree
    old = read_net(BASE / 'net0_cut.net.xml', BASE / 'net0_cut.pkl')
    pts, ids = [], []
    for k, e in cut['edges'].items():
        if not car_lanes(e):
            continue
        s = e['lanes'][0]['shape']
        for p, q in zip(s[:-1], s[1:]):
            n = max(1, int(np.linalg.norm(q - p) / 4))
            for j in range(n):
                pts.append(p + (q - p) * (j + .5) / n)
                ids.append((k, q - p))
    tree = cKDTree(np.array(pts))
    out, lost = {}, []
    for k, e in old['edges'].items():
        if k in cut['edges'] or not car_lanes(e):
            continue
        s = e['lanes'][0]['shape']
        v = s[-1] - s[0]
        mid = s[len(s) // 2 - 1] * .5 + s[len(s) // 2] * .5 if len(s) > 1 else s[0]
        best = None
        for j in tree.query_ball_point(mid, 12):
            o, w = ids[j]
            c = np.dot(v, w) / max(np.linalg.norm(v) * np.linalg.norm(w), 1e-6)
            if c > .7:
                d = np.linalg.norm(pts[j] - mid)
                if best is None or d < best[0]:
                    best = (d, o)
        if best:
            out[k] = best[1]
        else:
            lost.append(k)
    print('edges merged away', len(out), 'not found', len(lost))
    return out


def cut_demand(a):
    cut = read_net(OUT / 'net.net.xml', OUT / 'net.pkl')
    remap = edge_remap(cut)
    edges = {k: e for k, e in cut['edges'].items() if car_lanes(e)}
    nexts = collections.defaultdict(set)
    for f, t, *_ in cut['conns']:
        if f in edges and t in edges:
            nexts[f].add(t)
    tt = pickle.loads((B19 / 'step0/free_time.pkl').read_bytes())
    length = {k: car_lanes(e)[0]['length'] for k, e in edges.items()}
    log = collections.Counter()
    repaired = collections.Counter()
    memo = {}

    def bridge(u, v):
        if (u, v) in memo:
            return memo[(u, v)]
        q, seen = [(0.0, u, ())], {u}
        path = None
        while q and len(seen) < 3000:
            c, x, p = heapq.heappop(q)
            for n in nexts[x]:
                if n == v:
                    path = p
                    q = []
                    break
                if n not in seen and c < 1500:
                    seen.add(n)
                    heapq.heappush(q, (c + length[n], n, p + (n,)))
        memo[(u, v)] = path
        return path

    classes = vehicle_classes()
    rows = []
    with gzip.open(B19 / 'demand/legs.tsv.gz', 'rt') as f:
        next(f)
        for line in f:
            log['legs_read'] += 1
            person, leg, mode, dep, trav, dist, links = line.rstrip('\n').split('\t')
            raw = links.split()
            links = [remap.get(l, l) for l in raw]
            if not any(l in edges for l in links):
                continue
            dep, trav = int(dep), int(trav)
            times = [tt.get(l, 5.0) for l in raw]
            total = max(sum(times), 1.0)
            run, part, cur, t_start = 0.0, 0, [], None
            segs = []
            for l, dt in zip(links, times):
                if l in edges:
                    if not cur:
                        t_start = dep + trav * run / total
                    cur.append(l)
                elif cur:
                    segs.append((t_start, cur, False))
                    cur = []
                run += dt
            if cur:
                segs.append((t_start, cur, True))
            for t0, seg, ends_here in segs:
                fixed = [seg[0]]
                ok = True
                for u, v in zip(seg[:-1], seg[1:]):
                    if v in nexts[u]:
                        fixed.append(v)
                        continue
                    if u == v:
                        continue
                    p = bridge(u, v)
                    if p is None:
                        ok = False
                        repaired[(u, v, 'unrepaired')] += 1
                        break
                    repaired[(u, v, 'bridged')] += 1
                    fixed += list(p) + [v]
                log['segments'] += 1
                if not ok:
                    log['segments_dropped_no_path'] += 1
                    continue
                starts_cut = links[0] != seg[0]
                ends_cut = links[-1] != seg[-1]
                kind = 'inner' if not starts_cut and not ends_cut else 'through' if starts_cut and ends_cut else 'in' if starts_cut else 'out'
                log['kind_' + kind] += 1
                rows.append((t0, f'{person}.{leg}.{part}', classes.get((person, mode), 'car'), fixed, starts_cut))
                part += 1
    log = dict(log)
    print(log)
    print('route pairs without a connection, repaired', sum(v for k, v in repaired.items() if k[2] == 'bridged'), 'distinct', sum(1 for k in repaired if k[2] == 'bridged'), 'unrepaired', sum(v for k, v in repaired.items() if k[2] == 'unrepaired'))
    (OUT / 'route_repairs.csv').write_text('from,to,what,uses\n' + ''.join(f'{k[0]},{k[1]},{k[2]},{v}\n' for k, v in repaired.most_common()))
    (OUT / 'demand_stats.json').write_text(json.dumps(dict(log=log, trips_10pct=len(rows), km_10pct=sum(sum(length[e] for e in r[3]) for r in rows) / 1000), indent=1))
    rng = random.Random(20190515)
    for fac in map(int, a.factors.split(',')):
        out = []
        for t0, name, vt, route, starts_cut in rows:
            for c in range(fac):
                t = t0 if fac == 1 else t0 + rng.uniform(-150, 150)
                t = (t % 86400)
                out.append((t, f'{name}.{c}', vt, route, starts_cut))
        out.sort(key=lambda r: r[0])
        with gzip.open(OUT / f'routes_f{fac:02}.rou.gz', 'wt', compresslevel=4) as f:
            f.write('<routes>\n' + VTYPES)
            for t, name, vt, route, starts_cut in out:
                sp = ' departSpeed="max"' if starts_cut else ''
                f.write(f'  <vehicle id="{name}" type="{vt}" depart="{t:.1f}" departLane="best"{sp}><route edges="{" ".join(route)}"/></vehicle>\n')
            f.write('</routes>\n')
        print('factor', fac, 'vehicles', len(out))


def sensors():
    cut = read_net(OUT / 'net.net.xml', OUT / 'net.pkl')
    remap = edge_remap(cut)
    s = pd.read_csv(B19 / 'step0/sites.csv')
    lanes = pd.read_csv(B19 / 'step0/site_lanes.csv')
    freeze = json.load(open(B19 / 'step1/freeze.json'))
    rows, issues = [], []
    for site in freeze['district_sites']:
        r = s[s.site == site].iloc[0]
        edge = remap.get(r.edge, r.edge)
        e = cut['edges'].get(edge)
        if e is None or not car_lanes(e):
            issues.append((site, r.edge, 'edge not in the cut net'))
            continue
        # position by projecting the real coordinate on the edge as it now stands
        sh = car_lanes(e)[len(car_lanes(e)) // 2]['shape']
        best, run, pos = 1e18, 0.0, r.pos_m
        for p, q in zip(sh[:-1], sh[1:]):
            v = q - p
            t = np.clip(np.dot(np.array([r.x, r.y]) - p, v) / max(np.dot(v, v), 1e-9), 0, 1)
            d = np.linalg.norm(p + v * t - [r.x, r.y])
            if d < best:
                best, pos = d, run + t * np.linalg.norm(v)
            run += np.linalg.norm(v)
        ls = lanes[lanes.site == site]
        use = sorted(set(int(x) for x in ls.lane_index.dropna()))
        cl = [l['index'] for l in car_lanes(e)]
        if len(ls) >= len(cl) or not use:
            use = cl
        for i in use:
            if i in cl:
                rows.append(f'{site},{edge}_{i},{pos:.1f}')
        if len(ls) != len(cl):
            issues.append((site, r.edge, f'{len(ls)} detectors, {len(cl)} car lanes on the map; measured lanes {use}'))
    (OUT / 'sensors.csv').write_text('\n'.join(rows) + '\n')
    (OUT / 'sensor_issues.csv').write_text('site,edge,issue\n' + ''.join(f'{a},{b},"{c}"\n' for a, b, c in issues))
    print(len(rows), 'lane sensors,', len(freeze['district_sites']), 'sites,', len(issues), 'issues')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('what', choices=['net', 'demand', 'sensors'])
    p.add_argument('--factors', default='1,5,10')
    p.add_argument('--buffer', type=float, default=500.0)
    p.add_argument('--dir', help='a rebuilt net under district/')
    a = p.parse_args()
    if a.dir:
        global OUT
        OUT = BASE / a.dir
    box = json.load(open(B19 / 'step0/district.json'))['box']
    if a.what == 'net':
        cut_net(box, a.buffer)
    elif a.what == 'demand':
        cut_demand(a)
    else:
        sensors()


if __name__ == '__main__':
    main()
