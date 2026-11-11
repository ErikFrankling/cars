"""Forecasts for T0 scenes from the measured driver's own equations (research/truth/measure/MODEL.md), written before the
scenes run: a platoon on one lane, every car the kernel's law (the same twin as scripts/replay/md_twin.py, F307), at the
scenes' dt 0.25 with the kernel's noise. No simulator.

    python3 -I scripts/theory/md_platoon.py      # prints the numbers that go into forecasts.csv F312-F321
"""
import os, sys, json, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'scripts', 'measure'))
import fit_driver as FD

J = json.load(open(FD.OUTJ))
P5 = FD.r5_params()       # round 5 law (MODEL.md, F837): K, g_1, c_a, k_g, k_p, K_1
TV = J['slow']['T_v']
SIG, TN = (J['round2']['noise_sigma'], J['round2']['noise_tau']) if 'round2' in J else (J['noise']['sigma'], J['noise']['corr_time_s'])
R1, START = J['launch']['first_react'], 1.0
L, S0, MU = 5.0, 1.7, 0.85
GAP_SD = 0.27 * math.sqrt(1 - 0.41 ** 2)   # scenes set speedDev 0: only the part of the gap factor not tied to speed
EF = math.exp(GAP_SD ** 2 / 2)


def ph_force(u):
    pw = 0.775 * 90000 / 1650
    return (1 / 1.05) * (np.minimum(pw / np.maximum(u, 10.0), MU * 0.55 * 9.81) - 0.0105 * 9.81 - 0.5 * 1.225 * 0.68 / 1650 * u * u)


def stop_comfort(gap, v, dt):
    g = np.maximum(gap, 0.0)
    v1 = 1.2 * np.maximum(g - v * dt, 0) ** 0.6
    v2 = 1.2 * np.maximum(np.nan_to_num(g - 0.5 * (v + v1) * dt, posinf=1e9), 0) ** 0.6
    late = v - dt * np.maximum(2.2, 1.1 * v * v / (2 * np.maximum(g, 0.1)))
    return np.where(g <= 0.1, 0.0, np.minimum(np.maximum(v2, late), np.maximum(g - v * dt * 0.5, 0) / dt))


def cert(gb, v, vl, a_prev, dt, b=8.3, t_r=0.3):
    along = vl * vl / (2 * b)
    jerk = b / t_r if dt >= t_r else b / (t_r + dt)
    lam = np.maximum(0, 1 - np.maximum(0, -a_prev - jerk * dt) / b)
    h = (t_r * lam * lam + dt) * 0.5
    q = gb - 0.5 + along - v * dt * 0.5
    return b * (-h + np.sqrt(h * h + 2 * np.maximum(q, 0) / b))


