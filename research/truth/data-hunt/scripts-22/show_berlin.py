#!/usr/bin/env python3
"""Print noise_berlin.json: floors, which metric catches which surrogate, ensemble checks."""
import json
import sys

d = json.load(open(sys.argv[1]))
print(d['sites'], d['classes'])
F, S = d['floor'], d['surrogate']
for k, v in F.items():
    print(f"{k:32} p50 {v['p50']:.3f} p90 {v['p90']:.3f} max {v['max']:.3f}")
print()
for n in S:
    print(n, '=> flagged', len(d['flags'][n]), [(k, round(S[n][k] / max(F[k]['p90'], 1e-9), 1)) for k in d['flags'][n]])
print()
for n, e in d['ensemble'].items():
    print(n, {k: round(v, 3) for k, v in e.items()})
print()
keys = list(F)
for n in S:
    print(n)
    print('   ', {k: round(S[n][k], 3) for k in keys})
