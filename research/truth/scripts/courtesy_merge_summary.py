"""Yield probability per target-lane vehicle, gap acceptance hazard, waits and passes for the must-change cohorts. Writes courtesy/merge_summary.json."""
import sys; sys.path.insert(0, 'research/truth/scripts')
from courtesy_lib import *

SITES = ['us-101', 'i-80', 'ht', 'lankershim', 'peachtree']
out = {}
Ms, Es, Ss = {}, {}, {}
for s in SITES:
    Ms[s] = pd.read_csv(OUT / f'merge_cars_{s}.csv.gz'); Es[s] = pd.read_csv(OUT / f'merge_episodes_{s}.csv.gz'); Ss[s] = pd.read_csv(OUT / f'merge_steps_{s}.csv.gz')
    # A39 on-ramp only: a car labelled aux for minutes is a lane-label drift, not a merge
for s in ('ht',):
    keep = Ms[s][(Ms[s]['s_c'] < 500) & (Ms[s]['wait'] < 60)][['run', 'id']]
    Ms[s] = Ms[s].merge(keep, on=['run', 'id']); Es[s] = Es[s].merge(keep, on=['run', 'id']); Ss[s] = Ss[s].merge(keep, on=['run', 'id'])

VB = [0, 2, 5, 10, 15, 20, 40]
for s in SITES:
    M, E, S = Ms[s], Es[s], Ss[s]
    o = dict(cars=int(len(M)), wait=q(M['wait'], (10, 25, 50, 75, 90, 95, 99)), wait_max=float(M['wait'].max()), passes=M['passes'].value_counts().sort_index().to_dict(), passes_mean=round(float(M['passes'].mean()), 3),
             v_cross=q(M['v_c'], (5, 25, 50, 75, 95)), rem_cross=q(M['rem_c'], (5, 25, 50, 75, 95)), outcomes=E['outcome'].value_counts().to_dict())
    r = E[E['outcome'].isin(['letin', 'passed'])].copy(); r['y'] = (r['outcome'] == 'letin').astype(float)
    o['p_letin_per_resolved_vehicle'] = round(float(r['y'].mean()), 3)
    tab = {}
    vcol = r['vT0'].values
    for i in range(len(VB) - 1):
        m = (vcol >= VB[i]) & (vcol < VB[i + 1])
        if m.sum() >= 10: tab[f'{VB[i]}-{VB[i+1]}'] = dict(n=int(m.sum()), p=round(float(r['y'].values[m].mean()), 3))
    o['p_letin_by_T_speed'] = tab
    dv = (r['vT0'] - r['vM0']).values; tab = {}
    for a, b in [(-50, -3), (-3, -1), (-1, 1), (1, 3), (3, 50)]:
        m = (dv >= a) & (dv < b)
        if m.sum() >= 10: tab[f'{a}..{b}'] = dict(n=int(m.sum()), p=round(float(r['y'].values[m].mean()), 3))
    o['p_letin_by_closing'] = tab
    lag = r['lag0'].values; tab = {}
    for a, b in [(-50, 0), (0, 3), (3, 6), (6, 12), (12, 25), (25, 500)]:
        m = (lag >= a) & (lag < b)
        if m.sum() >= 10: tab[f'{a}..{b}'] = dict(n=int(m.sum()), p=round(float(r['y'].values[m].mean()), 3))
    o['p_letin_by_lag0'] = tab
    w = r['wait0'].values; tab = {}
    for a, b in [(0, 5), (5, 10), (10, 20), (20, 40), (40, 500)]:
        m = (w >= a) & (w < b)
        if m.sum() >= 10: tab[f'{a}-{b}'] = dict(n=int(m.sum()), p=round(float(r['y'].values[m].mean()), 3))
    o['p_letin_by_wait'] = tab
    if s in ('i-80', 'us-101', 'ht') and r['y'].min() == 0 and len(r) > 60:
        d = r[['vT0', 'vM0', 'lag0', 'wait0', 'rem0', 'y', 'id']].dropna(); d = d[d['lag0'].between(-30, 120)]
        X = np.c_[d['vT0'] / 10, (d['vT0'] - d['vM0']) / 3, d['lag0'] / 10, d['wait0'] / 10, d['rem0'] / 50]
        o['logit_letin'] = dict(n=int(len(d)), coef=logit_boot(X, d['y'].values, d['id'].values, ['vT_per10', 'closing_per3', 'lag_per10m', 'wait_per10s', 'rem_per50m']))
    # discrete-time hazard of starting the change, 1 Hz. The state 3 s before the crossing is the decision, later rows are the manoeuvre itself.
    z = S[(np.abs((S['tleft'] * 2) % 2) < 1e-6) & (S['tleft'] >= 3)].copy()
    z['y'] = (np.abs(z['tleft'] - 3) < 1e-6).astype(float)
    z = z.dropna(subset=['lag', 'lead', 'vT', 'vL'])
    z = z[z['lag'].between(-30, 150) & z['lead'].between(-30, 150)]
    if len(z) > 200 and z['y'].sum() > 30:
        X = np.c_[np.minimum(z['lag'], 40) / 10, np.minimum(z['lead'], 40) / 10, (z['vT'] - z['vM']) / 3, (z['vM'] - z['vL']) / 3, z['wait'] / 10, np.nan_to_num(z['rem'].values, nan=0.0) / 50, z['vM'] / 10]
        names = ['lag_per10m', 'lead_per10m', 'lag_closing_per3', 'lead_closing_per3', 'wait_per10s', 'rem_per50m', 'v_per10']
        if s in ('lankershim', 'peachtree'): X = X[:, [0, 1, 2, 3, 4, 6]]; names = [n for n in names if n != 'rem_per50m']
        o['logit_start_change'] = dict(n=int(len(z)), events=int(z['y'].sum()), coef=logit_boot(X, z['y'].values, z['id'].values, names))
        acc = z[z['y'] == 1]; rej = z[z['y'] == 0]
        o['accepted_lag'] = q(acc['lag'], (1, 5, 25, 50, 75, 95)); o['accepted_lead'] = q(acc['lead'], (1, 5, 25, 50, 75, 95)); o['rejected_lag'] = q(rej['lag'], (5, 25, 50, 75, 95)); o['rejected_lead'] = q(rej['lead'], (5, 25, 50, 75, 95))
        acc2 = acc.assign(lagT=acc['lag'] / acc['vT'].clip(lower=.5), leadT=acc['lead'] / acc['vM'].clip(lower=.5))
        rej2 = rej.assign(lagT=rej['lag'] / rej['vT'].clip(lower=.5), leadT=rej['lead'] / rej['vM'].clip(lower=.5))
        o['accepted_lag_s'] = q(acc2['lagT'], (5, 25, 50, 75, 95)); o['accepted_lead_s'] = q(acc2['leadT'], (5, 25, 50, 75, 95)); o['rejected_lag_s'] = q(rej2['lagT'], (5, 25, 50, 75, 95))
        # accepted lag gap by remaining distance and by wait
        tab = {}
        for a, b in [(0, 40), (40, 80), (80, 160), (160, 1000)]:
            m = acc[acc['rem'].between(a, b)]
            if len(m) >= 10: tab[f'{a}-{b}'] = dict(n=int(len(m)), lag=q(m['lag'], (5, 25, 50)), lead=q(m['lead'], (5, 25, 50)), v=round(float(m['vM'].mean()), 2))
        o['accepted_by_rem'] = tab
        tab = {}
        for a, b in [(0, 5), (5, 15), (15, 30), (30, 500)]:
            m = acc[acc['wait'].between(a, b)]
            if len(m) >= 10: tab[f'{a}-{b}'] = dict(n=int(len(m)), lag=q(m['lag'], (5, 25, 50)), lead=q(m['lead'], (5, 25, 50)), v=round(float(m['vM'].mean()), 2))
        o['accepted_by_wait'] = tab
        # hazard per second by elapsed wait (Kaplan-Meier style, on the whole cohort)
        tab = {}
        for a, b in [(0, 5), (5, 10), (10, 20), (20, 30), (30, 45), (45, 500)]:
            m = z[z['wait'].between(a, b - 1e-6)]
            if len(m) >= 30: tab[f'{a}-{b}'] = dict(n=int(len(m)), h=round(float(m['y'].mean()), 4))
        o['hazard_by_wait'] = tab
        o['stopped_before_change'] = round(float(S.groupby('id')['vM'].min().lt(1.0).mean()), 3)
    out[s] = o

