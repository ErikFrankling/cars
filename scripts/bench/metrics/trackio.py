"""Adapter: simulator output to the plain tracks of report 25's scripts, which are the code that measured the real ones.
A track is (id, cls, t, x, y, v). Positions come from lane polylines, with SUMO's length scaling."""
import sys
from pathlib import Path

import numpy as np
from lxml import etree

SCRIPTS = Path(__file__).resolve().parents[2]


def lane_shapes(net, wanted):
    out = {}
    with open(net, 'rb') as f:
        for _, e in etree.iterparse(f, events=('end',), tag='lane'):
            i = e.get('id')
            if i in wanted:
                p = np.array([[float(v) for v in q.split(',')[:2]] for q in e.get('shape').split()])
                s = np.r_[0, np.cumsum(np.hypot(*np.diff(p, axis=0).T))]
                out[i] = (p, s, float(e.get('length')))
            e.clear()
    return out


def centre(net, ids):
    """netconvert moves the origin, so a scene's centre is read from its junctions."""
    xs, ys = [], []
    with open(net, 'rb') as f:
        for _, e in etree.iterparse(f, events=('end',), tag='junction'):
            if e.get('id') in ids:
                xs.append(float(e.get('x')))
                ys.append(float(e.get('y')))
            e.clear()
    return float(np.mean(xs)), float(np.mean(ys))


def lane_end(net, lane):
    """The stop line of a lane, and the heading into it."""
    p = lane_shapes(net, {lane})[lane][0]
    return float(p[-1, 0]), float(p[-1, 1]), float(np.arctan2(p[-1, 1] - p[-2, 1], p[-1, 0] - p[-2, 0]))


def place(df, net):
    """x, y per row of a table with lane and pos. Rows on a lane missing from the net get nan."""
    shapes = lane_shapes(net, set(df.lane.unique()))
    x, y = np.full(len(df), np.nan), np.full(len(df), np.nan)
    lane = df.lane.to_numpy()
    pos = df.pos.to_numpy('f8')
    for name in pd_unique(lane):
        if name not in shapes:
            continue
        p, s, length = shapes[name]
        m = lane == name
        d = np.clip(pos[m] / max(length, 1e-3), 0, 1) * s[-1]
        x[m], y[m] = np.interp(d, s, p[:, 0]), np.interp(d, s, p[:, 1])
    return x, y


def pd_unique(a):
    import pandas as pd
    return pd.unique(a)


def tracks(df, net):
    """Tuples for rb.py, per vehicle, sorted in time. Cars only, as the real extractions keep."""
    x, y = place(df, net)
    ok = np.isfinite(x)
    t, v, trip = df.time.to_numpy('f8')[ok], df.speed.to_numpy('f8')[ok], df.trip.to_numpy()[ok]
    x, y = x[ok], y[ok]
    codes = {k: i + 1 for i, k in enumerate(pd_unique(trip))}
    ids = np.array([codes[k] for k in trip])
    o = np.lexsort((t, ids))
    ids, t, x, y, v = ids[o], t[o], x[o], y[o], v[o]
    cuts = np.r_[0, np.flatnonzero(np.diff(ids)) + 1, len(ids)]
    return [(int(ids[a]), 'Car', t[a:b], x[a:b], y[a:b], v[a:b]) for a, b in zip(cuts[:-1], cuts[1:]) if b - a >= 8]


def as_dicts(tr):
    return [dict(id=i, cls=c, t=t, x=x, y=y, v=v) for i, c, t, x, y, v in tr]


def from_trace(path, net, begin=None, end=None):
    """The same tracks from `cars run --trace`. Vehicles flagged as teleported or collided are left out: they did not drive there."""
    sys.path.insert(0, str(SCRIPTS))
    import cars_trace
    t = cars_trace.Trace(str(path))
    df = t.table(begin, end)
    if len(df):
        df = df[(df['flags'] & (cars_trace.TELEPORT | cars_trace.COLLISION)) == 0]
    return tracks(df, net)
