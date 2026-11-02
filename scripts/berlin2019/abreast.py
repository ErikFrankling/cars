#!/usr/bin/env python3
"""Cars stopped for a lane change: abreast.py OUT.csv NETDIR LABEL=TRACE ...
Abreast: adjacent lanes of one edge, the right car wants left, the left car wants right, both under 0.5 m/s, overlapping along the road, for at least 60 s. No lane swap exists, so only a third car or a gap ends it.
One-sided, from the .why beside the trace: a car under 0.5 m/s whose speed lane changing set, in seconds summed per edge. Counted at the trace's stride.
For the physics agent, which owns lane changing."""
import argparse
import sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from cars_trace import Trace, WANT_LEFT, WANT_RIGHT
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import B19, read_net

p = argparse.ArgumentParser()
p.add_argument('out')
p.add_argument('netdir')
p.add_argument('runs', nargs='+')
p.add_argument('--min-time', type=float, default=60)
a = p.parse_args()

net = read_net(B19 / a.netdir / 'net.net.xml', B19 / a.netdir / 'net.pkl')
LANE_CHANGE, WHY_RECORD = 14, 136
rows = []
for spec in a.runs:
    label, _, path = spec.partition('=')
    tr = Trace(path)
    lengths = np.array([t['length'] for t in tr.header['vtypes']], dtype=float)
    frames = tr.frames
    stride = frames[1]['time'] - frames[0]['time'] if len(frames) > 1 else 1
    live, done = {}, []
    solo = defaultdict(float)
    why = open(path + '.why', 'rb')
    why.seek(8)
    why.seek(int(np.fromfile(why, '<u4', 1)[0]), 1)
    for f in frames:
        r = tr.records(f)
        flags = r['trip_flags'] >> 24
        speed = r['speed'] / 512.0
        stopped = speed < .5
        lane = r['lane_type'] & 0xffffff
        trip = r['trip_flags'] & 0xffffff
        pos = (r['pos_link'] & 0xffffff) / 256.0
        length = lengths[r['lane_type'] >> 24]
        head = np.fromfile(why, '<u4', 4)
        rec = np.fromfile(why, 'u1', int(head[2]) * WHY_RECORD).reshape(-1, WHY_RECORD)
        for i in np.where(stopped & (rec[:, 0] == LANE_CHANGE))[0]:
            name = tr.lanes.get(int(lane[i]), '')
            if '_' in name and not name.startswith(':'):
                solo[name.rpartition('_')[0]] += stride
        by = defaultdict(list)
        keep = np.where(stopped & ((flags & (WANT_LEFT | WANT_RIGHT)) != 0))[0]
        for i in keep:
            name = tr.lanes.get(int(lane[i]), '')
            if name.startswith(':') or '_' not in name:
                continue
            edge, _, idx = name.rpartition('_')
            by[edge].append((int(idx), i))
        now = set()
        for edge, cars in by.items():
            for k1, i in cars:
                if not flags[i] & WANT_LEFT:
                    continue
                for k2, j in cars:
                    if k2 == k1 + 1 and flags[j] & WANT_RIGHT and abs(pos[i] - pos[j]) < (length[i] + length[j]) / 2:
                        now.add((edge, k1, int(trip[i]), int(trip[j]), float(pos[i])))
        seen = set()
        for edge, k, x, y, ps in now:
            key = (edge, k, x, y)
            seen.add(key)
            if key not in live:
                live[key] = [f['time'], f['time'], ps]
            live[key][1] = f['time']
        for key in [q for q in live if q not in seen]:
            done.append((key, live.pop(key)))
    done += list(live.items())
    per = defaultdict(lambda: dict(cases=0, pair_s=0.0, longest=0.0, first=1e12, lanes=set(), pos=[]))
    for edge in solo:
        per[edge]
    for (edge, k, x, y), (t0, t1, ps) in done:
        d = t1 - t0 + stride
        if d < a.min_time:
            continue
        q = per[edge]
        q['cases'] += 1
        q['pair_s'] += d
        q['longest'] = max(q['longest'], d)
        q['first'] = min(q['first'], t0)
        q['lanes'].add(k)
        q['pos'].append(ps)
    for edge, q in per.items():
        e = net['edges'].get(edge, dict(name='', lanes=[dict(length=0)]))
        rows.append(dict(run=label, edge=edge, name=e['name'], road_lanes=len(e['lanes']), road_m=round(e['lanes'][0]['length'], 1), abreast_cases=q['cases'], abreast_pair_seconds=round(q['pair_s']), longest_s=round(q['longest']), first_h=round(q['first'] / 3600, 2) if q['cases'] else '', lane_pairs='+'.join(f'{k}/{k + 1}' for k in sorted(q['lanes'])), median_pos_m=round(float(np.median(q['pos'])), 1) if q['pos'] else '', one_sided_seconds=round(solo[edge])))
    tot = [r for r in rows if r['run'] == label]
    print(label, 'frames', len(frames), 'stride', stride, 'edges', len(tot), 'abreast cases', sum(r['abreast_cases'] for r in tot), 'pair-hours', round(sum(r['abreast_pair_seconds'] for r in tot) / 3600, 1), 'one-sided car-hours', round(sum(r['one_sided_seconds'] for r in tot) / 3600, 1))
d = pd.DataFrame(rows).sort_values(['run', 'abreast_pair_seconds', 'one_sided_seconds'], ascending=[True, False, False])
d.to_csv(a.out, index=False)
print(d.head(15).to_string(index=False))
