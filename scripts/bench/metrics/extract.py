"""The drone view: what real trajectories were reduced to, applied to simulated trajectories."""
import numpy as np
import pandas as pd

BANDS = [(5, 10), (10, 15), (15, 25), (25, 40)]


def edge_of(lane):
    return lane.rsplit('_', 1)[0]


def track_arrays(f, interval):
    """Per-sample 1 s speed change and 1 s change of that, along each trip."""
    f = f.sort_values(['trip', 'time'], kind='stable').reset_index(drop=True)
    k = max(1, int(round(1.0 / interval)))
    v = f.speed.to_numpy('f8')
    t = f.time.to_numpy('f8')
    trip = f.trip.to_numpy()
    a = np.full(len(f), np.nan)
    ok = (trip[k:] == trip[:-k]) & (np.abs(t[k:] - t[:-k] - k * interval) < interval / 2)
    a[:-k][ok] = (v[k:] - v[:-k])[ok] * (1.0 / (k * interval))
    j = np.full(len(f), np.nan)
    ok2 = np.isfinite(a[k:]) & np.isfinite(a[:-k]) & (trip[k:] == trip[:-k])
    j[:-k][ok2] = (a[k:] - a[:-k])[ok2]
    f['a1'], f['j1'] = a, j
    return f


def leaders(f):
    """Same lane, next front ahead, at the same time. Centre spacing as front-to-front, as report 05 does."""
    f = f.sort_values(['time', 'lane', 'pos'], kind='stable').reset_index(drop=True)
    same = (f.time.shift(-1) == f.time) & (f.lane.shift(-1) == f.lane)
    f['cc'] = (f.pos.shift(-1) - f.pos).where(same)
    f['lead_len'] = f.length.shift(-1).where(same)
    f['lead_v'] = f.speed.shift(-1).where(same)
    f['bumper'] = f.cc - f.lead_len
    return f


def time_gap(f):
    T = ((f.cc - 5) / f.speed.clip(lower=.1)).clip(upper=10.0)
    return T.where((f.cc <= 100) & (f.speed >= 1))


def band_samples(f, lo, hi, col):
    m = (f.speed >= lo) & (f.speed < hi)
    x = f.loc[m, col].to_numpy('f8')
    return x[np.isfinite(x)]


def lane_changes(f, interval):
    """A lane id changing within one edge, between neighbouring samples of a trip. Returns rows at the new lane."""
    f = f.sort_values(['trip', 'time'], kind='stable').reset_index(drop=True)
    same = (f.trip.shift(1) == f.trip) & (f.lane.shift(1) != f.lane)
    edges = f.lane.str.rsplit('_', n=1).str[0]
    same &= edges.shift(1) == edges
    same &= ~edges.str.startswith(':')
    return f[same]


def veh_km(f, interval):
    return float(f.speed.sum() * interval / 1000)


def gaps_at_change(f, events):
    """Time gap to the new follower and new leader at the first sample on the new lane."""
    rows = []
    by = {t: g for t, g in f[f.time.isin(set(events.time))].groupby('time', sort=False)}
    for r in events.itertuples():
        g = by[r.time]
        g = g[(g.lane == r.lane) & (g.trip != r.trip)]
        ahead = g[g.pos > r.pos]
        behind = g[g.pos < r.pos]
        lead = lag = np.nan
        if len(ahead):
            x = ahead.loc[ahead.pos.idxmin()]
            lead = (x.pos - x.length - r.pos) / max(r.speed, .5)
        if len(behind):
            x = behind.loc[behind.pos.idxmax()]
            lag = (r.pos - r.length - x.pos) / max(x.speed, .5)
        rows.append((lag, lead, r.speed))
    return pd.DataFrame(rows, columns=['lag', 'lead', 'v'])


