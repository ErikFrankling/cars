"""Per-event time series, must-change steps, parallel episodes and follower controls. Usage: mg_events.py SITE [SITE...]. Writes MG_DATA/events/SITE.*.npz or csv.gz."""
import sys; sys.path.insert(0, 'research/truth/scripts/merging')
from mg_lib import *

MUST = {'sim': [(1, 2)], 'simf': [(1, 2)], 'simo': [(1, 2)], 'i-80': [(7, 6)], 'us-101': [(6, 5)], 'I395': [(-2, -3)], 'ht': [(-9, -10), (10, 11)]}
START = {'sim': {2: (1,)}, 'simf': {2: (1,)}, 'simo': {2: (1,)}, 'i-80': {6: (7,)}, 'us-101': {5: (6, 7)}, 'I395': {-3: (-2, -1)}, 'ht': {-10: (-9, -8, -7), 11: (8, 9, 10)}}
# through cars on the far side of the same target lane
CTRL = {'i-80': [(5, 6)], 'us-101': [(4, 5)], 'I395': [(-4, -3)], 'ht': [(-11, -10), (12, 11)], 'I90mov': [(3, 4), (4, 5)], 'I90stat': [(4, 5), (13, 14)], 'I294L1': [(3, 4), (-3, -4)]}
TAU = np.arange(-30, 10.01, 0.5)
CT = np.arange(-8, 8.01, 0.5)
CAP = 5000


def adj_ok(site, a, b):
    if site == 'us-101': return abs(a - b) == 1 and max(a, b) <= 7
    if site == 'i-80': return abs(a - b) == 1
    return abs(a - b) == 1 and a * b > 0 and {abs(a), abs(b)} not in ({3, 4}, {12, 13}) if site not in ('I90mov', 'I90stat', 'I294L1', 'I395', 'ht') else (abs(a - b) == 1 and a * b > 0)


def find_changes(st, hold=3.0):
    hw = int(hold * st.hz); out = []
    for k, (a, b) in st.veh.items():
        if b - a < 2 * hw + 1: continue
        l = st.LA[a:b]
        for c in np.where(l[1:] != l[:-1])[0] + 1:
            if c < hw or c > b - a - hw - 1: continue
            w = l[c - hw:c + hw]
            if (np.diff(w) != 0).sum() != 1: continue
            if not adj_ok(st.name, int(l[c - 1]), int(l[c])): continue
            if st.T[a + c + hw - 1] - st.T[a + c - hw] != 2 * hw - 1: continue
            out.append((int(st.R[a]), int(st.I[a]), int(st.T[a + c]), int(l[c - 1]), int(l[c])))
    return out


