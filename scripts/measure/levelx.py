"""levelX loader: highD, inD, rounD, exiD straight from the provider's zip, one recording at a time.

Data are non-commercial and must not be redistributed: nothing read here is written into the repo.
Columns are cached per recording as .npz under cars-data/measure/levelx/<ds>/ so each part reads them fast.

    python3 -I scripts/measure/levelx.py cache highD [inD rounD exiD]   # fill the cache, held-out recordings too
    python3 -I scripts/measure/levelx.py info highD                      # recordings, days, sites

Common columns, all datasets: frame, id, xc, yc (box centre, m), vx, vy, ax, ay, length, width, heading (deg).
highD is in image orientation (y down); its boxes are axis-aligned, `heading` is 0 or 180 from drivingDirection.
"""
import io, os, sys, json, zipfile
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from holdout import held

DATA = '/home/erikf/projects/personal/cars-data'
ZIP = DATA + '/datasets/levelx/{ds}/{ds}.zip'
CACHE = DATA + '/measure/levelx/{ds}'
DAYS = {'mon': 'Mon', 'tue': 'Tue', 'wed': 'Wed', 'thu': 'Thu', 'fri': 'Fri', 'sat': 'Sat', 'sun': 'Sun'}

_zips = {}


def zf(ds):
    if ds not in _zips:
        _zips[ds] = zipfile.ZipFile(ZIP.format(ds=ds))
    return _zips[ds]


def _member(ds, rec, what):
    return f'data/{rec:02d}_{what}.csv'


def recordings(ds, holdout=False):
    """Recording meta as a DataFrame with normalised columns rec, site, day, start, duration, fps, limit."""
    z = zf(ds)
    rows = []
    for n in sorted(x for x in z.namelist() if x.endswith('_recordingMeta.csv')):
        m = pd.read_csv(io.BytesIO(z.read(n))).iloc[0].to_dict()
        rec = int(m.get('id', m.get('recordingId')))
        day = str(m.get('weekDay', m.get('weekday', ''))).strip().lower()[:3]
        lim = float(m.get('speedLimit', -1))
        rows.append(dict(rec=rec, site=int(m['locationId']), day=DAYS.get(day, day), month=m.get('month', ''),
                         start=str(m.get('startTime', '')), duration=float(m['duration']), fps=float(m['frameRate']),
                         limit=lim if lim > 0 else None, held=held(ds, rec), raw=m))
    r = pd.DataFrame(rows)
    return r if holdout else r[~r.held].reset_index(drop=True)


def tracks_meta(ds, rec):
    return pd.read_csv(io.BytesIO(zf(ds).read(_member(ds, rec, 'tracksMeta'))))


HIGHD = dict(frame='i4', id='i4', x='f4', y='f4', width='f4', height='f4', xVelocity='f4', yVelocity='f4',
             xAcceleration='f4', yAcceleration='f4', dhw='f4', thw='f4', precedingId='i4', followingId='i4',
             leftPrecedingId='i4', leftAlongsideId='i4', leftFollowingId='i4', rightPrecedingId='i4',
             rightAlongsideId='i4', rightFollowingId='i4', laneId='i1')
DRONE = dict(frame='i4', trackId='i4', xCenter='f4', yCenter='f4', heading='f4', width='f4', length='f4',
             xVelocity='f4', yVelocity='f4', xAcceleration='f4', yAcceleration='f4', lonVelocity='f4',
             latVelocity='f4', lonAcceleration='f4', latAcceleration='f4')
EXID = dict(DRONE, **{k: 'str' for k in (
    'laneletId laneChange latLaneCenterOffset laneWidth lonLaneletPos laneletLength leadDHW leadId rearId leftLeadId '
    'leftRearId leftAlongsideId rightLeadId rightRearId rightAlongsideId traveledDistance').split()})
RENAME = dict(trackId='id', xCenter='xc', yCenter='yc', xVelocity='vx', yVelocity='vy', xAcceleration='ax',
              yAcceleration='ay', precedingId='prec', followingId='foll', laneId='lane')


def _first(s):
    """exiD packs several lanelets in one cell ('1503;1504') where a vehicle straddles two; keep the first."""
    return pd.to_numeric(s.astype(str).str.split(';').str[0], errors='coerce').astype('f4')


