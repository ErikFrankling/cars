"""Signal states read from stop-line crossings, and the reader scored where the controller's states are known.

pNEUMA and Songdo log no signals, so greens are read from the traffic: a green begins shortly before the head of a
standing queue starts, and ends shortly before the last car of the burst crosses. The reader sees only per-vehicle
tracks along one signal group's path: time, front position relative to the stop line (s, negative before it), speed,
lateral offset and class. Everything dataset-specific (which vehicles use the group, where its line is) is done by the
callers. Two readings:

- per cycle: onset = start of a standing head - d_start, end = last crossing of the burst - d_end;
- fixed time (pre-timed controllers, Athens): one cycle length, onset and green length fitted to every cycle's events.

d_start and d_end are biases measured on other sites (leave the scored site out), never on the scored one.

    python3 -I scripts/replay/signals.py dlrut          # events + truth per signal group, cached
    python3 -I scripts/replay/signals.py sind
    python3 -I scripts/replay/signals.py score          # -> research/truth/replay/signals.json
"""
import os, sys, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = '/home/erikf/projects/personal/cars-data/replay/signals'
RES = os.path.join(REPO, 'research', 'truth', 'replay')

V_STAND, V_GO = 0.5, 1.5           # m/s
STAND_MIN = 2.0                    # s standing before a start counts
HEAD_ZONE = 10.0                   # m: a standing front this close to the line can be a head
QZONE = 60.0                       # m: queue counted for the saturation level
LANE_BAND = 1.6                    # m: lateral band of one lane
MERGE = 6.0                        # s: head starts this close are one onset (lanes start together)
CROSS_MAX = 20.0                   # s: a head must cross within this after it starts, or it was not released by a green
MIN_RED = 8.0                      # s: shortest red the reader accepts between two greens
V_CROSS = 2.0                      # m/s: a crossing slower than this is a car creeping over the line, not a green
HEAD_GAP = 1.0                     # m: a head stands this far behind its line
MIN_GREEN = 8.0                    # s: shortest green a fixed program is given


# ---------------------------------------------------------------- events from tracks

def events(veh):
    """veh: list of dicts with arrays t, s (front, relative to the line), v, lat, and 'kind' ('car' or 'two' for
    two-wheelers and other small vehicles that filter through queues). Returns crossings and standing runs."""
    cross, stands = [], []
    for k, d in enumerate(veh):
        t, s, v = d['t'], d['s'], d['v']
        if len(t) < 3:
            continue
        j = np.flatnonzero((s[:-1] < 0) & (s[1:] >= 0))
        if len(j):
            a = j[0]; tc = t[a] + (0 - s[a]) / max(s[a + 1] - s[a], 1e-6) * (t[a + 1] - t[a])
            cross.append((k, tc, float(v[a + 1]), d['kind']))
        st = v < V_STAND
        if st.any():
            e = np.flatnonzero(np.diff(np.r_[0, st.astype(int), 0]))
            for b0, b1 in zip(e[::2], e[1::2]):
                if t[b1 - 1] - t[b0] < 0.6:
                    continue
                sf = float(np.median(s[b0:b1]))
                if sf < -QZONE or sf > 1.0:
                    continue
                go = np.flatnonzero((t > t[b1 - 1]) & (v > V_GO))
                tgo = float(t[go[0]]) if len(go) else np.nan
                stands.append((k, float(t[b0]), float(t[b1 - 1]), tgo, sf, float(np.median(d['lat'][b0:b1])), d['kind']))
    C = pd.DataFrame(cross, columns=['veh', 't', 'v', 'kind']).sort_values('t').reset_index(drop=True)
    S = pd.DataFrame(stands, columns=['veh', 't0', 't1', 'tgo', 's', 'lat', 'kind'])
    tc = dict(zip(C.veh, C.t))
    S['tcross'] = S.veh.map(tc)
    return C, S


