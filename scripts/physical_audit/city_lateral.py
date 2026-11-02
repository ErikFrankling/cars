#!/usr/bin/env python3
"""Lateral acceleration and turning speed in a city trace, from the net's geometry.

Per sample, a_y = v²/R at two scales: the 5 m window physics_qa uses, and 30 m, which a steering car can actually
follow. Internal lanes are also given by whole-lane radius, for speed by radius against real drivers.

    python3 city_lateral.py --net N --trace T --out f.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cars_trace_local as ct  # noqa: E402
from maps import radius_window, resample, vertex_kink  # noqa: E402


def lane_table(net, wanted):
    rows = {}
    with open(net, 'rb') as f:
        for _, e in etree.iterparse(f, events=('end',), tag='lane'):
            lid = e.get('id')
            if lid in wanted:
                shape = np.array([[float(x) for x in c.split(',')[:2]] for c in e.get('shape').split()])
                res, geom = resample(shape)
                if res is not None:
                    h0, h1 = np.arctan2(*(shape[1] - shape[0])[::-1]), np.arctan2(*(shape[-1] - shape[-2])[::-1])
                    turn = float(np.abs((h1 - h0 + np.pi) % (2 * np.pi) - np.pi))
                    rows[lid] = dict(r5=radius_window(res, geom, 5), r10=radius_window(res, geom, 10), r30=radius_window(res, geom, 30), r_mean=geom / max(turn, 1e-3), turn=np.degrees(turn), limit=float(e.get('speed')), internal=lid.startswith(':'), geom=geom)
            e.clear()
    return pd.DataFrame.from_dict(rows, orient='index')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--net', required=True)
    p.add_argument('--trace', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--stride', type=int, default=1)
    a = p.parse_args()
    t = ct.Trace(a.trace)
    frames = t.frames[:: a.stride]
    parts = []
    for f in frames:
        r = t.records(f)
        parts.append(np.c_[r['lane_type'] & 0xffffff, r['speed'] / 512.0, r['acc'] / 256.0])
    d = np.concatenate(parts)
    idx = np.unique(d[:, 0].astype(int))
    names = {int(i): t.lanes.get(int(i), '') for i in idx}
    lanes = lane_table(a.net, set(names.values()))
    arr = {w: np.full(int(idx.max()) + 1, np.inf) for w in ('r5', 'r10', 'r30', 'r_mean')}
    turn = np.zeros(int(idx.max()) + 1)
    internal = np.zeros(int(idx.max()) + 1, bool)
    limit = np.full(int(idx.max()) + 1, np.nan)
    for i, n in names.items():
        if n in lanes.index:
            for w in arr:
                arr[w][i] = lanes.at[n, w]
            turn[i] = lanes.at[n, 'turn']
            internal[i] = lanes.at[n, 'internal']
            limit[i] = lanes.at[n, 'limit']
    li, v, acc = d[:, 0].astype(int), d[:, 1], d[:, 2]
    m = v > 0.5
    out = dict(samples=int(m.sum()), vehicle_seconds=int(len(v) * a.stride), acc_max=round(float(acc.max()), 2), acc_min=round(float(acc.min()), 2),
               acc_p95=round(float(np.percentile(acc[m & (acc > .1)], 95)), 2), dec_p50_p95_p99=[round(float(x), 2) for x in np.percentile(-acc[m & (acc < -.1)], [50, 95, 99])],
               share_dec_over={str(x): round(float((acc[m] < -x).mean()), 5) for x in (2, 3, 4.5, 6, 8.9)})
    for w in ('r5', 'r10', 'r30'):
        ay = v[m] ** 2 / arr[w][li[m]]
        out[f'ay_{w}'] = dict(over_4=int((ay > 4).sum()), over_8=int((ay > 8).sum()), max=round(float(ay.max()), 1), share_over_4=round(float((ay > 4).mean()), 5), share_over_8=round(float((ay > 8).mean()), 6))
    k = m & internal[li] & (turn[li] > 60)
    ay = v[k] ** 2 / arr['r_mean'][li[k]]
    out['turning'] = dict(samples=int(k.sum()), ay_p50=round(float(np.percentile(ay, 50)), 2), ay_p95=round(float(np.percentile(ay, 95)), 2), share_over_4=round(float((ay > 4).mean()), 4), share_over_8=round(float((ay > 8).mean()), 4), r_mean_p50=round(float(np.median(arr['r_mean'][li[k]])), 1), speed_over_limit_p50=round(float(np.median(v[k] / limit[li[k]])), 2), v_p50=round(float(np.median(v[k])), 2))
    tab = {}
    rr = arr['r_mean'][li[k]]
    for lo, hi in [(0, 5), (5, 8), (8, 13), (13, 20), (20, 30), (30, 60)]:
        q = (rr >= lo) & (rr < hi)
        if q.sum() > 20:
            tab[f'{lo}-{hi}'] = dict(n=int(q.sum()), v=round(float(np.median(v[k][q])), 2), v85=round(float(np.percentile(v[k][q], 85)), 2))
    out['turning_by_radius'] = tab
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(out))


if __name__ == '__main__':
    main()
