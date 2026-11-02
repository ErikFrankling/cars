"""Follower response aligned on the start of the merger's sideways motion, against matched cars with an adjacent car ahead that does not change lane.
Matched on follower speed, lag, closing speed, gap to its own leader, and what that leader does next, so a slowing leader is not read as a yield.
Usage: mg_follow.py SITE [SITE...]. Writes research/truth/merging/follow_<site>.json"""
import sys; sys.path.insert(0, 'research/truth/scripts/merging')
from mg_lib import *
ST = {'sim': 1, 'simf': 2, 'simo': 1, 'i-80': 10, 'us-101': 10, 'I395': 10, 'ht': 5, 'I90mov': 10, 'I294L1': 10}
CT = np.arange(-8, 8.01, 0.5)
TC = np.arange(-4, 6.01, 0.5)


def first_below(dT, tau, thr):
    t = np.full(dT.shape[0], np.nan)
    for i in range(dT.shape[0]):
        w = np.where(dT[i] < thr[i])[0]; w = w[tau[w] <= 5]
        if len(w):
            brk = np.where(np.diff(w) > 1)[0]
            t[i] = tau[w[brk[-1] + 1]] if len(brk) else tau[w[0]]
    return t


def at(a, tau, t):
    j = np.clip(np.round((t - tau[0]) / 0.5).astype(int), 0, a.shape[1] - 1)
    return a[np.arange(a.shape[0]), j]


def cell(v, lag, dv, g, ld):
    return (np.digitize(v, [2, 5, 10, 15, 25]) * 10000 + np.digitize(lag, [0, 2, 5, 10, 20]) * 1000 + np.digitize(dv, [-1, 1]) * 100 + np.digitize(g, [8, 20, 50]) * 10 + np.digitize(ld, [-1, 1])).astype('i4')


def cell_coarse(v, lag, dv, g, ld):
    return (np.digitize(v, [5, 15, 25]) * 10000 + np.digitize(lag, [0, 5, 20]) * 1000 + np.digitize(dv, [0]) * 100 + np.digitize(g, [15, 50]) * 10 + np.digitize(ld, [-1, 1])).astype('i4')


