"""Part 1: each tracker's own noise, and what it bounds (F130).

For every moving car track (speed over 2 m/s for 2 s or more) the recorded centre is compared with a local quadratic
over 1 s (Savitzky-Golay, 25 samples at 25 Hz, 5 at 5 Hz, 11 at 10 Hz). What is left is jitter the provider's own
smoothing let through; it bounds spacing (sqrt 2 x), speed (the same residual on speed) and acceleration.
The provider's speed is also compared with the derivative of its own positions. Spacing jitter for TGSIM and DLR HT
comes from report 05's leader-follower caches (centre spacing about the same 1 s quadratic).

    python3 -I scripts/measure/noise.py      # -> research/truth/measure/noise.json
"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.signal import savgol_filter

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import levelx as LX

OUT = os.path.join(HERE, '..', '..', 'research', 'truth', 'measure')
CACHE05 = '/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-cache'
SAMPLE = {'highD': [1, 11, 25, 46, 7, 15, 4], 'inD': [0, 7, 18, 25], 'rounD': [0, 1, 2, 9], 'exiD': [0, 19, 39, 53, 61, 78]}


def q(v, ps=(50, 90, 99)):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    return {f'p{p}': round(float(np.percentile(v, p)), 4) for p in ps} | {'sd': round(float(v.std()), 4), 'n': int(len(v))}


def resid(x, w):
    return x - savgol_filter(x, w, 2)


def levelx_noise(ds):
    out = dict(pos_lon=[], pos_lat=[], speed=[], acc=[], dxdt_vs_v=[], length_car=[], tracks=0)
    for rec in SAMPLE[ds]:
        d = LX.tracks(ds, rec)
        tm = LX.tracks_meta(ds, rec)
        cl = tm.set_index('id' if ds == 'highD' else 'trackId')['class']
        ids, st, en = LX.by_track(d)
        xc, yc, vx, vy, ax, ay = (d[c].to_numpy(np.float64) for c in ('xc', 'yc', 'vx', 'vy', 'ax', 'ay'))
        for i, a, b in zip(ids, st, en):
            if str(cl.get(i, '')).lower() != 'car' or b - a < 50:
                continue
            v = np.hypot(vx[a:b], vy[a:b])
            if np.median(v) < 2:
                continue
            out['tracks'] += 1
            out['length_car'].append(float(d.length.iat[a]))
            # Direction of travel per sample, from the recorded velocity, splits jitter into along and across.
            ux, uy = vx[a:b] / np.maximum(v, 1e-6), vy[a:b] / np.maximum(v, 1e-6)
            rx, ry = resid(xc[a:b], 25), resid(yc[a:b], 25)
            mv = v > 2
            out['pos_lon'].append((rx * ux + ry * uy)[mv][12:-12])
            out['pos_lat'].append((-rx * uy + ry * ux)[mv][12:-12])
            out['speed'].append(resid(v, 25)[mv][12:-12])
            al = ax[a:b] * ux + ay[a:b] * uy
            out['acc'].append(resid(al, 25)[mv][12:-12])
            # Derivative of a 1 s quadratic of position against the provider's speed.
            dx = savgol_filter(xc[a:b], 25, 2, deriv=1, delta=0.04); dy = savgol_filter(yc[a:b], 25, 2, deriv=1, delta=0.04)
            out['dxdt_vs_v'].append((np.hypot(dx, dy) - v)[mv][12:-12])
    res = {k: q(np.concatenate(v)) for k, v in out.items() if k not in ('tracks', 'length_car')}
    res['tracks'] = out['tracks']; res['recordings'] = SAMPLE[ds]
    res['car_length_m'] = q(out['length_car'], (5, 50, 95))
    return res


def pair_noise(name, hz):
    z = np.load(f'{CACHE05}/pairs_{name}.npz')
    seg, cc, vf = z['seg'], z['cc'].astype(float), z['vf'].astype(float)
    w = {5: 5, 10: 11}[hz]
    cut = np.flatnonzero(np.diff(seg)) + 1
    r, rv = [], []
    for a, b in zip(np.r_[0, cut][:4000], np.r_[cut, len(seg)][:4000]):
        if b - a < 3 * w:
            continue
        r.append(resid(cc[a:b], w)[w:-w]); rv.append(resid(vf[a:b], w)[w:-w])
    return dict(spacing=q(np.concatenate(r)), speed=q(np.concatenate(rv)), segments=len(r))


def highd_dhw():
    """highD's own bumper gap column about the same quadratic, as a direct spacing jitter."""
    r = []
    for rec in SAMPLE['highD'][:3]:
        d = LX.tracks('highD', rec)
        ids, st, en = LX.by_track(d)
        dhw, prec = d.dhw.to_numpy(float), d.prec.to_numpy()
        for a, b in zip(st, en):
            p = prec[a:b]
            brk = np.flatnonzero(np.diff(p)) + 1
            for s0, s1 in zip(np.r_[0, brk], np.r_[brk, b - a]):
                if p[s0] > 0 and s1 - s0 > 75:
                    r.append(resid(dhw[a + s0:a + s1], 25)[12:-12])
    return q(np.concatenate(r))


if __name__ == '__main__':
    res = {ds: levelx_noise(ds) for ds in SAMPLE}
    res['highD']['bumper_gap_column'] = highd_dhw()
    res['tgsim_I90stat_10Hz'] = pair_noise('I90stat', 10)
    res['dlrht_5Hz'] = pair_noise('HT', 5)
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, 'noise.json'), 'w'), indent=1)
    for k, v in res.items():
        print(k, json.dumps({kk: (vv.get('sd') if isinstance(vv, dict) else vv) for kk, vv in v.items()}))
