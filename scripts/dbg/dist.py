"""`cars dist`: acceleration, braking, gaps, speeds and lane changes of two runs, or a run and real tracks, with a plain number for how far apart they are."""
import argparse
import json
import os

import numpy as np

from .real import real_sets, samples
from .run import LANE_CHANGED, NONE32, Run, accs_of, flags_of, lanes_of, pos_of, speeds_of, trips_of, vtypes_of

METRICS = ('speed', 'acceleration', 'braking', 'gap', 'headway')
UNITS = dict(speed='m/s', acceleration='m/s2', braking='m/s2', gap='m', headway='s')


def from_trace(path, begin, end, net, stride, one_second=True):
    run = Run(path, net)
    lengths = np.array([t['length'] for t in run.trace.header['vtypes']], dtype=float)
    speed, acc, gap, headway = [], [], [], []
    changes = 0
    km = 0.0
    km_frames = 0.0
    prev = None
    # Acceleration over one second, as on the real side, whatever dt the run used.
    frames = list(run.window(begin, end))
    each = max(int(round(1.0 / run.dt)), 1) if one_second else 1
    frames = frames[::max(stride, each)]
    step = run.dt * max(stride, each)
    for i in frames:
        rec, _ = run.read(i)
        on = (flags_of(rec) & 6) == 0
        rec = rec[on]
        v, trip, lane, pos = speeds_of(rec), trips_of(rec), lanes_of(rec), pos_of(rec)
        speed.append(v)
        km += float(v.sum()) * step / 1000.0
        km_frames += float(v.sum()) * run.dt / 1000.0
        changes += int((flags_of(rec) & LANE_CHANGED != 0).sum())
        if prev is not None:
            order = np.argsort(prev[0])
            at = np.searchsorted(prev[0][order], trip)
            at = np.minimum(at, len(order) - 1)
            hit = prev[0][order][at] == trip
            acc.append((v[hit] - prev[1][order][at[hit]]) / step)
        prev = (trip, v)
        order = np.lexsort((pos, lane))
        pair = lane[order][:-1] == lane[order][1:]
        lens = lengths[vtypes_of(rec)[order][1:]]
        g = (pos[order][1:] - lens - pos[order][:-1])[pair]
        gap.append(g[(g > 0) & (g < 200)])
        fv = v[order][:-1][pair]
        fine = (g > 0) & (fv > 1)
        h = g[fine] / fv[fine]
        headway.append(h[h < 10])
    empty = np.zeros(0)
    return dict(name=os.path.basename(path), speed=np.concatenate(speed) if speed else empty, acc=np.concatenate(acc) if acc else empty, gap=np.concatenate(gap) if gap else empty,
                headway=np.concatenate(headway) if headway else empty, lc_per_km=changes / max(km_frames, 1e-9), veh_km=km)


def load(spec, begin, end, net, stride):
    if spec.startswith('real:'):
        return samples(spec[5:])
    return from_trace(spec, begin, end, net, stride)


def wasserstein(a, b):
    """Mean absolute difference between quantiles: the average amount one sample must move to become the other."""
    if not len(a) or not len(b):
        return float('nan')
    q = np.linspace(0.0005, 0.9995, 1000)
    return float(np.mean(np.abs(np.quantile(a, q) - np.quantile(b, q))))


