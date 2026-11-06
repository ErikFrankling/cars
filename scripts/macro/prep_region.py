#!/usr/bin/env python3
"""Whole region with movement detail in the district, D 4.3. prep_region.py NETDIR BASE OUT [--ring 15000]
Inside: the district's repaired table. Outside: v6.4's sumo.net.xml (Jan 2023, no foe table), motorway to tertiary only, ESTIMATED: gap search with nothing known to yield to, signals by the same rule.
Demand: every vehicle leg's first and last link, departure and class. No route, capacity or free speed from MATSim. A leg that cannot come near the district is left out and counted.
Ends off the kept roads snap to the nearest kept edge."""
import argparse
import collections
import gzip
import pickle
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'berlin2019'))
import mtable as mt
import prepare
import step2_cut
from common import read_net, B19

KEEP = ('motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary', 'tertiary_link')
CL = {'car': (0, 1.0), 'van': (1, 1.2), 'truck8t': (2, 2.0), 'truck18t': (2, 2.0), 'truck40t': (3, 2.0)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('netdir')
    p.add_argument('base')
    p.add_argument('out')
    p.add_argument('--near', type=float, default=2500.0, help='a leg whose straight line stays further than this from the box is left out')
    a = p.parse_args()
    T = mt.read(B19 / 'district' / a.netdir / 'net.net.xml')
    mt.repair(T, mt.read(B19 / 'district' / a.base / 'net.net.xml'), [], None, mt.read_none_lanes(B19 / 'district' / a.netdir / 'lane_tags.csv'))
    print('reading the region', flush=True)
    R = mt.read(B19 / 'raw/sumo.net.xml')
    print('region edges', len(R['edges']), 'conns', len(R['conns']), flush=True)
    step2_cut.OUT = B19 / 'district' / a.netdir
    step2_cut.BASE = B19 / 'district'
    cut = read_net(step2_cut.OUT / 'net.net.xml', step2_cut.OUT / 'net.pkl')
    remap = step2_cut.edge_remap(cut)
    inside = set(T['edges'])
    def to_inside(k):
        k2 = remap.get(k, k)
        return k2 if k2 in inside else None
    box = __import__('json').load(open(B19 / 'step0/district.json'))['box']
    # kept outside edges: main roads, largest strongly connected part is checked by no_path counts in the run
    keep = {}
    for k, e in R['edges'].items():
        if to_inside(k) is None and k not in remap and e['any'] and e['type'] in KEEP and e['car']:
            keep[k] = e
    print('kept outside', len(keep), flush=True)
    edges = dict(T['edges'])
    for k, e in keep.items():
        edges[k] = e
    moves = {(m['frm'], m['to']): m for m in T['moves']}
    moves_list = list(T['moves'])
    conns = list(T['conns'])
    added = 0
    tl = dict(T['tl'])
    for k, v in R['tl'].items():
        tl['r:' + k] = v
    for c in R['conns']:
        a0, b0 = c['frm'], c['to']
        a1, b1 = to_inside(a0), to_inside(b0)
        if a1 is not None and b1 is not None:
            continue
        af = a1 if a1 is not None else (a0 if a0 in keep else None)
        bf = b1 if b1 is not None else (b0 if b0 in keep else None)
        if af is None or bf is None:
            continue
        key = (af, bf)
        m = moves.get(key)
        c2 = dict(c)
        c2['frm'], c2['to'] = af, bf
        c2['outside'] = True
        c2['foe_m'], c2['foe_yield'] = [], []
        c2['merge'] = False
        if c2['ctrl']:
            c2['ctrl'] = 'r:' + c2['ctrl']
        nl = {l['i'] for l in edges[af]['lanes']}
        if c2['fl'] not in nl:
            c2['fl'] = min(nl)
        if m is None:
            m = dict(id=len(moves_list), frm=af, to=bf, lanes=[], dir=c2['dir'], kinds=[], conns=[], mask=0, L=edges[af]['L'], v=edges[af]['v'], j=edges[af]['to'])
            moves[key] = m
            moves_list.append(m)
        c2['m'] = m['id']
        m['conns'].append(c2)
        m['lanes'] = sorted({x['fl'] for x in m['conns']})
        m['mask'] |= c2['mask']
        m['kinds'] = sorted(set(m['kinds']) | {mt.kind(c2)})
        conns.append(c2)
        added += 1
    print('connections added', added, 'movements', len(moves_list), flush=True)
    M = dict(edges=edges, conns=conns, moves=moves_list, index={(m['frm'], m['to']): m['id'] for m in moves_list}, tl=tl, junc={**R['junc'], **T['junc']})
    mt.index_lanes(M)
    mt.lane_groups(M)
    prepare.export(M, a.out)
    # demand
    ids = [k for k in keep]
    xy = np.array([keep[k]['xy'] for k in ids])
    tree = cKDTree(xy)
    classes = step2_cut.vehicle_classes()
    x0, y0, x1, y1 = box
    def near(p, q):
        # distance of a segment from the box, by sampling
        ts = np.linspace(0, 1, 9)
        xs, ys = p[0] + (q[0] - p[0]) * ts, p[1] + (q[1] - p[1]) * ts
        dx = np.maximum(np.maximum(x0 - xs, xs - x1), 0)
        dy = np.maximum(np.maximum(y0 - ys, ys - y1), 0)
        return np.hypot(dx, dy).min()
    n, far, unknown = 0, 0, 0
    kinds = collections.Counter()
    def place(k):
        i = to_inside(k)
        if i is not None:
            return i, T['edges'][i]['xy']
        e = R['edges'].get(k)
        if e is None:
            return None, None
        if k in keep:
            return k, e['xy']
        if k in remap and remap[k] is None:
            d, j = tree.query(e['xy'])
            return ids[j], keep[ids[j]]['xy']
        d, j = tree.query(e['xy'])
        return ids[j], e['xy']
    with gzip.open(B19 / 'demand/legs.tsv.gz', 'rt') as f, open(Path(a.out) / 'legs.tsv', 'w') as w:
        next(f)
        w.write('o\td\tdep\tclass\tpce\tw\n')
        for line in f:
            person, leg, mode, dep, trav, dist, links = line.rstrip('\n').split('\t')
            sp = links.split(' ')
            o, oxy = place(sp[0])
            d, dxy = place(sp[-1])
            if o is None or d is None:
                unknown += 1
                continue
            if near(oxy, dxy) > a.near:
                far += 1
                continue
            if o == d:
                kinds['same_edge'] += 1
                continue
            vt = classes.get((person, mode), 'car')
            c, pce = CL[vt]
            kinds[vt] += 1
            w.write(f"{o}\t{d}\t{int(dep) % 86400}\t{c}\t{pce}\t10\n")
            n += 1
    print('legs kept', n, 'far from the district', far, 'unknown link', unknown, dict(kinds), flush=True)


if __name__ == '__main__':
    main()
