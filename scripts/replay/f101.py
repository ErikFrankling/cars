"""F101 and F105: one simulated follower behind its replayed leader, report 05's held-out I-90/94 moving windows.
Each window runs on its own one-lane edge, so all 4,955 run side by side in one world, as separate rollouts.

    python3 -I scripts/replay/f101.py build                 # cars-data/replay/f101/
    python3 -I scripts/replay/f101.py run main 0 [--gpu]    # main's driver, physical mode, seed 0
    python3 -I scripts/replay/f101.py run sumo 0            # --sumo-compat Krauss with speedDev 0: the F105 cross-check
    python3 -I scripts/replay/f101.py score                 # every run in the folder
    F101_SITE=I294L1 python3 -I scripts/replay/f101.py build  # the same windows from another TGSIM site, in f101_I294L1/
    F101_FLAGS='--tune measured=0' ...                      # extra flags for cars run
    F101_COND=1 ...                                         # desired speed cut below at the release speed (routes_cond.xml)
"""
import sys, os, json, glob
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
from rpl import *
import numpy as np, pandas as pd

SITE = os.environ.get('F101_SITE', 'I90mov')
D = os.path.join(OUT, 'f101' if SITE == 'I90mov' else f'f101_{SITE}')
MAXN = int(os.environ.get('F101_MAXN', '0')) or None
T0 = 1.0          # window start in simulation time
X0 = 20.0         # follower's start on its edge
W = int(os.environ.get('F101_W', '300'))   # 30 s at 0.1 s, as report 05; highD's 13 s tracks take 100


def windows():
    """Report 05's I-90/94 moving test set, cut by its own code from its own pair cache, or windows prepared by
    heldout_windows.py (source.npz in the folder)."""
    if os.path.exists(f'{D}/source.npz'):
        from types import SimpleNamespace
        z = np.load(f'{D}/source.npz')
        n = z['s'].shape[1]
        return SimpleNamespace(N=n, s=z['s'], v=z['v'], vl=z['vl'], xl=z['xl'],
                               meta=dict(vref=np.full(n, float(z['vref'])), run=z['run'], t=z['t'], fid=z['fid'], lid=z['lid']))
    os.chdir(REPO)
    sys.path.insert(0, os.path.join(REPO, 'research/truth/scripts'))
    from opus_windows import windows as cut
    return cut(SITE, maxn=MAXN)


def build():
    os.makedirs(D, exist_ok=True)
    b = windows()
    N = b.N
    vref = float(b.meta['vref'][0])
    xl = X0 + b.xl[:W]                     # leader front, from the follower's integrated speed plus recorded spacing
    vl = b.vl[:W]
    with open(f'{D}/plain.nod.xml', 'w') as f, open(f'{D}/plain.edg.xml', 'w') as g:
        f.write('<nodes>\n'); g.write('<edges>\n')
        for i in range(N):
            L = float(xl[:, i].max()) + 150.0
            y = 20.0 * i
            f.write(f'  <node id="a{i}" x="0" y="{y}"/>\n  <node id="b{i}" x="{L:.1f}" y="{y}"/>\n')
            g.write(f'  <edge id="w{i}" from="a{i}" to="b{i}" numLanes="1" speed="{vref:.3f}"/>\n')
        f.write('</nodes>\n'); g.write('</edges>\n')
    netconvert(f'{D}/plain', f'{D}/net.xml')
    lanes = [f'w{i}_0' for i in range(N)]
    tracks, trips = [], []
    for i in range(N):
        # The leader enters one step before the window: a one-lane queue inserts one vehicle per step.
        tracks.append((f'L{i}', T0, 0.1, INF, np.full(W, i), xl[:, i], vl[:, i]))
        tracks.append((f'F{i}', T0, 0.1, T0, [], [], []))
        trips.append((T0 - 0.1, f'L{i}', 'lead', i, xl[0, i] - vl[0, i] * 0.1, vl[0, i]))
        trips.append((T0, f'F{i}', 'drv', i, X0, b.v[0, i]))
    write_rpl(f'{D}/windows.rpl', lanes, tracks)
    for tag, drv in (('main', '<vType id="drv" carFollowModel="Krauss"/>'),
                     ('sumo', '<vType id="drv" carFollowModel="Krauss" speedDev="0"/>')):
        with open(f'{D}/routes_{tag}.xml', 'w') as f:
            f.write('<routes>\n  <vType id="lead" length="5" lcStrategic="-1" lcCooperative="0" lcSpeedGain="0" lcKeepRight="0"/>\n')
            f.write(f'  {drv}\n')
            for t, tid, vt, i, pos, v in sorted(trips, key=lambda r: (r[0], r[1])):
                f.write(f'  <trip id="{tid}" type="{vt}" depart="{t:.1f}" from="w{i}" to="w{i}" departLane="0" departPos="{pos:.3f}" departSpeed="{max(v, 0):.3f}"/>\n')
            f.write('</routes>\n')
    # The follower drew its desired speed from the population, but it is one who drove at its release speed: the measured
    # spread (DRIVER.md, CV 0.17) cut below at that speed over the lane's. Nothing after the release is used.
    with open(f'{D}/routes_cond.xml', 'w') as f:
        f.write('<routes>\n  <vType id="lead" length="5" lcStrategic="-1" lcCooperative="0" lcSpeedGain="0" lcKeepRight="0"/>\n')
        for i in range(N):
            lo = min(max(float(b.v[0, i]), 0.0) / vref, 1.3)
            f.write(f'  <vType id="drv{i}" carFollowModel="Krauss" speedFactor="normc(1,0.17,{lo:.4f},2)"/>\n')
        for t, tid, vt, i, pos, v in sorted(trips, key=lambda r: (r[0], r[1])):
            f.write(f'  <trip id="{tid}" type="{vt if vt == "lead" else f"drv{i}"}" depart="{t:.1f}" from="w{i}" to="w{i}" departLane="0" departPos="{pos:.3f}" departSpeed="{max(v, 0):.3f}"/>\n')
        f.write('</routes>\n')
    np.savez_compressed(f'{D}/windows.npz', s=b.s[:W], v=b.v[:W], vl=b.vl[:W], run=b.meta['run'], t=b.meta['t'], fid=b.meta['fid'], lid=b.meta['lid'], vref=vref)
    print('windows', N, 'vref', vref)


