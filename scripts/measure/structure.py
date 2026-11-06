"""Round 3 of the measured driver: which structure of the following law reproduces every measured pattern at once.
Pattern list and margins: forecasts F800 onwards, research/truth/measure/STRUCTURE.md. Recordings not held out
(HOLDOUT.md): the five follower tables of follow.py, the queue launches of queues.py, the 30 s windows of gapclose.py.

    python3 -I scripts/measure/structure.py data       # build the cached query sets
    python3 -I scripts/measure/structure.py gain       # F801: closing gain by gap bin, tables and launches
    python3 -I scripts/measure/structure.py filter     # fit every candidate on all patterns jointly, score each
"""
import os, sys, json, pickle, math
import numpy as np, pandas as pd
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
RES = os.path.join(REPO, 'research', 'truth', 'measure')
OUT = os.path.join(RES, 'structure.json')
CACHE = '/home/erikf/projects/personal/cars-data/measure/md3'
QW = '/home/erikf/projects/personal/cars-data/measure/queues'
import fit_driver as FD
import md_twin_lite as MT

DT = 0.2
BETA = 1 - math.exp(-DT / FD.TAU_R)
HIST = 15                     # leader history kept before each query, samples (3 s at 5 Hz)
R2 = json.load(open(FD.OUTJ))['pooled']
P_R2 = [R2['K'], R2['c_a'], R2['k_g'], R2['k_p']]
rng = np.random.default_rng(20261110)
LAUNCH_SITES = ['rounD', 'inD', 'SinD Changchun']
LAUNCH_REPORT = ['SinD Tianjin', 'SinD Chongqing', 'Lankershim']


def save(key, val):
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    out[key] = val
    json.dump(out, open(OUT, 'w'), indent=1)


# ---------------------------------------------------------------- query sets
def _segpos(seg):
    n = len(seg)
    start = np.r_[0, np.flatnonzero(np.diff(seg)) + 1]
    return np.arange(n) - np.repeat(start, np.diff(np.r_[start, n]))


def table_queries(name, n_follow=3000, horizon=5, every=5):
    """FD.samples with the leader's last 3 s kept (for laws that look at the leader's past)."""
    import follow as F
    r = np.random.default_rng(20261107)
    d = F.load(name)
    d = d[d.lcar.astype(bool)]
    uf = d.fid.unique()
    d = d[d.fid.isin(r.choice(uf, min(n_follow, len(uf)), replace=False))].reset_index(drop=True)
    seg = d.seg.to_numpy(); vf = d.vf.to_numpy(float); vl = d.vl.to_numpy(float); al = d.al.to_numpy(float); gap = d.gap.to_numpy(float)
    n = len(d); pos = _segpos(seg)
    ok = np.zeros(n, bool)
    ok[HIST:n - horizon] = (seg[HIST:n - horizon] == seg[:n - horizon - HIST]) & (seg[HIST:n - horizon] == seg[HIST + horizon:])
    ok &= (pos % every == 0) & (vf > 2.0) & (gap > 0.5) & (gap < 100) & np.isfinite(al)
    i = np.flatnonzero(ok)
    J = i[:, None] + np.arange(-HIST, horizon + 1)[None, :]
    good = np.isfinite(al[J]).all(1) & np.isfinite(vl[J]).all(1)
    i, J = i[good], J[good]
    return dict(name=name, fid=d.fid.to_numpy()[i], v=vf[i], a=(vf[i] - vf[i - 2]) / 0.4, g=gap[i],
                VL=vl[J], AL=al[J], y=vf[i + horizon] - vf[i], vdes=1e3)


def launch_events():
    """Queue launches of queues.py (follower stands, leader passes 1 m/s; to 10 s past the follower's 1 m/s), resampled at
    5 Hz, same leader throughout. One array set per site."""
    out = {}
    for f in ('rounD', 'inD', 'sind', 'lankershim'):
        d = pd.read_csv(f'{QW}/{f}_launch.csv')
        for ds, g0 in d.groupby('ds'):
            ev = []
            for e, g in g0.groupby('ev'):
                g = g.sort_values('t')
                t = g.t.to_numpy(float)
                tt = np.arange(t[0], t[-1] + 1e-6, DT)
                if len(tt) < 12:
                    continue
                cols = {c: np.interp(tt, t, g[c].to_numpy(float)) for c in ('v', 'gap', 'vl', 'al')}
                lok = np.interp(tt, t, g.lok.to_numpy(float)) > 0.999
                cols['lok'] = lok
                ev.append((e, cols))
            out[ds] = ev
    return out


def launch_queries(ev, horizon=5):
    """Next-second queries along launches: from the follower's motion onset (0.3 m/s) on, under 12 m/s."""
    Q = dict(v=[], a=[], g=[], VL=[], AL=[], y=[], ev=[])
    for e, c in ev:
        v, gap, vl, al, ok = c['v'], c['gap'], c['vl'], c['al'], c['lok']
        on = np.flatnonzero(v >= 0.3)
        if not len(on):
            continue
        for i in range(max(on[0], 2), len(v) - horizon, 2):
            if not ok[i:i + horizon + 1].all() or v[i] > 12 or not np.isfinite(gap[i]):
                continue
            h = np.arange(i - HIST, i + horizon + 1)
            hc = np.clip(h, 0, None)
            VLh = np.where(h >= 0, vl[hc], 0.0)          # before the event the leader was under 1 m/s; take it as standing
            ALh = np.where(h >= 0, al[hc], 0.0)
            Q['v'].append(v[i]); Q['a'].append((v[i] - v[i - 2]) / 0.4); Q['g'].append(gap[i]); Q['VL'].append(VLh); Q['AL'].append(ALh)
            Q['y'].append(v[i + horizon] - v[i]); Q['ev'].append(e)
    Q = {k: np.array(x) for k, x in Q.items()}
    Q['vdes'] = 16.0
    return Q