def ks(a, b):
    if not len(a) or not len(b):
        return float('nan')
    x = np.sort(np.r_[a[:: max(len(a) // 200000, 1)], b[:: max(len(b) // 200000, 1)]])
    ca = np.searchsorted(np.sort(a), x) / len(a)
    cb = np.searchsorted(np.sort(b), x) / len(b)
    return float(np.max(np.abs(ca - cb)))


def metric(d, name):
    if name == 'acceleration':
        x = d['acc']
        return x[x > 0.02]
    if name == 'braking':
        x = d['acc']
        return -x[x < -0.02]
    return d[name]


def summary(x):
    if not len(x):
        return {}
    return dict(mean=round(float(x.mean()), 3), p5=round(float(np.percentile(x, 5)), 3), p50=round(float(np.percentile(x, 50)), 3), p95=round(float(np.percentile(x, 95)), 3), p99=round(float(np.percentile(x, 99)), 3), n=int(len(x)))


def main(argv):
    a = argparse.ArgumentParser(prog='cars dist', description=__doc__)
    a.add_argument('--a', required=True, help='a trace, or real:NAME')
    a.add_argument('--b', required=True, help=f'a trace, or real:NAME with NAME one of {", ".join(real_sets())}')
    a.add_argument('--begin', type=float)
    a.add_argument('--end', type=float)
    a.add_argument('--stride', type=int, default=1)
    a.add_argument('--net')
    a.add_argument('--out', default='dist')
    a.add_argument('--json', action='store_true')
    a = a.parse_args(argv)
    A = load(a.a, a.begin, a.end, a.net, a.stride)
    B = load(a.b, a.begin, a.end, a.net, a.stride)
    rows = {}
    for m in METRICS:
        x, y = metric(A, m), metric(B, m)
        spread = float(np.std(y)) if len(y) else float('nan')
        w = wasserstein(x, y)
        rows[m] = dict(unit=UNITS[m], a=summary(x), b=summary(y), distance=round(w, 3), distance_in_sds=round(w / spread, 3) if spread else None, ks=round(ks(x, y), 3))
    rows['lane_changes_per_km'] = dict(a=round(A['lc_per_km'], 4), b=round(B['lc_per_km'], 4), ratio=round(A['lc_per_km'] / B['lc_per_km'], 3) if B['lc_per_km'] else None)
    worst = sorted((m for m in METRICS if rows[m]['distance_in_sds'] is not None), key=lambda m: -rows[m]['distance_in_sds'])
    rows['overall'] = dict(mean_distance_in_sds=round(float(np.mean([rows[m]['distance_in_sds'] for m in worst])), 3), worst=worst[0] if worst else None)
    if a.json:
        print(json.dumps(rows, indent=1))
    else:
        print(f"a = {A['name']} ({A['veh_km']:.0f} veh km)   b = {B['name']} ({B['veh_km']:.0f} veh km)")
        print(f"{'':14} {'a mean':>9} {'a p50':>8} {'a p95':>8} {'b mean':>9} {'b p50':>8} {'b p95':>8} {'distance':>9} {'in SDs of b':>11} {'KS':>6}")
        for m in METRICS:
            r = rows[m]
            g = lambda s, k: s.get(k, float('nan'))
            print(f"{m:14} {g(r['a'], 'mean'):9.2f} {g(r['a'], 'p50'):8.2f} {g(r['a'], 'p95'):8.2f} {g(r['b'], 'mean'):9.2f} {g(r['b'], 'p50'):8.2f} {g(r['b'], 'p95'):8.2f} {r['distance']:9.3f} {r['distance_in_sds']:11.3f} {r['ks']:6.3f}  {r['unit']}")
        r = rows['lane_changes_per_km']
        print(f"lane changes per vehicle km: a {r['a']}  b {r['b']}  ratio {r['ratio']}")
        print(f"overall distance {rows['overall']['mean_distance_in_sds']} SDs, worst on {rows['overall']['worst']}")
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(a.out, exist_ok=True)
    fig, axs = plt.subplots(2, 3, figsize=(15, 8))
    for ax, m in zip(axs.flat, METRICS):
        x, y = metric(A, m), metric(B, m)
        hi = float(np.nanpercentile(np.r_[x[:200000], y[:200000]], 99.5)) if len(x) + len(y) else 1.0
        bins = np.linspace(0, max(hi, 1e-3), 60)
        ax.hist(x, bins=bins, density=True, histtype='step', lw=1.6, label=f"a {A['name']}")
        ax.hist(y, bins=bins, density=True, histtype='step', lw=1.6, label=f"b {B['name']}")
        ax.set(title=f"{m}: distance {rows[m]['distance']} {UNITS[m]}", xlabel=UNITS[m])
        ax.legend(fontsize=8)
    axs.flat[-1].bar(['a', 'b'], [A['lc_per_km'], B['lc_per_km']], color=['#1f77b4', '#ff7f0e'])
    axs.flat[-1].set(title='lane changes per vehicle km')
    fig.tight_layout()
    path = os.path.join(a.out, 'dist.png')
    fig.savefig(path, dpi=110)
    plt.close(fig)
    with open(os.path.join(a.out, 'dist.json'), 'w') as f:
        json.dump(rows, f, indent=1)
    print(f'chart {path}')