def _read_csv(ds, rec):
    cols = HIGHD if ds == 'highD' else EXID if ds == 'exiD' else DRONE
    with zf(ds).open(_member(ds, rec, 'tracks')) as f:
        d = pd.read_csv(f, usecols=list(cols), dtype={k: (object if v == 'str' else v) for k, v in cols.items()})
    for k, v in cols.items():
        if v == 'str':
            d[k] = _first(d[k])
    if ds == 'highD':
        tm = tracks_meta(ds, rec).set_index('id')
        d['xc'] = d.x + d.width / 2
        d['yc'] = d.y + d.height / 2
        d = d.rename(columns={'width': 'length', 'height': 'width'})
        dirn = tm.drivingDirection.reindex(d.id).values
        d['heading'] = np.where(dirn == 1, 180.0, 0.0).astype('f4')
        d['dir'] = dirn.astype('i1')
        d = d.drop(columns=['x', 'y'])
    d = d.rename(columns=RENAME)
    return d.sort_values(['id', 'frame'], kind='stable').reset_index(drop=True)


def tracks(ds, rec):
    """All samples of one recording, sorted by id then frame. Cached."""
    path = os.path.join(CACHE.format(ds=ds), f'{rec:02d}.npz')
    if os.path.exists(path):
        z = np.load(path)
        return pd.DataFrame({k: z[k] for k in z.files})
    d = _read_csv(ds, rec)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.savez(path + '.tmp.npz', **{c: d[c].to_numpy() for c in d.columns})
    os.replace(path + '.tmp.npz', path)
    return d


def by_track(d):
    """Start and end row of each track in a frame sorted by id then frame."""
    ids = d.id.to_numpy()
    cut = np.flatnonzero(np.diff(ids)) + 1
    starts = np.r_[0, cut]; ends = np.r_[cut, len(ids)]
    return ids[starts], starts, ends


def lanelets(ds, site, construction=False):
    """Lanelet2 map of a site in the recording's local frame: {lanelet id: dict(left, right, centre, tags)}."""
    import xml.etree.ElementTree as ET
    from pyproj import Transformer
    z = zf(ds)
    key = f'{site:02d}_' if ds == 'inD' else f'{site}_'
    names = [n for n in z.namelist() if n.endswith('.osm') and n.split('/')[-2].startswith(key)]
    names = [n for n in names if ('constuction' in n) == construction] or names
    root = ET.fromstring(z.read(names[0]))
    meta = recordings(ds, holdout=True)
    m = meta[meta.site == site].iloc[0].raw
    tr = Transformer.from_crs('EPSG:4326', 'EPSG:32632', always_xy=True)
    nid, lon, lat = [], [], []
    for n in root.iter('node'):
        nid.append(int(n.get('id'))); lon.append(float(n.get('lon'))); lat.append(float(n.get('lat')))
    ux, uy = tr.transform(np.array(lon), np.array(lat))
    P = {i: (x - m['xUtmOrigin'], y - m['yUtmOrigin']) for i, x, y in zip(nid, ux, uy)}
    ways = {int(w.get('id')): [int(r.get('ref')) for r in w.iter('nd')] for w in root.iter('way')}
    out = {}
    for r in root.iter('relation'):
        tags = {t.get('k'): t.get('v') for t in r.iter('tag')}
        if tags.get('type') != 'lanelet':
            continue
        mem = {m_.get('role'): int(m_.get('ref')) for m_ in r.iter('member') if m_.get('type') == 'way'}
        if 'left' not in mem or 'right' not in mem:
            continue
        L = np.array([P[i] for i in ways[mem['left']]]); R = np.array([P[i] for i in ways[mem['right']]])
        # Lanelet2 boundaries run in the driving direction, but a shared way may be stored reversed.
        if np.hypot(*(L[0] - R[0])) > np.hypot(*(L[0] - R[-1])) and np.hypot(*(L[-1] - R[-1])) > np.hypot(*(L[-1] - R[0])):
            R = R[::-1]
        out[int(r.get('id'))] = dict(left=L, right=R, centre=_centre(L, R), tags=tags,
                                     left_nodes=ways[mem['left']], right_nodes=ways[mem['right']])
    return out


def _resample(p, n):
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(p, axis=0).T))]
    s = np.linspace(0, d[-1], n)
    return np.c_[np.interp(s, d, p[:, 0]), np.interp(s, d, p[:, 1])]


def _centre(L, R):
    n = max(len(L), len(R), 2) * 2
    return (_resample(L, n) + _resample(R, n)) / 2


def info(ds):
    r = recordings(ds, holdout=True)
    g = r.groupby(['site', 'day', 'held']).agg(recs=('rec', 'size'), hours=('duration', lambda s: round(s.sum() / 3600, 2)),
                                                first=('rec', 'min'), last=('rec', 'max'))
    print(ds); print(g.to_string())


if __name__ == '__main__':
    cmd = sys.argv[1]
    for ds in sys.argv[2:]:
        if cmd == 'info':
            info(ds)
        elif cmd == 'cache':
            for rec in recordings(ds).rec:
                d = tracks(ds, int(rec))
                print(ds, rec, len(d), flush=True)
