#!/usr/bin/env python3
"""Recipe step 0. May 2019 site table, sensors matched to edges and lanes, then the district scan.

Writes step0/sites.csv, step0/site_lanes.csv, step0/district_scan.csv, step0/district.json.
A window is scored from real data and the map only, never from simulated flows.
"""
import json
import pickle
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from pyproj import Transformer
from scipy.spatial import cKDTree

OUT = B19 / 'step0'
MAX_DIST, MAX_ANGLE = 30.0, 50.0


def lane_rank(spur):
    """Position from the right among main-carriageway lanes; None when the code says nothing."""
    s = spur or ''
    if s.endswith('_R') and s.startswith('HF'):
        return 0
    m = re.match(r'HF_(\d)vR', s)
    if m:
        return int(m[1]) - 1
    if s.endswith('_L') and s.startswith('HF'):
        return 'L'
    return None


def main():
    slim = OUT / 'net_berlin.pkl'
    if slim.exists():
        net = pickle.loads(slim.read_bytes())
    else:
        full = read_net(RAW / 'sumo.net.xml', OUT / 'net.pkl')
        off0 = np.array(list(map(float, full['location']['netOffset'].split(','))))
        t0 = Transformer.from_crs('EPSG:4326', full['location']['projParameter'], always_xy=True)
        xa, ya = np.array(t0.transform(13.05, 52.33)) + off0
        xb, yb = np.array(t0.transform(13.80, 52.68)) + off0
        keep = {k: e for k, e in full['edges'].items() if xa <= e['lanes'][0]['shape'][0][0] <= xb and ya <= e['lanes'][0]['shape'][0][1] <= yb}
        net = dict(location=full['location'], edges=keep, junctions={k: v for k, v in full['junctions'].items() if xa <= v[1] <= xb and ya <= v[2] <= yb}, tls=full['tls'])
        # free-flow time per edge, everywhere, for the demand cut
        (OUT / 'free_time.pkl').write_bytes(pickle.dumps({k: e['lanes'][0]['length'] / max(e['lanes'][0]['speed'], 1) for k, e in full['edges'].items()}, protocol=4))
        del full
        slim.write_bytes(pickle.dumps(net, protocol=4))
    st = stammdaten()
    mq = pd.read_csv(MQ, sep=';')
    active_sites = set(mq.mq_name)
    active_dets = set(pd.read_csv(DET, sep=';', dtype={'detid_15': str}, usecols=['detid_15']).detid_15)
    st['in_2019'] = st.det_id.astype(str).isin(active_dets) & st.site.isin(active_sites)
    print('metadata lanes', len(st), 'with 2019 data', int(st.in_2019.sum()), 'sites', st[st.in_2019].site.nunique(), 'of mq sites', len(active_sites))
    print('spur codes', st[st.in_2019].spur.value_counts().to_dict())
    tr = Transformer.from_crs('EPSG:4326', net['location']['projParameter'], always_xy=True)
    off = np.array(list(map(float, net['location']['netOffset'].split(','))))
    # segments of every car-usable edge, along lane 0 of the car lanes
    starts, ends, ids, along = [], [], [], []
    keys = []
    for k, e in net['edges'].items():
        cl = car_lanes(e)
        if not cl:
            continue
        s = cl[len(cl) // 2]['shape']
        run = 0.0
        i = len(keys)
        keys.append(k)
        for p, q in zip(s[:-1], s[1:]):
            n = max(1, int(np.ceil(np.linalg.norm(q - p) / 40)))
            for j in range(n):
                a, b = p + (q - p) * j / n, p + (q - p) * (j + 1) / n
                starts.append(a); ends.append(b); ids.append(i); along.append(run + np.linalg.norm(a - p))
            run += np.linalg.norm(q - p)
    starts, ends, ids, along = map(np.array, (starts, ends, ids, along))
    tree = cKDTree((starts + ends) / 2)
    rows, lane_rows = [], []
    for site, g in st[st.in_2019].groupby('site'):
        r = g.iloc[0]
        xy = np.array(tr.transform(r.lon, r.lat)) + off
        bearing = COMPASS.get(r.direction)
        cand = {}
        for j in tree.query_ball_point(xy, MAX_DIST + 30):
            v = ends[j] - starts[j]
            t = np.clip(np.dot(xy - starts[j], v) / max(np.dot(v, v), 1e-9), 0, 1)
            pt = starts[j] + v * t
            dist = float(np.linalg.norm(pt - xy))
            hd = float(np.degrees(np.arctan2(v[0], v[1])) % 360)
            ang = abs((hd - bearing + 180) % 360 - 180) if bearing is not None else 0.0
            k = keys[ids[j]]
            nl = len(car_lanes(net['edges'][k]))
            # two detectors on three car lanes is a coverage question, not evidence against the edge
            miss = max(0, len(g) - nl)
            score = dist + ang * .5 + miss * 15
            if k not in cand or score < cand[k][0]:
                cand[k] = (score, dist, ang, nl, float(along[j] + np.linalg.norm(pt - starts[j])))
        ranked = sorted(cand.items(), key=lambda x: x[1][0])
        if not ranked:
            rows.append(dict(site=site, lat=r.lat, lon=r.lon, quality='no_edge', street=r.street, position=r.position, direction=r.direction, n_det=len(g)))
            continue
        k, (score, dist, ang, nl, pos) = ranked[0]
        margin = ranked[1][1][0] - score if len(ranked) > 1 else 99.0
        e = net['edges'][k]
        street_ok = bool(e['name']) and any(w.lower() in e['name'].lower() or e['name'].lower() in w.lower() for w in re.split(r'[ ,/]+', str(r.street)) if len(w) > 3)
        ranks = [lane_rank(x) for x in g.spur]
        covers_all = len(g) >= nl
        quality = 'trusted'
        why = []
        if dist > MAX_DIST: why.append('far')
        # compass labels have eight sectors, so a curved street can read 50-75 degrees off and still be right
        if ang > MAX_ANGLE and not (ang <= 80 and street_ok and margin >= 20): why.append('direction')
        if margin < 8 and not street_ok: why.append('ambiguous')
        if nl - len(g) >= 1 and any(x is None for x in ranks): why.append('lanes_unknown')
        map_short = len(g) > nl  # more loops than lanes: the 2023 map lost lanes. A map issue for step 2, the site stays.
        if why:
            quality = 'weak:' + '+'.join(why)
        rows.append(dict(site=site, lat=r.lat, lon=r.lon, x=xy[0], y=xy[1], bearing=bearing, direction=r.direction, street=r.street, position=r.position, n_det=len(g), edge=k, edge_name=e['name'], edge_type=e['type'], speed_kmh=car_lanes(e)[0]['speed'] * 3.6, car_lanes=nl, dist_m=dist, angle=ang, margin=margin, street_ok=street_ok, pos_m=pos, edge_len=car_lanes(e)[0]['length'], covers_all=covers_all, quality=quality, map_short=map_short, spur=','.join(g.spur)))
        for _, d in g.iterrows():
            rk = lane_rank(d.spur)
            cl = sorted(x['index'] for x in car_lanes(e))
            if rk == 'L':
                rk = len(cl) - 1
            lane = cl[rk] if isinstance(rk, int) and rk < len(cl) else None
            lane_rows.append(dict(site=site, det_id=d.det_id, spur=d.spur, edge=k, lane_index=lane))
    s = pd.DataFrame(rows)
    s['road_class'] = s.edge_type.fillna('').str.replace('highway.', '', regex=False)
    OUT.mkdir(exist_ok=True)
    s.to_csv(OUT / 'sites.csv', index=False, float_format='%.6f')
    pd.DataFrame(lane_rows).to_csv(OUT / 'site_lanes.csv', index=False)
    print(s.quality.value_counts().to_string())
    print(s[s.quality == 'trusted'].road_class.value_counts().to_string())
    print('edges with two trusted sites', int(s[s.quality == 'trusted'].edge.duplicated().sum()))

    # district scan: 6 x 6 km windows on a 1 km grid, 36 km2
    match = json.load(open(DATA / 'datasets/berlin-2019-detectors/holdout_match.json'))
    far = {r[0] for r in match if r[3] is None or r[3] > 200}
    far100 = {r[0] for r in match if r[3] is None or r[3] > 100}
    t = s[s.quality == 'trusted'].copy()
    signals = np.array([(v[1], v[2]) for v in net['junctions'].values() if v[0] == 'traffic_light'])
    rows = []
    for size in (5000, 6000, 7000):
        for x0 in np.arange(t.x.min() - size, t.x.max(), 1000.0):
            for y0 in np.arange(t.y.min() - size, t.y.max(), 1000.0):
                q = t[(t.x >= x0) & (t.x < x0 + size) & (t.y >= y0) & (t.y < y0 + size)]
                if len(q) < 8:
                    continue
                classes = q.road_class.value_counts().to_dict()
                sg = int(((signals[:, 0] >= x0) & (signals[:, 0] < x0 + size) & (signals[:, 1] >= y0) & (signals[:, 1] < y0 + size)).sum())
                rows.append(dict(size=size, x0=x0, y0=y0, km2=size * size / 1e6, sites=len(q), clean200=int(q.site.isin(far).sum()), clean100=int(q.site.isin(far100).sum()), motorway=int(q.road_class.str.startswith('motorway').sum()), classes=len(classes), signals=sg))
    scan = pd.DataFrame(rows).sort_values(['sites', 'clean200', 'motorway'], ascending=False)
    scan.to_csv(OUT / 'district_scan.csv', index=False)
    print(scan.groupby('size').head(4).to_string())
    print('sites with more loops than map lanes', int(t.map_short.sum()), sorted(t[t.map_short].street.unique()))
    best = scan[scan['size'] == 7000].iloc[0]
    box = [float(best.x0), float(best.y0), float(best.x0 + 7000), float(best.y0 + 7000)]
    json.dump(dict(box=box, km2=49.0, sites=int(best.sites), clean_200m=int(best.clean200), signals_on_map=int(best.signals), rule='Most trusted sites among 25, 36 and 49 km2 windows on a 1 km grid; ties by sites over 200 m from a v6.4 calibration station. No Berlin window has real signal plans, so signals do not separate windows.', crs='net coordinates of v6.4 sumo.net.xml, UTM 32 minus netOffset'), open(OUT / 'district.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
