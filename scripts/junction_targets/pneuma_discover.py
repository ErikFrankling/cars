"""Finds unsignalised crossings in pNEUMA from the tracks alone: where cars from one heading slow down while cars from another heading cross, with no signal node within 35 m.
Run on one member per drone. Prints candidates with any OSM stop or give-way tag within 20 m."""
import glob
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
from common import OUT
import jx
import pneuma_scan as ps


def main():
    nodes = ps.osm()
    sig = np.array([(n[0], n[1]) for n in nodes if n[2] == 'traffic_signals'])
    sg = np.array([(n[0], n[1]) for n in nodes if n[2] in ('stop', 'give_way')])
    out = []
    for f in sorted(glob.glob(str(OUT / 'pneuma' / '20181024_d*_0900_0930.npz'))):
        tr = ps.load(f)
        drone = pathlib.Path(f).stem.split('_')[1]
        P = []
        for a in tr:
            v = a['v']
            if len(v) < 25:
                continue
            s = np.r_[0, np.cumsum(np.hypot(np.diff(a['x']), np.diff(a['y'])))]
            low = np.flatnonzero((v < 3.) & (np.r_[True, v[:-1] >= v[1:]]) & (np.r_[v[:-1] <= v[1:], True]))
            if len(low) > 4:
                low = low[np.argsort(v[low])[:4]]
            for k in low:
                u, w = jx.index_arc(s, s[k] - 12), min(jx.index_arc(s, s[k] + 12), len(s) - 1)
                if s[k] - s[u] < 8 or s[w] - s[k] < 8:
                    continue
                P.append((a['x'][k], a['y'][k], jx.heading(a['x'], a['y'], u, k), a['id']))
        P = np.array(P)
        if not len(P):
            continue
        ix = np.floor(P[:, 0] / 15).astype(int)
        iy = np.floor(P[:, 1] / 15).astype(int)
        hb = np.floor((P[:, 2] + np.pi) / (np.pi / 4)).astype(int) % 8
        key = ix * 100000 + iy * 10 + hb
        uq, cnt = np.unique(key, return_counts=True)
        for k in uq[cnt >= 10]:
            m = key == k
            cx, cy, hd = P[m, 0].mean(), P[m, 1].mean(), np.angle(np.exp(1j * P[m, 2]).mean())
            if np.hypot(*(sig - [cx, cy]).T).min() < 35:
                continue
            # cars crossing near here at speed, from another heading
            cross = 0
            for a in tr:
                d = np.hypot(a['x'] - cx, a['y'] - cy)
                j = int(d.argmin())
                if d[j] > 12 or j < 3 or j > len(d) - 4 or a['v'][j] < 3:
                    continue
                h = jx.heading(a['x'], a['y'], max(j - 5, 0), min(j + 5, len(d) - 1))
                if abs(jx.wrap(h - hd)) > np.deg2rad(50) and abs(jx.wrap(h - hd)) < np.deg2rad(130):
                    cross += 1
            if cross < 15:
                continue
            tag = float(np.hypot(*(sg - [cx, cy]).T).min())
            out.append(dict(drone=drone, x=round(float(cx), 1), y=round(float(cy), 1), hd=round(float(hd), 2), slow=int(m.sum()), cross=cross, tag_dist=round(tag, 1), sig_dist=round(float(np.hypot(*(sig - [cx, cy]).T).min()), 1)))
        print(drone, len(tr), flush=True)
    out.sort(key=lambda z: -min(z['slow'], z['cross']))
    json.dump(out, open(OUT / 'pneuma_discovered.json', 'w'), indent=0)
    for z in out[:40]:
        print(z)


if __name__ == '__main__':
    main()