def stop_line(S):
    """Where queue heads stand: standing cars with nobody standing ahead of them in their lane within 25 m, that
    cross within CROSS_MAX of going (parked and blocked cars do not). Returns the shift to add to s so that the line
    is at 0 (heads stand HEAD_GAP behind it), and the number of heads it rests on."""
    c = S[(S.kind == 'car') & (S.t1 - S.t0 >= STAND_MIN) & S.tgo.notna() & (S.tcross > S.t1) & (S.tcross - S.tgo < CROSS_MAX)]
    A = S[S.kind == 'car']
    hs = []
    for r in c.itertuples():
        m = (A.t0 <= r.t1) & (A.t1 >= r.t1) & ((A.lat - r.lat).abs() < LANE_BAND) & (A.s > r.s + 1.0) & (A.s < r.s + 25) & (A.veh != r.veh)
        if not m.any():
            hs.append(r.s)
    if len(hs) < 5:
        return 0.0, len(hs)
    hs = np.array(hs)
    # the densest 4 m window of head positions, then its median
    best = max(((np.abs(hs - x) < 2.0).sum(), x) for x in hs)[1]
    return -(float(np.median(hs[np.abs(hs - best) < 2.0])) + HEAD_GAP), len(hs)


def heads(S):
    """Standing runs that are the front of their lane when they start, close to the line, standing long enough,
    and that cross soon after they go."""
    c = S[(S.kind == 'car') & (S.s >= -HEAD_ZONE) & (S.t1 - S.t0 >= STAND_MIN) & S.tgo.notna()]
    c = c[(c.tcross > c.t1) & (c.tcross - c.tgo < CROSS_MAX)]
    A = S[S.kind == 'car'].sort_values('t0')
    t0, t1, lat, s, vh = (A[k].to_numpy() for k in ('t0', 't1', 'lat', 's', 'veh'))
    keep = []
    for i, r in zip(c.index, c.itertuples()):
        # nobody standing ahead of it in its lane at the moment it starts
        a = np.searchsorted(t0, r.t1 - 900, 'left'); b = np.searchsorted(t0, r.t1, 'right')
        m = (t1[a:b] >= r.t1) & (np.abs(lat[a:b] - r.lat) < LANE_BAND) & (s[a:b] > r.s + 1.0) & (vh[a:b] != r.veh)
        if not m.any():
            keep.append(i)
    return c.loc[keep]


def read_cycles(C, S, d_start, d_end):
    """Per-cycle reading: list of (onset, end, n_heads, end_kind). The burst of a cycle runs from its onset to the
    first car that comes to stand at the line after it (red is on by then) or the next onset; its last moving
    crossing, minus d_end, is the end. end_kind 'bounded' when a car stopped after it, else 'open'."""
    H = heads(S).sort_values('tgo')
    on = []
    for t in H.tgo:
        if on and t - on[-1][-1] < MERGE:
            on[-1].append(t)
        else:
            on.append([t])
    onsets = [float(np.median(g)) - d_start for g in on]
    nh = [len(g) for g in on]
    car = C[(C.kind == 'car') & (C.v > V_CROSS)]
    near = S[(S.kind == 'car') & (S.s >= -HEAD_ZONE)].sort_values('t0')
    out = []
    for k, g in enumerate(onsets):
        nxt = onsets[k + 1] if k + 1 < len(onsets) else np.inf
        st = near[(near.t0 > g + d_start + 2.0) & (near.t0 < nxt)]
        red = float(st.t0.iloc[0]) if len(st) else np.inf
        lim = min(red, nxt - MIN_RED + d_start)
        cc = car[(car.t > g) & (car.t < lim)].t.values
        if not len(cc):
            out.append((g, np.nan, nh[k], 'none')); continue
        out.append((g, float(cc[-1]) - d_end, nh[k], 'bounded' if np.isfinite(red) and red < nxt else 'open'))
    return out


