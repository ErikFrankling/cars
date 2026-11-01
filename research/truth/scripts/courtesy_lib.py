"""Shared frame tables and neighbour lookups for the courtesy study. Inputs are inert CSVs read with python -I."""
import os
os.environ.setdefault('OMP_NUM_THREADS', '2'); os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
import numpy as np, pandas as pd, pathlib, json

T = pathlib.Path('/home/erikf/projects/personal/cars-data/truth/trajectories')
C = pathlib.Path('/home/erikf/projects/personal/cars-data/truth/courtesy')
OUT = pathlib.Path('research/truth/courtesy'); OUT.mkdir(exist_ok=True)
FT = 0.3048


def ngsim(path, urban=False):
    """US-101 and I-80 have three recording periods, so run comes from global_time gaps."""
    cols = ['vehicle_id', 'global_time', 'local_x', 'local_y', 'v_length', 'v_class', 'v_vel', 'v_acc', 'lane_id']
    if urban: cols += ['int_id', 'section_id', 'direction', 'movement']
    d = pd.read_csv(path, usecols=cols).drop_duplicates(['vehicle_id', 'global_time'])
    gt = d['global_time'].values.astype('i8')
    u = np.unique(gt); brk = np.where(np.diff(u) > 60000)[0]
    starts = np.r_[u[0], u[brk + 1]]
    run = np.searchsorted(starts, gt, side='right') - 1
    t = ((gt - starts[run]) / 100).round().astype('i4')
    out = dict(run=run.astype('i2'), t=t, id=d['vehicle_id'].values.astype('i4'), lane=d['lane_id'].values.astype('i2'),
               s=(d['local_y'].values * FT).astype('f4'), lat=(d['local_x'].values * FT).astype('f4'), v=(d['v_vel'].values * FT).astype('f4'),
               a=(d['v_acc'].values * FT).astype('f4'), L=(d['v_length'].values * FT).astype('f4'), cls=d['v_class'].values.astype('i1'))
    if urban:
        out.update(int_id=d['int_id'].values.astype('i2'), section=d['section_id'].values.astype('i2'), dirn=d['direction'].values.astype('i1'), move=d['movement'].values.astype('i1'))
    return pd.DataFrame(out)


def tgsim(name):
    d = pd.read_csv(T / 'opus-20261031-tgsim' / f'{name}.csv', dtype={'lane_kf': 'float32'})
    d.columns = [c.strip().lower().replace('-', '_') for c in d.columns]
    if 'run_index' not in d: d['run_index'] = 0
    d = d.drop_duplicates(['run_index', 'id', 'time'])
    axis = 'yloc_kf' if name == 'I395' else 'xloc_kf'; other = 'xloc_kf' if name == 'I395' else 'yloc_kf'
    ti = np.round(d['time'].values * 10).astype('i4')
    auto = np.zeros(len(d), 'i1')
    for c in ('av', 'acc'):
        if c in d: auto = d[c].map(lambda x: 0 if str(x).strip().lower() in ('no', '0', 'false', 'nan', '') else 1).values.astype('i1')
    out = pd.DataFrame(dict(run=d['run_index'].values.astype('i2'), t=ti, id=d['id'].values.astype('i4'), lane=d['lane_kf'].values.astype('i2'), x=d[axis].values.astype('f8'),
                            lat=d[other].values.astype('f4'), v=d['speed_kf'].values.astype('f4'), a=d['acceleration_kf'].values.astype('f4'), L=d['length_smoothed'].values.astype('f4'), auto=auto))
    out = out.sort_values(['run', 'id', 't'])
    dx = out.groupby(['run', 'id'])['x'].transform(lambda s: np.sign(s.iloc[-1] - s.iloc[0]))
    out['sgn'] = dx.values.astype('i1')
    out = out[out['sgn'] != 0]
    # front bumper along travel; the files hold the centre
    out['s'] = (out['x'] * out['sgn'] + out['L'] / 2).astype('f4')
    # lane key separates opposite directions that share a lane number
    out['lane'] = (out['lane'] * out['sgn']).astype('i2')
    return out.drop(columns=['x', 'sgn']).reset_index(drop=True)