def launch_rollouts(ev, H=8.0):
    """Launch rollouts: from the follower's motion onset (first sample at 0.3 m/s or more) for H s behind the recorded
    leader, same leader throughout. Leader position = recorded follower position + recorded gap."""
    S = int(round(H / DT))
    R = dict(v0=[], a0=[], g=[], vl=[], al=[], xf=[], VLh=[], ev=[])
    for e, c in ev:
        v, gap, vl, al, ok = c['v'], c['gap'], c['vl'], c['al'], c['lok']
        on = np.flatnonzero(v >= 0.3)
        if not len(on):
            continue
        i = on[0]
        if i + S >= len(v) or not ok[i:i + S + 1].all() or not np.isfinite(gap[i:i + S + 1]).all():
            continue
        xf = np.r_[0, np.cumsum(0.5 * (v[i + 1:i + S + 1] + v[i:i + S]) * DT)]
        h = np.arange(i - HIST, i + 1); hc = np.clip(h, 0, None)
        R['v0'].append(v[i]); R['a0'].append((v[i] - v[max(i - 2, 0)]) / (DT * min(2, max(i, 1))))
        R['g'].append(gap[i:i + S + 1]); R['vl'].append(vl[i:i + S + 1]); R['al'].append(al[i:i + S + 1]); R['xf'].append(xf)
        R['VLh'].append(np.where(h >= 0, vl[hc], 0.0)); R['ev'].append(e)
    R = {k: np.array(x) for k, x in R.items()}
    R['vdes'] = 16.0; R['H'] = H
    return R


def windows(name, H, n_max=2000):
    import gapclose as GC
    w = GC.windows(name, H, n_max=n_max)
    return w


def data():
    os.makedirs(CACHE, exist_ok=True)
    import follow as F
    T = {n: table_queries(n) for n in F.DSETS}
    for n, q in T.items():
        print(n, len(q['v']), flush=True)
    ev = launch_events()
    LQ = {ds: launch_queries(e) for ds, e in ev.items()}
    LR = {ds: launch_rollouts(e) for ds, e in ev.items()}
    for ds in ev:
        print(ds, len(ev[ds]), 'queries', len(LQ[ds]['v']), 'rollouts', len(LR[ds]['v0']), flush=True)
    pickle.dump(dict(tables=T, launch_q=LQ, launch_r=LR), open(f'{CACHE}/sets.pkl', 'wb'))


def load_sets():
    return pickle.load(open(f'{CACHE}/sets.pkl', 'rb'))


# ---------------------------------------------------------------- F801 diagnostic
def gain():
    S = load_sets()
    bins = [(1.5, 3), (3, 6), (6, 10), (10, 15), (15, 25), (25, 40), (40, 70)]
    kg, kp = R2['k_g'], R2['k_p']

    def roll(q, lam, ca, idx):
        v, a, g = q['v'][idx].copy(), q['a'][idx].copy(), q['g'][idx].copy()
        VL, AL = q['VL'][idx, HIST:], q['AL'][idx, HIST:]
        v0 = v.copy()
        for k in range(VL.shape[1] - 1):
            vt = np.maximum(v, 6.5); gs = FD.S0 + (FD.t_gap(vt) - FD.S0 / vt) * v
            e = (g - gs) / np.maximum(v, 1.0)
            c = lam * (VL[:, k] - v) + ca * AL[:, k] + kp * np.maximum(e, 0) - kg * np.maximum(-e - 0.5, 0)
            a = a + BETA * (c - a)
            vn = np.maximum(v + a * DT, 0.0); a = (vn - v) / DT
            g = g + 0.5 * (VL[:, k] + VL[:, k + 1] - v - vn) * DT; v = vn
        return v - v0

    res = {}
    sets = dict(S['tables']); sets.update({f'launch {k}': v for k, v in S['launch_q'].items()})
    for name, q in sets.items():
        rows = []
        for lo, hi in bins:
            idx = np.flatnonzero((q['g'] >= lo) & (q['g'] < hi))
            if len(idx) < 150:
                continue
            r = least_squares(lambda p: roll(q, p[0], p[1], idx) - q['y'][idx], [0.3, 0.5], bounds=([0, -1], [5, 3]), loss='soft_l1', f_scale=0.5)
            gm = float(np.median(q['g'][idx]))
            # bootstrap by follower / launch
            grp = q['fid'][idx] if 'fid' in q else q['ev'][idx]
            u, inv = np.unique(grp, return_inverse=True)
            members = [np.flatnonzero(inv == j) for j in range(len(u))]
            bs = []
            for _ in range(15):
                pick = np.concatenate([members[j] for j in rng.integers(0, len(u), len(u))])
                ii = idx[pick]
                bs.append(least_squares(lambda p: roll(q, p[0], p[1], ii) - q['y'][ii], r.x, bounds=([0, -1], [5, 3]), loss='soft_l1', f_scale=0.5).x[0])
            rows.append(dict(gap=f'{lo}-{hi}', n=int(len(idx)), median_gap=round(gm, 1), median_v=round(float(np.median(q['v'][idx])), 1),
                             gain=round(float(r.x[0]), 3), gain_ci=[round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)],
                             c_a=round(float(r.x[1]), 3), gain_x_gap=round(float(r.x[0]) * gm, 2)))
            print(name, rows[-1], flush=True)
        res[name] = rows
    save('gain_by_gap', res)




