"""Spec numbers on the braking side only, because the kernel's advice can only lower a speed; example events for clips; confidence intervals on the shares quoted as targets."""
import sys; sys.path.insert(0, 'research/truth/scripts/merging')
from mg_lib import *
from mg_seek import load
out = dict(w_neg={}, examples={}, ci={})
rng = np.random.default_rng(2)
def boot_share(x, n=800):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if not len(x): return None
    m = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(n)]
    return [round(float(x.mean()), 3), round(float(np.percentile(m, 2.5)), 3), round(float(np.percentile(m, 97.5)), 3), len(x)]
tr = []
for n in ['i-80', 'us-101', 'I395', 'ht', 'sim', 'simo']:
    d = load(n, 'steps'); d = d[(d['tleft'] >= 1) & d['ogap'].lt(80)].copy()
    gt = d['lead'].where(d['lead'] > 0); d['a_tgt'] = cf_target(gt.values, d['v'].values, d['vL'].values)
    d = d.dropna(subset=['a_next', 'a_cf', 'a_tgt']); d['y'] = d['a_next'] - d['a_cf']; d['x'] = np.minimum(d['a_tgt'] - d['a_cf'], 0.0); d['x_pos'] = np.maximum(d['a_tgt'] - d['a_cf'], 0.0)
    if n in ('i-80', 'us-101'): tr.append(d)
    w = float(np.sum(d['y'] * d['x']) / np.sum(d['x'] ** 2)); wp = float(np.sum(d['y'] * d['x_pos']) / np.sum(d['x_pos'] ** 2))
    out['w_neg'][n] = dict(w_neg_own=round(w, 3), w_pos_own=round(wp, 3), n=len(d), share_neg=round(float((d['x'] < -0.05).mean()), 3))
t = pd.concat(tr); wt = float(np.sum(t['y'] * t['x']) / np.sum(t['x'] ** 2)); out['w_neg']['train'] = round(wt, 3)
for n in ['i-80', 'us-101', 'I395', 'ht', 'sim', 'simo']:
    d = load(n, 'steps'); d = d[(d['tleft'] >= 1) & d['ogap'].lt(80)].copy(); gt = d['lead'].where(d['lead'] > 0); d['a_tgt'] = cf_target(gt.values, d['v'].values, d['vL'].values); d = d.dropna(subset=['a_next', 'a_cf', 'a_tgt'])
    y = d['a_next'] - d['a_cf']; x = np.minimum(d['a_tgt'] - d['a_cf'], 0.0)
    out['w_neg'][n]['rmse_follow'] = round(float(np.sqrt((y ** 2).mean())), 3); out['w_neg'][n]['rmse_train_w'] = round(float(np.sqrt(((y - wt * x) ** 2).mean())), 3)
for name, hz in (('i-80', 10), ('I395', 10), ('us-101', 10), ('ht', 5)):
    sc = pd.read_csv(EV / f'{name}.scalars.csv.gz'); z = np.load(EV / f'{name}.series.npz'); tau = z['tau']; idx = sc['e'].values.astype(int)
    lag, lead, ev, fv, dT = [z[k][idx] for k in ('lag', 'lead', 'ev', 'fv', 'edT')]
    i0 = int(np.argmin(np.abs(tau))); j5 = int(np.argmin(np.abs(tau + 5))); ja = int(np.argmin(np.abs(tau + 3))); jb = int(np.argmin(np.abs(tau - 3)))
    must = sc['must'].values == 1
    ov5 = (lag[:, j5] < 0) | (lead[:, j5] < 0)
    r = {}
    nose = np.where(must & (lag[:, ja] < -0.3) & (lag[:, i0] > 1) & (fv[:, ja] > 1))[0]
    r['nose_in'] = [dict(run=int(sc['run'].values[i]), id=int(sc['id'].values[i]), t_cross_s=round(sc['tc'].values[i] / hz, 1), lag_3s_before=round(float(lag[i, ja]), 1), lag_at_cross=round(float(lag[i, i0]), 1), v=round(float(ev[i, i0]), 1)) for i in nose[:3]]
    dec = np.where(must & (ev[:, ja] - ev[:, i0] > 1.5) & (lead[:, i0] > 2))[0]
    r['speed_match'] = [dict(run=int(sc['run'].values[i]), id=int(sc['id'].values[i]), t_cross_s=round(sc['tc'].values[i] / hz, 1), v_3s_before=round(float(ev[i, ja]), 1), v_at_cross=round(float(ev[i, i0]), 1), vL=round(float(z['vL'][idx][i, i0]), 1)) for i in dec[:3]]
    yield_ = np.where(must & (fv[:, ja] - fv[:, jb] > 2) & (lag[:, ja] > 3))[0]
    r['follower_slows'] = [dict(run=int(sc['run'].values[i]), id=int(sc['id'].values[i]), follower=int(sc['F'].values[i]), t_cross_s=round(sc['tc'].values[i] / hz, 1), f_lost=round(float(fv[i, ja] - fv[i, jb]), 1), lag_before=round(float(lag[i, ja]), 1)) for i in yield_[:3]]
    out['examples'][name] = r
    # confidence on overlap shares
    on = sc['t_on10'].values; ok = must & np.isfinite(on) & (on < -0.2)
    j = np.clip(np.round((on - tau[0]) / 0.5).astype(int), 0, len(tau) - 1)
    a = np.arange(len(sc))
    ovs = ((lag[a, j] < 0) | (lead[a, j] < 0)).astype(float)
    out['ci'][name] = dict(overlap_at_start_must=boot_share(ovs[ok]), overlap_at_label_must=boot_share((((lag[:, i0] < 0) | (lead[:, i0] < 0)).astype(float))[must]))
save('examples', out)
print(json.dumps(out)[:2600])
