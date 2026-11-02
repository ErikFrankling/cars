"""Does a must-change car steer its speed toward a gap? Regression of acceleration beyond plain following on target-lane state, against through cars next to the same lane (placebo).
Then the transfer test of when sideways motion starts: per-second hazard, fit on some sites, scored on others.
Usage: mg_seek.py. Writes research/truth/merging/seek.json and transfer.json"""
import sys; sys.path.insert(0, 'research/truth/scripts/merging')
from mg_lib import *
SITES = ['i-80', 'us-101', 'I395', 'ht']
X0, T0 = 295.0, 43.0


def load(name, kind):
    f = EV / f'{name}.{kind}.csv.gz'
    if not f.exists(): return None
    d = pd.read_csv(f).sort_values(['run', 'id', 't'])
    step = {'sim': 1, 'simf': 2, 'simo': 1, 'i-80': 10, 'us-101': 10, 'I395': 10, 'ht': 5, 'I90mov': 10, 'I294L1': 10}[name]
    same = lambda k: (d['id'].shift(-k) == d['id']) & (d['run'].shift(-k) == d['run']) & (d['t'].shift(-k) - d['t'] == k * step)
    d['a_next'] = np.where(same(1) & same(2), (d['a'].shift(-1) + d['a'].shift(-2)) / 2, np.nan)
    d['v_tgt'] = d[['vF', 'vL']].mean(axis=1)
    d['dv_tgt'] = d['v_tgt'] - d['v']
    # free gap ahead minus behind in the target lane: positive means the middle of the adjacent gap is ahead of the car
    tot = d['lag'].clip(-10, 60) + d['lead'].clip(-10, 60)
    d['centre'] = ((d['lead'].clip(-10, 60) - d['lag'].clip(-10, 60)) / (tot.abs() + 5)).clip(-1, 1)
    d['over_a'] = (d['lead'] < 0).astype(float)  # target-lane leader overlaps our nose: room is behind
    d['over_b'] = (d['lag'] < 0).astype(float)   # target-lane follower overlaps our tail: room is ahead
    g = d['ogap'].where(d['ogap'] < 80)
    d['a_cf'] = cf_target(g.values, d['v'].values, d['ov'].values)
    # synchronising on the target-lane leader: what plain following of that car would ask, relative to following the own leader
    gt = d['lead'].where((d['lead'] > 0) & (d['lead'] < 60))
    d['a_sync'] = cf_target(gt.values, d['v'].values, d['vL'].values) - d['a_cf']
    d['y'] = d['a_next'] - d['a_cf']
    return d


def ols(d, cols, seed=1, nb=200):
    d = d.dropna(subset=cols + ['y'])
    X = np.c_[np.ones(len(d)), d[cols].values]; y = d['y'].values
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    r2 = 1 - np.var(y - X @ b) / np.var(y)
    rng = np.random.default_rng(seed)
    key = d['id'].values * 10 + d['run'].values
    u, inv = np.unique(key, return_inverse=True); o = np.argsort(inv); st = np.r_[0, np.where(np.diff(inv[o]) != 0)[0] + 1, len(inv)]
    B = []
    for _ in range(nb):
        pick = rng.integers(0, len(u), len(u))
        ii = np.concatenate([o[st[p]:st[p + 1]] for p in pick])
        B.append(np.linalg.lstsq(X[ii], y[ii], rcond=None)[0])
    B = np.array(B)
    return dict(n=len(d), cars=len(u), r2=round(float(r2), 4), coef={c: [round(float(b[i + 1]), 3), round(float(np.percentile(B[:, i + 1], 2.5)), 3), round(float(np.percentile(B[:, i + 1], 97.5)), 3)] for i, c in enumerate(cols)}, const=round(float(b[0]), 3))


