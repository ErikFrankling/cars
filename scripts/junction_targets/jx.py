"""Junction measurements from plain tracks, with no map beyond a centre point: arms, movements, stop lines, queues, discharge, delay, gaps.
Same functions for real data and for `cars run --trace` output. Track = dict(id, cls, t, x, y, v)."""
import numpy as np
import pandas as pd
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks


def wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def make_tracks(i, c, t, x, y, v=None, keep=None, smooth=3):
    """Arrays sorted by (id, t) to tracks. keep is a set of classes."""
    o = np.lexsort((t, i))
    i, c, t, x, y = i[o], c[o], t[o], x[o], y[o]
    v = v[o] if v is not None else None
    cuts = np.r_[0, np.flatnonzero(np.diff(i)) + 1, len(i)]
    out = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        if b - a < 8 or (keep is not None and c[a] not in keep):
            continue
        tt = t[a:b].astype('f8')
        xx = uniform_filter1d(x[a:b].astype('f8'), smooth)
        yy = uniform_filter1d(y[a:b].astype('f8'), smooth)
        vv = v[a:b].astype('f8') if v is not None else np.hypot(np.gradient(xx, tt), np.gradient(yy, tt))
        out.append(dict(id=int(i[a]), cls=c[a], t=tt, x=xx, y=yy, v=vv))
    return out


def heading(x, y, a, b):
    return np.arctan2(y[b] - y[a], x[b] - x[a])


def index_arc(s, target):
    return int(np.searchsorted(s, target))


def passages(tr, cx, cy, R):
    """One record per pass through the circle: arm angle in, angle out, turn, in and out time."""
    rec = []
    for a in tr:
        d = np.hypot(a['x'] - cx, a['y'] - cy)
        ins = d < R
        if not ins.any():
            continue
        k0 = int(np.argmax(ins))
        k1 = len(ins) - 1 - int(np.argmax(ins[::-1]))
        s = np.r_[0, np.cumsum(np.hypot(np.diff(a['x']), np.diff(a['y'])))]
        complete = k0 > 0 and k1 < len(ins) - 1 and d[0] > R + 5 and d[-1] > R + 5
        up = max(index_arc(s, s[k0] - 12), 0)
        dn = min(index_arc(s, s[k1] + 12), len(s) - 1)
        hin = heading(a['x'], a['y'], up, k0) if k0 > up else np.nan
        hout = heading(a['x'], a['y'], k1, dn) if dn > k1 else np.nan
        turn = wrap(hout - hin)
        rec.append(dict(a=a, d=d, s=s, k0=k0, k1=k1, ang_in=np.arctan2(a['y'][k0] - cy, a['x'][k0] - cx), ang_out=np.arctan2(a['y'][k1] - cy, a['x'][k1] - cx),
                        hin=hin, hout=hout, turn=turn, complete=complete))
    return rec


def movement(turn):
    if not np.isfinite(turn):
        return 'unknown'
    u = abs(turn)
    return 'through' if u < np.deg2rad(35) else 'uturn' if u > np.deg2rad(150) else 'left' if turn > 0 else 'right'


def arms_of(angles, minshare=.07):
    h = np.histogram(angles % (2 * np.pi), bins=72, range=(0, 2 * np.pi))[0].astype(float)
    hh = uniform_filter1d(np.r_[h, h, h], 3)
    pk = find_peaks(hh, distance=8, height=max(4, minshare * h.max()))[0]
    pk = pk[(pk >= 72) & (pk < 144)] - 72
    return np.array(sorted((pk + .5) * 2 * np.pi / 72))


def assign(ang, arms, lim=.5):
    d = np.abs(wrap(ang[:, None] - arms[None, :]))
    j = d.argmin(1)
    j[d.min(1) > lim] = -1
    return j