def run(name):
    st = Site(name); hz = st.hz; must = set(MUST.get(name, []))
    ch = find_changes(st)
    rng = np.random.default_rng(11)
    is_must = np.array([(o, n) in must for r, i, t, o, n in ch], dtype=bool)
    print(name, 'changes', len(ch), 'must', int(is_must.sum()), flush=True)
    keep = np.where(is_must)[0].tolist(); oth = np.where(~is_must)[0]
    if len(oth) > CAP: oth = rng.choice(oth, CAP, replace=False)
    keep += oth.tolist()
    n = len(keep); m = len(TAU)
    names = ['ev', 'ea', 'es', 'eq', 'edT', 'lag', 'vF', 'idF', 'lead', 'vL', 'idL', 'ogap', 'ov', 'fv', 'fa', 'fs', 'fla', 'lv', 'ls', 'fgap', 'fvl', 'ela']
    A = {c: np.full((n, m), np.nan, 'f4') for c in names}
    sc = []; off = np.round(TAU * hz).astype('i4')
    for e, ix in enumerate(keep):
        r, vid, tc, old, new = ch[ix]
        tq = tc + off
        v, s, a, la, lat = st.series(r, vid, tq)
        A['ev'][e], A['es'][e], A['ea'][e], A['ela'][e] = v, s, a, la
        rng_ = st.veh[(r << 32) | (vid & 0xffffffff)]; Le = float(st.LL[rng_[0]])
        ok = np.isfinite(s)
        if not ok.any(): continue
        co = st.centre(r, old, s); cn = st.centre(r, new, s)
        wd = cn - co; sg = np.sign(np.nanmedian(wd)) if np.isfinite(wd).any() else 1.0
        wabs = np.abs(wd)
        A['eq'][e] = (lat - co) * sg / np.where(wabs > 1.5, wabs, np.nan)
        A['edT'][e] = (cn - lat) * sg
        F0, L0 = None, None
        i0 = int(np.argmin(np.abs(TAU)))
        for j in range(m):
            if not ok[j]: continue
            t = int(tq[j]); sj = float(s[j])
            F, L = st.around(r, t, new, sj, vid)
            if F: A['lag'][e, j], A['vF'][e, j], A['idF'][e, j] = sj - Le - F[1], F[3], F[0]
            if L: A['lead'][e, j], A['vL'][e, j], A['idL'][e, j] = L[1] - L[2] - sj, L[3], L[0]
            _, OL = st.around(r, t, old if j <= i0 else new, sj + 0.01, vid)
            if OL: A['ogap'][e, j], A['ov'][e, j] = OL[1] - OL[2] - sj, OL[3]
            if j == i0: F0, L0 = F, L
        Lf = Ll = np.nan; f = l = -1
        if F0:
            f = F0[0]; Lf = F0[2]
            fv_, fs_, fa_, fla_, _ = st.series(r, f, tq)
            A['fv'][e], A['fs'][e], A['fa'][e], A['fla'][e] = fv_, fs_, fa_, fla_
            for j in np.where(np.abs(TAU) <= 12)[0]:
                if not np.isfinite(fs_[j]): continue
                _, FL = st.around(r, int(tq[j]), new, float(fs_[j]) + 0.01, vid)
                if FL and FL[0] != f: A['fgap'][e, j], A['fvl'][e, j] = FL[1] - FL[2] - fs_[j], FL[3]
        if L0:
            l = L0[0]; Ll = L0[2]
            lv_, ls_, _, _, _ = st.series(r, l, tq)
            A['lv'][e], A['ls'][e] = lv_, ls_
        # lateral onset at full rate
        ta, tb = rng_
        tc_i = ta + int(np.searchsorted(st.T[ta:tb], tc))
        ss = st.S[ta:tc_i + 1]; ll = st.LT[ta:tc_i + 1]
        co2 = st.centre(r, old, ss); cn2 = st.centre(r, new, ss); w2 = np.abs(cn2 - co2); sg2 = np.sign(np.nanmedian(cn2 - co2)) if len(ss) else 1
        qq = (ll - co2) * sg2 / np.where(w2 > 1.5, w2, np.nan)
        # only frames in the old lane count
        inold = st.LA[ta:tc_i + 1] == old
        t_on = {}
        for th in (0.1, 0.2, 0.3):
            below = np.where((qq <= th) & inold)[0]
            t_on[th] = (below[-1] + 1 - (len(qq) - 1)) / hz if len(below) else np.nan
        i_on = int(len(qq) - 1 + round((t_on[0.1] if np.isfinite(t_on[0.1]) else 0) * hz))
        premax = float(np.nanmax(qq[max(0, i_on - 30 * hz):max(1, i_on - hz)])) if i_on - hz > 0 else np.nan
        # time in the old lane before the crossing
        d = np.where(st.LA[ta:tc_i] != old)[0]; first = d[-1] + 1 if len(d) else 0
        sc.append(dict(e=e, run=r, id=vid, tc=tc, old=old, new=new, must=int(is_must[ix]), Le=Le, Lf=Lf, Ll=Ll, F=f, L=l, s_c=float(s[i0]) if ok[i0] else np.nan, t_on10=t_on[0.1], t_on20=t_on[0.2], t_on30=t_on[0.3], premax=premax,
                       wait=(tc_i - (ta + first)) / hz, first_lane=int(st.LA[ta]), s_first=float(st.S[ta]), s_lane0=float(st.S[ta + first]), track_end=int(st.T[tb - 1]), W=float(np.nanmedian(np.abs(cn2 - co2)))))
    sc = pd.DataFrame(sc)
    sc.to_csv(EV / f'{name}.scalars.csv.gz', index=False, float_format='%.3f')
    np.savez_compressed(EV / f'{name}.series.npz', tau=TAU, **A)
    print(name, 'events done', len(sc), flush=True)

    # must-change steps at 1 Hz over the whole stay in the lane
    rows = []
    for ix in np.where(is_must)[0]:
        r, vid, tc, old, new = ch[ix]
        ta, tb = st.veh[(r << 32) | (vid & 0xffffffff)]
        if st.LA[ta] not in START[name][new]: continue
        tc_i = ta + int(np.searchsorted(st.T[ta:tb], tc))
        d = np.where(st.LA[ta:tc_i] != old)[0]; first = d[-1] + 1 if len(d) else 0
        Le = float(st.LL[ta])
        for i in range(tc_i, ta + first - 1, -hz):
            t, sj = int(st.T[i]), float(st.S[i])
            F, L = st.around(r, t, new, sj, vid); _, OL = st.around(r, t, old, sj + 0.01, vid)
            co = st.centre(r, old, sj); cn = st.centre(r, new, sj); wd = abs(cn - co); sg = np.sign(cn - co)
            rows.append(dict(run=r, id=vid, t=t, tleft=(tc_i - i) / hz, wait=(i - ta - first) / hz, s=sj, v=float(st.V[i]), a=float(st.A[i]), q=float((st.LT[i] - co) * sg / wd) if wd > 1.5 else np.nan, dT=float((cn - st.LT[i]) * sg),
                             lag=sj - Le - F[1] if F else np.nan, vF=F[3] if F else np.nan, idF=F[0] if F else -1, lead=L[1] - L[2] - sj if L else np.nan, vL=L[3] if L else np.nan, idL=L[0] if L else -1,
                             ogap=OL[1] - OL[2] - sj if OL else np.nan, ov=OL[3] if OL else np.nan))
    if rows:
        pd.DataFrame(rows).to_csv(EV / f'{name}.steps.csv.gz', index=False, float_format='%.3f')
    print(name, 'steps', len(rows), flush=True)

    # parallel episodes for must-change cars and for through cars on the far side of the target lane
    ep = []
    def episodes(group, r, vid, a0, b0, tgt, tc_i=None):
        Le = float(st.LL[a0]); cur = None; step = max(1, hz // 2)
        for i in range(a0, b0, step):
            t, sj = int(st.T[i]), float(st.S[i])
            F, L = st.around(r, t, tgt, sj, vid)
            X = None
            if F and sj - Le - F[1] < 0: X = F
            elif L and L[1] - L[2] - sj < 0: X = L
            if X is None:
                if cur: ep.append(cur); cur = None
                continue
            if cur is None or cur['X'] != X[0]:
                if cur: ep.append(cur)
                cur = dict(group=group, run=r, id=vid, X=X[0], t0=t, t1=t, v0=float(st.V[i]), vX0=X[3], d0=sj - X[1], s0=sj, adv=0.0, n=0, sdv=0.0, sa=0.0, dv1=np.nan, d1=np.nan, Le=Le, Lx=X[2])
            cur['t1'] = t; cur['n'] += 1; cur['sdv'] += abs(float(st.V[i]) - X[3]); cur['sa'] += float(st.A[i]); cur['dv1'] = float(st.V[i]) - X[3]; cur['d1'] = sj - X[1]
        if cur: ep.append(cur)

    for ix in np.where(is_must)[0]:
        r, vid, tc, old, new = ch[ix]
        ta, tb = st.veh[(r << 32) | (vid & 0xffffffff)]
        if st.LA[ta] not in START[name][new]: continue
        tc_i = ta + int(np.searchsorted(st.T[ta:tb], tc))
        d = np.where(st.LA[ta:tc_i] != old)[0]; first = d[-1] + 1 if len(d) else 0
        episodes('must', r, vid, ta + first, tc_i + 1, new)
    for c_lane, tgt in CTRL.get(name, []):
        ids = [k for k, (a, b) in st.veh.items() if (st.LA[a:b] == c_lane).mean() > 0.95 and (st.LA[a:b] == tgt).sum() == 0]
        if len(ids) > 1500: ids = [ids[i] for i in rng.choice(len(ids), 1500, replace=False)]
        for k in ids:
            a, b = st.veh[k]
            episodes('through', int(st.R[a]), int(st.I[a]), a, b, tgt)
    if ep:
        pd.DataFrame(ep).to_csv(EV / f'{name}.episodes.csv.gz', index=False, float_format='%.3f')
    print(name, 'episodes', len(ep), flush=True)

    # follower controls: an adjacent car ahead of the follower that does not change lane, same window
    lanes = sorted(set(int(x) for x in np.unique(st.LA)))
    busy = {}
    for r, vid, tc, old, new in ch: busy.setdefault((r, new), []).append(tc)
    busy = {k: np.sort(v) for k, v in busy.items()}
    Nrow = len(st.R); target = 8000; tries = 0; cts = []; off2 = np.round(CT * hz).astype('i4')
    i4 = int(np.argmin(np.abs(CT + 4))); i4b = int(np.argmin(np.abs(CT - 4))); i0 = int(np.argmin(np.abs(CT)))
    while len(cts) < target and tries < target * 40:
        tries += 1
        i = int(rng.integers(0, Nrow)); r, t, f, ln, sf = int(st.R[i]), int(st.T[i]), int(st.I[i]), int(st.LA[i]), float(st.S[i])
        cand = [x for x in (ln - 1, ln + 1) if x in lanes and adj_ok(name, x, ln)]
        if not cand: continue
        side = cand[int(rng.integers(0, len(cand)))]
        _, A_ = st.around(r, t, side, sf + 0.01, f)
        if A_ is None: continue
        La = A_[2]; lag = A_[1] - La - sf
        if lag < -6 or lag > 60: continue
        b = busy.get((r, ln))
        if b is not None:
            j = np.searchsorted(b, t)
            if any(0 <= jj < len(b) and abs(int(b[jj]) - t) <= 8 * hz for jj in (j - 1, j)): continue
        tq = t + off2
        vf, s_f, af, lf, _ = st.series(r, f, tq); va, sa, aa, la2, _ = st.series(r, A_[0], tq)
        if not (np.all(lf[i4:i4b + 1] == ln) and np.all(np.isfinite(sa)) and np.all(la2 == side)): continue
        _, FL = st.around(r, t, ln, sf + 0.01, f)
        if FL is None: continue
        vl, sl, _, ll, _ = st.series(r, FL[0], tq)
        if not np.all(ll[i4:i4b + 1] == ln): continue
        cts.append(dict(run=r, t=t, F=f, lane=ln, side=side, A=A_[0], LF=FL[0], lag0=lag, Lf=float(st.LL[st.veh[(r << 32) | (f & 0xffffffff)][0]]), Ll=FL[2], vF0=vf[i0], vA0=va[i0],
                        **{f'af{j}': af[j] for j in range(len(CT))}, **{f'vf{j}': vf[j] for j in range(len(CT))}, **{f'sf{j}': s_f[j] for j in range(len(CT))}, **{f'sl{j}': sl[j] for j in range(len(CT))}, **{f'vl{j}': vl[j] for j in range(len(CT))}, **{f'sa{j}': sa[j] for j in range(len(CT))}, **{f'va{j}': va[j] for j in range(len(CT))}))
    pd.DataFrame(cts).to_csv(EV / f'{name}.controls.csv.gz', index=False, float_format='%.3f')
    print(name, 'controls', len(cts), 'tries', tries, flush=True)


for s in sys.argv[1:]: run(s)