def fit_fixed(C, S, d_start, d_end, t0, t1, cmin=40.0, cmax=180.0):
    """One fixed program over [t0, t1]: cycle from head starts (circular concentration; the longest cycle near the
    best, so a harmonic is not taken), onset phase from their circular mean, green end where the moving car
    crossings' phases stop: the start of the longest empty arc of the cycle, minus d_end."""
    H = heads(S)
    H = H[(H.tgo >= t0) & (H.tgo <= t1)]
    g = H.tgo.values - d_start
    if len(g) < 6:
        return None
    grid = np.arange(cmin, cmax, 0.01)
    z = np.abs(np.exp(2j * np.pi * g[None, :] / grid[:, None]).mean(1))
    k = np.flatnonzero(z >= 0.95 * z.max())[-1]
    lo, hi = max(k - 300, 0), min(k + 300, len(grid))
    cyc = float(grid[lo + np.argmax(z[lo:hi])]); R = float(z[lo:hi].max())
    off = (np.angle(np.mean(np.exp(2j * np.pi * g / cyc))) / (2 * np.pi) * cyc) % cyc
    car = C[(C.kind == 'car') & (C.v > V_CROSS) & (C.t >= t0) & (C.t <= t1)].t.values
    rel = np.sort((car - off + 3.0) % cyc) - 3.0
    if len(rel) < 10:
        return None
    gaps = np.diff(np.r_[rel, rel[0] + cyc])
    arc = float(rel[int(np.argmax(gaps))])
    # per cycle, the last crossing inside the green arc; the 80th percentile over cycles
    kk = np.floor((car - off + 3.0) / cyc)
    last = pd.Series((car - off + 3.0) % cyc - 3.0).groupby(kk).apply(lambda x: x[x <= arc + 0.01].max())
    p80 = float(np.nanpercentile(last.values, 80)) if len(last) else arc
    ends = dict(arc=arc - d_end['arc'], p80=p80 - d_end['p80'])
    greens = {m: [(off + k * cyc, off + k * cyc + e, 0, 'fixed') for k in range(int(np.floor((t0 - off) / cyc)) - 1, int(np.ceil((t1 - off) / cyc)) + 1)]
              for m, e in ends.items()}
    return dict(cycle=cyc, R=R, offset=float(off), green=ends, greens=greens, raw_end=dict(arc=arc, p80=p80))


# ---------------------------------------------------------------- truth and scoring

def truth_cycles(states_t, states_g, t0, t1):
    """Green intervals [onset, yellow onset) from a state series (time-sorted change points, boolean green)."""
    g = np.asarray(states_g, bool); t = np.asarray(states_t, float)
    on = np.flatnonzero(g[1:] & ~g[:-1]) + 1
    off = np.flatnonzero(~g[1:] & g[:-1]) + 1
    out = []
    for k in on:
        e = off[off > k]
        if not len(e):
            continue
        if t0 <= t[k] <= t1:
            out.append((float(t[k]), float(t[e[0]])))
    return out


def saturation(S, C, g0, g1, yellow):
    """Queue at the true onset (standing cars within QZONE) and a residual queue at the end of the yellow."""
    before = (S.kind == 'car') & (S.s < 0) & ~(S.tcross < S.t0)          # standing before the line, not yet across it
    at = S[before & (S.t0 <= g0) & (S.t1 >= g0 - 0.5)]
    q = int(len(at))
    te = g1 + yellow + 2.0
    res = S[before & (S.t0 <= g1 - 5.0) & (S.t1 >= te)]
    r = int(len(res))
    lvl = 'none' if q == 0 else 'light' if q <= 3 else 'heavy'
    if r > 0 and q > 0:
        lvl = 'over'
    return q, r, lvl


def score(true, read, S, C, yellow, name):
    """Match each true green to the read green with the nearest onset among those overlapping it."""
    rows, used = [], set()
    R = [r for r in read if np.isfinite(r[0])]
    for g0, g1 in true:
        q, res, lvl = saturation(S, C, g0, g1, yellow)
        cand = [(abs(r[0] - g0), i) for i, r in enumerate(R) if r[0] < g1 and (not np.isfinite(r[1]) or r[1] > g0 - 3) and r[0] > g0 - 0.5 * (g1 - g0) - 10]
        cand = [c for c in cand if c[1] not in used]
        crossed = int(((C.kind == 'car') & (C.t >= g0) & (C.t <= g1 + yellow + 1)).sum())
        if cand:
            _, i = min(cand); used.add(i)
            rows.append(dict(group=name, g0=g0, g1=g1, queue=q, residual=res, level=lvl, crossed=crossed, read=True,
                             on_err=R[i][0] - g0, end_err=R[i][1] - g1, end_kind=R[i][3]))
        else:
            rows.append(dict(group=name, g0=g0, g1=g1, queue=q, residual=res, level=lvl, crossed=crossed, read=False, on_err=np.nan, end_err=np.nan, end_kind=''))
    lo, hi = (true[0][0] - 30, true[-1][1] + 30) if true else (0, 0)
    false = [r for i, r in enumerate(R) if i not in used and lo <= r[0] <= hi]
    return pd.DataFrame(rows), len(false), len([r for r in R if lo <= r[0] <= hi])


