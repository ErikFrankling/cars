"""T3 area metrics, measured the same way on a recording (matched samples) and on a run (FCD).
research/truth/replay/RESULTS.md, third round, says what each is for.

- travel time: from the front passing the point where the recording first sees a car to the front passing the last
  point the recording sees it on its route (the end of its last stitched piece);
- approach delay: per incoming edge of a junction, the time between two points on its visible part (up to 60 m
  before the end, and 0.5 m before the end), minus that distance at the edge's free speed (85th percentile of the
  recording's moving car speeds there, the same number on both sides, so it cancels in a difference);
- both by 5-minute bins of elapsed time, by the time a vehicle leaves the section.
"""
import numpy as np, pandas as pd

BIN = 300.0
APPROACH_LEN = 60.0


def edge_of(lane):
    return lane.str.rsplit('_', n=1).str[0]


def from_matched(m, trips=None):
    """matched.csv.gz rows as (trip, time, edge, pos, speed); trip = vid_piece, or given by `trips` (vid_piece -> trip)."""
    d = pd.DataFrame(dict(trip=m.vid.astype(int).astype(str) + '_' + m.piece.astype(str), time=m.ti * 0.2, edge=edge_of(m.lane),
                          internal=m.internal.astype(bool), pos=m.s, speed=m.v))
    if trips is not None:
        d['trip'] = d.trip.map(trips)
        d = d[d.trip.notna()]
    return d[~d.internal]


def from_fcd(f):
    d = pd.DataFrame(dict(trip=f.trip, time=f.time, edge=edge_of(f.lane), internal=f.lane.str.startswith(':'), pos=f.pos, speed=f.speed))
    return d[~d.internal]


def crossing(d, edge, s):
    """Per trip, the time its front passes `s` on `edge` (linear between samples), NaN where it never does."""
    g = d[d.edge == edge]
    out = {}
    for t, h in g.groupby('trip'):
        p, tm = h.pos.values, h.time.values
        k = np.flatnonzero((p[:-1] < s) & (p[1:] >= s))
        if len(k):
            i = k[0]
            out[t] = tm[i] + (s - p[i]) / max(p[i + 1] - p[i], 1e-6) * (tm[i + 1] - tm[i])
        elif len(p) and p[0] >= s and p[0] - s < 0.5:
            out[t] = tm[0]
    return pd.Series(out, dtype=float)


def crossings_many(d, points):
    """points: DataFrame (trip, edge, s) -> Series trip -> time, each trip at its own point."""
    out = {}
    by = {t: h for t, h in d.sort_values('time').groupby('trip')}
    for r in points.itertuples():
        if r.trip not in by:
            continue
        h = by[r.trip]
        h = h[h.edge == r.edge]
        p, tm = h.pos.values, h.time.values
        k = np.flatnonzero((p[:-1] < r.s) & (p[1:] >= r.s))
        if len(k):
            i = k[0]
            out[r.trip] = tm[i] + (r.s - p[i]) / max(p[i + 1] - p[i], 1e-6) * (tm[i + 1] - tm[i])
        elif len(p) and abs(p[0] - r.s) < 0.5:
            out[r.trip] = tm[0]
        elif len(p) and abs(p[-1] - r.s) < 0.5:
            out[r.trip] = tm[-1]
    return pd.Series(out, dtype=float)


def approaches(rec, lengths, incoming, min_veh=30):
    """Sections to score: incoming edges of junctions with at least `min_veh` recorded cars through the section."""
    out = []
    for e in incoming:
        g = rec[rec.edge == e]
        if g.trip.nunique() < min_veh or e not in lengths:
            continue
        L = lengths[e]
        s_vis = float(g.pos.quantile(0.02))
        a, b = max(s_vis + 1.0, L - APPROACH_LEN), L - 0.5
        if b - a < 10:
            continue
        mv = g[(g.pos > a) & (g.pos < b) & (g.speed > 1.0)].speed
        out.append(dict(edge=e, a=a, b=b, v_free=float(mv.quantile(0.85)) if len(mv) > 20 else 13.9))
    return out


