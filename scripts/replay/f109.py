"""F109: the driver's response given the same history. A follower is replayed from its recording up to a moment, then
released to the driver for one second behind its replayed leader. Its speed change over that second is scored with
CRPS against the recorded follower's, over a seed ensemble. The floor: the nearest-history real followers of other
vehicles (same leader motion in the next second too) as an ensemble. The null: constant speed.

    python3 -I scripts/replay/f109.py build
    python3 -I scripts/replay/f109.py run main 0..9
    python3 -I scripts/replay/f109.py score
"""
import sys, os, json, glob
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
from rpl import *
import numpy as np, pandas as pd

SITE = os.environ.get('F101_SITE', 'I90mov')
F101D = os.path.join(OUT, 'f101' if SITE == 'I90mov' else f'f101_{SITE}')
D = os.path.join(OUT, 'f109' if SITE == 'I90mov' else f'f109_{SITE}')
T0, X0, W = 1.0, 20.0, int(os.environ.get('F101_W', '300'))
RELEASE = tuple(int(x) for x in os.environ.get('F109_RELEASE', '30,80,130,180,230').split(','))   # samples into the window: 3, 8, 13, 18, 23 s
H = 10                               # one second ahead
NW = int(os.environ.get("F109_NW", "1000"))


def load():
    w = np.load(f'{F101D}/windows.npz')
    s, v, vl = w['s'].astype(float), w['v'].astype(float), w['vl'].astype(float)
    xf = np.vstack([np.zeros((1, s.shape[1])), np.cumsum((v[1:] + v[:-1]) * 0.05, 0)])
    return w, s, v, vl, xf


def build():
    os.makedirs(D, exist_ok=True)
    w, s, v, vl, xf = load()
    pick = np.sort(np.random.default_rng(11).choice(s.shape[1], NW, replace=False))
    q = [(i, r) for i in pick for r in RELEASE]
    with open(f'{D}/plain.nod.xml', 'w') as f, open(f'{D}/plain.edg.xml', 'w') as g:
        f.write('<nodes>\n'); g.write('<edges>\n')
        for c, (i, r) in enumerate(q):
            L = X0 + float(xf[-1, i] + s[:, i].max()) + 200.0
            f.write(f'  <node id="a{c}" x="0" y="{20.0 * c}"/>\n  <node id="b{c}" x="{L:.1f}" y="{20.0 * c}"/>\n')
            g.write(f'  <edge id="q{c}" from="a{c}" to="b{c}" numLanes="1" speed="{float(w["vref"]):.3f}"/>\n')
        f.write('</nodes>\n'); g.write('</edges>\n')
    netconvert(f'{D}/plain', f'{D}/net.xml')
    tracks, trips = [], []
    for c, (i, r) in enumerate(q):
        xl = X0 + xf[:, i] + s[:, i]
        tracks.append((f'L{c}', T0, 0.1, INF, np.full(W, c), xl, vl[:, i]))
        # Replayed through sample r, the driver's from the next step on.
        tracks.append((f'F{c}', T0, 0.1, T0 + r * 0.1 + 0.05, np.full(r + 1, c), X0 + xf[:r + 1, i], v[:r + 1, i]))
        trips.append((T0 - 0.1, f'L{c}', 'lead', c, xl[0] - vl[0, i] * 0.1, vl[0, i]))
        trips.append((T0, f'F{c}', 'drv', c, X0, v[0, i]))
    write_rpl(f'{D}/q.rpl', [f'q{c}_0' for c in range(len(q))], tracks)
    with open(f'{D}/routes.xml', 'w') as f:
        f.write('<routes>\n  <vType id="lead" length="5" lcStrategic="-1" lcCooperative="0" lcSpeedGain="0" lcKeepRight="0"/>\n')
        # The desired speed: the measured spread (CV 0.17) cut below at the speed at release, as f101.py F101_COND.
        for c, (i, r) in enumerate(q):
            lo = min(max(float(v[r, i]), 0.0) / float(w['vref']), 1.3)
            f.write(f'  <vType id="drv{c}" carFollowModel="Krauss" speedFactor="normc(1,0.17,{lo:.4f},2)"/>\n')
        for t, tid, vt, c, pos, sp in sorted(trips, key=lambda r: (r[0], r[1])):
            f.write(f'  <trip id="{tid}" type="{vt if vt == "lead" else f"drv{c}"}" depart="{t:.1f}" from="q{c}" to="q{c}" departLane="0" departPos="{pos:.3f}" departSpeed="{max(sp, 0):.3f}"/>\n')
        f.write('</routes>\n')
    json.dump(dict(q=[[int(i), int(r)] for i, r in q]), open(f'{D}/q.json', 'w'))
    print('queries', len(q))


def run(seed, tag='main', gpu=False):
    out = f'{D}/{tag}_s{seed}'
    end = T0 + (max(RELEASE) + H + 2) * 0.1
    run_cars(['--net', f'{D}/net.xml', '--routes', f'{D}/routes.xml', '--replay', f'{D}/q.rpl', '--dt', '0.1', '--begin', 0, '--end', end,
              '--seed', seed, '--time-to-teleport', '0', '--fcd', f'{out}.fcd.csv', '--fcd-begin', T0 - 0.05, '--fcd-interval', '0.1'] + os.environ.get('F101_FLAGS', '').split(), gpu=gpu, log=f'{out}.log')
    f = pd.read_csv(f'{out}.fcd.csv', usecols=['time', 'trip', 'speed'])
    f = f[f.trip.str[0] == 'F']
    f['k'] = np.round((f.time - T0) * 10).astype(int); f['c'] = f.trip.str[1:].astype(int)
    q = np.array(json.load(open(f'{D}/q.json'))['q'])
    want = q[:, 1] + H
    m = f.set_index(['c', 'k']).speed
    vs = np.array([m.get((c, k), np.nan) for c, k in zip(range(len(q)), want)])
    v0 = np.array([m.get((c, k), np.nan) for c, k in zip(range(len(q)), q[:, 1])])
    np.savez(f'{out}.resp.npz', v_end=vs, v_rel=v0)