# ---------------------------------------------------------------- DLR UT

CACHE = '/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-cache'
UT_PTS = {1: [(604755.480, 5792814.102), (604749.966, 5792812.211)], 2: [(604761.424, 5792815.793)],
          3: [(604790.745, 5792814.817), (604792.294, 5792809.095), (604793.765, 5792806.195)], 4: [(604795.332, 5792803.053), (604796.300, 5792798.214)],
          5: [(604793.626, 5792779.886), (604787.472, 5792776.873)], 6: [(604784.549, 5792776.031)], 7: [(604780.221, 5792775.418), (604775.881, 5792774.066)],
          8: [(604748.909, 5792774.532), (604748.134, 5792780.177)], 9: [(604746.834, 5792783.266), (604745.843, 5792786.123), (604744.122, 5792790.989)]}
UT_O = np.array([604625.0, 5792650.0])


def dlrut_groups():
    """Per signal group: the tracks of vehicles that pass within 1.8 m of one of its stop points heading inbound, as
    front position along the group's inbound direction relative to its line, plus the controller's green series."""
    d = np.load(f'{CACHE}/ut_veh.npz'); o = np.lexsort((d['t'], d['id']))
    ID, T, X, Y, V, L, TR = [d[k][o] for k in ('id', 't', 'x', 'y', 'v', 'L', 'truck')]
    ub = np.r_[0, np.flatnonzero(np.diff(ID)) + 1, len(ID)]
    pts = {s: np.array(p) - UT_O for s, p in UT_PTS.items()}
    centre = np.vstack(list(pts.values())).mean(0)
    tl = np.load(f'{CACHE}/ut_tl.npz')
    out = {}
    allp = np.vstack([p for p in pts.values()]); alls = np.concatenate([[s] * len(p) for s, p in pts.items()])
    users = {s: [] for s in pts}
    for i in range(len(ub) - 1):
        a, b = ub[i], ub[i + 1]
        if b - a < 10:
            continue
        x, y = X[a:b], Y[a:b]
        D = (x[:, None] - allp[:, 0]) ** 2 + (y[:, None] - allp[:, 1]) ** 2
        n, j = np.unravel_index(np.argmin(D), D.shape)
        if D[n, j] > 1.8 ** 2 or n < 2 or n > b - a - 3:
            continue
        dv = np.array([x[n + 2] - x[n - 2], y[n + 2] - y[n - 2]])
        if dv @ (centre - allp[j]) <= 0:
            continue
        users[int(alls[j])].append((a, b, j))
    for s, us in users.items():
        if not us:
            continue
        # inbound direction: median heading of users at their stop point
        hd = []
        for a, b, j in us:
            dd = np.hypot(X[a:b] - allp[j, 0], Y[a:b] - allp[j, 1]); n = int(np.argmin(dd))
            n0, n1 = max(n - 3, 0), min(n + 3, b - a - 1)
            h = np.array([X[a + n1] - X[a + n0], Y[a + n1] - Y[a + n0]])
            if np.linalg.norm(h) > 0.5:
                hd.append(h / np.linalg.norm(h))
        u = np.median(np.array(hd), 0); u /= np.linalg.norm(u); nrm = np.array([-u[1], u[0]])
        p0 = pts[s].mean(0)
        veh = []
        for a, b, j in us:
            rx, ry = X[a:b] - p0[0], Y[a:b] - p0[1]
            sf = rx * u[0] + ry * u[1] + L[a:b] / 2
            lat = rx * nrm[0] + ry * nrm[1]
            keep = sf > -120
            veh.append(dict(t=T[a:b][keep].astype(float), s=sf[keep].astype(float), v=V[a:b][keep].astype(float), lat=lat[keep].astype(float),
                            kind='car', id=int(ID[a])))
        m = tl['id'] == s; tt = tl['t'][m]; st = tl['state'][m]; oo = np.argsort(tt); tt, st = tt[oo], st[oo]
        ch = np.r_[0, np.flatnonzero(np.diff(st)) + 1]
        out[s] = dict(veh=veh, truth_t=tt[ch], truth_green=(st[ch] == 5), truth_state=st[ch], u=u.tolist())
    return out


