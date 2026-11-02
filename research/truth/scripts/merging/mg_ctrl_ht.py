"""A39 follower controls: the busy test in mg_events ignored position, which over a 6 km site rejects almost everything. Same rule, within 400 m."""
import sys; sys.path.insert(0, 'research/truth/scripts/merging')
from mg_lib import *
CT = np.arange(-8, 8.01, 0.5)
name = 'ht'
st = Site(name); hz = st.hz; rng = np.random.default_rng(13)
sc = pd.read_csv(EV / f'{name}.scalars.csv.gz')
lanes = set(int(x) for x in np.unique(st.LA))
busy = {}
for t, s, n in zip(sc['tc'].values, sc['s_c'].values, sc['new'].values): busy.setdefault(int(n), []).append((int(t), float(s)))
busy = {k: np.array(sorted(v)) for k, v in busy.items()}
Nrow = len(st.R); target = 6000; tries = 0; cts = []; off2 = np.round(CT * hz).astype('i4')
i4 = int(np.argmin(np.abs(CT + 4))); i4b = int(np.argmin(np.abs(CT - 4))); i0 = int(np.argmin(np.abs(CT)))
while len(cts) < target and tries < target * 60:
    tries += 1
    i = int(rng.integers(0, Nrow)); r, t, f, ln, sf = int(st.R[i]), int(st.T[i]), int(st.I[i]), int(st.LA[i]), float(st.S[i])
    cand = [x for x in (ln - 1, ln + 1) if x in lanes and x * ln > 0]
    if not cand: continue
    side = cand[int(rng.integers(0, len(cand)))]
    _, A_ = st.around(r, t, side, sf + 0.01, f)
    if A_ is None: continue
    La = A_[2]; lag = A_[1] - La - sf
    if lag < -6 or lag > 60: continue
    b = busy.get(ln)
    if b is not None:
        j0, j1 = np.searchsorted(b[:, 0], [t - 8 * hz, t + 8 * hz])
        if j1 > j0 and np.any(np.abs(b[j0:j1, 1] - sf) < 400): continue
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
print('ht controls', len(cts), 'tries', tries, flush=True)
# through-car steps, smaller sample, and flows at the two ramps
rows = []
for c_lane, tgt in [(-11, -10), (12, 11)]:
    ids = [k for k, (a, b) in st.veh.items() if (st.LA[a:b] == c_lane).mean() > 0.95 and (st.LA[a:b] == tgt).sum() == 0]
    if len(ids) > 300: ids = [ids[i] for i in rng.choice(len(ids), 300, replace=False)]
    for k in ids:
        a, b = st.veh[k]; r, vid = int(st.R[a]), int(st.I[a]); Le = float(st.LL[a])
        for i in range(a, b, hz):
            t, sj = int(st.T[i]), float(st.S[i])
            F, L = st.around(r, t, tgt, sj, vid); _, OL = st.around(r, t, c_lane, sj + 0.01, vid)
            rows.append(dict(run=r, id=vid, t=t, s=sj, v=float(st.V[i]), a=float(st.A[i]), lag=sj - Le - F[1] if F else np.nan, vF=F[3] if F else np.nan, idF=F[0] if F else -1, lead=L[1] - L[2] - sj if L else np.nan, vL=L[3] if L else np.nan, idL=L[0] if L else -1, ogap=OL[1] - OL[2] - sj if OL else np.nan, ov=OL[3] if OL else np.nan))
pd.DataFrame(rows).to_csv(EV / f'{name}.tsteps.csv.gz', index=False, float_format='%.3f')
print('ht tsteps', len(rows), flush=True)