def approach_delays(d, apps, begin):
    rows = []
    for ap in apps:
        ta, tb = crossing(d, ap['edge'], ap['a']), crossing(d, ap['edge'], ap['b'])
        both = ta.index.intersection(tb.index)
        dl = (tb[both] - ta[both]) - (ap['b'] - ap['a']) / ap['v_free']
        rows += [dict(edge=ap['edge'], trip=t, t_out=tb[t], delay=dl[t], bin=int((tb[t] - begin) // BIN)) for t in both if tb[t] > ta[t]]
    return pd.DataFrame(rows, columns=['edge', 'trip', 't_out', 'delay', 'bin'])


def delay_table(dl, min_n=3):
    """Mean delay per approach and bin, with counts."""
    g = dl.groupby(['edge', 'bin']).delay.agg(['mean', 'size']).reset_index()
    return g[g['size'] >= min_n]


def compare_delays(a, b, min_n=3):
    """Mean absolute difference of per-approach-bin mean delays (s), weighted by vehicles, and per bin."""
    ta, tb = delay_table(a, min_n), delay_table(b, min_n)
    j = ta.merge(tb, on=['edge', 'bin'], suffixes=('_a', '_b'))
    if not len(j):
        return dict(n_cells=0)
    j['err'] = j.mean_b - j.mean_a; w = np.minimum(j.size_a, j.size_b)
    per_bin = {int(k): round(float(np.average(np.abs(h.err), weights=np.minimum(h.size_a, h.size_b))), 2) for k, h in j.groupby('bin')}
    per_app = {e: round(float(h.err.mean()), 2) for e, h in j.groupby('edge')}
    return dict(n_cells=int(len(j)), mae_s=round(float(np.average(np.abs(j.err), weights=w)), 2), bias_s=round(float(np.average(j.err, weights=w)), 2),
                mean_delay_a_s=round(float(np.average(j.mean_a, weights=w)), 2), mae_by_bin=per_bin, bias_by_approach=per_app)


def held_by(f, sim, two_wheelers, dt_row=1.0):
    """Car-seconds a simulated car spends with a replayed two-wheeler as its leader on its lane, bumper gap under 2 m + 1 s x speed."""
    g = f.sort_values(['time', 'lane', 'pos'])
    same = (g.time.values[1:] == g.time.values[:-1]) & (g.lane.values[1:] == g.lane.values[:-1])
    gap = g.pos.values[1:] - g.length.values[1:] - g.pos.values[:-1]
    fol, lead = g.trip.values[:-1], g.trip.values[1:]
    is_sim = np.isin(fol, list(sim)); is_2w = np.isin(lead, list(two_wheelers))
    held = same & is_sim & is_2w & (gap < 2.0 + 1.0 * g.speed.values[:-1])
    led = same & is_sim
    return dict(car_seconds_held=round(float(held.sum() * dt_row), 1), cars_held=int(len(set(fol[held]))),
                share_of_led_car_seconds=round(float(held.sum() / max(led.sum(), 1)), 4))


def means(df, key, val, min_n):
    g = df.groupby(key)[val].agg(['mean', 'size'])
    return g[g['size'] >= min_n]


def compare_means(a, b, min_n=5):
    """Weighted (by the smaller count) mean absolute difference and bias of per-key means, b minus a."""
    j = a.join(b, how='inner', lsuffix='_a', rsuffix='_b')
    j = j[(j.size_a >= min_n) & (j.size_b >= min_n)]
    if not len(j):
        return dict(n_keys=0)
    w = np.minimum(j.size_a, j.size_b); d = j.mean_b - j.mean_a
    return dict(n_keys=int(len(j)), vehicles=int(w.sum()), mae_s=round(float(np.average(np.abs(d), weights=w)), 2),
                bias_s=round(float(np.average(d, weights=w)), 2), mean_a_s=round(float(np.average(j.mean_a, weights=w)), 2))


def session_delay(dl, min_n=30):
    """Per-approach mean delay over a whole period."""
    return means(dl, 'edge', 'delay', min_n)


def route_tt(tt, min_n=5):
    """tt: DataFrame with route (first edge > exit edge) and tt (s): per-route mean travel time."""
    return means(tt, 'route', 'tt', min_n)