# ---------------------------------------------------------------- 30 s windows with the leader's past
def windows_h(name, H, n_max=2000, every=25, open_only=False, seed=0):
    """gapclose.windows with 3 s of the leader's past and the shrunk own time gap factor of round 2."""
    import follow as F
    r = np.random.default_rng(20261108 + seed)
    d = F.load(name)
    d = d[d.lcar.astype(bool)].reset_index(drop=True)
    seg = d.seg.to_numpy(); n = len(d); S = int(round(H / DT))
    vf = d.vf.to_numpy(float); vl = d.vl.to_numpy(float); al = d.al.to_numpy(float); gap = d.gap.to_numpy(float)
    pos = _segpos(seg)
    ok = np.zeros(n, bool)
    ok[HIST:n - S] = (seg[HIST:n - S] == seg[:n - S - HIST]) & (seg[HIST:n - S] == seg[HIST + S:])
    ok &= (pos % every == 0) & (vf > 2.0) & (gap > 0.5) & (gap < 100)
    if open_only:
        ok &= (gap / np.maximum(vf, 1.0) - FD.t_gap(vf)) >= 1.0
    i = np.flatnonzero(ok)
    J = i[:, None] + np.arange(S + 1)[None, :]
    Jh = i[:, None] + np.arange(-HIST, 0)[None, :]
    good = np.isfinite(al[J]).all(1) & np.isfinite(vl[J]).all(1) & np.isfinite(vl[Jh]).all(1)
    i, J, Jh = i[good], J[good], Jh[good]
    if len(i) > n_max:
        pick = np.sort(r.choice(len(i), n_max, replace=False)); i, J, Jh = i[pick], J[pick], Jh[pick]
    tg = gap / np.maximum(vf, 0.1)
    st = (np.abs(vl - vf) < 1.0) & (vf > 5)
    ratio = np.where(st, tg / FD.t_gap(vf), np.nan)
    df = pd.DataFrame(dict(fid=d.fid.to_numpy(), seg=seg, lr=np.log(ratio)))
    by_fs = df.groupby(['fid', 'seg']).lr.agg(['sum', 'count']); by_f = df.groupby('fid').lr.agg(['sum', 'count'])
    fid = d.fid.to_numpy()[i]; sg = seg[i]
    tot = by_f.reindex(fid); own = by_fs.reindex(pd.MultiIndex.from_arrays([fid, sg]))
    cnt = tot['count'].to_numpy() - np.nan_to_num(own['count'].to_numpy())
    sm = tot['sum'].to_numpy() - np.nan_to_num(own['sum'].to_numpy())
    nw = np.maximum(cnt / 50.0, 1e-9); rho = 0.27 ** 2 / (0.27 ** 2 + (0.47 ** 2 - 0.27 ** 2) / nw)
    f_shrunk = np.where(cnt >= 25, np.exp(rho * sm / np.maximum(cnt, 1)), 1.0)
    xf = np.concatenate([[0], np.cumsum(0.5 * (vf[1:] + vf[:-1]) * DT)])
    return dict(name=name, H=H, fid=fid, v0=vf[i], a0=(vf[i] - vf[i - 2]) / (2 * DT), g=gap[J], vl=vl[J], al=al[J],
                xf=xf[J] - xf[J[:, :1]], VLh=np.concatenate([vl[Jh], vl[i][:, None]], 1), vf=vf[J], f=f_shrunk,
                vdes=float(np.percentile(vf[::7], 99)))


# ---------------------------------------------------------------- candidates
# Each takes p, the state and a context; returns the command behind this leader, m/s2. ctx: f, vlt (leader speed tau
# ago), Dt (leader distance over the last tau), vdes. All use the round 2 desired gap and band where they use a band.
def gstar(v, f):
    vt = np.maximum(v, 6.5)
    return FD.S0 + f * (FD.t_gap(vt) - FD.S0 / vt) * v


def band(v, g, f, kg, kp):
    e = (g - gstar(v, f)) / np.maximum(v, 1.0)
    return kp * np.maximum(e, 0.0) - kg * np.maximum(-e - FD.E_NEAR, 0.0)


def newell_tau(v, f):
    vt = np.maximum(v, 6.5)
    return f * (FD.t_gap(vt) - FD.S0 / vt)


_VG = np.linspace(0, 45, 451)
_HG = (FD.t_gap(np.maximum(_VG, 6.5)) - FD.S0 / np.maximum(_VG, 6.5)) * _VG


def V_of_gap(g, f, vdes):
    return np.minimum(np.interp((g - FD.S0) / f, _HG, _VG, left=0.0), vdes)


def c_a(p, v, g, vl, al, x):
    K, ca, kg, kp = p
    return K * np.minimum(vl - v, FD.DV_MAX) / np.maximum(g, 1.0) + ca * al + band(v, g, x['f'], kg, kp)


def c_b(p, v, g, vl, al, x):
    K, ca, kN = p
    eN = (g - FD.S0 - x['Dt']) / np.maximum(v, 1.0)
    return K * np.minimum(x['vlt'] - v, FD.DV_MAX) / np.maximum(g, 1.0) + ca * al + kN * eN


def c_c(p, v, g, vl, al, x):
    kap, lam, ca = p
    return kap * (V_of_gap(g, x['f'], x['vdes']) - v) + lam * (vl - v) + ca * al


def c_d(p, v, g, vl, al, x):
    am, b = p
    s = gstar(v, x['f']) + v * (v - vl) / (2 * np.sqrt(am * b))
    return am * (1 - (v / x['vdes']) ** 4 - (np.maximum(s, FD.S0) / np.maximum(g, 0.5)) ** 2)


def c_e(p, v, g, vl, al, x):
    K, ca, kg, kp, K1 = p
    launch = (v < 6.5) & (vl > v)
    return np.where(launch, K1 * np.minimum(vl - v, FD.DV_MAX) / np.maximum(g, 1.0), c_a([K, ca, kg, kp], v, g, vl, al, x))


def c_f(p, v, g, vl, al, x):
    K, g1, ca, kg, kp = p
    return K * np.minimum(vl - v, FD.DV_MAX) / (np.maximum(g, 0.0) + g1) + ca * al + band(v, g, x['f'], kg, kp)


def c_g(p, v, g, vl, al, x):
    K, t1, ca, kg, kp = p
    return K * np.minimum(vl - v, FD.DV_MAX) / (np.maximum(g, 1.0) + t1 * v) + ca * al + band(v, g, x['f'], kg, kp)


