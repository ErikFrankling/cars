"""Closed-loop vehicle arrays for ring, platoon and queue tests, using the same equations as opus_models."""
import numpy as np
from opus_models import L_EFF, EPS, _accel_idm, helly_accel

def krauss_step(v, s, vl, p, dt, rng):
    a, d, tau, mg, v0, sig = p['accel'], p['decel'], p['tau'], p['minGap'], p['v0'], p['sigma']
    B = max(9.0, float(np.max(d)))
    gap = s - L_EFF - mg
    r = d * dt
    n = np.floor(vl / r)
    bg = dt * (n * vl - r * n * (n + 1) * .5)
    g = gap + bg - EPS
    gg = np.maximum(g, 0)
    nn = np.floor(.5 - ((tau + np.sqrt(np.maximum(dt * dt + 4 * (dt * (2 * gg / r - tau) + tau * tau), 0)) * -.5) / dt))
    nn = np.maximum(nn, 0)
    h = .5 * nn * (nn - 1) * r * dt + nn * r * tau
    x = nn * r + (gg - h) / (nn * dt + tau)
    x = np.where(g < 0, 0.0, x)
    x = np.where(gap >= 0, x, np.maximum(v - B * dt, 0))
    orig = (v - x) / dt
    pbd = .5 * vl * vl / d
    b1 = .5 * v * v / np.maximum(gap + pbd, 1e-6)
    ed = np.where(b1 <= d, b1, .5 * (v * v - vl * vl) / np.maximum(gap, 1e-6))
    ed = np.where(gap <= 0, B, ed)
    sd = np.minimum(np.maximum(1.2 * ed, d), orig)
    x = np.where(orig > d + EPS, np.maximum(v - sd * dt, 0), x)
    ve = np.maximum(v - B * dt, 0)
    vmin = np.minimum(np.maximum(v - d * dt, 0), np.maximum(x, ve))
    vmax = np.maximum(vmin, np.minimum(np.minimum(v + a * dt, v0), x))
    U = rng.random(v.shape)
    s_ = np.where(vmax < a, vmax - dt * sig * vmax * U, vmax - dt * sig * a * U)
    return np.maximum(vmin, np.maximum(s_, 0))


class Driver:
    """kind: krauss | idm | idmplus | gipps | hdm-free variants with tau_a, tau_p, T_acc, q+tc, da (action point), t_start."""
    def __init__(self, kind, p, N, dt=0.1, seed=0, a0=None):
        self.kind, self.dt, self.N = kind, dt, N
        self.p = {k: np.broadcast_to(np.asarray(v, float), (N,)).copy() for k, v in p.items()}
        self.rng = np.random.default_rng(seed)
        self.ac = np.zeros(N) if a0 is None else a0.copy()
        self.dvh = None
        self.noise = np.zeros(N)
        self.held = np.zeros(N)
        self.started = np.zeros(N)

    def step(self, v, s, vl, dvh_init=None):
        p, dt = self.p, self.dt
        if self.kind == 'krauss':
            return krauss_step(v, s, vl, p, dt, self.rng)
        if self.kind == 'gipps':
            a, d, tau, s0, v0 = p['a'], p['b'], p['T'], p['s0'], p['v0']
            gap = s - L_EFF - s0
            rad = (d * tau) ** 2 + d * (2 * gap - v * tau + vl ** 2 / d)
            vs = -d * tau + np.sqrt(np.maximum(rad, 0))
            vf = v + 2.5 * a * tau * (1 - v / v0) * np.sqrt(np.maximum(.025 + v / v0, 0))
            vn = np.maximum(np.minimum(np.minimum(vf, vs), v + a * dt), np.maximum(v - 9 * dt, 0))
            return vn
        if self.kind == 'helly':
            if 'T_sd' in p:
                # slow drift of the wanted time gap within one driver
                if not hasattr(self, 'z'): self.z = self.rng.normal(0, p['T_sd'], self.N)
                r_ = np.exp(-dt / p['T_tc'])
                self.z = r_ * self.z + p['T_sd'] * np.sqrt(1 - r_ * r_) * self.rng.standard_normal(self.N)
                pu = dict(p); pu['T'] = p['T'] * np.exp(self.z)
            else:
                pu = p
            at = helly_accel(v, s, vl, pu)
            if 'tau_a' in p:
                self.ac = self.ac + (1 - np.exp(-dt / p['tau_a'])) * (at - self.ac)
            else:
                self.ac = at
            ae = self.ac
            if 'q' in p:
                tc = p.get('tc', np.full(self.N, 10.0)); rho = np.exp(-dt / tc)
                self.noise = rho * self.noise + np.sqrt(p['q'] * tc / 2) * np.sqrt(1 - rho * rho) * self.rng.standard_normal(self.N)
                ae = ae + self.noise
            vn = np.maximum(v + ae * dt, 0)
            if 't_start' in p:
                stopped = v < 0.05
                wants = at > 0.05
                self.started = np.where(stopped & wants, self.started + dt, np.where(stopped, 0.0, self.started))
                vn = np.where(stopped & (self.started < p['t_start']), 0.0, vn)
            return vn
        dv = v - vl
        if 'tau_p' in p:
            if self.dvh is None: self.dvh = dv.copy()
            self.dvh = self.dvh + (1 - np.exp(-dt / p['tau_p'])) * (dv - self.dvh)
            dv_use = self.dvh
        else:
            dv_use = dv
        pp = dict(p)
        if 'T_acc' in p: pp['T'] = np.where(dv_use < 0, p['T_acc'], p['T'])
        at = _accel_idm(v, s - L_EFF, dv_use, pp, self.kind == 'idmplus')
        if 'da' in p:
            # action point: keep the held acceleration until the target moves by da, unless the target asks for harder braking
            mv = (np.abs(at - self.held) > p['da'] * self.rng.random(self.N)) | (at < self.held - p['da'])
            self.held = np.where(mv, at, self.held); at = self.held
        if 'tau_a' in p:
            self.ac = self.ac + (1 - np.exp(-dt / p['tau_a'])) * (at - self.ac)
        else:
            self.ac = at
        ae = self.ac
        if 'q' in p:
            tc = p.get('tc', np.full(self.N, 10.0)); rho = np.exp(-dt / tc)
            self.noise = rho * self.noise + np.sqrt(p['q'] * tc / 2) * np.sqrt(1 - rho * rho) * self.rng.standard_normal(self.N)
            ae = ae + self.noise
        vn = np.maximum(v + ae * dt, 0)
        if 't_start' in p:
            # startup delay: from standstill a vehicle does not move for t_start after it first wants to
            stopped = v < 0.05
            wants = at > 0.05
            self.started = np.where(stopped & wants, self.started + dt, np.where(stopped, 0.0, self.started))
            vn = np.where(stopped & (self.started < p['t_start']), 0.0, vn)
        return vn


