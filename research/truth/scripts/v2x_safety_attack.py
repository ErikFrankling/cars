#!/usr/bin/env python3
"""Adversarial test of the stop-line rule in research/truth/08-v2x-and-safety-first-principles.md.

Truth (x, v, a, dead time, jerk limit, friction) is separate from what the rule sees.
Every suite is a Monte Carlo over vehicle parameters, tick phase, sensor error, leader
manoeuvre and channel. A contact is true bumper gap < 0.

    python3 -I v2x_safety_attack.py analytic|baseline|attacks|cross|tier0big [--n N] [--seeds S] [--part a/b]
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

G = 9.81
DT = 0.01
BMAX = 12.0
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "v2x-safety-attack-results.json"


def s_plus(v, td, A, J, b):
    """Closed-form upper bound on stopping distance: accelerate A for td, ramp to -b at J."""
    v1 = v + A * td
    vp = v1 + A * A / (2 * J)
    return v * td + 0.5 * A * td * td + v1 * A / J + A**3 / (3 * J * J) + vp * b / (2 * J) + vp * vp / (2 * b)


def s_exact(v, td, A, J, b, dt=2e-4):
    """Numerical stopping distance for scalar parameters, exact for a linear ramp."""
    x = v * td + 0.5 * A * td * td
    u = v + A * td
    a = A
    while u > 0:
        an = max(a - J * dt, -b)
        du = 0.5 * (a + an) * dt
        if u + du <= 0:
            x += u * u / (2 * max(-0.5 * (a + an), 1e-9))
            break
        x += u * dt + (2 * a + an) / 6 * dt * dt
        u += du
        a = an
    return x


def uni(rng, lo, hi, shape):
    return rng.uniform(lo, hi, shape)


def run_long(name, N=4000, C=2, T=30.0, seed=0, **cfg):
    """Chain of C cars per case. Car 0 is the adversary, the rest follow the rule."""
    t0 = time.time()
    rng = np.random.default_rng(seed)
    steps = int(T / DT)
    Ks, Kd = 64, 64
    rows = np.arange(N)[:, None]
    F = C - 1

    A_t = uni(rng, 0.5, 4.0, (N, C))
    J_t = uni(rng, 10.0, 80.0, (N, C))
    J_r = J_t * np.where(rng.random((N, C)) < 0.5, 1.0, uni(rng, 0.7, 1.0, (N, C)))
    kd = rng.integers(0, 31, (N, C))
    tick = rng.choice([2, 5, 10], (N, C))
    phase = (rng.random((N, C)) * tick).astype(int)
    ks = rng.integers(0, 31, (N, C))
    b_c = uni(rng, 2.0, 9.0, (N, C))
    cap = np.minimum(b_c * np.where(rng.random((N, C)) < 0.5, 1.0, uni(rng, 1.0, 1.3, (N, C))), BMAX)
    L = uni(rng, 3.5, 18.0, (N, C))
    ex = uni(rng, 0.0, 0.5, (N, C))
    ev = uni(rng, 0.0, 0.5, (N, C))
    exo = uni(rng, 0.0, 0.2, (N, C))
    evo = uni(rng, 0.0, 0.1, (N, C))
    m = uni(rng, 0.05, 1.0, (N, C))
    worst = rng.random(N) < 0.5
    B_l = BMAX * np.where(rng.random(N) < 0.5, 1.0, uni(rng, 0.5, 1.0, N))
    Br = np.full((N, C), BMAX)
    br = b_c.copy()
    Ar = A_t.copy()
    Jr = J_r.copy()
    tdr = (tick + kd) * DT

    if cfg.get("rule_no_tick"):
        tdr = kd * DT
    if cfg.get("rule_no_dead"):
        tdr = tick * DT
    if cfg.get("rule_no_react"):
        tdr = np.zeros_like(tdr)
    if cfg.get("rule_no_ramp"):
        Jr = np.full_like(Jr, 1e6)
    if cfg.get("rule_no_A"):
        Ar = np.zeros_like(Ar)
    if "rule_b_factor" in cfg:
        br = b_c * cfg["rule_b_factor"]
    if "advertised_B" in cfg:
        Br = np.full((N, C), float(cfg["advertised_B"]))
    if "B_l" in cfg:
        B_l = np.full(N, float(cfg["B_l"]))
    if cfg.get("equal_brakes"):
        b_c = np.repeat(b_c[:, :1], C, axis=1)
        cap = b_c.copy()
        B_l = b_c[:, 0].copy()
    if cfg.get("weak_leader"):
        B_l = uni(rng, 1.0, 3.0, N)
        Br = np.repeat(B_l[:, None], C, axis=1)
        b_c = uni(rng, 6.0, 9.0, (N, C))
        cap = b_c.copy()
        br = np.minimum(b_c, Br) if cfg.get("use_b_star") else b_c.copy()
    if cfg.get("brickwall_rule"):
        Br = np.full((N, C), 1e9)
    if cfg.get("cert"):
        B_c = uni(rng, 3.0, 8.0, N)
        b_c = np.maximum(b_c, 3.0)
        cap = np.maximum(cap, b_c)
        br = np.minimum(b_c, B_c[:, None])
    exr = np.zeros_like(ex) if cfg.get("rule_no_ex") else ex
    evr = np.zeros_like(ev) if cfg.get("rule_no_ev") else ev

    mu_road = np.maximum(b_c / G, uni(rng, 0.2, 1.25, (N, C)))
    v = uni(rng, 0.0, 40.0, (N, C))
    if cfg.get("weak_leader"):
        v[:, 0] = uni(rng, 5.0, 20.0, N)
        v[:, 1:] = v[:, 0:1] + uni(rng, 2.0, 15.0, (N, F))
    if cfg.get("cruise"):
        v[:] = cfg["cruise"]
    a = uni(rng, -1.0, 1.0, (N, C)) * np.where(rng.random((N, C)) < 0.5, 0.0, 1.0)
    a = np.clip(a, -b_c, A_t)
    x = np.zeros((N, C))
    y = np.full((N, C), -np.inf)

    y_iss = np.full((N, C), np.inf)
    if cfg.get("cert"):
        y_iss[:, 0] = x[:, 0] - L[:, 0] + v[:, 0] ** 2 / (2 * B_c)

    def rear_age(i):
        return x[:, i] - L[:, i] - v[:, i] * ks[:, i + 1] * DT

    for i in range(1, C):
        if cfg.get("cert"):
            y0 = y_iss[:, i - 1]
        elif cfg.get("msg_only"):
            y0 = x[:, i - 1] - L[:, i - 1] + np.maximum(v[:, i - 1], 0) ** 2 / (2 * Br[:, i])
        else:
            y0 = rear_age(i - 1) + np.maximum(v[:, i - 1], 0) ** 2 / (2 * Br[:, i])
        u = np.where(rng.random(N) < 0.7, 0.0, uni(rng, 0.0, 5.0, N))
        if "cutin" in cfg:
            u = uni(rng, 5.0, 150.0, N)
        xf = y0 - s_plus(v[:, i], tdr[:, i], Ar[:, i], Jr[:, i], br[:, i]) - m[:, i] - u + cfg.get("s_short", 0.0)
        if "fixed_gap" in cfg:
            xf = x[:, i - 1] - L[:, i - 1] - cfg["fixed_gap"](v[:, i])
        x[:, i] = np.minimum(xf, x[:, i - 1] - L[:, i - 1] - 0.1)
        y[:, i] = y0
        if cfg.get("cert"):
            y_iss[:, i] = np.minimum(x[:, i] - L[:, i] + v[:, i] ** 2 / (2 * B_c), y0 - m[:, i] - L[:, i])

    hx = np.repeat(x[:, :, None], Ks, axis=2) - v[:, :, None] * (DT * ((-np.arange(Ks)) % Ks))
    hv = np.repeat(v[:, :, None], Ks, axis=2)
    cmd = np.zeros_like(A_t) if "fixed_gap" in cfg else A_t.copy()
    if "fixed_gap" in cfg:
        a[:] = 0.0
    fifo = np.repeat(cmd[:, :, None], Kd, axis=2)

    # friction patch on the follower braking region
    xp = np.min(x, axis=1) + uni(rng, 0.0, 120.0, N)
    Lp = uni(rng, 20.0, 400.0, N)
    mu_p = np.maximum(b_c.max(axis=1) / G, uni(rng, 0.2, 1.2, N))
    if "mu_patch" in cfg:
        mu_p = np.full(N, float(cfg["mu_patch"]))
    brake_loss = cfg.get("brake_loss", 0.0)

    # leader schedule
    mode = rng.integers(0, 5, N) if "mode" not in cfg else np.full(N, cfg["mode"])
    t_b = uni(rng, 0.0, 15.0, N)
    t_b = np.where(mode == 3, np.floor(t_b / (tick[:, 1] * DT)) * tick[:, 1] * DT + (phase[:, 1] + 1) * DT, t_b)
    t_b = np.where(mode == 4, 0.0, t_b)
    tgt = np.zeros(N)
    nxt = np.where((mode == 1) | (mode == 2), uni(rng, 0.0, 3.0, N), np.inf)
    braking_flag = np.zeros(N, bool)
    first_brake = np.full(N, np.inf)
    vmax = 45.0

    # channel
    ch = cfg.get("channel", "none")
    Tm = 10
    Kr = 512
    msg_phase = rng.integers(0, Tm, (N, C))
    if cfg.get("msg_only") or cfg.get("cert"):
        inbox = np.full((N, C, Kr), -np.inf)
    t_black = uni(rng, 0.0, 15.0, N)
    ge_bad = rng.random((N, C)) < 0.2
    ge_in, ge_out = cfg.get("ge", (1 / 5.2, 1 / 1.42))
    p_good = cfg.get("p_good", 0.05)
    p_iid = cfg.get("p", 0.0)
    last_x = x.copy()
    last_v = v.copy()
    last_age = np.zeros((N, C))
    forge_t = uni(rng, 0.0, 10.0, N)

    # events
    drop_a = uni(rng, 0.0, 15.0, N)
    drop_b = drop_a + uni(rng, 0.5, 15.0, N)
    t_cut = uni(rng, 0.2, 2.0, N)
    cut_done = np.zeros(N, bool)
    reset_at = np.full(N, -1)
    cut_events = 0
    if "cutin" in cfg:
        mode[:] = 0
        t_b[:] = 1e9
    ph_car = rng.integers(1, C, N) if C > 1 else np.zeros(N, int)
    ph_a = uni(rng, 2.0, 15.0, N)
    ph_b = ph_a + uni(rng, 0.5, 5.0, N)

    dead = np.zeros((N, F), bool)
    impact = np.zeros((N, F))
    min_gap = np.full((N, F), np.inf)
    cruise_gap = []
    ridx = np.arange(N)

    for k in range(steps):
        t = k * DT
        idx = k % Ks
        hx[:, :, idx] = x
        hv[:, :, idx] = v

        # controller
        due = ((k - phase) % tick) == 0
        due[:, 0] = False
        if "cutin" in cfg and not cfg["cutin"].endswith("noreset"):
            y[:, 1] = np.where(k == reset_at, -np.inf, y[:, 1])
        i_prev = (k - ks[:, 1:]) % Ks
        c_prev = np.arange(F)[None, :]
        obs_x = hx[rows, c_prev, i_prev] - L[:, :-1]
        obs_v = hv[rows, c_prev, i_prev]
        sx = np.where(worst[:, None], 1.0, rng.uniform(-1, 1, (N, F)))
        sv = np.where(worst[:, None], 1.0, rng.uniform(-1, 1, (N, F)))
        obs_x = obs_x + sx * ex[:, 1:] + cfg.get("bias_x", 0.0)
        obs_v = obs_v + sv * ev[:, 1:] + cfg.get("bias_v", 0.0)
        y_new = obs_x - exr[:, 1:] + np.maximum(obs_v - evr[:, 1:], 0) ** 2 / (2 * Br[:, 1:])

        if cfg.get("msg_only") or cfg.get("cert"):
            # sender side: one message per Tm steps, a lower bound on final rear position
            gen = ((k - msg_phase) % Tm) == 0
            lost = np.zeros((N, F), bool)
            if ch == "iid":
                lost = rng.random((N, F)) < p_iid
            elif ch == "ge":
                flip = rng.random((N, C)) < np.where(ge_bad, 1 - np.exp(-ge_out * DT), 1 - np.exp(-ge_in * DT))
                ge_bad = ge_bad ^ flip
                lost = ge_bad[:, 1:] | (rng.random((N, F)) < p_good)
            elif ch == "blackout":
                lost = np.repeat((t >= t_black)[:, None], F, axis=1)
            elif ch == "brake_lost":
                lost = np.repeat((t >= first_brake)[:, None], F, axis=1)
            elif ch == "all_lost":
                lost = np.ones((N, F), bool)
            delay = np.clip((rng.lognormal(np.log(0.025), 0.4, (N, F)) / DT).astype(int) + 1, 1, Kr - 1)
            if ch == "replay":
                delay = np.where(rng.random((N, F)) < 0.5, rng.integers(1, Kr - 1, (N, F)), delay)
            if cfg.get("cert"):
                ylead = y_iss[:, :-1]
            else:
                ylead = x[:, :-1] - L[:, :-1] + np.maximum(v[:, :-1], 0) ** 2 / (2 * Br[:, 1:])
            if "forge" in cfg:
                ylead = ylead + np.where(t >= forge_t, cfg["forge"], 0.0)[:, None]
            send = gen[:, :-1] & ~lost
            r2, c2 = np.nonzero(send)
            if r2.size:
                j = (k + delay[r2, c2]) % Kr
                inbox[r2, c2 + 1, j] = np.maximum(inbox[r2, c2 + 1, j], ylead[r2, c2])
            rx = inbox[:, 1:, k % Kr].copy()
            inbox[:, 1:, k % Kr] = -np.inf

        if cfg.get("msg_only"):
            if cfg.get("dead_reckon"):
                got = send
                last_x[:, 1:] = np.where(got, x[:, :-1] - L[:, :-1], last_x[:, 1:])
                last_v[:, 1:] = np.where(got, v[:, :-1], last_v[:, 1:])
                last_age[:, 1:] = np.where(got, 0.0, last_age[:, 1:] + DT)
                y_est = (
                    last_x[:, 1:]
                    + last_v[:, 1:] * last_age[:, 1:]
                    - exr[:, 1:]
                    + np.maximum(last_v[:, 1:] - evr[:, 1:], 0) ** 2 / (2 * Br[:, 1:])
                )
                y[:, 1:] = np.where(due[:, 1:], y_est, y[:, 1:])
            else:
                y[:, 1:] = np.maximum(y[:, 1:], rx)
        else:
            ok = due[:, 1:]
            if cfg.get("sensor_dropout"):
                ok = ok & ~((t >= drop_a) & (t < drop_b))[:, None]
            if cfg.get("no_monotone"):
                y[:, 1:] = np.where(ok, y_new, y[:, 1:])
            else:
                y[:, 1:] = np.where(ok, np.maximum(y[:, 1:], y_new), y[:, 1:])
            if cfg.get("cert"):
                y[:, 1:] = np.maximum(y[:, 1:], rx)

        y_use = y.copy()
        if cfg.get("phantom"):
            act = (t >= ph_a) & (t < ph_b)
            yh = x[ridx, ph_car] + 0.5 * s_plus(v[ridx, ph_car], tdr[ridx, ph_car], Ar[ridx, ph_car], Jr[ridx, ph_car], br[ridx, ph_car])
            y_use[ridx, ph_car] = np.where(act, np.minimum(y_use[ridx, ph_car], yh), y_use[ridx, ph_car])

        so = np.where(worst[:, None], -1.0, rng.uniform(-1, 1, (N, F)))
        x_up = x[:, 1:] + so * exo[:, 1:] + exo[:, 1:]
        v_up = np.maximum(v[:, 1:] + so * evo[:, 1:] + evo[:, 1:], 0)
        M = y_use[:, 1:] - x_up - s_plus(v_up, tdr[:, 1:], Ar[:, 1:], Jr[:, 1:], br[:, 1:]) - m[:, 1:] + cfg.get("s_short", 0.0)
        brake_cmd = -br[:, 1:] if cfg.get("cert") else -np.minimum(cap[:, 1:], BMAX)
        if "fixed_gap" in cfg:
            # fixed-gap platoon: cruise, then brake on the first sensed or received deceleration
            if cfg.get("radio"):
                lead_seen = hv[:, :-1, (k - 3) % Ks] < v[:, 1:] - 0.3
            else:
                lead_seen = hv[rows, c_prev, i_prev] < v[:, 1:] - 0.3
            want = np.where(lead_seen, brake_cmd, 0.0)
        else:
            want = np.where(M < 0, brake_cmd, A_t[:, 1:])
        new_cmd = np.where(due[:, 1:], want, cmd[:, 1:])
        if cfg.get("restart_deadtime"):
            # implementation bug: every tick's fresh brake request restarts the actuator timer
            pend = due[:, 1:] & (new_cmd < 0) & (a[:, 1:] > -0.5)
            r3, c3 = np.nonzero(pend)
            if r3.size:
                fifo[r3, c3 + 1, :] = a[r3, c3 + 1][:, None]
        cmd[:, 1:] = new_cmd

        fifo[:, :, k % Kd] = cmd
        eff = fifo[rows, np.arange(C)[None, :], (k - kd) % Kd]

        # adversary
        sw = t >= nxt
        if sw.any():
            r = rng.random(N)
            m1 = sw & (mode == 1)
            tgt = np.where(m1 & (tgt < 0), A_t[:, 0], np.where(m1, -B_l, tgt))
            nxt = np.where(m1, t + np.where(tgt < 0, uni(rng, 0.2, 3.0, N), uni(rng, 1.0, 8.0, N)), nxt)
            m2 = sw & (mode == 2)
            tgt = np.where(m2, np.where(r < 0.5, -B_l, np.where(r < 0.75, 0.0, A_t[:, 0])), tgt)
            nxt = np.where(m2, t + rng.exponential(0.5, N) + 0.05, nxt)
        go = ((mode == 0) | (mode == 3) | (mode == 4)) & (t >= t_b)
        tgt = np.where(go, -B_l, tgt)
        first_brake = np.where((tgt < 0) & np.isinf(first_brake), t, first_brake)

        # dynamics
        mu = np.where((x >= xp[:, None]) & (x < (xp + Lp)[:, None]), np.minimum(mu_road, mu_p[:, None]), mu_road)
        blim = np.maximum(np.minimum(cap, mu * G) - brake_loss, 0.05)
        ad = np.maximum(eff, -blim)
        ad = np.minimum(ad, A_t)
        an = np.clip(ad, a - J_t * DT, a + 40.0 * DT)
        if cfg.get("cert"):
            room = np.maximum(y_iss - (x - L), 1e-3)
            capd = v * v / (2 * room)
            an = np.maximum(an, -capd)
        # head
        h_tgt = tgt.copy()
        if cfg.get("cert") and not cfg.get("cert_break"):
            h_tgt = np.maximum(h_tgt, -capd[:, 0])
        h_tgt = np.where((v[:, 0] >= vmax) & (h_tgt > 0), 0.0, h_tgt)
        an[:, 0] = h_tgt
        a_head_prev = h_tgt
        a[:, 0] = a_head_prev
        dv = 0.5 * (a + an) * DT
        vn = v + dv
        dx = v * DT + (2 * a + an) / 6 * DT * DT
        stop = vn < 0
        if cfg.get("reverse"):
            stop[:, 0] = False
        if stop.any():
            dx = np.where(stop, v * v / (2 * np.maximum(-0.5 * (a + an), 1e-6)), dx)
            vn = np.where(stop, 0.0, vn)
            an = np.where(stop, 0.0, an)
        if cfg.get("reverse"):
            vn[:, 0] = np.maximum(vn[:, 0], -2.0)
            an[:, 0] = np.where((vn[:, 0] <= 0) & (t >= first_brake), -1.0, an[:, 0])
        x = x + dx
        v = vn
        a = an

        if cfg.get("brickwall_event"):
            hit = t >= t_b
            v[:, 0] = np.where(hit, 0.0, v[:, 0])
            a[:, 0] = np.where(hit, 0.0, a[:, 0])

        if cfg.get("cert"):
            gen_i = ((k - msg_phase) % Tm) == 0
            cand = x - L + v * v / (2 * B_c[:, None])
            cand[:, 1:] = np.minimum(cand[:, 1:], y[:, 1:] - m[:, 1:] - L[:, 1:])
            y_iss = np.where(gen_i, np.maximum(y_iss, cand), y_iss)
            if cfg.get("cert_inflate"):
                y_iss[:, 0] = np.maximum(y_iss[:, 0], x[:, 0] - L[:, 0] + v[:, 0] ** 2 / (2 * 2.0))

        if "cutin" in cfg and (not cut_done.all()):
            c_ev = (t >= t_cut) & ~cut_done
            if c_ev.any():
                vc = v[:, 1] * uni(rng, 0.7, 1.0, N)
                extra = {"coop": ks[:, 1] * DT + tick[:, 1] * DT, "coop_naive": 0.0, "rude": 0.0, "rude_noreset": 0.0, "coop_noreset": ks[:, 1] * DT + tick[:, 1] * DT}[cfg["cutin"]]
                need = x[:, 1] + exo[:, 1] * 2 + s_plus(v[:, 1] + evo[:, 1] * 2, tdr[:, 1] + extra, Ar[:, 1], Jr[:, 1], br[:, 1]) + m[:, 1] + ex[:, 1] * 2 - (np.maximum(vc - 2 * ev[:, 1], 0)) ** 2 / (2 * BMAX)
                if cfg["cutin"].startswith("rude"):
                    rear_new = x[:, 1] + uni(rng, 0.1, 1.0, N) * np.maximum(need - x[:, 1], 0.2)
                else:
                    rear_new = need + 0.01
                old_rear = x[:, 0] - L[:, 0]
                apply = c_ev & (rear_new > x[:, 1] + 0.05) & (rear_new <= old_rear)
                x[:, 0] = np.where(apply, rear_new + L[:, 0], x[:, 0])
                v[:, 0] = np.where(apply, vc, v[:, 0])
                a[:, 0] = np.where(apply, 0.0, a[:, 0])
                r4 = np.nonzero(apply)[0]
                if r4.size:
                    # the sensor shows the cutter only after its own age has passed
                    reset_at[r4] = k + 1 + ks[r4, 1]
                    cut_events += r4.size
                    cut_done[r4] = True
                    # the cutter is now the adversary and may brake hard right away
                    mode[r4] = 4
                    t_b[r4] = t
                cut_done = cut_done | c_ev

        gap = x[:, :-1] - L[:, :-1] - x[:, 1:]
        min_gap = np.where(dead, min_gap, np.minimum(min_gap, gap))
        hit = (gap < 0) & ~dead
        if hit.any():
            impact = np.where(hit, np.maximum(v[:, 1:] - v[:, :-1], 0), impact)
            dead = dead | hit
        if cfg.get("log_cruise") and k == steps - 2:
            cruise_gap = gap.copy()

    case_hit = dead.any(axis=1)
    res = {
        "name": name,
        "cases": int(N),
        "cars": int(C),
        "contacts": int(case_hit.sum()),
        "contact_pct": round(100.0 * float(case_hit.mean()), 3),
        "min_true_gap_m": round(float(min_gap[~dead].min()), 4) if (~dead).any() else None,
        "mean_impact_ms": round(float(impact[dead].mean()), 2) if dead.any() else 0.0,
        "max_impact_ms": round(float(impact[dead].max()), 2) if dead.any() else 0.0,
        "seconds": round(time.time() - t0, 1),
    }
    if "cutin" in cfg:
        res["cut_in_events"] = int(cut_events)
    if cfg.get("log_cruise"):
        res["cruise_gap_mean_m"] = round(float(np.mean(cruise_gap)), 2)
    return res


def t_reach(d, v, A, vmax):
    """Earliest time to cover d >= 0 from speed v under acceleration A capped at vmax."""
    d = np.maximum(d, 0.0)
    v = np.minimum(v, vmax)
    t_acc = (vmax - v) / np.maximum(A, 1e-6)
    d_acc = v * t_acc + 0.5 * A * t_acc * t_acc
    t1 = (-v + np.sqrt(v * v + 2 * A * d)) / np.maximum(A, 1e-6)
    t2 = t_acc + (d - d_acc) / vmax
    return np.where(d <= d_acc, t1, t2)


def run_cross(name, N=4000, T=60.0, seed=0, proto="mutex", **cfg):
    """Two cars on crossing paths. The zone is s in [0, Z]; a car occupies it while s > 0 and s - L < Z."""
    t0 = time.time()
    rng = np.random.default_rng(seed)
    steps = int(T / DT)
    Kd, Ks = 64, 64
    rows = np.arange(N)[:, None]

    Z = uni(rng, 4.0, 12.0, (N, 2))
    L = uni(rng, 3.5, 12.0, (N, 2))
    vd = uni(rng, 6.0, 20.0, (N, 2))
    A = uni(rng, 0.5, 3.0, (N, 2))
    b_c = uni(rng, 2.5, 8.0, (N, 2))
    J_t = uni(rng, 10.0, 80.0, (N, 2))
    kd = rng.integers(0, 31, (N, 2))
    tick = rng.choice([2, 5, 10], (N, 2))
    phase = (rng.random((N, 2)) * tick).astype(int)
    ks = rng.integers(0, 31, (N, 2))
    ex = uni(rng, 0.0, 0.5, (N, 2))
    ev = uni(rng, 0.0, 0.5, (N, 2))
    m = uni(rng, 0.2, 1.5, (N, 2))
    tdr = (tick + kd) * DT
    Jr = J_t.copy()
    br = b_c.copy()
    if cfg.get("rule_no_react"):
        tdr = np.zeros_like(tdr)
        Jr = np.full_like(Jr, 1e6)
    if "brake_factor" in cfg:
        cap = b_c * cfg["brake_factor"]
    else:
        cap = b_c.copy()
    if proto.startswith("certified"):
        cap[:, 0] = BMAX
        J_t[:, 0] = 1000.0
        kd[:, 0] = 0
    v = uni(rng, 0.0, 1.0, (N, 2)) * vd
    if cfg.get("runner"):
        v[:, 1] = vd[:, 1]
    s = -s_plus(v, tdr, A, Jr, br) - m - uni(rng, 0.0, 80.0, (N, 2))
    a = np.zeros((N, 2))
    cmd = A.copy()
    fifo = np.repeat(cmd[:, :, None], Kd, axis=2)
    hs = np.repeat(s[:, :, None], Ks, axis=2)
    hv = np.repeat(v[:, :, None], Ks, axis=2)

    claim = np.zeros((N, 2), bool)
    committed = np.zeros((N, 2), bool)
    cleared = np.zeros((N, 2), bool)
    owner = np.full(N, -1)
    slot_next = np.zeros(N)
    t_grant = np.zeros(N)
    p = cfg.get("p", 0.0)
    ge_bad = np.zeros((N, 2), bool)
    forge_t = uni(rng, 0.0, 20.0, N)
    forged = np.zeros(N, bool)
    restart_t = uni(rng, 0.0, 20.0, N)
    restarted = np.zeros(N, bool)
    last_deny = np.zeros((N, 2))

    # stall: one car brakes hard somewhere in or near the zone and stays there
    stall_car = rng.integers(0, 2, N)
    stall_on = rng.random(N) < cfg.get("stall", 0.5)
    stall_s = uni(rng, -5.0, 1.0, N) * Z[np.arange(N), stall_car] / 2 + Z[np.arange(N), stall_car] * uni(rng, 0.0, 1.0, N)
    stall_T = np.where(rng.random(N) < 0.5, 1e9, uni(rng, 1.0, 20.0, N))
    stall_t0 = np.full(N, np.inf)
    runner = cfg.get("runner", False)
    if runner:
        stall_on[:] = False
    cross = np.zeros(N, bool)
    both_in_first = np.full(N, np.inf)
    clear_t = np.full((N, 2), np.inf)
    enter_t = np.full((N, 2), np.inf)
    vmax = 25.0
    sight = cfg.get("sight", np.inf)
    idx = np.arange(N)
    stopped_on_line = np.zeros((N, 2), bool)
    promise_rx = np.zeros(N, bool)
    margin = 0.05

    for k in range(steps):
        t = k * DT
        hs[:, :, k % Ks] = s
        hv[:, :, k % Ks] = v
        due = ((k - phase) % tick) == 0
        rear = s - L
        cleared = cleared | (rear >= Z)
        clear_t = np.where(cleared & np.isinf(clear_t), t, clear_t)
        enter_t = np.where((s > 0) & np.isinf(enter_t), t, enter_t)

        if p > 0 or cfg.get("ge"):
            if cfg.get("ge"):
                flip = rng.random((N, 2)) < np.where(ge_bad, 1 - np.exp(-DT / 1.42), 1 - np.exp(-DT / 5.2))
                ge_bad = ge_bad ^ flip
                lost_u = ge_bad | (rng.random((N, 2)) < 0.05)
                lost_d = ge_bad | (rng.random((N, 2)) < 0.05)
            else:
                lost_u = rng.random((N, 2)) < p
                lost_d = rng.random((N, 2)) < p
        else:
            lost_u = lost_d = np.zeros((N, 2), bool)

        arb_tick = k % 5 == 0
        if proto in ("mutex", "timeout", "optimistic", "slot", "forge", "restart") and arb_tick:
            req = ~cleared & ~lost_u
            free = owner < 0
            pick = np.where(req[:, 0] & (req[:, 1] & (rng.random(N) < 0.5) ^ True), 0, np.where(req[:, 1], 1, -1))
            pick = np.where(req[:, 0] & ~req[:, 1], 0, pick)
            if proto == "slot":
                new = free & (pick >= 0) & (t >= slot_next)
                # the slot ends at the nominal exit, whatever actually happens
                pc = np.maximum(pick, 0)
                dist = Z[idx, pc] + L[idx, pc] - s[idx, pc]
                slot_next = np.where(new, t + dist / vd[idx, pc] + 0.5, slot_next)
                owner = np.where(new, pick, owner)
                owner = np.where((owner >= 0) & (t >= slot_next), -1, owner)
            else:
                new = free & (pick >= 0)
                owner = np.where(new, pick, owner)
                t_grant = np.where(new, t, t_grant)
            for c in (0, 1):
                got = (owner == c) & ~lost_d[:, c]
                claim[:, c] = claim[:, c] | got
                denied = (owner >= 0) & (owner != c) & ~lost_d[:, c]
                last_deny[:, c] = np.where(denied, t, last_deny[:, c])
                rel = (owner == c) & cleared[:, c] & ~lost_u[:, c]
                owner = np.where(rel, -1, owner)
            if proto == "timeout":
                # silence is treated as release: the unsafe rule
                exp = (owner >= 0) & (t - t_grant > cfg.get("t_out", 3.0))
                owner = np.where(exp, -1, owner)
            if proto == "forge":
                f = (t >= forge_t) & ~forged & (owner >= 0)
                owner = np.where(f, -1, owner)
                forged = forged | f
            if proto == "restart":
                f = (t >= restart_t) & ~restarted
                owner = np.where(f, -1, owner)
                restarted = restarted | f

        M = -m - s - s_plus(v, tdr, A, Jr, br)
        nominal = np.where(v < vd, A, 0.0)
        want = np.where(M < 0, -cap, nominal)

        if proto in ("physics", "physics_occluded", "certified", "certified_const", "promise"):
            oth = 1 - np.arange(2)[None, :]
            i_o = (k - ks) % Ks
            s_o = hs[rows, oth, i_o]
            v_o = hv[rows, oth, i_o]
            age = ks * DT
            Lo = np.take_along_axis(L, np.repeat(oth, N, axis=0), axis=1)
            Zo = np.take_along_axis(Z, np.repeat(oth, N, axis=0), axis=1)
            Ao = np.take_along_axis(A, np.repeat(oth, N, axis=0), axis=1)
            s_lo = s_o - ex
            v_lo = np.maximum(v_o - ev, 0)
            o_clear = (s_lo - Lo) >= Zo
            if proto in ("physics", "physics_occluded", "promise"):
                s_up = s_o + ex
                v_up = v_o + ev
                d_arr = -s_up
                seen = -s_o <= sight
                if proto == "physics_occluded":
                    t_arr = np.where(seen, t_reach(d_arr, v_up, Ao, vmax) - age, np.inf)
                else:
                    t_arr = np.where(seen, t_reach(d_arr, v_up, Ao, vmax) - age, sight / vmax)
                inside = (s_up > 0) & ~o_clear
                t_arr = np.where(inside, -1.0, t_arr)
                # commands already in the actuator keep slowing the car after it commits
                v_low = v
                if not cfg.get("ignore_pipeline"):
                    pending = fifo.min(axis=2) < 0
                    v_low = np.where(pending | (a < -0.01), np.maximum(v - cap * ((kd + tick) * DT) - cap * cap / 80.0, 0.0), v)
                t_clear_me = (Z + L - s) / np.maximum(v_low, 0.5)
                ok = o_clear | (t_arr > t_clear_me + margin)
                if proto == "promise":
                    idle = (v < 0.05) & (s < 0)
                    send = idle[:, 1] & (~committed[:, 1] | bool(cfg.get("promise_any"))) & ~cleared[:, 0] & ~lost_u[:, 1]
                    promise_rx = promise_rx | send
                    ok[:, 0] = ok[:, 0] | (promise_rx & ~(inside[:, 0]))
                    # the promising car stays put until the other has cleared
                    ok[:, 1] = ok[:, 1] & (o_clear[:, 1] | ~promise_rx)
            else:
                # certified to clear: car 0 has priority, car 1 needs the other's rear stop line past the exit
                r = np.maximum(Zo + m - (s_lo - Lo), 0.0)
                cert = v_lo * v_lo >= 2 * BMAX * r
                if proto == "certified_const":
                    cert = np.ones_like(cert)
                    tc = r / np.maximum(v_lo, 0.1) - age
                else:
                    tc = (v_lo - np.sqrt(np.maximum(v_lo * v_lo - 2 * BMAX * r, 0))) / BMAX - age
                t_me = t_reach(-s - 0.0, v, A, vd)
                ok = o_clear | (cert & (t_me > tc + margin))
                ok[:, 0] = True
            start = (M < 0) & ok & ~committed
            committed = committed | start
            # a car that stopped short may go again from rest once the check holds
            want = np.where(committed | cleared, nominal, want)
            want = np.where((M >= 0) & ~committed, nominal, want)
        elif proto == "optimistic":
            silent = (t - last_deny) > 0.5
            go_claim = claim | ((M < 0) & silent & ~claim)
            claim = go_claim
            want = np.where(claim | cleared, nominal, want)
        else:
            want = np.where(claim | cleared, nominal, want)

        if runner:
            want[:, 1] = nominal[:, 1]
        # adversary: one car brakes hard and stays
        here = stall_on & (s[idx, stall_car] >= stall_s) & np.isinf(stall_t0)
        stall_t0 = np.where(here, t, stall_t0)
        active = stall_on & (t >= stall_t0) & (t < stall_t0 + stall_T)
        want[idx, stall_car] = np.where(active, -cap[idx, stall_car], want[idx, stall_car])

        cmd = np.where(due, want, cmd)
        fifo[:, :, k % Kd] = cmd
        eff = fifo[rows, np.arange(2)[None, :], (k - kd) % Kd]
        ad = np.minimum(np.maximum(eff, -cap), A)
        an = np.clip(ad, a - J_t * DT, a + 40.0 * DT)
        dv = 0.5 * (a + an) * DT
        vn = v + dv
        dx = v * DT + (2 * a + an) / 6 * DT * DT
        stop = vn < 0
        if stop.any():
            dx = np.where(stop, v * v / (2 * np.maximum(-0.5 * (a + an), 1e-6)), dx)
            vn = np.where(stop, 0.0, vn)
            an = np.where(stop, 0.0, an)
        s = s + dx
        v = vn
        a = an
        if cfg.get("crash_in_zone"):
            hit = (s[:, 0] > 0) & (s[:, 0] - L[:, 0] < Z[:, 0]) & (t >= uni(rng, 0.0, 60.0, N))
            v[:, 0] = np.where(hit, 0.0, v[:, 0])
            a[:, 0] = np.where(hit, 0.0, a[:, 0])

        occ = (s > 0) & (s - L < Z)
        both = occ[:, 0] & occ[:, 1]
        both_in_first = np.where(both & np.isinf(both_in_first), t, both_in_first)
        cross = cross | both

    done = cleared.all(axis=1)
    res = {
        "name": name,
        "proto": proto,
        "cases": int(N),
        "collisions": int(cross.sum()),
        "collision_pct": round(100.0 * float(cross.mean()), 3),
        "both_cleared_pct": round(100.0 * float(done.mean()), 1),
        "seconds": round(time.time() - t0, 1),
    }
    both_done = np.isfinite(clear_t[:, 0]) & np.isfinite(enter_t[:, 1]) & (enter_t[:, 1] > clear_t[:, 0]) & ~stall_on & ~cross
    if both_done.any():
        res["entry_after_clear_median_s"] = round(float(np.median((enter_t[:, 1] - clear_t[:, 0])[both_done])), 2)
    return res


def analytic():
    out = {}
    rng = np.random.default_rng(5)
    worst = np.inf
    ratio = []
    for _ in range(3000):
        v, td, A, J, b = rng.uniform(0, 40), rng.uniform(0, 0.6), rng.uniform(0, 4), rng.uniform(5, 100), rng.uniform(0.5, 12)
        e = s_exact(v, td, A, J, b)
        p = s_plus(v, td, A, J, b)
        worst = min(worst, p - e)
        if e > 1:
            ratio.append(p / e)
    out["s_plus_minus_exact_min_m"] = round(float(worst), 4)
    out["s_plus_over_exact_max"] = round(float(max(ratio)), 4)

    w0, B = rng.uniform(0, 40, 200000), rng.uniform(1, 14, 200000)
    age = rng.uniform(0, 30, 200000)
    q = np.where(age <= w0 / B, w0 * age - B * age * age / 2, w0 * w0 / (2 * B))
    W = np.maximum(w0 - B * age, 0)
    out["age_cancels_max_abs_error_m"] = float(np.abs(q + W * W / (2 * B) - w0 * w0 / (2 * B)).max())

    def rss(V, W, rho, bf, Bl, E=2.0, A=0.0):
        return E + max(0.0, V * rho + A * rho * rho / 2 + (V + A * rho) ** 2 / (2 * bf) - W * W / (2 * Bl))

    def sup_closure(V, W, bf, Bl):
        t = np.linspace(0, 40, 400001)
        sf = np.where(t < V / bf, V * t - bf * t * t / 2, V * V / (2 * bf))
        sl = np.where(t < W / Bl, W * t - Bl * t * t / 2, W * W / (2 * Bl))
        return float((sf - sl).max())

    out["report_examples"] = {
        "transient_6p25": round(sup_closure(20, 10, 10, 2), 3),
        "b_star_75": rss(20, 10, 0, 2, 2, E=0),
        "rho_0p2_equal_8": rss(30, 30, 0.2, 8, 8),
        "rho_0p02_equal_2p6": rss(30, 30, 0.02, 8, 8),
        "bf5_Bl9_48": rss(30, 30, 0.2, 5, 9),
        "bf2_Bl8_176p75": rss(30, 30, 0.2, 2, 8),
        "age_inflation_vs_cv": [round(rss(30, 30 - 8 * a, 0.2, 8, 8) + 8 * a * a / 2, 2) for a in (0.1, 0.5, 1.0)],
    }

    # terms of the invariant at 30 m/s
    V = 30.0
    out["sensitivity_at_30ms"] = {
        "per_100ms_reaction_m": round(V * 0.1, 2),
        "per_1ms2_uncertainty_at_8_m": round(V * V / (2 * 7.5) - V * V / (2 * 8.5), 2),
        "per_0p1_mu_at_mu0p8_m": round(V * V / (2 * 0.7 * G) - V * V / (2 * 0.8 * G), 2),
        "per_0p5ms_speed_error_at_b8_m": round((V + 0.5) ** 2 / 16 - V * V / 16, 2),
        "gnss_3m_vs_radar_0p5m_m": 2.5,
    }

    # required spacing and flow
    td, Ax, J, e = 0.25, 1.0, 12.7, 1.0
    age_s = 0.1

    def gap(V, b, B):
        return np.maximum(0.5, s_plus(V, td, Ax, J, b) - V * V / (2 * B) + V * age_s + e)

    speeds = np.array([5.0, 8.33, 13.89, 16.67, 22.22, 30.0, 36.11])
    sets = {
        "no_trust_b6_B12": (6.0, 12.0),
        "no_trust_b7p5_B10": (7.5, 10.0),
        "certificate_b6_Bc6": (6.0, 6.0),
        "certificate_b7p5_Bc7p5": (7.5, 7.5),
        "brick_wall_b6": (6.0, 1e9),
        "brick_wall_b7p5": (7.5, 1e9),
        "wet_no_trust_b4_B12": (4.0, 12.0),
        "ice_no_trust_b1p5_B12": (1.5, 12.0),
    }
    L = 4.5
    table = {}
    for name, (b, B) in sets.items():
        g = gap(speeds, b, B)
        table[name] = {
            "gap_m": [round(float(x), 1) for x in g],
            "time_gap_s": [round(float(x / v), 2) for x, v in zip(g, speeds)],
            "flow_veh_h": [int(3600 * v / (x + L)) for x, v in zip(g, speeds)],
        }
    out["speeds_ms"] = [float(s) for s in speeds]
    out["spacing"] = table
    out["spacing_assumptions"] = {"td_s": td, "A_ms2": Ax, "J_ms3": J, "E_m": e, "sensor_age_s": age_s, "vehicle_length_m": L}

    # how quickly a car stops: dead time, ramp at J, then constant braking
    def stop_time(v, b):
        v1 = v + Ax * td
        t0 = Ax / J
        vp = v1 + Ax * Ax / (2 * J)
        tr = b / J
        if vp <= J * tr * tr / 2:
            return td + t0 + np.sqrt(2 * vp / J)
        return td + t0 + tr + (vp - J * tr * tr / 2) / b

    out["stopping"] = {}
    for surf, b in [("dry_0p77g", 0.77 * G), ("wet_0p55g", 0.55 * G), ("snow_2p6", 2.6), ("ice_2p0", 2.0), ("truck_0p45g", 0.45 * G)]:
        out["stopping"][surf] = {
            f"{kmh}kmh": {
                "m": round(float(s_exact(kmh / 3.6, td, Ax, J, b)), 1),
                "s": round(float(stop_time(kmh / 3.6, b)), 2),
            }
            for kmh in (30, 50, 70, 110)
        }

    # leader stops dead (crash): impact speed from the spacing each policy keeps at 30 m/s
    out["brick_wall_impact_at_30ms"] = {}
    for name, (b, B) in sets.items():
        if name.startswith("brick"):
            continue
        g = float(gap(np.array([30.0]), b, B)[0])
        free = g - float(s_plus(30.0, td, Ax, J, b) - 30.0**2 / (2 * b))
        out["brick_wall_impact_at_30ms"][name] = {
            "gap_m": round(g, 1),
            "impact_ms": round(float(np.sqrt(max(30.0**2 - 2 * b * max(free, 0), 0))), 1),
        }

    # fixed gaps seen in demonstrations, leader brakes hardest, follower reacts by sensor only
    def impact(V, g, rho, bf, Bl, dt=1e-4):
        xl, vl, xf, vf, t = g, V, 0.0, V, 0.0
        while vf > 0:
            vl_n = max(vl - Bl * dt, 0)
            xl += 0.5 * (vl + vl_n) * dt
            vl = vl_n
            if t >= rho:
                vf_n = max(vf - bf * dt, 0)
                xf += 0.5 * (vf + vf_n) * dt
                vf = vf_n
            else:
                xf += vf * dt
            t += dt
            if xf >= xl:
                return round(vf - vl, 2)
        return 0.0

    demos = {
        "SARTRE_6m_25ms": (25.0, 6.0),
        "PATH97_6p5m_27ms": (26.8, 6.5),
        "Peloton_12p2m_24p6ms": (24.6, 12.19),
        "Ploeg_0p7s_gap_16ms": (16.0, 0.7 * 16.0),
        "RSS_like_8m_30ms": (30.0, 8.0),
    }
    out["demo_gap_impact_ms"] = {}
    for name, (V, g) in demos.items():
        row = {}
        for rho, bf, Bl in [(0.2, 8, 8), (0.5, 8, 8), (0.2, 6, 10), (0.5, 6, 10), (0.2, 6, 12)]:
            row[f"rho{rho}_b{bf}_B{Bl}"] = impact(V, g, rho, bf, Bl)
        row["required_gap_rho0p2_b6_B10"] = round(0.2 * V + V * V / 12 - V * V / 20, 1)
        out["demo_gap_impact_ms"][name] = row

    # crossing: headway between conflicting cars
    rows = {}
    for vkmh in (30, 50, 70):
        v = vkmh / 3.6
        for b, rho, B in [(6.0, 0.5, 12.0)]:
            occ = (7.0 + 4.5) / v
            commit_ahead = rho + v / (2 * b)
            cert_credit = v / (2 * B)
            rows[f"{vkmh}kmh"] = {
                "occupancy_s": round(occ, 2),
                "clear_before_commit_extra_s": round(commit_ahead, 2),
                "certified_credit_s": round(cert_credit, 2),
                "headway_nominal_slot_unsafe_s": round(occ, 2),
                "headway_mutex_clear_s": round(occ + commit_ahead, 2),
                "headway_certified_s": round(occ + commit_ahead - cert_credit, 2),
                "stop_distance_m": round(v * rho + v * v / (2 * b), 1),
                "sight_needed_at_50kmh_foe_m": round(13.89 * (float(s_plus(v, td, Ax, J, b)) + 0.5 + 11.5) / v, 1),
            }
    out["crossing_headway"] = rows
    return out


def save_row(key, row):
    res = json.loads(OUT.read_text()) if OUT.exists() else {}
    res.setdefault(key, {})[row["name"]] = row
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps(row), flush=True)


def pick(items, part):
    a, b = (int(x) for x in part.split("/"))
    return [kv for i, kv in enumerate(items) if i % b == a]


def baseline(n, seeds, part="0/1"):
    variants = {
        "tier0_sensor_2car": dict(),
        "tier0_sensor_chain6": dict(C=6, N=max(n // 3, 500)),
        "tier0_sensor_dropout": dict(sensor_dropout=True),
        "stop_line_msg_only_iid_p0.5": dict(msg_only=True, channel="iid", p=0.5),
        "stop_line_msg_only_iid_p0.95": dict(msg_only=True, channel="iid", p=0.95),
        "stop_line_msg_only_field_bursts_802.11p": dict(msg_only=True, channel="ge"),
        "stop_line_msg_only_long_bursts_10s": dict(msg_only=True, channel="ge", ge=(1 / 5.0, 1 / 10.0)),
        "stop_line_msg_only_random_blackout": dict(msg_only=True, channel="blackout"),
        "stop_line_msg_only_brake_msg_lost": dict(msg_only=True, channel="brake_lost"),
        "stop_line_msg_only_replay_reorder_5s": dict(msg_only=True, channel="replay"),
        "certificate_tier1_blackout": dict(cert=True, channel="blackout"),
        "certificate_tier1_brake_msg_lost": dict(cert=True, channel="brake_lost"),
        "certificate_tier1_field_bursts": dict(cert=True, channel="ge"),
        "certificate_tier1_chain4_blackout": dict(cert=True, channel="blackout", C=4, N=max(n // 2, 500)),
        "certificate_tier1_replay": dict(cert=True, channel="replay"),
        "phantom_brake_chain4": dict(C=4, phantom=True, N=max(n // 2, 500)),
        "cutin_cooperative_with_detection_allowance": dict(cutin="coop"),
    }
    for name, cfg in pick(list(variants.items()), part):
        cfg = dict(cfg)
        N = cfg.pop("N", n)
        agg = None
        for sd in range(seeds):
            r = run_long(name, N=N, seed=100 + sd, **cfg)
            if agg is None:
                agg = r
            else:
                agg["cases"] += r["cases"]
                agg["contacts"] += r["contacts"]
                agg["seconds"] += r["seconds"]
                if r["min_true_gap_m"] is not None:
                    agg["min_true_gap_m"] = min(agg["min_true_gap_m"], r["min_true_gap_m"])
                agg["max_impact_ms"] = max(agg["max_impact_ms"], r["max_impact_ms"])
        agg["contact_pct"] = round(100.0 * agg["contacts"] / agg["cases"], 3)
        save_row("baseline", agg)


def tier0big(n, seeds):
    """Accumulates across calls: each call continues with new seeds and saves."""
    full = json.loads(OUT.read_text()) if OUT.exists() else {}
    agg = full.get("tier0_big") or {"name": "tier0_sensor_2car_large", "cases": 0, "contacts": 0, "min_true_gap_m": 1e9, "seconds": 0.0, "runs": 0}
    agg.setdefault("runs", 5)
    for _ in range(seeds):
        r = run_long("t", N=n, seed=1000 + agg["runs"])
        agg["runs"] += 1
        agg["cases"] += r["cases"]
        agg["contacts"] += r["contacts"]
        agg["seconds"] = round(agg["seconds"] + r["seconds"], 1)
        agg["min_true_gap_m"] = min(agg["min_true_gap_m"], r["min_true_gap_m"])
        full = json.loads(OUT.read_text()) if OUT.exists() else {}
        full["tier0_big"] = agg
        OUT.write_text(json.dumps(full, indent=1))
        print(json.dumps(agg), flush=True)
    return agg


def attacks(n, part="0/1"):
    A = {
        "reaction_delay_ignored": dict(rule_no_react=True),
        "control_tick_ignored": dict(rule_no_tick=True),
        "actuator_dead_time_ignored": dict(rule_no_dead=True),
        "brake_ramp_jerk_ignored": dict(rule_no_ramp=True),
        "acceleration_during_response_ignored": dict(rule_no_A=True),
        "position_error_ignored": dict(rule_no_ex=True, rule_no_ev=False),
        "speed_error_ignored": dict(rule_no_ev=True),
        "sensor_bias_3m_outside_bound": dict(bias_x=3.0),
        "sensor_speed_bias_3ms_outside_bound": dict(bias_v=3.0),
        "unseen_low_friction_mu0.15": dict(mu_patch=0.15),
        "brake_fade_or_downhill_1ms2": dict(brake_loss=1.0),
        "follower_claims_120pct_brake": dict(rule_b_factor=1.2),
        "leader_advertises_B4_true_higher": dict(advertised_B=4.0),
        "leader_advertises_B8_true_higher": dict(advertised_B=8.0),
        "weak_leader_final_position_only": dict(weak_leader=True),
        "weak_leader_with_b_star": dict(weak_leader=True, use_b_star=True),
        "stale_msg_dead_reckoned_blackout": dict(msg_only=True, channel="blackout", dead_reckon=True),
        "stale_msg_dead_reckoned_brake_lost": dict(msg_only=True, channel="brake_lost", dead_reckon=True),
        "forged_msg_raises_stop_line_40m": dict(msg_only=True, channel="none", forge=40.0),
        "brick_wall_leader_rule_assumes_Bmax": dict(brickwall_event=True),
        "brick_wall_leader_rule_is_brick_wall": dict(brickwall_event=True, brickwall_rule=True),
        "leader_reverses": dict(reverse=True, mode=4),
        "cutin_rude": dict(cutin="rude"),
        "cutin_cooperative_no_detection_allowance": dict(cutin="coop_naive"),
        "cutin_cooperative_stale_y_not_reset": dict(cutin="coop_noreset"),
        "actuator_timer_restarted_by_each_brake_tick": dict(restart_deadtime=True),
        "rule_short_by_1p5m_margin_removed": dict(s_short=1.5),
        "leader_brakes_14_rule_bound_12": dict(B_l=14.0),
        "fixed_0p3s_gap_radio_lost_mixed_brakes": dict(fixed_gap=lambda v: 0.3 * v, cruise=25.0, mode=0),
        "fixed_0p6s_gap_radio_lost_mixed_brakes": dict(fixed_gap=lambda v: 0.6 * v, cruise=25.0, mode=0),
        "fixed_1p0s_gap_radio_lost_mixed_brakes": dict(fixed_gap=lambda v: 1.0 * v, cruise=25.0, mode=0),
        "fixed_0p3s_gap_radio_works_mixed_brakes": dict(fixed_gap=lambda v: 0.3 * v, cruise=25.0, mode=0, radio=True),
        "fixed_0p3s_gap_radio_works_equal_brakes": dict(fixed_gap=lambda v: 0.3 * v, cruise=25.0, mode=0, radio=True, equal_brakes=True),
        "certificate_broken_by_leader": dict(cert=True, channel="none", cert_break=True),
        "certificate_inflated_by_leader": dict(cert=True, channel="none", cert_inflate=True, cert_break=True),
    }
    for name, cfg in pick(list(A.items()), part):
        cfg = dict(cfg)
        save_row("attacks", run_long(name, N=n, seed=7, **cfg))


def cross(n, part="0/1"):
    C = {
        "mutex_no_loss": dict(proto="mutex"),
        "mutex_loss_50": dict(proto="mutex", p=0.5),
        "mutex_loss_95": dict(proto="mutex", p=0.95),
        "mutex_loss_100": dict(proto="mutex", p=1.0),
        "mutex_field_bursts": dict(proto="mutex", ge=True),
        "mutex_all_stall": dict(proto="mutex", stall=1.0),
        "physics_only_no_radio": dict(proto="physics"),
        "physics_only_all_stall": dict(proto="physics", stall=1.0),
        "physics_plus_promise_loss_50": dict(proto="promise", p=0.5),
        "physics_vs_red_light_runner": dict(proto="physics", runner=True),
        "physics_sight_40m_phantom_at_edge": dict(proto="physics", sight=40.0),
        "certified_to_clear": dict(proto="certified"),
        "mutex_no_stall_for_headway": dict(proto="mutex", stall=0.0),
        "certified_no_stall_for_headway": dict(proto="certified", stall=0.0),
        "ATTACK_commit_ignores_actuator_pipeline_vs_runner": dict(proto="physics", runner=True, ignore_pipeline=True),
        "ATTACK_committed_car_may_promise_yield": dict(proto="promise", p=0.5, promise_any=True),
        "ATTACK_grant_timeout_reissued": dict(proto="timeout"),
        "ATTACK_no_reply_means_go_loss_50": dict(proto="optimistic", p=0.5),
        "ATTACK_time_slot_no_clearance_check": dict(proto="slot"),
        "ATTACK_forged_release": dict(proto="forge"),
        "ATTACK_arbiter_restart_lost_state": dict(proto="restart"),
        "ATTACK_stop_rule_ignores_reaction_ramp": dict(proto="mutex", rule_no_react=True),
        "ATTACK_true_brake_60pct_of_certified": dict(proto="mutex", brake_factor=0.6),
        "ATTACK_mutex_vs_red_light_runner": dict(proto="mutex", runner=True),
        "ATTACK_occluded_foe_treated_as_absent": dict(proto="physics_occluded", sight=15.0),
        "ATTACK_certified_uses_constant_speed": dict(proto="certified_const"),
        "ATTACK_certified_foe_crashes_in_zone": dict(proto="certified", crash_in_zone=True, stall=0.0),
    }
    for name, cfg in pick(list(C.items()), part):
        cfg = dict(cfg)
        proto = cfg.pop("proto")
        save_row("crossing", run_cross(name, N=n, seed=11, proto=proto, **cfg))


def rerun_cross_rows(names, n):
    C = dict(
        physics_vs_red_light_runner=dict(proto="physics", runner=True),
        ATTACK_commit_ignores_actuator_pipeline_vs_runner=dict(proto="physics", runner=True, ignore_pipeline=True),
        ATTACK_mutex_vs_red_light_runner=dict(proto="mutex", runner=True),
        ATTACK_committed_car_may_promise_yield=dict(proto="promise", p=0.5, promise_any=True),
        physics_plus_promise_loss_50=dict(proto="promise", p=0.5),
    )
    for name in names:
        cfg = dict(C[name])
        proto = cfg.pop("proto")
        save_row("crossing", run_cross(name, N=n, seed=11, proto=proto, **cfg))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["analytic", "baseline", "attacks", "cross", "tier0big", "crossrows"])
    ap.add_argument("--rows", default="")
    ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--part", default="0/1")
    args = ap.parse_args()
    if args.what == "analytic":
        res = json.loads(OUT.read_text()) if OUT.exists() else {}
        res["analytic"] = analytic()
        OUT.write_text(json.dumps(res, indent=1))
        print("analytic saved")
    elif args.what == "crossrows":
        rerun_cross_rows(args.rows.split(","), args.n)
    elif args.what == "tier0big":
        tier0big(args.n, args.seeds)
    elif args.what == "baseline":
        baseline(args.n, args.seeds, args.part)
    elif args.what == "attacks":
        attacks(args.n, args.part)
    else:
        cross(args.n, args.part)


if __name__ == "__main__":
    main()