# ---------------------------------------------------------------- SinD

SIND = '/home/erikf/projects/personal/cars-data/datasets/jt25-sind/'
SIND_REC = {'Tianjin': ('Tianjin_8_2_1_Veh_smoothed_tracks.csv', 'Tianjin_8_2_1_TrafficLight_8_2_1.csv'),
            'Chongqing': ('Chongqing_6_22_NR_1_Veh_smoothed_tracks.csv', 'Chongqing_6_22_NR_1_TrafficLight_06_22_NR1_add_plight.csv')}


def sind_groups(city):
    """Approach and movement groups as scripts/measure/sind.py finds them (entry direction clusters, turn from heading
    change); stop line from where first-in-queue cars stand (95th percentile of their fronts). The governing light is
    taken as sind.py does, from which light's onsets the standing cars start after: that picks the truth to score
    against, the reader does not see it."""
    sys.path.insert(0, os.path.join(REPO, 'scripts', 'measure'))
    import sind as SM
    from holdout import HOLD
    assert city not in HOLD['sind']
    tp, lp = SIND_REC[city]
    t = pd.read_csv(SIND + tp, usecols=['track_id', 'timestamp_ms', 'agent_type', 'x', 'y', 'vx', 'vy', 'length'])
    t['t'] = t.timestamp_ms / 1000.0; t['v'] = np.hypot(t.vx, t.vy)
    t = t.sort_values(['track_id', 't']).reset_index(drop=True)
    motor = t[t.agent_type.isin(SM.MOTOR)]
    T = SM.describe_tracks(motor)
    lab, Cc = SM.approaches(T)
    T['app'] = lab
    # every road user of an approach, by its entry heading: cars, and two- and three-wheelers that filter
    allT = []
    for i, g in t.groupby('track_id'):
        mv = g[g.v > 1.0]
        if len(mv) < 10:
            continue
        h0 = np.arctan2(mv.vy.iloc[:10].mean(), mv.vx.iloc[:10].mean()); h1 = np.arctan2(mv.vy.iloc[-10:].mean(), mv.vx.iloc[-10:].mean())
        turn = np.rad2deg(np.angle(np.exp(1j * (h1 - h0))))
        app = int(np.argmax(np.array([np.cos(h0), np.sin(h0)]) @ Cc.T))
        allT.append((i, app, 'left' if turn > 45 else 'right' if turn < -45 else 'straight', g.agent_type.iloc[0], float(g.length.median())))
    A = pd.DataFrame(allT, columns=['id', 'app', 'mv', 'type', 'L']).set_index('id')
    L = pd.read_csv(SIND + lp)
    cols = [c for c in L.columns if 'light' in c.lower() and 'pedestrian' not in c.lower()]
    ts = L['timestamp(ms)'].to_numpy(float) / 1000
    groups = {}
    for (app, mv), ids in A.groupby(['app', 'mv']).groups.items():
        if mv == 'right':
            continue
        u = Cc[app]; nrm = np.array([-u[1], u[0]])
        g = t[t.track_id.isin(ids)].copy()
        g['s'] = g.x * u[0] + g.y * u[1] + g.length / 2
        g['lat'] = g.x * nrm[0] + g.y * nrm[1]
        car = g[g.agent_type.isin(SM.MOTOR)]
        stops = []
        for i, gg in car.groupby('track_id'):
            st = gg.v.to_numpy() < 0.5
            if st.sum() < 20:
                continue
            k = np.flatnonzero(st)
            stops.append((i, float(gg.s.to_numpy()[k].max()), float(gg.t.to_numpy()[k[0]]), float(gg.t.to_numpy()[k[-1]])))
        if len(stops) < 5:
            continue
        St = pd.DataFrame(stops, columns=['id', 's', 't0', 't1'])
        s_line = float(np.percentile(St.s, 95))
        best, score_ = None, -1
        for c in cols:
            s_ = L[c].to_numpy()
            on = [ts[i] for i in range(1, len(s_)) if s_[i] == 1 and s_[i - 1] != 1]
            n = sum(int(((St.t1 >= gon - 0.5) & (St.t1 <= gon + 10) & (St.t0 < gon)).sum()) for gon in on)
            if n > score_:
                best, score_ = c, n
        veh = []
        for i, gg in g.groupby('track_id'):
            kind = 'car' if gg.agent_type.iloc[0] in SM.MOTOR else 'two'
            veh.append(dict(t=gg.t.to_numpy(), s=gg.s.to_numpy() - s_line, v=gg.v.to_numpy(), lat=gg.lat.to_numpy(), kind=kind, id=int(i)))
        s_ = L[best].to_numpy()
        groups[f'{city} app{app} {mv}'] = dict(veh=veh, truth_t=ts, truth_green=(s_ == 1), truth_state=s_, light=best, starts_matched=score_,
                                               n_cars=int(sum(1 for v in veh if v['kind'] == 'car')))
    return groups