def crps(ens, y):
    ens = np.asarray(ens, float)
    return np.mean(np.abs(ens - y)) - 0.5 * np.mean(np.abs(ens[:, None] - ens[None, :]))


def score(tag='main'):
    w, s, v, vl, xf = load()
    q = np.array(json.load(open(f'{D}/q.json'))['q'])
    runs = sorted(glob.glob(f'{D}/{tag}_s*.resp.npz'))
    E = np.stack([np.load(p)['v_end'] for p in runs], 1)
    V0 = np.stack([np.load(p)['v_rel'] for p in runs], 1)
    i, r = q[:, 0], q[:, 1]
    y = v[r + H, i] - v[r, i]
    sim = E - v[r, i][:, None]
    harness = float(np.nanmax(np.abs(V0 - v[r, i][:, None])))
    # History features at 1 s steps: own speed, spacing, leader speed over the last 3 s, and the leader's next second.
    def hist(ii, rr):
        cols = [v[rr - k, ii] for k in (0, 10, 20, 30)] + [s[rr - k, ii] / 3 for k in (0, 10, 20, 30)] + [vl[rr + k, ii] for k in (-30, -20, -10, 0, 5, 10)]
        return np.stack(cols, 1)
    pool_i, pool_r = np.meshgrid(np.arange(s.shape[1]), np.arange(30, W - H, 10), indexing='ij')
    pool_i, pool_r = pool_i.ravel(), pool_r.ravel()
    P = hist(pool_i, pool_r); Q = hist(i, r); dy_pool = v[pool_r + H, pool_i] - v[pool_r, pool_i]
    mu, sd = P.mean(0), P.std(0) + 1e-9; P = (P - mu) / sd; Q = (Q - mu) / sd
    fid = w['fid']; K = 10
    floor, sim_c, null_c, n_ok = [], [], [], 0
    sqP = (P ** 2).sum(1)
    for a in range(0, len(Q), 256):
        d = (Q[a:a + 256] ** 2).sum(1)[:, None] + sqP[None, :] - 2 * Q[a:a + 256] @ P.T
        for rr, qi in enumerate(range(a, min(a + 256, len(Q)))):
            d[rr, fid[pool_i] == fid[i[qi]]] = np.inf
            d[rr, w['lid'][pool_i] == w['lid'][i[qi]]] = np.inf
        nn = np.argpartition(d, K, 1)[:, :K]
        for rr, qi in enumerate(range(a, min(a + 256, len(Q)))):
            if not np.isfinite(sim[qi]).all():
                continue
            n_ok += 1
            floor.append(crps(dy_pool[nn[rr]], y[qi])); sim_c.append(crps(sim[qi], y[qi])); null_c.append(abs(y[qi]))
    floor, sim_c, null_c = map(np.array, (floor, sim_c, null_c))
    rng = np.random.default_rng(2); g = np.array([w['fid'][i[k]] for k in range(len(q)) if np.isfinite(sim[k]).all()])
    ug, gi = np.unique(g, return_inverse=True)
    def ci(x):
        sx = np.bincount(gi, x, len(ug)); c = np.bincount(gi, minlength=len(ug)); bs = []
        for _ in range(1000):
            k = np.bincount(rng.integers(0, len(ug), len(ug)), minlength=len(ug)); bs.append((k * sx).sum() / (k * c).sum())
        return [float(z) for z in np.percentile(bs, [2.5, 97.5])]
    res = dict(queries=int(len(q)), scored=int(n_ok), seeds=len(runs), harness_max_speed_error_at_release=harness,
               crps_driver=float(sim_c.mean()), crps_driver_ci95=ci(sim_c), crps_real_floor_knn10=float(floor.mean()), crps_floor_ci95=ci(floor),
               crps_constant_speed=float(null_c.mean()), crps_null_ci95=ci(null_c), driver_minus_floor_ci95=ci(sim_c - floor),
               recorded_dv_sd=float(np.std(y)), driver_dv_sd=float(np.nanstd(sim)), driver_ensemble_spread_mean=float(np.nanmean(np.nanstd(sim, 1))))
    print(json.dumps(res, indent=1))
    name = ('f109' if tag == 'main' else f'f109_{tag}') + ('' if SITE == 'I90mov' else f'_{SITE}')
    json.dump(res, open(os.path.join(REPO, 'research/truth/replay', f'{name}.json'), 'w'), indent=1)


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'build':
        build()
    elif c == 'run':
        for sd in sys.argv[3].split(',') if ',' in sys.argv[3] else range(int(sys.argv[3].split('..')[0]), int(sys.argv[3].split('..')[1]) + 1):
            run(int(sd), sys.argv[2], gpu='--gpu' in sys.argv)
    elif c == 'score':
        score(sys.argv[2] if len(sys.argv) > 2 else 'main')
