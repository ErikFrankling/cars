"""Fit and freeze the few free numbers of the measured driver (research/truth/measure/MODEL.md) on recordings that
are NOT held out (HOLDOUT.md): the follower tables of follow.py (highD without location 6, DLR HT 06-14 UTC,
TGSIM I-90/94 stationary, I-294 L1, I-395). Nothing here reads a held-out recording.

The model is run exactly as the kernel runs it (twin of md_* in common.wgsl): from the recorded state at t, behind the
recorded leader, for one second; the predicted speed change is scored against the recorded one.

    python3 -I scripts/measure/fit_driver.py fit       # -> research/truth/measure/model_fit.json
    python3 -I scripts/measure/fit_driver.py noise     # noise from the fit's residuals
    python3 -I scripts/measure/fit_driver.py launch    # first-car launch constants from SinD (Tianjin, Chongqing, Changchun)
"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
RES = os.path.join(HERE, '..', '..', 'research', 'truth', 'measure')
OUTJ = os.path.join(RES, 'model_fit.json')
rng = np.random.default_rng(20261107)

# Fixed from DRIVER.md, never fitted.
T_V = np.array([6.5, 12.5, 17.5, 22.5, 30.0, 40.0])     # band centres, m/s
T_T = np.array([1.6, 1.4, 1.2, 1.1, 0.95, 0.8])          # median steady time gap, s
S0 = 1.7            # standstill bumper gap, m
TAU_R = 0.5         # first-order response, s (0.48-0.56)
DV_MAX = 1.5        # closing response flattens above +1.5 m/s
E_NEAR = 0.5        # no braking until 0.5 s too close
G_MIN = 1.0         # the inverse time-to-collision term is not evaluated closer than this, m
A0, A1, AF = 2.02, 0.125, 0.7   # vehicle table (Long 2000); a0 refitted on launches below


def t_gap(v):
    return np.interp(v, T_V, T_T)


def command(v, g, vl, al, p, f=1.0, a_cap=None):
    K, ca, kg, kp = p[:4]
    gstar = np.maximum(S0, f * t_gap(v) * v)
    e = (g - gstar) / np.maximum(v, 1.0)
    G = -kg * np.maximum(0.0, -e - E_NEAR) + kp * np.maximum(0.0, e)
    a = K * np.minimum(vl - v, DV_MAX) / np.maximum(g, G_MIN) + ca * al + G
    # A follower is held only by its engine: the launch law binds with no leader within 100 m (F311). The tables are
    # followers within 100 m, and the engine's cap does not bind in them.
    return a if a_cap is None else np.minimum(a, a_cap)


def rollout(v0, a0, g0, VL, AL, p, dt=0.2, tau=TAU_R, noise=None):
    """VL, AL: leader speed and acceleration at the start of each step, shape (n, steps+1). Returns follower speeds."""
    beta = 1.0 - np.exp(-dt / tau)
    v, a, g = v0.copy(), a0.copy(), g0.copy()
    out = [v.copy()]
    for k in range(VL.shape[1] - 1):
        cmd = command(v, g, VL[:, k], AL[:, k], p)
        if noise is not None:
            cmd = cmd + noise[:, k]
        a = a + beta * (cmd - a)
        vn = np.maximum(v + a * dt, 0.0)
        a = (vn - v) / dt
        g = g + 0.5 * ((VL[:, k] + VL[:, k + 1]) - (v + vn)) * dt
        v = vn
        out.append(v.copy())
    return np.stack(out, 1)


def samples(name, n_follow=3000, horizon=5, every=5):
    """One query per second of each leader-follower segment: state at t, causal acceleration over the last 0.4 s, the
    leader's speed and acceleration over the next second, and what the follower did."""
    import follow as F
    d = F.load(name)
    d = d[d.lcar.astype(bool)]
    uf = d.fid.unique()
    d = d[d.fid.isin(rng.choice(uf, min(n_follow, len(uf)), replace=False))].reset_index(drop=True)
    seg = d.seg.to_numpy(); vf = d.vf.to_numpy(float); vl = d.vl.to_numpy(float); al = d.al.to_numpy(float); gap = d.gap.to_numpy(float)
    n = len(d); idx = np.arange(n)
    ok = np.zeros(n, bool)
    ok[2:n - horizon] = (seg[2:n - horizon] == seg[:n - horizon - 2]) & (seg[2:n - horizon] == seg[2 + horizon:])
    pos_in_seg = idx - np.r_[0, np.flatnonzero(np.diff(seg)) + 1].repeat(np.diff(np.r_[0, np.flatnonzero(np.diff(seg)) + 1, n]))
    ok &= (pos_in_seg % every == 0) & (vf > 2.0) & (gap > 0.5) & (gap < 100) & np.isfinite(al)
    i = np.flatnonzero(ok)
    VL = np.stack([vl[i + k] for k in range(horizon + 1)], 1)
    AL = np.stack([al[i + k] for k in range(horizon + 1)], 1)
    good = np.isfinite(AL).all(1)
    i, VL, AL = i[good], VL[good], AL[good]
    return dict(name=name, fid=d.fid.to_numpy()[i], seg=seg[i], v=vf[i], a=(vf[i] - vf[i - 2]) / 0.4, g=gap[i], VL=VL, AL=AL,
                y=vf[i + horizon] - vf[i], pos=pos_in_seg[i])


