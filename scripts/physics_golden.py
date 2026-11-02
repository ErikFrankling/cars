#!/usr/bin/env python3
"""Q12 of research/truth/11-vehicle-physics.md: the kernel's formulas, in Python, against the report's
golden values. Needs no GPU, and must pass before anything else is worth looking at.

    python3 scripts/physics_golden.py [--wltc FILE]

FILE holds one km/h value per second of WLTC class 3b; without it the WLTC rows are skipped, not passed.
"""
import argparse
import json
import math
import sys

import numpy as np

G = 9.81
RHO = 1.225
KAPPA_ICE, KAPPA_EV = 0.775, 0.83
# name, kerb kg, kW, declared 0-100, declared top km/h, kind, driven axle share, CdA
CARS = [
    ('Dacia Sandero SCe 65', 1089, 49, 16.7, 158, 'ice', 0.55, 0.72),
    ('VW Golf 1.5 TSI 85 kW', 1307, 85, 9.9, 203, 'ice', 0.55, 0.63),
    ('Volvo XC90 3.2 AWD', 2202, 179, 9.5, 210, 'ice', 1.0, 0.95),
    ('Volvo XC90 T6 AWD', 2060, 228, 6.5, 230, 'ice', 1.0, 0.95),
    ('Tesla Model 3 RWD', 1836, 208, 6.1, 201, 'ev', 0.6, 0.50),
]
TYPES = {
    'car': dict(m=1650, kw=90, kappa=0.775, cda=0.68, crr=0.0105, vc=10, fd=0.55, eps=0.05, b_lo=7.0, b_hi=11.3, tr=0.30, L=5.0),
    'van': dict(m=2800, kw=95, kappa=0.775, cda=1.6, crr=0.012, vc=10, fd=0.55, eps=0.05, b_lo=6.0, b_hi=8.5, tr=0.47, L=6.5),
    'bus': dict(m=16000, kw=170, kappa=0.85, cda=5.0, crr=0.007, vc=3, fd=0.30, eps=0.08, b_lo=4.5, b_hi=7.5, tr=0.45, L=12.0),
    'rigid': dict(m=18000, kw=220, kappa=0.85, cda=5.0, crr=0.006, vc=3, fd=0.40, eps=0.08, b_lo=4.4, b_hi=7.7, tr=0.45, L=10.0),
    'artic': dict(m=40000, kw=300, kappa=0.85, cda=6.0, crr=0.006, vc=3, fd=0.275, eps=0.08, b_lo=4.4, b_hi=7.7, tr=0.45, L=16.5),
}
results = []


def check(name, ok, detail):
    results.append(dict(name=name, ok=bool(ok), detail=detail))
    print(('ok   ' if ok else 'FAIL ') + name + ': ' + detail)


class Veh:
    """cap() of the update equations in the spec, ph_force and ph_a_cap in common.wgsl."""

    def __init__(s, m, kw, kappa, cda, crr, vc, fd, eps, mu=1.0, L=1.0, W=1.0):
        s.pw, s.road_a, s.road_c, s.iinv, s.trac, s.vc, s.mu, s.L, s.W = kappa * kw * 1e3 / m, crr * G, 0.5 * RHO * cda / m, 1 / (1 + eps), fd * G, vc, mu, L, W

    def force(s, u, gz=0.0):
        return s.iinv * (min(s.pw * s.W / (s.L * max(u, s.vc)), s.mu * s.trac) - s.road_a - s.road_c * u * u / s.L) - gz

    def cap(s, v, dt, gz=0.0):
        return s.force(v + 0.5 * max(s.force(v, gz), 0.0) * dt, gz)


def from_type(t, **kw):
    return Veh(t['m'], t['kw'], t['kappa'], t['cda'], t['crr'], t['vc'], t['fd'], t['eps'], **kw)


def to_speed(v, target, dt=0.01):
    t, u = 0.0, 0.0
    while u < target and t < 400:
        a = v.cap(u, dt)
        if a <= 1e-5:
            return math.inf
        if u + a * dt >= target:
            return t + (target - u) / a
        u += a * dt
        t += dt
    return t


def top_speed(v):
    u = 20.0
    while u < 95 and v.force(u) > 0:
        u += 0.01
    return u


def b_rate(b, tr, dt):
    return b / tr if dt >= tr else b / (tr + dt)


def v_cert(gap, v, vl, bf, bl, tr, a_prev, dt):
    b = min(bf, bl)
    d_lo = max(0.0, -a_prev - b_rate(b, tr, dt) * dt)
    lam = max(0.0, 1.0 - d_lo / b)
    h = (tr * lam * lam + dt) * 0.5
    q = gap - 0.5 + vl * vl / (2 * bl) - v * dt * 0.5
    return b * (-h + math.sqrt(h * h + 2 * max(q, 0.0) / b))