def platoon(x0, v0, vdes, T, dt=0.25, green=0.0, seed=0, noise=True, lead_trace=None, line=None):
    """x0: fronts, front car first. green: time the first car may go (it stands at the line before). lead_trace(t): the
    first car's desired speed. Returns times, positions, speeds (steps x cars)."""
    rng = np.random.default_rng(seed)
    n = len(x0)
    f = np.exp(GAP_SD * rng.standard_normal(n))
    x, v, a = np.array(x0, float), np.array(v0, float), np.zeros(n)
    beta = 1 - math.exp(-dt / FD.TAU_R)
    rho = math.exp(-dt / TN); scale = SIG * math.sqrt(2 * (TN / dt) ** 2 * (dt / TN - 1 + math.exp(-dt / TN)))
    z = np.zeros(n)
    moved = np.full(n, np.inf)        # when each car first moved
    steps = np.zeros(n, int)
    X, V, Ts = [x.copy()], [v.copy()], [0.0]
    t = 0.0
    for k in range(int(T / dt)):
        t1 = t + dt
        vd = np.full(n, vdes)
        if lead_trace is not None:
            vd[0] = lead_trace(t1)
        g = np.r_[np.inf, x[:-1] - L - x[1:]]
        vl = np.r_[0.0, v[:-1]]; al = np.r_[0.0, a[:-1]]
        lead = np.r_[False, np.ones(n - 1, bool)]
        alone = ~lead | (g > 100)
        eng = ph_force(v + 0.5 * np.maximum(ph_force(v), 0) * dt)
        free = np.minimum((vd - v) / TV, eng)
        free = np.where(alone, np.minimum(free, np.maximum(2.02 - 0.125 * v, 0.7)), free)
        af = FD.command_r5(v, g, vl, al, P5, f)
        cmd = np.where(lead, np.minimum(af, free), free)
        nz = np.where(v >= 0.5, z * scale, 0.0) if noise else 0.0
        vn = np.maximum(v + (a + beta * (cmd + nz - a)) * dt, 0.0)
        vn = np.where(lead & (vl < 0.5 * v), np.minimum(vn, stop_comfort(g - S0 + vl * vl / 2.6, v, dt)), vn)
        c = np.where(lead, cert(g, v, vl, a, dt), np.inf)
        if line is not None and t1 < green:
            c[0] = min(c[0], 0.0)
        vn = np.where(c <= 0, -1.0, np.minimum(vn, c))
        jerk = 8.3 / 0.3 if dt >= 0.3 else 8.3 / (0.3 + dt)
        floor = v - np.minimum(8.3, np.maximum(0, -a) + (8.3 * dt / (0.3 + dt) if dt < 0.3 else 8.3)) * dt
        release = np.where(a >= 0, 1e9, v + (a + jerk * dt) * dt)
        vn = np.where(vn < 0, floor, np.maximum(np.minimum(vn, release), floor))
        # start hold: the first car r_1 after green, every other one 1.0 s after the car ahead moved
        stand = v < 0.05
        open_t = np.r_[green + R1 if line is not None else -np.inf, moved[:-1] + START]
        hold = stand & (t1 < open_t - 1e-6)
        part = stand & ~hold & (t1 - dt < open_t)
        vn = np.where(hold, 0.0, np.where(part, vn * np.clip((t1 - open_t) / dt, 0, 1), vn))
        acc = (vn - v) / dt
        vn = np.maximum(vn, 0.0)
        ds = np.where(vn > 0, v * dt + 0.5 * acc * dt * dt, np.where(acc < 0, v * v / (2 * np.maximum(-acc, 1e-9)), 0.0))
        a = np.where(vn > 0, acc, 0.0)
        moved = np.where(np.isinf(moved) & (vn > 1e-3), t1, moved)
        x = x + ds; v = vn
        z = rho * z + math.sqrt(1 - rho * rho) * rng.standard_normal(n)
        t = t1
        X.append(x.copy()); V.append(v.copy()); Ts.append(t)
    return np.array(Ts), np.array(X), np.array(V)


def crossings(T, X, at):
    out = []
    for i in range(X.shape[1]):
        k = np.argmax(X[:, i] >= at)
        if X[k, i] < at:
            out.append(np.nan); continue
        out.append(T[k - 1] + (at - X[k - 1, i]) / max(X[k, i] - X[k - 1, i], 1e-9) * (T[k] - T[k - 1]) if k else T[0])
    return np.array(out)


def queue(n, d0, line=0.0):
    return [line - d0 - i * (L + S0) for i in range(n)]


def discharge(kmh, n, d0, at, seeds=5, T=300.0):
    """L1 and S1: a standing queue at a light turning green at t 0; crossing times of a point `at` past the line."""
    res = []
    for s in range(seeds):
        Ts, X, V = platoon(queue(n, d0), np.zeros(n), kmh / 3.6, T, green=0.0, seed=s, line=0.0)
        res.append(crossings(Ts, X, at))
    return np.array(res)


