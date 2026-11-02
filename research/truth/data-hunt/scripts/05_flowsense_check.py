#!/usr/bin/env python3
# Streams FlowSense geojson line by line; compares trajectory counts to Stockholm Arstrafik counts.
# Usage: 05_flowsense_check2.py FLOWS.geojson GT.geojson
import json, sys, math, statistics as st
key = None; cell = 50; grid = {}; n = 0; total = 0; keys = None; byspeed = {}
with open(sys.argv[1]) as fh:
    for line in fh:
        line = line.strip().rstrip(",")
        if not line.startswith('{ "type": "Feature"'): continue
        f = json.loads(line); p = f["properties"]
        if keys is None:
            keys = [k for k in p if k.startswith("trajcount")]; print("count keys", keys); key = keys[0]
            print("all props", list(p.keys()))
        n += 1; t = p.get(key) or 0; total += t
        g = f["geometry"]
        if not g: continue
        cs = g["coordinates"]
        if g["type"] == "MultiLineString": cs = [q for l in cs for q in l]
        counts = tuple((p.get(k) or 0) for k in keys)
        for a, b in zip(cs, cs[1:]):
            m = max(1, int(math.dist(a[:2], b[:2]) // 25))
            for i in range(m + 1):
                x = a[0] + (b[0]-a[0])*i/m; y = a[1] + (b[1]-a[1])*i/m
                grid.setdefault((int(x//cell), int(y//cell)), []).append((x, y, counts))
print("segments", n, "sum trajcount over segments", total, "cells", len(grid))
gt = json.load(open(sys.argv[2]))["features"]
import re
hkeys = [k for k in gt[0]["properties"] if re.match(r"trafikflöde_(\d\d)_(\d\d)__fordon_dygn__alla_fordon$", k) and int(k[12:14])+1 == int(k[15:17])]
print("hour keys", len(hkeys), "sample", hkeys[:2], "non-hour flow keys", [k for k in gt[0]["properties"] if "trafikflöde" in k and "fordon_dygn" not in k])
def mid(c):
    if isinstance(c[0][0], list): c = c[0]
    return c[len(c)//2]
def near(x, y, r=15):
    best = None; bd = r; cx, cy = int(x//cell), int(y//cell)
    for i in range(cx-1, cx+2):
        for j in range(cy-1, cy+2):
            for (px, py, c) in grid.get((i, j), []):
                d = math.hypot(px-x, py-y)
                if d < bd: bd, best = d, c
    return best
rows = []
for f in gt:
    p = f["properties"]
    h = [p.get(k) for k in hkeys]
    if any(v is None for v in h) or not f["geometry"]: continue
    x, y = mid(f["geometry"]["coordinates"])[:2]
    c = near(x, y)
    if c is None: continue
    rows.append((sum(h), c[0], p.get("riktningsuppdelad"), p.get("namn")))
print("gt", len(gt), "with hourly flows and matched", len(rows))
def rank(a):
    o = sorted(range(len(a)), key=lambda i: a[i]); r = [0]*len(a); i = 0
    while i < len(a):
        j = i
        while j+1 < len(a) and a[o[j+1]] == a[o[i]]: j += 1
        for k in range(i, j+1): r[o[k]] = (i+j)/2
        i = j+1
    return r
def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    return sum((x-ma)*(y-mb) for x, y in zip(a, b))/math.sqrt(sum((x-ma)**2 for x in a)*sum((y-mb)**2 for y in b))
a = [r[0] for r in rows]; b = [r[1] for r in rows]
print("pearson", round(corr(a, b), 3), "spearman", round(corr(rank(a), rank(b)), 3))
nz = [(x, y) for x, y in zip(a, b) if x > 0 and y > 0]
print("nonzero", len(nz), "log-log pearson", round(corr([math.log(x) for x, _ in nz], [math.log(y) for _, y in nz]), 3))
# fit in log space, spread of residual in factor terms
la = [math.log(x) for x, _ in nz]; lb = [math.log(y) for _, y in nz]
sl = corr(la, lb)*st.pstdev(lb)/st.pstdev(la); ic = st.mean(lb)-sl*st.mean(la)
res = sorted(l-(ic+sl*k) for k, l in zip(la, lb))
print("log fit slope", round(sl, 3), "residual p10,p90 as factors", round(math.exp(res[len(res)//10]), 2), round(math.exp(res[9*len(res)//10]), 2))
for lo, hi in [(0,2000),(2000,5000),(5000,10000),(10000,20000),(20000,10**9)]:
    s = sorted(y/x for x, y in nz if lo <= x < hi)
    if len(s) > 5: print(f"  measured {lo}-{hi} veh/day: n={len(s)} trajectories per measured veh/day p10 {s[len(s)//10]:.4f} p50 {s[len(s)//2]:.4f} p90 {s[9*len(s)//10]:.4f}")
print("measured total mean", round(st.mean(a)), "max", max(a), "zero traj", sum(1 for v in b if v == 0))
