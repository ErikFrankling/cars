#!/usr/bin/env python3
"""On-ramp merge for research/truth/13-learned-drivers.md. Same 212-float network as learned_drivers.py.

One main lane of 1000 m, a ramp from 400 m to a merge zone at 600-800 m. Demand waits in a queue at
each entrance, so a policy cannot look good by keeping cars out. Humans are IDM with noise. A waiting
ramp head is let in by the first main car behind it after 5 s (Erik's courtesy requirement, crude).

  nix develop --command python3 -I research/truth/scripts/learned_merge.py <command> ...
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import learned_drivers as ld  # noqa: E402

OUT = ld.OUT
HUMAN = ld.P(a=1.0, b=1.5, T=1.0, s0=2.0, v0=25.0, noise=0.2, length=5.0)
C = ld.P(L=1000.0, ramp0=400.0, z0=600.0, z1=800.0, dt=0.2, warm=150.0, horizon=400.0, qm=2000.0, qr=400.0, pav=0.1, nmax=160, ramp_v0=20.0)


class Merge:
    def __init__(self, R, c, h, seed, shield=False, obsmode="v2x", kind="policy", pair=True):
        self.R, self.c, self.h = R, c, h
        self.rng = np.random.default_rng(seed)
        self.pair = pair and R % 2 == 0
        self.shield, self.obsmode, self.kind = shield, obsmode, kind
        n = c.nmax
        self.x = np.zeros((R, n))
        self.v = np.zeros((R, n))
        self.a_prev = np.zeros((R, n))
        self.active = np.zeros((R, n), bool)
        self.ramp = np.zeros((R, n), bool)
        self.av = np.zeros((R, n), bool)
        self.ema = np.zeros((R, n))
        self.ema_g = np.full((R, n), 20.0)
        self.qm = np.zeros(R)
        self.qr = np.zeros(R)
        self.alive = np.ones(R, bool)
        self.wait = np.zeros(R)
        self.overflow = np.zeros(R, int)
        self.reset_acc()

    def reset_acc(self):
        R = self.R
        self.delay = np.zeros(R)
        self.net_v = np.zeros(R)
        self.net_n = np.zeros(R)
        self.out = np.zeros(R)
        self.energy = np.zeros(R)
        self.dist = np.zeros(R)
        self.acc2 = np.zeros(R)
        self.acc_n = np.zeros(R)
        self.interv = np.zeros(R)
        self.merges = np.zeros(R)
        self.courtesy = np.zeros(R)
        self.min_gap_av = np.full(R, 1e9)
        self.coll_av = np.zeros(R, bool)
        self.t = 0
        self.live = np.zeros(R)

    def _spawn(self, r, ramp, is_av):
        slot = np.argmin(self.active[r])
        if self.active[r, slot]:
            self.overflow[r] += 1
            return False
        c = self.c
        x0 = c.ramp0 if ramp else 0.0
        sel = self.active[r] & (self.ramp[r] == ramp)
        v0 = min(c.ramp_v0 if ramp else self.h.v0, 15.0)
        if sel.any():
            xt = self.x[r][sel].min()
            gap = xt - x0 - self.h.length
            vt = self.v[r][sel][np.argmin(self.x[r][sel])]
            if gap < 5.0 + 0.8 * vt:
                return False
            v0 = min(v0, vt + 2.0)
        self.x[r, slot], self.v[r, slot] = x0, v0
        self.active[r, slot], self.ramp[r, slot], self.av[r, slot] = True, ramp, is_av
        self.a_prev[r, slot] = 0.0
        self.ema[r, slot] = v0
        self.ema_g[r, slot] = 20.0
        return True

    def arrivals(self):
        c = self.c
        dt = c.dt
        half = self.R // 2 if self.pair else self.R
        am = self.rng.random(half) < c.qm / 3600.0 * dt
        ar = self.rng.random(half) < c.qr / 3600.0 * dt
        if self.pair:
            am, ar = np.concatenate([am, am]), np.concatenate([ar, ar])
        self.qm += am
        self.qr += ar
        p = self.rng.random((2, half))
        if self.pair:
            p = np.concatenate([p, p], axis=1)
        self.k = getattr(self, "k", 0) + 1
        if self.k % max(int(1.0 / dt), 1):
            return
        for r in np.nonzero(self.alive & ((self.qm >= 1) | (self.qr >= 1)))[0]:
            if self.qm[r] >= 1 and self._spawn(r, False, p[0, r] < c.pav):
                self.qm[r] -= 1
            if self.qr[r] >= 1 and self._spawn(r, True, p[1, r] < c.pav):
                self.qr[r] -= 1

    def structure(self):
        """Leader index per slot, in each lane, from one sort per replica."""
        R, n = self.R, self.c.nmax
        key = np.where(self.active, self.x + 1e5 * self.ramp, 1e9)
        order = np.argsort(key, axis=1)
        sx = np.take_along_axis(key, order, axis=1)
        nxt = np.empty((R, n), int)
        nxt[:, :-1] = order[:, 1:]
        nxt[:, -1] = order[:, -1]
        same = np.zeros((R, n), bool)
        same[:, :-1] = (sx[:, 1:] < 1e8) & ((sx[:, 1:] >= 1e5) == (sx[:, :-1] >= 1e5))
        lead = np.empty((R, n), int)
        has = np.empty((R, n), bool)
        np.put_along_axis(lead, order, nxt, axis=1)
        np.put_along_axis(has, order, same, axis=1)
        return lead, has & self.active, order

    def head_of_ramp(self):
        """Index of the most advanced ramp car per replica, -1 if none."""
        k = np.where(self.active & self.ramp, self.x, -1.0)
        h = np.argmax(k, axis=1)
        return np.where(k[np.arange(self.R), h] >= 0, h, -1)

    def neighbours(self, head):
        """Main-lane car just ahead of and just behind the ramp head."""
        R = np.arange(self.R)
        xh = np.where(head >= 0, self.x[R, np.maximum(head, 0)], -1e9)[:, None]
        main = self.active & ~self.ramp
        ahead = np.where(main & (self.x >= xh), self.x, 1e9)
        behind = np.where(main & (self.x < xh), self.x, -1e9)
        fi = np.argmin(ahead, axis=1)
        bi = np.argmax(behind, axis=1)
        return fi, ahead[R, fi] < 1e8, bi, behind[R, bi] > -1e8

    def obs(self, lead, has, head):
        c, h = self.c, self.h
        R = np.arange(self.R)
        o = np.zeros((self.R, c.nmax, ld.IN))
        vl = np.take_along_axis(self.v, lead, axis=1)
        xl = np.take_along_axis(self.x, lead, axis=1)
        gap = np.where(has, xl - self.x - h.length, 40.0)
        vl = np.where(has, vl, self.v)
        o[..., 0] = self.v / 20.0
        o[..., 1] = vl / 20.0
        o[..., 2] = np.minimum(gap, 40.0) / 40.0
        o[..., 3] = (vl - self.v) / 5.0
        o[..., 4] = 1.0
        o[..., 8] = self.ema / 20.0
        o[..., 9] = np.minimum(self.ema_g, 40.0) / 40.0
        o[..., 11] = self.a_prev / ld.A_MAX
        if self.obsmode == "v2x":
            xh = self.x[R, np.maximum(head, 0)][:, None]
            vh = self.v[R, np.maximum(head, 0)][:, None]
            hs = (head >= 0)[:, None]
            o[..., 6] = np.clip((c.z1 - self.x) / 200.0, -1.0, 1.0)
            o[..., 7] = np.where(hs, np.clip((xh - self.x) / 100.0, -1.0, 1.0), 1.0)
            o[..., 10] = np.where(hs, vh / 20.0, 0.0)
            zone = self.active & (self.x > c.z0) & ~self.ramp & (self.x < c.z1 + 150.0)
            mean = (self.v * zone).sum(axis=1) / np.maximum(zone.sum(axis=1), 1)
            o[..., 5] = (mean / 20.0)[:, None]
        return o, gap, vl

    def step(self, net=None):
        c, h, dt = self.c, self.h, self.c.dt
        Ri = np.arange(self.R)
        self.arrivals()
        lead, has, _ = self.structure()
        head = self.head_of_ramp()
        o, gap, vl = self.obs(lead, has, head)
        v0 = np.where(self.ramp, c.ramp_v0, h.v0)
        a = ld.idm(self.v, vl, gap, h.with_(v0=v0))
        free = ~has
        a = np.where(free, h.a * (1.0 - (self.v / v0) ** 4), a)
        noise_half = (self.R // 2 if self.pair else self.R, c.nmax)
        nz = self.rng.normal(0.0, h.noise * np.sqrt(0.1 / dt), noise_half)
        if self.pair:
            nz = np.concatenate([nz, nz])
        a = a + nz * (~self.av)

        # Ramp cars stop at the end of the zone, ramp head adjusts to the main car ahead of it.
        end_gap = c.z1 - self.x
        # A driver keeps speed down the zone and brakes only when the end forces it.
        need = self.v * self.v / (2.0 * np.maximum(end_gap - 2.0, 0.1))
        a = np.where(self.ramp & (need > 2.0), np.minimum(a, -need), a)
        fi, fok, bi, bok = self.neighbours(head)
        ok = head >= 0
        hh = np.maximum(head, 0)
        if ok.any():
            xh, vh = self.x[Ri, hh], self.v[Ri, hh]
            gf = self.x[Ri, fi] - xh - h.length
            sync = ok & fok & (xh > c.z0 - 150.0) & (gf > 0.0)
            a_sync = ld.idm(vh, self.v[Ri, fi], np.maximum(gf, 0.1), h.with_(v0=c.ramp_v0))
            a[Ri[sync], hh[sync]] = np.minimum(a[Ri[sync], hh[sync]], a_sync[sync])
            inz = ok & (xh >= c.z0)
            self.wait = np.where(inz, self.wait + dt, 0.0)
            # Courtesy: the first main car behind opens the gap for a head that has waited.
            cour = inz & bok & (self.wait > 3.0) & ~self.av[Ri, bi]
            gb = xh - self.x[Ri, bi] - h.length
            cc = cour & (gb < 60.0)
            if cc.any():
                ab = ld.idm(self.v[Ri, bi], vh, np.maximum(gb, 0.1), h.with_(v0=h.v0))
                a[Ri[cc], bi[cc]] = np.minimum(a[Ri[cc], bi[cc]], ab[cc])
                self.courtesy += cc

        self.ema_g += (dt / 30.0) * (np.minimum(gap, 100.0) - self.ema_g)
        mask_av = self.av & self.active & ~self.ramp
        if net is not None and mask_av.any():
            u = net(o)
            ap = ld.out_to_accel(u[..., 0])
            a = np.where(mask_av, ap, a)
        elif callable(self.kind):
            a = self.kind(self, a, gap, vl, mask_av)
        interv = np.zeros(self.R)
        if self.shield and mask_av.any():
            gs = np.where(has, gap, 1e3)
            lim = (ld.shield_limit(self.v, vl, gs, dt) - self.v) / dt
            if self.shield:
                endlim = (ld.shield_limit(self.v, np.zeros_like(self.v), np.maximum(end_gap, 0.0), dt) - self.v) / dt
                lim = np.where(self.ramp, np.minimum(lim, endlim), lim)
            hit = mask_av & (a > lim)
            a = np.where(hit, lim, a)
            interv = hit.sum(axis=1) / np.maximum(mask_av.sum(axis=1), 1)
        a = np.maximum(a, -ld.PHYS_B)
        a = np.where(self.alive[:, None] & self.active, a, 0.0)
        v1 = np.maximum(self.v + a * dt, 0.0)
        ar = (v1 - self.v) / dt
        self.x = self.x + 0.5 * (self.v + v1) * dt
        self.v = v1
        self.a_prev = ar
        self.ema += (dt / 30.0) * (self.v - self.ema)

        # Merge: at most one per replica per step, the same gap rule for humans and policy cars.
        if ok.any():
            xh, vh = self.x[Ri, hh], self.v[Ri, hh]
            inz = ok & (xh >= c.z0) & self.alive
            gf = np.where(fok, self.x[Ri, fi] - xh - h.length, 1e3)
            gb = np.where(bok, xh - self.x[Ri, bi] - h.length, 1e3)
            vb = np.where(bok, self.v[Ri, bi], 0.0)
            vf = np.where(fok, self.v[Ri, fi], vh)
            need_f = 2.0 + 0.3 * vh + np.maximum(vh - vf, 0.0) ** 2 / 6.0
            need_b = 2.0 + 0.3 * vb + np.maximum(vb - vh, 0.0) ** 2 / 6.0
            go = inz & (gf >= need_f) & (gb >= need_b)
            self.ramp[Ri[go], hh[go]] = False
            self.merges += go
            self.wait = np.where(go, 0.0, self.wait)

        done = self.active & (self.x >= c.L)
        self.out += done.sum(axis=1)
        self.active &= ~done

        lead1, has1, _ = self.structure()
        xl = np.take_along_axis(self.x, lead1, axis=1)
        g1 = np.where(has1, xl - self.x - h.length, 1e3)
        hit = (g1 < 0.0) & self.active
        anyhit = hit.any(axis=1) & self.alive
        if anyhit.any():
            self.coll_av |= (hit & self.av).any(axis=1) & anyhit
            self.alive &= ~anyhit
        al = self.alive
        act = self.active
        self.delay += ((act * (1.0 - self.v / v0)).sum(axis=1) + self.qm + self.qr) * dt * al
        self.net_v += (self.v * act).sum(axis=1) * al
        self.net_n += act.sum(axis=1) * al
        self.energy += (ld.energy_power(ar, self.v) * act).sum(axis=1) * dt * al
        self.dist += (self.v * act).sum(axis=1) * dt * al
        self.acc2 += (ar * ar * mask_av).sum(axis=1) * al
        self.acc_n += mask_av.sum(axis=1) * al
        self.interv += interv * al
        gav = np.where(self.av & act, g1, 1e9)
        self.min_gap_av = np.where(al, np.minimum(self.min_gap_av, gav.min(axis=1)), self.min_gap_av)
        self.live += al
        self.t += 1


def rollout(theta, c, h, seed, shield=False, obsmode="v2x", kind="policy"):
    R = theta.shape[0] if theta is not None else 32
    env = Merge(R, c, h, seed, shield=shield, obsmode=obsmode, kind=kind)
    net = ld.Net(theta) if theta is not None else None
    for _ in range(int(c.warm / c.dt)):
        env.step(None)
    env.reset_acc()
    for _ in range(int(c.horizon / c.dt)):
        env.step(net)
    return env


def stats(env):
    c = env.c
    T = max(env.t, 1) * c.dt
    demand_veh = (c.qm + c.qr) / 3600.0 * T
    return dict(
        outflow=env.out / T * 3600.0,
        delay_per_veh=env.delay / np.maximum(demand_veh, 1.0),
        netspeed=env.net_v / np.maximum(env.net_n, 1.0),
        wh_km=env.energy / 3600.0 / np.maximum(env.dist / 1000.0, 1e-3),
        queue=env.qm + env.qr,
        merges=env.merges / T * 3600.0,
        acc_rms=np.sqrt(env.acc2 / np.maximum(env.acc_n, 1.0)),
        shield=env.interv / max(env.t, 1),
        coll=(~env.alive).astype(float),
        coll_av=env.coll_av.astype(float),
        min_gap_av=env.min_gap_av,
        courtesy=env.courtesy / T * 3600.0,
        overflow=env.overflow.astype(float),
        survived=env.live / max(env.t, 1),
    )


def fitness(env, reward):
    s = stats(env)
    # Dying early must score worse than dying late, or a dead replica has no gradient.
    coll = s["coll"] * (2.0 - s["survived"])
    if reward == "delay":
        return -s["delay_per_veh"] / 60.0 - 0.1 * s["wh_km"] / 100.0 - 0.02 * s["acc_rms"] ** 2 / 9.0 - 0.5 * s["shield"] - 5.0 * coll
    if reward == "outflow":
        return s["outflow"] / 2000.0 - 5.0 * coll
    if reward == "netspeed":
        return s["netspeed"] / 25.0 - 5.0 * coll
    raise ValueError(reward)


def cmd_grid(a):
    rows = []
    for qm in (1400.0, 1600.0, 1800.0, 2000.0, 2200.0, 2400.0):
        for qr in (200.0, 400.0, 600.0):
            c = C.with_(qm=qm, qr=qr, pav=0.0)
            env = rollout(None, c, HUMAN, 7, kind="idm")
            s = {k: float(np.mean(v)) for k, v in stats(env).items()}
            row = dict(qm=qm, qr=qr, **{k: round(s[k], 3) for k in ("outflow", "delay_per_veh", "netspeed", "wh_km", "queue", "merges", "coll", "courtesy", "overflow")})
            rows.append(row)
            print(row, flush=True)
    OUT.mkdir(exist_ok=True)
    (OUT / "merge-grid.json").write_text(json.dumps(rows, indent=1))


def _val(c, h, a):
    def val(theta):
        env = rollout(np.tile(theta, (12, 1)), c, h, 900001, shield=a.shield, obsmode=a.obs)
        s = {k: float(np.mean(v)) for k, v in stats(env).items()}
        return dict(score=float(fitness(env, a.reward).mean()), outflow=s["outflow"], delay=s["delay_per_veh"], netspeed=s["netspeed"], wh_km=s["wh_km"], queue=s["queue"], coll=s["coll"], shield=s["shield"], minav=s["min_gap_av"])
    return val


def cmd_es(a):
    c = C.with_(qm=a.qm, qr=a.qr, pav=a.pav, horizon=a.horizon)
    h = HUMAN

    def ro(th, seed):
        env = rollout(th, c, h, seed, shield=a.shield, obsmode=a.obs)
        updates = int(env.net_n.sum() + 0)
        return fitness(env, a.reward), int((c.warm + c.horizon) / c.dt * th.shape[0] * 90)

    OUT.mkdir(exist_ok=True)

    def log(curve, best):
        np.savez(OUT / f"{a.tag}.npz", theta=best, curve=json.dumps(curve), args=json.dumps(ld.argd(a)))

    theta0 = np.load(a.init)["theta"] if a.init else None
    best, curve = ld.es_train(ro, a.seed, a.gens, a.pairs, a.sigma, a.lr, a.eval_every, _val(c, h, a), theta0=theta0, log=log)
    log(curve, best)


def ctrl_idm_t(T):
    def f(env, a, gap, vl, mask):
        h = env.h
        v0 = np.where(env.ramp, env.c.ramp_v0, h.v0)
        ai = ld.idm(env.v, vl, gap, h.with_(T=T, v0=v0))
        return np.where(mask, ai, a)
    return f


def ctrl_noiseless(env, a, gap, vl, mask):
    return ctrl_idm_t(env.h.T)(env, a, gap, vl, mask)


def cmd_eval(a):
    out = {}
    base = C.with_(qm=a.qm, qr=a.qr, pav=a.pav)
    conds = {
        "test": (base, HUMAN, {}),
        "test, shield": (base, HUMAN, dict(shield=True)),
        "dt=0.1": (base.with_(dt=0.1), HUMAN, {}),
        "demand -20%": (base.with_(qm=a.qm * 0.8, qr=a.qr * 0.8), HUMAN, {}),
        "demand +10%": (base.with_(qm=a.qm * 1.1, qr=a.qr * 1.1), HUMAN, {}),
        "ramp x2": (base.with_(qr=a.qr * 2), HUMAN, {}),
        "AV 5%": (base.with_(pav=0.05), HUMAN, {}),
        "AV 30%": (base.with_(pav=0.3), HUMAN, {}),
        "AV 100%": (base.with_(pav=1.0), HUMAN, {}),
        "humans T=1.3": (base, HUMAN.with_(T=1.3), {}),
        "humans a=1.5": (base, HUMAN.with_(a=1.5), {}),
    }
    runners = {}
    for path in a.policies:
        z = np.load(path)
        ar = json.loads(str(z["args"]))
        runners[Path(path).stem] = (np.tile(z["theta"], (32, 1)), ar.get("obs", "v2x"))
    res = {}
    for tag, (th, om) in runners.items():
        res[tag] = {}
        for name, (c, h, kw) in conds.items():
            s = stats(rollout(th, c.with_(horizon=a.horizon), h, 777001, obsmode=om, **kw))
            res[tag][name] = {k: float(np.mean(v)) for k, v in s.items()}
        print(tag, json.dumps(res[tag]["test"]), flush=True)
    for tag, kd in (("IDM humans only", None), ("IDM T=1.0 AV", ctrl_noiseless), ("IDM T=1.5 AV", ctrl_idm_t(1.5))):
        res[tag] = {}
        for name, (c, h, kw) in conds.items():
            cc = c.with_(horizon=a.horizon)
            if kd is None:
                cc = cc.with_(pav=0.0)
            s = stats(rollout(None, cc, h, 777001, kind=kd or "idm"))
            res[tag][name] = {k: float(np.mean(v)) for k, v in s.items()}
        print(tag, json.dumps(res[tag]["test"]), flush=True)
    (OUT / f"{a.out}.json").write_text(json.dumps(res, indent=1))


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    g = sp.add_parser("grid"); g.set_defaults(fn=cmd_grid)
    e = sp.add_parser("es"); e.set_defaults(fn=cmd_es)
    e.add_argument("--tag", required=True); e.add_argument("--seed", type=int, default=0)
    e.add_argument("--gens", type=int, default=100); e.add_argument("--pairs", type=int, default=16)
    e.add_argument("--sigma", type=float, default=0.1); e.add_argument("--lr", type=float, default=0.03)
    e.add_argument("--reward", default="delay"); e.add_argument("--obs", default="v2x")
    e.add_argument("--shield", action="store_true"); e.add_argument("--qm", type=float, default=2000.0)
    e.add_argument("--qr", type=float, default=400.0); e.add_argument("--pav", type=float, default=0.1)
    e.add_argument("--horizon", type=float, default=400.0)
    e.add_argument("--eval-every", type=int, default=10); e.add_argument("--init", default=None)
    v = sp.add_parser("eval"); v.set_defaults(fn=cmd_eval)
    v.add_argument("policies", nargs="*"); v.add_argument("--out", required=True)
    v.add_argument("--qm", type=float, default=2000.0); v.add_argument("--qr", type=float, default=400.0)
    v.add_argument("--pav", type=float, default=0.1)
    v.add_argument("--horizon", type=float, default=800.0)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
