"""Vectorised car-following candidates. Every model rolls out N followers behind replayed leaders, shape (P,N) per step.

Krauss follows MSCFModel/MSCFModel_Krauss as transcribed in research/sumo-01-step-carfollow.md and common.wgsl.
Leader input is the measured leader; `s` is centre-to-centre or front-to-front spacing, L is the effective leader length.
"""
import numpy as np
EPS = 0.001
L_EFF = 5.0  # SUMO passenger length, so s0 absorbs any data length bias


class Batch:
    """Windows on a 0.1 s grid: s (spacing), v, vl, a0, shape (T,N)."""
    def __init__(self, s, v, vl, a0=None, meta=None):
        self.s, self.v, self.vl = s, v, vl
        self.T, self.N = s.shape
        self.dt = 0.1
        self.xf = np.vstack([np.zeros((1, self.N)), np.cumsum((v[1:] + v[:-1]) * .5 * self.dt, axis=0)])
        self.xl = self.xf + s
        self.a0 = np.zeros(self.N) if a0 is None else a0
        self.meta = meta

    def subset(self, idx):
        m = {k: v[idx] for k, v in self.meta.items()} if self.meta else None
        return Batch(self.s[:, idx], self.v[:, idx], self.vl[:, idx], self.a0[idx], m)


def _broad(p, n):
    return {k: np.asarray(v, float).reshape(-1, 1) if np.ndim(v) <= 1 else v for k, v in p.items()}


def krauss(b, p, dt=1.0, rng=None, return_a=False):
    """SUMO Krauss with semi-implicit Euler. p: accel, decel, tau, minGap, v0, sigma, emergency."""
    p = _broad(p, b.N)
    a, d, tau, mg, v0, sig = p['accel'], p['decel'], p['tau'], p['minGap'], p['v0'], p['sigma']
    B = np.maximum(p.get('emergency', 9.0) * np.ones_like(d), d)
    P = max(v.shape[0] for v in p.values())
    k = max(1, int(round(dt / b.dt)))
    steps = int((b.T - 1) / k)
    xf = np.tile(b.xf[0], (P, 1))
    v = np.tile(b.v[0], (P, 1))
    S = np.empty((steps + 1, P, b.N)); V = np.empty((steps + 1, P, b.N))
    S[0] = b.xl[0] - xf; V[0] = v
    if rng is None: rng = np.random.default_rng(0)
    for i in range(steps):
        j = i * k
        vl = b.vl[j]; gap = b.xl[j] - xf - L_EFF - mg
        r = d * dt
        n = np.floor(vl / r)
        bg = dt * (n * vl - r * n * (n + 1) * .5)  # brake_gap(vp, decel, 0) with bp=decel
        g = gap + bg - EPS
        with np.errstate(invalid='ignore', divide='ignore'):
            nn = np.floor(.5 - ((tau + np.sqrt(np.maximum(dt * dt + 4 * (dt * (2 * np.maximum(g, 0) / r - tau) + tau * tau), 0)) * -.5) / dt))
            nn = np.maximum(nn, 0)
            h = .5 * nn * (nn - 1) * r * dt + nn * r * tau
            x = nn * r + (np.maximum(g, 0) - h) / (nn * dt + tau)
        x = np.where(g < 0, 0.0, x)
        x = np.where(gap >= 0, x, np.maximum(v - B * dt, 0))
        orig = (v - x) / dt
        with np.errstate(invalid='ignore', divide='ignore'):
            pbd = .5 * vl * vl / d
            b1 = .5 * v * v / np.maximum(gap + pbd, 1e-6)
            ed = np.where(b1 <= d, b1, .5 * (v * v - vl * vl) / np.maximum(gap, 1e-6))
        ed = np.where(gap <= 0, B, ed)
        sd = np.minimum(np.maximum(1.2 * ed, d), orig)
        x = np.where(orig > d + EPS, np.maximum(v - sd * dt, 0), x)
        vpos = x
        ve = np.maximum(v - B * dt, 0)
        vmin = np.minimum(np.maximum(v - d * dt, 0), np.maximum(vpos, ve))
        vmaxnext = np.minimum(v + a * dt, v0)
        vmax = np.maximum(vmin, np.minimum(vmaxnext, vpos))
        if np.any(sig > 0):
            U = rng.random(vmax.shape)
            s_ = np.where(vmax < a, vmax - dt * sig * vmax * U, vmax - dt * sig * a * U)
        else:
            s_ = vmax
        vn = np.maximum(vmin, np.maximum(s_, 0))
        xf = xf + vn * dt
        v = vn
        S[i + 1] = b.xl[(i + 1) * k] - xf; V[i + 1] = v
    if k > 1:
        idx = np.arange(0, steps * k + 1, k)
        return _interp(S, idx, b.T), _interp(V, idx, b.T)
    return S, V


