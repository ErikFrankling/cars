"""Cars that must change lane, with the outcome known: on-ramp merges at US-101 and I-80, and left or right turners at Lankershim and Peachtree.
For each such car every target-lane vehicle that comes alongside is one opportunity: it either passes (no entry) or ends up behind (let in).
Usage: courtesy_merge.py SITE [SITE...]. Writes steps and episodes under research/truth/courtesy."""
import sys; sys.path.insert(0, 'research/truth/scripts')
from courtesy_lib import *

STEP = 0.5


def freeway_cohort(fr, ramp_lane, aux_lane, target):
    """Cars first seen on the ramp or aux lane that later change from aux_lane to target."""
    out = []; never = 0; kept_end = []
    for (a, b) in fr.veh.values():
        l = fr.vLA[a:b]; t = fr.vT[a:b]; s = fr.vS[a:b]
        if l[0] not in (ramp_lane, aux_lane): continue
        ch = np.where((l[:-1] == aux_lane) & (l[1:] == target))[0]
        if len(ch) == 0:
            if l[-1] == aux_lane or l[-1] == ramp_lane: never += 1
            continue
        k = ch[-1] + 1
        # must have stayed in the target or further for 2 s
        hz2 = 2 * fr.hz
        if b - a - k < hz2 or np.any(l[k:k + hz2] != target): continue
        i0 = np.where(l[:k] == aux_lane)[0]
        if not len(i0): continue
        out.append((int(fr.vR[a]), int(fr.vID[a]), int(t[i0[0]]), int(t[k]), aux_lane, target, float(s[k]), float(fr.vV[a + k])))
        kept_end.append(float(s[k]))
    return out, never


def urban_cohort(fr, d):
    """Turners: a vehicle whose later movement is left or right, and the last lane changes in the approach that head that way."""
    out = []
    for (run, vid), g in d.groupby(['run', 'id'], sort=False):
        g = g.sort_values('t')
        t, la, mv, it, sec, dr, s = [g[c].values for c in ('t', 'lane', 'move', 'int_id', 'section', 'dirn', 's')]
        ins = np.where(it > 0)[0]
        if not len(ins): continue
        # blocks of intersection frames with a turn
        blocks = np.split(ins, np.where(np.diff(ins) > 1)[0] + 1)
        for b in blocks:
            turn = mv[b[0]]
            if turn not in (2, 3) or b[0] == 0: continue
            if dr[b[0] - 1] not in (2, 4): continue
            k = b[0] - 1
            j = k
            while j > 0 and it[j - 1] == 0 and t[j] - t[j - 1] == 1: j -= 1
            lanes = la[j:k + 1]; ts = t[j:k + 1]; ss = s[j:k + 1]
            base = int(dr[k]) * 100
            ch = np.where(lanes[1:] != lanes[:-1])[0] + 1
            for c in ch:
                old, new = int(lanes[c - 1]), int(lanes[c])
                ol, nl = old % 100, new % 100
                if ol > 12 or nl > 12: continue
                left = (nl == ol - 1 and nl >= 1 and nl <= 4) or (ol == 1 and nl == 11) or (ol == 11 and nl == 12)
                right = nl == ol + 1 and nl <= 4
                if (turn == 2 and not left) or (turn == 3 and not right): continue
                # stable for 2 s each side
                if c < 20 or len(lanes) - c < 20 or np.any(lanes[c - 20:c] != old) or np.any(lanes[c:c + 20] != new): continue
                prev = np.where(lanes[:c] != old)[0]
                i0 = prev[-1] + 1 if len(prev) else 0
                out.append((int(run), int(vid), int(ts[i0]), int(ts[c]), old, new, float(ss[c]), float(g['v'].values[j + c])))
    return out


def walk(fr, r, vid, t0, tc, old, new, site, s_end):
    """Half-second states of the waiting car and its target-lane neighbours, ending 2 s after the crossing."""
    rows = []; tq = np.arange(tc, t0 - 1, -int(round(STEP * fr.hz)))[::-1]
    ve, se, ae, le = fr.series(r, vid, tq)
    Le = fr.vL[fr.track(r, vid)[0]]
    for i, t_ in enumerate(tq):
        if not np.isfinite(se[i]): continue
        f, l = fr.neighbours(r, int(t_), new, float(se[i]), vid)
        rows.append(dict(site=site, run=r, id=vid, t=int(t_), wait=(t_ - t0) / fr.hz, tleft=(tc - t_) / fr.hz, vM=float(ve[i]), rem=(s_end - float(se[i])) if s_end is not None else np.nan,
                         T=int(fr.ID[f]) if f >= 0 else -1, lag=float(se[i] - Le - fr.S[f]) if f >= 0 else np.nan, vT=float(fr.V[f]) if f >= 0 else np.nan, aT=float(fr.A[f]) if f >= 0 else np.nan,
                         Lead=int(fr.ID[l]) if l >= 0 else -1, lead=float(fr.S[l] - fr.LEN[l] - se[i]) if l >= 0 else np.nan, vL=float(fr.V[l]) if l >= 0 else np.nan))
    return rows


