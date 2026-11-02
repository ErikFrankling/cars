#!/usr/bin/env python3
"""Compare swept-path conflicts on internal-lane shapes with SUMO's <request foes> on real junctions,
and measure the crossing time T_x against the same-lane headway h that decides interleaving versus batching."""
import json, random, sys, xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np

net = Path('/home/erikf/projects/personal/cars-data') / sys.argv[1]
W, L, S0, TAU, MT = 2.3, 5.0, 2.0, 0.8, 0.3
lanes, conns, juncs = {}, [], {}
for _, e in ET.iterparse(net, events=('end',)):
    if e.tag == 'lane':
        lanes[e.get('id')] = dict(shape=np.array([[float(c) for c in p.split(',')] for p in e.get('shape').split()]), speed=float(e.get('speed')), length=float(e.get('length')))
        e.clear()
    elif e.tag == 'connection':
        conns.append(dict(fr=e.get('from'), to=e.get('to'), fl=e.get('fromLane'), tl=e.get('toLane'), via=e.get('via'), li=e.get('linkIndex'), dir=e.get('dir'), tlid=e.get('tl')))
        e.clear()
    elif e.tag == 'junction':
        reqs = {int(r.get('index')): r.get('foes') for r in e.findall('request')}
        if reqs:
            juncs[e.get('id')] = dict(type=e.get('type'), reqs=reqs, int=e.get('intLanes', '').split())
        e.clear()
    elif e.tag == 'edge':
        pass
by_int = {f"{c['fr']}_{c['fl']}": c for c in conns if c['fr'].startswith(':')}
paths = {}
for c in conns:
    if c['fr'].startswith(':') or not c['via'] or c['li'] is None:
        continue
    pts, sp, v, n = [], 1e9, c['via'], 0
    j = v[1:v.rfind('_', 0, v.rfind('_'))]
    while v and n < 4:
        pts.append(lanes[v]['shape'])
        sp = min(sp, lanes[v]['speed'])
        nx = by_int.get(v)
        v = nx['via'] if nx is not None else None
        n += 1
    P = np.vstack(pts)
    seg = np.hypot(*np.diff(P, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    s = np.arange(0, cum[-1] + 1e-6, 0.25)
    xy = np.column_stack([np.interp(s, cum, P[:, 0]), np.interp(s, cum, P[:, 1])])
    paths.setdefault(j, {})[int(c['li'])] = dict(s=s, xy=xy, P=cum[-1], speed=sp, fr=f"{c['fr']}_{c['fl']}", to=f"{c['to']}_{c['tl']}", dir=c['dir'])
random.seed(1)
ids = [j for j in juncs if j in paths and len(paths[j]) >= 4 and juncs[j]['type'] in ('traffic_light', 'priority', 'right_before_left')]
random.shuffle(ids)
agree = geo_only = sumo_only = merges = diverges = 0
tx, hh, boxlen, npairs, ntl = [], [], [], [], 0
for j in ids[:int(sys.argv[2])]:
    pj, req = paths[j], juncs[j]['reqs']
    keys = sorted(pj)
    n = 0
    for a in range(len(keys)):
        for b in range(a + 1, len(keys)):
            i, k = keys[a], keys[b]
            A, B = pj[i], pj[k]
            d = np.hypot(A['xy'][:, None, 0] - B['xy'][None, :, 0], A['xy'][:, None, 1] - B['xy'][None, :, 1])
            hit = (d <= W).any()
            if A['fr'] == B['fr']:
                diverges += 1
                continue
            if A['to'] == B['to']:
                merges += 1
                continue
            bits = req.get(i, '')
            foe = len(bits) > k and bits[len(bits) - 1 - k] == '1'
            if hit and foe:
                agree += 1
            elif hit:
                geo_only += 1
            elif foe:
                sumo_only += 1
            if hit:
                n += 1
                ia = np.where((d <= W).any(axis=1))[0]
                sa = A['s'][ia[-1]] - A['s'][ia[0]]
                if A['dir'] == 's' and A['speed'] > 8:
                    tx.append((sa + L) / A['speed'] + MT)
                    hh.append((L + S0) / A['speed'] + TAU)
    npairs.append(n)
    boxlen += [p['P'] for p in pj.values()]
tx, hh = np.array(tx), np.array(hh)
res = dict(net=sys.argv[1], junctions=len(npairs), both=agree, geometry_only=geo_only, foes_only=sumo_only, merge_pairs=merges, diverge_pairs=diverges,
           crossing_pairs_per_junction_mean=float(np.mean(npairs)), crossing_pairs_p99=float(np.percentile(npairs, 99)),
           path_length_median=float(np.median(boxlen)), path_length_p99=float(np.percentile(boxlen, 99)),
           through_tx_median=float(np.median(tx)), through_tx_p10=float(np.percentile(tx, 10)), through_tx_p90=float(np.percentile(tx, 90)),
           h_median=float(np.median(hh)), share_tx_below_h=float(np.mean(tx < hh)))
print(json.dumps(res, indent=1))
out = Path(__file__).resolve().parents[1] / 'fig' / '09b-foes-check.json'
prev = json.loads(out.read_text()) if out.exists() else {}
prev[sys.argv[1]] = res
out.write_text(json.dumps(prev, indent=1))
