"""F310, F311: the slow numbers of the measured driver, fitted on 30 s one-follower rollouts of sites that are not held out
(TGSIM I-294 L1, I-90/94 stationary, I-395; report 05's windows, cut by its own code). K, c_a and k_g stay as the
one-second fit froze them (model_fit.json). The rollout is the kernel's twin (scripts/replay/md_twin.py, F307), with
noise and the personal spreads off, so it scores the mean driver.

    python3 -I scripts/measure/fit_slow.py      # -> model_fit.json, key "slow"
"""
import os, sys, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(REPO, 'scripts', 'replay'))
import fit_driver as FD
import md_twin as MT

SITES = ('I294L1', 'I90stat', 'I395')
W, X0, DT = 300, 20.0, 0.1


def windows(site, maxn=1500):
    os.chdir(REPO)
    sys.path.insert(0, os.path.join(REPO, 'research/truth/scripts'))
    from opus_windows import windows as cut
    b = cut(site, maxn=maxn)
    return dict(xl=X0 + b.xl[:W], vl=b.vl[:W].astype(float), v0=b.v[0].astype(float), s=b.s[:W], vref=float(b.meta['vref'][0]))


def rollout(d, kp, tv):
    P = list(MT.P); P[3] = kp
    xl, vl = d['xl'], d['vl']
    N = xl.shape[1]
    beta = 1 - np.exp(-DT / FD.TAU_R)
    x = np.full(N, X0); v = d['v0'].copy(); a = np.zeros(N); steps = np.zeros(N, int)
    al = np.vstack([np.diff(vl, axis=0) / DT, np.zeros((1, N))])
    X = [x.copy()]
    vdes = d['vref']
    for k in range(W - 1):
        g = xl[k] - MT.L - x
        c = FD.command(v, g, vl[k], al[k], P, a_cap=np.full(N, 1e9))
        if tv > 0:
            # every window has its leader within 100 m: the launch law does not bind (F311)
            free = np.minimum((vdes - v) / tv, MT.a_cap(v))
        else:
            r = np.minimum(v, 1.5 * vdes) / vdes
            free = np.minimum(np.maximum(2.02 - 0.125 * v, 0.7) * np.maximum(1 - r ** 4, -1.0), MT.a_cap(v))
        c = np.minimum(c, free)
        an = a + beta * (c - a)
        vn = np.maximum(v + an * DT, 0.0)
        vn = np.where(vl[k] < 0.5 * v, np.minimum(vn, MT.stop_comfort(g - FD.S0 + vl[k] ** 2 / 2.6, v)), vn)
        ce = MT.cert(g, v, vl[k], a)
        vn = np.where(ce <= 0, -1.0, np.minimum(np.maximum(vn, 0.0), ce))
        jerk = 8.3 / (0.3 + DT)
        floor = v - np.minimum(8.3, np.maximum(0, -a) + 8.3 * DT / (0.3 + DT)) * DT
        release = np.where(a >= 0, 1e9, v + (a + jerk * DT) * DT)
        vn = np.where(vn < 0, floor, np.maximum(np.minimum(vn, release), floor))
        stand = v < 0.05; still = (vl[k] < 1e-3) & (g < 15.0)
        steps = np.where(stand & still, 0, np.where(stand & (vn > 0), steps + 1, steps))
        waited = steps * DT
        held = np.where(still | (steps == 0) | (waited + DT <= 1.0 + 1e-3), 0.0, np.where(waited < 1.0 - 1e-3, vn * (waited + DT - 1.0) / DT, vn))
        vn = np.where(stand, held, vn)
        acc = (vn - v) / DT; vn = np.maximum(vn, 0.0)
        ds = np.where(vn > 0, v * DT + 0.5 * acc * DT * DT, np.where(acc < 0, v * v / (2 * np.maximum(-acc, 1e-9)), 0.0))
        a = np.where(vn > 0, acc, 0.0); x = x + ds; v = vn
        X.append(x.copy())
    return xl - np.array(X)


def main():
    data = {s: windows(s) for s in SITES}
    def score(kp, tv):
        per = {}
        for s, d in data.items():
            e = rollout(d, kp, tv) - d['s']
            per[s] = float(np.sqrt(np.mean(e ** 2)))
        return float(np.mean(list(per.values()))), per
    kp = json.load(open(FD.OUTJ))['pooled']['k_p']
    grid = {}
    for tv in (0.5, 1.0, 2.0, 3.0, 4.0, 6.0):
        grid[(kp, tv)] = score(kp, tv)
        print(kp, tv, round(grid[(kp, tv)][0], 3), flush=True)
    best = min(grid, key=lambda k: grid[k][0])
    # For the record, not adopted: how far a stronger pull would still go (F310's question).
    info = {f'{k2},{best[1]}': round(score(k2, best[1])[0], 3) for k2 in (0.05, 0.1, 0.15)}
    out = json.load(open(FD.OUTJ))
    out['slow'] = dict(sites=list(SITES), windows_per_site={s: int(d['s'].shape[1]) for s, d in data.items()},
                       note='F311: launch law off within 100 m of a leader; k_p from the one-second fit; T_v from these rollouts',
                       k_p=kp, T_v=best[1], rmse30=round(grid[best][0], 3), per_site={k: round(v, 3) for k, v in grid[best][1].items()},
                       grid={f'{k[0]},{k[1]}': round(v[0], 3) for k, v in grid.items()}, stronger_pull_not_adopted=info)
    json.dump(out, open(FD.OUTJ, 'w'), indent=1)
    print(json.dumps(out['slow'], indent=1))


if __name__ == '__main__':
    main()