# ---------------------------------------------------------------- driver

def build_events(name, groups):
    os.makedirs(OUT, exist_ok=True)
    rows = {}
    for g, d in groups.items():
        C, S = events(d['veh'])
        shift, nheads = stop_line(S)
        if abs(shift) > 0.3:
            for v in d['veh']:
                v['s'] = v['s'] + shift
            C, S = events(d['veh'])
        rows[str(g)] = dict(line_shift=shift, line_heads=nheads, C=C, S=S, truth_t=np.asarray(d['truth_t'], float), truth_green=np.asarray(d['truth_green'], bool),
                            t_range=(float(min(v['t'][0] for v in d['veh'])), float(max(v['t'][-1] for v in d['veh']))),
                            meta={k: v for k, v in d.items() if k in ('light', 'starts_matched', 'n_cars', 'u')})
        print(name, g, 'crossings', len(C), 'stands', len(S), 'line moved', round(shift, 1), 'm on', nheads, 'heads', flush=True)
    pd.to_pickle(rows, f'{OUT}/{name}_events.pkl')


def start_end_bias(ev, yellow):
    """Per-cycle onset and end biases (read minus true) with zero correction, from a site's events."""
    on, en, en_sat = [], [], []
    for g, d in ev.items():
        true = truth_cycles(d['truth_t'], d['truth_green'], *d['t_range'])
        read = read_cycles(d['C'], d['S'], 0.0, 0.0)
        df, _, _ = score(true, read, d['S'], d['C'], yellow, g)
        if not len(df):
            continue
        k = df[df.read & (df.queue > 0)]
        on += list(k.on_err)
        en += list(df[df.read & (df.end_kind == 'bounded')].end_err.dropna())
    return float(np.median(on)), float(np.median(en)), len(on), len(en)


def q(x):
    x = np.abs(np.asarray(x, float)); x = x[np.isfinite(x)]
    if not len(x):
        return None
    return dict(n=int(len(x)), median=round(float(np.median(x)), 2), p90=round(float(np.percentile(x, 90)), 2))