def v_floor(v, a_prev, b, tr, dt):
    d = max(0.0, -a_prev)
    if dt >= tr:
        t1 = max(b - d, 0.0) * tr / b
        return v - (d * t1 + 0.5 * (b / tr) * t1 * t1 + b * (dt - t1))
    return v - min(b, d + b * dt / (tr + dt)) * dt


def stop_driver(gt, v, b, tau, dt):
    if gt <= 0:
        return 0.0
    if gt <= v * tau * 0.5:
        return max(0.0, v - v * v / (2 * gt) * dt)
    bt = b * tau * 0.5
    v1 = -bt + math.sqrt(bt * bt + b * (2 * gt - tau * v))
    return max(0.0, v + (v1 - v) / tau * dt)


def adversary(dt, n, seed=7):
    # The same pairs, in the same draw order, as the report's own test in physics_check.py.
    rng = np.random.default_rng(seed)
    pool = {'car': (7.0, 11.3, 0.30), 'van': (6.0, 8.5, 0.47), 'bus': (4.5, 7.5, 0.45), 'truck_full': (4.4, 7.7, 0.45), 'truck_empty': (5.0, 7.7, 0.45)}
    names = list(pool)
    collisions, worst, trials = 0, 1e9, 0
    for _ in range(n):
        f, l = rng.choice(names), rng.choice(names)
        b_lo, _, tr = pool[f]
        _, b_hi, _ = pool[l]
        grade = rng.uniform(-0.08, 0.08)
        mu = rng.choice([0.85, 0.54, 0.32, 0.073], p=[0.7, 0.2, 0.08, 0.02])
        gz = G * math.sin(math.atan(grade))
        bf = min(b_lo, mu * G) + gz
        bl = min(b_hi, 1.35 * mu * G) + gz
        if bf <= 0.05 or bl <= 0.05:
            continue
        trials += 1
        vl = rng.uniform(0, 36)
        v = rng.uniform(0, 36)
        a = rng.uniform(-bf, 2.0)
        b = min(bf, bl)
        lam = tr * max(0.0, 1.0 - max(0.0, -a - b / tr * dt) / b) ** 2
        g = max(v * v / (2 * b) + 0.5 * (lam + dt) * v + 0.5 * v * dt - vl * vl / (2 * bl) + 0.5 + rng.uniform(0, 8), 0.6)
        onset = rng.uniform(0, dt)
        xl, xf, ul, uf, t, least = g, 0.0, vl, v, 0.0, g
        sub = 40 if dt == 1.0 else 4
        h = dt / sub
        for _ in range(int(600 / dt)):
            vc = v_cert(xl - xf, uf, ul, bf, bl, tr, a, dt)
            up = a + b_rate(b, tr, dt) * dt if a < 0 else 2.0
            want = min(v, uf + min(up, 2.0) * dt, vc)
            raw = v_floor(uf, a, bf, tr, dt)
            nv = raw if want <= 0.0 else max(want, raw)
            a = (nv - uf) / dt
            for i in range(sub):
                ab = -bl if t + i * h >= onset else 0.0
                n1 = max(0.0, ul + ab * h)
                xl += 0.5 * (ul + n1) * h
                ul = n1
                n2 = max(0.0, uf + a * h)
                xf += 0.5 * (uf + n2) * h
                uf = n2
                least = min(least, xl - xf)
            t += dt
            if uf <= 0.0:
                a = 0.0
            if uf <= 0.0 and ul <= 0.0:
                break
        worst = min(worst, least)
        collisions += least < 0
    return trials, collisions, worst


def queue(dt, n=30, L=5.0, g0=2.5, tau=1.35, b_plan=4.5, vmax=13.89):
    car = TYPES['car']
    v_model = from_type(car, mu=0.85)
    x = [-1.0 - i * (L + g0) for i in range(n)]
    v, a, cross = [0.0] * n, [0.0] * n, [None] * n
    t = 0.0
    for _ in range(int(240 / dt)):
        nv = [0.0] * n
        for i in range(n):
            amax = min(max(2.02 - 0.125 * v[i], 0.7), v_model.cap(v[i], dt))
            vs = 1e9
            if i:
                g = x[i - 1] - L - x[i] - g0
                vs = stop_driver(max(g, 0.0) + v[i - 1] ** 2 / (2 * b_plan), v[i], b_plan, tau, dt)
                vs = min(vs, v_cert(g + g0, v[i], v[i - 1], min(car['b_lo'], .85 * G), min(car['b_hi'], 1.35 * .85 * G), car['tr'], a[i], dt))
            nv[i] = max(0.0, min(v[i] + amax * dt, vs, vmax))
        for i in range(n):
            nx = x[i] + 0.5 * (v[i] + nv[i]) * dt
            if cross[i] is None and x[i] < 0 <= nx:
                cross[i] = t + dt * (0 - x[i]) / max(nx - x[i], 1e-6)
            a[i] = (nv[i] - v[i]) / dt
            x[i], v[i] = nx, nv[i]
        t += dt
        if all(c is not None for c in cross):
            break
    hw = [b - a for a, b in zip(cross, cross[1:])]
    return 3600 / (sum(hw[8:]) / len(hw[8:]))