def fit():
    import follow as F
    sets = [samples(n) for n in F.DSETS]
    # Equal weight per dataset: each contributes the same number of queries.
    m = min(len(s['v']) for s in sets)
    pick = [rng.choice(len(s['v']), m, replace=False) for s in sets]
    cat = {k: np.concatenate([s[k][p] for s, p in zip(sets, pick)]) for k in ('v', 'a', 'g', 'VL', 'AL', 'y')}
    lab = np.concatenate([[s['name']] * m for s in sets])

    def resid(p, c):
        return rollout(c['v'], c['a'], c['g'], c['VL'], c['AL'], p)[:, -1] - c['v'] - c['y']

    p0 = [3.0, 0.6, 0.3, 0.05]
    lo, hi = [0.0, 0.0, 0.0, 0.0], [20.0, 2.0, 3.0, 1.0]
    r = least_squares(resid, p0, args=(cat,), bounds=(lo, hi), loss='soft_l1', f_scale=0.5)
    p = r.x
    out = dict(fixed=dict(T_v=T_V.tolist(), T_s=T_T.tolist(), s0=S0, tau_r=TAU_R, dv_max=DV_MAX, e_near=E_NEAR, g_min=G_MIN),
               pooled=dict(K=round(float(p[0]), 3), c_a=round(float(p[1]), 3), k_g=round(float(p[2]), 3), k_p=round(float(p[3]), 4), queries=int(len(lab)), per_dataset=int(m)))
    # Per dataset, to see how much one law has to cover.
    per = {}
    for s in sets:
        rr = least_squares(resid, p, args=(s,), bounds=(lo, hi), loss='soft_l1', f_scale=0.5)
        e_ = resid(rr.x, s); e0 = resid(p, s); null = -s['y']
        per[s['name']] = dict(K=round(float(rr.x[0]), 3), c_a=round(float(rr.x[1]), 3), k_g=round(float(rr.x[2]), 3), k_p=round(float(rr.x[3]), 4),
                              rmse_own_fit=round(float(np.sqrt(np.mean(e_ ** 2))), 4), rmse_pooled=round(float(np.sqrt(np.mean(e0 ** 2))), 4),
                              rmse_constant_speed=round(float(np.sqrt(np.mean(null ** 2))), 4), mae_pooled=round(float(np.mean(np.abs(e0))), 4),
                              mae_constant_speed=round(float(np.mean(np.abs(null))), 4), queries=int(len(s['v'])),
                              median_v=round(float(np.median(s['v'])), 1), median_gap=round(float(np.median(s['g'])), 1))
    out['per_dataset'] = per
    # Bootstrap the pooled fit by follower.
    B = []
    for b in range(20):
        cc = {k: [] for k in ('v', 'a', 'g', 'VL', 'AL', 'y')}
        for s in sets:
            uf = np.unique(s['fid']); pk = rng.choice(uf, len(uf))
            by = pd.Series(np.arange(len(s['fid']))).groupby(s['fid']).apply(np.array)
            ii = np.concatenate([by[f] for f in pk])[:m]
            for k in cc:
                cc[k].append(s[k][ii])
        cc = {k: np.concatenate(v) for k, v in cc.items()}
        B.append(least_squares(resid, p, args=(cc,), bounds=(lo, hi), loss='soft_l1', f_scale=0.5).x)
    B = np.array(B)
    out['pooled']['ci95'] = {k: [round(float(np.percentile(B[:, j], 2.5)), 4), round(float(np.percentile(B[:, j], 97.5)), 4)] for j, k in enumerate(('K', 'c_a', 'k_g', 'k_p'))}
    # Noise: what the deterministic law leaves, second by second along a segment.
    noise = {}
    for s in sets:
        e_ = resid(p, s)
        df = pd.DataFrame(dict(seg=s['seg'], pos=s['pos'], e=e_)).sort_values(['seg', 'pos'])
        ac = {}
        for L in (1, 2, 3, 5):
            sh = df.groupby('seg').e.shift(-L); same = df.groupby('seg').pos.shift(-L) == df.pos + 5 * L
            mm = np.isfinite(sh) & same
            ac[L] = round(float(np.corrcoef(df.e[mm], sh[mm])[0, 1]), 3) if mm.sum() > 100 else None
        noise[s['name']] = dict(sd_1s_speed_change=round(float(np.std(e_)), 4), autocorr_by_lag_s=ac)
    out['residual'] = noise
    out['noise'] = noise_fit(noise, p)
    json.dump(out, open(OUTJ, 'w'), indent=1)
    print(json.dumps(out, indent=1))


