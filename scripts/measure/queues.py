"""Round 2 of the measured driver, part 3: low speed and standstill, on recordings not held out (HOLDOUT.md).
Forecasts F609-F614.

Recordings: rounD and inD (levelX cache, locations and days not held out), SinD Tianjin, Chongqing, Changchun (Xi'an held
out), NGSIM Lankershim (2005; positions only, the signal archive on disk holds only aerial photos), TGSIM I-90/94
stationary (follower table of follow.py; centre spacing minus 5 m, lengths are defaults).

Who follows whom: in each frame, the nearest car ahead whose centre lies within 1.5 m of the follower's heading line,
heading within 35 degrees, bumper gap under 40 m (2D sets); NGSIM's own preceding id (Lankershim); the table's leader
(TGSIM). At 5 Hz (levelX, TGSIM) or 10 Hz (SinD, Lankershim). Speeds from a 1 s local quadratic of the arc length.

Per stop of a follower behind a standing leader (both under 0.3 m/s):
  stand gap       median bumper gap over the stop (F609)
  creep           the follower moves 0.5 m or more while its leader still stands (leader moves under 0.3 m), counted on
                  stops where the leader stands 8 s or more after the follower first stops (F610)
Per start, the leader passes 1 m/s while the follower stands behind it:
  start delay     follower passes 1 m/s minus leader passes 1 m/s (F612), by queue position (1 + the standing leader's)
  launch          follower's peak acceleration within 10 s, its bumper gap when it passes 5 and 8 m/s (F614)
  stop-line headway   front crossings of the line through the queue head's standing front, consecutive cars of one
                  queue, by position (F613)
Low speed (F611): bumper gap of quasi-steady followers (|dv| under 0.5 m/s) by speed.

    python3 -I scripts/measure/queues.py run [rounD inD sind lankershim tgsim]   # -> research/truth/measure/queues.json
"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.signal import savgol_filter

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from holdout import HOLD

RES = os.path.join(HERE, '..', '..', 'research', 'truth', 'measure')
OUT = os.path.join(RES, 'queues.json')
WORK = '/home/erikf/projects/personal/cars-data/measure/queues'
rng = np.random.default_rng(20261109)
FT = 0.3048
VSTAND, VGO = 0.3, 1.0


def smooth_speed(s, ids, hz):
    """Speed and acceleration from a 1 s local quadratic of arc length, per track."""
    w = int(hz) | 1
    v = np.full(len(s), np.nan); a = np.full(len(s), np.nan)
    cut = np.flatnonzero(np.diff(ids)) + 1
    for b, e in zip(np.r_[0, cut], np.r_[cut, len(s)]):
        if e - b >= w + 2:
            v[b:e] = savgol_filter(s[b:e], w, 2, deriv=1, delta=1.0 / hz)
            a[b:e] = savgol_filter(s[b:e], w + 2 * (w // 2) if e - b > 2 * w else w, 2, deriv=2, delta=1.0 / hz)
    return np.maximum(v, 0), a


def arc(x, y, ids):
    d = np.r_[0, np.hypot(np.diff(x), np.diff(y))]
    d[np.r_[True, ids[1:] != ids[:-1]]] = 0
    # Jitter at standstill adds up to arc length; drop steps under 1 cm per sample.
    d[d < 0.01] = 0
    s = np.cumsum(d)
    first = np.r_[0, np.flatnonzero(np.diff(ids)) + 1]
    return s - np.repeat(s[first], np.diff(np.r_[first, len(ids)]))


# ---------------------------------------------------------------- loaders: one frame table per recording
def frames_levelx(ds, rec):
    import levelx as LX
    d = LX.tracks(ds, rec)
    cls = LX.tracks_meta(ds, rec).set_index('trackId' if 'trackId' in LX.tracks_meta(ds, rec) else 'id')['class']
    d = d[d.frame % 5 == 0].copy()
    d['cls'] = cls.reindex(d.id).values
    d = d[d.cls.isin(['car', 'van', 'truck', 'bus', 'truck_bus'])].sort_values(['id', 'frame']).reset_index(drop=True)
    h = np.deg2rad(d.heading.to_numpy(float))
    return pd.DataFrame(dict(id=d.id.to_numpy(), t=d.frame.to_numpy() / 25.0, x=d.xc.to_numpy(float), y=d.yc.to_numpy(float),
                             hx=np.cos(h), hy=np.sin(h), L=d.length.to_numpy(float), car=d.cls.isin(['car', 'van']).to_numpy())), 5


def frames_sind(path):
    D = '/home/erikf/projects/personal/cars-data/datasets/jt25-sind/'
    t = pd.read_csv(D + path, usecols=['track_id', 'timestamp_ms', 'agent_type', 'x', 'y', 'yaw_rad', 'length'])
    t = t[t.agent_type.isin({'car', 'truck', 'bus'})].sort_values(['track_id', 'timestamp_ms']).reset_index(drop=True)
    return pd.DataFrame(dict(id=t.track_id.to_numpy(), t=np.round(t.timestamp_ms.to_numpy() / 100.0) / 10.0, x=t.x.to_numpy(float),
                             y=t.y.to_numpy(float), hx=np.cos(t.yaw_rad.to_numpy(float)), hy=np.sin(t.yaw_rad.to_numpy(float)),
                             L=t.length.to_numpy(float), car=(t.agent_type == 'car').to_numpy())), 10


def frames_lankershim():
    p = '/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-ngsim/lankershim.csv'
    d = pd.read_csv(p, usecols=['vehicle_id', 'frame_id', 'local_x', 'local_y', 'v_length', 'v_class', 'preceding', 'lane_id', 'int_id', 'direction'])
    d = d.drop_duplicates(['vehicle_id', 'frame_id']).sort_values(['vehicle_id', 'frame_id']).reset_index(drop=True)
    ids = d.vehicle_id.to_numpy()
    x = d.local_x.to_numpy(float) * FT; y = d.local_y.to_numpy(float) * FT
    # Positions jitter; smooth 1 s before taking heading.
    xs = x.copy(); ys = y.copy()
    cut = np.flatnonzero(np.diff(ids)) + 1
    for b, e in zip(np.r_[0, cut], np.r_[cut, len(ids)]):
        if e - b >= 13:
            xs[b:e] = savgol_filter(x[b:e], 11, 2); ys[b:e] = savgol_filter(y[b:e], 11, 2)
    hx = np.gradient(xs); hy = np.gradient(ys)
    n = np.hypot(hx, hy); bad = n < 1e-3
    # Heading at standstill: the direction of travel of that track overall.
    for b, e in zip(np.r_[0, cut], np.r_[cut, len(ids)]):
        tx, ty = xs[e - 1] - xs[b], ys[e - 1] - ys[b]; tn = max(np.hypot(tx, ty), 1e-6)
        hx[b:e][bad[b:e]] = tx / tn; hy[b:e][bad[b:e]] = ty / tn
    n = np.hypot(hx, hy)
    return pd.DataFrame(dict(id=ids, t=d.frame_id.to_numpy() / 10.0, x=xs, y=ys, hx=hx / n, hy=hy / n, L=d.v_length.to_numpy(float) * FT,
                             car=(d.v_class == 2).to_numpy(), lead=d.preceding.to_numpy(), lane=d.lane_id.to_numpy(), dirn=d.direction.to_numpy())), 10


# ---------------------------------------------------------------- leader finder and per-frame state
def leaders(f):
    """Leader id and bumper gap per row: nearest car ahead on the follower's heading line."""
    lid = np.full(len(f), -1, np.int64); gap = np.full(len(f), np.nan)
    if 'lead' in f:
        # NGSIM: the provided preceding vehicle, gap along the follower's heading.
        key = pd.MultiIndex.from_arrays([f.t.round(1), f.id])
        look = pd.Series(np.arange(len(f)), index=key)
        j = look.reindex(pd.MultiIndex.from_arrays([f.t.round(1), f.lead])).to_numpy()
        ok = np.isfinite(j) & (f.lead.to_numpy() > 0)
        jj = j[ok].astype(int); ii = np.flatnonzero(ok)
        along = (f.x.to_numpy()[jj] - f.x.to_numpy()[ii]) * f.hx.to_numpy()[ii] + (f.y.to_numpy()[jj] - f.y.to_numpy()[ii]) * f.hy.to_numpy()[ii]
        g = along - (f.L.to_numpy()[ii] + f.L.to_numpy()[jj]) / 2
        good = (g > -1) & (g < 40)
        lid[ii[good]] = f.id.to_numpy()[jj[good]]; gap[ii[good]] = g[good]
        return lid, gap
    order = np.argsort(f.t.to_numpy(), kind='stable')
    t = f.t.to_numpy()[order]
    cut = np.flatnonzero(np.diff(t) > 1e-6) + 1
    X, Y, HX, HY, L, ID = (f[c].to_numpy()[order] for c in ('x', 'y', 'hx', 'hy', 'L', 'id'))
    for b, e in zip(np.r_[0, cut], np.r_[cut, len(t)]):
        if e - b < 2:
            continue
        dx = X[None, b:e] - X[b:e, None]; dy = Y[None, b:e] - Y[b:e, None]
        al = dx * HX[b:e, None] + dy * HY[b:e, None]
        la = -dx * HY[b:e, None] + dy * HX[b:e, None]
        cosd = HX[b:e, None] * HX[None, b:e] + HY[b:e, None] * HY[None, b:e]
        g = al - (L[b:e, None] + L[None, b:e]) / 2
        ok = (al > 0) & (np.abs(la) < 1.5) & (cosd > np.cos(np.deg2rad(35))) & (g > -1) & (g < 40)
        al = np.where(ok, al, np.inf)
        k = np.argmin(al, axis=1); has = np.isfinite(al[np.arange(e - b), k])
        rows = order[b:e][has]
        lid[rows] = ID[b:e][k[has]]; gap[rows] = g[np.arange(e - b)[has], k[has]]
    return lid, gap