def lc_shapes(f):
    """Lateral motion from `offset` on drivers that have one. A change runs from full width down to zero."""
    rows = []
    if 'offset' not in f or not (f.offset.abs() > 1e-3).any():
        return pd.DataFrame(columns=['t1090', 'peak', 'v'])
    for trip, g in f[f.trip.isin(f.loc[f.offset.abs() > 1e-3, 'trip'].unique())].groupby('trip'):
        g = g.sort_values('time')
        moving = g.offset.abs().values > 1e-3
        idx = np.where(moving)[0]
        for chunk in np.split(idx, np.where(np.diff(idx) > 1)[0] + 1):
            if len(chunk) < 4 or chunk[0] == 0 or chunk[-1] == len(g) - 1:
                continue
            o = g.offset.abs().values[chunk]
            t = g.time.values[chunk]
            w = o.max()
            frac = 1 - o / w
            if w < 2.0 or g.speed.values[chunk].min() < 3.0:
                continue
            rows.append((np.interp(.9, frac, t) - np.interp(.1, frac, t), np.max(np.abs(np.diff(o) / np.diff(t))), g.speed.values[chunk].mean()))
    return pd.DataFrame(rows, columns=['t1090', 'peak', 'v'])


def queue_table(f, lane, length, cycle, green, end):
    """Per green onset, the standing queue in order, with crossing times. Returns rows per position per cycle."""
    f = f.sort_values(['trip', 'time'], kind='stable')
    tracks = {t: g for t, g in f.groupby('trip', sort=False)}
    onl = f[f.lane == lane]
    rows = []
    interval = float(np.median(np.diff(np.unique(f.time.values)[:50])))
    for k in range(1, int(end / cycle)):
        tg = k * cycle
        if not len(onl):
            continue
        nearest = onl.time.iloc[np.abs(onl.time.to_numpy() - tg).argmin()]
        if abs(nearest - tg) > interval:
            continue
        snap = onl[onl.time == nearest]
        snap = snap[snap.speed < 1.0].sort_values('pos', ascending=False)
        if snap.empty or length - snap.pos.iloc[0] > 15:
            continue
        prev_pos, prev_cross = None, tg
        for i, s in enumerate(snap.itertuples(), 1):
            if prev_pos is not None and prev_pos - s.pos > 15:
                break
            g = tracks[s.trip]
            g = g[g.time >= tg]
            onlane = g[g.lane == lane]
            if onlane.empty or len(g) == len(onlane):
                break
            last = onlane.iloc[-1]
            cross = float(last.time + (length - last.pos) / max(last.speed, .5))
            if cross > tg + green + 1:
                break
            moved = g[g.speed > .5]
            start = float(moved.time.iloc[0] - tg) if len(moved) else np.nan
            to5 = g[g.speed >= 5]
            rows.append(dict(cycle=k, pos=i, h=cross - prev_cross, cross=cross - tg, start=start, spacing=(prev_pos - s.pos) if prev_pos is not None else np.nan, stand=s.pos,
                             peak=float(g[g.time < tg + 10].acc.max()) if 'acc' in g else np.nan, t5=float(to5.time.iloc[0] - tg) if len(to5) else np.nan))
            prev_pos, prev_cross = s.pos, cross
    return pd.DataFrame(rows)


def wave_lag(speeds_a, speeds_b, dt, sep):
    """Backward wave speed from the lag that best lines up the two speed series, km/h."""
    a = np.asarray(speeds_a) - np.mean(speeds_a)
    b = np.asarray(speeds_b) - np.mean(speeds_b)
    n = min(len(a), len(b))
    if n < 20 or a.std() < .05 or b.std() < .05:
        return np.nan
    best, lag = -2, 0
    for k in range(1, int(60 / dt)):
        if k >= n - 10:
            break
        c = np.corrcoef(a[:n - k], b[k:n])[0, 1]
        if c > best:
            best, lag = c, k
    return sep / (lag * dt) * 3.6 if lag and best > .2 else np.nan


def swing(x, dt):
    k = max(1, int(round(5 / dt)))
    s = np.convolve(x, np.ones(k) / k, mode='valid')
    d = s - s.mean()
    up = np.flatnonzero((d[:-1] < 0) & (d[1:] >= 0))
    per = float(np.median(np.diff(up)) * dt) if len(up) >= 2 else np.nan
    return float(np.quantile(x, .9) - np.quantile(x, .1)), per
