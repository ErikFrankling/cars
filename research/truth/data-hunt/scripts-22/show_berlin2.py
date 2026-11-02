#!/usr/bin/env python3
"""Compact table for the report: floors in both periods, detection at the max rule, false alarms, nulls."""
import json
import sys

a, b, e = (json.load(open(sys.argv[i])) for i in (1, 2, 3))
print('2019', a['sites'], a['classes'], a['days'])
print('2024', b['sites'], b['classes'], b['days'])
for k, v in a['floor'].items():
    w = b['floor'][k]
    print(f"{k:30} 2019 p50 {v['p50']:.3f} p90 {v['p90']:.3f} max {v['max']:.3f} | 2024 p50 {w['p50']:.3f} p90 {w['p90']:.3f} max {w['max']:.3f}")
print()
for r, days in a['loo_false_alarms'].items():
    print('2019 LOO', r, {d: len(x) for d, x in days.items()})
for r, days in b['loo_false_alarms'].items():
    print('2024 LOO', r, {d: len(x) for d, x in days.items()})
print(a['loo_false_alarms']['1.25 max'], a['loo_false_alarms']['max'])
print()
n = len(a['floor'])
for s in a['surrogate']:
    print(f"{s:42} p90:{len(a['flags'][s]):2} max:{len(a['flags_max'][s]):2} 1.25max:{len(a['flags_125max'][s]):2} of {n} {a['flags_125max'][s]}")
print()
for s, e2 in a['ensemble'].items():
    print(f"{s:42} crps_q {e2['crps_flow_norm']:.3f} crps_v {e2['crps_speed_kmh']:.2f} outer {e2['rank_outer_share']:.3f} low {e2['rank_low']:.3f} high {e2['rank_high']:.3f}")
print()
print(json.dumps(e['floor']))
print(json.dumps(e['null'], indent=0))
print(e['classes'])