CANDS = {
    'a': dict(fn=c_a, names=['K', 'c_a', 'k_g', 'k_p'], p0=P_R2, lo=[0, 0, 0, 0], hi=[20, 2, 3, 1]),
    'b': dict(fn=c_b, names=['K', 'c_a', 'k_N'], p0=[2.7, 0.5, 0.1], lo=[0, 0, 0], hi=[20, 2, 5], newell=True),
    'c': dict(fn=c_c, names=['kappa', 'lambda', 'c_a'], p0=[0.05, 0.3, 0.5], lo=[0, 0, 0], hi=[3, 5, 2]),
    'd': dict(fn=c_d, names=['a_m', 'b'], p0=[1.5, 2.0], lo=[0.2, 0.2], hi=[6, 9]),
    'e': dict(fn=c_e, names=['K', 'c_a', 'k_g', 'k_p', 'K_1'], p0=P_R2 + [4.0], lo=[0, 0, 0, 0, 0], hi=[20, 2, 3, 1, 20]),
    'f': dict(fn=c_f, names=['K', 'g_1', 'c_a', 'k_g', 'k_p'], p0=[6.0, 5.0, 0.4, 0.28, 0.025], lo=[0, 0, 0, 0, 0], hi=[30, 40, 2, 3, 1]),
    'g': dict(fn=c_g, names=['K', 't_1', 'c_a', 'k_g', 'k_p'], p0=[5.0, 0.5, 0.4, 0.28, 0.025], lo=[0, 0, 0, 0, 0], hi=[30, 5, 2, 3, 1]),
}


# ---------------------------------------------------------------- the twin engine (kernel order, md_twin.py)
OU_SD, OU_T = 0.38, 0.75
OU_RHO = math.exp(-DT / OU_T)
OU_SCALE = OU_SD * math.sqrt(2 * (OU_T / DT) ** 2 * (DT / OU_T - 1 + math.exp(-DT / OU_T)))


def _leader_track(VLh, VL):
    """Leader speeds and positions over history and horizon, position 0 at the start of the horizon."""
    V = np.concatenate([VLh[:, :-1], VL], 1)
    X = np.concatenate([np.zeros((len(V), 1)), np.cumsum(0.5 * (V[:, 1:] + V[:, :-1]) * DT, 1)], 1)
    X = X - X[:, VLh.shape[1] - 1:VLh.shape[1]]
    return V, X


def _interp_rows(A, idx):
    i0 = np.clip(np.floor(idx).astype(int), 0, A.shape[1] - 1); i1 = np.clip(i0 + 1, 0, A.shape[1] - 1)
    w = np.clip(idx - np.floor(idx), 0, 1); r = np.arange(len(A))
    return A[r, i0] * (1 - w) + A[r, i1] * w


def roll(cand, p, v0, a0, xl, VL, AL, f, vdes, VLh=None, noise=None, keep=False):
    """One follower behind its recorded leader. xl: leader rear minus follower front at the start, plus the leader's path
    (n, S+1). Returns the follower's path and speed (n, S+1)."""
    C = CANDS[cand]; fn = C['fn']
    n, S1 = VL.shape
    v = v0.astype(float).copy(); a = np.clip(a0.astype(float), -3, 3); x = np.zeros(n); steps = np.zeros(n, int)
    ctx = dict(f=f, vdes=vdes)
    if C.get('newell'):
        Vh, Xh = _leader_track(VLh, VL); h0 = VLh.shape[1] - 1
    X = [x.copy()]; Vs = [v.copy()]
    for k in range(S1 - 1):
        g = xl[:, k] - x
        vl, al = VL[:, k], AL[:, k]
        if C.get('newell'):
            idx = h0 + k - newell_tau(v, f) / DT
            ctx['vlt'] = _interp_rows(Vh, idx); ctx['Dt'] = Xh[:, h0 + k] - _interp_rows(Xh, idx)
        c = fn(p, v, g, vl, al, ctx)
        free = np.minimum((vdes - v) / 1.0, MT.a_cap(v, DT))
        c = np.minimum(c, free)
        if noise is not None:
            c = c + np.where(v >= 0.5, noise[:, k], 0.0)
        an = a + BETA * (c - a)
        vn = np.maximum(v + an * DT, 0.0)
        vn = np.where(vl < 0.5 * v, np.minimum(vn, MT.stop_comfort(g - FD.S0 + vl ** 2 / 2.6, v, DT)), vn)
        ce = MT.cert(g, v, vl, a, DT)
        vn = np.where(ce <= 0, -1.0, np.minimum(np.maximum(vn, 0.0), ce))
        jerk = 8.3 / (0.3 + DT)
        floor = v - np.minimum(8.3, np.maximum(0, -a) + 8.3 * DT / (0.3 + DT)) * DT
        release = np.where(a >= 0, 1e9, v + (a + jerk * DT) * DT)
        vn = np.where(vn < 0, floor, np.maximum(np.minimum(vn, release), floor))
        stand = v < 0.05; still = (vl < 1e-3) & (g < 15.0)
        steps = np.where(stand & still, 0, np.where(stand & (vn > 0), steps + 1, steps))
        waited = steps * DT
        held = np.where(still | (steps == 0) | (waited + DT <= 1.0 + 1e-3), 0.0, np.where(waited < 1.0 - 1e-3, vn * (waited + DT - 1.0) / DT, vn))
        vn = np.where(stand, held, vn)
        acc = (vn - v) / DT; vn = np.maximum(vn, 0.0)
        ds = np.where(vn > 0, v * DT + 0.5 * acc * DT * DT, np.where(acc < 0, v * v / (2 * np.maximum(-acc, 1e-9)), 0.0))
        a = np.where(vn > 0, acc, 0.0); x = x + ds; v = vn
        X.append(x.copy()); Vs.append(v.copy())
    return np.stack(X, 1), np.stack(Vs, 1)


def ou(n, steps, seed):
    r = np.random.default_rng(seed)
    z = r.standard_normal(n); out = []
    for _ in range(steps):
        out.append(OU_SCALE * z); z = OU_RHO * z + math.sqrt(1 - OU_RHO ** 2) * r.standard_normal(n)
    return np.stack(out, 1)