# roundabout entries (Zenodo 15077435), from opus_roundabout's decision table: Troutbeck maximum likelihood by waiting class
from scipy.optimize import minimize
from scipy.stats import norm
R = pd.read_csv(T / 'opus-20261031-cache' / 'roundabout_decisions.csv')
R = R[R['acc'].notna() & (R['acc'] > 0)].copy()
def troutbeck(acc, rej):
    acc, rej = np.maximum(acc, .05), np.maximum(rej, .01)
    def nll(p):
        mu, ls = p; sd = np.exp(ls)
        f = norm.cdf((np.log(acc) - mu) / sd) - norm.cdf((np.log(rej) - mu) / sd)
        return -np.sum(np.log(np.maximum(f, 1e-9)))
    r = minimize(nll, [np.log(4.0), np.log(.4)], method='Nelder-Mead')
    mu, sd = r.x[0], np.exp(r.x[1])
    return dict(mean=round(float(np.exp(mu + sd * sd / 2)), 2), median=round(float(np.exp(mu)), 2), sd_log=round(float(sd), 3))
K = R[R['acc'] > R['rmax']]
rb = dict(rows=int(len(R)), used=int(len(K)), wait=q(R['wait'], (50, 90, 99)), all=troutbeck(K['acc'].values, K['rmax'].values), by_wait={}, by_rejections={})
for a, b in [(0, 5), (5, 10), (10, 20), (20, 40), (40, 1e4)]:
    m = K[K['wait'].between(a, b - 1e-6)]
    if len(m) > 25:
        rng = np.random.default_rng(1); bs = []
        for _ in range(60):
            i = rng.integers(0, len(m), len(m)); bs.append(troutbeck(m['acc'].values[i], m['rmax'].values[i])['median'])
        rb['by_wait'][f'{a}-{b}'] = dict(n=int(len(m)), **troutbeck(m['acc'].values, m['rmax'].values), ci=[round(float(np.percentile(bs, 2.5)), 2), round(float(np.percentile(bs, 97.5)), 2)], acc_p05=round(float(np.percentile(m['acc'], 5)), 2), acc_p50=round(float(np.percentile(m['acc'], 50)), 2))
for a, b in [(0, 1), (1, 2), (2, 4), (4, 8), (8, 1e4)]:
    m = K[K['nrej'].between(a, b - 1e-6)]
    if len(m) > 25: rb['by_rejections'][f'{a}-{b}'] = dict(n=int(len(m)), **troutbeck(m['acc'].values, m['rmax'].values), acc_p50=round(float(np.percentile(m['acc'], 50)), 2))
out['roundabout'] = rb
save('merge_summary', out)
for s in SITES + ['roundabout']:
    print(s, json.dumps(out[s])[:3400], '\n', flush=True)
