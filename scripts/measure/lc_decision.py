"""Lane-change decisions (F700-F708): what makes a driver start a change, which gaps they take and refuse, how the
sideways motion runs, on non-held-out exiD, highD and DLR HT (research/truth/measure/HOLDOUT.md).

The event is the START of the sideways motion: the last frame before the centre crosses the marking at which the car has
done under 10% of its lateral displacement (plateaus are the medians of the 0.5 s windows 6 s before and after the
crossing, or as far as the track allows, at least 3 s). The simulator's lane change commits at that moment, so the gaps
and the hazard are read there. Every car is sampled once a second while it is not changing; the outcome is a start within
the next second.

  exiD on-ramps (must change): every second on the acceleration lane is a gap offered, taken or refused. One likelihood:
      h = sigmoid(a0 + aT tte/10) * A_lag * A_lead,  A = Phi((ln t - mu) / sd), t a time gap (lag over the follower's
      speed, lead over own speed, floored at 1 m/s), mu = m0 + m1 max(0, closing speed); no car there means A = 1.
  highD and DLR HT (by choice): the same acceptance, frozen from exiD, times a desire sigmoid(b . x) per side.

    python3 -I scripts/measure/lc_decision.py exiD | highD | dlrht      # states -> cars-data/measure/lc_decision/
    python3 -I scripts/measure/lc_decision.py fit                       # -> research/truth/measure/lc_decision.json
"""
import os, sys, json, glob
import numpy as np, pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, log_ndtr, ndtr

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import levelx as LX
from lanechange import accel_lane_chains

WORK = os.environ.get('LCD_WORK', '/home/erikf/projects/personal/cars-data/measure/lc_decision')
RES = os.path.join(HERE, '..', '..', 'research', 'truth', 'measure')
rng = np.random.default_rng(7)


class Look:
    """(frame, id) -> row, vectorised; -1 where absent."""
    def __init__(self, frame, ids):
        k = frame.astype(np.int64) * (1 << 22) + ids.astype(np.int64)
        self.o = np.argsort(k, kind='stable'); self.k = k[self.o]

    def __call__(self, frame, ids):
        ids = np.nan_to_num(np.asarray(ids, float), nan=-1).astype(np.int64)
        q = np.asarray(frame, np.int64) * (1 << 22) + np.maximum(ids, 0)
        j = np.minimum(np.searchsorted(self.k, q), len(self.k) - 1)
        return np.where((self.k[j] == q) & (ids > 0), self.o[j], -1)