def advance(x, v, vn, dt, lead_x=None, min_spacing=None):
    """Ballistic for continuous models; caller guards overlap."""
    adv = (v + vn) * .5 * dt
    if lead_x is not None:
        adv = np.minimum(adv, np.maximum(lead_x - x - min_spacing, 0))
        vn = np.where(adv < (v + vn) * .5 * dt - 1e-6, np.minimum(vn, adv / dt), vn)
    return x + adv, vn


def ring(kind, p, N=22, L=230.0, T=600.0, dt=0.1, seed=1, v_init=8.0, spatial_jitter=0.3, min_sp=2.0):
    """Sugiyama geometry: returns dict of steady statistics from the last half."""
    r = np.random.default_rng(seed)
    d = Driver(kind, p, N, dt, seed)
    x = np.arange(N) * L / N + r.normal(0, spatial_jitter, N); v = np.full(N, v_init)
    steps = int(T / dt); keep = int(T / 2 / dt)
    VV = np.empty((steps, N), 'f4'); XX = np.empty((steps, N), 'f8')
    collisions = 0
    for i in range(steps):
        lx = np.roll(x, -1); lx[-1] += L
        lv = np.roll(v, -1)
        s = lx - x
        vn = d.step(v, s, lv)
        x, vn = advance(x, v, vn, dt, lx, 2.0 if kind != 'krauss' else 2.0)
        collisions += int((s < 3).sum())
        v = vn
        VV[i] = v; XX[i] = x
    V2 = VV[keep:]
    sd_time = float(V2.std(axis=0).mean())
    # backward wave: lag between successive vehicles of the speed signal
    laglist = []
    mean_s = L / N
    st = max(1, int(round(.5 / dt))); W = V2[::st]; ld = st * dt
    for k in range(N):
        a = W[:, k] - W[:, k].mean(); b = W[:, (k + 1) % N] - W[:, (k + 1) % N].mean()
        if a.std() < .2 or b.std() < .2: continue
        cc = [np.dot(a[m:], b[:len(b) - m]) / (len(b) - m) for m in range(0, 24)]
        m = int(np.argmax(cc))
        if 0 < m < 23: laglist.append(m * ld)
    wave = float(mean_s / np.median(laglist) * 3.6) if laglist else None
    stops = float((V2 < .5).mean())
    return dict(mean_v=float(V2.mean()), sd_v=sd_time, min_v=float(np.percentile(V2, 1)), max_v=float(np.percentile(V2, 99)), stopped_frac=stops, wave_kmh=wave, lag_n=len(laglist), lag_med=float(np.median(laglist)) if laglist else None, overlap_events=collisions)


def queue(kind, p, N=15, spacing=7.0, dt=0.1, first_dist=2.0, T=70.0, seed=1):
    """Green at t=0 for a standing queue. Stop line at x=0; x is the front bumper. Returns crossing times."""
    d = Driver(kind, p, N, dt, seed)
    x = -first_dist - spacing * np.arange(N); v = np.zeros(N)
    cross = np.full(N, np.nan)
    move = np.full(N, np.nan)
    for i in range(int(T / dt)):
        lx = np.r_[x[0] + 1e4, x[:-1]]; lv = np.r_[50.0, v[:-1]]
        vn = d.step(v, lx - x, lv)
        xn, vn = advance(x, v, vn, dt, lx, 3.0)
        cr = (x < 0) & (xn >= 0) & np.isnan(cross)
        cross[cr] = (i + 1) * dt
        mv = (vn > 1.5) & np.isnan(move)
        move[mv] = (i + 1) * dt
        x, v = xn, vn
    h = np.diff(np.r_[0, cross])
    hsat = float(np.nanmedian(h[4:])) if N > 5 else np.nan
    lost = float(np.nansum(h[:4] - hsat))
    return dict(h=[round(float(z), 2) for z in h], cross=[round(float(z), 2) for z in cross], start=[round(float(z), 2) for z in move], hsat=hsat, lost=lost)
