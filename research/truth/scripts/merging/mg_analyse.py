"""Merging measurements on the events from mg_events.py. Usage: mg_analyse.py SITE [SITE...]. Writes research/truth/merging/<site>.json."""
import sys; sys.path.insert(0, 'research/truth/scripts/merging')
from mg_lib import *

ST = {'sim': 1, 'simf': 2, 'simo': 1, 'i-80': 10, 'us-101': 10, 'I395': 10, 'ht': 5, 'I90mov': 10, 'I294L1': 10}
CT = np.arange(-8, 8.01, 0.5)


def at(arr, tau, t):
    """Values of a 2D series (events x tau) at per-event times t (nearest grid point)."""
    j = np.clip(np.round((t - tau[0]) / 0.5).astype(int), 0, arr.shape[1] - 1)
    return arr[np.arange(arr.shape[0]), j]


def cell(v, lag, dv, g):
    return (np.digitize(v, [5, 10, 15, 25]) * 1000 + np.digitize(lag, [0, 2, 5, 10, 20]) * 100 + np.digitize(dv, [-1, 1]) * 10 + np.digitize(g, [8, 20, 50])).astype('i4')


def qq(x, ps=(5, 25, 50, 75, 95)):
    return q(x, ps)


def analyse(name):
    sc = pd.read_csv(EV / f'{name}.scalars.csv.gz')
    z = np.load(EV / f'{name}.series.npz'); tau = z['tau']
    S = {k: z[k] for k in z.files if k != 'tau'}
    n = len(sc); assert n == S['ev'].shape[0] or True
    idx = sc['e'].values.astype(int)
    S = {k: v[idx] for k, v in S.items()}
    hz = ST[name]; out = dict(site=name, events=len(sc), must=int(sc['must'].sum()))
    must = sc['must'].values == 1
    # --- lane end position ---
    send = np.full(len(sc), np.nan)
    keepm = must.copy()
    if name == 'ht':
        pos = sc['new'].values == 11
        keepm &= (pos & (sc['s_c'].values < 1000)) | (~pos & (sc['s_c'].values > 5400))
        for flag in (True, False):
            m = keepm & (pos == flag)
            for i in np.where(m)[0]:
                near = sc['s_c'].values[m]; near = near[np.abs(near - sc['s_c'].values[i]) < 400]
                send[i] = np.percentile(near, 99)
    elif must.any():
        send[must] = {'i-80': 204.0, 'I395': 503.0}.get(name, np.percentile(sc['s_c'].values[must], 99.5))
    first_ok = np.ones(len(sc), bool)
    out['s_end'] = float(np.nanmedian(send)) if must.any() else None
    W = sc['W'].values
    i0 = int(np.argmin(np.abs(tau)))
    # first time centre over the line and first time body over the line, from the absolute distance to the target-lane centre
    dT = S['edT']; es = S['es']; ev = S['ev']
    def first_below(thr):
        t = np.full(len(sc), np.nan)
        for i in range(len(sc)):
            w = np.where(dT[i] < thr[i])[0]
            # the first entry of the last stretch below the threshold before 5 s after the crossing
            w = w[tau[w] <= 5]
            if len(w):
                brk = np.where(np.diff(w) > 1)[0]
                t[i] = tau[w[brk[-1] + 1]] if len(brk) else tau[w[0]]
        return t
    t_geo = first_below(np.full(len(sc), 1.75)); t_touch = first_below(np.full(len(sc), 2.65))
    t_on = sc['t_on10'].values.copy()
    t_on[~np.isfinite(t_on)] = np.nan
    ton_i = np.where(np.isfinite(t_on), t_on, 0.0)
    s_on = at(es, tau, ton_i); s_geo = at(es, tau, np.nan_to_num(t_geo)); s_tch = at(es, tau, np.nan_to_num(t_touch))
    if keepm.any():
        loc = {}
        m = keepm
        loc['n'] = int(m.sum())
        loc['rem_label'] = qq(send[m] - sc['s_c'].values[m])
        loc['rem_centre_over_line'] = qq((send - s_geo)[m & np.isfinite(t_geo)])
        loc['rem_body_touches_line'] = qq((send - s_tch)[m & np.isfinite(t_touch)])
        loc['rem_lateral_start'] = qq((send - s_on)[m & np.isfinite(t_on)])
        loc['tau_on_before_label'] = qq(-t_on[m])
        loc['tau_centre_vs_label'] = qq(t_geo[m])
        loc['v_at_label'] = qq(ev[m, i0])
        loc['wait_in_lane'] = qq(sc['wait'].values[m])
        loc['W'] = qq(W[m])
        # stop before merging
        mv = np.nanmin(np.where(tau[None, :] <= 0, ev[m], np.nan), axis=1)
        loc['stopped_below_1'] = float(np.mean(mv < 1.0))
        out['location'] = loc
        f = EV / f'{name}.flows.csv.gz'
        if f.exists():
            fl = pd.read_csv(f); fl = fl[fl['lane'] == 'tgt']
            b = (sc['tc'].values / hz / 300).astype(int)
            key = pd.DataFrame(dict(run=sc['run'].values, bin=b, new=sc['new'].values, rem=send - s_geo, keep=m, v=ev[:, i0]))
            j = key[key['keep']].merge(fl, left_on=['run', 'bin', 'new'], right_on=['run', 'bin', 'new'])
            if len(j):
                out['by_flow'] = []
                j['fb'] = np.digitize(j['flow_vph'], [600, 1000, 1400, 1800])
                for b_, g in j.groupby('fb'):
                    out['by_flow'].append(dict(flow=[0, 600, 1000, 1400, 1800][b_], n=len(g), rem=qq(g['rem']), v_tgt=float(g['v_mean'].mean()), flow_mean=float(g['flow_vph'].mean())))
    # --- overlap and gaps at lateral start and label crossing ---
    Le = sc['Le'].values
    lag = S['lag']; lead = S['lead']; vF = S['vF']; vL = S['vL']
    def gapstats(m, t):
        la, le, vf, vl, v = at(lag, tau, t)[m], at(lead, tau, t)[m], at(vF, tau, t)[m], at(vL, tau, t)[m], at(ev, tau, t)[m]
        tot = la + le
        return dict(n=int(m.sum()), lag=qq(la), lead=qq(le), total_free=qq(tot), lag_time=qq(la / np.maximum(vf, 1)), lead_time=qq(le / np.maximum(v, 1)), overlap_share=float(np.nanmean((la < 0) | (le < 0))), overlap_m15=float(np.nanmean((la < -1.5) | (le < -1.5))), no_room_share=float(np.nanmean(tot < 2.0)), closing_lag=qq(vf - v), v=qq(v))
    groups = {'must': keepm, 'other': ~must}
    out['gaps'] = {}
    for g, m0 in groups.items():
        m = m0 & np.isfinite(t_on) & (t_on < -0.2)
        if m.sum() < 20: continue
        lag_on = at(lag, tau, ton_i)
        # require the same target-lane pair for gap growth, only for those already adjacent to the final gap at onset
        same = (at(S['idF'], tau, ton_i) == sc['F'].values) & (at(S['idL'], tau, ton_i) == sc['L'].values)
        r = dict(at_lateral_start=gapstats(m, ton_i), at_touch=gapstats(m & np.isfinite(t_touch), np.nan_to_num(t_touch)), at_centre=gapstats(m & np.isfinite(t_geo), np.nan_to_num(t_geo)), at_label=gapstats(m, np.zeros(len(sc))))
        r['already_adjacent_final_gap_at_start'] = float(np.nanmean(same[m]))
        # growth of the gaps from lateral start to centre over line, same pair
        mm = m & same & np.isfinite(t_geo)
        dl = (at(lag, tau, np.nan_to_num(t_geo)) - lag_on)[mm]; dd = (at(lead, tau, np.nan_to_num(t_geo)) - at(lead, tau, ton_i))[mm]
        dur = (np.nan_to_num(t_geo) - ton_i)[mm]
        r['growth_same_pair'] = dict(n=int(mm.sum()), dlag=qq(dl), dlead=qq(dd), duration=qq(dur), lag_grew_share=float(np.mean(dl > 0)), lead_grew_share=float(np.mean(dd > 0)))
        # who moved: change in F speed and in ego speed between start and centre over line
        r['speed_change_start_to_centre'] = dict(ego=qq((at(ev, tau, np.nan_to_num(t_geo)) - at(ev, tau, ton_i))[mm]), follower=qq((at(S['fv'], tau, np.nan_to_num(t_geo)) - at(S['fv'], tau, ton_i))[mm]))
        # lateral intrusion before room: how far in, while total free gap under 2 m or lag negative
        q_ = S['eq']
        pre = np.where(np.isfinite(lag) & ((lag < 0) | (lead < 0)) & (tau[None, :] <= 0), q_, np.nan)
        mx = np.nanmax(pre[m], axis=1) if m.any() else np.array([])
        r['max_q_while_overlapping'] = qq(mx)
        r['premax_q_before_final_start'] = qq(sc['premax'].values[m])
        r['probe_share_q25'] = float(np.nanmean(sc['premax'].values[m] >= 0.25))
        r['lateral_time_start_to_label'] = qq(-t_on[m])
        out['gaps'][g] = r
    # --- target gap: where was the final gap before lateral start ---
    tg = {}
    for g, m0 in groups.items():
        m = m0 & np.isfinite(t_on)
        if m.sum() < 20: continue
        row = {}
        for back in (0, 2, 5, 10, 15):
            t = ton_i - back
            ok = m & (t >= tau[0]) & np.isfinite(at(es, tau, t)) & np.isfinite(at(S['fs'], tau, t)) & np.isfinite(at(S['ls'], tau, t))
            s_e = at(es, tau, t)[ok]; s_f = at(S['fs'], tau, t)[ok]; s_l = at(S['ls'], tau, t)[ok]; Ll = sc['Ll'].values[ok]
            ahead = s_f > s_e  # final follower still ahead of ego: the final gap lies ahead
            behind = (s_l - Ll) < s_e  # final leader's rear is behind ego's front: the final gap lies behind
            adj = ~ahead & ~behind
            row[str(back)] = dict(n=int(ok.sum()), adjacent=float(adj.mean()), gap_ahead=float(ahead.mean()), gap_behind=float(behind.mean()))
        tg[g] = row
    out['target_gap'] = tg
    # --- own acceleration against plain following, before the lateral start ---
    r_e = np.full_like(ev, np.nan)
    gp = np.where(S['ogap'] < 80, S['ogap'], np.nan)
    tgt = cf_target(gp, ev, S['ov'])
    r_e[:, 2:] = S['ea'][:, 2:] - tgt[:, :-2]  # one second lag, as report 05
    ct = pd.read_csv(EV / f'{name}.controls.csv.gz')
    aF = ct[[f'af{j}' for j in range(len(CT))]].values; vFc = ct[[f'vf{j}' for j in range(len(CT))]].values; sFc = ct[[f'sf{j}' for j in range(len(CT))]].values; sLc = ct[[f'sl{j}' for j in range(len(CT))]].values; vLc = ct[[f'vl{j}' for j in range(len(CT))]].values
    gc = sLc - ct['Ll'].values[:, None] - sFc
    gc = np.where(gc < 80, gc, np.nan)
    tgc = cf_target(gc, vFc, vLc); rc = np.full_like(aF, np.nan); rc[:, 2:] = aF[:, 2:] - tgc[:, :-2]
    # mean residual of ordinary following by speed and gap cell
    cc = (np.digitize(vFc, [2, 5, 10, 15, 25]) * 10 + np.digitize(gc, [5, 10, 20, 40]))
    tab = pd.DataFrame(dict(c=cc[:, 4:].ravel(), r=rc[:, 4:].ravel())).dropna().groupby('c')['r'].mean()
    def base(v, g):
        c = (np.digitize(v, [2, 5, 10, 15, 25]) * 10 + np.digitize(g, [5, 10, 20, 40])).ravel()
        return pd.Series(c).map(tab).values.reshape(np.shape(v))
    ex = r_e - base(ev, gp)
    bins = [(-20, -15), (-15, -10), (-10, -5), (-5, -2), (-2, 0), (0, 2)]
    res = {}
    for g, m0 in groups.items():
        m = np.where(m0 & np.isfinite(t_on))[0]
        if len(m) < 20: continue
        tab_ = {}
        for a, b in bins:
            vals = []
            for i in m:
                ww = (tau >= t_on[i] + a) & (tau < t_on[i] + b) & (tau <= 2)
                if ww.any():
                    x = ex[i, ww]; x = x[np.isfinite(x)]
                    if len(x): vals.append(x.mean())
            mn, lo, hi = boot_mean(vals, 400)
            tab_[f'{a}..{b}'] = dict(n=len(vals), excess=round(mn, 3), lo=round(lo, 3), hi=round(hi, 3))
        res[g] = tab_
    out['pre_accel_excess'] = res
    # --- parallel episodes ---
    f = EV / f'{name}.episodes.csv.gz'
    if f.exists():
        ep = pd.read_csv(f)
        ep['dur'] = (ep['t1'] - ep['t0']) / hz + 0.5
        ep['mdv'] = ep['sdv'] / ep['n']
        ep['ma'] = ep['sa'] / ep['n']
        pr = {}
        for g, e in ep.groupby('group'):
            cars = e.groupby(['run', 'id'])['dur'].agg(['sum', 'max'])
            cnt = dict(cars=int(len(cars)), episodes=int(len(e)), dur=qq(e['dur'], (25, 50, 75, 90, 95, 99)), mean_abs_dv=qq(e['mdv']), share_ge2=float((e['dur'] >= 2).mean()), share_ge5=float((e['dur'] >= 5).mean()), share_ge10=float((e['dur'] >= 10).mean()),
                       locked_3s=float(((e['dur'] >= 3) & (e['mdv'] < 0.5)).mean()), locked_5s=float(((e['dur'] >= 5) & (e['mdv'] < 0.5)).mean()), car_longest=qq(cars['max'], (25, 50, 75, 90, 95)), car_total=qq(cars['sum'], (25, 50, 75, 90, 95)))
            # how the relative speed moves through a long episode
            long_ = e[e['dur'] >= 3]
            cnt['long_dv_start'] = qq(np.abs(long_['v0'] - long_['vX0']))
            cnt['long_dv_end'] = qq(np.abs(long_['dv1']))
            # direction: does the car go the way it already leans
            lean = np.sign(long_['d0'] + (long_['Lx'] - long_['Le']) / 2)
            mv = np.sign(long_['d1'] - long_['d0'])
            cnt['moves_with_lean'] = float((lean == mv).mean()) if len(long_) else np.nan
            pr[g] = cnt
        out['parallel'] = pr
    # share of time overlapped, last seconds before lateral start
    ov = (lag < 0) | (lead < 0)
    o2 = {}
    for g, m0 in groups.items():
        m = np.where(m0 & np.isfinite(t_on))[0]
        if len(m) < 20: continue
        for a, b in ((-20, -10), (-10, -5), (-5, 0)):
            vals = [np.nanmean(ov[i, (tau >= t_on[i] + a) & (tau < t_on[i] + b)]) for i in m if ((tau >= t_on[i] + a) & (tau < t_on[i] + b)).any() and np.isfinite(ev[i, (tau >= t_on[i] + a) & (tau < t_on[i] + b)]).any()]
            o2.setdefault(g, {})[f'{a}..{b}'] = round(float(np.mean(vals)), 3) if vals else None
    out['overlap_time_share_before_start'] = o2
    # --- follower response against matched controls, aligned on the lateral start ---
    TA = np.arange(-4, 8.01, 0.5)
    fgap = np.where(S['fgap'] < 80, S['fgap'], np.nan)
    tgf = cf_target(fgap, S['fv'], S['fvl']); rf = np.full_like(ev, np.nan); rf[:, 2:] = S['fa'][:, 2:] - tgf[:, :-2]
    # state at the lateral start
    v0 = at(S['fv'], tau, ton_i); lag0 = at(lag, tau, ton_i); dv0 = v0 - at(ev, tau, ton_i); g0 = at(fgap, tau, ton_i)
    fid_ok = (at(S['idF'], tau, ton_i) == sc['F'].values) & np.isfinite(t_on)
    stable = np.zeros(len(sc), bool)
    for i in range(len(sc)):
        if not fid_ok[i]: continue
        w = (tau >= t_on[i] - 3) & (tau <= min(t_on[i] + 5, 5))
        stable[i] = np.all(S['fla'][i, w] == sc['new'].values[i])
    c_e = cell(np.nan_to_num(v0, nan=-1), np.nan_to_num(lag0, nan=99), np.nan_to_num(dv0), np.nan_to_num(g0, nan=99))
    # control: state at control time zero
    j0 = int(np.argmin(np.abs(CT)))
    va0 = ct[f'va{j0}'].values; lagc = ct['lag0'].values
    c_c = cell(ct[f'vf{j0}'].values, lagc, ct[f'vf{j0}'].values - va0, np.nan_to_num(gc[:, j0], nan=99))
    bycell = {}
    for c in np.unique(c_c):
        bycell[int(c)] = np.where(c_c == c)[0]
    TC = CT[(CT >= -4) & (CT <= 6)]; cidx = np.array([int(np.argmin(np.abs(CT - t))) for t in TC])
    def response(mask):
        rows = []; ids = np.where(mask & stable)[0]; dH = []; ev_h = []; ct_q = []; pct = []
        for i in ids:
            cc_ = bycell.get(int(c_e[i]))
            if cc_ is None or len(cc_) < 15: continue
            t_ev = t_on[i] + TC
            ri = np.interp(t_ev, tau, rf[i], left=np.nan, right=np.nan)
            ri[t_ev > 6] = np.nan
            base_ = np.nanmean(rc[cc_][:, cidx], axis=0)
            rows.append(ri - base_)
            # speed lost from -1 to +4 s against the same in control cell
            vv = np.interp(t_on[i] + np.array([-1.0, 4.0]), tau, S['fv'][i])
            drop = vv[0] - vv[1]
            cc2 = vFc[cc_][:, int(np.argmin(np.abs(CT + 1)))] - vFc[cc_][:, int(np.argmin(np.abs(CT - 4)))]
            cc2 = cc2[np.isfinite(cc2)]
            if not len(cc2): continue
            dH.append(drop - cc2.mean()); ev_h.append(drop > np.percentile(cc2, 80)); pct.append(drop)
        rows = np.array(rows)
        if len(rows) < 15: return dict(n=len(rows))
        mean = np.nanmean(rows, axis=0)
        se = np.nanstd(rows, axis=0) / np.sqrt(np.sum(np.isfinite(rows), axis=0))
        pre = np.nanmean(rows[:, (TC >= -3) & (TC < -0.5)], axis=1); post = np.nanmean(rows[:, (TC >= 0) & (TC <= 3)], axis=1)
        m1, a1, b1 = boot_mean(dH, 500); m2, a2, b2 = boot_mean(pre, 500); m3, a3, b3 = boot_mean(post, 500)
        return dict(n=len(rows), excess_a=[round(float(x), 3) for x in mean], se=[round(float(x), 3) for x in se], speed_lost_excess=(round(m1, 3), round(a1, 3), round(b1, 3)), responders_excess_over_20pct=round(float(np.mean(ev_h)) - 0.2, 3), pre_start_excess=(round(m2, 3), round(a2, 3), round(b2, 3)), post_start_excess=(round(m3, 3), round(a3, 3), round(b3, 3)))
    resp = dict(tau=[float(x) for x in TC])
    resp['all'] = response(np.ones(len(sc), bool)); resp['must'] = response(keepm); resp['other'] = response(~must)
    for lo, hi in ((-20, 0), (0, 2), (2, 5), (5, 10), (10, 20), (20, 200)):
        resp[f'lag_{lo}_{hi}'] = response((lag0 >= lo) & (lag0 < hi))
    for lo, hi in ((0, 5), (5, 10), (10, 15), (15, 25), (25, 60)):
        resp[f'v_{lo}_{hi}'] = response((v0 >= lo) & (v0 < hi))
    out['follower'] = resp
    return out, sc, S, tau, t_on, keepm, send


if __name__ == '__main__':
    for name in sys.argv[1:]:
        r = analyse(name)[0]
        save(name, r)
        print(name, 'events', r['events'], 'must', r['must'], flush=True)
