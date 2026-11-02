"""Second replay: synchronisation weight by time to the lane end (a quantity the model can see), follower weight capped response, gap-centring size. Fit on I-80 and US-101, others held out."""
import sys; sys.path.insert(0, 'research/truth/scripts/merging')
from mg_lib import *
from mg_seek import load
from mg_replay_lib import follower_rows
END = {'i-80': 204.0, 'I395': 503.0, 'us-101': 408.7}
out = dict(merger={}, follower={})
TR = ['i-80', 'us-101']
def wfit(y, x):
    return float(np.nansum(y * x) / np.nansum(x * x))
def tab(d, col, edges):
    r = {}
    for lo, hi in zip(edges[:-1], edges[1:]):
        b = d[(d[col] >= lo) & (d[col] < hi)]
        if len(b) > 40:
            r[f'{lo}_{hi}'] = dict(n=len(b), w=round(wfit(b['y'].values, b['x'].values), 3))
    return r
M = {}
for n in ['i-80', 'us-101', 'I395', 'ht', 'sim', 'simo']:
    d = load(n, 'steps'); d = d[(d['tleft'] >= 1) & d['ogap'].lt(80)].copy()
    if n == 'ht':
        sc = pd.read_csv(EV / 'ht.scalars.csv.gz'); sc = sc[sc['must'] == 1][['run', 'id', 's_c', 'new']]
        d = d.merge(sc, on=['run', 'id']); pos = d['new'] == 11
        d = d[(pos & (d['s_c'] < 1000)) | (~pos & (d['s_c'] > 5400))]
        sc_ = d.groupby(['run', 'id'])['s_c'].first().values
        d['end'] = [float(np.percentile(sc_[np.abs(sc_ - x) < 400], 99)) for x in d['s_c'].values]
    elif n in ('sim', 'simo'): d['end'] = 222.0
    else: d['end'] = END[n]
    d['rem'] = (d['end'] - d['s']).clip(lower=0)
    d['tte'] = d['rem'] / d['v'].clip(lower=1)
    gt = d['lead'].where(d['lead'] > 0)
    d['a_tgt'] = cf_target(gt.values, d['v'].values, d['vL'].values)
    d = d.dropna(subset=['a_next', 'a_cf', 'a_tgt'])
    d['y'] = d['a_next'] - d['a_cf']; d['x'] = d['a_tgt'] - d['a_cf']
    M[n] = d
    out['merger'][n] = dict(by_tte=tab(d, 'tte', [0, 2, 4, 8, 15, 30, 400]), by_rem=tab(d, 'rem', [0, 10, 25, 50, 100, 200, 500]))
# one law: w = w0 + w1 * exp(-tte / 5)
tr = pd.concat([M[n] for n in TR])
E = np.exp(-tr['tte'].values / 5.0); X = np.c_[tr['x'].values, tr['x'].values * E]; b = np.linalg.lstsq(X, tr['y'].values, rcond=None)[0]
out['merger']['law'] = dict(w0=round(float(b[0]), 3), w1=round(float(b[1]), 3), tau=5.0)
for n, d in M.items():
    w = b[0] + b[1] * np.exp(-d['tte'].values / 5.0)
    out['merger'][n]['rmse'] = dict(follow=round(float(np.sqrt(np.nanmean(d['y'] ** 2))), 3), law=round(float(np.sqrt(np.nanmean((d['y'] - w * d['x']) ** 2))), 3), lmrs_min=round(float(np.sqrt(np.nanmean((d['a_next'] - np.minimum(d['a_cf'], d['a_tgt'])) ** 2))), 3))
    out['merger'][n]['n'] = len(d)
# follower: weight on the part of following the merger that asks for less than following its own leader
Fd = {}
for n in ['i-80', 'us-101', 'I395', 'I90mov', 'I294L1', 'ht']:
    d = follower_rows(n)
    own = cf_target(d['g'].where(d['g'] < 80).values, d['v'].values, d['vl'].values); d['own'] = np.where(np.isfinite(own), own, 0.5)
    d['mer'] = cf_target(np.maximum(d['lag'].values, 0.5), d['v'].values, d['ve'].values)
    d['x'] = np.minimum(d['mer'] - d['own'], 0.0); d['y'] = d['a'] - d['own']
    Fd[n] = d
    r = dict(n_ev=int(d['e'].nunique()), all=round(wfit(d['y'].values, d['x'].values), 3), share_asked=round(float((d['x'] < -0.05).mean()), 3))
    r['by_t'] = tab(d, 't', [0, 1, 2, 3, 4.5]); r['by_lag'] = tab(d, 'lag', [-5, 1, 3, 6, 10, 20, 60])
    d['cl'] = d['v'] - d['ve']; r['by_closing'] = tab(d, 'cl', [-20, -1, 1, 3, 20]); r['by_v'] = tab(d, 'v', [0, 2, 5, 10, 15, 25, 60])
    x = d['x'].values
    r['mean_x_when_asked'] = round(float(np.nanmean(x[x < -0.05])), 3)
    out['follower'][n] = r
tr = pd.concat([Fd[n] for n in TR]); wF = wfit(tr['y'].values, tr['x'].values)
out['follower']['wF_train'] = round(wF, 3)
for n, d in Fd.items():
    out['follower'][n]['rmse'] = dict(own=round(float(np.sqrt(np.nanmean(d['y'] ** 2))), 3), law=round(float(np.sqrt(np.nanmean((d['y'] - wF * d['x']) ** 2))), 3), full=round(float(np.sqrt(np.nanmean((d['y'] - d['x']) ** 2))), 3))
save('replay2', out)