def ou_stats(tn, dt=0.05, n=4000):
    """SD and lag-1 correlation of the one-second speed change that a unit OU command noise of correlation time tn
    gives through the 0.5 s response. Each step uses the noise averaged over the step, as the kernel does."""
    steps = int(10 / dt); rho = np.exp(-dt / tn); beta = 1 - np.exp(-dt / TAU_R)
    scale = np.sqrt(2 * (tn / dt) ** 2 * (dt / tn - 1 + np.exp(-dt / tn)))
    x = np.zeros(n); a = np.zeros(n); v = np.zeros(n); vs = []
    z = np.random.default_rng(3).standard_normal((steps, n))
    for k in range(steps):
        x = rho * x + np.sqrt(1 - rho * rho) * z[k]
        a = a + beta * (scale * x - a); v = v + a * dt
        if k % int(round(1 / dt)) == 0:
            vs.append(v.copy())
    dv = np.diff(np.array(vs)[3:], axis=0)
    return dv.std(), np.mean([np.corrcoef(dv[j], dv[j + 1])[0, 1] for j in range(len(dv) - 1)])


def noise_fit(noise, p=None):
    """sigma and correlation time of an Ornstein-Uhlenbeck command noise that, through the 0.5 s response, gives each
    table's residual SD of the one-second speed change and its correlation from one second to the next. Pooled as the
    median over tables of each number. A lag-1 correlation below the white-noise limit takes the shortest time."""
    grid = [(tn,) + ou_stats(tn) for tn in (0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0)]
    per = {}
    for name, r in noise.items():
        r1 = r['autocorr_by_lag_s']['1'] if '1' in r['autocorr_by_lag_s'] else r['autocorr_by_lag_s'][1]
        tn, s1, c1 = min(grid, key=lambda g: abs(g[2] - r1))
        per[name] = dict(lag1=r1, corr_time_s=tn, sigma=round(r['sd_1s_speed_change'] / s1, 3))
    return dict(per_table=per, corr_time_s=float(np.median([v['corr_time_s'] for v in per.values()])),
                sigma=round(float(np.median([v['sigma'] for v in per.values()])), 3),
                grid=[[g[0], round(float(g[1]), 3), round(float(g[2]), 3)] for g in grid])


def noise():
    out = json.load(open(OUTJ))
    out['noise'] = noise_fit(out['residual'])
    json.dump(out, open(OUTJ, 'w'), indent=1)
    print(json.dumps(out['noise'], indent=1))


def launch():
    """a0 of the driver's launch so that a first car from rest, through the 0.5 s response, peaks at the SinD weekday
    1.77 m/s2, and the reaction after green so that it passes 1.5 m/s at 2.0 s (Tianjin and Chongqing, DRIVER.md)."""
    dt = 0.01
    beta = 1 - np.exp(-dt / TAU_R)
    def run(a0):
        v = a = 0.0; t = 0.0; peak = 0.0; t15 = None
        while t < 15:
            cmd = max(a0 - A1 * v, AF)
            a += beta * (cmd - a); v += a * dt; t += dt
            peak = max(peak, a)
            if t15 is None and v >= 1.5:
                t15 = t
        return peak, t15
    lo, hi = 1.0, 4.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if run(mid)[0] < 1.77: lo = mid
        else: hi = mid
    a0 = 0.5 * (lo + hi); pk, t15 = run(a0)
    res = dict(a0=round(a0, 3), a1=A1, peak=round(pk, 3), time_to_1_5_ms_from_motion=round(t15, 3), first_react=round(2.0 - t15, 3),
               source='SinD Tianjin, Chongqing (start), all three cities (peak); Xi\'an held out')
    out = json.load(open(OUTJ)) if os.path.exists(OUTJ) else {}
    out['launch'] = res
    json.dump(out, open(OUTJ, 'w'), indent=1)
    print(res)


if __name__ == '__main__':
    {'fit': fit, 'noise': noise, 'launch': launch}[sys.argv[1]]()
