"""Wiedemann 99 and Gipps on report 05's frozen replay windows. Same split and scoring. Writes human-build/replay_w99.json.
W99 follows the published form of the model with Vissim's parameter names CC0-CC9. Deterministic: the published
random terms are left out, as noise in replay only adds error. Fit on 1,200 training windows with a smaller search than
report 05's (population 40 in all, 25 generations), which favours the incumbent if anything.
Usage: python3 -I research/truth/scripts/human_w99.py"""
import json, os, sys, time, pathlib
os.chdir(pathlib.Path(__file__).resolve().parents[3])
sys.path.insert(0, 'research/truth/scripts')
import numpy as np
from opus_common import *
from opus_models import score, objective, Batch
from opus_fit import split
from scipy.optimize import differential_evolution

L = 5.0
DEF = dict(cc0=1.5, cc1=0.9, cc2=4.0, cc3=-8.0, cc4=-0.35, cc5=0.35, cc6=11.44, cc7=0.25, cc8=3.5, cc9=1.5, gamma=1.0)


def w99_acc(v, vl, al, s, vdes, p, last):
    dv = vl - v
    dx = np.maximum(s - L, 0.01)
    v_slow = np.where((dv >= 0) | (al < -1), v, vl)
    sdxc = p['cc0'] + p['cc1'] * v_slow
    sdxo = sdxc + p['cc2']
    sdxv = sdxo + p['cc3'] * (dv - p['cc4'])
    sdv = p['cc6'] * 1e-4 * dx * dx
    sdvc = np.where(vl > 0, p['cc4'] - sdv, 0.0)
    sdvo = np.where(v > p['cc5'], p['cc5'] + sdv, sdv)
    # Decelerate, increase distance.
    c1 = (dv < sdvo) & (dx <= sdxc)
    a1 = np.where(dx > p['cc0'], np.minimum(al + dv * dv / np.minimum(p['cc0'] - dx, -0.01), 0.0), np.minimum(al + 0.5 * (dv - sdvo), 0.0))
    a1 = np.where((v > 0) & (dv < 0), a1, 0.0)
    a1 = np.where(a1 > -p['cc7'], -p['cc7'], np.maximum(a1, -10 + 0.5 * np.sqrt(v)))
    # Decelerate, decrease distance.
    c2 = ~c1 & (dv < sdvc) & (dx < sdxv)
    a2 = np.maximum(0.5 * dv * dv / np.minimum(-dx + sdxc - 0.1, -0.01), -10.0)
    # Keep distance: hold the last rate, at least CC7 either way.
    c3 = ~c1 & ~c2 & (dv < sdvo) & (dx < sdxo)
    a3 = np.where(last <= 0, np.minimum(last, -p['cc7']), np.minimum(np.maximum(last, p['cc7']), vdes - v))
    # Accelerate: CC8 at a standstill falling to CC9 at 80 km/h.
    amax = p['cc8'] + (p['cc9'] - p['cc8']) * np.minimum(v, 22.2) / 22.2
    a4 = np.where(dx < sdxo, np.minimum(dv * dv / np.maximum(sdxo - dx, 0.01), amax), amax)
    a4 = np.where(dx > sdxc, np.minimum(a4, vdes - v), np.minimum(last, vdes - v))
    return np.select([c1, c2, c3], [a1, a2, a3], a4)


def w99(b, p, vref):
    x = np.zeros(b.N)
    v = b.v[0].copy()
    S = np.empty((b.T, 1, b.N))
    V = np.empty((b.T, 1, b.N))
    S[0, 0] = b.xl[0] - x
    V[0, 0] = v
    vdes = p['gamma'] * vref
    alead = np.gradient(b.vl, 0.1, axis=0)
    last = b.a0.copy()
    for i in range(b.T - 1):
        a = w99_acc(v, b.vl[i], alead[i], b.xl[i] - x, vdes, p, last)
        last = a
        vn = np.maximum(v + a * 0.1, 0.0)
        step = (v + vn) * 0.05
        room = np.maximum(b.xl[i + 1] - x - 3.0, 0.0)
        step = np.minimum(step, room)
        vn = np.minimum(vn, np.maximum(step / 0.1, 0.0))
        x = x + step
        v = vn
        S[i + 1, 0] = b.xl[i + 1] - x
        V[i + 1, 0] = v
    return S, V


