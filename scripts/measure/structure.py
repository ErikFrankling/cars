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


if __name__ == '__main__':
    {'data': data, 'gain': gain}[sys.argv[1]]()
