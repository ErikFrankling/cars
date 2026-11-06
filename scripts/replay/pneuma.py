"""pNEUMA (Athens, 4 weekday mornings, 10 drones): streaming reader, inventory, lanes from trajectory density,
signal reading, T3 replay scene. research/truth/replay/PNEUMA.md says what each step found.

The zip (15 GB, 98 GB unpacked) is never unpacked: each per-drone file is streamed row by row from the zip, resampled
to 5 Hz on a common 0.2 s grid and written to cars-data/replay/pneuma/raw/<day>_d<k>_<hhmm>.npz in metres (UTM 34N
minus a fixed origin). The dX files (all drones merged) are not read: the per-drone files hold the same tracks.

    python3 -I scripts/replay/pneuma.py convert [GLOB]     # long: run as agent-job
    python3 -I scripts/replay/pneuma.py inventory           # -> research/truth/replay/pneuma_inventory.json
"""
import os, sys, io, re, json, zipfile, glob, fnmatch
import numpy as np

ZIP = '/home/erikf/projects/personal/cars-data/datasets/pneuma-full/pNEUMA_dataset.zip'
OUTD = '/home/erikf/projects/personal/cars-data/replay/pneuma'
RAW = os.path.join(OUTD, 'raw')
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
TYPES = ['Car', 'Taxi', 'Bus', 'Medium Vehicle', 'Heavy Vehicle', 'Motorcycle', 'Other']
DIMS = {0: (5.0, 2.0), 1: (5.0, 2.0), 2: (12.5, 4.0), 3: (5.83, 2.67), 4: (12.5, 3.33), 5: (2.5, 1.0), 6: (5.0, 2.0)}
ORIGIN = (738000.0, 4206000.0)          # UTM 34N easting, northing subtracted (Athens centre is near 739.5k, 4207k)
DT = 0.2
NAME = re.compile(r'(\d{8})_d(\d+)_(\d{4})_(\d{4})\.csv$')


def proj():
    import pyproj
    return pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:32634', always_xy=True)


def to_xy(tr, lat, lon):
    x, y = tr.transform(lon, lat)
    return np.asarray(x) - ORIGIN[0], np.asarray(y) - ORIGIN[1]


