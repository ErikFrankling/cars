"""Shared table for the merging study. Reads the per-site cache from mg_cache.py. No inputs are executed."""
import os
os.environ.setdefault('OMP_NUM_THREADS', '2'); os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
import numpy as np, pandas as pd, pathlib, json

ROOT = pathlib.Path(os.environ.get('MG_DATA', '/home/erikf/projects/personal/cars-data/truth/merging-20261102'))
CACHE = ROOT / 'cache'; EV = ROOT / 'events'; EV.mkdir(exist_ok=True)
RES = pathlib.Path('research/truth/merging'); RES.mkdir(exist_ok=True)


class Site:
    def __init__(self, name):
        self.name = name
        z = np.load(CACHE / f'{name}.npz')
        self.R, self.T, self.I, self.LA, self.S, self.V, self.A, self.LL, self.LT = [z[c] for c in ('run', 't', 'id', 'lane', 's', 'v', 'a', 'L', 'lat')]
        self.hz = int(z['hz'])
        k = (self.R.astype('i8') << 32) | (self.I.astype('i8') & 0xffffffff)
        ub = np.r_[0, np.where(np.diff(k) != 0)[0] + 1, len(k)]
        self.veh = {int(k[a]): (int(a), int(b)) for a, b in zip(ub[:-1], ub[1:])}
        o = np.lexsort((self.S, self.LA.astype('i8'), self.T, self.R))
        self.oS, self.oI, self.oL, self.oV = self.S[o], self.I[o], self.LL[o], self.V[o]
        self.K = self.key(self.R[o], self.T[o], self.LA[o])
        cen = pd.read_csv(CACHE / f'{name}.centres.csv.gz')
        self.cen = {}
        for (r, l), g in cen.groupby(['r', 'l']):
            g = g.sort_values('b'); self.cen[(int(r), int(l))] = (g['b'].values * 20.0 + 10.0, g['median'].values)

    @staticmethod
    def key(r, t, l):
        return (np.asarray(r, 'i8') << 44) | (np.asarray(t, 'i8') << 12) | (np.asarray(l, 'i8') + 2048)

    def centre(self, r, l, s):
        c = self.cen.get((int(r), int(l)))
        if c is None: return np.full(np.shape(s), np.nan)
        return np.interp(s, c[0], c[1])

    def around(self, r, t, lane, s_front, skip):
        """Follower and leader of position s_front in a lane at frame t, by front bumper, skipping one id. Returns (id, s, L, v) pairs or None."""
        k = self.key(r, t, lane)
        a = np.searchsorted(self.K, k, 'left'); b = np.searchsorted(self.K, k, 'right')
        if a == b: return None, None
        i = a + int(np.searchsorted(self.oS[a:b], s_front, 'left'))
        f = i - 1
        while f >= a and self.oI[f] == skip: f -= 1
        l = i
        while l < b and self.oI[l] == skip: l += 1
        F = (int(self.oI[f]), float(self.oS[f]), float(self.oL[f]), float(self.oV[f])) if f >= a else None
        L = (int(self.oI[l]), float(self.oS[l]), float(self.oL[l]), float(self.oV[l])) if l < b else None
        return F, L

    def series(self, r, vid, tq):
        """v, s, a, lane, lat at integer frames tq; nan where missing."""
        n = len(tq)
        rng = self.veh.get((int(r) << 32) | (int(vid) & 0xffffffff))
        if rng is None: return [np.full(n, np.nan) for _ in range(5)]
        a, b = rng
        i = np.minimum(np.searchsorted(self.T[a:b], tq), b - a - 1) + a
        ok = self.T[i] == tq
        return [np.where(ok, x[i], np.nan) for x in (self.V, self.S, self.A, self.LA, self.LT)]


def cf_target(g, v, vl, T=1.30, s0=2.8, k1=0.011, k2=0.52, amax=1.8):
    """Report 05's feedback law, without its 1 s lag. g is bumper gap, m. Spacing there uses a 5 m leader, so s0 is the gap term as fitted."""
    g = np.maximum(g, 1.0)
    return np.clip(k1 * (g - s0 - T * v) + k2 * np.sqrt(15.0 / g) * (vl - v), -4.5, amax)


def q(x, ps=(5, 25, 50, 75, 95)):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if not len(x): return {'n': 0}
    return {'n': int(len(x)), **{f'p{p:02d}': round(float(np.percentile(x, p)), 3) for p in ps}, 'mean': round(float(x.mean()), 3)}


def boot_mean(x, n=1000, seed=3):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) < 3: return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    m = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(n)]
    return float(x.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def save(name, obj):
    (RES / f'{name}.json').write_text(json.dumps(obj, indent=1, default=float)); print('wrote', name, flush=True)
