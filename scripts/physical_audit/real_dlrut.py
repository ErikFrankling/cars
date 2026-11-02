#!/usr/bin/env python3
"""Real driving from DLR Urban Traffic: samples, stops, launches and turns, from positions only.

Positions at 20 Hz go through a Savitzky-Golay fit (order 3) over each of --windows seconds; speed,
acceleration and jerk are derivatives of that fit. The provider's own velocity and acceleration are
not used. Tracks are cut at the 15 minute batch edges. Reads one batch at a time.

    python3 -I real_dlrut.py --zip Z --out DIR [--windows 1,2] [--every 1]
"""
import argparse
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

COLS = ['timestamp', 'id', 'center_easting', 'center_northing', 'dimension_length', 'dimension_width',
        'classifications_car', 'classifications_van', 'classifications_truck', 'classifications_bicycle',
        'classifications_motorbike', 'classifications_pedestrian']
HZ = 20.0


def derive(e, n, window):
    w = int(round(window * HZ)) | 1
    w = max(w, 5)
    dt = 1 / HZ
    ve, vn = (savgol_filter(x, w, 3, deriv=1, delta=dt) for x in (e, n))
    ae, an = (savgol_filter(x, w, 3, deriv=2, delta=dt) for x in (e, n))
    v = np.hypot(ve, vn)
    safe = np.maximum(v, 0.3)
    al = (ae * ve + an * vn) / safe
    at = (ve * an - vn * ae) / safe
    jerk = np.gradient(savgol_filter(al, w, 2), dt)
    return v, al, at, jerk


def along(v):
    return np.concatenate(([0], np.cumsum(v[:-1] / HZ)))


def stops(t, v, al, s):
    """Brake episodes that end at a stand, and launches from a stand."""
    out_s, out_l = [], []
    stand = v < 0.25
    i = 1
    while i < len(v):
        if stand[i] and not stand[i - 1]:
            j = i
            while j > 0 and al[j] < -0.1:
                j -= 1
            # Onset: last point with no braking before the stop.
            if v[j] >= 3.0 and i - j >= 4:
                out_s.append(dict(i=i, t=float(t[i]), v0=float(v[j]), dur=float((i - j) / HZ), dist=float(s[i] - s[j]),
                                  mean=float(v[j] / ((i - j) / HZ)), peak=float(al[j:i + 1].min()),
                                  need=float(v[j] ** 2 / max(2 * (s[i] - s[j]), 0.1))))
        if stand[i - 1] and not stand[i]:
            k = i
            while k < len(v) and v[k] < 10.5 and k - i < 25 * HZ:
                k += 1
            if v[min(k, len(v) - 1)] >= 3.0:
                seg = v[i:k + 1]
                rec = dict(t=float(t[i]), peak=float(al[i:k + 1].max()), top=float(seg.max()))
                for target in (3, 5, 8, 10):
                    hit = np.argmax(seg >= target) if (seg >= target).any() else -1
                    rec[f't{target}'] = float(hit / HZ) if hit >= 0 else None
                    rec[f'd{target}'] = float(s[i + hit] - s[i]) if hit >= 0 else None
                out_l.append(rec)
        i += 1
    return out_s, out_l


