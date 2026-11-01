#!/usr/bin/env python3
"""Item 19 of research/truth/05: critical gap and follow-up at a single-lane roundabout, from simulated trajectories,
with the censored lognormal fit report 05 used on the Swiss data. Target 2.65-3.25 s and 2.3-3.1 s.

    python3 scripts/human_roundabout.py --out DIR [--tune gap_roundabout=1.0 ...]
"""
import argparse
import json
import math
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]


def net(d):
    r = 18.0
    arms = 4
    nodes = ''
    edges = ''
    for i in range(arms):
        a = i * 2 * math.pi / arms
        x, y = r * math.cos(a), r * math.sin(a)
        nodes += f'<node id="j{i}" x="{x:.2f}" y="{y:.2f}" type="priority"/><node id="o{i}" x="{300*math.cos(a):.2f}" y="{300*math.sin(a):.2f}"/>'
        edges += f'<edge id="in{i}" from="o{i}" to="j{i}" numLanes="1" speed="13.89"/><edge id="out{i}" from="j{i}" to="o{i}" numLanes="1" speed="13.89"/>'
        b = (i + 1) % arms
        pts = ' '.join(f'{r*math.cos(a + k/8*2*math.pi/arms):.2f},{r*math.sin(a + k/8*2*math.pi/arms):.2f}' for k in range(9))
        edges += f'<edge id="ring{i}" from="j{i}" to="j{b}" numLanes="1" speed="8.33" priority="3" shape="{pts}"/>'
    (d / 'n.nod.xml').write_text(f'<nodes>{nodes}</nodes>')
    (d / 'n.edg.xml').write_text(f'<edges>{edges}</edges>')
    rb = ' '.join(f'ring{i}' for i in range(arms))
    nd = ' '.join(f'j{i}' for i in range(arms))
    (d / 'n.xml').write_text(f'<additional/>')
    (d / 'nb.xml').write_text(f'<nodes>{nodes}<roundabout nodes="{nd}" edges="{rb}"/></nodes>')
    subprocess.run(['netconvert', '-n', d / 'nb.xml', '-e', d / 'n.edg.xml', '-o', d / 'net.xml', '--no-turnarounds', 'true'], check=True, capture_output=True)


def routes(d, q_in, dur, seed):
    rng = np.random.default_rng(seed)
    rows = []
    for arm in range(4):
        for t in np.cumsum(rng.exponential(3600 / q_in, int(dur * q_in / 3600 * 1.3))):
            if t >= dur:
                break
            exit_arm = (arm + rng.integers(1, 4)) % 4
            ring = ' '.join(f'ring{(arm + k) % 4}' for k in range(0, (exit_arm - arm) % 4))
            rows.append((t, f'<vehicle id="a{arm}_{t:.1f}" type="h" depart="{t:.1f}" departSpeed="max"><route edges="in{arm} {ring} out{exit_arm}"/></vehicle>'))
    rows.sort()
    vt = '<vType id="h" carFollowModel="Human" length="5" minGap="2.5" speedDev="0.05"/>'
    (d / 'r.xml').write_text(f'<routes>{vt}' + ''.join(r[1] for r in rows) + '</routes>')


def decisions(f):
    """Per entry: the gaps offered on the ring to the first car at the line, in seconds at the point of entry."""
    rows, follow = [], []
    for arm in range(4):
        lane = f'in{arm}_0'
        ring_up = f'ring{(arm - 1) % 4}_0'
        ring_len = f[f.lane == ring_up].pos.max() if (f.lane == ring_up).any() else 0
        passing = f[f.lane == ring_up].sort_values('time')
        # Time each ring car reaches the end of the ring edge before this entry.
        crossings = []
        for trip, g in passing.groupby('trip'):
            crossings.append(g.time.iloc[-1])
        crossings = np.array(sorted(crossings))
        ent = f[f.lane == lane]
        length = ent.pos.max()
        entries = []
        for trip, g in ent.groupby('trip'):
            g = g.sort_values('time')
            near = g[length - g.pos < 12.0]
            if near.empty:
                continue
            t_arrive, t_enter = near.time.iloc[0], g.time.iloc[-1]
            entries.append((t_arrive, t_enter, trip))
        entries.sort()
        last = None
        for t_arrive, t_enter, trip in entries:
            first_in_line = last is None or t_arrive >= last
            if not first_in_line:
                follow.append(t_enter - last)
            else:
                k = np.searchsorted(crossings, t_enter)
                if 0 < k < len(crossings):
                    accepted = crossings[k] - crossings[k - 1]
                    # Gaps that closed while it waited at the line.
                    k0 = np.searchsorted(crossings, t_arrive)
                    rejected = np.diff(crossings[max(k0 - 1, 0):k]) if k > k0 else np.array([])
                    rows.append((accepted, rejected.max() if len(rejected) else 0.0))
            last = t_enter
    return np.array(rows), np.array(follow)


def censored(rows):
    a = np.maximum(rows[:, 0], 0.1)
    r = rows[:, 1]
    def nll(p):
        mu, s = p
        s = abs(s) + 1e-3
        fa = norm.cdf((np.log(a) - mu) / s)
        fr = np.where(r > 0, norm.cdf((np.log(np.maximum(r, 0.1)) - mu) / s), 0.0)
        return -np.log(np.maximum(fa - fr, 1e-9)).sum()
    m = minimize(nll, [1.0, 0.3], method='Nelder-Mead').x
    return float(np.exp(m[0])), abs(float(m[1]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='/tmp/human-roundabout')
    p.add_argument('--tune', action='append', default=[])
    p.add_argument('--dt', type=float, default=0.5)
    p.add_argument('--seeds', type=int, default=3)
    p.add_argument('--inflow', type=float, default=350)
    a = p.parse_args()
    d = Path(a.out)
    d.mkdir(parents=True, exist_ok=True)
    net(d)
    bin_ = os.environ.get('CARS_BIN', ROOT / 'target/release/cars')
    lock = [] if os.environ.get('CARS_GPU_HELD') or os.environ.get('CARS_ADAPTER') else ['flock', '/tmp/cars-gpu.lock']
    all_rows, all_follow, collisions = [], [], 0
    for seed in range(a.seeds):
        routes(d, a.inflow, 1800, seed)
        fc = d / f's{seed}.csv'
        rep = d / f's{seed}.json'
        subprocess.run(list(map(str, [*lock, bin_, 'run', '--net', d / 'net.xml', '--routes', d / 'r.xml', '--dt', a.dt, '--end', 2000, '--seed', seed, '--fcd', fc, '--fcd-interval', a.dt, '--report-json', rep, *[x for t in a.tune for x in ('--tune', t)]])), check=True, capture_output=True)
        f = pd.read_csv(fc, usecols=['time', 'trip', 'lane', 'pos', 'speed'], dtype={'trip': str, 'lane': str})
        r, fo = decisions(f)
        all_rows.append(r)
        all_follow.append(fo)
        collisions += json.loads(rep.read_text())['collision_incidents']
    rows = np.vstack(all_rows)
    fo = np.concatenate(all_follow)
    med, sd = censored(rows)
    out = dict(decisions=len(rows), with_rejected=int((rows[:, 1] > 0).sum()), critical_gap_median=med, log_sd=sd, follow_up_median=float(np.median(fo[(fo > 0.5) & (fo < 10)])) if len(fo) else None, follow_ups=len(fo), collisions=collisions, tune=a.tune)
    (d / 'roundabout.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out))


if __name__ == '__main__':
    main()
