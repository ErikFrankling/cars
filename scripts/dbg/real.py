"""Real tracks from report 05's data, in one shape. A tracker's output is a measurement with error; flaws are listed in research/truth/05-real-human-driving.md."""
import os

import numpy as np

ROOT = os.environ.get('CARS_DATA', '/home/erikf/projects/personal/cars-data') + '/truth/trajectories/'
TGSIM = {'I395': 'I395', 'I90stat': 'I90stat', 'I90mov': 'I90mov', 'I294L1': 'I294L1', 'I294L2': 'I294L2', 'Foggy': 'Foggy'}


def real_sets():
    return list(TGSIM) + ['drat']


def _cache_path(name):
    d = os.path.join(os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache')), 'cars-dbg')
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'{name}.npz')


def _along(x, y, v):
    """Metres along a straight road: the main axis of the points, positive with the traffic."""
    good = np.isfinite(x) & np.isfinite(y)
    px, py = x[good][::37], y[good][::37]
    cov = np.cov(px - px.mean(), py - py.mean())
    w, e = np.linalg.eigh(cov)
    axis = e[:, np.argmax(w)]
    s = (x - px.mean()) * axis[0] + (y - py.mean()) * axis[1]
    return s


def _tgsim(name):
    import pandas as pd
    path = ROOT + 'opus-20261031-tgsim/' + TGSIM[name] + '.csv'
    head = pd.read_csv(path, nrows=2)
    cols = list(head.columns)
    run = next((c for c in cols if 'run' in c.lower()), None)
    want = ['id', 'time', 'xloc_kf', 'yloc_kf', 'lane_kf', 'speed_kf', 'acceleration_kf', 'length_smoothed'] + ([run] if run else [])
    types = {c: 'float32' for c in want}
    types['id'] = 'int64'
    types['time'] = 'float64'
    parts = []
    for chunk in pd.read_csv(path, usecols=want, dtype=types, chunksize=500000):
        parts.append(chunk)
    d = pd.concat(parts, ignore_index=True)
    track = d['id'].to_numpy(dtype=np.int64)
    t = d['time'].to_numpy(dtype=np.float64)
    if run:
        r = d[run].to_numpy().astype(np.int64)
        track = track + r * 10_000_000
        t = t + r * 100_000.0
    return dict(track=track, t=t, x=d['xloc_kf'].to_numpy(dtype=np.float32), y=d['yloc_kf'].to_numpy(dtype=np.float32), lane=d['lane_kf'].to_numpy(dtype=np.int32), v=d['speed_kf'].to_numpy(dtype=np.float32),
                a=d['acceleration_kf'].to_numpy(dtype=np.float32), length=d['length_smoothed'].to_numpy(dtype=np.float32), dt=0.1, s=_along(d['xloc_kf'].to_numpy(dtype=np.float64), d['yloc_kf'].to_numpy(dtype=np.float64), None).astype(np.float32))


def _drat():
    import pandas as pd
    path = ROOT + 'opus-20261031-drat/drone_GT.csv'
    d = pd.read_csv(path, usecols=['track_id', 'timestamp', 'utm_x', 'utm_y', 'speed_mps', 'accel_mps2', 'length_m'])
    x, y = d['utm_x'].to_numpy(), d['utm_y'].to_numpy()
    t = d['timestamp'].to_numpy()
    return dict(track=d['track_id'].to_numpy(dtype=np.int64), t=t - t.min(), x=x.astype(np.float32), y=y.astype(np.float32), lane=np.zeros(len(d), dtype=np.int32), v=d['speed_mps'].to_numpy(dtype=np.float32),
                a=d['accel_mps2'].to_numpy(dtype=np.float32), length=d['length_m'].to_numpy(dtype=np.float32), dt=float(np.median(np.diff(np.unique(t)[:500]))), s=_along(x, y, None).astype(np.float32))


def tracks(name):
    """All rows of a real dataset, cached after the first read."""
    path = _cache_path(name)
    if os.path.exists(path):
        z = np.load(path)
        return {k: (float(z[k]) if k == 'dt' else z[k]) for k in z.files}
    if name in TGSIM:
        d = _tgsim(name)
    elif name == 'drat':
        d = _drat()
    else:
        raise SystemExit(f'unknown real data {name}. Known: {", ".join(real_sets())}')
    np.savez(path, **d)
    return d


def _rebase(s):
    return s - np.nanpercentile(s, 0.1)