# ---------------------------------------------------------------- set adapters
def q_args(q, idx=None):
    """Next-second query set -> roll() arguments."""
    s = slice(None) if idx is None else idx
    VL = q['VL'][s, HIST:]; AL = q['AL'][s, HIST:]
    xl = q['g'][s][:, None] + np.concatenate([np.zeros((len(VL), 1)), np.cumsum(0.5 * (VL[:, 1:] + VL[:, :-1]) * DT, 1)], 1)
    n = len(VL)
    return dict(v0=q['v'][s], a0=q['a'][s], xl=xl, VL=VL, AL=AL, f=np.ones(n), vdes=q.get('vdes_arr', np.full(n, q['vdes']))[s] if 'vdes_arr' in q else q['vdes'],
                VLh=q['VL'][s, :HIST + 1])


def w_args(w):
    """Window set (launch rollouts or 30 s windows) -> roll() arguments."""
    n = len(w['v0'])
    return dict(v0=w['v0'], a0=w['a0'], xl=w['g'] + w['xf'], VL=w['vl'], AL=w['al'], f=w.get('f', np.ones(n)), vdes=w['vdes'], VLh=w['VLh'])


def sub(w, m):
    return {k: (v[m] if isinstance(v, np.ndarray) and v.shape[:1] == (len(w['v0']) if 'v0' in w else len(w['v'])) else v) for k, v in w.items()}


# ---------------------------------------------------------------- the joint objective (P1 + P2 + P6)
FIT_TABLES = ['highD', 'HT', 'I90stat', 'I294L1', 'I395']
ROLL_TABLES = ['HT', 'I90stat', 'I294L1', 'I395']
LAUNCH_AT = (2.0, 4.0, 6.0, 8.0)


def fit_sets():
    p = f'{CACHE}/fitsets.pkl'
    if os.path.exists(p):
        return pickle.load(open(p, 'rb'))
    S = load_sets()
    r = np.random.default_rng(5)
    nx = {}
    for n, q in S['tables'].items():
        q['vdes'] = 1e3
        idx = np.sort(r.choice(len(q['v']), min(2500, len(q['v'])), replace=False))
        nx[n] = sub(q, idx)
    w30 = {n: windows_h(n, 30, n_max=800) for n in ROLL_TABLES}
    op = {n: windows_h(n, 30, n_max=3000, open_only=True, seed=1) for n in ROLL_TABLES}
    out = dict(next=nx, w30=w30, open=op, launch=S['launch_r'])
    pickle.dump(out, open(p, 'wb'))
    return out


def next_pred(cand, p, q, noise=None):
    A = q_args(q)
    X, V = roll(cand, p, noise=noise, **A)
    return V[:, -1] - q['v']


def w_err(cand, p, w, noise=None):
    """Spacing error x_sim - x_rec along the window (positive: the model ahead, its gap smaller), and speeds."""
    A = w_args(w)
    X, V = roll(cand, p, noise=noise, **A)
    return X - w['xf'], V


def _soft(z):
    return np.sign(z) * np.sqrt(2 * (np.sqrt(1 + z * z) - 1))


def objective(cand, p, FS, scale):
    r = []
    for n in FIT_TABLES:
        q = FS['next'][n]
        r.append(_soft((next_pred(cand, p, q) - q['y']) / scale[f'next {n}']) / math.sqrt(len(q['y'])))
    for n in ROLL_TABLES:
        e, _ = w_err(cand, p, FS['w30'][n])
        z = e[:, [50, 150]] / scale[f'w30 {n}']
        r.append(_soft(z.ravel()) / math.sqrt(z.size))
    for ds in LAUNCH_SITES:
        e, _ = w_err(cand, p, FS['launch'][ds])
        z = e[:, [int(t / DT) for t in LAUNCH_AT]] / scale[f'launch {ds}']
        r.append(_soft(z.ravel()) / math.sqrt(z.size))
    return np.concatenate(r)


def scales(FS):
    """Each data set's round 2 RMS, so that every set weighs 1 at the round 2 law."""
    s = {}
    for n in FIT_TABLES:
        q = FS['next'][n]; s[f'next {n}'] = float(np.sqrt(np.mean((next_pred('a', P_R2, q) - q['y']) ** 2)))
    for n in ROLL_TABLES:
        e, _ = w_err('a', P_R2, FS['w30'][n]); s[f'w30 {n}'] = float(np.sqrt(np.mean(e[:, [50, 150]] ** 2)))
    for ds in LAUNCH_SITES:
        e, _ = w_err('a', P_R2, FS['launch'][ds]); s[f'launch {ds}'] = float(np.sqrt(np.mean(e[:, [int(t / DT) for t in LAUNCH_AT]] ** 2)))
    return s


# ---------------------------------------------------------------- platoon twin (md_platoon.py with any candidate)
LCAR = 5.0
GAP_SD = 0.27 * math.sqrt(1 - 0.41 ** 2)
R1 = json.load(open(FD.OUTJ))['launch']['first_react']