def wltc(trace, veh, dt):
    n = int(round((len(trace) - 1) / dt))
    u = trace[0]
    worst = 0.0
    for i in range(n):
        target = trace[min(int((i + 1) * dt), len(trace) - 1)]
        frac = (i + 1) * dt - int((i + 1) * dt)
        if frac and int((i + 1) * dt) + 1 < len(trace):
            target += frac * (trace[int((i + 1) * dt) + 1] - target)
        want = (target - u) / dt
        a = min(want, veh.cap(u, dt))
        a = max(a, -11.0)
        u = max(0.0, u + a * dt)
        worst = max(worst, abs(u - target))
    return worst * 3.6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wltc')
    ap.add_argument('--trials', type=int, default=12000)
    ap.add_argument('--json')
    a = ap.parse_args()
    for name, kg, kw, t100, top, kind, fd, cda in CARS:
        k = KAPPA_ICE if kind == 'ice' else KAPPA_EV
        v = Veh(kg + 100, kw, k, cda, 0.011, 10, fd, 0.05)
        fine = to_speed(v, 100 / 3.6, 0.01)
        coarse = to_speed(v, 100 / 3.6, 1.0)
        check(f'0-100 {name}', abs(fine / t100 - 1) <= 0.15, f'{fine:.2f} s against declared {t100}')
        check(f'midpoint at dt 1, {name}', abs(coarse / fine - 1) <= 0.015, f'{coarse:.2f} s against {fine:.2f} s')
        if kind == 'ice':
            check(f'top speed {name}', abs(top_speed(v) * 3.6 / top - 1) <= 0.08, f'{top_speed(v) * 3.6:.0f} against {top} km/h')
    for mph, ft in ((45, 144), (50, 176), (55, 212), (60, 250)):
        vv, b, tr = mph * 88 / 60, 16.8, 0.45
        d = vv * tr / 2 + vv * vv / (2 * b) - b * tr * tr / 24
        check(f'NHTSA {mph} mph', abs(d - ft) <= 1, f'{d:.1f} ft against {ft}')
    car = TYPES['car']
    u = 100 / 3.6
    lo, hi = u * u / (2 * 11.3) + u * car['tr'] / 2, u * u / (2 * 7.0) + u * car['tr'] / 2
    check('ADAC dry inside car band', lo <= 43.3 and 46.5 <= hi, f'43.3 to 46.5 m inside {lo:.1f} to {hi:.1f} m')
    # The report's regression figure uses 5% rotating inertia; the build table has 8% and gives 1 km/h less.
    truck = Veh(40000, 300, 0.85, 6.0, 0.006, 3, 0.275, 0.05)
    for grade, want in ((0.03, 58.5), (0.05, 39.3)):
        gz = G * grade * (1 - grade * grade / 2)
        speed = next((s / 100 for s in range(3000, 100, -1) if truck.force(s / 100, gz) >= 0), 0)
        check(f'crawl 40 t at {grade:.0%}', abs(speed * 3.6 - want) <= 1, f'{speed * 3.6:.1f} km/h against {want}')
    for dt in (1.0, 0.1):
        tr, col, worst = adversary(dt, a.trials)
        check(f'certificate adversary dt {dt}', col == 0 and worst > 0.25 and tr >= 10000, f'{tr} trials, {col} collisions, least gap {worst:.3f} m')
    q1, q2 = queue(1.0), queue(0.1)
    check('queue saturation flow', abs(q1 / q2 - 1) <= 0.01 and 1800 <= q1 <= 2000 and 1800 <= q2 <= 2000, f'{q1:.0f} at dt 1, {q2:.0f} at dt 0.1, spec 1861 and 1855')
    if a.wltc:
        trace = [float(x) / 3.6 for x in open(a.wltc).read().split()]
        for name, kg, kw, _, _, kind, fd, cda in CARS:
            k = KAPPA_ICE if kind == 'ice' else KAPPA_EV
            v = Veh(kg + 100, kw, k, cda, 0.011, 10, fd, 0.05)
            for dt in (0.1, 1.0):
                e = wltc(trace, v, dt)
                check(f'WLTC {name} dt {dt}', e <= 0.1, f'max error {e:.2f} km/h')
        van = from_type(TYPES['van'])
        for dt in (0.1, 1.0):
            e = wltc(trace, van, dt)
            check(f'WLTC van dt {dt}', e <= 3, f'max error {e:.2f} km/h')
    else:
        print('skipped: WLTC, no --wltc file')
    bad = [r for r in results if not r['ok']]
    print(f'{len(results) - len(bad)} of {len(results)} passed')
    if a.json:
        json.dump(results, open(a.json, 'w'), indent=1)
    sys.exit(bool(bad))


if __name__ == '__main__':
    main()