def summarise(df, nfalse, nread):
    out = dict(true_greens=int(len(df)), read_greens=int(nread), false=int(nfalse), false_pct=round(100 * nfalse / max(nread, 1), 1))
    wq = df[df.queue > 0]
    out['with_standing_car'] = dict(n=int(len(wq)), missed_pct=round(100 * float((~wq.read).mean()), 1) if len(wq) else None,
                                    onset_abs=q(wq.on_err), onset_bias=round(float(wq.on_err.median()), 2) if wq.read.any() else None)
    out['no_standing_car'] = dict(n=int((df.queue == 0).sum()), with_crossings=int(((df.queue == 0) & (df.crossed > 0)).sum()),
                                  read_pct=round(100 * float(df[df.queue == 0].read.mean()), 1) if (df.queue == 0).any() else None)
    out['by_level'] = {}
    for lv in ('none', 'light', 'heavy', 'over'):
        k = df[df.level == lv]
        if not len(k):
            continue
        b = k[k.end_kind == 'bounded']
        out['by_level'][lv] = dict(n=int(len(k)), missed_pct=round(100 * float((~k.read).mean()), 1), onset_abs=q(k.on_err),
                                   end_abs_bounded=q(b.end_err), end_bias_bounded=round(float(b.end_err.median()), 2) if b.end_err.notna().any() else None,
                                   end_abs_open=q(k[k.end_kind == 'open'].end_err))
    return out


def score_fixed(items, d_start, yellow):
    """Fixed-time fits where the truth's cycle is constant. The end's bias (estimate minus true green) is measured
    per site (city) and applied to the other ones: never to its own."""
    site = lambda g: g.split()[0]
    raw = {}
    for g, d, true, t0, t1, cyc_true in items:
        fx = fit_fixed(d['C'], d['S'], d_start, dict(arc=0.0, p80=0.0), t0, t1)
        if fx:
            tg = float(np.median([b - a for a, b in true]))
            raw[g] = {m: fx['raw_end'][m] - tg for m in ('arc', 'p80')}
    out = dict(groups={}, end_bias_by_site={})
    sites = sorted({site(g) for g in raw})
    for sname in sites:
        out['end_bias_by_site'][sname] = {m: round(float(np.median([v[m] for g, v in raw.items() if site(g) == sname])), 2) for m in ('arc', 'p80')}
    for g, d, true, t0, t1, cyc_true in items:
        others = [v for gg, v in raw.items() if site(gg) != site(g)]
        if not others:
            continue
        d_end = {m: float(np.median([v[m] for v in others])) for m in ('arc', 'p80')}
        fx = fit_fixed(d['C'], d['S'], d_start, d_end, t0, t1)
        if not fx:
            continue
        r = dict(true_cycle=round(float(np.median(cyc_true)), 2), fit_cycle=round(fx['cycle'], 2), R=round(fx['R'], 2),
                 true_green=round(float(np.median([b - a for a, b in true])), 1))
        for m in ('arc', 'p80'):
            dff, _, _ = score(true, fx['greens'][m], d['S'], d['C'], yellow, g)
            r[m] = dict(fit_green=round(fx['green'][m], 1), onset_abs=q(dff.on_err), end_abs=q(dff.end_err), end_bias=round(float(dff.end_err.median()), 2), missed=int((~dff.read).sum()))
        out['groups'][g] = r
    # End from the junction's next onset: a group's green ends one intergreen (yellow + all-red) before the next
    # onset at the same junction that comes at least MIN_GREEN after its own. The intergreen is measured on the
    # other sites' truth; the onsets are the fitted ones.
    fits = {}
    for g, d, true, t0, t1, cyc_true in items:
        fx = fit_fixed(d['C'], d['S'], d_start, dict(arc=0.0, p80=0.0), t0, t1)
        if fx:
            fits[g] = (fx, true, d)
    inter = {}
    for g, (fx, true, d) in fits.items():
        nxt = [t for t in d['truth_t'][1:][~d['truth_green'][1:] & d['truth_green'][:-1]]]
        # true intergreen: from this group's yellow onset to the next green onset of any other group at the site
        ons = sorted(a for gg, (f2, tr2, d2) in fits.items() if site(gg) == site(g) and gg != g for a, b in tr2)
        ig = []
        for a, b in true:
            k = np.searchsorted(ons, b)
            if k < len(ons) and ons[k] - b < 15:
                ig.append(ons[k] - b)
        inter[g] = float(np.median(ig)) if ig else np.nan
    out['intergreen_by_site'] = {sn: round(float(np.nanmedian([v for g, v in inter.items() if site(g) == sn])), 2) for sn in sites}
    for g, (fx, true, d) in fits.items():
        if g not in out['groups']:
            continue
        ig = np.nanmedian([v for gg, v in inter.items() if site(gg) != site(g)])
        cyc, off = fx['cycle'], fx['offset']
        others = [((f2['offset'] - off) % cyc) for gg, (f2, _, _) in fits.items() if site(gg) == site(g) and gg != g]
        others = sorted(o for o in others if o >= MIN_GREEN)
        if not others:
            continue
        e = others[0] - ig
        greens = [(off + k * cyc, off + k * cyc + e, 0, 'fixed') for k in range(int(np.floor((t0 - off) / cyc)) - 1, int(np.ceil((t1 - off) / cyc)) + 1)]
        dff, _, _ = score(true, greens, d['S'], d['C'], yellow, g)
        out['groups'][g]['next_onset'] = dict(fit_green=round(e, 1), end_abs=q(dff.end_err), end_bias=round(float(dff.end_err.median()), 2))
    allg = out['groups'].values()
    out['pooled'] = dict(cycle_abs=q([v['fit_cycle'] - v['true_cycle'] for v in allg]),
                         onset_median_of_groups=q([v['arc']['onset_abs']['median'] for v in allg]),
                         **{f'end_{m}_median_of_groups': q([v[m]['end_abs']['median'] for v in allg]) for m in ('arc', 'p80')},
                         end_next_onset_median_of_groups=q([v['next_onset']['end_abs']['median'] for v in allg if 'next_onset' in v]))
    return out


