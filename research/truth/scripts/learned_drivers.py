#!/usr/bin/env python3
"""Learned-driver prototype for research/truth/13-learned-drivers.md. CPU only, 1D, numpy.

Ring: N cars on one closed lane with IDM humans that make their own waves, K policy cars.
Merge: an open main lane with an on-ramp, a demand queue at each entrance, K% policy cars.
One network everywhere: 12 inputs -> 8 -> 8 -> 4 (212 floats), the layout the WGSL version uses.

  nix develop --command python3 -I research/truth/scripts/learned_drivers.py <command> ...

Torch is imported only by the ppo and bc commands; see the report for the Nix env.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parents[1] / "learned"
IN, HID, NOUT = 12, 8, 4
DIM = IN * HID + HID + HID * HID + HID + HID * NOUT + NOUT
A_MAX, B_POLICY = 3.0, 6.0
PHYS_B = 9.0


class P:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def with_(self, **kw):
        d = dict(self.__dict__)
        d.update(kw)
        return P(**d)


# Calibrated in `baselines` against Stern's 22 cars, 260 m (see report section 4).
HUMAN = P(a=2.0, b=2.1, T=0.7, s0=2.0, v0=30.0, noise=0.2, length=5.0)
RING = P(n=22, length=260.0, dt=0.1, warm=120.0, horizon=300.0)


def idm(v, vl, gap, h):
    ss = h.s0 + np.maximum(0.0, v * h.T + v * (v - vl) / (2.0 * np.sqrt(h.a * h.b)))
    return h.a * (1.0 - (v / h.v0) ** 4 - (ss / np.maximum(gap, 0.1)) ** 2)


def uniform_speed(gap, h):
    lo, hi = 0.0, h.v0
    for _ in range(60):
        m = 0.5 * (lo + hi)
        if idm(m, m, gap, h) > 0:
            lo = m
        else:
            hi = m
    return lo


def energy_power(a, v):
    """Battery power per car in W: assumed 1,800 kg EV, F = 150 + 0.4 v^2 N, drive 0.85, regen 0.6."""
    p = (1800.0 * a + 150.0 + 0.4 * v * v) * v
    return np.where(p > 0, p / 0.85, 0.6 * p)


def shield_limit(v, vl, gap, dt, b_f=6.0, b_l=PHYS_B, m=0.5):
    """Largest safe next speed, the certificate of report 11 with t_r = 0. b_l bounds the leader."""
    b_c = min(b_f, b_l)
    h = dt / 2.0
    q = gap - m + vl * vl / (2.0 * b_l) - v * dt / 2.0
    return b_c * (-h + np.sqrt(h * h + 2.0 * np.maximum(q, 0.0) / b_c))


def unpack(th):
    p = th.shape[0]
    i = 0
    out = []
    for r, c in ((HID, IN), (HID, 1), (HID, HID), (HID, 1), (NOUT, HID), (NOUT, 1)):
        n = r * c
        out.append(th[:, i : i + n].reshape(p, r, c))
        i += n
    return out


class Net:
    """Batched forward pass: one weight set per replica. Observations are [R, K, 12]."""

    def __init__(self, theta):
        w0, b0, w1, b1, w2, b2 = unpack(theta)
        self.w0t, self.w1t, self.w2t = w0.transpose(0, 2, 1), w1.transpose(0, 2, 1), w2.transpose(0, 2, 1)
        self.b0, self.b1, self.b2 = b0.transpose(0, 2, 1), b1.transpose(0, 2, 1), b2.transpose(0, 2, 1)

    def __call__(self, o):
        h = np.tanh(o @ self.w0t + self.b0)
        h = np.tanh(h @ self.w1t + self.b1)
        return h @ self.w2t + self.b2


def out_to_accel(u):
    x = np.tanh(u)
    return np.where(x >= 0, A_MAX * x, B_POLICY * x)


def init_theta(rng, scale=0.15):
    return rng.normal(0.0, scale, DIM)


class Ring:
    def __init__(self, reps, cfg, human, seed, k=1, shield=False, memory="ema", pair_noise=True, hetero=False):
        self.R, self.c, self.h, self.k = reps, cfg, human, k
        self.N = cfg.n
        self.rng = np.random.default_rng(seed)
        self.pair = pair_noise and reps % 2 == 0
        self.shield, self.memory = shield, memory
        self.spacing = cfg.length / cfg.n
        self.x = np.tile(np.arange(self.N) * self.spacing, (reps, 1)) + self.rng.normal(0, 0.1, (reps, self.N))
        if self.pair:
            self.x[reps // 2 :] = self.x[: reps // 2]
        ue = uniform_speed(self.spacing - human.length, human)
        self.ue = ue
        self.v = np.full((reps, self.N), ue)
        self.av = np.linspace(0, self.N, k, endpoint=False).astype(int)
        self.mask = np.zeros(self.N, bool)
        self.mask[self.av] = True
        self.alive = np.ones(reps, bool)
        self.a_prev = np.zeros((reps, k))
        self.mem = np.zeros((reps, k, 3))
        self.ema_v = np.full((reps, k), ue)
        self.ema_g = np.full((reps, k), self.spacing - human.length)
        self.scale = (
            {k_: np.exp(self.rng.normal(0, 0.15, (reps, self.N))) for k_ in ("a", "T")} if hetero else None
        )
        self.reset_acc()

    def reset_acc(self):
        self.t = 0
        self.sum_v = np.zeros(self.R)
        self.sum_sd = np.zeros(self.R)
        self.sum_e = np.zeros(self.R)
        self.sum_dist = np.zeros(self.R)
        self.sum_acc = np.zeros(self.R)
        self.sum_gap = np.zeros(self.R)
        self.min_gap = np.full(self.R, 1e9)
        self.min_tg = np.full(self.R, 1e9)
        self.interv = np.zeros(self.R)
        self.coll_av_rear = np.zeros(self.R, bool)
        self.coll_h_rear = np.zeros(self.R, bool)
        self.live_t = np.zeros(self.R)

    def gaps(self):
        lead = np.roll(self.x, -1, axis=1)
        vl = np.roll(self.v, -1, axis=1)
        gap = lead - self.x - self.h.length
        gap[:, -1] += self.c.length
        return gap, vl

    def obs(self):
        gap, vl = self.gaps()
        i = self.av
        v, vla, g = self.v[:, i], vl[:, i], gap[:, i]
        o = np.zeros((self.R, self.k, IN))
        o[..., 0] = v / 20.0
        o[..., 1] = vla / 20.0
        o[..., 2] = np.minimum(g, 40.0) / 40.0
        o[..., 3] = (vla - v) / 5.0
        o[..., 4] = 1.0
        if self.memory == "ema":
            o[..., 8] = self.ema_v / 20.0
            o[..., 9] = np.minimum(self.ema_g, 40.0) / 40.0
        elif self.memory == "learned":
            o[..., 8:11] = self.mem
        o[..., 11] = self.a_prev / A_MAX
        return o

    def step(self, a_av=None, out_mem=None):
        c, h, dt = self.c, self.h, self.c.dt
        gap, vl = self.gaps()
        if self.scale is None:
            a = idm(self.v, vl, gap, h)
        else:
            a = idm(self.v, vl, gap, h.with_(a=h.a * self.scale["a"], T=h.T * self.scale["T"]))
        noise = self.rng.normal(0, h.noise * np.sqrt(0.1 / dt), (self.R // 2 if self.pair else self.R, self.N))
        if self.pair:
            noise = np.concatenate([noise, noise])
        a = a + noise
        i = self.av
        if a_av is not None:
            a[:, i] = a_av
        else:
            a[:, i] -= noise[:, i]
        interv = np.zeros(self.R)
        if self.shield and a_av is not None:
            lim = (shield_limit(self.v[:, i], vl[:, i], gap[:, i], dt) - self.v[:, i]) / dt
            hit = a[:, i] > lim
            a[:, i] = np.minimum(a[:, i], lim)
            interv = hit.mean(axis=1)
        a = np.maximum(a, -PHYS_B)
        a = np.where(self.alive[:, None], a, 0.0)
        v1 = np.maximum(self.v + a * dt, 0.0)
        ar = (v1 - self.v) / dt
        self.x = self.x + 0.5 * (self.v + v1) * dt
        self.v = np.where(self.alive[:, None], v1, 0.0)
        self.a_prev = ar[:, i]
        if self.memory == "learned" and out_mem is not None:
            self.mem += (dt / 10.0) * (np.tanh(out_mem) - self.mem)
        k = dt / 30.0
        self.ema_v += k * (self.v[:, i] - self.ema_v)
        self.ema_g += k * (gap[:, i] - self.ema_g)

        gap1, vl1 = self.gaps()
        hit = gap1 < 0.0
        any_hit = hit.any(axis=1) & self.alive
        if any_hit.any():
            self.coll_av_rear |= hit[:, i].any(axis=1) & any_hit
            self.coll_h_rear |= (hit & ~self.mask).any(axis=1) & any_hit
            self.alive &= ~any_hit
        al = self.alive
        mv = self.v.mean(axis=1)
        self.sum_v += mv * al
        self.sum_sd += self.v.std(axis=1, ddof=1) * al
        self.sum_e += energy_power(ar, self.v).sum(axis=1) * dt * al
        self.sum_dist += self.v.sum(axis=1) * dt * al
        self.sum_acc += (ar[:, i] ** 2).mean(axis=1) * al
        self.sum_gap += gap1[:, i].mean(axis=1) * al
        self.min_gap = np.where(al, np.minimum(self.min_gap, gap1[:, i].min(axis=1)), self.min_gap)
        tg = gap1[:, i] / np.maximum(self.v[:, i], 1.0)
        self.min_tg = np.where(al, np.minimum(self.min_tg, tg.min(axis=1)), self.min_tg)
        self.interv += interv * al
        self.live_t += al
        self.t += 1
        return mv, ar


REWARDS = {
    # weights on: speed, SD, energy, AV accel^2, shield intervention, collision
    "full": (1.0, 0.5, 0.0, 0.05, 0.5, 5.0),
    "speed": (1.0, 0.0, 0.0, 0.0, 0.0, 5.0),
    "energy": (0.0, 0.0, 1.0, 0.0, 0.0, 5.0),
    "energy_full": (1.0, 0.5, 0.5, 0.05, 0.5, 5.0),
}


def fitness_from(env, reward, horizon_steps):
    w = REWARDS[reward]
    nt = max(horizon_steps, 1)
    ue = env.ue
    wh_km = env.sum_e / 3600.0 / np.maximum(env.sum_dist / 1000.0, 1e-3)
    energy = np.minimum(wh_km, 2000.0) / 200.0
    if reward == "energy":
        # Raw energy use per second, the naive objective. Zero distance is zero energy.
        energy = env.sum_e / nt / (env.N * 5000.0)
    f = (
        w[0] * env.sum_v / nt / ue
        - w[1] * env.sum_sd / nt / ue
        - w[2] * energy
        - w[3] * env.sum_acc / nt / 9.0
        - w[4] * env.interv / nt
        - w[5] * (~env.alive)
    )
    return f


def policy_rollout(theta, cfg, human, seed, k=1, shield=False, memory="ema", warm=True, env_kw=None):
    R = theta.shape[0]
    env = Ring(R, cfg, human, seed, k=k, shield=shield, memory=memory, **(env_kw or {}))
    net = Net(theta)
    for _ in range(int(cfg.warm / cfg.dt)):
        env.step()
    env.reset_acc()
    steps = int(cfg.horizon / cfg.dt)
    for _ in range(steps):
        u = net(env.obs())
        env.step(out_to_accel(u[..., 0]), u[..., 1:])
    return env, steps


def summary(env, steps, cfg):
    t = np.maximum(env.live_t, 1)
    wh = env.sum_e / 3600.0 / np.maximum(env.sum_dist / 1000.0, 1e-3)
    v = env.sum_v / t
    return dict(
        speed=v,
        flow=v * cfg.n / cfg.length * 3600.0,
        sd=env.sum_sd / t,
        wh_km=wh,
        acc_rms=np.sqrt(env.sum_acc / t),
        gap=env.sum_gap / t,
        min_gap=env.min_gap,
        min_tg=env.min_tg,
        shield=env.interv / t,
        coll=(~env.alive).astype(float),
        coll_av=env.coll_av_rear.astype(float),
        coll_h=env.coll_h_rear.astype(float),
        survived=env.live_t / max(steps, 1),
    )


# Designed comparison controllers. Each returns the AV acceleration from env state.
class IdmAV:
    name = "IDM (no noise)"

    def __init__(self, env, **kw):
        self.env = env

    def __call__(self):
        return None


class FollowerStopper:
    name = "FollowerStopper, oracle U"

    def __init__(self, env, u_factor=1.0, **kw):
        self.env, self.U = env, env.ue * u_factor

    def __call__(self):
        e = self.env
        gap, vl = e.gaps()
        i = e.av
        dx, v, va = gap[:, i], vl[:, i], e.v[:, i]
        dv = np.minimum(v - va, 0.0)
        x1 = 4.5 + dv * dv / (2 * 1.5)
        x2 = 5.25 + dv * dv / (2 * 1.0)
        x3 = 6.0 + dv * dv / (2 * 0.5)
        vb = np.minimum(np.maximum(v, 0), self.U)
        cmd = np.where(
            dx <= x1, 0.0,
            np.where(dx <= x2, vb * (dx - x1) / np.maximum(x2 - x1, 1e-6),
                     np.where(dx <= x3, vb + (self.U - vb) * (dx - x2) / np.maximum(x3 - x2, 1e-6), self.U)))
        return np.clip((cmd - va) / 0.5, -B_POLICY, A_MAX)


class PISaturation:
    name = "PI with saturation"

    def __init__(self, env, **kw):
        self.env = env
        n = int(38.0 / env.c.dt)
        self.buf = np.tile(env.v[:, env.av][None], (n, 1, 1))
        self.j = 0
        self.cmd = env.v[:, env.av].copy()

    def __call__(self):
        e = self.env
        gap, vl = e.gaps()
        i = e.av
        dx, v = gap[:, i], vl[:, i]
        self.buf[self.j] = e.v[:, i]
        self.j = (self.j + 1) % self.buf.shape[0]
        U = self.buf.mean(axis=0)
        tgt = U + 1.0 * np.clip((dx - 7.0) / 23.0, 0, 1)
        dv = v - e.v[:, i]
        xs = np.maximum(2.0 * np.maximum(-dv, 0.0), 4.0)
        alpha = np.clip((dx - xs) / 2.0, 0, 1)
        beta = 1.0 - 0.5 * alpha
        # Stern's rule is per 0.05 s measurement; time-scale beta to this dt.
        beta = 1.0 - (1.0 - beta) ** (e.c.dt / 0.05)
        self.cmd = beta * (alpha * tgt + (1 - alpha) * v) + (1 - beta) * self.cmd
        return np.clip((self.cmd - e.v[:, i]) / 0.5, -B_POLICY, A_MAX)


def controller_rollout(ctrl_cls, cfg, human, seed, R=32, k=1, shield=False, env_kw=None, **kw):
    env = Ring(R, cfg, human, seed, k=k, shield=shield, **(env_kw or {}))
    for _ in range(int(cfg.warm / cfg.dt)):
        env.step()
    ctrl = ctrl_cls(env, **kw)
    env.reset_acc()
    steps = int(cfg.horizon / cfg.dt)
    for _ in range(steps):
        env.step(ctrl())
    return env, steps


def agg(s):
    return {k: float(np.mean(v)) for k, v in s.items()}


def cmd_calibrate(a):
    cfg = RING.with_(horizon=400.0)
    rows = []
    for aa in (0.5, 0.6, 0.73, 1.0):
        for T in (0.7, 0.8, 0.9, 1.0):
            for b in (1.5, 2.0):
                h = HUMAN.with_(a=aa, T=T, b=b)
                e, st = controller_rollout(IdmAV, cfg, h, 1, R=16)
                s = agg(summary(e, st, cfg))
                rows.append(dict(a=aa, T=T, b=b, ue=e.ue, speed=s["speed"], flow=s["flow"], sd=s["sd"], coll=s["coll"]))
                print(rows[-1], flush=True)
    OUT.mkdir(exist_ok=True)
    (OUT / "calibrate.json").write_text(json.dumps(rows, indent=1))


def baseline_table(cfg, human, R, seed, k=1):
    out = {}
    for cls in (IdmAV, FollowerStopper, PISaturation):
        e, st = controller_rollout(cls, cfg, human, seed, R=R, k=k)
        out[cls.name] = agg(summary(e, st, cfg))
    return out


def argd(a):
    return {k: v for k, v in vars(a).items() if k != "fn"}


class Adam:
    def __init__(self, dim, lr):
        self.lr, self.m, self.s, self.t = lr, np.zeros(dim), np.zeros(dim), 0

    def step(self, g):
        self.t += 1
        self.m = 0.9 * self.m + 0.1 * g
        self.s = 0.999 * self.s + 0.001 * g * g
        return self.lr * (self.m / (1 - 0.9**self.t)) / (np.sqrt(self.s / (1 - 0.999**self.t)) + 1e-8)


def rank_shape(f):
    r = np.empty(f.size)
    r[np.argsort(f)] = np.arange(f.size)
    return r / (f.size - 1) - 0.5


def es_train(rollout, seed, gens, pairs, sigma, lr, eval_every, val_fn, theta0=None, decay=0.002, log=None):
    rng = np.random.default_rng(seed)
    theta = init_theta(rng) if theta0 is None else theta0.copy()
    opt = Adam(DIM, lr)
    best, best_val = theta.copy(), -1e18
    curve = []
    updates = 0
    t0 = time.time()
    for g in range(gens):
        eps = rng.normal(0, 1, (pairs, DIM))
        th = np.concatenate([theta + sigma * eps, theta - sigma * eps])
        f, n = rollout(th, int(rng.integers(1 << 31)))
        updates += n
        s = rank_shape(f)
        grad = ((s[:pairs] - s[pairs:]) @ eps) / (2 * pairs * sigma)
        theta = theta + opt.step(grad - decay * theta)
        if g % eval_every == 0 or g == gens - 1:
            val = val_fn(theta)
            row = dict(gen=g, updates=updates, wall=time.time() - t0, train_f=float(f.mean()), train_coll=float(np.mean(f < -3.0)), **val)
            curve.append(row)
            if val["score"] > best_val:
                best_val, best = val["score"], theta.copy()
            print(json.dumps(row), flush=True)
            if log:
                log(curve, best)
    return best, curve


def ring_val(cfg, human, memory, shield, reward, k=1):
    # Fixed validation seeds, never the test seeds.
    def val(theta):
        th = np.tile(theta, (16, 1))
        env, steps = policy_rollout(th, cfg, human, 900001, k=k, shield=shield, memory=memory)
        s = agg(summary(env, steps, cfg))
        return dict(score=float(fitness_from(env, reward, steps).mean()), speed=s["speed"], sd=s["sd"], flow=s["flow"], coll=s["coll"], wh_km=s["wh_km"], shield=s["shield"], gap=s["gap"])
    return val


def cmd_es_ring(a):
    cfg = RING.with_(warm=a.warm, horizon=a.horizon)
    if a.lmin:
        pass
    h = HUMAN
    def rollout(th, seed):
        if a.lmin:
            r = np.random.default_rng(seed)
            c = cfg.with_(length=float(r.uniform(a.lmin, a.lmax)))
        else:
            c = cfg
        env, steps = policy_rollout(th, c, h, seed, k=a.k, shield=a.shield, memory=a.memory)
        return fitness_from(env, a.reward, steps), (int(c.warm / c.dt) + steps) * c.n * th.shape[0]
    val = ring_val(cfg, h, a.memory, a.shield, a.reward, k=a.k)
    OUT.mkdir(exist_ok=True)
    tag = a.tag
    def log(curve, best):
        np.savez(OUT / f"{tag}.npz", theta=best, curve=json.dumps(curve), args=json.dumps(argd(a)))
    theta0 = np.load(a.init)["theta"] if a.init else None
    best, curve = es_train(rollout, a.seed, a.gens, a.pairs, a.sigma, a.lr, a.eval_every, val, theta0=theta0, log=log)
    log(curve, best)


def test_matrix(act_factory, R=32, seed=777001, memory="ema", k=1):
    """Held-out seeds, then conditions the policy never saw. act_factory(cfg, human, seed, R, shield, k, env_kw) -> summary."""
    h = HUMAN
    base = RING.with_(horizon=600.0)
    conds = {
        "test seeds": (base, h, {}, 1),
        "test seeds, shield": (base, h, dict(shield=True), 1),
        "L=220": (base.with_(length=220.0), h, {}, 1),
        "L=240": (base.with_(length=240.0), h, {}, 1),
        "L=300": (base.with_(length=300.0), h, {}, 1),
        "L=400": (base.with_(length=400.0), h, {}, 1),
        "humans a=1.6": (base, h.with_(a=1.6), {}, 1),
        "humans b=2.5": (base, h.with_(b=2.5), {}, 1),
        "humans T=0.9": (base, h.with_(T=0.9), {}, 1),
        "noise x2": (base, h.with_(noise=0.4), {}, 1),
        "hetero humans": (base, h, dict(env_kw=dict(hetero=True)), 1),
        "dt=0.05": (base.with_(dt=0.05), h, {}, 1),
        "dt=0.5": (base.with_(dt=0.5), h, {}, 1),
        "dt=1.0": (base.with_(dt=1.0), h, {}, 1),
        "k=3 of 22": (base, h, {}, 3),
        "k=11 of 22": (base, h, {}, 11),
        "k=22 of 22": (base, h, {}, 22),
    }
    out = {}
    for name, (c, hu, kw, kk) in conds.items():
        out[name] = agg(act_factory(c, hu, seed, R, kk, **kw))
    return out


def policy_factory(theta, memory):
    def f(c, h, seed, R, k, shield=False, env_kw=None):
        th = np.tile(theta, (R, 1))
        e, st = policy_rollout(th, c, h, seed, k=k, shield=shield, memory=memory, env_kw=env_kw)
        return summary(e, st, c)
    return f


def ctrl_factory(cls, **kw0):
    def f(c, h, seed, R, k, shield=False, env_kw=None):
        if k == c.n and cls is not IdmAV:
            pass
        e, st = controller_rollout(cls, c, h, seed, R=R, k=k, shield=shield, env_kw=env_kw, **kw0)
        return summary(e, st, c)
    return f


def brake_test(act, cfg, h, seed, R=64, b=9.0, every=60.0, memory="ema", shield=False):
    """The car ahead of the AV brakes hard to a stop at random times, then drives on."""
    if act == "idm":
        env = Ring(R, cfg, h, seed, k=1, shield=False, memory=memory)
        net = None
    else:
        env = Ring(R, cfg, h, seed, k=1, shield=shield, memory=memory)
        net = Net(np.tile(act, (R, 1)))
    for _ in range(int(cfg.warm / cfg.dt)):
        env.step()
    env.reset_acc()
    rng = np.random.default_rng(seed + 1)
    steps = int(cfg.horizon / cfg.dt)
    lead = (env.av[0] + 1) % env.N
    brake = np.zeros(R, bool)
    for s in range(steps):
        start = rng.random(R) < cfg.dt / every
        brake = (brake | start) & (env.v[:, lead] > 0.05)
        u = net(env.obs()) if net is not None else None
        env_noise_a = out_to_accel(u[..., 0]) if u is not None else None
        v_before = env.v[:, lead].copy()
        x_before = env.x[:, lead].copy()
        env.step(env_noise_a, u[..., 1:] if u is not None else None)
        v1 = np.maximum(v_before - b * cfg.dt, 0.0)
        env.v[:, lead] = np.where(brake, v1, env.v[:, lead])
        env.x[:, lead] = np.where(brake, x_before + 0.5 * (v_before + v1) * cfg.dt, env.x[:, lead])
    return agg(summary(env, steps, cfg))


def cmd_eval(a):
    out = {}
    memory_of = {}
    for path in a.policies:
        z = np.load(path)
        args = json.loads(str(z["args"]))
        tag = Path(path).stem
        memory = args.get("memory", "ema")
        memory_of[tag] = memory
        out[tag] = test_matrix(policy_factory(z["theta"], memory))
        print(tag, json.dumps(out[tag]["test seeds"]), flush=True)
    res = OUT / f"{a.out}.json"
    if a.baselines:
        for cls, kw in ((IdmAV, {}), (FollowerStopper, {}), (PISaturation, {})):
            out[cls.name] = test_matrix(ctrl_factory(cls, **kw))
            print(cls.name, json.dumps(out[cls.name]["test seeds"]), flush=True)
    res.write_text(json.dumps(out, indent=1))


def cmd_brake(a):
    cfg = RING.with_(horizon=600.0)
    out = {}
    for path in a.policies:
        z = np.load(path)
        args = json.loads(str(z["args"]))
        tag = Path(path).stem
        for sh in (False, True):
            r = brake_test(z["theta"], cfg, HUMAN, 555, memory=args.get("memory", "ema"), shield=sh)
            out[f"{tag}{' + shield' if sh else ''}"] = r
            print(tag, sh, json.dumps(r), flush=True)
    r = brake_test("idm", cfg, HUMAN, 555)
    out["IDM"] = r
    print("IDM", json.dumps(r))
    (OUT / f"{a.out}.json").write_text(json.dumps(out, indent=1))


def cmd_baselines(a):
    cfg = RING.with_(horizon=600.0)
    t = baseline_table(cfg, HUMAN, 32, 777001)
    t["uniform"] = dict(ue=uniform_speed(cfg.length / cfg.n - HUMAN.length, HUMAN))
    print(json.dumps(t, indent=1))
    OUT.mkdir(exist_ok=True)
    (OUT / "ring-baselines.json").write_text(json.dumps(t, indent=1))


def cmd_ppo(a):
    import torch
    torch.set_num_threads(1)
    torch.manual_seed(a.seed)
    cfg = RING.with_(warm=a.warm, horizon=a.horizon)

    class AC(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.pi = torch.nn.Sequential(torch.nn.Linear(IN, HID), torch.nn.Tanh(), torch.nn.Linear(HID, HID), torch.nn.Tanh(), torch.nn.Linear(HID, NOUT))
            self.logstd = torch.nn.Parameter(torch.full((1,), -0.7))
            self.v = torch.nn.Sequential(torch.nn.Linear(IN, 64), torch.nn.Tanh(), torch.nn.Linear(64, 64), torch.nn.Tanh(), torch.nn.Linear(64, 1))

        def mean(self, o):
            return self.pi(o)[..., 0]

    ac = AC()
    opt = torch.optim.Adam(ac.parameters(), lr=a.lr)
    w = REWARDS[a.reward]

    def theta_of():
        sd = ac.pi.state_dict()
        return np.concatenate([
            sd["0.weight"].numpy().ravel(), sd["0.bias"].numpy().ravel(),
            sd["2.weight"].numpy().ravel(), sd["2.bias"].numpy().ravel(),
            sd["4.weight"].numpy().ravel(), sd["4.bias"].numpy().ravel()])

    val = ring_val(cfg, HUMAN, "ema", a.shield, a.reward, k=a.k)
    OUT.mkdir(exist_ok=True)
    curve, best, best_val = [], theta_of(), -1e18
    updates, t0 = 0, time.time()
    rng = np.random.default_rng(a.seed)
    steps = int(cfg.horizon / cfg.dt)
    rep = a.repeat
    for it in range(a.iters):
        env = Ring(a.envs, cfg, HUMAN, int(rng.integers(1 << 31)), k=a.k, shield=a.shield, memory="ema", pair_noise=False)
        for _ in range(int(cfg.warm / cfg.dt)):
            env.step()
        env.reset_acc()
        O, A, LP, Rw, D = [], [], [], [], []
        for s in range(0, steps, rep):
            o = env.obs()
            with torch.no_grad():
                to = torch.as_tensor(o, dtype=torch.float32)
                mu = ac.mean(to)
                std = ac.logstd.exp()
                dist = torch.distributions.Normal(mu, std)
                act = dist.sample()
                lp = dist.log_prob(act)
            acc = out_to_accel(act.numpy().astype(np.float64))
            r = np.zeros(a.envs)
            alive0 = env.alive.copy()
            for _ in range(rep):
                mv, ar = env.step(acc)
                r += w[0] * mv / env.ue - w[1] * env.v.std(axis=1, ddof=1) / env.ue - w[3] * (ar[:, env.av] ** 2).mean(axis=1) / 9.0
            r = r / rep * (alive0 & env.alive)
            hit = alive0 & ~env.alive
            r = r - hit * w[5] * 20.0
            O.append(o), A.append(act.numpy()), LP.append(lp.numpy()), Rw.append(np.repeat(r[:, None], a.k, 1)), D.append(np.repeat((~env.alive)[:, None], a.k, 1))
        O, A, LP, Rw, D = map(np.array, (O, A, LP, Rw, D))
        updates += (int(cfg.warm / cfg.dt) + steps) * cfg.n * a.envs
        T, E, K = Rw.shape
        with torch.no_grad():
            V = ac.v(torch.as_tensor(O, dtype=torch.float32))[..., 0].numpy()
            last = ac.v(torch.as_tensor(env.obs(), dtype=torch.float32))[..., 0].numpy()
        adv = np.zeros_like(Rw)
        g = np.zeros((E, K))
        nextv = last
        lam, gamma = 0.95, a.gamma
        for t in range(T - 1, -1, -1):
            nd = 1.0 - D[t]
            delta = Rw[t] + gamma * nextv * nd - V[t]
            g = delta + gamma * lam * nd * g
            adv[t] = g
            nextv = V[t]
        ret = adv + V
        O2 = torch.as_tensor(O.reshape(-1, IN), dtype=torch.float32)
        A2 = torch.as_tensor(A.reshape(-1), dtype=torch.float32)
        LP2 = torch.as_tensor(LP.reshape(-1), dtype=torch.float32)
        AD = torch.as_tensor(adv.reshape(-1), dtype=torch.float32)
        AD = (AD - AD.mean()) / (AD.std() + 1e-6)
        RT = torch.as_tensor(ret.reshape(-1), dtype=torch.float32)
        n = O2.shape[0]
        for ep in range(a.epochs):
            perm = torch.randperm(n)
            for b in range(0, n, a.minibatch):
                ix = perm[b : b + a.minibatch]
                d = torch.distributions.Normal(ac.mean(O2[ix]), ac.logstd.exp())
                lp = d.log_prob(A2[ix])
                ratio = (lp - LP2[ix]).exp()
                l1 = -(AD[ix] * ratio).mean()
                l2 = -(AD[ix] * ratio.clamp(0.8, 1.2)).mean()
                vl = ((ac.v(O2[ix])[..., 0] - RT[ix]) ** 2).mean()
                loss = torch.max(l1, l2) + 0.5 * vl - 0.0 * d.entropy().mean()
                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(ac.parameters(), 0.5)
                opt.step()
        if it % a.eval_every == 0 or it == a.iters - 1:
            th = theta_of()
            v = val(th)
            row = dict(gen=it, updates=updates, wall=time.time() - t0, train_f=float(Rw.mean()), train_coll=float((~env.alive).mean()), std=float(ac.logstd.exp()), **v)
            curve.append(row)
            if v["score"] > best_val:
                best_val, best = v["score"], th.copy()
            print(json.dumps(row), flush=True)
            np.savez(OUT / f"{a.tag}.npz", theta=best, curve=json.dumps(curve), args=json.dumps(argd(a) | dict(memory="ema")))


def cmd_bc(a):
    import torch
    torch.set_num_threads(1)
    torch.manual_seed(a.seed)
    cfg = RING.with_(horizon=300.0)
    expert = {"pi": PISaturation, "fs": FollowerStopper}[a.expert]
    O, Y = [], []
    rng = np.random.default_rng(a.seed)
    theta = None

    class Pi(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.pi = torch.nn.Sequential(torch.nn.Linear(IN, HID), torch.nn.Tanh(), torch.nn.Linear(HID, HID), torch.nn.Tanh(), torch.nn.Linear(HID, NOUT))

    net = Pi()
    opt = torch.optim.Adam(net.parameters(), lr=3e-3)
    curve = []
    for round_ in range(a.rounds):
        env = Ring(32, cfg, HUMAN, int(rng.integers(1 << 31)), k=1, memory="ema", pair_noise=False)
        for _ in range(int(cfg.warm / cfg.dt)):
            env.step()
        ctrl = expert(env)
        pol = Net(np.tile(theta, (32, 1))) if theta is not None else None
        for s in range(int(cfg.horizon / cfg.dt)):
            o = env.obs()
            label = ctrl()
            O.append(o.reshape(-1, IN).copy())
            Y.append(label.reshape(-1).copy())
            if pol is None or a.rounds == 1:
                env.step(label)
            else:
                env.step(out_to_accel(pol(o)[..., 0]))
        Xt = torch.as_tensor(np.concatenate(O), dtype=torch.float32)
        Yt = torch.as_tensor(np.concatenate(Y), dtype=torch.float32)
        # Regress in the policy's squashed output: acceleration in m/s^2.
        n = Xt.shape[0]
        for ep in range(a.epochs):
            perm = torch.randperm(n)
            for b in range(0, n, 2048):
                ix = perm[b : b + 2048]
                u = net.pi(Xt[ix])[..., 0]
                x = torch.tanh(u)
                acc = torch.where(x >= 0, A_MAX * x, B_POLICY * x)
                loss = ((acc - Yt[ix]) ** 2).mean()
                opt.zero_grad()
                loss.backward()
                opt.step()
        sd = net.pi.state_dict()
        theta = np.concatenate([sd[k].numpy().ravel() for k in ("0.weight", "0.bias", "2.weight", "2.bias", "4.weight", "4.bias")])
        e, st = policy_rollout(np.tile(theta, (16, 1)), cfg, HUMAN, 900001, memory="ema")
        s = agg(summary(e, st, cfg))
        row = dict(round=round_, samples=int(n), loss=float(loss), **{k: s[k] for k in ("speed", "sd", "flow", "wh_km", "coll", "gap")})
        curve.append(row)
        print(json.dumps(row), flush=True)
    OUT.mkdir(exist_ok=True)
    np.savez(OUT / f"{a.tag}.npz", theta=theta, curve=json.dumps(curve), args=json.dumps(argd(a) | dict(memory="ema")))


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("calibrate"); c.set_defaults(fn=cmd_calibrate)
    c = sp.add_parser("baselines"); c.set_defaults(fn=cmd_baselines)
    c = sp.add_parser("es-ring"); c.set_defaults(fn=cmd_es_ring)
    c.add_argument("--tag", required=True); c.add_argument("--seed", type=int, default=0)
    c.add_argument("--gens", type=int, default=200); c.add_argument("--pairs", type=int, default=32)
    c.add_argument("--sigma", type=float, default=0.1); c.add_argument("--lr", type=float, default=0.03)
    c.add_argument("--memory", default="ema"); c.add_argument("--reward", default="full")
    c.add_argument("--shield", action="store_true"); c.add_argument("--k", type=int, default=1)
    c.add_argument("--warm", type=float, default=120.0); c.add_argument("--horizon", type=float, default=300.0)
    c.add_argument("--eval-every", type=int, default=10); c.add_argument("--init", default=None)
    c.add_argument("--lmin", type=float, default=0.0); c.add_argument("--lmax", type=float, default=0.0)
    c = sp.add_parser("ppo"); c.set_defaults(fn=cmd_ppo)
    c.add_argument("--tag", required=True); c.add_argument("--seed", type=int, default=0)
    c.add_argument("--iters", type=int, default=100); c.add_argument("--envs", type=int, default=16)
    c.add_argument("--repeat", type=int, default=5); c.add_argument("--lr", type=float, default=3e-4)
    c.add_argument("--gamma", type=float, default=0.99); c.add_argument("--epochs", type=int, default=5)
    c.add_argument("--minibatch", type=int, default=2048); c.add_argument("--reward", default="full")
    c.add_argument("--shield", action="store_true"); c.add_argument("--k", type=int, default=1)
    c.add_argument("--warm", type=float, default=120.0); c.add_argument("--horizon", type=float, default=300.0)
    c.add_argument("--eval-every", type=int, default=5)
    c = sp.add_parser("bc"); c.set_defaults(fn=cmd_bc)
    c.add_argument("--tag", required=True); c.add_argument("--seed", type=int, default=0)
    c.add_argument("--expert", default="pi"); c.add_argument("--rounds", type=int, default=1)
    c.add_argument("--epochs", type=int, default=30)
    c = sp.add_parser("eval"); c.set_defaults(fn=cmd_eval)
    c.add_argument("policies", nargs="*"); c.add_argument("--out", required=True); c.add_argument("--baselines", action="store_true")
    c = sp.add_parser("brake"); c.set_defaults(fn=cmd_brake)
    c.add_argument("policies", nargs="*"); c.add_argument("--out", required=True)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
