#!/usr/bin/env python3
"""Conflicts from trajectories, the way FHWA's SSAM does it: rectangles moved along their headings at their
speeds, TTC under 1.5 s, PET under 5 s, typed by angle. Works on any `cars run --fcd` file.

    python3 scripts/physics_conflicts.py --net n.xml --fcd f.csv --out conflicts.csv

For comparing designs relative to each other only. FHWA's own test found conflicts predict crashes worse than
traffic volume does (R2 0.41 against 0.68 at 83 intersections) and under-count path crossings. Do not turn these
into crash rates for human traffic. Sample at 0.1 s where it matters: SSAM's own step, and 1 s misses things.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from lxml import etree
from scipy.spatial import cKDTree

TTC_MAX = 1.5
PET_MAX = 5.0
STEP = 0.1
REAR_END_DEG = 30.0
CROSSING_DEG = 85.0


def read_net(path, wanted):
    shape, length, nodes = {}, {}, {}
    with open(path, 'rb') as f:
        for _, e in etree.iterparse(f, events=('end',), tag=('edge',)):
            internal = e.get('function') == 'internal'
            for l in e:
                if l.tag != 'lane':
                    continue
                i = l.get('id')
                if i in wanted:
                    shape[i] = np.array([[float(v) for v in q.split(',')[:2]] for q in l.get('shape').split()])
                    length[i] = float(l.get('length'))
                    if internal:
                        j = i[1:].rsplit('_', 2)[0]
                        nodes[i] = (j, j)
                    else:
                        nodes[i] = (e.get('from'), e.get('to'))
            e.clear()
    return shape, length, nodes


def place(df, shape, length):
    x, y, hx, hy = (np.zeros(len(df)) for _ in range(4))
    for lane, idx in df.groupby('lane', sort=False).indices.items():
        p = shape[lane]
        cum = np.concatenate(([0.0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))))
        pos = df['pos'].to_numpy()[idx]
        lens = df['length'].to_numpy()[idx]
        scale = cum[-1] / max(length[lane], 1e-3)
        front = np.clip(pos, 0, length[lane]) * scale
        rear = np.clip(pos - lens, 0, length[lane]) * scale
        fx, fy = np.interp(front, cum, p[:, 0]), np.interp(front, cum, p[:, 1])
        rx, ry = np.interp(rear, cum, p[:, 0]), np.interp(rear, cum, p[:, 1])
        # The rear of a body just past a lane start is still on the lane before.
        hanging = pos < lens
        prev = df['prev_lane'].to_numpy()[idx]
        for other in set(prev[hanging]):
            q = shape.get(other)
            if q is None or np.hypot(*(q[-1] - p[0])) > 4.0:
                continue
            mask = hanging & (prev == other)
            c2 = np.concatenate(([0.0], np.cumsum(np.hypot(*np.diff(q, axis=0).T))))
            at = np.clip((length[other] + pos[mask] - lens[mask]) * c2[-1] / max(length[other], 1e-3), 0, c2[-1])
            rx[mask], ry[mask] = np.interp(at, c2, q[:, 0]), np.interp(at, c2, q[:, 1])
        k = np.clip(np.searchsorted(cum, front, side='right') - 1, 0, len(p) - 2)
        seg = p[k + 1] - p[k]
        dx, dy = fx - rx, fy - ry
        d = np.hypot(dx, dy)
        short = d < 0.5
        dx, dy = np.where(short, seg[:, 0], dx), np.where(short, seg[:, 1], dy)
        d = np.maximum(np.hypot(dx, dy), 1e-6)
        hx[idx], hy[idx] = dx / d, dy / d
        cx, cy = fx - hx[idx] * lens / 2, fy - hy[idx] * lens / 2
        if 'offset' in df:
            off = df['offset'].to_numpy()[idx]
            cx, cy = cx - hy[idx] * off, cy + hx[idx] * off
        x[idx], y[idx] = cx, cy
    return x, y, hx, hy


def overlap(ax, ay, ahx, ahy, al, aw, bx, by, bhx, bhy, bl, bw):
    """Separating axes for rectangles given by centre, unit heading, half length, half width."""
    dx, dy = bx - ax, by - ay
    c = np.abs(ahx * bhx + ahy * bhy)
    s = np.abs(ahx * -bhy + ahy * bhx)
    s1 = al + bl * c + bw * s - np.abs(dx * ahx + dy * ahy)
    s2 = aw + bl * s + bw * c - np.abs(-dx * ahy + dy * ahx)
    s3 = bl + al * c + aw * s - np.abs(dx * bhx + dy * bhy)
    s4 = bw + al * s + aw * c - np.abs(-dx * bhy + dy * bhx)
    return (s1 > 0) & (s2 > 0) & (s3 > 0) & (s4 > 0)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--net', required=True)
    p.add_argument('--fcd', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    df = pd.read_csv(a.fcd, dtype={'trip': str, 'lane': str}, keep_default_na=False, usecols=lambda c: c in ('time', 'trip', 'lane', 'prev_lane', 'pos', 'speed', 'acc', 'length', 'width', 'offset'))
    for c in ('time', 'pos', 'speed', 'acc', 'length', 'width'):
        df[c] = pd.to_numeric(df[c])
    if 'offset' in df:
        df['offset'] = pd.to_numeric(df['offset'])
    shape, length, nodes = read_net(a.net, set(df['lane']) | set(df['prev_lane']))
    df = df[df['lane'].isin(shape)].reset_index(drop=True)
    df['x'], df['y'], df['hx'], df['hy'] = place(df, shape, length)
    times = np.sort(df['time'].unique())
    interval = float(np.median(np.diff(times))) if len(times) > 1 else 0.0
    taus = np.arange(0.0, TTC_MAX + 1e-6, STEP)
    events = {}
    for time, g in df.groupby('time', sort=True):
        if len(g) < 2:
            continue
        xy = g[['x', 'y']].to_numpy()
        reach = g['speed'].to_numpy().max() * 2 * TTC_MAX + g['length'].to_numpy().max() + 5
        pairs = cKDTree(xy).query_pairs(min(reach, 80.0), output_type='ndarray')
        if len(pairs) == 0:
            continue
        i, j = pairs[:, 0], pairs[:, 1]
        c = {k: g[k].to_numpy() for k in ('x', 'y', 'hx', 'hy', 'speed', 'length', 'width', 'acc')}
        lanes = g['lane'].to_numpy()
        trips = g['trip'].to_numpy()
        # Bridges and tunnels: only lanes sharing an edge end can meet.
        node_a, node_b = [nodes[l][0] for l in lanes], [nodes[l][1] for l in lanes]
        related = np.array([lanes[u] == lanes[v] or node_a[u] == node_a[v] or node_a[u] == node_b[v] or node_b[u] == node_a[v] or node_b[u] == node_b[v] for u, v in zip(i, j)], dtype=bool)
        i, j = i[related], j[related]
        ttc = np.full(len(i), np.inf)
        for tau in taus:
            todo = np.isinf(ttc)
            if not todo.any():
                break
            u, v = i[todo], j[todo]
            hit = overlap(c['x'][u] + c['hx'][u] * c['speed'][u] * tau, c['y'][u] + c['hy'][u] * c['speed'][u] * tau, c['hx'][u], c['hy'][u], c['length'][u] / 2, c['width'][u] / 2,
                          c['x'][v] + c['hx'][v] * c['speed'][v] * tau, c['y'][v] + c['hy'][v] * c['speed'][v] * tau, c['hx'][v], c['hy'][v], c['length'][v] / 2, c['width'][v] / 2)
            where = np.flatnonzero(todo)[hit]
            ttc[where] = tau
        for k in np.flatnonzero(np.isfinite(ttc)):
            u, v = i[k], j[k]
            key = tuple(sorted((trips[u], trips[v])))
            e = events.get(key)
            if e is None or ttc[k] < e['ttc']:
                angle = np.degrees(np.arccos(np.clip(c['hx'][u] * c['hx'][v] + c['hy'][u] * c['hy'][v], -1, 1)))
                tau = ttc[k]
                events[key] = dict(trip_a=trips[u], trip_b=trips[v], ttc=float(tau), t=float(time), lane_a=lanes[u], lane_b=lanes[v], angle=float(angle),
                                   x=float(c['x'][u] + c['hx'][u] * c['speed'][u] * tau), y=float(c['y'][u] + c['hy'][u] * c['speed'][u] * tau),
                                   speed_a=float(c['speed'][u]), speed_b=float(c['speed'][v]), acc_a=float(c['acc'][u]), acc_b=float(c['acc'][v]),
                                   delta_s=float(np.hypot(c['hx'][u] * c['speed'][u] - c['hx'][v] * c['speed'][v], c['hy'][u] * c['speed'][u] - c['hy'][v] * c['speed'][v])))
    by_trip = {t: g for t, g in df[df['trip'].isin({t for k in events for t in k})].groupby('trip')}
    rows = []
    for key, e in events.items():
        # PET: between one body leaving the conflict point and the other reaching it.
        passes = []
        for trip in key:
            g = by_trip[trip]
            d = np.hypot(g['x'].to_numpy() - e['x'], g['y'].to_numpy() - e['y'])
            near = g['time'].to_numpy()[d < g['length'].to_numpy() / 2 + 1.0]
            passes.append((near.min(), near.max()) if len(near) else (np.nan, np.nan))
        (a0, a1), (b0, b1) = passes
        pet = np.nan if np.isnan(a0 + b0) else max(0.0, max(a0, b0) - min(a1, b1))
        kind = 'rear end' if e['angle'] < REAR_END_DEG else 'crossing' if e['angle'] > CROSSING_DEG else 'lane change'
        rows.append(dict(e, pet=pet, kind=kind, contact=e['ttc'] == 0.0))
    out = pd.DataFrame(rows, columns=['t', 'trip_a', 'trip_b', 'kind', 'ttc', 'pet', 'angle', 'contact', 'x', 'y', 'lane_a', 'lane_b', 'speed_a', 'speed_b', 'acc_a', 'acc_b', 'delta_s'])
    out = out[(out['pet'].isna()) | (out['pet'] <= PET_MAX)].sort_values('ttc')
    out.to_csv(a.out, index=False, float_format='%.3f')
    summary = dict(interval=interval, conflicts=len(out), by_kind=out['kind'].value_counts().to_dict(), ttc_median=float(out['ttc'].median()) if len(out) else None, pet_median=float(out['pet'].median()) if len(out) else None,
                   ttc_zero=int(out['contact'].sum()), vehicle_seconds=float(len(df) * interval),
                   conflicts_per_1000_vehicle_hours=1000 * len(out) / max(len(df) * interval / 3600, 1e-9),
                   note='Relative comparison between designs only. Not a crash rate; path crossings are under-represented.')
    Path(a.out).with_suffix('.json').write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary))
    if interval > 0.2:
        print(f'Sampled at {interval:g} s, against SSAM\'s 0.1 s: expect fewer conflicts than exist.')


if __name__ == '__main__':
    main()