def platoon(cand, p, x0, v0, vdes, T, dt=0.25, green=None, seed=0, noise=True, lead_trace=None, fvar=True):
    C = CANDS[cand]; fn = C['fn']
    r = np.random.default_rng(seed)
    n = len(x0)
    f = np.exp(GAP_SD * r.standard_normal(n)) if fvar else np.ones(n)
    x, v, a = np.array(x0, float), np.array(v0, float), np.zeros(n)
    beta = 1 - math.exp(-dt / FD.TAU_R)
    rho = math.exp(-dt / OU_T); scale = OU_SD * math.sqrt(2 * (OU_T / dt) ** 2 * (dt / OU_T - 1 + math.exp(-dt / OU_T)))
    z = r.standard_normal(n)
    moved = np.full(n, np.inf)
    HX, HV = [x.copy()], [v.copy()]
    t = 0.0
    for k in range(int(T / dt)):
        t1 = t + dt
        vd = np.full(n, float(vdes))
        if lead_trace is not None:
            vd[0] = lead_trace(t1)
        g = np.r_[np.inf, x[:-1] - LCAR - x[1:]]
        vl = np.r_[0.0, v[:-1]]; al = np.r_[0.0, a[:-1]]
        lead = np.r_[False, np.ones(n - 1, bool)]
        alone = ~lead | (g > 100)
        eng = MT.a_cap(v, dt)
        free = np.minimum((vd - v) / 1.0, eng)
        free = np.where(alone, np.minimum(free, np.maximum(2.02 - 0.125 * v, 0.7)), free)
        ctx = dict(f=f, vdes=vd)
        if C.get('newell'):
            tau = newell_tau(v, f)
            kb = len(HX) - 1 - tau / dt
            Hx = np.array(HX); Hv = np.array(HV)
            i0 = np.clip(np.floor(kb).astype(int), 0, len(HX) - 1); i1 = np.clip(i0 + 1, 0, len(HX) - 1); w_ = np.clip(kb - np.floor(kb), 0, 1)
            lead_idx = np.r_[0, np.arange(n - 1)]
            xt = Hx[i0, lead_idx] * (1 - w_) + Hx[i1, lead_idx] * w_
            ctx['vlt'] = Hv[i0, lead_idx] * (1 - w_) + Hv[i1, lead_idx] * w_
            ctx['Dt'] = x[lead_idx] - xt
        gg = np.where(lead, g, 1e3)
        af = fn(p, v, gg, vl, al, ctx)
        cmd = np.where(lead, np.minimum(af, free), free)
        nz = np.where(v >= 0.5, z * scale, 0.0) if noise else 0.0
        vn = np.maximum(v + (a + beta * (cmd + nz - a)) * dt, 0.0)
        vn = np.where(lead & (vl < 0.5 * v), np.minimum(vn, MT.stop_comfort(g - FD.S0 + vl * vl / 2.6, v, dt)), vn)
        c = np.where(lead, MT.cert(np.where(lead, g, 1e3), v, vl, a, dt), np.inf)
        if green is not None and t1 < green:
            c[0] = min(c[0], 0.0)
        vn = np.where(c <= 0, -1.0, np.minimum(vn, c))
        jerk = 8.3 / 0.3 if dt >= 0.3 else 8.3 / (0.3 + dt)
        floor = v - np.minimum(8.3, np.maximum(0, -a) + (8.3 * dt / (0.3 + dt) if dt < 0.3 else 8.3)) * dt
        release = np.where(a >= 0, 1e9, v + (a + jerk * dt) * dt)
        vn = np.where(vn < 0, floor, np.maximum(np.minimum(vn, release), floor))
        stand = v < 0.05
        open_t = np.r_[green + R1 if green is not None else -np.inf, moved[:-1] + 1.0]
        hold = stand & (t1 < open_t - 1e-6)
        part = stand & ~hold & (t1 - dt < open_t)
        vn = np.where(hold, 0.0, np.where(part, vn * np.clip((t1 - open_t) / dt, 0, 1), vn))
        acc = (vn - v) / dt
        vn = np.maximum(vn, 0.0)
        ds = np.where(vn > 0, v * dt + 0.5 * acc * dt * dt, np.where(acc < 0, v * v / (2 * np.maximum(-acc, 1e-9)), 0.0))
        a = np.where(vn > 0, acc, 0.0)
        moved = np.where(np.isinf(moved) & (vn > 1e-3), t1, moved)
        x = x + ds; v = vn
        z = rho * z + math.sqrt(1 - rho * rho) * r.standard_normal(n)
        t = t1
        HX.append(x.copy()); HV.append(v.copy())
    return np.arange(len(HX)) * dt, np.array(HX), np.array(HV)


def crossings(T, X, at):
    out = []
    for i in range(X.shape[1]):
        k = int(np.argmax(X[:, i] >= at))
        if X[k, i] < at:
            out.append(np.nan); continue
        out.append(T[k - 1] + (at - X[k - 1, i]) / max(X[k, i] - X[k - 1, i], 1e-9) * (T[k] - T[k - 1]) if k else T[0])
    return np.array(out)


def queue_x(n, d0=1.0):
    return [-d0 - i * (LCAR + FD.S0) for i in range(n)]


def platoon_patterns(cand, p, seeds=20):
    out = {}
    # P4: a standing queue of 6, the head drives off to a crawl at v_c and holds it; the followers' gap over the last 10 s of 60
    low = {}
    for vc in (1.0, 2.0, 3.0, 5.0):
        T, X, V = platoon(cand, p, queue_x(6), np.zeros(6), 13.9, 60.0, seed=0, noise=False, fvar=False, lead_trace=lambda t, vc=vc: vc)
        G = X[:, :-1] - LCAR - X[:, 1:]
        low[str(vc)] = round(float(np.median(G[-40:, :])), 2)
    out['P4_gap_at_1_2_3_5'] = low
    # P5: six cars at 8 m/s on their desired gap; the head stops at 1.5 m/s2; gaps 20 s after the head stands
    x0 = np.cumsum(np.r_[0, -np.full(5, LCAR + float(gstar(8.0, 1.0)))])
    T, X, V = platoon(cand, p, x0, np.full(6, 8.0), 8.0, 50.0, seed=0, noise=False, fvar=False, lead_trace=lambda t: max(0.0, 8.0 - 1.5 * max(t - 10, 0)))
    G = X[-1, :-1] - LCAR - X[-1, 1:]
    out['P5_standstill_gap'] = round(float(np.median(G)), 2)
    # P7 P8 P9: a standing queue of 10, the head 1 m behind the line, green at 0
    rows = []
    for s in range(seeds):
        T, X, V = platoon(cand, p, queue_x(10), np.zeros(10), 13.9, 40.0, green=0.0, seed=s)
        go = np.array([crossings(T, V[:, [i]], 1.0)[0] for i in range(10)])
        line = X[0, 0] + 1.0 + 0.0
        cr = crossings(T, X, line)
        for i in range(1, 10):
            rows.append(dict(seed=s, pos=i + 1, delay=go[i] - go[i - 1], hw=cr[i] - cr[i - 1], go=go[i], x0=X[0, i]))
    d = pd.DataFrame(rows)
    out['P7_start_delay_by_pos'] = {int(k): round(float(g.delay.median()), 2) for k, g in d[d.pos <= 6].groupby('pos')}
    sl = np.polyfit(d[d.pos <= 6].pos, d[d.pos <= 6].delay, 1)[0]
    out['P7_trend_s_per_pos'] = round(float(sl), 3)
    out['P8_line_headway_by_pos'] = {int(k): round(float(g.hw.median()), 2) for k, g in d.groupby('pos')}
    wv = np.polyfit(d.go, d.x0, 1)[0]
    out['P9_start_wave_kmh'] = round(float(-wv * 3.6), 1)
    # P12: L1 capacity at 50 and 100 km/h (released queue, count past 300 / 1200 m from car 10, 300 s), S1 headway from car 10
    for kmh in (50, 100):
        at = 1200.0 if kmh == 100 else 300.0
        caps = []
        for s in range(5):
            T, X, V = platoon(cand, p, queue_x(120, 1.5), np.zeros(120), kmh / 3.6, 260.0, green=0.0, seed=s)
            c = crossings(T, X, at); w = c[10:]; w = w[np.isfinite(w)]; w = w[w <= w[0] + 300]
            caps.append(3600 * (len(w) - 1) / (w[-1] - w[0]))
        out[f'P12_L1_{kmh}'] = round(float(np.mean(caps)))
    hs = []
    for s in range(10):
        T, X, V = platoon(cand, p, queue_x(25, 1.5), np.zeros(25), 50 / 3.6, 120.0, green=0.0, seed=s)
        c = crossings(T, X, 0.0); hs.append(np.nanmean(np.diff(c)[9:]))
    out['P12_S1_headway'] = round(float(np.mean(hs)), 2)
    # P3 (reported): the gap a follower keeps behind a steady leader after 120 s, started on T(v) and 1 s above it
    p3 = {}
    for vv in (10.0, 20.0, 30.0):
        res = []
        for ex in (0.0, 1.0):
            g0 = float(gstar(vv, 1.0)) + ex * vv
            T, X, V = platoon(cand, p, [0.0, -(LCAR + g0)], np.full(2, vv), vv + 3, 120.0, noise=False, fvar=False, lead_trace=lambda t, vv=vv: vv)
            res.append(round(float((X[-1, 0] - LCAR - X[-1, 1]) / vv), 2))
        p3[str(vv)] = res
    out['P3_time_gap_after_120s_from_T_and_T+1'] = p3
    return out


