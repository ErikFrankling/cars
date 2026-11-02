"""Flow per 5 minutes around each lane end, and 1 Hz steps of through cars next to the same target lane (placebo for must-change cars). Usage: mg_more.py SITE [SITE...]"""
import sys; sys.path.insert(0, 'research/truth/scripts/merging')
from mg_lib import *
MUST = {'i-80': [(7, 6, 200.0)], 'us-101': [(6, 5, 400.0)], 'I395': [(-2, -3, 500.0)], 'ht': [(-9, -10, 6000.0), (10, 11, 250.0)]}
CTRL = {'i-80': [(5, 6)], 'us-101': [(4, 5)], 'I395': [(-4, -3)], 'ht': [(-11, -10), (12, 11)], 'I90mov': [(3, 4), (4, 5)], 'I90stat': [(4, 5), (13, 14)], 'I294L1': [(3, 4), (-3, -4)]}
W5 = 300
for name in sys.argv[1:]:
    st = Site(name); hz = st.hz; rng = np.random.default_rng(5)
    fl = []
    for old, new, sx in MUST.get(name, []):
        for r in np.unique(st.R):
            m = st.R == r
            tt = st.T[m] / hz
            for lane, tag in ((new, 'tgt'), (old, 'src')):
                mm = st.LA[m] == lane
                near = mm & (st.S[m] > sx - 100) & (st.S[m] <= sx)
                bins = (tt / W5).astype('i4')
                # crossings of the section at sx - 50
                I_ = st.I[m]; S_ = st.S[m]
                cross = np.r_[False, (I_[1:] == I_[:-1]) & (S_[:-1] < sx - 50) & (S_[1:] >= sx - 50)] & mm
                for b in np.unique(bins):
                    q_ = bins == b
                    fl.append(dict(site=name, run=int(r), bin=int(b), old=old, new=new, lane=tag, flow_vph=float(cross[q_].sum()) * 3600 / W5, v_mean=float(st.V[m][near & q_].mean()) if (near & q_).any() else np.nan, occ_veh=float((near & q_).sum()) / (hz * W5) / 100 * 1000))
    if fl: pd.DataFrame(fl).to_csv(EV / f'{name}.flows.csv.gz', index=False, float_format='%.3f')
    rows = []
    for c_lane, tgt in CTRL.get(name, []):
        ids = [k for k, (a, b) in st.veh.items() if (st.LA[a:b] == c_lane).mean() > 0.95 and (st.LA[a:b] == tgt).sum() == 0]
        if len(ids) > 800: ids = [ids[i] for i in rng.choice(len(ids), 800, replace=False)]
        for k in ids:
            a, b = st.veh[k]; r, vid = int(st.R[a]), int(st.I[a]); Le = float(st.LL[a])
            for i in range(a, b, hz):
                t, sj = int(st.T[i]), float(st.S[i])
                F, L = st.around(r, t, tgt, sj, vid); _, OL = st.around(r, t, c_lane, sj + 0.01, vid)
                rows.append(dict(run=r, id=vid, t=t, s=sj, v=float(st.V[i]), a=float(st.A[i]), lag=sj - Le - F[1] if F else np.nan, vF=F[3] if F else np.nan, idF=F[0] if F else -1, lead=L[1] - L[2] - sj if L else np.nan, vL=L[3] if L else np.nan, idL=L[0] if L else -1, ogap=OL[1] - OL[2] - sj if OL else np.nan, ov=OL[3] if OL else np.nan))
    if rows: pd.DataFrame(rows).to_csv(EV / f'{name}.tsteps.csv.gz', index=False, float_format='%.3f')
    print(name, 'flows', len(fl), 'tsteps', len(rows), flush=True)
