"""Open-loop tests of the candidate formulas on observed states. Fit on I-80 and US-101, score on held-out sites.
A. Merger before it moves sideways: plain following, plus a weight on following the target-lane leader, LMRS's min form.
B. Follower: plain following of its own leader, or min(own leader, merger as leader at a shortened headway) with a share p of drivers responding, from first body over the line.
C. Parallel measures in the last stretch of lane, for a like-for-like comparison with the simulator.
Writes research/truth/merging/replay.json"""
import sys; sys.path.insert(0, 'research/truth/scripts/merging')
from mg_lib import *
from mg_seek import load
HZ = {'sim': 1, 'simo': 1, 'simf': 2, 'i-80': 10, 'us-101': 10, 'I395': 10, 'ht': 5, 'I90mov': 10, 'I294L1': 10}
TRAIN = ['i-80', 'us-101']; HOLD = ['I395', 'ht']; out = {}


def rmse(x): return float(np.sqrt(np.nanmean(x ** 2)))


def merger(name):
    d = load(name, 'steps')
    d = d[(d['tleft'] >= 1) & d['ogap'].lt(80)].copy()
    gt = d['lead'].where(d['lead'] > 0)
    d['a_tgt'] = cf_target(gt.values, d['v'].values, d['vL'].values)
    d = d.dropna(subset=['a_next', 'a_cf'])
    d['has'] = d['a_tgt'].notna()
    return d


M = {n: merger(n) for n in TRAIN + HOLD + ['sim', 'simo']}
tr = pd.concat([M[n][M[n]['has']] for n in TRAIN])
# weight on the difference, by the site mix of the train set
w = float(np.sum((tr['a_next'] - tr['a_cf']) * (tr['a_tgt'] - tr['a_cf'])) / np.sum((tr['a_tgt'] - tr['a_cf']) ** 2))
out['merger'] = dict(w_train=round(w, 3), sites={})
for n, d in M.items():
    h = d[d['has']]
    base = rmse(h['a_next'] - h['a_cf'])
    wfit = rmse(h['a_next'] - (h['a_cf'] + w * (h['a_tgt'] - h['a_cf'])))
    lm = rmse(h['a_next'] - np.minimum(h['a_cf'], h['a_tgt']))
    # weight rising with time pressure: stays on the same fit form, fit on train set in bins
    rows = {}
    for lo, hi in ((0, 3), (3, 6), (6, 12), (12, 25), (25, 400)):
        tte = (h['tleft'])
        b = h[(tte >= lo) & (tte < hi)]
        if len(b) > 50:
            rows[f'tleft_{lo}_{hi}'] = dict(n=len(b), w=round(float(np.sum((b['a_next'] - b['a_cf']) * (b['a_tgt'] - b['a_cf'])) / np.sum((b['a_tgt'] - b['a_cf']) ** 2)), 3))
    out['merger']['sites'][n] = dict(n=len(h), rmse_follow=round(base, 3), rmse_w=round(wfit, 3), rmse_lmrs_min=round(lm, 3), w_by_time_left=rows, target_leader_lower_share=round(float((h['a_tgt'] < h['a_cf']).mean()), 3))
# site own best weight
for n, d in M.items():
    h = d[d['has']]
    out['merger']['sites'][n]['w_own'] = round(float(np.sum((h['a_next'] - h['a_cf']) * (h['a_tgt'] - h['a_cf'])) / np.sum((h['a_tgt'] - h['a_cf']) ** 2)), 3)


def follower_rows(name):
    sc = pd.read_csv(EV / f'{name}.scalars.csv.gz'); z = np.load(EV / f'{name}.series.npz'); tau = z['tau']
    idx = sc['e'].values.astype(int); S = {k: z[k][idx] for k in ('edT', 'lag', 'fa', 'fv', 'fgap', 'fvl', 'ev', 'idF', 'fla')}
    rows = []
    for i in range(len(sc)):
        w = np.where(S['edT'][i] < 2.65)[0]; w = w[tau[w] <= 5]
        if not len(w): continue
        brk = np.where(np.diff(w) > 1)[0]; j0 = w[brk[-1] + 1] if len(brk) else w[0]
        if not (S['idF'][i, j0] == sc['F'].values[i]): continue
        for j in range(j0, min(j0 + 9, len(tau) - 2)):
            if S['fla'][i, j] != sc['new'].values[i]: continue
            rows.append((i, tau[j] - tau[j0], S['fa'][i, j + 2], S['lag'][i, j], S['fv'][i, j], S['ev'][i, j], S['fgap'][i, j], S['fvl'][i, j]))
    d = pd.DataFrame(rows, columns=['e', 't', 'a', 'lag', 'v', 've', 'g', 'vl']).dropna(subset=['a', 'v', 've', 'lag'])
    return d


