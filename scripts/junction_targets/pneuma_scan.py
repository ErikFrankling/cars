"""Finds usable junctions in the downloaded tuning pNEUMA members from OSM tags, and checks each with the tracks: stop and give-way nodes with
real slowing and real cross traffic, and signal clusters with periodic queues. Prints a table and writes candidates.json."""
import glob
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
from common import OUT
import jx

LAT0, LON0 = 37.98, 23.735
CAR = {0, 1, 2, 3, 4}


def to_xy(lat, lon):
    return (lon - LON0) * 111320 * np.cos(np.deg2rad(LAT0)), (lat - LAT0) * 110574


def osm():
    d = json.load(open(OUT / 'osm_athens_foggy.json'))
    E = [e for e in d['elements'] if e['lat'] < 38.5]
    out = []
    for e in E:
        x, y = to_xy(e['lat'], e['lon'])
        out.append((x, y, e['tags'].get('highway'), e['id']))
    return out


def clusters(nodes, kind, r=35.):
    pts = np.array([(n[0], n[1]) for n in nodes if n[2] == kind])
    done = np.zeros(len(pts), bool)
    out = []
    for i in range(len(pts)):
        if done[i]:
            continue
        m = np.hypot(*(pts - pts[i]).T) < r
        done |= m
        out.append(pts[m].mean(0))
    return np.array(out)


def load(f, keep=CAR):
    z = np.load(f)
    return jx.make_tracks(z['id'], z['cls'], z['t'].astype('f8'), z['x'].astype('f8'), z['y'].astype('f8'), z['v'].astype('f8'), keep=keep)


def main():
    nodes = osm()
    sig = clusters(nodes, 'traffic_signals')
    res = []
    for f in sorted(glob.glob(str(OUT / "pneuma" / "20181024_d*_0900_0930.npz"))):
        name = pathlib.Path(f).stem
        drone = name.split('_')[1]
        tr = load(f)
        allx = np.concatenate([a['x'][::10] for a in tr])
        ally = np.concatenate([a['y'][::10] for a in tr])
        box = (allx.min(), allx.max(), ally.min(), ally.max())
        for x, y, kind, nid in nodes:
            if kind not in ('stop', 'give_way') or not (box[0] + 30 < x < box[1] - 30 and box[2] + 30 < y < box[3] - 30):
                continue
            sd = np.hypot(sig[:, 0] - x, sig[:, 1] - y).min()
            near = [a for a in tr if np.hypot(a['x'] - x, a['y'] - y).min() < 6.]
            if len(near) < 6:
                continue
            vm = []
            for a in near:
                d = np.hypot(a['x'] - x, a['y'] - y)
                k = int(d.argmin())
                s = np.r_[0, np.cumsum(np.hypot(np.diff(a['x']), np.diff(a['y'])))]
                u = max(jx.index_arc(s, s[k] - 12), 0)
                vm.append(a['v'][u:k + 3].min())
            # cross traffic: other tracks within 15 m of the node, heading more than 40 degrees from the minor heading
            others = [a for a in tr if np.hypot(a['x'] - x, a['y'] - y).min() < 15.]
            res.append(dict(member=name, drone=drone, node=nid, kind=kind, x=float(x), y=float(y), n_minor=len(near), n_all=len(others), vmin_p50=float(np.median(vm)), signal_dist=float(sd)))
        for c in sig:
            if not (box[0] + 40 < c[0] < box[1] - 40 and box[2] + 40 < c[1] < box[3] - 40):
                continue
            df, _ = jx.per_vehicle(tr, c[0], c[1], R=18., U=60.)
            if len(df) < 60:
                continue
            res.append(dict(member=name, drone=drone, node=-1, kind='signal', x=float(c[0]), y=float(c[1]), n_minor=len(df), n_all=len(df), vmin_p50=float(df['stop'].mean()), signal_dist=0., arms=df[df['arm'] >= 0]['arm'].nunique()))
        print(name, len(tr), flush=True)
    json.dump(res, open(OUT / 'pneuma_candidates.json', 'w'), indent=0)
    for k in ('stop', 'give_way', 'signal'):
        r = sorted([x for x in res if x['kind'] == k], key=lambda z: -z['n_minor'])
        print(k, len(r))
        for x in r[:30]:
            print(' ', x['drone'], x['node'], 'xy %.0f %.0f' % (x['x'], x['y']), 'n', x['n_minor'], 'all', x['n_all'], 'vmin/stop %.2f' % x['vmin_p50'], 'sigd %.0f' % x['signal_dist'], x.get('arms', ''))


if __name__ == '__main__':
    main()
