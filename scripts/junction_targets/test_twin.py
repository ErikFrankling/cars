"""Twin test: synthetic ring traffic with known critical gap and follow-up goes through the same track code as real data.
The instrument reads above the input, by 0.4 to 0.8 s: that offset is a property of the instrument, so compare sim with real through this same code and never copy the number into a driver."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
from common import gap_mle
import rb

R, RY, V = 15., 18., 7.


def ring_track(i, t0, rng):
    """Comes in at an upstream arm, drives round, leaves past the entry at angle 0."""
    a0, a1 = -2.2, 2.2
    w = V / R
    T = (a1 - a0) / w
    t = np.arange(t0 - 6, t0 + T + 6, .2)
    a = np.clip(a0 + (t - t0) * w, a0, a1)
    rr = R + np.where(t < t0, (t0 - t) * V, 0) + np.where(t > t0 + T, (t - t0 - T) * V, 0)
    return (i, 'Car', t, rr * np.cos(a), rr * np.sin(a), np.full(len(t), V))


def run(tc_med, sd, tf, flow, hours=6., seed=1, rate=360.):
    rng = np.random.default_rng(seed)
    t = 0.
    tr, starts = [], []
    while t < hours * 3600:
        t += max(rng.exponential(3600 / flow), 1.2)
        starts.append(t)
        tr.append(ring_track(len(tr) + 1, t, rng))
    w = V / R
    passes = np.array(starts) + 2.2 / w    # time at angle 0
    # entrants arrive at random, queue, and take the first lag or gap at least their own critical gap
    n = int(hours * rate)
    arr = np.sort(rng.uniform(0, hours * 3600, n))
    last = -1e9
    true = []
    for a_t in arr:
        c = float(np.exp(np.log(tc_med) + sd * rng.standard_normal()))
        ready = max(a_t + 2.5, last + tf)
        k = np.searchsorted(passes, ready)
        go = ready
        while k < len(passes) and passes[k] - go < c:
            go = passes[k] + .3
            k += 1
        last = go
        true.append(go)
        # radial approach to 1 m outside the line, wait, then enter at the line at time go, then round and off
        i = len(tr) + 1
        tt = np.arange(a_t - 3, go + 1.5 + 2.2 / w + 6, .2)
        before = np.maximum(RY + 1 + (a_t + 2.5 - tt) * V, RY + 1 + (go - .5 - tt) * 2)
        before = np.where(tt < go - .5, np.maximum(RY + 1, RY + 1 + (a_t + 2.5 - tt) * V), RY + 1 - (tt - go + .5) * 2)
        rr = np.where(tt < go + .5, np.maximum(before, R), R)
        ang = np.where(tt < go + .5, 0., (tt - go - .5) * w)
        out = ang > 2.2
        rr = np.where(out, R + (ang - 2.2) / w * V, rr)
        ang = np.minimum(ang, 2.2)
        x, y = rr * np.cos(ang), rr * np.sin(ang)
        v = np.hypot(np.gradient(x, tt), np.gradient(y, tt))
        tr.append((i, 'Car', tt, x, y, v))
    return tr


def main():
    bad = 0
    for tc, tf, flow in ((3.5, 2.6, 400), (4.5, 2.8, 500), (3.0, 2.4, 700)):
        tr = run(tc, .25, tf, flow)
        arms = [0.]
        rec, fu, _, _ = rb.analyse(tr, 0., 0., RY, arms, 1, None, 'twin')
        d = [(x['acc'], x['rmax']) for x in rec if x['first'] and x['acc'] is not None and (x['nrej'] > 0 or x['acc'] < 25)]
        a = np.array(d)
        est = gap_mle(a[:, 0], a[:, 1])[0]
        fh = np.median([f['h'] for f in fu if f['h'] > .5]) if fu else float('nan')
        ok = 0 < est - tc < 1.
        bad += not ok
        print(f'true critical gap {tc}: recovered {est:.2f}, n {len(a)}; true follow-up {tf}: recovered {fh:.2f}, n {len(fu)} {"ok" if ok else "OFF"}', flush=True)
    return bad


if __name__ == '__main__':
    sys.exit(main())