def seek():
    out = {}
    for name in SITES + ['sim']:
        m = load(name, 'steps'); t = load(name, 'tsteps')
        if m is None: continue
        r = {}
        cols = ['dv_tgt', 'centre']; cols2 = ['dv_tgt', 'centre', 'over_a', 'over_b']
        cols3 = ['a_sync']
        for tag, md in (('all_before_last2s', m[m['tleft'] >= 2]), ('tleft_2_5', m[(m['tleft'] >= 2) & (m['tleft'] < 5)]), ('tleft_5_15', m[(m['tleft'] >= 5) & (m['tleft'] < 15)]), ('tleft_15plus', m[m['tleft'] >= 15])):
            if len(md) > 100:
                r[tag] = dict(base=ols(md, cols), overlap=ols(md, cols2), sync=ols(md, cols3))
        if t is not None and len(t) > 100:
            t_ = t[t['v'].between(m['v'].quantile(.05), m['v'].quantile(.95))]
            r['through'] = dict(base=ols(t_, cols), overlap=ols(t_, cols2), sync=ols(t_, cols3))
        out[name] = r
    save('seek', out)


def hazard_table(name):
    d = pd.read_csv(EV / f'{name}.steps.csv.gz').sort_values(['run', 'id', 't'])
    sc = pd.read_csv(EV / f'{name}.scalars.csv.gz'); sc = sc[sc['must'] == 1]
    z = np.load(EV / f'{name}.series.npz'); idx = sc['e'].values.astype(int); dT = z['edT'][idx]; tau = z['tau']; W = sc['W'].values
    t_touch = np.full(len(sc), np.nan)
    for i in range(len(sc)):
        w = np.where(dT[i] < 2.65)[0]; w = w[tau[w] <= 5]
        if len(w):
            b = np.where(np.diff(w) > 1)[0]; t_touch[i] = tau[w[b[-1] + 1]] if len(b) else tau[w[0]]
    sc = sc.assign(t_touch=t_touch)
    d = d.merge(sc[['run', 'id', 's_c', 't_touch', 'new']], on=['run', 'id'], how='inner')
    if name == 'ht':
        pos = d['new'] == 11
        d = d[(pos & (d['s_c'] < 1000)) | (~pos & (d['s_c'] > 5400))]
        sc_ = d.groupby(['run', 'id'])['s_c'].first().values
        d['s_end'] = [float(np.percentile(sc_[np.abs(sc_ - x) < 400], 99)) for x in d['s_c'].values]
    else:
        d['s_end'] = {'i-80': 204.0, 'I395': 503.0}.get(name, d['s_c'].quantile(.995))
    d['rem'] = (d['s_end'] - d['s']).clip(lower=0)
    d = d[np.isfinite(d['t_touch'])]
    # at-risk steps run until the first touch; the event is the step that holds it
    d = d[d['tleft'] >= -d['t_touch'] - 0.5]
    d = d.sort_values(['run', 'id', 't'])
    d['y'] = (d.groupby(['run', 'id']).cumcount(ascending=False) == 0).astype(float)
    return d


def features(d, kind):
    v = d['v'].clip(lower=0.5); rem = d['rem']
    lag = d['lag'].fillna(60).clip(-5, 60); lead = d['lead'].fillna(60).clip(-5, 60); vF = d['vF'].fillna(d['v']); vL = d['vL'].fillna(d['v'])
    F = {}
    if kind in ('dist', 'dist+gapm'):
        F['rem50'] = rem / 50
    if kind == 'dist+gapm':
        F['lag10'] = lag / 10; F['lead10'] = lead / 10
    if kind == 'time':
        F['tte'] = np.minimum(rem / v, 60) / 10
        F['tlag'] = (lag / vF.clip(lower=1)).clip(-3, 8); F['tlead'] = (lead / v).clip(-3, 8)
    if kind == 'lmrs':
        F['d'] = np.maximum(1 - rem / X0, 1 - rem / (v * T0)).clip(lower=-1)
        F['tlag'] = (lag / vF.clip(lower=1)).clip(-3, 8); F['tlead'] = (lead / v).clip(-3, 8)
    if kind == 'lmrs+dv':
        F['d'] = np.maximum(1 - rem / X0, 1 - rem / (v * T0)).clip(lower=-1)
        F['tlag'] = (lag / vF.clip(lower=1)).clip(-3, 8); F['tlead'] = (lead / v).clip(-3, 8)
        F['close_lag'] = (vF - d['v']).clip(-5, 5) / 3; F['close_lead'] = (d['v'] - vL).clip(-5, 5) / 3
        F['adv'] = (d['ov'].fillna(d['v']) - d['v_tgt'].fillna(d['v'])).clip(-5, 5) / 3
    if kind == 'gaponly':
        F['tlag'] = (lag / vF.clip(lower=1)).clip(-3, 8); F['tlead'] = (lead / v).clip(-3, 8)
    return np.c_[[np.asarray(x, float) for x in F.values()]].T, list(F)


