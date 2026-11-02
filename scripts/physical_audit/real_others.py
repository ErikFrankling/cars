#!/usr/bin/env python3
"""The same measurement as real_dlrut.py on other real tracks: pNEUMA (Athens), the Swiss roundabouts, TGSIM Foggy Bottom.

    python3 -I real_others.py pneuma FILE --out DIR
    python3 -I real_others.py swiss FILE... --out DIR
    python3 -I real_others.py foggy FILE --out DIR [--rows 2000000]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import real_dlrut as U  # noqa: E402


def analyse(tracks, hz, window, out, tag):
    """tracks yields (kind, t, x, y) with t in seconds, x and y in metres."""
    U.HZ = float(hz)
    samples, stops, launches, turns = [], [], [], []
    n = 0
    for kind, t, x, y in tracks:
        if len(t) < hz * 4 or t[-1] - t[0] < 4:
            continue
        n += 1
        tu = np.arange(t[0], t[-1], 1 / hz)
        e, nn = np.interp(tu, t, x), np.interp(tu, t, y)
        v, al, at, jerk = U.derive(e, nn, window)
        s = U.along(v)
        heading = np.arctan2(np.gradient(nn), np.gradient(e))
        step = max(int(hz / 2), 1)
        samples.append(np.c_[v[::step], al[::step], at[::step], jerk[::step]].astype('f4'))
        st, la = U.stops(tu, v, al, s)
        for r in st:
            r.pop('i')
            r['kind'] = kind
        for r in la:
            r['kind'] = kind
        stops += st
        launches += la
        for r in U.turns(v, at, s, heading):
            r['kind'] = kind
            turns.append(r)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / f'{tag}_samples.npy', np.concatenate(samples))
    pd.DataFrame(stops).to_csv(out / f'{tag}_stops.csv', index=False)
    pd.DataFrame(launches).to_csv(out / f'{tag}_launches.csv', index=False)
    pd.DataFrame(turns).to_csv(out / f'{tag}_turns.csv', index=False)
    print(tag, 'tracks', n, 'stops', len(stops), 'launches', len(launches), 'turns', len(turns), flush=True)


def latlon(lat, lon, lat0, lon0):
    R = 6371000.0
    return np.radians(lon - lon0) * R * np.cos(np.radians(lat0)), np.radians(lat - lat0) * R


def pneuma(path):
    with open(path) as f:
        f.readline()
        for line in f:
            parts = [p.strip() for p in line.rstrip().rstrip(';').split(';')]
            kind = parts[1]
            if kind not in ('Car', 'Taxi', 'Medium', 'Heavy', 'Bus'):
                continue
            vals = np.array(parts[4:], dtype=float)
            vals = vals[: len(vals) // 6 * 6].reshape(-1, 6)
            lat, lon, t = vals[:, 0], vals[:, 1], vals[:, 5]
            x, y = latlon(lat, lon, 37.98, 23.73)
            yield kind.lower(), t, x, y


def swiss(paths):
    for path in paths:
        df = pd.read_csv(path)
        tt = pd.to_timedelta(df.time).dt.total_seconds().values
        df['t'] = tt
        for tid, g in df.groupby('track_id'):
            kind = str(g.type.iloc[0]).lower()
            if kind not in ('car', 'van', 'truck', 'bus'):
                continue
            g = g.sort_values('t')
            t = g.t.values
            x, y = latlon(g.lat.values, g.lon.values, g.lat.values[0], g.lon.values[0])
            keep = np.concatenate(([True], np.diff(t) > 0))
            yield kind, t[keep], x[keep], y[keep]


def foggy(path, rows):
    df = pd.read_csv(path, nrows=rows, usecols=['id', 'time', 'xloc_kf', 'yloc_kf', 'length_smoothed'])
    for tid, g in df.groupby('id'):
        g = g.sort_values('time')
        t = g.time.values
        kind = 'car' if g.length_smoothed.median() < 7.5 else 'truck'
        for seg in np.split(np.arange(len(t)), np.flatnonzero(np.diff(t) > 0.5) + 1):
            if len(seg) > 40:
                yield kind, t[seg], g.xloc_kf.values[seg], g.yloc_kf.values[seg]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('source', choices=['pneuma', 'swiss', 'foggy'])
    p.add_argument('files', nargs='+')
    p.add_argument('--out', required=True)
    p.add_argument('--windows', default='2')
    p.add_argument('--rows', type=int, default=2_000_000)
    a = p.parse_args()
    for w in [float(x) for x in a.windows.split(',')]:
        tag = f'{a.source}_w{w:g}'
        if a.source == 'pneuma':
            analyse(pneuma(a.files[0]), 25, w, a.out, tag)
        elif a.source == 'swiss':
            analyse(swiss(a.files), 29.97, w, a.out, tag)
        else:
            analyse(foggy(a.files[0], a.rows), 10, w, a.out, tag)
    json.dumps({})


if __name__ == '__main__':
    main()
