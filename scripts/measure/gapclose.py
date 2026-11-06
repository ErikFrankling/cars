"""Round 2 of the measured driver: how open gaps close, on the follower tables of follow.py, none held out (HOLDOUT.md):
highD without location 6, DLR HT 06-14 UTC, TGSIM I-90/94 stationary, I-294 L1, I-395. Forecasts F602-F608.

    python3 -I scripts/measure/gapclose.py selection   # F602 F603: steady windows against all following; the attractor
    python3 -I scripts/measure/gapclose.py profile     # F604: the one-second objective against k_p
    python3 -I scripts/measure/gapclose.py horizons    # F605 F606: k_p (and the joint law) on 1, 10, 30 s rollouts
    python3 -I scripts/measure/gapclose.py relax       # F607 F608: open gaps over 30 s, recordings against the model

Results go to research/truth/measure/gapclose.json, one key per command.
"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import follow as F
import fit_driver as FD

RES = os.path.join(HERE, '..', '..', 'research', 'truth', 'measure')
OUT = os.path.join(RES, 'gapclose.json')
rng = np.random.default_rng(20261108)
DT = 0.2
R1 = json.load(open(FD.OUTJ))['pooled']
P1 = [R1['K'], R1['c_a'], R1['k_g'], R1['k_p']]


def save(key, val):
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    out[key] = val
    json.dump(out, open(OUT, 'w'), indent=1)


def boot(stat, groups, x, reps=300):
    """Statistic with a 95% interval from resampling groups (followers)."""
    g = pd.factorize(groups)[0]
    idx = pd.Series(np.arange(len(g))).groupby(g).apply(np.array).to_list()
    vals = []
    for _ in range(reps):
        pick = rng.integers(0, len(idx), len(idx))
        ii = np.concatenate([idx[i] for i in pick])
        vals.append(stat(x[ii] if not isinstance(x, tuple) else tuple(a[ii] for a in x)))
    return [round(float(stat(x)), 3), round(float(np.nanpercentile(vals, 2.5)), 3), round(float(np.nanpercentile(vals, 97.5)), 3)]


# ---------------------------------------------------------------- F602 F603 selection
def selection():
    res = {}
    for name in F.DSETS:
        d = F.load(name)
        d = d[d.lcar.astype(bool)].reset_index(drop=True)
        band = (25, 35) if name in ('highD', 'HT') else (15, 25)
        r = dict(band_m_s=list(band))
        # Steady windows, DRIVER.md's definition, median of each window, within the band.
        w = F.steady_windows(d, 3.0)
        w = w[(w.v >= band[0]) & (w.v < band[1])]
        r['steady_windows'] = dict(n=len(w), median=boot(np.median, w.fid.to_numpy(), w.tg.to_numpy()))
        # All following: one median per segment of at least 5 s inside the band, gap under 100 m.
        m = (d.vf >= band[0]) & (d.vf < band[1]) & (d.gap > 0.3) & (d.gap < 100)
        k = d[m]
        tg = (k.gap / k.vf)
        g = pd.DataFrame(dict(seg=k.seg, fid=k.fid, tg=tg)).groupby('seg').agg(fid=('fid', 'first'), tg=('tg', 'median'), n=('tg', 'size'))
        g = g[g.n >= 25]
        r['all_following_segments'] = dict(n=len(g), median=boot(np.median, g.fid.to_numpy(), g.tg.to_numpy()),
                                          p5_p95=[round(float(g.tg.quantile(.05)), 3), round(float(g.tg.quantile(.95)), 3)])
        r['all_following_samples_median'] = round(float(tg.median()), 3)
        # Relaxed steadiness: 10 s windows whose mean |dv| is small but samples may exceed 1 m/s; and whose gap may drift.
        # Attractor: mean gap change over the next 10 s against the time gap now, same segment, in the band.
        seg = d.seg.to_numpy(); n = len(d); H = 50
        ok = np.zeros(n, bool); ok[:n - H] = seg[:n - H] == seg[H:]
        gap = d.gap.to_numpy(); vf = d.vf.to_numpy(); vl = d.vl.to_numpy()
        i = np.flatnonzero(ok & m.to_numpy() & (np.arange(n) % 5 == 0))
        tg0 = gap[i] / vf[i]
        dg = (gap[i + H] - gap[i]) / (H * DT)          # mean closing speed over 10 s, m/s (negative closes)
        dtg = gap[i + H] / np.maximum(vf[i + H], 1) - tg0
        dvl = vl[i + H] - vl[i]
        bins = np.arange(0.3, 3.01, 0.1)
        rows = []
        for lo in bins[:-1]:
            mm = (tg0 >= lo) & (tg0 < lo + 0.1)
            if mm.sum() >= 40:
                rows.append([round(lo + 0.05, 2), int(mm.sum()), round(float(dg[mm].mean()), 3), round(float(dtg[mm].mean()), 3),
                             round(float(dvl[mm].mean()), 3)])
        r['drift_by_time_gap'] = dict(cols=['tg_mid', 'n', 'mean_gap_rate_m_s', 'mean_time_gap_change_10s', 'leader_speed_change'], rows=rows)
        # Zero crossing of the mean time-gap change (the attractor), with a follower bootstrap.
        def cross(a):
            t0, x = a
            mids, vals = [], []
            for lo in bins[:-1]:
                mm = (t0 >= lo) & (t0 < lo + 0.1)
                if mm.sum() >= 20:
                    mids.append(lo + 0.05); vals.append(x[mm].mean())
            mids, vals = np.array(mids), np.array(vals)
            s = np.flatnonzero((vals[:-1] > 0) & (vals[1:] <= 0))
            if not len(s):
                return np.nan
            j = s[0]
            return mids[j] + (mids[j + 1] - mids[j]) * vals[j] / (vals[j] - vals[j + 1])
        r['attractor_time_gap'] = boot(cross, d.fid.to_numpy()[i], (tg0, dtg), reps=200)
        # Same, holding the leader's speed nearly constant over the 10 s (|change| under 1 m/s).
        st = np.abs(dvl) < 1.0
        r['attractor_time_gap_leader_steady'] = boot(cross, d.fid.to_numpy()[i][st], (tg0[st], dtg[st]), reps=200)
        res[name] = r
        print(name, json.dumps(r)[:900], flush=True)
    save('selection', res)


# ---------------------------------------------------------------- rollouts from the tables
def windows(name, H, n_max=3000, every=25, vmin=2.0):
    """Windows of H seconds inside one leader-follower segment: state at the start, the recorded leader and follower."""
    d = F.load(name)
    d = d[d.lcar.astype(bool)].reset_index(drop=True)
    seg = d.seg.to_numpy(); n = len(d); S = int(round(H / DT))
    vf = d.vf.to_numpy(float); vl = d.vl.to_numpy(float); al = d.al.to_numpy(float); gap = d.gap.to_numpy(float)
    start = np.r_[0, np.flatnonzero(np.diff(seg)) + 1]
    pos = np.arange(n) - np.repeat(start, np.diff(np.r_[start, n]))
    ok = np.zeros(n, bool)
    ok[2:n - S] = (seg[2:n - S] == seg[:n - S - 2]) & (seg[2:n - S] == seg[2 + S:])
    ok &= (pos % every == 0) & (vf > vmin) & (gap > 0.5) & (gap < 100)
    i = np.flatnonzero(ok)
    J = i[:, None] + np.arange(S + 1)[None, :]
    good = np.isfinite(al[J]).all(1) & np.isfinite(vl[J]).all(1)
    i, J = i[good], J[good]
    if len(i) > n_max:
        pick = np.sort(rng.choice(len(i), n_max, replace=False)); i, J = i[pick], J[pick]
    # The follower's own time gap factor from its other segments (other leaders), where it has any steady following there.
    tg = gap / np.maximum(vf, 0.1)
    st = (np.abs(vl - vf) < 1.0) & (vf > 5)
    ratio = np.where(st, tg / FD.t_gap(vf), np.nan)
    df = pd.DataFrame(dict(fid=d.fid.to_numpy(), seg=seg, lr=np.log(ratio)))
    by_fs = df.groupby(['fid', 'seg']).lr.agg(['sum', 'count'])
    by_f = df.groupby('fid').lr.agg(['sum', 'count'])
    fid = d.fid.to_numpy()[i]; sg = seg[i]
    tot = by_f.reindex(fid); own = by_fs.reindex(pd.MultiIndex.from_arrays([fid, sg]))
    cnt = tot['count'].to_numpy() - np.nan_to_num(own['count'].to_numpy())
    sm = tot['sum'].to_numpy() - np.nan_to_num(own['sum'].to_numpy())
    f_other = np.where(cnt >= 25, np.exp(sm / np.maximum(cnt, 1)), np.nan)
    # Shrunk towards 1 by its reliability: DRIVER.md's persistent log-SD 0.27 against the 0.47 between 10 s windows,
    # with one window per 10 s of other steady following.
    nw = np.maximum(cnt / 50.0, 1e-9); rho = 0.27 ** 2 / (0.27 ** 2 + (0.47 ** 2 - 0.27 ** 2) / nw)
    f_shrunk = np.where(cnt >= 25, np.exp(rho * sm / np.maximum(cnt, 1)), 1.0)
    f_track = np.exp(tot['sum'].to_numpy() / np.maximum(tot['count'].to_numpy(), 1))
    xf = np.concatenate([[0], np.cumsum(0.5 * (vf[1:] + vf[:-1]) * DT)])
    return dict(name=name, H=H, fid=fid, v0=vf[i], a0=(vf[i] - vf[i - 2]) / (2 * DT), g=gap[J], vf=vf[J], vl=vl[J], al=al[J],
                xf=xf[J] - xf[J[:, :1]], vdes=float(np.percentile(vf[::7], 99)), f_other=f_other, f_track=f_track, f_shrunk=f_shrunk)


def rollout(w, p, f=None, tv=1.0, noise=None, return_all=False):
    """The kernel's equations (md_twin.py) from the recorded state at the window start, behind the recorded leader, dt 0.2.
    p = K, c_a, k_g, k_p. Returns the spacing error x_sim - x_rec (positive: the model is ahead, the gap smaller)."""
    import md_twin_lite as MT
    N, S1 = w['g'].shape
    beta = 1 - np.exp(-DT / FD.TAU_R)
    v = w['v0'].copy(); a = np.clip(w['a0'].copy(), -3, 3); x = np.zeros(N); steps = np.zeros(N, int)
    f = np.ones(N) if f is None else f
    xs = [x.copy()]; vs = [v.copy()]
    for k in range(S1 - 1):
        g = w['g'][:, k] + w['xf'][:, k] - x
        vl, al = w['vl'][:, k], w['al'][:, k]
        c = FD.command(v, g, vl, al, p, f=f)
        free = np.minimum((w['vdes'] - v) / tv, MT.a_cap(v, DT))
        c = np.minimum(c, free)
        if noise is not None:
            c = c + noise[:, k]
        an = a + beta * (c - a)
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
        xs.append(x.copy()); vs.append(v.copy())
    X = np.stack(xs, 1); V = np.stack(vs, 1)
    if return_all:
        return X - w['xf'], V
    return X[:, -1] - w['xf'][:, -1], V[:, -1]


def score(w, p, f=None):
    e, v = rollout(w, p, f)
    return e


def null_err(w):
    """Constant speed from the start."""
    return w['v0'] * w['H'] - w['xf'][:, -1]


def pick_f(w, mode):
    if mode == 'pop':
        return np.ones(len(w['v0']))
    if mode == 'track':
        return np.nan_to_num(w['f_track'], nan=1.0)
    if mode == 'shrunk':
        return w['f_shrunk']
    return np.nan_to_num(w['f_other'], nan=1.0)


def fit_kp(ws, mode, p0=P1):
    def res(kp):
        p = list(p0); p[3] = kp[0]
        return np.concatenate([score(w, p, pick_f(w, mode)) / np.sqrt(np.mean(null_err(w) ** 2)) / np.sqrt(len(w['v0'])) for w in ws])
    r = least_squares(res, [0.05], bounds=([0.0], [1.0]), loss='soft_l1', f_scale=0.5)
    return float(r.x[0])


MODES = ('pop', 'other', 'track', 'shrunk')


def horizons():
    out = {}
    sets = {}
    for H in (10, 30):
        names = [n for n in F.DSETS if not (H == 30 and n == 'highD')]
        sets[H] = {n: windows(n, H, n_max=2000) for n in names}
        for n, w in sets[H].items():
            print(H, n, len(w['v0']), 'f_other share', round(float(np.isfinite(w['f_other']).mean()), 2), flush=True)
    res = {}
    for H in (10, 30):
        ws = list(sets[H].values())
        rH = {}
        for mode in MODES:
            kp = fit_kp(ws, mode)
            per = {}
            for n, w in sets[H].items():
                kpn = fit_kp([w], mode)
                p = list(P1); p[3] = kp
                e = score(w, p, pick_f(w, mode)); e1 = score(w, P1, pick_f(w, mode))
                per[n] = dict(k_p=round(kpn, 4), rmse_at_pooled=round(float(np.sqrt(np.mean(e ** 2))), 3), rmse_round1=round(float(np.sqrt(np.mean(e1 ** 2))), 3),
                              rmse_constant_speed=round(float(np.sqrt(np.mean(null_err(w) ** 2))), 3), bias_round1=round(float(np.mean(e1)), 3),
                              windows=int(len(w['v0'])))
            # Bootstrap of the pooled k_p by follower (20 replicates).
            B = []
            for b in range(20):
                wb = []
                for w in ws:
                    uf = np.unique(w['fid']); pk = rng.choice(uf, len(uf))
                    by = pd.Series(np.arange(len(w['fid']))).groupby(w['fid']).apply(np.array)
                    ii = np.concatenate([by[q] for q in pk])
                    wb.append({k: (v[ii] if isinstance(v, np.ndarray) and v.shape[:1] == w['fid'].shape else v) for k, v in w.items()})
                B.append(fit_kp(wb, mode))
            rH[mode] = dict(k_p=round(kp, 4), ci95=[round(float(np.percentile(B, 2.5)), 4), round(float(np.percentile(B, 97.5)), 4)], per_table=per)
            print(H, mode, json.dumps(rH[mode])[:600], flush=True)
        # Where the desired speed cannot bind: leader always under 0.85 of the site's free speed.
        sub = []
        for w in ws:
            m = w['vl'].max(1) < 0.85 * w['vdes']
            sub.append({k: (v[m] if isinstance(v, np.ndarray) and v.shape[:1] == m.shape else v) for k, v in w.items()})
        rH['other_leader_under_0.85_vdes'] = dict(k_p=round(fit_kp(sub, 'other'), 4), windows=int(sum(len(s['v0']) for s in sub)))
        res[H] = rH
    out['by_horizon'] = res
    # Joint law on 1 + 10 + 30 s, own reference from other leaders; each horizon weighted by its constant-speed error.
    one = [FD.samples(n) for n in F.DSETS]
    m1 = min(len(s['v']) for s in one)
    def res_joint(p):
        r = []
        for s in one:
            r.append((FD.rollout(s['v'][:m1], s['a'][:m1], s['g'][:m1], s['VL'][:m1], s['AL'][:m1], p)[:, -1] - s['v'][:m1] - s['y'][:m1]) / np.sqrt(np.mean(s['y'][:m1] ** 2)) / np.sqrt(m1))
        for H in (10, 30):
            for w in sets[H].values():
                r.append(score(w, p, pick_f(w, 'other')) / np.sqrt(np.mean(null_err(w) ** 2)) / np.sqrt(len(w['v0'])))
        return np.concatenate(r)
    rj = least_squares(res_joint, P1, bounds=([0, 0, 0, 0], [20, 2, 3, 1]), loss='soft_l1', f_scale=0.5)
    out['joint_1_10_30'] = dict(K=round(float(rj.x[0]), 3), c_a=round(float(rj.x[1]), 3), k_g=round(float(rj.x[2]), 3), k_p=round(float(rj.x[3]), 4))
    # The one-second error of the joint law, against round 1's, per table.
    out['joint_next_second_rmse'] = {s['name']: [round(float(np.sqrt(np.mean((FD.rollout(s['v'], s['a'], s['g'], s['VL'], s['AL'], p)[:, -1] - s['v'] - s['y']) ** 2))), 4)
                                                 for p in (P1, list(rj.x))] for s in one}
    print(json.dumps(out['joint_1_10_30']), json.dumps(out['joint_next_second_rmse']), flush=True)
    save('horizons', out)


# ---------------------------------------------------------------- F604 identification at one second
def profile():
    sets = [FD.samples(n) for n in F.DSETS]
    m = min(len(s['v']) for s in sets)
    cat = {k: np.concatenate([s[k][:m] for s in sets]) for k in ('v', 'a', 'g', 'VL', 'AL', 'y')}
    def resid(p, c):
        return FD.rollout(c['v'], c['a'], c['g'], c['VL'], c['AL'], p)[:, -1] - c['v'] - c['y']
    rows = []
    for kp in (0.0, 0.025, 0.05, 0.1, 0.15, 0.2, 0.3):
        def r3(q):
            return resid([q[0], q[1], q[2], kp], cat)
        r = least_squares(r3, P1[:3], bounds=([0, 0, 0], [20, 2, 3]), loss='soft_l1', f_scale=0.5)
        e = r3(r.x)
        rows.append(dict(k_p=kp, K=round(float(r.x[0]), 3), c_a=round(float(r.x[1]), 3), k_g=round(float(r.x[2]), 3),
                         rmse=round(float(np.sqrt(np.mean(e ** 2))), 5), mae=round(float(np.mean(np.abs(e))), 5)))
        print(rows[-1], flush=True)
    base = [r for r in rows if r['k_p'] == 0.025][0]['rmse']
    for r in rows:
        r['rmse_vs_0.025_pct'] = round(100 * (r['rmse'] / base - 1), 3)
    # How much of the pooled sample is far enough from the band for the pull to matter.
    gs = np.maximum(FD.S0, FD.t_gap(cat['v']) * cat['v'])
    e = (cat['g'] - gs) / np.maximum(cat['v'], 1)
    share = {f'e>{t}': round(float(np.mean(e > t)), 3) for t in (0.5, 1.0, 1.75)}
    save('profile', dict(rows=rows, share_of_queries=share, queries=int(len(cat['v']))))


# ---------------------------------------------------------------- F607 F608 relaxation of open gaps
def relax(kp=None):
    out = {}
    G = json.load(open(OUT)) if os.path.exists(OUT) else {}
    if kp is None:
        kp = G.get('horizons', {}).get('by_horizon', {}).get('30', {}).get('shrunk', {}).get('k_p')
    taus = (0, 2, 5, 10, 15, 20, 25, 30)
    for name in ('HT', 'I90stat', 'I294L1', 'I395'):
        w = windows(name, 30, n_max=40000, every=25)
        tgs = w['g'] / np.maximum(w['vf'], 1.0)
        ex = tgs - FD.t_gap(w['vf'])                 # excess over the population T(v), s
        sel = ex[:, 0] >= 1.0
        r = dict(windows=int(sel.sum()))
        idx = [int(round(t / DT)) for t in taus]
        def half(curve):
            c0 = curve[0]
            for j in range(1, len(curve)):
                if curve[j] <= c0 / 2:
                    return taus[j - 1] + (taus[j] - taus[j - 1]) * (curve[j - 1] - c0 / 2) / (curve[j - 1] - curve[j])
            return np.nan
        rec = [float(np.median(ex[sel, j])) for j in idx]
        r['recorded_median_excess'] = [round(x, 3) for x in rec]
        r['recorded_half_time_s'] = round(float(half(rec)), 1) if np.isfinite(half(rec)) else None
        wsel = {k: (v[sel] if isinstance(v, np.ndarray) and v.shape[:1] == sel.shape else v) for k, v in w.items()}
        for lab, p in (('round1', P1), (f'k_p {kp}', [P1[0], P1[1], P1[2], kp] if kp is not None else None)):
            if p is None:
                continue
            Xe, V = rollout(wsel, p, pick_f(wsel, 'shrunk'), return_all=True)
            g = wsel['g'] - Xe
            exm = g / np.maximum(V, 1.0) - FD.t_gap(V)
            cur = [float(np.median(exm[:, j])) for j in idx]
            r[lab] = dict(median_excess=[round(x, 3) for x in cur], half_time_s=round(float(half(cur)), 1) if np.isfinite(half(cur)) else None)
        out[name] = r
        print(name, json.dumps(r), flush=True)
    save('relax', out)


if __name__ == '__main__':
    {'selection': selection, 'profile': profile, 'horizons': horizons, 'relax': relax}[sys.argv[1]]()
