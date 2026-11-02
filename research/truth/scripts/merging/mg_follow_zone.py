"""Must-change followers at the lane end against controls drawn from the same stretch of road, because traffic accelerates through it."""
import sys; sys.path.insert(0, 'research/truth/scripts/merging')
from mg_lib import *
CT = np.arange(-8, 8.01, 0.5); j0 = int(np.argmin(np.abs(CT))); jm1 = int(np.argmin(np.abs(CT + 1))); j4 = int(np.argmin(np.abs(CT - 4)))
TC = np.arange(-4, 6.01, 0.5); cidx = np.array([int(np.argmin(np.abs(CT - t))) for t in TC])
ZONE = {'I395': (-3, 400, 540), 'i-80': (6, 120, 240), 'us-101': (5, 210, 420)}
res = {}
for name, (lane, lo, hi) in ZONE.items():
    sc = pd.read_csv(EV / f'{name}.scalars.csv.gz'); sc = sc[sc['must'] == 1]; z = np.load(EV / f'{name}.series.npz'); tau = z['tau']
    S = {k: z[k][sc['e'].values.astype(int)] for k in ('edT', 'lag', 'fa', 'fv', 'fgap', 'fvl', 'ev', 'idF', 'fla')}
    ct = pd.read_csv(EV / f'{name}.controls.csv.gz')
    ct = ct[(ct[f'sf{j0}'] >= lo) & (ct[f'sf{j0}'] <= hi) & (ct['lane'].abs() == abs(lane))]
    g = lambda p: ct[[f'{p}{j}' for j in range(len(CT))]].values
    aC, vC, sC, sL, vL = g('af'), g('vf'), g('sf'), g('sl'), g('vl')
    key = lambda v, cl, l: (np.digitize(v, [3, 6, 10, 15]) * 100 + np.digitize(cl, [-1, 1]) * 10 + np.digitize(l, [2, 10]))
    kc = key(vC[:, j0], vC[:, j0] - ct[f'va{j0}'].values, ct['lag0'].values)
    rows, drops, hits, n_ = [], [], [], 0
    for i in range(len(sc)):
        w = np.where(S['edT'][i] < 2.65)[0]; w = w[tau[w] <= 5]
        if not len(w): continue
        b = np.where(np.diff(w) > 1)[0]; t0 = tau[w[b[-1] + 1]] if len(b) else tau[w[0]]; j = int(np.argmin(np.abs(tau - t0)))
        if S['idF'][i, j] != sc['F'].values[i]: continue
        cc = np.where(kc == key(np.array([S['fv'][i, j]]), np.array([S['fv'][i, j] - S['ev'][i, j]]), np.array([S['lag'][i, j]]))[0])[0]
        if len(cc) < 10: continue
        ai = np.interp(t0 + TC, tau, S['fa'][i], left=np.nan, right=np.nan)
        rows.append(ai - np.nanmean(aC[cc][:, cidx], axis=0))
        vv = np.interp(t0 + np.array([-1.0, 4.0]), tau, S['fv'][i]); d = vv[0] - vv[1]; dc = vC[cc, jm1] - vC[cc, j4]; dc = dc[np.isfinite(dc)]
        if len(dc) and np.isfinite(d): drops.append(d - dc.mean()); hits.append(d > np.percentile(dc, 80))
    print(name, 'controls in zone', len(ct), 'matched', len(rows), flush=True)
    if not len(rows): continue
    rows = np.array(rows)
    pre = np.nanmean(rows[:, (TC >= -3) & (TC < -.5)], axis=1); post = np.nanmean(rows[:, (TC >= 0) & (TC <= 3)], axis=1)
    res[name] = dict(n=len(rows), controls=len(ct), lost=[round(x, 3) for x in boot_mean(drops, 500)], responders_vs_20=round(float(np.mean(hits)) - .2, 3), pre=[round(x, 3) for x in boot_mean(pre, 500)], post=[round(x, 3) for x in boot_mean(post, 500)], curve=[round(float(x), 3) for x in np.nanmean(rows, axis=0)])
save('follow_zone', res)
print(json.dumps(res)[:1500])
