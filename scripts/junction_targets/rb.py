"""Roundabout measurements from tracks: one function for OpenDD, Swiss and simulated output.
A track is (id, cls, t, x, y, v) in metres, seconds, m/s at about 5 Hz. Right-hand traffic is not assumed: the sense comes from the tracks."""
import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks

import os
ENTRY_ZONE = float(os.environ.get('JT_ZONE', 6.0))
UP = 25.0


def polar(tr, cx, cy):
    out = []
    for i, c, t, x, y, v in tr:
        if len(t) < 8:
            continue
        r = np.hypot(x - cx, y - cy)
        th = np.unwrap(np.arctan2(y - cy, x - cx))
        out.append(dict(id=i, cls=c, t=t, x=x, y=y, v=v, r=r, th=th))
    return out


def mark(tr, Ry):
    """Finds who crosses the yield radius from outside, and who leaves it."""
    ent, ext = [], []
    for a in tr:
        ins = a['r'] < Ry
        a['kin'] = a['kout'] = -1
        if not ins.any():
            continue
        k = int(np.argmax(ins))
        if k > 0 and a['r'][0] > Ry + 4:
            a['kin'] = k
            a['ang'] = a['th'][k] % (2 * np.pi)
            ent.append(a)
        k2 = len(ins) - 1 - int(np.argmax(ins[::-1]))
        if k2 < len(ins) - 1 and a['r'][-1] > Ry + 4:
            a['kout'] = k2
            a['ango'] = a['th'][k2] % (2 * np.pi)
            ext.append(a)
    return ent, ext


def sense(ent):
    s = [np.sign(a['th'][min(a['kin'] + 15, len(a['th']) - 1)] - a['th'][a['kin']]) for a in ent if a['kin'] + 8 < len(a['th'])]
    return int(np.sign(np.sum(s))) or 1


def arm_angles(angs, minshare=.06):
    h = np.histogram(angs, bins=72, range=(0, 2 * np.pi))[0].astype(float)
    hh = uniform_filter1d(np.r_[h, h, h], 3)
    pk = find_peaks(hh, distance=7, height=max(5, minshare * h.max()))[0]
    pk = pk[(pk >= 72) & (pk < 144)] - 72
    return sorted(np.round((pk + .5) * 2 * np.pi / 72, 3))


def nearest_arm(a, arms, lim=.45):
    d = [abs((a - b + np.pi) % (2 * np.pi) - np.pi) for b in arms]
    j = int(np.argmin(d))
    return j if d[j] < lim else -1


def passes(tr, arms, Ry, sgn):
    """Ring cars crossing each arm's entry angle. A car that entered through this arm, or leaves right after the angle, does not count."""
    p = {j: [] for j in range(len(arms))}
    for a in tr:
        r, th, t = a['r'], a['th'], a['t']
        ring = r < Ry + .5
        if ring.sum() < 3:
            continue
        for j, b in enumerate(arms):
            m = np.flatnonzero(ring[:-1] & ring[1:])
            d0 = (th[m] - b + np.pi) % (2 * np.pi) - np.pi
            d1 = (th[m + 1] - b + np.pi) % (2 * np.pi) - np.pi
            hit = m[(d0 * sgn < 0) & (d1 * sgn >= 0) & (np.abs(d0 - d1) < 1)]
            for k in hit:
                if a['kin'] >= 0 and nearest_arm(a['ang'], arms) == j and t[k] - t[a['kin']] < 4:
                    continue
                if abs(th[-1] - th[k]) < .15 and a['kout'] >= 0:
                    continue
                p[j].append((float(t[k + 1]), a['id'], float(a['v'][k]), float(r[k])))
    return {j: sorted(v) for j, v in p.items()}


