#!/usr/bin/env python3
"""The gate's "physically real" check, measured from a run's own trajectories: how cars accelerate, brake, jerk,
creep, change lane and keep their gaps, set against published figures for real cars and drivers.

    python3 scripts/physics_realism.py --fcd f.csv --dt 1 [--json out.json]

The FCD must be written every step (`--fcd-interval` = dt). Figures come with their source and class in REAL below;
a row outside its range is a fault to explain. Matching another simulator is not evidence.
"""
import argparse
import json

import numpy as np
import pandas as pd

# Name: (statistic, low, high, source). Sources: research/truth/11-vehicle-physics.md and what it grades.
REAL = {
    'acceleration p50, m/s2, from under 10 m/s': ('p50', 0.8, 2.0, 'Long 2000, measured at signals, 2.02 at rest falling with speed'),
    'acceleration p99, m/s2': ('p99', 1.5, 3.5, 'Long 2000; Bosetti 2014 upper envelope, measured'),
    'braking p50, m/s2': ('p50', 0.3, 2.0, 'Bosetti 2014, measured'),
    'braking p99, m/s2': ('p99', 2.0, 4.5, 'Bosetti 2014, ordinary driving, measured; emergencies are the tail above'),
    'braking worst, m/s2': ('max', 0.0, 9.0, 'ADAC tyre tests, dry, measured: past this no car can'),
    'jerk p99, m/s3': ('p99', 0.0, 5.0, 'design range from comfort studies; graded weak in report 11'),
    'moving this slowly: share of samples between 0 and 0.3 m/s': ('share', 0.0, 0.02, 'invented bound: real cars stand or roll, they do not creep at walking pace a tenth'),
    'stand gap bumper to bumper p50, m': ('p50', 1.5, 3.5, 'TRVMB jam spacing 7.43 m less a 4.8-5 m car'),
    'time headway above 5 m/s p50, s': ('p50', 1.2, 2.5, 'common range from field headway studies; design range'),
    'time headway above 5 m/s p1, s': ('p1', 0.4, 1.2, 'common range from field headway studies; design range'),
    'lane change seconds p50': ('p50', 3.0, 8.0, 'field 5-8 s in report 15 register, 3 s lower from congested merges'),
    'lane change heading at over 2 m/s p99, degrees': ('p99', 0.0, 13.0, 'report 11, I11'),
    'sideways per metre forward under 2 m/s p99': ('p99', 0.0, 0.7, 'kinematic bicycle at 5.5 m turning radius: 3.2 m across takes about 7.8 m forward, peak about 35 degrees'),
    'sideways while at a stand: share of change samples': ('share', 0.0, 0.0, 'no car moves sideways at a stand'),
}


def stat(x, kind):
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return float('nan')
    if kind == 'max':
        return float(np.max(x))
    return float(np.percentile(x, float(kind[1:])))


def measure(f, dt):
    f = f.sort_values(['trip', 'time'])
    same = f.trip.values[1:] == f.trip.values[:-1]
    step = np.isclose(f.time.values[1:] - f.time.values[:-1], dt)
    ok = same & step
    v0, v1 = f.speed.values[:-1][ok], f.speed.values[1:][ok]
    acc = (v1 - v0) / dt
    a = {}
    a['acceleration p50, m/s2, from under 10 m/s'] = acc[(acc > 0.2) & (v0 < 10)]
    a['acceleration p99, m/s2'] = acc[acc > 0.2]
    a['braking p50, m/s2'] = -acc[acc < -0.2]
    a['braking p99, m/s2'] = -acc[acc < -0.2]
    a['braking worst, m/s2'] = -acc[acc < 0]
    both = ok[1:] & ok[:-1]
    d = (f.speed.values[1:] - f.speed.values[:-1]) / dt
    a['jerk p99, m/s3'] = np.abs((d[1:] - d[:-1])[both] / dt)
    v = f.speed.values
    out = {'samples': int(len(f)), 'rows': []}
    a['moving this slowly: share of samples between 0 and 0.3 m/s'] = float(((v > 0) & (v < 0.3)).mean())
    # Same lane leaders.
    g = f.sort_values(['time', 'lane', 'pos'])
    near = (g.lane.values[1:] == g.lane.values[:-1]) & (g.time.values[1:] == g.time.values[:-1])
    gap = g.pos.values[1:] - g.length.values[1:] - g.pos.values[:-1]
    fv = g.speed.values[:-1]
    a['stand gap bumper to bumper p50, m'] = gap[near & (fv < 0.1) & (gap > -1) & (gap < 15)]
    head = gap[near & (fv > 5)] / fv[near & (fv > 5)]
    a['time headway above 5 m/s p50, s'] = head[head > 0]
    a['time headway above 5 m/s p1, s'] = head[head > 0]
    # Lane changes, from the sideways offset.
    off = f.offset.values
    o0, o1 = off[:-1][ok], off[1:][ok]
    in_change = (np.abs(o0) > 1e-3) & (np.abs(o1) > 1e-3)
    lat = np.abs(o1 - o0)[in_change] / dt
    fw = (0.5 * (v0 + v1))[in_change]
    a['lane change heading at over 2 m/s p99, degrees'] = np.degrees(np.arctan2(lat[fw > 2], fw[fw > 2]))
    slow = (fw > 0.01) & (fw <= 2)
    a['sideways per metre forward under 2 m/s p99'] = lat[slow] / fw[slow]
    a['sideways while at a stand: share of change samples'] = float(((fw <= 0.01) & (lat > 1e-3)).sum() / max(in_change.sum(), 1))
    mov = np.abs(off) > 1e-3
    trips = f.trip.values
    dur = []
    start = None
    for i in range(len(f)):
        if mov[i] and start is None:
            start = i
        if start is not None and (not mov[i] or trips[i] != trips[start]):
            if trips[i] == trips[start] and start > 0 and trips[start - 1] == trips[start]:
                dur.append(f.time.values[i] - f.time.values[start])
            start = i if mov[i] else None
    a['lane change seconds p50'] = np.array(dur)
    out['lane_changes_seen'] = len(dur)
    for name, (kind, lo, hi, source) in REAL.items():
        x = a[name]
        val = x if isinstance(x, float) else stat(x, kind)
        n = 1 if isinstance(x, float) else len(x)
        good = bool(lo - 1e-9 <= val <= hi + 1e-9) if val == val else False
        out['rows'].append(dict(name=name, value=round(val, 3), low=lo, high=hi, n=n, ok=good, source=source))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--fcd', required=True)
    p.add_argument('--dt', type=float, required=True)
    p.add_argument('--json')
    a = p.parse_args()
    f = pd.read_csv(a.fcd, usecols=['time', 'trip', 'lane', 'pos', 'speed', 'length', 'offset'], dtype={'trip': str, 'lane': str})
    r = measure(f, a.dt)
    for row in r['rows']:
        print(f"{'ok  ' if row['ok'] else 'FAIL'} {row['value']:>9} in {row['low']}..{row['high']}  {row['name']}  (n {row['n']})")
    print(f"{r['samples']} samples, {r['lane_changes_seen']} lane changes seen whole")
    if a.json:
        open(a.json, 'w').write(json.dumps(r, indent=1))


if __name__ == '__main__':
    main()