# ---------------------------------------------------------------- scoring every pattern
def crps_ens(X, y):
    """X: (n, m) ensemble, y: (n,). Mean CRPS."""
    m = X.shape[1]
    t1 = np.mean(np.abs(X - y[:, None]), 1)
    Xs = np.sort(X, 1); w = (2 * np.arange(1, m + 1) - m - 1) / (m * m)
    t2 = np.sum(Xs * w, 1)          # = 0.5 E|X - X'|
    return float(np.mean(t1 - t2))


def score_data(cand, p, FS, members=20):
    out = {}
    # P1: next-second CRPS with the frozen command noise, against constant speed
    for n in FIT_TABLES:
        q = FS['next'][n]; A = q_args(q); N = len(q['y'])
        ens = np.stack([roll(cand, p, noise=ou(N, 6, 100 + m), **A)[1][:, -1] - q['v'] for m in range(members)], 1)
        det = next_pred(cand, p, q)
        out[f'P1 {n}'] = dict(crps=round(crps_ens(ens, q['y']), 4), null=round(float(np.mean(np.abs(q['y']))), 4),
                              rmse=round(float(np.sqrt(np.mean((det - q['y']) ** 2))), 4))
    # P2: open gaps over 30 s (closed share of the median excess), and 30 s spacing RMSE on ordinary windows
    for n in ROLL_TABLES:
        w = FS['open'][n]
        e, V = w_err(cand, p, w)
        g = w['g'] - e
        ex_m = g / np.maximum(V, 1.0) - FD.t_gap(V)
        ex_r = w['g'] / np.maximum(w['vf'], 1.0) - FD.t_gap(w['vf'])
        r = {}
        for H in (10, 30):
            j = int(H / DT)
            rec = 1 - np.median(ex_r[:, j]) / np.median(ex_r[:, 0]); mod = 1 - np.median(ex_m[:, j]) / np.median(ex_r[:, 0])
            r[f'closed_{H}s'] = [round(float(rec), 3), round(float(mod), 3)]
        e30, _ = w_err(cand, p, FS['w30'][n])
        r['rmse_30s'] = round(float(np.sqrt(np.mean(e30[:, 150] ** 2))), 3)
        r['windows_open'] = int(len(w['v0']))
        out[f'P2 {n}'] = r
    # P6: launches, median gap error (positive: the model behind, its gap larger) at 2, 4, 8 s
    for ds in LAUNCH_SITES + LAUNCH_REPORT:
        if ds not in FS['launch'] or len(FS['launch'][ds]['v0']) < 5:
            continue
        w = FS['launch'][ds]
        e, _ = w_err(cand, p, w)
        r = {}
        for t in (2, 4, 8):
            ge = -e[:, int(t / DT)]
            bs = [np.median(ge[rng.integers(0, len(ge), len(ge))]) for _ in range(300)]
            r[f'{t}s'] = [round(float(np.median(ge)), 2), round(float(np.percentile(bs, 2.5)), 2), round(float(np.percentile(bs, 97.5)), 2)]
        r['n'] = int(len(ge))
        out[f'P6 {ds}'] = r
    return out


LIM = dict(P4={'1.0': (2.4, 4.2), '2.0': (3.7, 5.1), '3.0': (4.8, 6.2), '5.0': (5.8, 8.9)}, P5=(1.6, 2.0), P7=(1.0, 1.45), P7_trend=0.1,
           P8={2: 2.99, 3: 2.34, 6: 1.97}, P8_tol=0.35, P9=(17, 26), P12_L1=(1640, 1900), P12_S1=(1.8, 2.2),
           P6={'2s': 0.5, '4s': 0.5, '8s': 1.0}, P2=0.15, P2_rmse=1.05, P1=1.10)