def analyse(tr, cx, cy, Ry, arms, sgn, armsx, label):
    """Returns per-entry records, follow-up headways and per-second queue counts for one flight."""
    tr = polar(tr, cx, cy)
    ent, ext = mark(tr, Ry)
    pp = passes(tr, arms, Ry, sgn)
    byarm = {j: [] for j in range(len(arms))}
    for a in ent:
        a['arm'] = nearest_arm(a['ang'], arms)
        if a['arm'] >= 0:
            byarm[a['arm']].append(a)
    for j in byarm:
        byarm[j].sort(key=lambda a: a['t'][a['kin']])
    if not tr:
        return [], [], {}, {}
    t0 = min(a['t'][0] for a in tr)
    t1 = max(a['t'][-1] for a in tr)
    rec, fu = [], []
    for j, L in byarm.items():
        P = np.array([x[0] for x in pp[j]]) if pp[j] else np.zeros(0)
        Pid = np.array([x[1] for x in pp[j]]) if pp[j] else np.zeros(0)
        tcs = np.array([a['t'][a['kin']] for a in L])
        # tangential offset of the entry point separates entry lanes
        w = np.array([((a['th'][a['kin']] - arms[j] + np.pi) % (2 * np.pi) - np.pi) * Ry for a in L])
        for n, a in enumerate(L):
            t, r, v = a['t'], a['r'], a['v']
            k = a['kin']
            tc = t[k]
            ka = int(np.argmax(r < Ry + ENTRY_ZONE))
            ta = t[ka]
            first = ka > 0 and not np.any((tcs > ta) & (tcs < tc))
            q = P[Pid != a['id']] if len(P) else P
            nx = q[q > tc]
            pv = q[q <= tc]
            acc = rmax = None
            nrej = 0
            is_lag = False
            if len(nx):
                acc = nx[0] - max(pv[-1] if len(pv) else -1e9, ta)
                is_lag = (pv[-1] if len(pv) else -1e9) < ta
                btw = q[(q > ta) & (q <= tc)]
                rej = ([btw[0] - ta] + list(np.diff(btw))) if len(btw) else []
                nrej = len(rej)
                rmax = max(rej) if rej else 0.
            ku = int(np.argmax(r < Ry + UP))
            trav = tc - t[ku] if ku > 0 and r[0] > Ry + UP else np.nan
            kex = a['kout']
            sweep = abs(a['th'][kex] - a['th'][k]) if kex > k else np.nan
            kmin = max(ka - 10, 0)
            minv = float(v[kmin:k + 1].min())
            pet = (nx[0] - tc) if len(nx) else np.nan
            rec.append(dict(flight=label, arm=j, id=a['id'], cls=a['cls'], tc=tc, ta=ta, first=first, acc=acc, rmax=rmax, nrej=nrej, is_lag=is_lag,
                            minv=minv, vin=float(v[k]), trav=trav, sweep=sweep, pet=pet, w=float(w[n]), censored_exit=kex <= k,
                            vring=float(np.median(v[k:kex + 1])) if kex > k else np.nan,
                            rring=float(np.median(r[k:kex + 1])) if kex > k else np.nan,
                            vout=float(v[min(kex + 5, len(v) - 1)]) if kex > k else np.nan, stop=minv < 1.0))
            if n and tc - tcs[n - 1] < 8 and not np.any((P > tcs[n - 1]) & (P < tc)) and v[max(k - 15, 0):k].min() < 2.5:
                fu.append(dict(flight=label, arm=j, h=float(tc - tcs[n - 1]), dw=abs(w[n] - w[n - 1])))
    # one-second queue count per arm: stopped cars within 60 m outside the yield radius on the arm
    grid = np.arange(np.ceil(t0), np.floor(t1))
    Q = {j: np.zeros(len(grid), int) for j in byarm}
    for j, L in byarm.items():
        for a in L:
            k = a['kin']
            m = (a['v'][:k] < 1.5) & (a['r'][:k] < Ry + 60)
            if m.any():
                ii = np.unique(np.searchsorted(grid, a['t'][:k][m]))
                Q[j][ii[ii < len(grid)]] += 1
    flows = dict(grid=grid, Q=Q, passes={j: np.array([x[0] for x in pp[j]]) for j in pp}, entries={j: np.array([a['t'][a['kin']] for a in byarm[j]]) for j in byarm},
                 t0=t0, t1=t1, n_ext=len(ext))
    return rec, fu, flows, {'n': len(tr), 'ent': len(ent)}