def convert_one(z, name, tr):
    m = NAME.search(name)
    day, drone, hhmm = m[1], int(m[2]), m[3]
    t_start = int(hhmm[:2]) * 3600 + int(hhmm[2:]) * 60
    out = os.path.join(RAW, f'{day}_d{drone}_{hhmm}.npz')
    if os.path.exists(out):
        return
    ids, typ, off, dist = [], [], [0], []
    T, LA, LO, V, AX, AY = [], [], [], [], [], []
    with z.open(name) as fb:
        f = io.TextIOWrapper(fb, encoding='utf-8', errors='replace')
        f.readline()
        for line in f:
            p = line.split(';', 4)
            if len(p) < 5:
                continue
            try:
                a = np.array([s for s in p[4].replace('\n', '').split(';') if s.strip()], dtype=float)
                int(p[0]); float(p[2])
            except ValueError:
                print('bad row', p[0][:20], p[1][:20], name, flush=True)
                continue
            a = a[:len(a) // 6 * 6].reshape(-1, 6)
            if len(a) < 2:
                continue
            t = a[:, 5]
            g = np.arange(np.ceil(t[0] / DT - 1e-6), np.floor(t[-1] / DT + 1e-6) + 1) * DT
            if len(g) < 1:
                continue
            ids.append(int(p[0])); ty = p[1].strip(); typ.append(TYPES.index(ty) if ty in TYPES else 6)
            if ty not in TYPES:
                print('unknown type', repr(ty), name, flush=True); dist.append(float(p[2]))
            T.append(g.astype(np.float32))
            for dst, c in ((LA, 0), (LO, 1), (V, 2), (AX, 3), (AY, 4)):
                dst.append(np.interp(g, t, a[:, c]))
            off.append(off[-1] + len(g))
    la = np.concatenate(LA); lo = np.concatenate(LO)
    x, y = to_xy(tr, la, lo)
    np.savez(out + '.tmp.npz', id=np.array(ids, np.int32), type=np.array(typ, np.uint8), off=np.array(off, np.int64),
             dist=np.array(dist, np.float32), t0=np.float64(t_start), t=np.concatenate(T), x=x.astype(np.float32), y=y.astype(np.float32),
             v=(np.concatenate(V) / 3.6).astype(np.float32), ax=np.concatenate(AX).astype(np.float32), ay=np.concatenate(AY).astype(np.float32))
    os.replace(out + '.tmp.npz', out)
    print(name, len(ids), off[-1], flush=True)


def convert(pat='*'):
    os.makedirs(RAW, exist_ok=True)
    tr = proj()
    z = zipfile.ZipFile(ZIP)
    names = [i.filename for i in z.infolist() if NAME.search(i.filename) and fnmatch.fnmatch(os.path.basename(i.filename), pat)]
    for n in sorted(names, key=lambda s: (NAME.search(s)[2].zfill(2), s)):
        convert_one(z, n, tr)


def load(day, drone, hhmm):
    d = np.load(os.path.join(RAW, f'{day}_d{drone}_{hhmm}.npz'))
    return {k: d[k] for k in d.files}


def files():
    out = []
    for p in sorted(glob.glob(os.path.join(RAW, '*.npz'))):
        m = re.search(r'(\d{8})_d(\d+)_(\d{4})\.npz$', p)
        if m:
            out.append((m[1], int(m[2]), m[3], p))
    return out


def samples(day, drone, hhmm, every=1):
    """Flat sample arrays of one file with vehicle index, class and heading (from neighbouring samples)."""
    d = load(day, drone, hhmm)
    n = np.diff(d['off']); vi = np.repeat(np.arange(len(n)), n)
    x, y = d['x'].astype(float), d['y'].astype(float)
    same_next = np.r_[vi[1:] == vi[:-1], False]; same_prev = np.r_[False, vi[1:] == vi[:-1]]
    i1 = np.where(same_next, np.arange(len(x)) + 1, np.arange(len(x))); i0 = np.where(same_prev, np.arange(len(x)) - 1, np.arange(len(x)))
    hx, hy = x[i1] - x[i0], y[i1] - y[i0]
    out = dict(x=x, y=y, v=d['v'].astype(float), t=d['t'].astype(float) + float(d['t0']), veh=vi, vid=d['id'][vi], type=d['type'][vi],
               hx=hx, hy=hy, ay=d['ay'].astype(float))
    if every > 1:
        out = {k: v[::every] for k, v in out.items()}
    return out


# ---------------------------------------------------------------- the net: OSM topology, lanes from trajectory density

OSM_NET = os.path.join(OUTD, 'osm_net.xml')
NETCONVERT_OSM = ['--proj', '+proj=utm +zone=34 +ellps=WGS84 +datum=WGS84 +units=m +no_defs', '--offset.disable-normalization',
                  '--offset.x', str(-ORIGIN[0]), '--offset.y', str(-ORIGIN[1]), '--junctions.join', '--tls.guess-signals', '--tls.join',
                  '--no-turnarounds', '--remove-edges.isolated', '--keep-edges.by-vclass', 'passenger', '--osm.sidewalks', 'false', '--output.street-names', '--no-warnings']


def net_lanes(path=OSM_NET):
    import xml.etree.ElementTree as ET
    cache = path + '.lanes.pkl'
    if os.path.exists(cache) and os.path.getmtime(cache) > os.path.getmtime(path):
        import pickle
        return pickle.load(open(cache, 'rb'))
    E = {}
    for e in ET.parse(path).getroot().iter('edge'):
        if e.get('function') == 'internal':
            continue
        lanes = []
        for ln in e.iter('lane'):
            if 'passenger' in (ln.get('disallow') or '') or (ln.get('allow') and 'passenger' not in ln.get('allow')):
                continue
            pts = np.array([[float(a) for a in p.split(',')[:2]] for p in ln.get('shape').split()])
            lanes.append(dict(id=ln.get('id'), index=int(ln.get('index')), shape=pts, width=float(ln.get('width', 3.2)), length=float(ln.get('length')),
                              allow=ln.get('allow') or '', disallow=ln.get('disallow') or ''))
        if lanes:
            E[e.get('id')] = dict(lanes=lanes, type=e.get('type'), name=e.get('name'), frm=e.get('from'), to=e.get('to'))
    import pickle
    pickle.dump(E, open(cache, 'wb'))
    return E


def project(P, x, y):
    """Onto polyline P: arc length, signed lateral (left positive), segment index."""
    d = np.diff(P, axis=0); seg = np.hypot(d[:, 0], d[:, 1]); u = d / np.maximum(seg, 1e-9)[:, None]; cum = np.r_[0, np.cumsum(seg)]
    best = np.full(len(x), np.inf); s = np.zeros(len(x)); lat = np.zeros(len(x)); si = np.zeros(len(x), int)
    for i in range(len(seg)):
        dx = x - P[i, 0]; dy = y - P[i, 1]
        t = np.clip(dx * u[i, 0] + dy * u[i, 1], 0, seg[i])
        px = dx - t * u[i, 0]; py = dy - t * u[i, 1]; dist = np.hypot(px, py)
        m = dist < best
        best[m] = dist[m]; s[m] = cum[i] + t[m]; lat[m] = (u[i, 0] * py - u[i, 1] * px)[m]; si[m] = i
    return s, lat, si, u, cum[-1]


def peaks(lat, lo, hi, bw=0.2, sig=0.35, rel=0.15, sep=2.0):
    b = np.arange(lo, hi + bw, bw)
    h, _ = np.histogram(lat, b)
    k = np.arange(-4 * sig, 4 * sig + bw, bw); g = np.exp(-0.5 * (k / sig) ** 2); hs = np.convolve(h, g / g.sum(), 'same')
    c = 0.5 * (b[1:] + b[:-1])
    pk = [i for i in range(1, len(hs) - 1) if hs[i] >= hs[i - 1] and hs[i] > hs[i + 1] and hs[i] >= rel * hs.max()]
    pk = sorted(pk, key=lambda i: -hs[i]); keep = []
    for i in pk:
        if all(abs(c[i] - c[j]) >= sep for j in keep):
            keep.append(i)
    return sorted(float(c[i]) for i in keep)


def area_box(drone, pad=0.0):
    xs, ys = [], []
    for day, dr, hh, p in files():
        if dr == drone and hh in ('0900',):
            d = np.load(p); xs.append(np.percentile(d['x'], [0.5, 99.5])); ys.append(np.percentile(d['y'], [0.5, 99.5]))
    xs, ys = np.array(xs), np.array(ys)
    return float(xs[:, 0].min() - pad), float(ys[:, 0].min() - pad), float(xs[:, 1].max() + pad), float(ys[:, 1].max() + pad)


def lanes_area(drone, periods=('0900', '0930'), min_samples=400):
    """Per OSM edge in the drone's view: lanes found from where cars drive against the OSM lanes, map-matching
    residual per lane, motorcycle share per lane."""
    from scipy.spatial import cKDTree
    S = [samples(day, dr, hh) for day, dr, hh, p in files() if dr == drone and hh in periods]
    if not S:
        return None
    A = {k: np.concatenate([s[k] for s in S]) for k in ('x', 'y', 'v', 'type', 'hx', 'hy')}
    mv = (A['v'] > 1.0) & (np.hypot(A['hx'], A['hy']) > 0.05)
    A = {k: v[mv] for k, v in A.items()}
    moto = A['type'] == 5
    car = np.isin(A['type'], (0, 1))
    tree = cKDTree(np.c_[A['x'], A['y']])
    box = area_box(drone)
    E = net_lanes()
    res = {}
    used = np.zeros(len(A['x']), bool)
    for eid, e in E.items():
        L0 = e['lanes'][0]; P = L0['shape']
        if not ((P[:, 0] > box[0]) & (P[:, 0] < box[2]) & (P[:, 1] > box[1]) & (P[:, 1] < box[3])).mean() > 0.5:
            continue
        n_osm = len(e['lanes']); w = np.array([l['width'] for l in e['lanes']])
        osm_c = np.r_[0, np.cumsum(0.5 * (w[1:] + w[:-1]))]
        dd = np.diff(P, axis=0); seg = np.hypot(dd[:, 0], dd[:, 1]); cum = np.r_[0, np.cumsum(seg)]
        if cum[-1] < 25:
            continue
        q = np.array([np.interp(np.arange(0, cum[-1], 4.0), cum, P[:, j]) for j in (0, 1)]).T
        idx = sorted(set(i for l in tree.query_ball_point(q, r=osm_c[-1] + 9.0) for i in l))
        if len(idx) < min_samples:
            continue
        idx = np.array(idx)
        s, lat, si, u, Ltot = project(P, A['x'][idx], A['y'][idx])
        hn = np.hypot(A['hx'][idx], A['hy'][idx])
        cosang = (A['hx'][idx] * u[si, 0] + A['hy'][idx] * u[si, 1]) / hn
        k = (cosang > 0.87) & (s > 8) & (s < Ltot - 8) & (lat > -7) & (lat < osm_c[-1] + 7)
        idx, lat = idx[k], lat[k]
        c_ = car[idx]
        if c_.sum() < min_samples:
            continue
        pk = peaks(lat[c_], -7, osm_c[-1] + 7)
        if not pk:
            continue
        pk = np.array(pk)
        near = np.abs(lat[:, None] - pk[None, :]); j = np.argmin(near, 1); dn = near[np.arange(len(lat)), j]
        onl = dn < 0.8
        per_lane = []
        for m in range(len(pk)):
            cm = c_ & (j == m) & (dn < 1.6)
            per_lane.append(dict(lat=round(float(pk[m]), 2), cars=int(cm.sum()),
                                 residual_p50=round(float(np.median(dn[cm])), 2) if cm.any() else None,
                                 residual_p90=round(float(np.percentile(dn[cm], 90)), 2) if cm.any() else None,
                                 moto_share=round(float(moto[idx][(j == m) & onl].mean()), 3) if ((j == m) & onl).any() else None))
        osm_near = np.abs(lat[c_][:, None] - osm_c[None, :]).min(1)
        res[eid] = dict(name=e['name'], type=e['type'], length=round(float(Ltot), 1), osm_lanes=n_osm, density_lanes=int(len(pk)),
                        osm_lane_lat=[round(float(v), 2) for v in osm_c], density_lane_lat=[round(float(v), 2) for v in pk],
                        centre_offset=round(float(pk.mean() - osm_c.mean()), 2),
                        spacing=round(float(np.median(np.diff(pk))), 2) if len(pk) > 1 else None,
                        residual_density_p50=round(float(np.median(dn[c_])), 2), residual_osm_p50=round(float(np.median(osm_near)), 2),
                        moto_between_lanes=round(float((~onl[moto[idx]]).mean()), 3) if moto[idx].any() else None,
                        moto_share=round(float(moto[idx].mean()), 3), lanes=per_lane, samples=int(len(idx)))
        used[idx] = True
    return dict(box=box, edges=res, samples=int(len(A['x'])), matched_to_edges=round(float(used.mean()), 3))


def inventory():
    """Days, drones, periods, vehicles by class and motorcycle shares (by vehicle and by vehicle-time)."""
    rows = []
    for day, dr, hh, p in files():
        d = np.load(p)
        n = np.diff(d['off']); ty = d['type']
        rows.append(dict(day=day, drone=dr, period=hh, vehicles=int(len(ty)), samples=int(n.sum()),
                         **{TYPES[k]: int((ty == k).sum()) for k in range(len(TYPES))},
                         moto_share_veh=float((ty == 5).mean()), moto_share_time=float(n[ty == 5].sum() / max(n.sum(), 1)),
                         x0=float(np.percentile(d['x'], 1)), x1=float(np.percentile(d['x'], 99)), y0=float(np.percentile(d['y'], 1)), y1=float(np.percentile(d['y'], 99))))
    import pandas as pd
    R = pd.DataFrame(rows)
    out = dict(days=sorted(R.day.unique().tolist()), drones=sorted(int(v) for v in R.drone.unique()), files=int(len(R)),
               files_per_day={dd: int(k) for dd, k in R.groupby('day').size().items()},
               missing=[f'{dd} d{k}' for dd in R.day.unique() for k in R.drone.unique() if len(R[(R.day == dd) & (R.drone == k)]) < 5],
               vehicles_total=int(R.vehicles.sum()), by_class={t: int(R[t].sum()) for t in TYPES},
               by_drone={int(k): dict(vehicles_per_file=int(g.vehicles.median()), moto_share_veh=round(float(g.moto_share_veh.mean()), 3),
                                      moto_share_time=round(float(g.moto_share_time.mean()), 3),
                                      box=[round(float(g.x0.min())), round(float(g.y0.min())), round(float(g.x1.max())), round(float(g.y1.max()))])
                         for k, g in R.groupby('drone')},
               by_period={hh: round(float(g.moto_share_veh.mean()), 3) for hh, g in R.groupby('period')})
    R.to_csv(os.path.join(OUTD, 'inventory.csv'), index=False)
    return out


def lanes_summary():
    """Per drone area: OSM lane-count agreement, offsets, residuals, motorcycle share per lane (from lanes/d*.json)."""
    out, allv = {}, []
    for p in sorted(glob.glob(os.path.join(OUTD, 'lanes', 'd*.json')), key=lambda s: int(re.search(r'd(\d+)', s)[1])):
        dr = int(re.search(r'd(\d+)\.json', p)[1]); r = json.load(open(p)); E = list(r['edges'].values())
        allv += E
        w = np.array([e['samples'] for e in E], float)
        lanes = [l for e in E for l in e['lanes'] if l['moto_share'] is not None]
        by_pos = {}
        for e in E:
            n = len(e['lanes'])
            for i, l in enumerate(e['lanes']):
                if l['moto_share'] is None or n < 2:
                    continue
                k = 'kerb' if i == 0 else 'median side' if i == n - 1 else 'middle'
                by_pos.setdefault(k, []).append(l['moto_share'])
        out[dr] = dict(edges=len(E), agree=int(sum(e['osm_lanes'] == e['density_lanes'] for e in E)),
                       density_more=int(sum(e['density_lanes'] > e['osm_lanes'] for e in E)), density_fewer=int(sum(e['density_lanes'] < e['osm_lanes'] for e in E)),
                       lanes_density=int(sum(e['density_lanes'] for e in E)), lanes_osm=int(sum(e['osm_lanes'] for e in E)),
                       centre_offset_abs_m_weighted=round(float(np.average([abs(e['centre_offset']) for e in E], weights=w)), 2),
                       residual_density_p50_weighted=round(float(np.average([e['residual_density_p50'] for e in E], weights=w)), 2),
                       residual_osm_p50_weighted=round(float(np.average([e['residual_osm_p50'] for e in E], weights=w)), 2),
                       lane_spacing_median_m=round(float(np.median([e['spacing'] for e in E if e['spacing']])), 2) if any(e['spacing'] for e in E) else None,
                       moto_share_samples_weighted=round(float(np.average([e['moto_share'] for e in E], weights=w)), 3),
                       moto_between_lanes_weighted=round(float(np.average([e['moto_between_lanes'] or 0 for e in E], weights=w)), 3),
                       moto_share_by_lane_position={k: round(float(np.median(v)), 3) for k, v in by_pos.items()},
                       moving_samples_on_edges=r['matched_to_edges'], box=[round(v) for v in r['box']],
                       streets=sorted({e['name'] for e in E if e['name']}))
    tot_e = sum(v['edges'] for v in out.values()); tot_a = sum(v['agree'] for v in out.values())
    allres = [e['residual_density_p50'] for e in allv]
    return dict(areas=out, all=dict(edges=tot_e, agree=tot_a, agree_pct=round(100 * tot_a / max(tot_e, 1), 1),
                                    density_more=sum(v['density_more'] for v in out.values()), density_fewer=sum(v['density_fewer'] for v in out.values()),
                                    residual_density_p50_median_of_edges=round(float(np.median(allres)), 2),
                                    residual_osm_p50_median_of_edges=round(float(np.median([e['residual_osm_p50'] for e in allv])), 2),
                                    moto_between_lanes_median_of_edges=round(float(np.median([e['moto_between_lanes'] for e in allv if e['moto_between_lanes'] is not None])), 3)))



# ---------------------------------------------------------------- signals read from crossings, residual queues

D_START = 1.9      # s: onset bias, mean of DLR UT (1.83) and SinD (2.0), research/truth/replay/signals.json
D_END_ARC = -0.95  # s: fixed-time end bias, mean of SinD Tianjin (+0.26) and Chongqing (-2.17); their spread is the band
YELLOW = 3.0


def net_junctions(path=OSM_NET):
    import xml.etree.ElementTree as ET
    return {j.get('id'): dict(type=j.get('type'), x=float(j.get('x')), y=float(j.get('y')))
            for j in ET.parse(path).getroot().iter('junction') if j.get('type') != 'internal'}


def approaches(drone, E=None, J=None):
    """Incoming edges of signalised junctions whose end is in the drone's view."""
    E = E or net_lanes(); J = J or net_junctions()
    box = area_box(drone)
    out = []
    for eid, e in E.items():
        j = J.get(e['to'])
        if not j or j['type'] not in ('traffic_light', 'traffic_light_right_on_red', 'traffic_light_unregulated'):
            continue
        P = e['lanes'][0]['shape']
        if not (box[0] + 15 < P[-1, 0] < box[2] - 15 and box[1] + 15 < P[-1, 1] < box[3] - 15):
            continue
        out.append(eid)
    return out


def approach_tracks(A, tree, e, back=90.0, ahead=15.0):
    """Per vehicle: front position along the edge's lane 0 relative to its end, lateral, speed, class."""
    import signals as SG
    P = e['lanes'][0]['shape']; w = np.array([l['width'] for l in e['lanes']]); width = w.sum()
    d = np.diff(P, axis=0); seg = np.hypot(d[:, 0], d[:, 1]); cum = np.r_[0, np.cumsum(seg)]
    if cum[-1] < 30:
        return None
    # extend the end straight on by `ahead` so crossings past the line are seen
    u_end = d[-1] / seg[-1]
    P2 = np.vstack([P, P[-1] + u_end * ahead])
    s0 = max(cum[-1] - back, 0)
    q = np.array([np.interp(np.arange(s0, cum[-1] + ahead, 4.0), np.r_[cum, cum[-1] + ahead], P2[:, j]) for j in (0, 1)]).T
    idx = np.array(sorted(set(i for l in tree.query_ball_point(q, r=width + 6.0) for i in l)))
    if len(idx) < 200:
        return None
    s, lat, si, uu, Lt = project(P2, A['x'][idx], A['y'][idx])
    hn = np.maximum(np.hypot(A['hx'][idx], A['hy'][idx]), 1e-6)
    cosang = (A['hx'][idx] * uu[si, 0] + A['hy'][idx] * uu[si, 1]) / hn
    k = ((cosang > 0.8) | (A['v'][idx] < 0.5)) & (lat > -2.0) & (lat < width + 1.0) & (s > s0)
    idx, s, lat = idx[k], s[k], lat[k]
    L = np.array([DIMS[int(t)][0] for t in range(7)])[A['type'][idx]]
    sf = s - cum[-1] + L / 2
    veh = []
    o = np.lexsort((A['t'][idx], A['vid'][idx]))
    idx, sf, lat = idx[o], sf[o], lat[o]
    cut = np.flatnonzero(np.diff(A['vid'][idx])) + 1
    for a, b in zip(np.r_[0, cut], np.r_[cut, len(idx)]):
        if b - a < 5:
            continue
        ty = int(A['type'][idx[a]])
        veh.append(dict(t=A['t'][idx[a:b]], s=sf[a:b], v=A['v'][idx[a:b]], lat=lat[a:b], kind='two' if ty == 5 else 'car', id=int(A['vid'][idx[a]]), type=ty))
    return veh


def residual_cycles(S, greens):
    """Per read cycle: cars standing before the line at its onset, and a residual queue (a car standing before the
    line from 5 s before the end of green until 2 s after the yellow)."""
    before = (S.kind == 'car') & (S.s < 0) & ~(S.tcross < S.t0)
    out = []
    for g0, g1, *_ in greens:
        q = int((before & (S.t0 <= g0) & (S.t1 >= g0 - 0.5)).sum())
        r = int((before & (S.t0 <= g1 - 5.0) & (S.t1 >= g1 + YELLOW + 2.0)).sum())
        out.append((g0, g1, q, r))
    return out


def signals_file(day, drone, hhmm, E, J, apps):
    import signals as SG
    from scipy.spatial import cKDTree
    A = samples(day, drone, hhmm)
    tree = cKDTree(np.c_[A['x'], A['y']])
    rows, cyc = [], []
    t0, t1 = float(A['t'].min()), float(A['t'].max())
    for eid in apps:
        e = E[eid]
        veh = approach_tracks(A, tree, e)
        if not veh or sum(v['kind'] == 'car' for v in veh) < 30:
            continue
        C, S = SG.events(veh)
        shift, nh = SG.stop_line(S)
        if nh < 5:
            continue
        for v in veh:
            v['s'] = v['s'] + shift
        C, S = SG.events(veh)
        fx = SG.fit_fixed(C, S, D_START, dict(arc=D_END_ARC, p80=0.0), t0 + 60, t1 - 60)
        if not fx:
            continue
        greens = [g for g in fx['greens']['arc'] if t0 + 30 < g[0] < t1 - 120]
        rc = residual_cycles(S, greens)
        nq = sum(1 for c in rc if c[2] > 0)
        rows.append(dict(day=day, drone=drone, period=hhmm, edge=eid, junction=e['to'], name=e['name'], lanes=len(e['lanes']),
                         line_shift_m=round(shift, 1), heads=nh, cars=int(sum(v['kind'] == 'car' for v in veh)), moto=int(sum(v['kind'] == 'two' for v in veh)),
                         cycle=round(fx['cycle'], 2), R=round(fx['R'], 3), green=round(fx['green']['arc'], 1), offset=round(fx['offset'], 2),
                         cycles=len(rc), cycles_with_queue=nq, residual_cycles=sum(1 for c in rc if c[3] > 0),
                         queue_mean=round(float(np.mean([c[2] for c in rc])), 2) if rc else 0, queue_max=max([c[2] for c in rc], default=0),
                         residual_max=max([c[3] for c in rc], default=0)))
        cyc += [dict(day=day, drone=drone, period=hhmm, edge=eid, g0=round(c[0], 1), g1=round(c[1], 1), queue=c[2], residual=c[3]) for c in rc]
    return rows, cyc


def signals_all(drones):
    import pandas as pd
    E = net_lanes(); J = net_junctions()
    rows, cyc = [], []
    for dr in drones:
        apps = approaches(dr, E, J)
        for day, d_, hh, p in files():
            if d_ != dr:
                continue
            r, c = signals_file(day, dr, hh, E, J, apps)
            rows += r; cyc += c
            print(day, dr, hh, 'approaches read', len(r), flush=True)
        pd.DataFrame(rows).to_csv(os.path.join(OUTD, 'signals_approaches.csv'), index=False)
        pd.DataFrame(cyc).to_csv(os.path.join(OUTD, 'signals_cycles.csv'), index=False)


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'convert':
        convert(sys.argv[2] if len(sys.argv) > 2 else '*')
    elif c == 'osmnet':
        import subprocess
        subprocess.run(['netconvert', '--osm-files', os.path.join(OUTD, 'osm.osm'), '-o', OSM_NET] + NETCONVERT_OSM, check=True)
    elif c == 'inventory':
        r = inventory()
        json.dump(r, open(os.path.join(REPO, 'research/truth/replay/pneuma_inventory.json'), 'w'), indent=1)
        print(json.dumps(r, indent=1))
    elif c == 'lanes':
        out = {}
        for dr in [int(a) for a in sys.argv[2].split(',')]:
            r = lanes_area(dr)
            if r:
                out[dr] = r
                ed = r['edges']
                print(dr, 'edges', len(ed), 'agree', sum(1 for v in ed.values() if v['osm_lanes'] == v['density_lanes']), 'matched', r['matched_to_edges'], flush=True)
        os.makedirs(os.path.join(OUTD, 'lanes'), exist_ok=True)
        for dr, r in out.items():
            json.dump(r, open(os.path.join(OUTD, 'lanes', f'd{dr}.json'), 'w'), indent=1)

    elif c == 'lanes_summary':
        r = lanes_summary()
        json.dump(r, open(os.path.join(REPO, 'research/truth/replay/pneuma_lanes.json'), 'w'), indent=1)
        print(json.dumps(r['all'], indent=1))
        for k, v in r['areas'].items():
            print(k, {kk: vv for kk, vv in v.items() if kk not in ('box', 'streets')}, v['streets'][:6])
    elif c == 'signals':
        sys.path.insert(0, HERE)
        signals_all([int(a) for a in sys.argv[2].split(',')])