def run_score():
    res = {}
    ev = {n: pd.read_pickle(f'{OUT}/{n}_events.pkl') for n in ('dlrut', 'sind')}
    yellow = {'dlrut': 3.0, 'sind': 3.0}
    raw = {n: start_end_bias(ev[n], yellow[n]) for n in ev}
    res['raw_bias'] = {n: dict(onset=round(r[0], 2), end_bounded=round(r[1], 2), n_onset=r[2], n_end=r[3]) for n, r in raw.items()}
    other = {'dlrut': 'sind', 'sind': 'dlrut'}
    for n in ev:
        d_start, d_end = raw[other[n]][0], raw[other[n]][1]
        dfs, nf, nr = [], 0, 0
        fixed_in = []
        for g, d in ev[n].items():
            if n == 'dlrut':
                t0, t1 = 6 * 3600.0, 22 * 3600.0
            else:
                t0, t1 = d['t_range']
            true = truth_cycles(d['truth_t'], d['truth_green'], t0, t1)
            if len(true) < 3:
                continue
            read = read_cycles(d['C'], d['S'], d_start, d_end)
            df, f_, r_ = score(true, read, d['S'], d['C'], yellow[n], g)
            dfs.append(df); nf += f_; nr += r_
            cyc_true = np.diff([a for a, b in true])
            if len(cyc_true) >= 4 and np.ptp(cyc_true) < 2.5:
                fixed_in.append((g, d, true, t0, t1, cyc_true))
        df = pd.concat(dfs, ignore_index=True)
        df.to_csv(f'{OUT}/{n}_scored.csv', index=False)
        res[n] = dict(d_start=round(d_start, 2), d_end=round(d_end, 2), stop_line_shift_m={g: round(d['line_shift'], 2) for g, d in ev[n].items()}, per_cycle=summarise(df, nf, nr),
                      per_group={g: summarise(k, 0, 0)['with_standing_car'] for g, k in df.groupby('group')},
                      fixed=score_fixed(fixed_in, d_start, yellow[n]) if fixed_in else 'no group with a constant cycle')
    json.dump(res, open(os.path.join(RES, 'signals.json'), 'w'), indent=1)
    print(json.dumps(res, indent=1)[:6000])


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'dlrut':
        build_events('dlrut', dlrut_groups())
    elif c == 'sind':
        g = {}
        for city in SIND_REC:
            g.update(sind_groups(city))
        build_events('sind', g)
    elif c == 'score':
        run_score()