def enrich(f, hz):
    f = f.sort_values(['id', 't']).reset_index(drop=True)
    ids = f.id.to_numpy()
    s = arc(f.x.to_numpy(), f.y.to_numpy(), ids)
    v, a = smooth_speed(s, ids, hz)
    f['s'], f['v'], f['a'] = s, v, a
    lid, gap = leaders(f)
    f['lid'], f['gap'] = lid, gap
    key = pd.MultiIndex.from_arrays([f.t.round(2), f.id])
    look = pd.Series(np.arange(len(f)), index=key)
    j = look.reindex(pd.MultiIndex.from_arrays([f.t.round(2), f.lid])).to_numpy()
    f['li'] = np.where(np.isfinite(j), j, -1).astype(int)
    li = f.li.to_numpy()
    f['vl'] = np.where(li >= 0, v[np.maximum(li, 0)], np.nan)
    f['lcar'] = np.where(li >= 0, f.car.to_numpy()[np.maximum(li, 0)], False)
    # Queue position and head while standing: 1 + the standing leader's position if it stands within 12 m.
    stand = v < VSTAND
    sl = (li >= 0) & stand & (np.where(li >= 0, stand[np.maximum(li, 0)], False)) & (gap < 12)
    pos = np.where(stand, 1, 0); head = np.where(stand, np.arange(len(f)), -1)
    for _ in range(30):
        npos = np.where(sl, pos[np.maximum(li, 0)] + 1, pos)
        nhead = np.where(sl, head[np.maximum(li, 0)], head)
        if (npos == pos).all() and (nhead == head).all():
            break
        pos, head = npos, nhead
    f['pos'], f['qhead'] = pos, head
    return f