def turns(v, at, s, heading):
    """Stretches of a curve: signed curvature of one sign, over 25 degrees in all."""
    out = []
    kappa = at / np.maximum(v ** 2, 1.0)
    curving = (np.abs(kappa) > 1 / 300) & (v > 1.5)
    i = 0
    n = len(v)
    while i < n:
        if not curving[i]:
            i += 1
            continue
        j = i
        sign = np.sign(kappa[i])
        while j + 1 < n and curving[j + 1] and np.sign(kappa[j + 1]) == sign:
            j += 1
        dh = abs(np.unwrap(heading[i:j + 1])[-1] - np.unwrap(heading[i:j + 1])[0]) if j > i else 0
        length = s[j] - s[i]
        if dh > np.radians(25) and length > 5:
            # Tightest 5 m held: the radius a driver had to steer, and speed through it.
            r_mean = length / dh
            core = np.abs(kappa[i:j + 1]) >= 0.6 * np.abs(kappa[i:j + 1]).max()
            out.append(dict(r_mean=float(r_mean), r_tight=float(1 / np.abs(kappa[i:j + 1]).max()),
                            r_core=float(1 / np.abs(kappa[i:j + 1][core]).mean()),
                            v_min=float(v[i:j + 1].min()), v_mean=float(v[i:j + 1].mean()), v_core=float(v[i:j + 1][core].mean()),
                            ay_peak=float(np.abs(at[i:j + 1]).max()), ay_core=float(np.abs(at[i:j + 1][core]).mean()),
                            turn_deg=float(np.degrees(dh)), length=float(length)))
        i = j + 1
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--zip', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--windows', default='1,2')
    p.add_argument('--every', type=int, default=1, help='use every n-th batch')
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    z = zipfile.ZipFile(a.zip)
    names = sorted(n for n in z.namelist() if '/raw_data/trajectories/' in n and n.endswith('.csv'))[::a.every]
    windows = [float(x) for x in a.windows.split(',')]
    res = {w: dict(samples=[], stops=[], launches=[], turns=[], noise=[]) for w in windows}
    dims = []
    for name in names:
        with z.open(name) as f:
            df = pd.read_csv(io.BytesIO(f.read()), usecols=COLS, parse_dates=False)
        u, inv = np.unique(df.timestamp.values.astype(str), return_inverse=True)
        df['t'] = ((pd.to_datetime(pd.Series(u), format='ISO8601', utc=True) - pd.Timestamp('2023-09-24', tz='UTC')).dt.total_seconds().values)[inv]
        df = df.drop(columns='timestamp')
        cls = df.groupby('id')[['classifications_car', 'classifications_van', 'classifications_truck', 'classifications_bicycle', 'classifications_motorbike', 'classifications_pedestrian']].mean()
        kind = cls.idxmax(axis=1).str.replace('classifications_', '')
        keep = kind[kind.isin(['car', 'van', 'truck'])].index
        df = df[df.id.isin(keep)]
        # Who stood where, for the leader test at the moment of a stop.
        frames = df[['t', 'id', 'center_easting', 'center_northing']].copy()
        frames['tk'] = (frames.t * 2).round().astype('int64')
        frames = frames.groupby(['tk', 'id']).first().reset_index()
        by_time = {k: g for k, g in frames.groupby('tk')}
        for vid, g in df.groupby('id'):
            g = g.sort_values('t')
            if len(g) < 60:
                continue
            t = g.t.values
            if np.median(np.diff(t)) > 0.1 or t[-1] - t[0] < 4:
                continue
            tu = np.arange(t[0], t[-1], 1 / HZ)
            e = np.interp(tu, t, g.center_easting.values)
            n = np.interp(tu, t, g.center_northing.values)
            k = kind[vid]
            dims.append((k, float(g.dimension_length.median()), float(g.dimension_width.median())))
            heading = np.arctan2(np.gradient(n), np.gradient(e))
            for w in windows:
                R = res[w]
                v, al, at, jerk = derive(e, n, w)
                s = along(v)
                stand = v < 0.15
                if stand.sum() > 40:
                    R['noise'].append(np.c_[al[stand][::10], jerk[stand][::10]].astype('f4'))
                step = int(HZ / 2)
                kk = {'car': 0, 'van': 1, 'truck': 2}[k]
                R['samples'].append(np.c_[v[::step], al[::step], at[::step], jerk[::step], np.full(len(v[::step]), kk)].astype('f4'))
                st, la = stops(tu, v, al, s)
                for r in st:
                    i = r.pop('i')
                    r['kind'] = k
                    fr = by_time.get(int(round(tu[i] * 2)))
                    r['leader_gap'] = None
                    if fr is not None:
                        dx = fr.center_easting.values - e[i]
                        dy = fr.center_northing.values - n[i]
                        h = heading[max(i - 40, 0)]
                        lon = dx * np.cos(h) + dy * np.sin(h)
                        lat = -dx * np.sin(h) + dy * np.cos(h)
                        m = (lon > 2) & (lon < 25) & (np.abs(lat) < 1.6) & (fr.id.values != vid)
                        r['leader_gap'] = float(lon[m].min()) if m.any() else None
                    R['stops'].append(r)
                for r in la:
                    r['kind'] = k
                    R['launches'].append(r)
                for r in turns(v, at, s, heading):
                    r['kind'] = k
                    R['turns'].append(r)
        print(name[-35:], len(res[windows[0]]['stops']), flush=True)
    pd.DataFrame(dims, columns=['kind', 'length', 'width']).to_csv(out / 'ut_dims.csv', index=False)
    for w in windows:
        R = res[w]
        tag = f'w{w:g}'
        np.save(out / f'ut_samples_{tag}.npy', np.concatenate(R['samples']))
        pd.DataFrame(R['stops']).to_csv(out / f'ut_stops_{tag}.csv', index=False)
        pd.DataFrame(R['launches']).to_csv(out / f'ut_launches_{tag}.csv', index=False)
        pd.DataFrame(R['turns']).to_csv(out / f'ut_turns_{tag}.csv', index=False)
        nz = np.concatenate(R['noise'])
        (out / f'ut_noise_{tag}.json').write_text(json.dumps(dict(n=len(nz), acc_sd=float(nz[:, 0].std()), acc_p99=float(np.percentile(np.abs(nz[:, 0]), 99)), jerk_p99=float(np.percentile(np.abs(nz[:, 1]), 99)))))


if __name__ == '__main__':
    main()