class Frames:
    """Fast 'who is next to whom at time t' lookups on a frame table with columns run,t,id,lane,s,v,a,L."""

    def __init__(self, d, hz=10):
        self.hz = hz
        o = np.lexsort((d['s'].values, d['lane'].values.astype('i8'), d['t'].values, d['run'].values))
        self.R, self.TT, self.ID, self.LA, self.S, self.V, self.A, self.LEN = [d[c].values[o] for c in ('run', 't', 'id', 'lane', 's', 'v', 'a', 'L')]
        self.K = self.key(self.R, self.TT, self.LA)
        o2 = np.lexsort((d['t'].values, d['id'].values.astype('i8'), d['run'].values))
        self.vR, self.vID, self.vT, self.vLA, self.vS, self.vV, self.vA, self.vL = [d[c].values[o2] for c in ('run', 'id', 't', 'lane', 's', 'v', 'a', 'L')]
        k = (self.vR.astype('i8') << 32) | (self.vID.astype('i8') & 0xffffffff)
        self.vk = k
        ub = np.r_[0, np.where(np.diff(k) != 0)[0] + 1, len(k)]
        self.veh = {int(k[a]): (int(a), int(b)) for a, b in zip(ub[:-1], ub[1:])}

    @staticmethod
    def key(r, t, l):
        return (np.asarray(r, 'i8') << 44) | (np.asarray(t, 'i8') << 12) | (np.asarray(l, 'i8') + 2048)

    def lane_at(self, r, t, l):
        k = self.key(r, t, l)
        return np.searchsorted(self.K, k, 'left'), np.searchsorted(self.K, k, 'right')

    def neighbours(self, r, t, l, s_front, skip):
        """Front-bumper order in lane l at time t: returns indices (follower, leader) of the sorted table or -1."""
        a, b = self.lane_at(r, t, l)
        if a == b: return -1, -1
        i = a + int(np.searchsorted(self.S[a:b], s_front, 'left'))
        f = i - 1
        while f >= a and self.ID[f] == skip: f -= 1
        ld = i
        while ld < b and self.ID[ld] == skip: ld += 1
        return (f if f >= a else -1), (ld if ld < b else -1)

    def track(self, r, vid):
        return self.veh.get((int(r) << 32) | (int(vid) & 0xffffffff))

    def series(self, r, vid, tq):
        """v,s,a,lane for vehicle vid at integer frame times tq; nan where missing."""
        rng = self.track(r, vid)
        n = len(tq); nan = np.full(n, np.nan)
        if rng is None: return nan, nan.copy(), nan.copy(), nan.copy()
        a, b = rng
        i = np.searchsorted(self.vT[a:b], tq); i2 = np.minimum(i, b - a - 1)
        ok = self.vT[a:b][i2] == tq
        v = np.where(ok, self.vV[a:b][i2], np.nan); s = np.where(ok, self.vS[a:b][i2], np.nan)
        ac = np.where(ok, self.vA[a:b][i2], np.nan); la = np.where(ok, self.vLA[a:b][i2], np.nan)
        return v, s, ac, la


def lane_changes(fr, adj, hold=4.0):
    """Debounced lane changes: one label step, same lane for `hold` seconds on both sides, no frame gaps."""
    hw = int(hold * fr.hz); out = []
    for (a, b) in fr.veh.values():
        if b - a < 2 * hw + 1: continue
        l = fr.vLA[a:b]
        for k in np.where(l[1:] != l[:-1])[0] + 1:
            if k < hw or k > b - a - hw - 1: continue
            lw = l[k - hw:k + hw]
            if (np.diff(lw) != 0).sum() != 1: continue
            if not adj(int(l[k - 1]), int(l[k])): continue
            if fr.vT[a + k + hw - 1] - fr.vT[a + k - hw] != 2 * hw - 1: continue
            out.append((int(fr.vR[a]), int(fr.vID[a]), int(fr.vT[a + k]), int(l[k - 1]), int(l[k])))
    return out


def q(x, ps=(5, 25, 50, 75, 95)):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if not len(x): return {'n': 0}
    return {'n': int(len(x)), **{f'p{p:02d}': round(float(np.percentile(x, p)), 3) for p in ps}, 'mean': round(float(x.mean()), 3)}


def logit_fit(X, y, names, w=None, l2=1e-6):
    """Newton logistic with intercept. Returns coefficient dict."""
    X = np.c_[np.ones(len(X)), X]; b = np.zeros(X.shape[1]); w = np.ones(len(y)) if w is None else w
    for _ in range(40):
        p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        g = X.T @ (w * (y - p)) - l2 * b
        H = (X * (w * p * (1 - p))[:, None]).T @ X + l2 * np.eye(X.shape[1])
        d = np.linalg.solve(H, g); b += d
        if np.abs(d).max() < 1e-7: break
    return dict(zip(['const'] + names, b))


def logit_boot(X, y, cluster, names, n=200, seed=1):
    """Logistic with a percentile bootstrap that resamples clusters (a car's repeated decisions are not independent)."""
    full = logit_fit(X, y, names)
    rng = np.random.default_rng(seed); u, inv = np.unique(cluster, return_inverse=True)
    order = np.argsort(inv); starts = np.r_[0, np.where(np.diff(inv[order]) != 0)[0] + 1, len(inv)]
    bs = []
    for _ in range(n):
        pick = rng.integers(0, len(u), len(u))
        idx = np.concatenate([order[starts[i]:starts[i + 1]] for i in pick])
        try: bs.append(list(logit_fit(X[idx], y[idx], names).values()))
        except np.linalg.LinAlgError: pass
    bs = np.array(bs)
    return {k: {'b': round(float(full[k]), 4), 'lo': round(float(np.percentile(bs[:, i], 2.5)), 4), 'hi': round(float(np.percentile(bs[:, i], 97.5)), 4)} for i, k in enumerate(full)}


def save(name, obj):
    (OUT / f'{name}.json').write_text(json.dumps(obj, indent=1, default=float)); print('wrote', name, flush=True)
