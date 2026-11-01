#!/usr/bin/env python3
"""Demand for coordinated junction runs, drawn as research/truth/scripts/ci_model.py draws it.

Poisson arrivals per entrance with the same CRC seeded arrival times; a turn per junction from the mix;
a fixed lane from the entrance on, with no lane changes unless --lane-change. Writes a .rou.xml.
"""
import argparse, random, zlib, xml.etree.ElementTree as ET
from pathlib import Path

MIX = {'T': (0.0, 0.0), 'M': (0.1, 0.1), 'H': (0.25, 0.1)}
TYPES = {
    'av': dict(tau=0.8, minGap=2.0, reaction=0.3),
    'human': dict(tau=1.4, minGap=2.5, reaction=1.0),
}


def load(path):
    root = ET.parse(path).getroot()
    lanes, edges = {}, {}
    for e in root.findall('edge'):
        if e.get('function') == 'internal':
            continue
        edges[e.get('id')] = dict(frm=e.get('from'), to=e.get('to'), lanes=[l.get('id') for l in e.findall('lane')])
        for l in e.findall('lane'):
            p = [tuple(map(float, q.split(','))) for q in l.get('shape').split()]
            lanes[l.get('id')] = dict(edge=e.get('id'), shape=p, moves=[], length=float(l.get('length')))
    for c in root.findall('connection'):
        f = c.get('from')
        if f.startswith(':') or f not in edges:
            continue
        lane = f"{f}_{c.get('fromLane')}"
        if lane in lanes and c.get('dir') != 't':
            lanes[lane]['moves'].append((c.get('dir'), f"{c.get('to')}_{c.get('toLane')}"))
    tls = {t.get('id') for t in root.findall('tlLogic')}
    junctions = {j.get('id'): j for j in root.findall('junction') if j.get('type') != 'internal'}
    return lanes, edges, tls, junctions


def controlled(name, edges, tls, want):
    if want:
        return set(want.split(','))
    in_edges = {}
    for i, e in edges.items():
        in_edges.setdefault(e['to'], set()).add(i)
    all_c = {j for j, es in in_edges.items() if len(es) >= 3 and j in tls}
    if name.startswith('j'):
        return {'B1'}
    if name.startswith('grid'):
        return {j for j in all_c if j[0] in 'BCD' and j[1] in '123'}
    return all_c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--net', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--demand', type=float, required=True, help='veh/h across all entrances')
    ap.add_argument('--mix', default='M')
    ap.add_argument('--ew', type=float, default=0.5)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--end', type=float, default=800.0)
    ap.add_argument('--controlled', default='')
    ap.add_argument('--type', default='av', choices=TYPES)
    ap.add_argument('--lane-change', action='store_true')
    a = ap.parse_args()
    left, right = MIX[a.mix]
    lanes, edges, tls, _ = load(a.net)
    ctrl = controlled(Path(a.net).stem, edges, tls, a.controlled)
    rng = random.Random(a.seed * 7919 + 1)
    srcs = [i for i, e in edges.items() if e['to'] in ctrl and e['frm'] not in ctrl]
    horiz = lambda e: abs(lanes[edges[e]['lanes'][0]]['shape'][-1][0] - lanes[edges[e]['lanes'][0]]['shape'][0][0]) > abs(lanes[edges[e]['lanes'][0]]['shape'][-1][1] - lanes[edges[e]['lanes'][0]]['shape'][0][1])
    events = []
    for e in srcs:
        share = (a.ew if horiz(e) else 1 - a.ew) / 2 * (4 / max(len(srcs), 1))
        rate = a.demand * share / 3600
        t = 0.0
        r = random.Random(zlib.crc32(f"{e}/{a.seed}".encode()))
        while rate > 0:
            t += r.expovariate(rate)
            if t >= a.end:
                break
            events.append((t, e))
    events.sort()

    def pick_dir():
        u = rng.random()
        return 'l' if u < left else 'r' if u < left + right else 's'

    load_on = {}
    out = ['<routes>']
    t = TYPES[a.type]
    strat = '1' if a.lane_change else '-1'
    out.append(f'  <vType id="av" carFollowModel="CarsAV" length="5" width="1.8" minGap="{t["minGap"]}" accel="2.6" decel="2.5" emergencyDecel="7" apparentDecel="4.5" tau="{t["tau"]}" sigma="0" maxSpeed="50" speedDev="0" lcStrategic="{strat}" lcSpeedGain="0" lcKeepRight="0" lcCooperative="0"><param key="reactionTime" value="{t["reaction"]}"/></vType>')
    for n, (t0, e) in enumerate(events):
        d = pick_dir()
        opts = [l for l in edges[e]['lanes'] if any(m[0] == d for m in lanes[l]['moves'])] or edges[e]['lanes']
        lane = min(opts, key=lambda l: (load_on.get(l, 0), l))
        load_on[lane] = load_on.get(lane, 0) + 1
        route = [e]
        at, dd = lane, d
        for _ in range(64):
            moves = lanes[at]['moves']
            if not moves:
                break
            match = [m for m in moves if m[0] == dd] or [m for m in moves if m[0] == 's'] or moves
            mv = match[0] if len(match) == 1 else rng.choice(match)
            at = mv[1]
            route.append(lanes[at]['edge'])
            if edges[lanes[at]['edge']]['to'] not in ctrl:
                break
            dd = pick_dir()
        index = edges[e]['lanes'].index(lane)
        out.append(f'  <vehicle id="v{n}" type="av" depart="{t0:.2f}" departLane="{index}" departSpeed="max"><route edges="{" ".join(route)}"/></vehicle>')
    out.append('</routes>')
    Path(a.out).write_text('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