def _interp(A, idx, T):
    out = np.empty((T,) + A.shape[1:])
    last = idx[-1]
    ii = np.minimum(np.arange(T) // (idx[1] - idx[0]), len(idx) - 2)
    w = (np.arange(T) - idx[ii]) / (idx[1] - idx[0])
    w = np.minimum(w, 1).reshape(-1, 1, 1)
    out[:] = A[ii] * (1 - w) + A[ii + 1] * w
    return out


def _accel_idm(v, g, dv, p, plus=False):
    a, bb, T, s0, v0, delta = p['a'], p['b'], p['T'], p['s0'], p['v0'], p.get('delta', 4.0)
    ss = s0 + np.maximum(0.0, v * T + v * dv / (2 * np.sqrt(a * bb)))
    g = np.maximum(g, 0.05)
    free = 1 - (np.minimum(v, 1.5 * v0) / v0) ** delta
    inter = (ss / g) ** 2
    if plus:
        return a * np.minimum(free, 1 - inter)
    return a * (free - inter)


def idm_family(b, p, plus=False, dt=0.1, rng=None):
    """IDM/IDM+ with optional mechanisms, each one float of state per vehicle:
    tau_a: first-order lag on executed acceleration; tau_p: perception filter on closing speed;
    T_acc: time gap used while opening (dv<0); q: OU acceleration noise intensity m^2/s^3 with tc."""
    p = _broad(p, b.N)
    P = max(v.shape[0] for v in p.values())
    k = max(1, int(round(dt / b.dt)))
    steps = int((b.T - 1) / k)
    x = np.tile(b.xf[0], (P, 1)); v = np.tile(b.v[0], (P, 1))
    S = np.empty((steps + 1, P, b.N)); V = np.empty((steps + 1, P, b.N))
    S[0] = b.xl[0] - x; V[0] = v
    ac = np.tile(b.a0, (P, 1))
    dvh = v - b.vl[0]
    tau_a = p.get('tau_a'); tau_p = p.get('tau_p'); Tacc = p.get('T_acc'); qn = p.get('q'); tcn = p.get('tc', 10.0)
    fa = None if tau_a is None else 1 - np.exp(-dt / np.maximum(tau_a, 1e-3))
    fp = None if tau_p is None else 1 - np.exp(-dt / np.maximum(tau_p, 1e-3))
    noise = None
    if qn is not None:
        noise = np.zeros_like(v); rho = np.exp(-dt / tcn); amp = np.sqrt(qn * tcn / 2) * np.sqrt(1 - rho * rho)
        rng = rng or np.random.default_rng(0)
    pp = dict(p)
    for i in range(steps):
        j = i * k
        gap = b.xl[j] - x - L_EFF
        dv = v - b.vl[j]
        if fp is not None:
            dvh = dvh + fp * (dv - dvh); dv_use = dvh
        else:
            dv_use = dv
        if Tacc is not None:
            pp['T'] = np.where(dv_use < 0, Tacc, p['T'])
        at = _accel_idm(v, gap, dv_use, pp, plus)
        if fa is not None:
            ac = ac + fa * (at - ac)
        else:
            ac = at
        ae = ac
        if noise is not None:
            noise = rho * noise + amp * rng.standard_normal(noise.shape)
            ae = ac + noise
        vn = np.maximum(v + ae * dt, 0.0)
        adv = (v + vn) * .5 * dt
        # geometric guard: never drive through the leader, as any simulator kernel must
        adv = np.minimum(adv, np.maximum(b.xl[j + k] - x - L_EFF * .6, 0))
        vn = np.where(adv < (v + vn) * .5 * dt - 1e-6, np.minimum(vn, adv / dt), vn)
        x = x + adv
        v = vn
        S[i + 1] = b.xl[j + k] - x; V[i + 1] = v
    if k > 1:
        idx = np.arange(0, steps * k + 1, k)
        return _interp(S, idx, b.T), _interp(V, idx, b.T)
    return S, V


def hdm(b, p):
    """HDM core per Treiber, Kesting, Helbing 2006: ring-buffer reaction delay with temporal anticipation,
    IDM acceleration on the estimated state; deterministic mean (estimation noise off)."""
    p = _broad(p, b.N)
    P = max(v.shape[0] for v in p.values())
    Tr = np.broadcast_to(p['Tr'], (P, b.N))
    ks = np.clip(np.round(Tr / b.dt).astype(int), 0, 25)
    x = np.tile(b.xf[0], (P, 1)); v = np.tile(b.v[0], (P, 1))
    S = np.empty((b.T, P, b.N)); V = np.empty((b.T, P, b.N))
    S[0] = b.xl[0] - x; V[0] = v
    rows, cols = np.indices((P, b.N))
    for i in range(b.T - 1):
        j = np.maximum(i - ks, 0)
        sd = S[j, rows, cols]; vd = V[j, rows, cols]; vld = b.vl[j, cols]
        al = (b.vl[np.minimum(j + 1, b.T - 1), cols] - vld) / b.dt
        Tp = (i - j) * b.dt
        gh = sd - L_EFF + (vld - vd) * Tp
        vh = vd + 0 * Tp
        at = _accel_idm(vh, gh, vh - vld, p)
        vn = np.maximum(v + at * b.dt, 0)
        adv = (v + vn) * .5 * b.dt
        adv = np.minimum(adv, np.maximum(b.xl[i + 1] - x - L_EFF * .6, 0))
        vn = np.where(adv < (v + vn) * .5 * b.dt - 1e-6, np.minimum(vn, adv / b.dt), vn)
        x = x + adv; v = vn
        S[i + 1] = b.xl[i + 1] - x; V[i + 1] = v
    return S, V


def gipps(b, p, dt=0.5):
    """Gipps 1981 as summarised in Hou et al. 2025; tau is both reaction interval and step."""
    p = _broad(p, b.N)
    a, d, tau, s0, v0 = p['a'], p['b'], p['tau'], p['s0'], p['v0']
    bh = p.get('bhat', d)
    P = max(v.shape[0] for v in p.values())
    k = max(1, int(round(dt / b.dt)))
    steps = int((b.T - 1) / k)
    x = np.tile(b.xf[0], (P, 1)); v = np.tile(b.v[0], (P, 1))
    S = np.empty((steps + 1, P, b.N)); V = np.empty((steps + 1, P, b.N))
    S[0] = b.xl[0] - x; V[0] = v
    for i in range(steps):
        j = i * k
        gap = b.xl[j] - x - L_EFF - s0
        rad = (d * tau) ** 2 + d * (2 * gap - v * tau + b.vl[j] ** 2 / bh)
        vs = -d * tau + np.sqrt(np.maximum(rad, 0))
        vf = v + 2.5 * a * tau * (1 - v / v0) * np.sqrt(np.maximum(.025 + v / v0, 0))
        vn = np.maximum(np.minimum(vf, vs), 0)
        vn = np.minimum(vn, np.maximum(v + a * dt, 0))
        vn = np.maximum(vn, v - 9 * dt)
        adv = (v + vn) * .5 * dt
        adv = np.minimum(adv, np.maximum(b.xl[j + k] - x - L_EFF * .6, 0))
        x = x + adv; v = np.maximum(vn, 0)
        S[i + 1] = b.xl[j + k] - x; V[i + 1] = v
    idx = np.arange(0, steps * k + 1, k)
    return _interp(S, idx, b.T), _interp(V, idx, b.T)


def newell_anchor(b, tau):
    """Newell shift anchored on the initial state: x_f(t)=x_l(t-tau)-d, d chosen so t=0 matches."""
    k = int(round(tau / b.dt))
    v = np.empty_like(b.v)
    v[:k] = b.v[0]
    v[k:] = b.vl[:b.T - k]
    x = np.vstack([np.zeros((1, b.N)), np.cumsum((v[1:] + v[:-1]) * .5 * b.dt, axis=0)])
    return (b.xl - x)[:, None, :], v[:, None, :]


def const_speed(b):
    v = np.tile(b.v[0], (b.T, 1))
    x = b.dt * np.arange(b.T).reshape(-1, 1) * b.v[0]
    return (b.xl - x)[:, None, :], v[:, None, :]


def speed_copy(b):
    return newell_anchor(b, 0.0)


def const_time_gap(b, T, s0):
    """Instant constant-time-gap policy: s=s0+v T with v chosen to track it, closed form per step."""
    x = b.xf[0].copy(); v = b.v[0].copy()
    S = np.empty((b.T, 1, b.N)); V = np.empty((b.T, 1, b.N))
    S[0, 0] = b.xl[0] - x; V[0, 0] = v
    for i in range(b.T - 1):
        target = (b.xl[i] - x - L_EFF - s0) / T
        a = np.clip((target - v) / 2.0, -4, 2.5)
        v = np.maximum(v + a * b.dt, 0)
        x = x + v * b.dt
        S[i + 1, 0] = b.xl[i + 1] - x; V[i + 1, 0] = v
    return S, V


def score(b, S, V, horizons=(5, 10, 30)):
    """RMSE per horizon pooled over windows, plus collisions. S,V shape (T,P,N); returns dict for P=0 or mean over P."""
    out = {}
    for h in horizons:
        t = int(h / b.dt)
        if t >= b.T + 1: continue
        es = (S[:t] - b.s[:t, None, :]); ev = (V[:t] - b.v[:t, None, :])
        out[f'spacing_rmse_{h}s'] = float(np.sqrt(np.nanmean(es ** 2)))
        out[f'speed_rmse_{h}s'] = float(np.sqrt(np.nanmean(ev ** 2)))
    out['collision_frac'] = float(np.mean(np.nanmin(S, axis=0) < L_EFF * .6 + 0.05))
    return out


def per_window_errors(b, S, V, t=300):
    es = np.sqrt(np.nanmean((S[:t, 0] - b.s[:t]) ** 2, axis=0))
    ev = np.sqrt(np.nanmean((V[:t, 0] - b.v[:t]) ** 2, axis=0))
    return es, ev


def objective(b, S, V):
    """Spacing in units of 5 m, speed in units of 1 m/s; per population member."""
    es = np.nanmean((S - b.s[:, None, :]) ** 2, axis=(0, 2))
    ev = np.nanmean((V - b.v[:, None, :]) ** 2, axis=(0, 2))
    return es / 25.0 + ev


def de_fit(fun, bounds, names, pop=24, gens=40, seed=1, F=0.6, CR=0.8, fixed=None):
    """Batched differential evolution. fun(dict of arrays length P) -> array length P."""
    r = np.random.default_rng(seed)
    lo = np.array([bounds[n][0] for n in names]); hi = np.array([bounds[n][1] for n in names])
    X = lo + (hi - lo) * r.random((pop, len(names)))
    def ev(X):
        d = {n: X[:, i] for i, n in enumerate(names)}
        if fixed: d.update(fixed)
        return fun(d)
    fx = ev(X)
    for g in range(gens):
        idx = np.array([r.choice(pop, 3, replace=False) for _ in range(pop)])
        best = X[np.argmin(fx)]
        V_ = X + F * (best - X) + F * (X[idx[:, 1]] - X[idx[:, 2]])
        cross = r.random(X.shape) < CR
        cross[np.arange(pop), r.integers(0, len(names), pop)] = True
        U = np.clip(np.where(cross, V_, X), lo, hi)
        fu = ev(U)
        better = fu < fx
        X[better] = U[better]; fx[better] = fu[better]
    i = np.argmin(fx)
    return dict(zip(names, map(float, X[i]))), float(fx[i]), float(np.median(fx))


def helly_accel(v, s, vl, p):
    """Linear spacing and relative-speed feedback with bounded acceleration and a kinematic closing guard."""
    g = s - L_EFF
    e = g - p['s0'] - v * p['T']
    dv = vl - v
    k2 = p['k2']
    if 'k2c' in p: k2 = np.where(dv < 0, p['k2c'], k2)
    if 'm' in p: k2 = k2 * (15.0 / np.maximum(g, 2.0)) ** p['m']
    k1 = p['k1']
    if 'k1o' in p: k1 = np.where(e > 0, p['k1o'], k1)
    at = k1 * e + k2 * dv
    up = p['amax'] * np.maximum(1 - (np.minimum(v, 1.5 * p['v0']) / p['v0']) ** 4, -1)
    at = np.minimum(at, up)
    at = np.maximum(at, -p['bmax'])
    kin = -dv * dv / (2 * np.maximum(g - 0.5, 0.3))
    return np.where(dv < 0, np.minimum(at, kin), at)


def helly(b, p, dt=0.1):
    p = _broad(p, b.N)
    P = max(v.shape[0] for v in p.values())
    k = max(1, int(round(dt / b.dt)))
    steps = int((b.T - 1) / k)
    x = np.tile(b.xf[0], (P, 1)); v = np.tile(b.v[0], (P, 1))
    S = np.empty((steps + 1, P, b.N)); V = np.empty((steps + 1, P, b.N))
    S[0] = b.xl[0] - x; V[0] = v
    ac = np.tile(b.a0, (P, 1))
    fa = None if p.get('tau_a') is None else 1 - np.exp(-dt / np.maximum(p['tau_a'], 1e-3))
    for i in range(steps):
        j = i * k
        at = helly_accel(v, b.xl[j] - x, b.vl[j], p)
        ac = at if fa is None else ac + fa * (at - ac)
        vn = np.maximum(v + ac * dt, 0.0)
        adv = (v + vn) * .5 * dt
        adv = np.minimum(adv, np.maximum(b.xl[j + k] - x - L_EFF * .6, 0))
        vn = np.where(adv < (v + vn) * .5 * dt - 1e-6, np.minimum(vn, adv / dt), vn)
        x = x + adv; v = vn
        S[i + 1] = b.xl[j + k] - x; V[i + 1] = v
    if k > 1:
        idx = np.arange(0, steps * k + 1, k)
        return _interp(S, idx, b.T), _interp(V, idx, b.T)
    return S, V
