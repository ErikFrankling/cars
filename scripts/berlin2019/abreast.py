#!/usr/bin/env python3
"""Cars stopped side by side, each wanting the other's lane: abreast.py OUT.csv LABEL=TRACE ...
Pair: adjacent lanes of one edge, the right car wants left, the left car wants right, both under 0.5 m/s, overlapping along the road. A case is a pair that lasts at least 60 s. No lane swap exists, so only a third car, a gap or a teleport ends it.
Per edge: cases, pair-seconds, longest, and how many cars stood queued behind them on that edge. For the physics agent, which owns lane changing."""
import argparse
import sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from cars_trace import Trace, WANT_LEFT, WANT_RIGHT

p = argparse.ArgumentParser()
p.add_argument('out')
p.add_argument('runs', nargs='+')
p.add_argument('--min-time', type=float, default=60)
p.add_argument('--net-length', help='not used by the count, only labels')
a = p.parse_args()

rows = []
for spec in a.runs:
    label, _, path = spec.partition('=')
    tr = Trace(path)
    lengths = np.array([t['length'] for t in tr.header['vtypes']], dtype=float)
    frames = tr.frames
    stride = frames[1]['time'] - frames[0]['time'] if len(frames) > 1 else 1
    live, done = {}, []
    behind = defaultdict(int)
    for f in frames:
        r = tr.records(f)
        flags = r['trip_flags'] >> 24
        speed = r['speed'] / 512.0
        stopped = speed < .5
        lane = r['lane_type'] & 0xffffff
        trip = r['trip_flags'] & 0xffffff
        pos = (r['pos_link'] & 0xffffff) / 256.0
        length = lengths[r['lane_type'] >> 24]
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
        rows.append(dict(run=label, edge=edge, cases=q['cases'], pair_seconds=round(q['pair_s']), longest_s=round(q['longest']), first_h=round(q['first'] / 3600, 2), lanes='+'.join(f'{k}/{k + 1}' for k in sorted(q['lanes'])), median_pos_m=round(float(np.median(q['pos'])), 1)))
    tot = [r for r in rows if r['run'] == label]
    print(label, 'frames', len(frames), 'stride', stride, 'edges', len(tot), 'cases', sum(r['cases'] for r in tot), 'pair-hours', round(sum(r['pair_seconds'] for r in tot) / 3600, 1))
d = pd.DataFrame(rows).sort_values(['run', 'pair_seconds'], ascending=[True, False])
d.to_csv(a.out, index=False)
print(d.head(15).to_string(index=False))