def run(name):
    sc = pd.read_csv(EV / f'{name}.scalars.csv.gz'); z = np.load(EV / f'{name}.series.npz'); tau = z['tau']
    idx = sc['e'].values.astype(int); S = {k: z[k][idx] for k in z.files if k != 'tau'}
    W = sc['W'].values
    t_touch = first_below(S['edT'], tau, np.full(len(sc), 2.65)); t_label = np.zeros(len(sc))
    t_on = sc['t_on10'].values.astype(float); t_on = np.where(t_on < -0.2, t_on, np.nan)
    ct = pd.read_csv(EV / f'{name}.controls.csv.gz')
    g = lambda p: ct[[f'{p}{j}' for j in range(len(CT))]].values
    aC, vC, sC, sLc, vLc = g('af'), g('vf'), g('sf'), g('sl'), g('vl')
    j0 = int(np.argmin(np.abs(CT))); jm1 = int(np.argmin(np.abs(CT + 1))); j4 = int(np.argmin(np.abs(CT - 4)))
    gC = (sLc - ct['Ll'].values[:, None] - sC)[:, j0]
    ldC = vLc[:, j4] - vLc[:, jm1]
    keys = (cell(vC[:, j0], ct['lag0'].values, vC[:, j0] - ct[f'va{j0}'].values, np.nan_to_num(gC, nan=99), np.nan_to_num(ldC)),
            cell_coarse(vC[:, j0], ct['lag0'].values, vC[:, j0] - ct[f'va{j0}'].values, np.nan_to_num(gC, nan=99), np.nan_to_num(ldC)))
    book = [{int(c): np.where(k == c)[0] for c in np.unique(k)} for k in keys]
    cidx = np.array([int(np.argmin(np.abs(CT - t))) for t in TC])
    dropC = vC[:, jm1] - vC[:, j4]
    gapC4 = None

    def study(align, mask, tag):
        rows = []; drops = []; hit = []; meta = []
        ids = np.where(mask & np.isfinite(align))[0]
        v0 = at(S['fv'], tau, np.nan_to_num(align)); lag0 = at(S['lag'], tau, np.nan_to_num(align)); ev0 = at(S['ev'], tau, np.nan_to_num(align))
        g0 = at(np.where(S['fgap'] < 200, S['fgap'], np.nan), tau, np.nan_to_num(align))
        vlA = at(S['fvl'], tau, np.nan_to_num(align) - 1); vlB = at(S['fvl'], tau, np.nan_to_num(align) + 4)
        idF0 = at(S['idF'], tau, np.nan_to_num(align))
        for i in ids:
            if idF0[i] != sc['F'].values[i]: continue
            w = (tau >= align[i] - 2) & (tau <= min(align[i] + 4, 8))
            if not np.all(S['fla'][i, w] == sc['new'].values[i]): continue
            ld = (vlB[i] - vlA[i]) if np.isfinite(vlA[i]) and np.isfinite(vlB[i]) else 0.0
            gi = g0[i] if np.isfinite(g0[i]) else 99.0
            c1 = int(cell(np.array([v0[i]]), np.array([lag0[i]]), np.array([v0[i] - ev0[i]]), np.array([gi]), np.array([ld]))[0])
            cc = book[0].get(c1)
            if cc is None or len(cc) < 10:
                c2 = int(cell_coarse(np.array([v0[i]]), np.array([lag0[i]]), np.array([v0[i] - ev0[i]]), np.array([gi]), np.array([ld]))[0])
                cc = book[1].get(c2)
                if cc is None or len(cc) < 10: continue
            a_i = np.interp(align[i] + TC, tau, S['fa'][i], left=np.nan, right=np.nan)
            a_i = np.where(align[i] + TC > 8, np.nan, a_i)
            rows.append(a_i - np.nanmean(aC[cc][:, cidx], axis=0))
            vv = np.interp(align[i] + np.array([-1.0, 4.0]), tau, S['fv'][i])
            d = vv[0] - vv[1]; dc = dropC[cc]; dc = dc[np.isfinite(dc)]
            if not len(dc) or not np.isfinite(d):
                rows.pop(); continue
            drops.append(d - dc.mean()); hit.append(d > np.percentile(dc, 80))
            meta.append((v0[i], lag0[i], v0[i] - ev0[i], d))
        rows = np.array(rows)
        if len(rows) < 15: return dict(n=len(rows))
        mean = np.nanmean(rows, axis=0); se = np.nanstd(rows, axis=0) / np.sqrt(np.sum(np.isfinite(rows), axis=0))
        pre = np.nanmean(rows[:, (TC >= -3) & (TC < -0.5)], axis=1); post = np.nanmean(rows[:, (TC >= 0) & (TC <= 3)], axis=1); late = np.nanmean(rows[:, (TC > 3) & (TC <= 6)], axis=1)
        m1 = boot_mean(drops, 600); m2 = boot_mean(pre, 600); m3 = boot_mean(post, 600); m4 = boot_mean(late, 600)
        hb = np.array(hit, float); rng = np.random.default_rng(1)
        hbb = [hb[rng.integers(0, len(hb), len(hb))].mean() for _ in range(600)]
        # first time the curve is below zero by 2 SE and stays there for 1 s
        on = None
        below = mean + 2 * se < 0
        for k in range(len(TC) - 2):
            if below[k] and below[k + 1] and below[k + 2]:
                on = float(TC[k]); break
        return dict(n=len(rows), excess_a=[round(float(x), 3) for x in mean], se=[round(float(x), 3) for x in se], onset=on, lost_excess=[round(x, 3) for x in m1], responders_vs_20=[round(float(hb.mean()) - .2, 3), round(float(np.percentile(hbb, 2.5)) - .2, 3), round(float(np.percentile(hbb, 97.5)) - .2, 3)], pre=[round(x, 3) for x in m2], post=[round(x, 3) for x in m3], late=[round(x, 3) for x in m4])

    must = sc['must'].values == 1
    if name == 'ht':
        pos = sc['new'].values == 11
        must &= (pos & (sc['s_c'].values < 1000)) | (~pos & (sc['s_c'].values > 5400))
    other = sc['must'].values == 0
    out = dict(site=name, tau=[float(x) for x in TC], control_n=len(ct))
    for tag, al in (('touch', t_touch), ('onset', t_on), ('label', t_label)):
        r = dict(all=study(al, np.ones(len(sc), bool), 'all'), must=study(al, must, 'must'), other=study(al, other, 'other'))
        lag_at = at(S['lag'], tau, np.nan_to_num(al)); v_at = at(S['fv'], tau, np.nan_to_num(al)); dv_at = v_at - at(S['ev'], tau, np.nan_to_num(al))
        for lo, hi in ((-30, 0), (0, 2), (2, 5), (5, 10), (10, 20), (20, 200)):
            r[f'lag{lo}_{hi}'] = study(al, (lag_at >= lo) & (lag_at < hi), '')
        for lo, hi in ((0, 2), (2, 5), (5, 10), (10, 15), (15, 25), (25, 60)):
            r[f'v{lo}_{hi}'] = study(al, (v_at >= lo) & (v_at < hi), '')
        r['closing_pos'] = study(al, dv_at > 1, ''); r['closing_neg'] = study(al, dv_at < -1, ''); r['closing_flat'] = study(al, np.abs(dv_at) <= 1, '')
        out[tag] = r
    # how a gap appears when the car started sideways with no room: lag under 1 m at first touch
    tt = np.nan_to_num(t_touch)
    lag_t = at(S['lag'], tau, tt); lead_t = at(S['lead'], tau, tt)
    same = at(S['idF'], tau, tt) == sc['F'].values
    fin = np.isfinite(t_touch) & same
    def room(m, tag):
        m = m & fin
        if m.sum() < 15: return dict(n=int(m.sum()))
        dur = -tt[m]
        lag0 = S['lag'][:, int(np.argmin(np.abs(tau)))][m]
        vE = at(S['ev'], tau, tt)[m]; vF = at(S['fv'], tau, tt)[m]
        vE1 = S['ev'][:, int(np.argmin(np.abs(tau)))][m]; vF1 = S['fv'][:, int(np.argmin(np.abs(tau)))][m]
        return dict(n=int(m.sum()), lag_touch=q(lag_t[m]), lag_label=q(lag0), dur=q(dur), ego_dv=q(vE1 - vE), fol_dv=q(vF1 - vF), fol_slows_share=float(np.mean((vF1 - vF) < -0.3)), ego_speeds_share=float(np.mean((vE1 - vE) > 0.3)), closing_touch=q(vF - vE), closing_label=q(vF1 - vE1))
    out['no_room_at_touch'] = dict(lag_under_1=room(lag_t < 1, ''), lag_1_to_5=room((lag_t >= 1) & (lag_t < 5), ''), lag_over_5=room(lag_t >= 5, ''))
    save(f'follow_{name}', out)


for s in sys.argv[1:]: run(s)