def logit(X, y, l2=1e-3):
    X = np.c_[np.ones(len(X)), X]; b = np.zeros(X.shape[1])
    for _ in range(50):
        p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        g = X.T @ (y - p) - l2 * b; H = (X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(X.shape[1])
        s = np.linalg.solve(H, g); b += s
        if np.abs(s).max() < 1e-6: break
    return b


def nll_per_car(b, X, y, key):
    X = np.c_[np.ones(len(X)), X]; p = np.clip(1 / (1 + np.exp(-np.clip(X @ b, -30, 30))), 1e-9, 1 - 1e-9)
    ll = y * np.log(p) + (1 - y) * np.log(1 - p)
    return pd.Series(ll).groupby(key).sum().values, p


def transfer():
    T = {}
    for n in SITES + ['sim']:
        try:
            d = hazard_table(n); d['v_tgt'] = d[['vF', 'vL']].mean(axis=1); T[n] = d
            print(n, 'hazard rows', len(d), 'cars', int(d['y'].sum()), flush=True)
        except FileNotFoundError:
            print('missing', n)
    kinds = ['dist', 'dist+gapm', 'gaponly', 'time', 'lmrs', 'lmrs+dv']
    real = [s for s in SITES if s in T]
    out = dict(leave_one_out={}, train_i80_us101={}, coef={})
    def score(train, test, kind):
        Xt = np.vstack([features(T[s], kind)[0] for s in train]); yt = np.concatenate([T[s]['y'].values for s in train])
        # weight sites equally by subsampling nothing: fit is pooled
        b = logit(Xt, yt)
        X, names = features(T[test], kind); key = T[test]['id'].values * 10 + T[test]['run'].values
        ll, p = nll_per_car(b, X, T[test]['y'].values, key)
        # predicted distribution of remaining distance at first touch: walk each car's observed states under the hazard
        dd = T[test].assign(p=p, key=key)
        surv = dd.groupby('key')['p'].transform(lambda x: np.r_[1.0, np.cumprod(1 - x.values)[:-1]])
        w = surv * dd['p']
        o = np.argsort(dd['rem'].values); cw = np.cumsum(w.values[o]); cw /= cw[-1]
        pred50 = float(dd['rem'].values[o][np.searchsorted(cw, .5)]); pred25 = float(dd['rem'].values[o][np.searchsorted(cw, .25)]); pred75 = float(dd['rem'].values[o][np.searchsorted(cw, .75)])
        real_rem = dd[dd['y'] == 1]['rem']
        return dict(ll=round(float(ll.mean()), 3), pred=[round(pred25, 1), round(pred50, 1), round(pred75, 1)], real=[round(float(real_rem.quantile(x)), 1) for x in (.25, .5, .75)], coef=dict(zip(['const'] + names, [round(float(x), 3) for x in b])))
    for kind in kinds:
        out['leave_one_out'][kind] = {t: score([s for s in real if s != t], t, kind) for t in real}
        if 'i-80' in T and 'us-101' in T:
            out['train_i80_us101'][kind] = {t: score(['i-80', 'us-101'], t, kind) for t in real if t not in ('i-80', 'us-101')}
            out['train_i80_us101'][kind]['sim'] = score(['i-80', 'us-101'], 'sim', kind) if 'sim' in T else None
    save('transfer', out)


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'both'
    if what in ('seek', 'both'): seek()
    if what in ('transfer', 'both'): transfer()
