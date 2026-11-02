"""Final checks. (1) Follower law with its gap taper, held out, including the simulator's followers. (2) When sideways motion starts, scored only inside the zone where a change is physically possible (I-80 last 54 m, I-395 last 63 m, where lane centres are under about 4 m apart)."""
import sys; sys.path.insert(0, 'research/truth/scripts/merging')
from mg_lib import *
from mg_replay_lib import follower_rows
import mg_seek as M
out = {}
TR = ['i-80', 'us-101']; Fd = {}
for n in ['i-80', 'us-101', 'I395', 'I90mov', 'I294L1', 'ht', 'sim', 'simo', 'simf']:
    d = follower_rows(n)
    own = cf_target(d['g'].where(d['g'] < 80).values, d['v'].values, d['vl'].values); d['own'] = np.where(np.isfinite(own), own, 0.5)
    d['mer'] = cf_target(np.maximum(d['lag'].values, 0.5), d['v'].values, d['ve'].values)
    d['x'] = np.minimum(d['mer'] - d['own'], 0.0); d['y'] = d['a'] - d['own']
    d['cl'] = d['v'] - d['ve']
    d['g_lag'] = np.clip(0.2 + d['lag'] / 5.0, 0.2, 1.0); d['g_cl'] = np.where(d['cl'] > 3, 0.5, 1.0)
    d['x2'] = d['x'] * d['g_lag'] * d['g_cl']
    Fd[n] = d
tr = pd.concat([Fd[n] for n in TR])
w1 = float(np.nansum(tr['y'] * tr['x']) / np.nansum(tr['x'] ** 2)); w2 = float(np.nansum(tr['y'] * tr['x2']) / np.nansum(tr['x2'] ** 2))
out['w_flat'] = round(w1, 3); out['w_taper'] = round(w2, 3); out['sites'] = {}
r2 = lambda e: round(float(np.sqrt(np.nanmean(e ** 2))), 3)
for n, d in Fd.items():
    out['sites'][n] = dict(events=int(d['e'].nunique()), own=r2(d['y']), full=r2(d['y'] - d['x']), flat=r2(d['y'] - w1 * d['x']), taper=r2(d['y'] - w2 * d['x2']), w_own=round(float(np.nansum(d['y'] * d['x']) / np.nansum(d['x'] ** 2)), 3))
ZONE = {'i-80': 54.0, 'I395': 63.0}
T = {}
for n in ['i-80', 'us-101', 'I395', 'ht']:
    d = M.hazard_table(n); d['v_tgt'] = d[['vF', 'vL']].mean(axis=1)
    if n in ZONE:
        d = d[d['rem'] <= ZONE[n]]
    T[n] = d
kinds = ['dist', 'dist+gapm', 'gaponly', 'time', 'lmrs', 'lmrs+dv']
def score(train, test, kind):
    Xt = np.vstack([M.features(T[s], kind)[0] for s in train]); yt = np.concatenate([T[s]['y'].values for s in train]); b = M.logit(Xt, yt)
    X, names = M.features(T[test], kind); key = T[test]['id'].values * 10 + T[test]['run'].values
    ll, p = M.nll_per_car(b, X, T[test]['y'].values, key)
    dd = T[test].assign(p=p, key=key)
    surv = dd.groupby('key')['p'].transform(lambda x: np.r_[1.0, np.cumprod(1 - x.values)[:-1]])
    w = surv * dd['p']; o = np.argsort(dd['rem'].values); cw = np.cumsum(w.values[o]); cw /= cw[-1]
    real = dd[dd['y'] == 1]['rem']
    return dict(ll=round(float(ll.mean()), 3), pred=[round(float(dd['rem'].values[o][np.searchsorted(cw, x)]), 1) for x in (.25, .5, .75)], real=[round(float(real.quantile(x)), 1) for x in (.25, .5, .75)], coef=dict(zip(['const'] + names, [round(float(x), 3) for x in b])))
out['zone'] = dict(train={}, loo={})
for k in kinds:
    out['zone']['train'][k] = {t: score(TR, t, k) for t in ('I395', 'ht')}
    out['zone']['loo'][k] = {t: score([s for s in T if s != t], t, k) for t in T}
save('replay3', out)