def episodes(steps, tc):
    """Per target-lane vehicle in turn: how it stopped being the waiting car's lag vehicle."""
    eps = []
    if not len(steps): return eps
    cur = None
    for k, s in enumerate(steps):
        if s['T'] < 0: cur = None; continue
        if cur is None or cur['T'] != s['T']:
            if cur is not None: eps.append(cur)
            cur = dict(site=s['site'], run=s['run'], id=s['id'], T=s['T'], t0=s['t'], wait0=s['wait'], vT0=s['vT'], vM0=s['vM'], lag0=s['lag'], lead0=s['lead'], rem0=s['rem'], t1=s['t'], lag_min=s['lag'], lag_last=s['lag'], aT_min=s['aT'], vT_last=s['vT'], vM_last=s['vM'], next_T=-2)
        else:
            cur['t1'] = s['t']; cur['lag_min'] = min(cur['lag_min'], s['lag']) if np.isfinite(s['lag']) else cur['lag_min']; cur['lag_last'] = s['lag']; cur['aT_min'] = min(cur['aT_min'], s['aT']); cur['vT_last'] = s['vT']; cur['vM_last'] = s['vM']
    if cur is not None: eps.append(cur)
    return eps


def process(site):
    if site in ('us-101', 'i-80'):
        d = ngsim(C / 'ngsim-20261101' / f'{site}.csv'); d = d[d['lane'] > 0]
    elif site == 'ht':
        d = ht(); d = d[d['tr'] == 0]
    else:
        d = ngsim(T / 'opus-20261031-ngsim' / f'{site}.csv', urban=True)
        keep = d['dirn'].isin([2, 4]) & ((d['int_id'] > 0) | d['lane'].isin([1, 2, 3, 4, 11, 12]))
        d = d[keep].copy(); d['s'] = (d['s'] * np.where(d['dirn'] == 2, 1, -1)).astype('f4')
        d['lane'] = (d['lane'].astype('i4') + 100 * d['dirn'].astype('i4')).astype('i2')
        d.loc[d['int_id'] > 0, 'lane'] = 0
    fr = Frames(d, 5 if site == 'ht' else 10)
    ends_by = None
    if site == 'ht':
        coh, never = [], 0
        for ramp, tgt in ((-9, -10), (10, 11)):
            c, n = freeway_cohort(fr, ramp, ramp, tgt); coh += c; never += n
    elif site == 'us-101': coh, never = freeway_cohort(fr, 7, 6, 5)
    elif site == 'i-80': coh, never = freeway_cohort(fr, 7, 7, 6)
    else: coh = urban_cohort(fr, d[d['lane'] != 0].pipe(lambda x: d)); never = 0
    print(site, 'cohort', len(coh), 'never-merged-in-view', never, flush=True)
    ends = np.array([c[6] for c in coh]) if coh else np.array([0.0])
    s_end = float(np.percentile(ends, 99.5)) if site in ('us-101', 'i-80') else None
    if site == 'ht':
        print('HT merge positions', np.histogram(ends, bins=np.arange(0, 6600, 200))[0].tolist(), flush=True)
    S, E, M = [], [], []
    for r, vid, t0, tc, old, new, sc, vc in coh:
        if site == 'ht':
            sc_all = np.array([c[6] for c in coh if c[4] == old]); near = sc_all[np.abs(sc_all - sc) < 400]
            s_end = float(np.percentile(near, 99))
        rows = walk(fr, r, vid, t0, tc, old, new, site, s_end)
        S += rows; ep = episodes(rows, tc)
        for j, e in enumerate(ep):
            last = j == len(ep) - 1
            # the last lag vehicle at the crossing is the one that lets the car in
            e['outcome'] = 'letin' if last else ('passed' if ep[j + 1]['lag0'] is not None else 'other')
            # a change of lag vehicle only counts as passing if the old one really got ahead
            if not last:
                ts = np.array([e['t1'] + 5])
                vt, st, _, lt = fr.series(r, e['T'], ts); vm, sm, _, _ = fr.series(r, vid, ts)
                if lt[0] != new: e['outcome'] = 'left_lane'
                elif not st[0] > sm[0]: e['outcome'] = 'car_moved_ahead'
        E += ep
        M.append(dict(site=site, run=r, id=vid, t0=t0, tc=tc, old=old, new=new, s_c=sc, v_c=vc, rem_c=(s_end - sc) if s_end is not None else np.nan, wait=(tc - t0) / fr.hz,
                      passes=sum(e['outcome'] == 'passed' for e in ep), lags=len(ep)))
    pd.DataFrame(S).to_csv(OUT / f'merge_steps_{site}.csv.gz', index=False, float_format='%.3f')
    pd.DataFrame(E).to_csv(OUT / f'merge_episodes_{site}.csv.gz', index=False, float_format='%.3f')
    pd.DataFrame(M).to_csv(OUT / f'merge_cars_{site}.csv.gz', index=False, float_format='%.3f')
    print(site, 'steps', len(S), 'episodes', len(E), 's_end', s_end, 'never', never, flush=True)


for s in sys.argv[1:]: process(s)
