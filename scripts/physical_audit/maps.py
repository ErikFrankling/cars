#!/usr/bin/env python3
"""Why maps demand impossible corners: is it the speed or the geometry?

For every lane a QA report flagged, the peak lateral acceleration is recomputed with curvature measured over
longer windows, as a steering car smooths a kink in a polyline, and each lane is sorted by what causes it.
For all internal lanes of a net it also gives turning radius by the whole lane, kinks at vertices, and limit speed.

    python3 -I maps.py --net N --lanes lanes_over_lateral.csv --out f.json
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from lxml import etree


def resample(shape, step=1.0):
    d = np.hypot(*np.diff(shape, axis=0).T)
    keep = np.concatenate(([True], d > 1e-3))
    shape = shape[keep]
    if len(shape) < 2:
        return None, 0.0
    s = np.concatenate(([0], np.cumsum(np.hypot(*np.diff(shape, axis=0).T))))
    n = max(int(s[-1] / step) + 1, 2)
    u = np.linspace(0, s[-1], n)
    return np.c_[np.interp(u, s, shape[:, 0]), np.interp(u, s, shape[:, 1])], float(s[-1])


def radius_window(p, length, w):
    """Smallest radius over chords of total length w: heading change across the window."""
    step = length / max(len(p) - 1, 1)
    k = max(int(round(w / 2 / step)), 1)
    if len(p) < 2 * k + 1:
        k = (len(p) - 1) // 2
        if k < 1:
            return np.inf
    a = np.arctan2(p[k:] [:, 1] - p[:-k][:, 1], p[k:][:, 0] - p[:-k][:, 0])
    if len(a) <= k:
        return np.inf
    dh = np.abs((a[k:] - a[:-k] + np.pi) % (2 * np.pi) - np.pi)
    dh = np.maximum(dh, 1e-6)
    return float((k * step / dh).min())


def vertex_kink(shape):
    v = np.diff(shape, axis=0)
    ok = np.hypot(*v.T) > 1e-3
    v = v[ok]
    if len(v) < 2:
        return 0.0
    a = np.arctan2(v[:, 1], v[:, 0])
    return float(np.degrees(np.abs((np.diff(a) + np.pi) % (2 * np.pi) - np.pi).max()))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--net', required=True)
    p.add_argument('--lanes', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    q = pd.read_csv(a.lanes).set_index('lane')
    wanted = set(q.index)
    rows, internal = [], []
    with open(a.net, 'rb') as f:
        for _, e in etree.iterparse(f, events=('end',), tag='lane'):
            lid = e.get('id')
            is_int = lid.startswith(':')
            if is_int or lid in wanted:
                shape = np.array([[float(x) for x in c.split(',')[:2]] for c in e.get('shape').split()])
                res, geom = resample(shape)
                if res is not None:
                    r = {w: radius_window(res, geom, w) for w in (5, 10, 20, 30)}
                    h0, h1 = np.arctan2(*(shape[1] - shape[0])[::-1]), np.arctan2(*(shape[-1] - shape[-2])[::-1])
                    turn = float(np.abs((h1 - h0 + np.pi) % (2 * np.pi) - np.pi))
                    row = dict(lane=lid, geom=geom, speed=float(e.get('speed')), kink=vertex_kink(shape), turn_deg=float(np.degrees(turn)), r_mean=geom / max(turn, 1e-3), **{f'r{w}': r[w] for w in r})
                    if is_int:
                        internal.append(row)
                    if lid in wanted:
                        rows.append(row)
            e.clear()
            while e.getprevious() is not None:
                del e.getparent()[0]
    d = pd.DataFrame(rows).set_index('lane').join(q[['internal', 'samples', 'over4', 'over8', 'peak', 'speed_kmh', 'mean_lateral']])
    d['v'] = d.speed_kmh / 3.6
    for w in (5, 10, 20, 30):
        d[f'ay{w}'] = d.v ** 2 / d[f'r{w}']
    out = {}
    for name, g in [('normal', d[~d.internal]), ('internal', d[d.internal])]:
        g8 = g[g.over8 > 0]
        out[name] = dict(lanes=len(g), lanes_over8=len(g8), samples_over8=int(g.over8.sum()),
                         over8_by_window={f'{w}m': int(((g[f'ay{w}'] > 8)).sum()) for w in (5, 10, 20, 30)},
                         share_over8_samples_gone_at_20m=round(float(g8[g8.ay20 <= 8].over8.sum() / max(g8.over8.sum(), 1)), 3),
                         share_over8_samples_gone_at_30m=round(float(g8[g8.ay30 <= 8].over8.sum() / max(g8.over8.sum(), 1)), 3),
                         median=dict(kink_deg=round(float(g8.kink.median()), 1), r5=round(float(g8.r5.median()), 1), r20=round(float(g8.r20.median()), 1), r_mean=round(float(g8.r_mean.median()), 1), speed_kmh=round(float(g8.speed_kmh.median()), 1), lane_limit_kmh=round(float(g8.speed.median() * 3.6), 1), geom=round(float(g8.geom.median()), 1)),
                         speed_over_limit_ratio=round(float((g8.v / g8.speed).median()), 2))
    k = pd.DataFrame(internal)
    if len(k):
        turns = k[k.turn_deg > 60]
        out['all_internal'] = dict(n=len(k), turning_60deg=len(turns), r_mean=dict(p10=round(float(turns.r_mean.quantile(.1)), 1), p50=round(float(turns.r_mean.median()), 1), p90=round(float(turns.r_mean.quantile(.9)), 1)),
                                   r5=dict(p10=round(float(turns.r5.quantile(.1)), 1), p50=round(float(turns.r5.median()), 1), p90=round(float(turns.r5.quantile(.9)), 1)),
                                   speed_kmh=dict(p10=round(float(turns.speed.quantile(.1) * 3.6), 1), p50=round(float(turns.speed.median() * 3.6), 1), p90=round(float(turns.speed.quantile(.9) * 3.6), 1)),
                                   ay_at_limit=dict(p50=round(float((turns.speed ** 2 / turns.r_mean).median()), 2), p95=round(float((turns.speed ** 2 / turns.r_mean).quantile(.95)), 2), share_over_4=round(float(((turns.speed ** 2 / turns.r_mean) > 4).mean()), 3), share_over_8=round(float(((turns.speed ** 2 / turns.r_mean) > 8).mean()), 3)),
                                   ay_at_8ms=dict(p50=round(float((64 / turns.r_mean).median()), 2), share_over_4=round(float(((64 / turns.r_mean) > 4).mean()), 3), share_over_8=round(float(((64 / turns.r_mean) > 8).mean()), 3)),
                                   vertex_kink_deg=dict(p50=round(float(turns.kink.median()), 1), p90=round(float(turns.kink.quantile(.9)), 1)),
                                   short_under_5m=round(float((turns.geom < 5).mean()), 3))
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
