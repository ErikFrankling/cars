#!/usr/bin/env python3
"""Print noise_micro.json compactly."""
import json
import sys

d = json.load(open(sys.argv[1]))
for s, bands in d['sites'].items():
    for b, r in bands.items():
        w = r['within']
        f = lambda k: 'none' if not w[k] else f"{w[k]['p50']:.3f}/{w[k]['p90']:.3f}/{w[k]['max']:.3f}"
        p = r['pooled']
        print(f"{s:8} {b:6} n {r['n']:8} blk {r['blocks']:3} W1 a {f('a')} j {f('j')} T {f('T')} | a q {[round(x, 2) for x in p['a_q']]} |j|p95 {p['j_abs_p95']:.2f} T q {[round(x, 2) for x in p['T_q']]}")
print()
for k, v in d['between'].items():
    print(k, {a: round(b, 3) for a, b in v.items()})
print()
print(json.dumps(d['queue'])[:1800])
print()
print(json.dumps(d['roundabout']))
print({k: (v['n'], round(v['crit'], 2)) for k, v in d['roundabout_sessions'].items()})
print()
print({h: (v['n'], v['d1090'], round(v['peak'], 2)) for h, v in d['lane_change_by_hour'].items()})
