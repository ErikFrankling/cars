#!/usr/bin/env python3
"""Audit of the earlier point-queue model: reproduces its numbers, then shows what it assumed.

Does not edit coordinated_intersections.py. Writes fig/09b-audit-old.csv.
"""
import csv, statistics, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coordinated_intersections as old

OUT = Path(__file__).resolve().parents[1] / 'fig' / '09b-audit-old.csv'
rows = []


def mean(demand, policy, seeds=8, **kw):
    rs = [old.run(old.arrivals(demand, s), policy, **kw) for s in range(seeds)]
    return statistics.mean(r['flow'] for r in rs), statistics.mean(r['queue_delay'] for r in rs)


def rec(label, demand, policy, **kw):
    f, d = mean(demand, policy, **kw)
    rows.append(dict(case=label, demand=demand, policy=policy, flow=round(f, 1), queue_delay=round(d, 2)))
    print(rows[-1], flush=True)


# 1. the published figures
rec('published_batch_gain', 4400, 'batch', minimum=3., maximum=60., gap=2.)
rec('published_batch_gain', 4400, 'signal', minimum=3., maximum=60., gap=2.)
for cross in (1.2, 3.0):
    rec(f'published_sensitivity_cross_{cross}', 3000, 'fcfs', seeds=4, cross=cross)
rec('published_sensitivity_signal', 3000, 'signal', seeds=4)
# 2. true saturation capacity of each abstract policy
for policy in ('signal', 'fcfs', 'batch'):
    rec('saturated_12000', 12000, policy, minimum=3., maximum=60., gap=2.)
# 3. the model's own analytic limit: 4 vehicles per 2*cross when 2*cross >= h
for cross in (1.2, 1.5, 2.0, 3.0, 3.16):
    rec(f'saturated_cross_{cross}', 12000, 'fcfs', seeds=2, cross=cross)
    rows.append(dict(case=f'analytic_cross_{cross}', demand=12000, policy='fcfs',
                     flow=round(4 * 3600 / max(2 * cross, 2.0), 1), queue_delay=''))
with OUT.open('w') as f:
    w = csv.DictWriter(f, fieldnames=rows[0])
    w.writeheader()
    w.writerows(rows)