def per_vehicle(tr, cx, cy, R=15., U=60., label=''):
    """Per-vehicle table of a junction: arm, movement, stop line crossing, stop facts, speeds."""
    P = [p for p in passages(tr, cx, cy, R) if p['k0'] > 0]
    if len(P) < 5:
        return pd.DataFrame(), P
    arms = arms_of(np.array([p['ang_in'] for p in P]))
    if not len(arms):
        return pd.DataFrame(), P
    j = assign(np.array([p['ang_in'] for p in P]), arms)
    rows = []
    for p, arm in zip(P, j):
        a, d, s, k0, k1 = p['a'], p['d'], p['s'], p['k0'], p['k1']
        up = max(index_arc(s, s[k0] - U), 0)
        vup = a['v'][up:k0 + 1]
        stopped = vup < 1.0
        kstop = up + int(np.argmax(stopped)) if stopped.any() else -1
        klast = up + len(stopped) - 1 - int(np.argmax(stopped[::-1])) if stopped.any() else -1
        rows.append(dict(flight=label, id=a['id'], cls=a['cls'], arm=int(arm), move=movement(p['turn']), turn=p['turn'], complete=p['complete'], tin=a['t'][k0], tout=a['t'][k1],
                         stop=bool(stopped.any()), tstop=a['t'][kstop] if kstop >= 0 else np.nan, tgo=a['t'][klast] if klast >= 0 else np.nan,
                         xstop=a['x'][klast] if klast >= 0 else np.nan, ystop=a['y'][klast] if klast >= 0 else np.nan, dstop=d[klast] if klast >= 0 else np.nan,
                         sstop=(s[k0] - s[klast]) if klast >= 0 else np.nan, vmin_core=a['v'][k0:k1 + 1].min(), vin=a['v'][k0], vout=a['v'][k1], vmed_core=np.median(a['v'][k0:k1 + 1]),
                         vup=np.median(a['v'][up:max(up + 1, index_arc(s, s[k0] - U / 2))]), up_full=s[k0] - s[up] >= U - 5, t_up=a['t'][k0] - a['t'][up],
                         hin=p['hin'], ang_in=p['ang_in']))
    return pd.DataFrame(rows), P


def lane_clusters(df, spacing=2.2):
    """Lanes of an arm from the side offset of stopped cars. Crude, and says so: it splits a wide lane if two queues form in it."""
    df = df.copy()
    df['lane'] = -1
    for arm, g in df[df['stop'] & (df['arm'] >= 0)].groupby('arm'):
        hd = np.nanmedian(g['hin'])
        if not np.isfinite(hd):
            continue
        w = -g['xstop'] * np.sin(hd) + g['ystop'] * np.cos(hd)
        h, e = np.histogram(w, bins=np.arange(w.min() - 1, w.max() + 1.5, .5))
        hs = uniform_filter1d(h.astype(float), 3)
        pk = find_peaks(hs, distance=max(2, int(spacing / .5)), height=max(3, .12 * hs.max()))[0]
        if not len(pk):
            continue
        ctr = e[pk] + .25
        lane = np.abs(w.values[:, None] - ctr[None, :]).argmin(1)
        df.loc[g.index, 'lane'] = lane
    return df


def discharge(df, maxgap=8., nearline=12.):
    """Queue chains per arm and lane: a car joins the chain if it was already stopped when the one ahead left."""
    out = []
    for (arm, lane), g in df[(df['lane'] >= 0) & df['stop'] & (df['arm'] >= 0)].groupby(['arm', 'lane']):
        g = g.sort_values('tin')
        line = np.nanpercentile(g['sstop'], 10)
        pos = 0
        prev = None
        for _, c in g.iterrows():
            ok = prev is not None and c['tstop'] < prev['tin'] and c['tin'] - prev['tin'] < maxgap
            if ok:
                pos += 1
                out.append(dict(flight=c['flight'], arm=arm, lane=lane, pos=pos, h=c['tin'] - prev['tin'], move=c['move'], prevmove=prev['move'], tin=c['tin'], cls=c['cls'], prevcls=prev['cls'], vin=c['vin'], sstop=c['sstop']))
            else:
                pos = 1 if c['sstop'] - line < nearline else 0
            prev = c
    return pd.DataFrame(out)