def verdict(sc, ref):
    """Every filter pattern against its F800 interval. ref: the round 2 law's scores (for P1 and P2's RMSE)."""
    miss = []
    for n in FIT_TABLES:
        s = sc[f'P1 {n}']
        if not (s['crps'] < s['null'] and s['crps'] <= LIM['P1'] * ref[f'P1 {n}']['crps']):
            miss.append(f"P1 {n}: CRPS {s['crps']} (round 2 {ref[f'P1 {n}']['crps']}, null {s['null']})")
    for n in ROLL_TABLES:
        s = sc[f'P2 {n}']
        rec, mod = s['closed_30s']
        if abs(mod - rec) > LIM['P2']:
            miss.append(f'P2 {n}: closed {mod:.2f} in 30 s against {rec:.2f}')
        if s['rmse_30s'] > LIM['P2_rmse'] * ref[f'P2 {n}']['rmse_30s']:
            miss.append(f"P2 {n}: 30 s RMSE {s['rmse_30s']} against round 2 {ref[f'P2 {n}']['rmse_30s']}")
    for k, (lo, hi) in LIM['P4'].items():
        x = sc['P4_gap_at_1_2_3_5'][k]
        if not lo <= x <= hi:
            miss.append(f'P4 {k} m/s: gap {x} m outside {lo}-{hi}')
    if not LIM['P5'][0] <= sc['P5_standstill_gap'] <= LIM['P5'][1]:
        miss.append(f"P5: {sc['P5_standstill_gap']} m")
    for ds in LAUNCH_SITES:
        for t, m in LIM['P6'].items():
            x = sc[f'P6 {ds}'][t][0]
            if abs(x) > m:
                miss.append(f'P6 {ds} {t}: gap error {x:+.2f} m')
    for pos, x in sc['P7_start_delay_by_pos'].items():
        if not LIM['P7'][0] <= x <= LIM['P7'][1]:
            miss.append(f'P7 position {pos}: {x} s')
    if abs(sc['P7_trend_s_per_pos']) > LIM['P7_trend']:
        miss.append(f"P7 trend {sc['P7_trend_s_per_pos']} s per position")
    for pos, x in LIM['P8'].items():
        y = sc['P8_line_headway_by_pos'].get(pos, np.nan)
        if not abs(y - x) <= LIM['P8_tol']:
            miss.append(f'P8 position {pos}: {y} s against {x}')
    if not LIM['P9'][0] <= sc['P9_start_wave_kmh'] <= LIM['P9'][1]:
        miss.append(f"P9: {sc['P9_start_wave_kmh']} km/h")
    for kmh in (50, 100):
        x = sc[f'P12_L1_{kmh}']
        if not LIM['P12_L1'][0] <= x <= LIM['P12_L1'][1]:
            miss.append(f'P12 L1 {kmh}: {x} veh/h')
    if not LIM['P12_S1'][0] <= sc['P12_S1_headway'] <= LIM['P12_S1'][1]:
        miss.append(f"P12 S1: {sc['P12_S1_headway']} s")
    return miss


def score_all(cand, p, FS):
    sc = score_data(cand, p, FS)
    sc.update(platoon_patterns(cand, p))
    return sc


def fit(cand, FS, sc_):
    C = CANDS[cand]
    r = least_squares(lambda q: objective(cand, list(q), FS, sc_), C['p0'], bounds=(C['lo'], C['hi']), diff_step=1e-3, max_nfev=200)
    return list(map(float, r.x)), float(np.sum(r.fun ** 2))


def run_filter(which):
    FS = fit_sets()
    sc_ = scales(FS)
    print('scales', json.dumps({k: round(v, 3) for k, v in sc_.items()}), flush=True)
    res = json.load(open(OUT)).get('filter', {}) if os.path.exists(OUT) else {}
    if 'round2' not in res:
        ref = score_all('a', P_R2, FS)
        res['round2'] = dict(params=dict(zip(CANDS['a']['names'], P_R2)), scores=ref, objective=float(np.sum(objective('a', P_R2, FS, sc_) ** 2)))
        res['round2']['misses'] = verdict(ref, ref)
        save('filter', res)
        print('round2', res['round2']['misses'], flush=True)
    ref = res['round2']['scores']
    for cand in which:
        p, obj = fit(cand, FS, sc_)
        sc = score_all(cand, p, FS)
        miss = verdict(sc, ref)
        res[cand] = dict(params={k: round(v, 4) for k, v in zip(CANDS[cand]['names'], p)}, objective=round(obj, 4), scores=sc, misses=miss,
                         survives=not miss)
        print(cand, res[cand]['params'], 'obj', round(obj, 4), 'misses', len(miss), miss, flush=True)
        res = {**(json.load(open(OUT)).get('filter', {}) if os.path.exists(OUT) else {}), cand: res[cand], 'round2': res['round2']}
        save('filter', res)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'data':
        data()
    elif cmd == 'gain':
        gain()
    elif cmd == 'filter':
        run_filter(sys.argv[2:] or list(CANDS))


def run_profile(cands=('f', 'e'), kp=0.025):
    """F809: refit with k_p held, score every pattern."""
    FS = fit_sets(); sc_ = scales(FS)
    res = json.load(open(OUT)); ref = res['filter']['round2']['scores']; out = {}
    for cand in cands:
        C = CANDS[cand]; j = C['names'].index('k_p')
        keep = [i for i in range(len(C['names'])) if i != j]
        full = lambda q: [q[keep.index(i)] if i != j else kp for i in range(len(C['names']))]
        r = least_squares(lambda q: objective(cand, full(list(q)), FS, sc_), [C['p0'][i] for i in keep],
                          bounds=([C['lo'][i] for i in keep], [C['hi'][i] for i in keep]), diff_step=1e-3, max_nfev=200)
        p = full(list(map(float, r.x)))
        sc = score_all(cand, p, FS); miss = verdict(sc, ref)
        out[cand] = dict(params={k: round(v, 4) for k, v in zip(C['names'], p)}, objective=round(float(np.sum(r.fun ** 2)), 4), scores=sc, misses=miss)
        print(cand, out[cand]['params'], len(miss), miss, flush=True)
    save(f'profile_kp_{kp}', out)


if __name__ == '__main__' and sys.argv[1] == 'profile':
    run_profile()