# ---------------------------------------------------------------- events
def events(f, hz, ds):
    ids = f.id.to_numpy(); t = f.t.to_numpy(); v = f.v.to_numpy(); s = f.s.to_numpy(); a = f.a.to_numpy()
    lid = f.lid.to_numpy(); li = f.li.to_numpy(); gap = f.gap.to_numpy(); vl = f.vl.to_numpy()
    x, y, L = f.x.to_numpy(), f.y.to_numpy(), f.L.to_numpy()
    car = f.car.to_numpy(); lcar = f.lcar.to_numpy(); pos = f.pos.to_numpy(); head = f.qhead.to_numpy()
    starts = np.r_[0, np.flatnonzero(np.diff(ids)) + 1]; ends = np.r_[starts[1:], len(ids)]
    stops, starts_ev, low = [], [], []
    for b, e in zip(starts, ends):
        if not car[b]:
            continue
        st = v[b:e] < VSTAND
        # stop episodes
        edges = np.flatnonzero(np.diff(np.r_[0, st.astype(int), 0]))
        for p, q in zip(edges[::2], edges[1::2]):
            p += b; q += b
            if q - p < hz or lid[p] < 0 or not lcar[p] or li[p] < 0 or vl[p] >= VSTAND or np.isnan(gap[p]):
                continue
            same = lid[p:q] == lid[p]
            # how long the leader keeps standing from the follower's first stop
            j = li[p]; lead_stand = 0; lt = j
            lids = ids[j]
            while lt < len(ids) and ids[lt] == lids and v[lt] < VSTAND:
                lt += 1
            lead_stand = (lt - j) / hz
            g0 = float(np.nanmedian(gap[p:min(p + hz, q)]))
            # over the whole time the leader keeps standing, whatever the follower does (it may creep past 0.3 m/s)
            k_end = min(e, p + int(lead_stand * hz)) - 1
            g1 = gap[k_end] if lid[k_end] == lid[p] else np.nan
            jl = min(j + int(lead_stand * hz) - 1, len(s) - 1)
            lead_moved = s[jl] - s[j] if ids[jl] == lids else np.nan
            moved = s[k_end] - s[p] if lid[k_end] == lid[p] else np.nan
            stops.append((ds, ids[p], lid[p], t[p], (q - p) / hz, lead_stand, g0, float(np.nanmedian(gap[p:q][same])), g1, moved, lead_moved, pos[p], round(t[j] + lead_stand, 1)))
        # starts: the leader passes VGO while this car stands behind it, same leader
        for k in range(b + 1, e):
            if li[k] < 0 or not (v[k] < VSTAND) or not lcar[k]:
                continue
            j = li[k]
            if not (vl[k] >= VGO and j - 1 >= 0 and ids[j - 1] == ids[j] and v[j - 1] < VGO):
                continue
            # follower passes VGO
            m = k
            while m < e and v[m] < VGO and lid[m] == lid[k]:
                m += 1
            if m >= e or v[m] < VGO:
                continue
            delay = t[m] - t[k] + (VGO - v[j - 1]) / max(v[j] - v[j - 1], 1e-6) / hz * 0 - (t[k] - t[k - 1]) * 0
            # sub-sample: interpolate both crossings
            tl = t[j - 1] + (VGO - v[j - 1]) / max(v[j] - v[j - 1], 1e-6) / hz
            tf = t[m - 1] + (VGO - v[m - 1]) / max(v[m] - v[m - 1], 1e-6) / hz
            seg_end = m
            while seg_end < min(e, m + 10 * hz) and lid[seg_end] == lid[k]:
                seg_end += 1
            pk = float(np.nanmax(a[m:min(e, m + 10 * hz)])) if m < e else np.nan
            g5 = g8 = np.nan
            for vv, nm in ((5.0, 'g5'), (8.0, 'g8')):
                w = np.flatnonzero(v[m:seg_end] >= vv)
                if len(w):
                    if nm == 'g5': g5 = gap[m + w[0]]
                    else: g8 = gap[m + w[0]]
            # stop-line headway: crossing of the line through the queue head's standing front, by this car and its leader
            # queue position and head read when the leader last stood (it may already roll at under 1 m/s)
            jj = j
            while jj - 1 >= 0 and ids[jj - 1] == ids[j] and v[jj] >= VSTAND:
                jj -= 1
            kq = max(b, k - (j - jj))
            # the deepest the follower stood in its queue during this stop: the head left first, so read it then
            r0 = kq
            while r0 - 1 >= b and v[r0 - 1] < VSTAND and kq - r0 < 90 * hz and lid[r0 - 1] == lid[k]:
                r0 -= 1
            kq = r0 + int(np.argmax(pos[r0:kq + 1]))
            hd = head[kq] if head[kq] >= 0 and pos[kq] >= 2 else -1
            hw = np.nan
            if hd >= 0:
                ux, uy = f.hx.to_numpy()[hd], f.hy.to_numpy()[hd]
                fx, fy = x[hd] + ux * (L[hd] / 2 + 1.0), y[hd] + uy * (L[hd] / 2 + 1.0)
                def cross(r0, r1, Lr):
                    pr = (x[r0:r1] - fx) * ux + (y[r0:r1] - fy) * uy + Lr / 2
                    w = np.flatnonzero((pr[:-1] < 0) & (pr[1:] >= 0))
                    if not len(w):
                        return np.nan
                    i0 = w[0]
                    return t[r0 + i0] + (0 - pr[i0]) / max(pr[i0 + 1] - pr[i0], 1e-6) / hz
                jb = starts[np.searchsorted(starts, j, 'right') - 1]; je = ends[np.searchsorted(starts, j, 'right') - 1]
                c_l = cross(jb, je, L[j]) if ids[jb] == ids[j] else np.nan
                c_f = cross(b, e, L[k])
                hw = c_f - c_l
            starts_ev.append((ds, ids[k], lid[k], t[k], tf - tl, pos[kq] if pos[kq] > 0 else np.nan, pk, g5, g8, hw, gap[k]))
            break_k = True
        # low-speed quasi-steady following
        m = (lid[b:e] >= 0) & lcar[b:e] & np.isfinite(vl[b:e]) & (np.abs(vl[b:e] - v[b:e]) < 0.5) & (v[b:e] >= 0.5) & (v[b:e] < 12)
        k = np.flatnonzero(m)[:: max(1, hz // 2)] + b
        low += [(ds, ids[i], v[i], gap[i]) for i in k]
    S = pd.DataFrame(stops, columns=['ds', 'id', 'lid', 't', 'dur', 'lead_stand', 'gap_first', 'gap_med', 'gap_before_leader_moves', 'moved', 'lead_moved', 'pos', 'lead_go'])
    # a creeping follower stops again behind the same standing leader: keep its first stop per leader stand
    S = S.sort_values(['id', 't']).drop_duplicates(['id', 'lid', 'lead_go'], keep='first')
    E = pd.DataFrame(starts_ev, columns=['ds', 'id', 'lid', 't', 'delay', 'pos', 'peak_acc', 'gap_5', 'gap_8', 'headway', 'gap_stand'])
    Lw = pd.DataFrame(low, columns=['ds', 'id', 'v', 'gap'])
    # one start per follower stand: the first leader start after it stood
    E = E.sort_values(['id', 't']).drop_duplicates(['id', 'lid'], keep='first')
    return S, E, Lw


def tgsim():
    """TGSIM I-90/94 stationary from follow.py's table: 1D, centre spacing minus 5 m."""
    import follow as F
    d = F.load('I90stat')
    d = d[d.lcar.astype(bool)].reset_index(drop=True)
    hz = 5
    seg = d.seg.to_numpy(); vf = d.vf.to_numpy(float); vl = d.vl.to_numpy(float); gap = d.gap.to_numpy(float); t = d.t.to_numpy(float)
    xf = np.r_[0, np.cumsum(0.5 * (vf[1:] + vf[:-1]) / hz)]
    st = np.r_[0, np.flatnonzero(np.diff(seg)) + 1]; en = np.r_[st[1:], len(seg)]
    xf = xf - np.repeat(xf[st], en - st)
    xl = xf + gap
    stops, starts, low = [], [], []
    for b, e in zip(st, en):
        fst = vf[b:e] < VSTAND
        edges = np.flatnonzero(np.diff(np.r_[0, fst.astype(int), 0]))
        last_go = -1
        for p, q0 in zip(edges[::2], edges[1::2]):
            p += b; q0 += b
            if q0 - p < hz or vl[p] >= VSTAND or p < last_go:
                continue
            go = np.flatnonzero(vl[p:e] >= VSTAND)
            q = p + go[0] if len(go) else e
            last_go = q
            lead_stand = (q - p) / hz
            g0 = float(np.median(gap[p:min(q0, p + hz)])); g1 = gap[q - 1]
            stops.append(('I90stat', d.fid.iat[p], d.lid.iat[p], t[p], (q0 - p) / hz, lead_stand, g0, float(np.median(gap[p:q0])), g1,
                          xf[q - 1] - xf[p], xl[q - 1] - xl[p], np.nan, 0))
            if q >= e or (vf[q - 1] >= VSTAND):
                continue
            # start: the leader passes VGO after q
            jl = np.flatnonzero(vl[q:e] >= VGO)
            jf = np.flatnonzero(vf[q:e] >= VGO)
            if len(jl) and len(jf):
                kl, kf = q + jl[0], q + jf[0]
                tl = t[kl - 1] + (VGO - vl[kl - 1]) / max(vl[kl] - vl[kl - 1], 1e-6) / hz
                tf = t[kf - 1] + (VGO - vf[kf - 1]) / max(vf[kf] - vf[kf - 1], 1e-6) / hz
                # flow out of the jam: headway at the point 50 m beyond where the leader stood (leader front)
                P = xl[q - 1] + 50.0
                il = np.flatnonzero(xl[q:e] >= P); i_f = np.flatnonzero(xf[q:e] + 0 >= P + 5.0 - 0.0 - (gap[q - 1] * 0))
                hw = np.nan
                # here xl - xf is the bumper gap: xl is the leader's rear in the follower-front frame, so both fronts
                # pass P when the leader's rear passes P - 5 and the follower's front passes P
                il = np.flatnonzero(xl[q:e] + 5.0 >= P)
                i_f = np.flatnonzero(xf[q:e] >= P)
                if len(il) and len(i_f):
                    hw = t[q + i_f[0]] - t[q + il[0]]
                a = np.gradient(vf[q:e]) * hz if e - q > 3 else np.array([np.nan])
                pk = float(np.max(a[:10 * hz])) if len(a) else np.nan
                g5 = gap[q + np.flatnonzero(vf[q:e] >= 5)[0]] if (vf[q:e] >= 5).any() else np.nan
                g8 = gap[q + np.flatnonzero(vf[q:e] >= 8)[0]] if (vf[q:e] >= 8).any() else np.nan
                starts.append(('I90stat', d.fid.iat[p], d.lid.iat[p], t[q], tf - tl, np.nan, pk, g5, g8, hw, gap[q - 1]))
        m = (np.abs(vl[b:e] - vf[b:e]) < 0.5) & (vf[b:e] >= 0.5) & (vf[b:e] < 12)
        k = np.flatnonzero(m)[::2] + b
        low += [('I90stat', d.fid.iat[i], vf[i], gap[i]) for i in k]
    S = pd.DataFrame(stops, columns=['ds', 'id', 'lid', 't', 'dur', 'lead_stand', 'gap_first', 'gap_med', 'gap_before_leader_moves', 'moved', 'lead_moved', 'pos', 'lead_go'])
    E = pd.DataFrame(starts, columns=['ds', 'id', 'lid', 't', 'delay', 'pos', 'peak_acc', 'gap_5', 'gap_8', 'headway', 'gap_stand'])
    return S, E, pd.DataFrame(low, columns=['ds', 'id', 'v', 'gap'])


# ---------------------------------------------------------------- run and summarise
def collect(name):
    os.makedirs(WORK, exist_ok=True)
    out = []
    if name in ('rounD', 'inD'):
        import levelx as LX
        for rec in LX.recordings(name).rec:
            f, hz = frames_levelx(name, int(rec))
            out.append(events(enrich(f, hz), hz, f'{name}'))
            print(name, rec, [len(x) for x in out[-1]], flush=True)
    elif name == 'sind':
        import sind as SD
        for city, (tr, _) in SD.REC.items():
            if city in HOLD['sind']:
                continue
            f, hz = frames_sind(tr)
            out.append(events(enrich(f, hz), hz, f'SinD {city}'))
            print(city, [len(x) for x in out[-1]], flush=True)
    elif name == 'lankershim':
        f, hz = frames_lankershim()
        out.append(events(enrich(f, hz), hz, 'Lankershim'))
    elif name == 'tgsim':
        out.append(tgsim())
    S = pd.concat([o[0] for o in out]); E = pd.concat([o[1] for o in out]); Lw = pd.concat([o[2] for o in out])
    S.to_csv(f'{WORK}/{name}_stops.csv', index=False); E.to_csv(f'{WORK}/{name}_starts.csv', index=False); Lw.to_csv(f'{WORK}/{name}_low.csv', index=False)


def med_ci(x, groups, reps=300):
    x = np.asarray(x, float); ok = np.isfinite(x); x = x[ok]; g = np.asarray(groups)[ok]
    if len(x) < 5:
        return None
    u, inv = np.unique(g, return_inverse=True)
    parts = [x[inv == i] for i in range(len(u))]
    b = [np.median(np.concatenate([parts[i] for i in rng.integers(0, len(u), len(u))])) for _ in range(reps)]
    return [round(float(np.median(x)), 2), round(float(np.percentile(b, 2.5)), 2), round(float(np.percentile(b, 97.5)), 2), int(len(x))]


def summary():
    res = {}
    for name in ('rounD', 'inD', 'sind', 'lankershim', 'tgsim'):
        if not os.path.exists(f'{WORK}/{name}_stops.csv'):
            continue
        S = pd.read_csv(f'{WORK}/{name}_stops.csv'); E = pd.read_csv(f'{WORK}/{name}_starts.csv'); Lw = pd.read_csv(f'{WORK}/{name}_low.csv')
        for ds in sorted(S.ds.unique()):
            s = S[S.ds == ds]; ev = E[E.ds == ds]; lw = Lw[Lw.ds == ds]
            r = {}
            key = s.id.astype(str) + ds
            r['stand_gap_m'] = med_ci(s.gap_med, key)
            r['stand_gap_p10_p90'] = [round(float(s.gap_med.quantile(.1)), 2), round(float(s.gap_med.quantile(.9)), 2)] if len(s) else None
            r['stand_gap_by_pos'] = {int(p): med_ci(g.gap_med, g.id) for p, g in s[s.pos.between(2, 6)].groupby('pos') if len(g) >= 10}
            c = s[(s.lead_stand >= 8) & (s.lead_moved.abs() < 0.3)]
            r['creep'] = dict(stops=int(len(c)), share_moved_0_5m=round(float((c.moved >= 0.5).mean()), 3) if len(c) else None,
                              gap_first=med_ci(c.gap_first, c.id), gap_before_leader_moves=med_ci(c.gap_before_leader_moves, c.id),
                              moved_median_of_movers=round(float(c.moved[c.moved >= 0.5].median()), 2) if (c.moved >= 0.5).any() else None,
                              by_gap_first={f'{lo}-{lo + 1}': [round(float((k.moved >= 0.5).mean()), 2), int(len(k))]
                                            for lo in range(0, 8) for k in [c[(c.gap_first >= lo) & (c.gap_first < lo + 1)]] if len(k) >= 10})
            r['start_delay_s'] = med_ci(ev.delay[(ev.delay > 0) & (ev.delay < 6)], ev.id[(ev.delay > 0) & (ev.delay < 6)])
            ok = (ev.delay > 0) & (ev.delay < 6)
            r['start_delay_by_pos'] = {int(p): med_ci(g.delay, g.id) for p, g in ev[ok & ev.pos.between(1, 6)].groupby('pos') if len(g) >= 10}
            r['follower_peak_acc'] = med_ci(ev.peak_acc[ev.peak_acc.between(0, 6)], ev.id[ev.peak_acc.between(0, 6)])
            r['gap_at_5_8_m_s'] = [med_ci(ev.gap_5, ev.id), med_ci(ev.gap_8, ev.id)]
            hw = ev[(ev.headway > 0.5) & (ev.headway < 8)]
            r['headway_at_head_line_by_pos'] = {int(p): med_ci(g.headway, g.id) for p, g in hw[hw.pos.between(1, 8)].groupby('pos') if len(g) >= 8}
            r['headway_all'] = med_ci(hw.headway, hw.id)
            r['low_speed_gap_m'] = {f'{lo}-{hi}': med_ci(k.gap, k.id) for lo, hi in ((0.5, 1.5), (1.5, 2.5), (2.5, 3.5), (4, 6), (7, 9), (9, 12))
                                   for k in [lw[(lw.v >= lo) & (lw.v < hi)]] if len(k) >= 30}
            res[ds] = r
            print(ds, json.dumps(r)[:1500], flush=True)
    json.dump(res, open(OUT, 'w'), indent=1)


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        for n in sys.argv[2:] or ['rounD', 'inD', 'sind', 'lankershim', 'tgsim']:
            collect(n)
        summary()
    elif sys.argv[1] == 'summary':
        summary()