def load_real(spec, begin=None, span=None):
    """Tracks for a time-space diagram: `I395`, `I395:lane=-3`, or a CSV of time,track,pos,speed[,lane]."""
    name, _, opt = spec.partition(':')
    if name.endswith('.csv'):
        import pandas as pd
        d = pd.read_csv(name)
        t, track, s, v = d['time'].to_numpy(float), d['track'].to_numpy(), d['pos'].to_numpy(float), d['speed'].to_numpy(float)
        lanes = d['lane'].nunique() if 'lane' in d else 1
        dt = float(np.median(np.diff(np.unique(t)[:500])))
        return dict(name=os.path.basename(name), t=t, s=s, v=v, track=track, dt=dt, lanes=lanes)
    d = tracks(name)
    keep = np.isfinite(d['s']) & np.isfinite(d['v'])
    lane = None
    if opt.startswith('lane='):
        lane = int(opt[5:])
    elif name != 'drat':
        vals, counts = np.unique(d['lane'][keep], return_counts=True)
        lane = int(vals[np.argmax(counts)])
    if lane is not None:
        keep &= d['lane'] == lane
    t = d['t'][keep]
    a = float(t.min()) if begin is None else float(begin)
    if span is not None:
        inside = (t >= a) & (t <= a + span)
        idx = np.nonzero(keep)[0][inside]
    else:
        idx = np.nonzero(keep)[0]
    s = _rebase(d['s'][idx].astype(float))
    if len(s) > 2:
        # A road direction opposite to the axis reads as cars going backwards.
        order = np.lexsort((d['t'][idx], d['track'][idx]))
        ds = np.diff(s[order])
        same = np.diff(d['track'][idx][order]) == 0
        if len(ds[same]) and np.median(ds[same]) < 0:
            s = s.max() - s
    return dict(name=f"{name} lane {lane}" if lane is not None else name, t=d['t'][idx].astype(float), s=s, v=d['v'][idx].astype(float), track=d['track'][idx], dt=d['dt'], lanes=1)


def _per_second(d):
    """Keep one sample a second per track, so a real acceleration reads as one simulated at dt 1."""
    steps = np.round(d['t'] / d['dt']).astype(np.int64)
    every = max(int(round(1.0 / d['dt'])), 1)
    return np.nonzero(steps % every == 0)[0]


def samples(name, every_second=True, max_rows=4_000_000):
    """Speed, acceleration, gap and time headway samples of a real dataset, and lane changes per vehicle km."""
    d = tracks(name)
    keep = _per_second(d) if every_second else np.arange(len(d['t']))
    if len(keep) > max_rows:
        keep = keep[:: len(keep) // max_rows + 1]
    t, track, v = d['t'][keep], d['track'][keep], d['v'][keep]
    order = np.lexsort((t, track))
    tr, ts, vs = track[order], t[order], v[order]
    same = (np.diff(tr) == 0) & (np.abs(np.diff(ts) - 1.0 if every_second else np.diff(ts) - d['dt']) < 0.01)
    acc = np.diff(vs)[same] / (1.0 if every_second else d['dt'])
    # Bumper gaps within a lane and instant.
    lane, s, length = d['lane'][keep], d['s'][keep].astype(float), d['length'][keep]
    order2 = np.lexsort((s, lane, t))
    ti, la, ss, ll, vv = t[order2], lane[order2], s[order2], length[order2], v[order2]
    pair = (np.diff(ti) == 0) & (np.diff(la) == 0)
    gaps = (np.diff(ss) - ll[1:])[pair]
    follower_v = vv[:-1][pair]
    # The axis can run against the traffic: then the car behind is the one with greater s.
    with np.errstate(invalid='ignore', divide='ignore'):
        headway = np.where((gaps > 0) & (follower_v > 1), gaps / follower_v, np.nan)
    order3 = np.lexsort((d['t'], d['track']))
    tr3, la3 = d['track'][order3], d['lane'][order3]
    changes = int(((np.diff(tr3) == 0) & (np.diff(la3) != 0)).sum())
    km = float(np.nansum(d['v']) * d['dt'] / 1000.0)
    return dict(name=name, speed=vs.astype(float), acc=acc.astype(float), gap=gaps[(gaps > 0) & (gaps < 200)].astype(float), headway=headway[np.isfinite(headway) & (headway < 10)], lc_per_km=changes / max(km, 1e-9), veh_km=km)
