"""One-follower windows from the held-out car-following recordings (research/truth/measure/HOLDOUT.md), in the format of
f101.py's windows.npz, for F326-F329. Run only after the forecasts are committed.

  highD location 6 (recordings 58-60): 10 s windows (tracks are about 13 s), from the 25 Hz tracks at 10 Hz.
  DLR HT 14:00-16:00 UTC: 30 s windows by report 05's rules from scripts/measure/dlrht.py blocks (--holdout), 5 Hz to 10 Hz.

Spacing is the real bumper gap (real box lengths) plus the harness leader's 5 m, so the simulated driver sees the true gap.

    python3 -I scripts/replay/heldout_windows.py highd6           # -> cars-data/replay/f101_highD6/source.npz
    python3 -I scripts/replay/heldout_windows.py ht1416 24 26     # blocks 24, 25 -> cars-data/replay/f101_HT1416/source.npz
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(REPO, 'scripts', 'measure'))
from rpl import OUT
import numpy as np, pandas as pd

LEAD_L = 5.0


def save(name, S, V, VL, run, t, fid, lid):
    D = os.path.join(OUT, f'f101_{name}'); os.makedirs(D, exist_ok=True)
    S, V, VL = (np.array(x, float).T for x in (S, V, VL))   # (W, N)
    xf = np.vstack([np.zeros((1, S.shape[1])), np.cumsum((V[1:] + V[:-1]) * 0.05, 0)])
    vref = float(np.percentile(V, 99))
    np.savez_compressed(f'{D}/source.npz', s=S, v=V, vl=VL, xl=xf + S, run=np.array(run), t=np.array(t, float), fid=np.array(fid), lid=np.array(lid), vref=vref)
    print(name, 'windows', S.shape[1], 'samples', S.shape[0], 'vref', round(vref, 2))


def highd6(W=100):
    import levelx as LX
    meta = LX.recordings('highD', holdout=True)
    out = ([], [], [], [], [], [], [])
    for rec in (58, 59, 60):
        assert int(meta.set_index('rec').loc[rec].site) == 6
        d = LX.tracks('highD', rec)
        cls = LX.tracks_meta('highD', rec).set_index('id')['class']
        car = set(cls[cls == 'Car'].index)
        u = np.where(d.dir.values == 1, -d.xc.values, d.xc.values)
        d = d.assign(u=u, v=np.abs(d.vx.values))
        key = d.set_index(['frame', 'id'])
        for fid, g in d[d.id.isin(car)].groupby('id'):
            g = g.sort_values('frame')
            pr = g.prec.values
            for lid in np.unique(pr[pr > 0]):
                if lid not in car:
                    continue
                k = g[(g.prec == lid)]
                if len(k) < W * 2.5 + 1 or (np.diff(k.frame.values) != 1).any() or k.lane.nunique() != 1:
                    continue
                try:
                    L = key.loc[list(zip(k.frame.values, np.full(len(k), lid)))]
                except KeyError:
                    continue
                tt = k.frame.values / 25.0
                ts = tt[0] + np.arange(W) * 0.1
                gap = (L.u.values - L.length.values / 2) - (k.u.values + k.length.values / 2)
                s = np.interp(ts, tt, gap) + LEAD_L
                if s.min() < 3 or s.max() > 100:
                    continue
                for a, x in zip(out, (s, np.interp(ts, tt, k.v.values), np.interp(ts, tt, L.v.values), rec, ts[0], rec * 100000 + fid, rec * 100000 + lid)):
                    a.append(x)
    save('highD6', *out)


def ht1416(b0, b1, W=300, stride=150):
    out = ([], [], [], [], [], [], [])
    for b in range(b0, b1):
        p = f'/home/erikf/projects/personal/cars-data/measure/dlrht/b{b:02d}.npz'
        z = np.load(p)
        d = pd.DataFrame({k: z[k] for k in ('id', 'ti', 's', 'lane', 'v', 'L', 'tr', 'cc', 'vl', 'Ll', 'lid')})
        d = d[(d.tr == 0)].sort_values(['id', 'ti'])
        trk = set(z['id'][z['tr'] == 1])
        for (fid, lid), g in d[d.lid >= 0].groupby(['id', 'lid']):
            if lid in trk or len(g) < 151:
                continue
            ti = g.ti.values
            cut = np.flatnonzero(np.diff(ti) != 1) + 1
            for a_, b_ in zip(np.r_[0, cut], np.r_[cut, len(g)]):
                if b_ - a_ < 151:
                    continue
                h = g.iloc[a_:b_]
                tt = h.ti.values / 5.0
                gap = h.cc.values - (h.L.values + h.Ll.values) / 2
                for t0 in np.arange(tt[0], tt[-1] - 30.0 + 1e-6, stride / 10.0):
                    ts = t0 + np.arange(W) * 0.1
                    s = np.interp(ts, tt, gap) + LEAD_L
                    v = np.interp(ts, tt, h.v.values)
                    if s.min() < 3 or s.max() > 100 or np.mean(s) / max(np.mean(v), .5) > 8:
                        continue
                    for a, x in zip(out, (s, v, np.interp(ts, tt, h.vl.values), b, t0, int(fid), int(lid))):
                        a.append(x)
    n = len(out[0])
    if n > 5000:
        pick = np.sort(np.random.default_rng(7).choice(n, 5000, replace=False))
        out = tuple([a[i] for i in pick] for a in out)
    save('HT1416', *out)


if __name__ == '__main__':
    if sys.argv[1] == 'highd6':
        highd6()
    else:
        ht1416(int(sys.argv[2]), int(sys.argv[3]))