def main():
    out = {}
    # S1 S2 S3: 25 cars, the first d0 behind the line (the scene measures d0; main's runs read about 2 m), line crossing.
    d0 = 1.5      # main's S1 reads d0 1.5 m
    c = discharge(50, 25, d0, 0.0, seeds=40, T=120.0)  # the front crosses the line
    H = np.c_[c[:, :1], np.diff(c, axis=1)]
    out['S1_headway_from_car10'] = float(np.nanmean(H[:, 9:]))
    out['S2_t1_and_headways_2_9'] = [round(float(x), 2) for x in np.nanmean(H[:, :9], axis=0)]
    out['S3_lost_time_first4'] = float(np.nanmean((H[:, :4] - np.nanmean(H[:, 9:], axis=1)[:, None]).sum(axis=1)))
    # Tolerances: two standard errors of a 5-seed mean, from the spread between seeds here (the scenes run 5).
    se5 = lambda x: 2 * float(np.nanstd(x)) / math.sqrt(5)
    out['S1_tol'] = se5(np.nanmean(H[:, 9:], axis=1))
    out['S2_tol'] = [round(se5(H[:, i]), 2) for i in range(9)]
    # L1: 180 cars, count past the line at 300 m (1200 m at 100 km/h), from car 10, over 300 s
    for kmh in (30, 50, 100):
        at = 1200.0 if kmh == 100 else 300.0
        c = discharge(kmh, 120, 1.5, at, seeds=5, T=260.0)
        caps = []
        for r in c:
            w = r[10:]; w = w[np.isfinite(w)]; w = w[w <= w[0] + 300]
            caps.append(3600 * (len(w) - 1) / (w[-1] - w[0]))
        out[f'L1_cap_{kmh}'] = float(np.mean(caps)); out[f'L1_tol_{kmh}'] = se5(caps)
    # W1: 30 cars closed up at 10 m/s at the band centre, the leader's wanted speed down to 3 m/s at 2 m/s2, 5 s, back at 1.5
    def lead(t, t0=60.0):
        t1 = t0 + 3.5
        if t < t0: return 10.0
        if t < t1: return 10.0 - 2.0 * (t - t0)
        if t < t1 + 5.0: return 3.0
        return min(10.0, 3.0 + 1.5 * (t - t1 - 5.0))
    sp = L + (EF * FD.t_gap(10.0) - 0.25) * 10.0
    dips, mins = [], []
    for s in range(20):
        Ts, X, V = platoon([-i * sp for i in range(30)], np.full(30, 10.0), 10.0, 160.0, seed=s, lead_trace=lead)
        m = Ts >= 55
        dips.append(float(V[m, -1].min() - V[m, 0].min())); mins.append(float(V[m, -1].min()))
    out['W1_car30_min_less_leader_min'] = float(np.mean(dips)); out['W1_car30_min'] = float(np.mean(mins))
    out['W1_dips_by_seed'] = [round(d, 2) for d in dips]; out['W1_tol'] = se5(dips)
    # Steady states at the band centre e = -0.25 s, with the half band 0.25 s as the spread (E[f] over the gap factor).
    def spacing(v, e=-0.25):
        vt = max(v, 6.5)
        return L + S0 + (EF * (float(FD.t_gap(vt)) - S0 / vt) + e) * v
    out['band'] = dict(EF=EF)
    v50 = 50 / 3.6
    out['L2_kc'] = 1000 / spacing(v50); out['L2_kc_band'] = [1000 / spacing(v50, 0), 1000 / spacing(v50, -0.5)]
    out['L2_qmax'] = 3600 * v50 / spacing(v50); out['L2_qmax_band'] = [3600 * v50 / spacing(v50, 0), 3600 * v50 / spacing(v50, -0.5)]
    def speed_at(spc, e):
        lo, hi = 0.0, 40.0
        for _ in range(60):
            m = 0.5 * (lo + hi)
            if spacing(m, e) < spc: lo = m
            else: hi = m
        return 0.5 * (lo + hi)
    out['L2_speed_at_spacing_10_12_15_20'] = [round(speed_at(s, -0.25), 2) for s in (10, 12, 15, 20)]
    out['L2_speed_band'] = [[round(speed_at(s, 0), 2), round(speed_at(s, -0.5), 2)] for s in (10, 12, 15, 20)]
    out['L6_q_at_1_63'] = 3600 * 1.63 / spacing(1.63); out['L6_band'] = [3600 * 1.63 / spacing(1.63, 0), 3600 * 1.63 / spacing(1.63, -0.5)]
    out['G1_followup_at_v'] = {f'{v:.1f}': round(spacing(v) / v, 3) for v in (2.5, 3.0, 3.5, 4.0)}
    print(json.dumps(out, indent=1))
    json.dump(out, open(os.path.join(REPO, 'research/truth/foundations/md_platoon_r5.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