KEYS = ['cc0', 'cc1', 'cc2', 'cc3', 'cc4', 'cc5', 'cc6', 'cc7', 'gamma']
BOUNDS = [(0.5, 5), (0.3, 3), (0, 15), (-20, -1), (-3, -0.05), (0.05, 3), (1, 40), (0.05, 1.5), (0.8, 1.6)]


def gipps(b, p, vref):
    # MITSIM and Aimsun's family, as report 05's Driver: a, b, T, s0, gamma.
    a_, d, tau, s0 = p['a'], p['b'], p['T'], p['s0']
    v0 = p['gamma'] * vref
    x = np.zeros(b.N)
    v = b.v[0].copy()
    k = 5  # Gipps steps at 0.5 s, as the report
    S = np.empty((b.T, 1, b.N))
    V = np.empty((b.T, 1, b.N))
    S[0, 0] = b.xl[0] - x
    V[0, 0] = v
    dt = 0.1 * k
    idx = np.arange(0, b.T, k)
    Sc, Vc = [S[0, 0].copy()], [v.copy()]
    for j in idx[:-1]:
        gap = b.xl[j] - x - 5.0 - s0
        rad = (d * tau) ** 2 + d * (2 * gap - v * tau + b.vl[j] ** 2 / d)
        vs = -d * tau + np.sqrt(np.maximum(rad, 0))
        vf = v + 2.5 * a_ * tau * (1 - v / v0) * np.sqrt(np.maximum(.025 + v / v0, 0))
        vn = np.maximum(np.minimum(np.minimum(vf, vs), v + a_ * dt), np.maximum(v - 9 * dt, 0))
        step = np.minimum((v + vn) * .5 * dt, np.maximum(b.xl[j + k] - x - 3.0, 0))
        x = x + step
        v = np.minimum(vn, step / dt)
        Sc.append(b.xl[j + k] - x)
        Vc.append(v.copy())
    Sc, Vc = np.array(Sc), np.array(Vc)
    for i in range(b.N):
        S[:, 0, i] = np.interp(np.arange(b.T), idx, Sc[:, i])
        V[:, 0, i] = np.interp(np.arange(b.T), idx, Vc[:, i])
    return S, V


GK = ['a', 'b', 'T', 's0', 'gamma']
GB = [(0.3, 4), (0.5, 6), (0.3, 3), (0.2, 6), (0.8, 1.6)]


def fit(model, keys, bounds, b, seed=1):
    vref = b.meta['vref']
    def f(x):
        return float(objective(b, *model(b, dict(zip(keys, x)), vref))[0])
    r = differential_evolution(f, bounds, popsize=max(1, 40 // len(keys)), maxiter=25, seed=seed, tol=1e-3, polish=False, workers=1, updating='immediate')
    return dict(zip(keys, map(float, r.x))), float(r.fun)


def main():
    tr, va, te = split(False)
    rng = np.random.default_rng(1)
    pick = rng.choice(tr.N, 1200, replace=False)
    small = tr.subset(pick)
    t0 = time.time()
    p_w, o_w = fit(lambda b, p, vref: w99(b, {**DEF, **p}, vref), KEYS, BOUNDS, small)
    print('w99 fit', p_w, o_w, time.time() - t0, flush=True)
    t0 = time.time()
    p_g, o_g = fit(gipps, GK, GB, small)
    print('gipps fit', p_g, o_g, time.time() - t0, flush=True)
    out = dict(params=dict(w99=p_w, gipps=p_g), objective=dict(w99=o_w, gipps=o_g))
    for name, b in te.items():
        vref = b.meta['vref']
        rows = {}
        S, V = w99(b, {**DEF, 'gamma': 1.0}, vref)
        rows['w99_vissim_defaults'] = score(b, S, V)
        S, V = w99(b, {**DEF, **p_w}, vref)
        rows['w99_calibrated'] = score(b, S, V)
        S, V = gipps(b, p_g, vref)
        rows['gipps_calibrated'] = score(b, S, V)
        out[name] = rows
        print(name, {k: (round(v['spacing_rmse_30s'], 2), round(v['speed_rmse_30s'], 2)) for k, v in rows.items()}, flush=True)
    (pathlib.Path('research/truth/human-build') / 'replay_w99.json').write_text(json.dumps(out, indent=1))


main()