def lateral_event(y, k, fps, w, fixed=None):
    """Start (10%), end (90%), straddle in and out frames around crossing index k of continuous lateral y. `fixed`
    gives the two lane centres instead of plateaus (merges, whose ramp converges on the marking before the lane)."""
    pre = min(6 * fps, k - fps // 2); post = min(6 * fps, len(y) - k - fps // 2)
    if pre < 3 * fps or post < 3 * fps:
        return None
    h = fps // 2
    y0 = np.median(y[k - pre - h:k - pre + 1]); y1 = np.median(y[k + post:k + post + h])
    if fixed is not None:
        y0, y1 = fixed
    D = y1 - y0
    if not 2.5 <= abs(D) <= 5.5:
        return None
    f = (y - y0) / D
    lo = np.flatnonzero(f[k - pre:k] < 0.1); hi = np.flatnonzero(f[k:k + post] > 0.9)
    if not len(lo) or not len(hi):
        return None
    start = k - pre + lo[-1] + 1; end = k + hi[0]
    ym = 0.5 * (y[k - 1] + y[k]); half = 0.5 * w
    out = np.abs(y - ym) >= half
    a = np.flatnonzero(out[:k]); b = np.flatnonzero(out[k:])
    s_in = a[-1] + 1 if len(a) else None; s_out = k + b[0] if len(b) else None
    return start, end, s_in, s_out


def gaps(s, L, i, j, ahead):
    g = (s[j] - s[i]) if ahead else (s[i] - s[j])
    return np.where(j >= 0, g - 0.5 * (L[i] + np.where(j >= 0, L[j], 0)), np.nan)


# ---------------------------------------------------------------- highD

def run_highd():
    meta = LX.recordings('highD')
    S, E = [], []
    for _, m in meta.iterrows():
        rec, site = int(m.rec), int(m.site)
        d = LX.tracks('highD', rec)
        cls = LX.tracks_meta('highD', rec).set_index('id')['class']
        d['cls'] = cls.reindex(d.id).values
        sg = np.where(d.dir.to_numpy() == 2, 1.0, -1.0)
        s = d.xc.to_numpy() * sg; lat = -d.yc.to_numpy() * sg
        v = np.abs(d.vx.to_numpy()); acc = d.ax.to_numpy() * sg
        L = d.length.to_numpy(); W = d.width.to_numpy(); fr = d.frame.to_numpy(); lane = d.lane.to_numpy()
        look = Look(fr, d.id.to_numpy())
        # Lane rank from the right, per direction, from where cars drive.
        rank = np.zeros(len(d), int); nl = np.zeros(len(d), int)
        for dr in (1, 2):
            mm = d.dir.to_numpy() == dr
            ls = pd.Series(lat[mm]).groupby(lane[mm]).median().sort_values()
            ls = ls[pd.Series(lane[mm]).value_counts().reindex(ls.index) > 200]
            r = {int(l): k for k, l in enumerate(ls.index)}
            rank[mm] = [r.get(int(x), -1) for x in lane[mm]]; nl[mm] = len(r)
        # Check that the provider's 'left' is the driver's left.
        jl = look(fr, d.leftPrecedingId.to_numpy())
        ok = (jl >= 0) & (rank >= 0)
        left_ok = float(np.mean(rank[jl[ok]] == rank[ok] + 1))
        ids, st, en = LX.by_track(d)
        rows = []
        for tid, a, b in zip(ids, st, en):
            if b - a < 3 * 25 or rank[a] < 0:
                continue
            ch = np.flatnonzero(lane[a + 1:b] != lane[a:b - 1]) + 1
            busy = np.zeros(b - a, bool); starts = {}
            for k in ch:
                ev = lateral_event(lat[a:b], k, 25, W[a])
                side = 'L' if rank[a + k] > rank[a + k - 1] else 'R'
                if ev is None:
                    busy[max(0, k - 6 * 25):k + 6 * 25] = True; continue
                st0, e0, si, so = ev
                busy[st0 + 1:e0 + 1] = True
                starts[st0] = side
                E.append(dict(ds='highD', rec=rec, site=site, id=int(tid), cls=d.cls.iat[a], side=side, i_start=a + st0, i_cross=a + k,
                              t_cross=(k - st0) / 25, t_end=(e0 - k) / 25, dur_10_90=(e0 - st0) / 25,
                              straddle=(so - si) / 25 if si is not None and so is not None else np.nan,
                              t_body=(si - st0) / 25 if si is not None else np.nan, v=v[a + st0]))
            for r0 in range(0, b - a - 25, 25):
                if busy[r0:r0 + 25].any() and not any(r0 <= x < r0 + 25 for x in starts):
                    continue
                if busy[r0]:
                    continue
                y = next((starts[x] for x in starts if r0 <= x < r0 + 25), '')
                rows.append((a + r0, y))
        if not rows:
            continue
        i = np.array([r[0] for r in rows]); y = np.array([r[1] for r in rows])
        out = dict(rec=rec, site=site, id=d.id.to_numpy()[i], cls=d.cls.to_numpy()[i], v=v[i], acc=acc[i], rank=rank[i], nl=nl[i], y=y)
        jo = look(fr[i], d.prec.to_numpy()[i])
        out['own_gap'] = gaps(s, L, i, jo, True); out['own_v'] = np.where(jo >= 0, v[jo], np.nan)
        for side, pre in (('L', 'left'), ('R', 'right')):
            jp = look(fr[i], d[f'{pre}PrecedingId'].to_numpy()[i]); jf = look(fr[i], d[f'{pre}FollowingId'].to_numpy()[i])
            ja = look(fr[i], d[f'{pre}AlongsideId'].to_numpy()[i])
            lead = gaps(s, L, i, jp, True); lead_v = np.where(jp >= 0, v[jp], np.nan)
            lag = gaps(s, L, i, jf, False); lag_v = np.where(jf >= 0, v[jf], np.nan)
            al = ja >= 0
            al_ahead = al & (s[np.maximum(ja, 0)] >= s[i])
            lead = np.where(al_ahead, gaps(s, L, i, ja, True), lead); lead_v = np.where(al_ahead, v[np.maximum(ja, 0)], lead_v)
            lag = np.where(al & ~al_ahead, gaps(s, L, i, ja, False), lag); lag_v = np.where(al & ~al_ahead, v[np.maximum(ja, 0)], lag_v)
            out[f'{side}_ex'] = (rank[i] + 1 < nl[i]) if side == 'L' else (rank[i] > 0)
            out[f'{side}_lead'] = lead; out[f'{side}_lead_v'] = lead_v; out[f'{side}_lag'] = lag; out[f'{side}_lag_v'] = lag_v
        S.append(pd.DataFrame(out))
        print('highD', rec, site, len(i), int((y != '').sum()), f'left check {left_ok:.3f}', flush=True)
    os.makedirs(WORK, exist_ok=True)
    pd.concat(S).to_pickle(f'{WORK}/highD_states.pkl'); pd.DataFrame(E).to_csv(f'{WORK}/highD_events.csv', index=False)


# ---------------------------------------------------------------- exiD on-ramps

def project_many(pts, x, y):
    seg = np.diff(pts, axis=0); Ls = np.hypot(*seg.T); cum = np.r_[0, np.cumsum(Ls)]
    u = seg / np.maximum(Ls, 1e-9)[:, None]
    best = np.full(len(x), np.inf); sb = np.zeros(len(x))
    for k in range(len(seg)):
        t = np.clip((x - pts[k, 0]) * u[k, 0] + (y - pts[k, 1]) * u[k, 1], 0, Ls[k])
        dd = np.hypot(x - pts[k, 0] - t * u[k, 0], y - pts[k, 1] - t * u[k, 1])
        b = dd < best; best[b] = dd[b]; sb[b] = cum[k] + t[b]
    return sb, best


def chain_marks(ll, chains):
    """The marking each acceleration lane shares with the main carriageway, in driving order, extended 400 m both ways."""
    main_bounds = set()
    for v in ll.values():
        if v['tags'].get('subtype') == 'highway' and v['tags'].get('onramp') != 'yes' and v['tags'].get('offramp') != 'yes':
            main_bounds.add(frozenset(v['left_nodes'])); main_bounds.add(frozenset(v['right_nodes']))
    out = []
    for c in chains:
        parts = []
        for k in c['lanelets']:
            side = 'left' if frozenset(ll[k]['left_nodes']) in main_bounds else 'right'
            pts = ll[k][side]
            sp, _ = project_many(c['centre'], pts[[0, -1], 0], pts[[0, -1], 1])
            if sp[1] < sp[0]:
                pts = pts[::-1]
            parts.append((sp.min(), pts))
        pts = np.vstack([p for _, p in sorted(parts, key=lambda t: t[0])])
        u0 = pts[1] - pts[0]; u1 = pts[-1] - pts[-2]
        pts = np.vstack([pts[0] - 400 * u0 / np.hypot(*u0), pts, pts[-1] + 400 * u1 / np.hypot(*u1)])
        out.append(pts)
    return out


def signed_lateral(pts, x, y):
    """Signed distance of points to a polyline, positive to the left of its direction."""
    seg = np.diff(pts, axis=0); Ls = np.hypot(*seg.T); u = seg / np.maximum(Ls, 1e-9)[:, None]
    best = np.full(len(x), np.inf); sgn = np.zeros(len(x))
    for k in range(len(seg)):
        t = np.clip((x - pts[k, 0]) * u[k, 0] + (y - pts[k, 1]) * u[k, 1], 0, Ls[k])
        rx = x - pts[k, 0] - t * u[k, 0]; ry = y - pts[k, 1] - t * u[k, 1]
        dd = np.hypot(rx, ry); b = dd < best
        best[b] = dd[b]; sgn[b] = np.sign(u[k, 0] * ry[b] - u[k, 1] * rx[b])
    return best * sgn


def run_exid():
    meta = LX.recordings('exiD')
    S, E = [], []
    for _, m in meta.iterrows():
        rec, site = int(m.rec), int(m.site)
        ll = LX.lanelets('exiD', site)
        chains, adj = accel_lane_chains(ll)
        marks = chain_marks(ll, chains)
        d = LX.tracks('exiD', rec)
        cls = LX.tracks_meta('exiD', rec).set_index('trackId')['class']
        d['cls'] = cls.reindex(d.id).values
        fr = d.frame.to_numpy(); look = Look(fr, d.id.to_numpy())
        v = np.hypot(d.vx, d.vy).to_numpy(); L = d.length.to_numpy(); W = d.width.to_numpy()
        lane = d.laneletId.to_numpy(); lc = d.laneChange.to_numpy() == 1
        on = np.isin(lane, list(adj))
        cid = np.full(len(d), -1); rem = np.full(len(d), np.nan)
        for c_i, c in enumerate(chains):
            mm = np.isin(lane, list(c['lanelets']))
            sp, _ = project_many(c['centre'], d.xc.to_numpy()[mm], d.yc.to_numpy()[mm])
            cid[mm] = c_i; rem[mm] = c['length'] - sp
        ids, st, en = LX.by_track(d)
        rows = []
        for tid, a, b in zip(ids, st, en):
            if not on[a:b].any() or b - a < 3 * 25:
                continue
            k_m = None
            for k in np.flatnonzero(lc[a:b]):
                if k >= 1 and on[a + k - 1] and lane[a + k] in ll and ll[lane[a + k]]['tags'].get('onramp') != 'yes':
                    k_m = k; break
            if k_m is not None:
                y_lat = signed_lateral(marks[cid[a + k_m - 1]], d.xc.to_numpy()[a:b], d.yc.to_numpy()[a:b])
            ev = None
            if k_m is not None:
                lw = d.laneWidth.to_numpy()
                ev = lateral_event(y_lat, k_m, 25, W[a], fixed=(-0.5 * lw[a + k_m - 1], 0.5 * lw[a + k_m]))
            if ev is None:
                # The cohort is cars that merge in view: an ending lane makes every car seen to its end merge, while a
                # car that never merges may be on a lane that goes on, or one whose start cannot be read.
                continue
            stop = ev[0]
            if ev:
                st0, e0, si, so = ev
                i0 = a + st0
                E.append(dict(ds='exiD', rec=rec, site=site, id=int(tid), cls=d.cls.iat[a], side='L', i_start=i0, i_cross=a + k_m,
                              t_cross=(k_m - st0) / 25, t_end=(e0 - k_m) / 25, dur_10_90=(e0 - st0) / 25,
                              straddle=(so - si) / 25 if si is not None and so is not None else np.nan,
                              t_body=(si - st0) / 25 if si is not None else np.nan, v=v[i0], rem_start=rem[i0] if on[i0] else np.nan,
                              rem_cross=rem[a + k_m - 1]))
            for r0 in range(0, stop + 1, 25):
                if not on[a + r0] or r0 + 25 > b - a:
                    continue
                y = 'L' if ev and r0 <= ev[0] < r0 + 25 else ''
                if y == '' and ev and r0 + 25 > ev[0]:
                    continue
                rows.append((a + r0, y))
        if not rows:
            continue
        i = np.array([r[0] for r in rows]); y = np.array([r[1] for r in rows])
        hd = np.deg2rad(d.heading.to_numpy()[i]); ux, uy = np.cos(hd), np.sin(hd)
        xc, yc = d.xc.to_numpy(), d.yc.to_numpy()

        def lon_gap(j, ahead):
            jj = np.maximum(j, 0)
            lon = (xc[jj] - xc[i]) * ux + (yc[jj] - yc[i]) * uy
            g = (lon if ahead else -lon) - 0.5 * (L[i] + L[jj])
            return np.where(j >= 0, g, np.nan), np.where(j >= 0, v[jj], np.nan), lon
        out = dict(rec=rec, site=site, id=d.id.to_numpy()[i], cls=d.cls.to_numpy()[i], v=v[i], acc=d.lonAcceleration.to_numpy()[i],
                   rem=rem[i], chain=cid[i], y=y)
        jp = look(fr[i], d.leftLeadId.to_numpy()[i]); jf = look(fr[i], d.leftRearId.to_numpy()[i]); ja = look(fr[i], d.leftAlongsideId.to_numpy()[i])
        lead, lead_v, _ = lon_gap(jp, True); lag, lag_v, _ = lon_gap(jf, False)
        ga, va, lon_a = lon_gap(ja, True)
        al = ja >= 0; ahead = al & (lon_a >= 0)
        lead = np.where(ahead, ga, lead); lead_v = np.where(ahead, va, lead_v)
        gb, vb, _ = lon_gap(ja, False)
        lag = np.where(al & ~ahead, gb, lag); lag_v = np.where(al & ~ahead, vb, lag_v)
        out.update(L_lead=lead, L_lead_v=lead_v, L_lag=lag, L_lag_v=lag_v, lag_id=np.where(jf >= 0, d.id.to_numpy()[np.maximum(jf, 0)], -1))
        S.append(pd.DataFrame(out))
        print('exiD', rec, site, len(i), int((y != '').sum()), flush=True)
    os.makedirs(WORK, exist_ok=True)
    pd.concat(S).to_pickle(f'{WORK}/exiD_states.pkl'); pd.DataFrame(E).to_csv(f'{WORK}/exiD_events.csv', index=False)


def LX_unwrap(off, rows):
    y = off.astype(float).copy()
    for k in rows:
        if 2 <= k < len(y):
            jump = y[k] - y[k - 1]
            if abs(jump) > 1.5:
                y[k:] -= jump - (y[k - 1] - y[k - 2])
    return y


# ---------------------------------------------------------------- DLR HT

def run_dlrht():
    S, E = [], []
    for k in range(24):  # 06:00-14:00 UTC; 14:00-16:00 held out
        p = f'/home/erikf/projects/personal/cars-data/measure/dlrht/b{k:02d}.npz'
        z = np.load(p); d = pd.DataFrame({c: z[c] for c in z.files})
        d = d.sort_values(['id', 'ti']).reset_index(drop=True)
        # Left is the faster lane, per direction.
        sgn = {}
        for dr in (-1, 1):
            g = d[d.dir == dr].groupby('lane').v.mean()
            g = g[d[d.dir == dr].lane.value_counts().reindex(g.index) > 1000]
            sgn[dr] = 1 if g.idxmax() > g.idxmin() else -1
        d['lat'] = d.dd * d.dir.map(sgn)
        d['rk'] = d.lane * d.dir.map(sgn)
        lanes_ok = {dr: sorted(set((d[d.dir == dr].lane.value_counts() > 1000).pipe(lambda s: s[s].index))) for dr in (-1, 1)}
        lo = {dr: min(l * sgn[dr] for l in lanes_ok[dr]) for dr in (-1, 1)}; hi = {dr: max(l * sgn[dr] for l in lanes_ok[dr]) for dr in (-1, 1)}
        # Sorted index for neighbour search at one time: (ti, dir, rank, s).
        key = ((d.ti.to_numpy().astype(np.float64) * 3 + d.dir.to_numpy() + 1) * 64 + d.rk.to_numpy() + 32) * 1e5 + d.s.to_numpy()
        o = np.argsort(key); ks = key[o]
        s = d.s.to_numpy(); L = d.L.to_numpy(); v = d.v.to_numpy(); lat = d.lat.to_numpy(); rk = d.rk.to_numpy()
        ids, st, en = LX.by_track(d)
        rows = []
        for tid, a, b in zip(ids, st, en):
            if b - a < 15 or d.tr.iat[a]:
                continue
            ch = np.flatnonzero(rk[a + 1:b] != rk[a:b - 1]) + 1
            busy = np.zeros(b - a, bool); starts = {}
            for kk in ch:
                if abs(rk[a + kk] - rk[a + kk - 1]) != 1:
                    busy[:] = True; break
                ev = lateral_event(lat[a:b], kk, 5, 1.8)
                side = 'L' if rk[a + kk] > rk[a + kk - 1] else 'R'
                if ev is None:
                    busy[max(0, kk - 30):kk + 30] = True; continue
                st0, e0, si, so = ev
                busy[st0 + 1:e0 + 1] = True; starts[st0] = side
                E.append(dict(ds='dlrht', rec=k, site=0, id=int(tid), cls='car', side=side, t_cross=(kk - st0) / 5, t_end=(e0 - kk) / 5,
                              dur_10_90=(e0 - st0) / 5, straddle=(so - si) / 5 if si is not None and so is not None else np.nan,
                              t_body=(si - st0) / 5 if si is not None else np.nan, v=v[a + st0]))
            for r0 in range(0, b - a - 5, 5):
                if busy[r0] or (busy[r0:r0 + 5].any() and not any(r0 <= x < r0 + 5 for x in starts)):
                    continue
                rows.append((a + r0, next((starts[x] for x in starts if r0 <= x < r0 + 5), '')))
        i = np.array([r[0] for r in rows]); y = np.array([r[1] for r in rows])
        dr = d.dir.to_numpy()[i]
        out = dict(rec=k, site=0, id=d.id.to_numpy()[i], cls=np.where(d.tr.to_numpy()[i] > 0, 'truck', 'car'), v=v[i], acc=np.nan, y=y,
                   rank=rk[i] - np.array([lo[x] for x in dr]), nl=np.array([hi[x] - lo[x] + 1 for x in dr]))
        has = d.lid.to_numpy()[i] >= 0
        out['own_gap'] = np.where(has, d.cc.to_numpy()[i] - 0.5 * (L[i] + d.Ll.to_numpy()[i]), np.nan); out['own_v'] = np.where(has, d.vl.to_numpy()[i], np.nan)
        for side, dk in (('L', 1), ('R', -1)):
            q = ((d.ti.to_numpy()[i].astype(np.float64) * 3 + dr + 1) * 64 + rk[i] + dk + 32) * 1e5
            j = np.searchsorted(ks, q + s[i])
            jl = o[np.minimum(j, len(o) - 1)]; okl = (j < len(o)) & (ks[np.minimum(j, len(o) - 1)] < q + 1e5 - 1) & (ks[np.minimum(j, len(o) - 1)] >= q)
            jf = o[np.maximum(j - 1, 0)]; okf = (j > 0) & (ks[np.maximum(j - 1, 0)] >= q)
            out[f'{side}_ex'] = (rk[i] + dk >= np.array([lo[x] for x in dr])) & (rk[i] + dk <= np.array([hi[x] for x in dr]))
            out[f'{side}_lead'] = np.where(okl, s[jl] - s[i] - 0.5 * (L[i] + L[jl]), np.nan); out[f'{side}_lead_v'] = np.where(okl, v[jl], np.nan)
            out[f'{side}_lag'] = np.where(okf, s[i] - s[jf] - 0.5 * (L[i] + L[jf]), np.nan); out[f'{side}_lag_v'] = np.where(okf, v[jf], np.nan)
        S.append(pd.DataFrame(out))
        print('dlrht', k, len(i), int((y != '').sum()), sgn, flush=True)
    pd.concat(S).to_pickle(f'{WORK}/dlrht_states.pkl'); pd.DataFrame(E).to_csv(f'{WORK}/dlrht_events.csv', index=False)


# ---------------------------------------------------------------- fits

def tgap(g, vv):
    return g / np.maximum(vv, 1.0)


def accept_logp(t, close, m0, m1, sd):
    """log P(gap accepted): lognormal critical time gap; no car (nan) accepts; a non-positive gap refuses."""
    mu = m0 + m1 * np.maximum(close, 0.0)
    lp = log_ndtr((np.log(np.maximum(t, 1e-6)) - mu) / sd)
    lp = np.where(t > 0, lp, np.log(1e-9))
    return np.where(np.isnan(t), 0.0, lp)


def ramp_arrays(S):
    tl = tgap(S.L_lag.to_numpy(), S.L_lag_v.to_numpy()); cl = (S.L_lag_v - S.v).to_numpy()
    td = tgap(S.L_lead.to_numpy(), S.v.to_numpy()); cd = (S.v - S.L_lead_v).to_numpy()
    tte = np.minimum(S.rem.to_numpy() / np.maximum(S.v.to_numpy(), 1.0), 60.0)
    return tl, cl, td, cd, tte, (S.y == 'L').to_numpy().astype(float)


def nll_ramp(p, tl, cl, td, cd, X, y, form='time'):
    a0, aT = p[0], p[1]
    lp = accept_logp(tl, cl, p[2], p[3], np.exp(p[4])) + accept_logp(td, cd, p[5], p[6], np.exp(p[7]))
    ld = -np.logaddexp(0, -(a0 + aT * X / 10))
    lh = np.clip(ld + lp, -50, -1e-12)
    return -np.sum(y * lh + (1 - y) * np.log1p(-np.exp(lh)))


P0 = np.array([-1.0, -1.0, 0.0, 0.1, np.log(0.6), -0.3, 0.1, np.log(0.6)])
NAMES_RAMP = ['a0', 'aT_per10s', 'lag_mu0', 'lag_mu_per_ms_closing', 'lag_log_sd', 'lead_mu0', 'lead_mu_per_ms_closing', 'lead_log_sd']


def fit_ramp(S, form='time'):
    tl, cl, td, cd, tte, y = ramp_arrays(S)
    X = tte if form == 'time' else np.minimum(S.rem.to_numpy(), 600.0) / 25.0
    r = minimize(nll_ramp, P0, args=(tl, cl, td, cd, X, y), method='L-BFGS-B')
    return r.x, r.fun


def desire_X(S, side):
    v = S.v.to_numpy()
    og = S.own_gap.to_numpy(); ov = S.own_v.to_numpy()
    otg = np.where(np.isnan(og), 4.0, np.clip(og / np.maximum(v, 1.0), 0, 4))
    odef = np.where(otg < 4, np.clip(v - ov, 0, 10), 0.0); odef = np.nan_to_num(odef)
    lg = S[f'{side}_lead'].to_numpy(); lv = S[f'{side}_lead_v'].to_numpy()
    ltg = np.where(np.isnan(lg), 4.0, np.clip(lg / np.maximum(v, 1.0), -1, 4))
    tdef = np.nan_to_num(np.where(ltg < 4, np.clip(v - lv, 0, 10), 0.0))
    tgain = np.nan_to_num(np.where(ltg < 4, np.clip(lv - v, 0, 10), 0.0))
    return np.c_[np.ones(len(v)), odef, otg, tdef, tgain, v / 10.0]


NAMES_DES = ['b0', 'own_deficit_per_ms', 'own_time_gap_per_s', 'target_leader_deficit_per_ms', 'target_leader_faster_per_ms', 'speed_per_10ms']


def nll_des(b, X, lp, y, w):
    lh = np.clip(-np.logaddexp(0, -(X @ b)) + lp, -50, -1e-12)
    return -np.sum(w * (y * lh + (1 - y) * np.log1p(-np.exp(lh))))


def side_arrays(S, side, acc):
    S = S[S[f'{side}_ex'].astype(bool)]
    tl = tgap(S[f'{side}_lag'].to_numpy(), S[f'{side}_lag_v'].to_numpy()); cl = (S[f'{side}_lag_v'] - S.v).to_numpy()
    td = tgap(S[f'{side}_lead'].to_numpy(), S.v.to_numpy()); cd = (S.v - S[f'{side}_lead_v']).to_numpy()
    lp = accept_logp(tl, cl, acc[2], acc[3], np.exp(acc[4])) + accept_logp(td, cd, acc[5], acc[6], np.exp(acc[7]))
    return S, desire_X(S, side), lp, (S.y == side).to_numpy().astype(float), tl, td


def fit_des(X, lp, y, w):
    b0 = np.zeros(X.shape[1]); b0[0] = np.log(max(np.sum(w * y) / np.sum(w), 1e-5))
    r = minimize(nll_des, b0, args=(X, lp, y, w), method='L-BFGS-B')
    return r.x, r.fun


def boot(groups, fn, reps):
    u = np.unique(groups); idx = {g: np.flatnonzero(groups == g) for g in u}
    out = []
    for _ in range(reps):
        pick = rng.choice(u, len(u))
        out.append(fn(np.concatenate([idx[g] for g in pick])))
    return np.array(out)


def ci(arr):
    return [[round(float(x), 4) for x in np.percentile(arr[:, k], [2.5, 97.5])] for k in range(arr.shape[1])]


def wq(x, w, ps):
    o = np.argsort(x); x = x[o]; w = w[o]; c = np.cumsum(w) / w.sum()
    return [round(float(np.interp(p / 100, c, x)), 3) for p in ps]


def q(v, ps=(5, 25, 50, 75, 95)):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    return {f'p{p}': round(float(np.percentile(v, p)), 3) for p in ps} | {'n': int(len(v))} if len(v) else {'n': 0}


def fit_all():
    res = {}
    R = pd.read_pickle(f'{WORK}/exiD_states.pkl'); R = R[R.cls.isin(['car', 'van'])].reset_index(drop=True)
    R['g'] = R.rec.astype(str) + '_' + R.id.astype(str)
    p, f = fit_ramp(R)
    tl, cl, td, cd, tte, y = ramp_arrays(R)
    B = boot(R.g.to_numpy(), lambda ix: fit_ramp(R.iloc[ix])[0], 100)
    res['ramp'] = dict(n_seconds=len(R), n_starts=int(y.sum()), n_cars=int(R.g.nunique()), params=dict(zip(NAMES_RAMP, [round(float(x), 4) for x in p])),
                       ci95=dict(zip(NAMES_RAMP, ci(B))), nll=round(float(f), 1),
                       critical_lag_median_s=round(float(np.exp(p[2])), 3), critical_lag_log_sd=round(float(np.exp(p[4])), 3),
                       critical_lead_median_s=round(float(np.exp(p[5])), 3), critical_lead_log_sd=round(float(np.exp(p[7])), 3),
                       critical_lag_median_ci=[round(float(np.exp(x)), 3) for x in np.percentile(B[:, 2], [2.5, 97.5])],
                       critical_lead_median_ci=[round(float(np.exp(x)), 3) for x in np.percentile(B[:, 5], [2.5, 97.5])],
                       log_sd_ci=[[round(float(np.exp(x)), 3) for x in np.percentile(B[:, k], [2.5, 97.5])] for k in (4, 7)])
    # Leave one site out: time against distance.
    loso = {}
    for site in sorted(R.site.unique()):
        tr, te = R[R.site != site], R[R.site == site]
        row = {}
        for form in ('time', 'distance'):
            pp, _ = fit_ramp(tr, form)
            a = ramp_arrays(te); X = a[4] if form == 'time' else np.minimum(te.rem.to_numpy(), 600.0) / 25.0
            row[form] = round(float(-nll_ramp(pp, a[0], a[1], a[2], a[3], X, a[5]) / te.g.nunique()), 4)
            if form == 'time':
                row['aT'] = round(float(pp[1]), 3)
        loso[int(site)] = row
    res['ramp']['leave_one_site_out_loglik_per_car'] = loso
    res['ramp']['by_site_aT'] = {int(s): round(float(fit_ramp(R[R.site == s])[0][1]), 3) for s in sorted(R.site.unique())}
    # Fit check: predicted against observed accepted gaps and starts by time to the end.
    ph = expit(p[0] + p[1] * tte / 10) * np.exp(accept_logp(tl, cl, p[2], p[3], np.exp(p[4])) + accept_logp(td, cd, p[5], p[6], np.exp(p[7])))
    ok = np.isfinite(tl) & (tl > 0)
    res['ramp']['accepted_lag_s_observed_vs_model'] = [wq(tl[ok & (y > 0)], np.ones((ok & (y > 0)).sum()), (5, 25, 50)), wq(tl[ok], ph[ok], (5, 25, 50))]
    ok = np.isfinite(td) & (td > 0)
    res['ramp']['accepted_lead_s_observed_vs_model'] = [wq(td[ok & (y > 0)], np.ones((ok & (y > 0)).sum()), (5, 25, 50)), wq(td[ok], ph[ok], (5, 25, 50))]
    bins = [0, 3, 6, 10, 15, 25, 60.1]
    res['ramp']['starts_per_s_by_tte_observed_vs_model'] = {f'{lo}-{hi}': [round(float(y[(tte >= lo) & (tte < hi)].mean()), 4), round(float(ph[(tte >= lo) & (tte < hi)].mean()), 4), int(((tte >= lo) & (tte < hi)).sum())]
                                                         for lo, hi in zip(bins[:-1], bins[1:])}
    res['ramp']['offered_refused_lag_s'] = q(tl[(y == 0) & np.isfinite(tl)], (5, 25, 50))
    # The exiD fit above is degenerate (LANECHANGE.md): discretionary desire uses the acceptance frozen from the I-80 and
    # US-101 must-change cohorts (world.rs LCM_*).
    acc = np.array([-0.825, -1.119, -0.908, 0.551, np.log(1.676), -2.004, 0.453, np.log(1.374)])
    # Discretionary: highD fit, DLR HT check.
    for ds in ('highD', 'dlrht'):
        H = pd.read_pickle(f'{WORK}/{ds}_states.pkl')
        H = H[H.cls.isin(['Car', 'car'])].reset_index(drop=True)
        H['g'] = H.rec.astype(str) + '_' + H.id.astype(str)
        r = dict(n_seconds=len(H), starts=dict(L=int((H.y == 'L').sum()), R=int((H.y == 'R').sum())))
        # Rates use every second; the fits keep every start and a fifth of the other seconds, weighted 5 (case-control).
        dist = H.v.to_numpy() * 1.0
        rates = {}
        for lo, hi in ((0, 15), (15, 25), (25, 35), (35, 60)):
            mm = (H.v >= lo) & (H.v < hi)
            rates[f'{lo}-{hi}'] = dict(per_vkm=round(float((H.y[mm] != '').sum() / max(dist[mm].sum() / 1000, 1e-9)), 3), km=round(float(dist[mm].sum() / 1000), 1))
        r['rate_per_vehicle_km'] = rates
        r['rate_all'] = round(float((H.y != '').sum() / (dist.sum() / 1000)), 3)
        keep = (H.y != '').to_numpy() | (rng.random(len(H)) < 0.2)
        H = H[keep].reset_index(drop=True); H['w'] = np.where(H.y != '', 1.0, 5.0)
        for side in ('L', 'R'):
            Ss, X, lp, ys, tl, td = side_arrays(H, side, acc)
            ww = Ss.w.to_numpy()
            b, f = fit_des(X, lp, ys, ww)
            Bd = boot(Ss.g.to_numpy(), lambda ix: fit_des(X[ix], lp[ix], ys[ix], ww[ix])[0], 10)
            pr = expit(X @ b) * np.exp(lp) * ww
            chk = {}
            for nm, t in (('lag', tl), ('lead', td)):
                ok = np.isfinite(t) & (t > 0)
                chk[nm] = dict(observed=wq(t[ok & (ys > 0)], np.ones((ok & (ys > 0)).sum()), (5, 50)), model_exiD_acceptance=wq(t[ok], pr[ok], (5, 50)))
            # The same desire with acceptance off: what the gaps would be with no acceptance at all.
            pr0 = expit(X @ b) * ww
            for nm, t in (('lag', tl), ('lead', td)):
                ok = np.isfinite(t) & (t > 0)
                chk[nm]['offered_weighted_by_desire_only'] = wq(t[ok], pr0[ok], (5, 50))
            r[side] = dict(n=int(ys.sum()), params=dict(zip(NAMES_DES, [round(float(x), 4) for x in b])), ci95=dict(zip(NAMES_DES, ci(Bd))),
                           gap_check=chk, by_site={int(s): dict(zip(NAMES_DES, [round(float(x), 3) for x in fit_des(X[(Ss.site == s).to_numpy()], lp[(Ss.site == s).to_numpy()], ys[(Ss.site == s).to_numpy()], ww[(Ss.site == s).to_numpy()])[0]]))
                                                   for s in sorted(Ss.site.unique()) if ys[(Ss.site == s).to_numpy()].sum() > 50})
        res[ds] = r
    # Lateral motion and the follower before the start.
    lat = {}
    for ds in ('exiD', 'highD', 'dlrht'):
        Ev = pd.read_csv(f'{WORK}/{ds}_events.csv')
        Ev = Ev[Ev.cls.isin(['car', 'van', 'Car'])]
        g = Ev[(Ev.v >= 20) & (Ev.v < 30)]
        lat[ds] = dict(n=len(Ev), start_to_cross_s=q(g.t_cross), start_to_body_s=q(g.t_body), straddle_s=q(g.straddle), dur_10_90_s=q(g.dur_10_90),
                       straddle_by_speed={f'{lo}-{hi}': q(Ev.straddle[(Ev.v >= lo) & (Ev.v < hi)], (25, 50, 75)) for lo, hi in ((5, 15), (15, 20), (20, 25), (25, 30), (30, 45))})
        if ds == 'exiD':
            lat[ds]['merge_metres_left_at_start'] = q(Ev.rem_start, (10, 25, 50, 75, 90)); lat[ds]['merge_metres_left_at_crossing'] = q(Ev.rem_cross, (10, 50, 90))
    res['lateral'] = lat
    json.dump(res, open(os.path.join(RES, 'lc_decision.json'), 'w'), indent=1)
    print(json.dumps(res, indent=1)[:12000])


def follower_before_start():
    """F707: the new follower's mean acceleration over the 3 s before the START, against speed-matched followers with no
    merger (lanechange.py's baseline windows)."""
    Ev = pd.read_csv(f'{WORK}/exiD_events.csv'); Ev = Ev[Ev.cls.isin(['car', 'van'])]
    Bl = pd.read_csv('/home/erikf/projects/personal/cars-data/measure/lanechange/exiD_baseline.csv')
    Bl['vb'] = (Bl.v // 2).astype(int); mu = Bl.groupby('vb').acc3.mean()
    zs, zb = [], (Bl.acc3 - mu.reindex(Bl.vb).to_numpy()).dropna().to_numpy()
    for rec, g in Ev.groupby('rec'):
        d = LX.tracks('exiD', int(rec)); look = Look(d.frame.to_numpy(), d.id.to_numpy())
        acc = d.lonAcceleration.to_numpy(); v = np.hypot(d.vx, d.vy).to_numpy(); rear = d.leftRearId.to_numpy()
        for e in g.itertuples():
            fid = rear[e.i_start]
            if not np.isfinite(fid) or fid <= 0:
                continue
            fr0 = d.frame.iat[e.i_start]
            js = look(np.arange(fr0 - 75, fr0), np.full(75, fid)); js = js[js >= 0]
            if len(js) < 50:
                continue
            zs.append(float(acc[js].mean() - mu.get(int(v[js[-1]] // 2), np.nan)))
    zs = np.array([z for z in zs if np.isfinite(z)])
    bs = [float((zs[rng.integers(0, len(zs), len(zs))] <= -0.3).mean()) for _ in range(400)]
    return dict(n=len(zs), share_slowing_0_3=round(float((zs <= -0.3).mean()), 4), ci=[round(float(x), 4) for x in np.percentile(bs, [2.5, 97.5])],
                baseline_share=round(float((zb <= -0.3).mean()), 4), mean_relative_acc=round(float(zs.mean()), 3))


if __name__ == '__main__':
    if sys.argv[1] == 'follow':
        r = follower_before_start(); print(r)
        p = os.path.join(RES, 'lc_decision.json'); res = json.load(open(p)) if os.path.exists(p) else {}
        res['follower_before_start'] = r; json.dump(res, open(p, 'w'), indent=1)
    else:
        {'highD': run_highd, 'exiD': run_exid, 'dlrht': run_dlrht, 'fit': fit_all}[sys.argv[1]]()
