#!/usr/bin/env python3
"""Demand for a cut of a real net: shortest paths between random entrances and exits, Poisson in time.

--type av is the automated car with lane changing on; --type krauss is SUMO's default driver for the signal baseline.
No count data is behind this: it is through traffic, chosen to load the net, and any result says so."""
import argparse, heapq, random, xml.etree.ElementTree as ET
from pathlib import Path


def allowed(l):
    a, d = l.get('allow'), l.get('disallow')
    if a is not None:
        return 'passenger' in a.split()
    return not (d and 'passenger' in d.split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--net', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--demand', type=float, required=True)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--end', type=float, default=900.0)
    ap.add_argument('--type', default='av', choices=('av', 'krauss'))
    a = ap.parse_args()
    root = ET.parse(a.net).getroot()
    length, frm, to, ok = {}, {}, {}, {}
    for e in root.findall('edge'):
        if e.get('function') in ('internal', 'crossing', 'walkingarea'):
            continue
        lanes = e.findall('lane')
        i = e.get('id')
        length[i] = float(lanes[0].get('length'))
        frm[i], to[i] = e.get('from'), e.get('to')
        ok[i] = [allowed(l) for l in lanes]
    nxt = {i: set() for i in length}
    prev = {i: set() for i in length}
    for c in root.findall('connection'):
        f, t = c.get('from'), c.get('to')
        if f in length and t in length and c.get('dir') != 't' and ok[f][int(c.get('fromLane'))] and ok[t][int(c.get('toLane'))]:
            nxt[f].add(t)
            prev[t].add(f)
    usable = [i for i in length if any(ok[i])]
    src = [i for i in usable if not prev[i] and nxt[i] and length[i] > 20]
    dst = [i for i in usable if not nxt[i] and prev[i]]
    rng = random.Random(a.seed)

    def path(s):
        dist, back, q = {s: 0.0}, {}, [(0.0, s)]
        while q:
            d, u = heapq.heappop(q)
            if d > dist[u]:
                continue
            for v in nxt[u]:
                nd = d + length[v]
                if nd < dist.get(v, 1e18):
                    dist[v], back[v] = nd, u
                    heapq.heappush(q, (nd, v))
        return dist, back

    routes = {}
    for s in src:
        dist, back = path(s)
        reach = [d for d in dst if d in dist and dist[d] > 150]
        out = []
        for d in reach:
            r, at = [d], d
            while at != s:
                at = back[at]
                r.append(at)
            out.append(r[::-1])
        if out:
            routes[s] = out
    srcs = sorted(routes)
    print(len(src), 'entrances', len(dst), 'exits', len(srcs), 'usable entrances')
    events = []
    rate = a.demand / max(len(srcs), 1) / 3600
    for s in srcs:
        t, r = 0.0, random.Random(f'{s}/{a.seed}')
        while True:
            t += r.expovariate(rate)
            if t >= a.end:
                break
            events.append((t, s))
    events.sort()
    out = ['<routes>']
    if a.type == 'av':
        out.append('  <vType id="v" carFollowModel="CarsAV" length="5" width="1.8" minGap="2" accel="2.6" decel="2.5" emergencyDecel="7" apparentDecel="4.5" tau="0.8" sigma="0" maxSpeed="50" speedDev="0" lcKeepRight="0"><param key="reactionTime" value="0.3"/></vType>')
    else:
        out.append('  <vType id="v" length="5" width="1.8" minGap="2.5" accel="2.6" decel="4.5" tau="1" sigma="0.5"/>')
    for n, (t, s) in enumerate(events):
        r = rng.choice(routes[s])
        out.append(f'  <vehicle id="v{n}" type="v" depart="{t:.2f}" departLane="best" departSpeed="max"><route edges="{" ".join(r)}"/></vehicle>')
    out.append('</routes>')
    Path(a.out).write_text('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
