#!/usr/bin/env python3
"""Lane-km per km² and vehicles in a radio disc, from a SUMO net. Usage: v2x_density.py net.xml out.json label"""
import sys, json, math
import xml.etree.ElementTree as ET
import numpy as np
net, out, label = sys.argv[1], sys.argv[2], sys.argv[3]
pts, lens = [], []
for ev, el in ET.iterparse(net):
    if el.tag == "edge":
        if el.get("function") in (None, "normal"):
            for l in el.findall("lane"):
                allow = l.get("allow") or ""
                dis = l.get("disallow") or ""
                if "passenger" in dis or (allow and "passenger" not in allow):
                    continue
                xy = [tuple(map(float, p.split(","))) for p in l.get("shape").split()]
                for (a, b), (c, d) in zip(xy, xy[1:]):
                    s = math.hypot(c - a, d - b)
                    if s > 0:
                        pts.append(((a + c) / 2, (b + d) / 2)); lens.append(s)
        el.clear()
P, L = np.array(pts), np.array(lens) / 1000
C = 250.0
ix, iy = (P[:, 0] // C).astype(int), (P[:, 1] // C).astype(int)
ix -= ix.min(); iy -= iy.min()
G = np.zeros((ix.max() + 1, iy.max() + 1))
np.add.at(G, (ix, iy), L)
res = {"label": label, "lane_km_total": float(L.sum()), "cell_m": C}
gx, gy = np.meshgrid(np.arange(G.shape[0]), np.arange(G.shape[1]), indexing="ij")
for R in (100, 150, 300, 500, 800):
    r = int(R // C) + 1
    k = np.array([[1 if (i * C) ** 2 + (j * C) ** 2 <= R ** 2 or (i == 0 and j == 0) else 0 for j in range(-r, r + 1)] for i in range(-r, r + 1)], float)
    # lane-km inside a disc at every cell, via FFT convolution
    F = np.fft.rfft2(G, s=(G.shape[0] + 2 * r + 1, G.shape[1] + 2 * r + 1)) * np.fft.rfft2(k, s=(G.shape[0] + 2 * r + 1, G.shape[1] + 2 * r + 1))
    D = np.fft.irfft2(F, s=(G.shape[0] + 2 * r + 1, G.shape[1] + 2 * r + 1))[r:r + G.shape[0], r:r + G.shape[1]]
    area = k.sum() * (C / 1000) ** 2
    v = D[G > 0]
    res[f"disc_{R}"] = {"p50_lane_km": float(np.percentile(v, 50)), "p95_lane_km": float(np.percentile(v, 95)), "p99_lane_km": float(np.percentile(v, 99)), "max_lane_km": float(v.max()), "area_km2_grid": float(area)}
c = G[G > 0] / (C / 1000) ** 2
res["lane_km_per_km2"] = {"p50": float(np.percentile(c, 50)), "p95": float(np.percentile(c, 95)), "p99": float(np.percentile(c, 99)), "max": float(c.max())}
json.dump(res, open(out, "a")); open(out, "a").write("\n")
print(json.dumps(res, indent=0)[:1500])