def run(tag, seed, gpu=False):
    out = f'{D}/{tag}_s{seed}'
    flags = (['--sumo-compat'] if tag == 'sumo' else []) + os.environ.get('F101_FLAGS', '').split()
    routes = 'sumo' if tag == 'sumo' else ('cond' if os.environ.get('F101_COND') else 'main')
    log = run_cars(['--net', f'{D}/net.xml', '--routes', f'{D}/routes_{routes}.xml', '--replay', f'{D}/windows.rpl', '--dt', '0.1',
                    '--begin', 0, '--end', T0 + W * 0.1, '--seed', seed, '--time-to-teleport', '0', '--fcd', f'{out}.fcd.csv',
                    '--fcd-begin', T0 - 0.05, '--fcd-interval', '0.1'] + flags, gpu=gpu, log=f'{out}.log')
    print(log[-600:])
    rollout(out)


def rollout(out):
    """Simulated spacing and speed per window on the window's time grid; NaN where a vehicle is missing."""
    f = pd.read_csv(f'{out}.fcd.csv', usecols=['time', 'trip', 'pos', 'speed', 'acc'])
    f['k'] = np.round((f.time - T0) * 10).astype(int)
    f = f[(f.k >= 0) & (f.k < W)]
    f['i'] = f.trip.str[1:].astype(int)
    N = int(np.load(f'{D}/windows.npz')['s'].shape[1])
    xf = np.full((W, N), np.nan); vf = xf.copy(); af = xf.copy(); xl = xf.copy()
    F = f[f.trip.str[0] == 'F']; Lr = f[f.trip.str[0] == 'L']
    xf[F.k, F.i] = F.pos; vf[F.k, F.i] = F.speed; af[F.k, F.i] = F.acc
    xl[Lr.k, Lr.i] = Lr.pos
    np.savez_compressed(f'{out}.roll.npz', S=xl - xf, V=vf, A=af)


def score():
    w = np.load(f'{D}/windows.npz')
    s, v = w['s'], w['v']
    cl = np.array([f'{r}:{int(t // 300)}' for r, t in zip(w['run'], w['t'])])
    res = {}
    for p in sorted(glob.glob(f'{D}/*_s*.roll.npz')):
        r = np.load(p); S, V = r['S'], r['V']
        ok = np.isfinite(S).all(0)
        overlap = (np.nanmin(S, 0) < 5.0)          # bumper gap below zero: leader length is 5 m
        es = (S - s) ** 2; ev = (V - v) ** 2
        name = os.path.basename(p)[:-9]
        per = dict(windows=int(len(ok)), complete=int(ok.sum()), overlap_windows=int(overlap.sum()),
                   spacing_rmse_30s=float(np.sqrt(np.nanmean(es[:, ok]))), speed_rmse_30s=float(np.sqrt(np.nanmean(ev[:, ok]))),
                   spacing_rmse_10s=float(np.sqrt(np.nanmean(es[:100, ok]))), spacing_rmse_5s=float(np.sqrt(np.nanmean(es[:50, ok]))))
        # 95% interval: bootstrap of 300 s traffic blocks, as report 05
        u, inv = np.unique(cl[ok], return_inverse=True)
        sx = np.bincount(inv, es[:, ok].mean(0), len(u)); c = np.bincount(inv, minlength=len(u))
        rng = np.random.default_rng(1); bs = []
        for _ in range(500):
            k = np.bincount(rng.integers(0, len(u), len(u)), minlength=len(u))
            bs.append(np.sqrt((k * sx).sum() / (k * c).sum()))
        per['spacing_ci95'] = [float(x) for x in np.percentile(bs, [2.5, 97.5])]
        res[name] = per
        print(name, json.dumps(per))
    for tag in sorted({k.rsplit('_s', 1)[0] for k in res}):
        vals = [r['spacing_rmse_30s'] for k, r in res.items() if k.startswith(tag + '_')]
        if vals:
            res[f'{tag}_over_seeds'] = dict(n=len(vals), mean=float(np.mean(vals)), min=float(np.min(vals)), max=float(np.max(vals)))
            print(tag, res[f'{tag}_over_seeds'])
    os.makedirs(os.path.join(REPO, 'research/truth/replay'), exist_ok=True)
    json.dump(res, open(os.path.join(REPO, 'research/truth/replay', 'f101.json' if SITE == 'I90mov' else f'f101_{SITE}.json'), 'w'), indent=1)


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'build':
        build()
    elif c == 'run':
        run(sys.argv[2], int(sys.argv[3]), gpu='--gpu' in sys.argv)
    elif c == 'score':
        score()