F = {n: follower_rows(n) for n in ['i-80', 'us-101', 'I395', 'I90mov', 'I294L1', 'ht']}


def mixfit(d, T, sigma=0.5, it=30):
    own = cf_target(d['g'].where(d['g'] < 80).values, d['v'].values, d['vl'].values)
    own = np.where(np.isfinite(own), own, 0.5)
    mer = cf_target(np.maximum(d['lag'].values, 0.5), d['v'].values, d['ve'].values, T=T)
    resp = np.minimum(own, mer)
    a = d['a'].values
    l0 = -0.5 * ((a - own) / sigma) ** 2; l1 = -0.5 * ((a - resp) / sigma) ** 2
    ev = d['e'].values; u, inv = np.unique(ev, return_inverse=True)
    L0 = np.bincount(inv, np.nan_to_num(l0)); L1 = np.bincount(inv, np.nan_to_num(l1))
    p = 0.5
    for _ in range(it):
        r = p / (p + (1 - p) * np.exp(np.clip(L0 - L1, -50, 50)))
        p = float(r.mean())
    ll = np.log(p * np.exp(np.clip(L1 - L0, -50, 50)) + (1 - p)).sum() + L0.sum()
    return dict(p=round(p, 3), ll_per_event=round(float(ll / len(u)), 3), rmse_own=round(rmse(a - own), 3), rmse_resp=round(rmse(a - resp), 3))


out['follower'] = {}
for n, d in F.items():
    out['follower'][n] = {f'T{t}': mixfit(d, t) for t in (0.3, 0.5, 0.7, 1.0, 1.3)}
    bins = {}
    for vlo, vhi in ((0, 5), (5, 10), (10, 15), (15, 25), (25, 60)):
        b = d[(d['v'] >= vlo) & (d['v'] < vhi)]
        if b['e'].nunique() > 30: bins[f'v{vlo}_{vhi}'] = mixfit(b, 0.7)
    for lo, hi in ((-5, 1), (1, 5), (5, 10), (10, 20), (20, 60)):
        b = d[(d['lag'] >= lo) & (d['lag'] < hi)]
        if b['e'].nunique() > 30: bins[f'lag{lo}_{hi}'] = mixfit(b, 0.7)
    d2 = d.assign(cl=d['v'] - d['ve'])
    for lo, hi, tag in ((-20, -1, 'open'), (-1, 1, 'flat'), (1, 20, 'close')):
        b = d2[(d2['cl'] >= lo) & (d2['cl'] < hi)]
        if b['e'].nunique() > 30: bins[f'closing_{tag}'] = mixfit(b, 0.7)
    out['follower'][n]['by'] = bins

# C: parallel with cars in the last stretch of lane
cmp = {}
for n, end, stretch in (('i-80', 204.0, 110.0), ('I395', 503.0, 110.0), ('sim', 222.0, 110.0), ('simo', 222.0, 110.0)):
    ep = pd.read_csv(EV / f'{n}.episodes.csv.gz'); ep = ep[ep['group'] == 'must']
    ep = ep[ep['s0'] >= end - stretch]
    ep['dur'] = (ep['t1'] - ep['t0']) / HZ[n] + (1 / HZ[n] if HZ[n] < 2 else 0.5)
    ep['mdv'] = ep['sdv'] / ep['n']
    cars = ep.groupby(['run', 'id'])['dur'].max()
    cmp[n] = dict(n_ep=len(ep), dur=q(ep['dur'], (50, 90, 95)), share_ge5=round(float((ep['dur'] >= 5).mean()), 3), share_ge10=round(float((ep['dur'] >= 10).mean()), 3), locked3=round(float(((ep['dur'] >= 3) & (ep['mdv'] < .5)).mean()), 3), car_longest=q(cars, (50, 90)), mdv=q(ep['mdv'], (50,)))
out['parallel_last_110m'] = cmp
save('replay', out)
