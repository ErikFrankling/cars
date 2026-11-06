"""Round 4 of the measured driver, steps 2-4: does each driver's own preferred gap, read from its PAST, explain why open gaps
close slowly, and does a strong pull towards it pass every pattern? Forecasts F815 onwards, research/truth/measure/PERSONAL.md.
Recordings not held out (HOLDOUT.md): follow.py's tables (highD without location 6, DLR HT 06-14 UTC, TGSIM I-90/94
stationary, I-294 L1, I-395).

    python3 -I scripts/measure/personal.py decompose    # F815 F816: persistent and transient parts of open gaps
"""
import os, sys, json, math
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
RES = os.path.join(HERE, '..', '..', 'research', 'truth', 'measure')
OUT = os.path.join(RES, 'personal.json')
import fit_driver as FD
rng = np.random.default_rng(815)
DT = 0.2
SD_P, SD_W = 0.27, 0.47          # persistent log-SD and the spread between 10 s windows (DRIVER.md)


def save(key, val):
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    out[key] = val
    json.dump(out, open(OUT, 'w'), indent=1)


def shrink(s, c):
    """Mean log ratio over c steady samples (5 Hz), pulled towards 0 by its reliability."""
    nw = np.maximum(c / 50.0, 1e-9)
    rho = SD_P ** 2 / (SD_P ** 2 + (SD_W ** 2 - SD_P ** 2) / nw)
    return np.where(c >= 25, rho * s / np.maximum(c, 1), 0.0), np.where(c >= 25, rho, 0.0)


def gstar(v, f):
    vt = np.maximum(v, 6.5)
    return FD.S0 + f * (FD.t_gap(vt) - FD.S0 / vt) * v


def table_past(name):
    """follow.py table with car leaders, sorted by driver and time, with each sample's past sums of the steady log ratio:
    (A) over the driver's earlier segments only (other leaders), (B) over everything before it."""
    import follow as F
    d = F.load(name)
    d = d[d.lcar.astype(bool)]
    d['drv'] = pd.factorize(d.rec.astype(str) + '_' + d.fid.astype(str))[0]
    d = d.sort_values(['drv', 't'], kind='stable').reset_index(drop=True)
    vf = d.vf.to_numpy(float); vl = d.vl.to_numpy(float); gap = d.gap.to_numpy(float)
    st = (np.abs(vl - vf) < 1.0) & (vf > 5) & (gap > 0.5) & (gap < 100)
    lr = np.where(st, np.log(np.maximum(gap, 0.01) / np.maximum(vf, 0.1) / FD.t_gap(vf)), 0.0)
    drv = d.drv.to_numpy(); seg = d.seg.to_numpy()
    first = np.r_[True, drv[1:] != drv[:-1]]
    cs = np.cumsum(lr); cc = np.cumsum(st.astype(int))
    base_s = np.maximum.accumulate(np.where(first, np.arange(len(d)), 0))
    s0 = (cs - lr)[base_s]; c0 = (cc - st)[base_s]
    sB = cs - lr - s0; cB = cc - st - c0                     # strictly before this sample, same driver
    seg_first = np.r_[True, (seg[1:] != seg[:-1]) | (drv[1:] != drv[:-1])]
    bs = np.maximum.accumulate(np.where(seg_first, np.arange(len(d)), 0))
    sA = sB[bs]; cA = cB[bs]                                 # before the current segment began
    d['sA'], d['cA'], d['sB'], d['cB'] = sA, cA, sB, cB
    return d


def windows(d, H, every=25, open_only=False):
    seg = d.seg.to_numpy(); n = len(d); S = int(round(H / DT))
    vf = d.vf.to_numpy(float); gap = d.gap.to_numpy(float); vl = d.vl.to_numpy(float)
    start = np.r_[0, np.flatnonzero(np.diff(seg) != 0) + 1]
    pos = np.arange(n) - np.repeat(start, np.diff(np.r_[start, n]))
    ok = np.zeros(n, bool)
    ok[:n - S] = seg[:n - S] == seg[S:]
    ok &= (pos % every == 0) & (vf > 5.0) & (gap > 0.5) & (gap < 100) & np.isfinite(vl)
    ex = gap / np.maximum(vf, 1.0) - FD.t_gap(vf)
    if open_only:
        ok &= ex >= 1.0
    i = np.flatnonzero(ok)
    # the segment must be contiguous in time over the horizon
    tt = d.t.to_numpy()
    i = i[np.abs(tt[i + S] - tt[i] - H) < 0.5 * DT + 1e-6]
    return i, i + S


def decompose():
    import follow as F
    res = {}
    for name in F.DSETS:
        d = table_past(name)
        vf = d.vf.to_numpy(float); gap = d.gap.to_numpy(float)
        drv = d.drv.to_numpy()
        r = {}
        for which in ('A', 'B'):
            lf, rho = shrink(d[f's{which}'].to_numpy(), d[f'c{which}'].to_numpy())
            fp = np.exp(lf)
            has = d[f'c{which}'].to_numpy() >= 25
            e1 = (gap - gstar(vf, 1.0)) / np.maximum(vf, 1.0)          # error against the population's desired gap
            ef = (gap - gstar(vf, fp)) / np.maximum(vf, 1.0)           # against the driver's own (past) desired gap
            pers = e1 - ef
            rw = {}
            # open windows, P2's selection: share with a past, persistent share of the median excess, closing
            i0, i1 = windows(d, 30.0, open_only=True)
            ex = gap / np.maximum(vf, 1.0) - FD.t_gap(vf)
            rw['open_windows'] = int(len(i0))
            rw['share_with_past'] = round(float(has[i0].mean()), 3) if len(i0) else None
            k0, k1 = i0[has[i0]], i1[has[i0]]
            if len(k0) >= 30:
                rw['n_open_with_past'] = int(len(k0))
                rw['median_excess_s'] = round(float(np.median(ex[k0])), 3)
                rw['median_persistent_s'] = round(float(np.median(pers[k0])), 3)
                rw['persistent_share_of_excess'] = round(float(np.median(pers[k0]) / np.median(ex[k0])), 3)
                rw['mean_persistent_share'] = round(float(np.mean(pers[k0]) / np.mean(ex[k0])), 3)
                rw['closed_30s_whole'] = round(float(1 - np.median(ex[k1]) / np.median(ex[k0])), 3)
                # transient part at the end: the same driver, the same (past) factor
                ef1 = (gap[k1] - gstar(vf[k1], fp[k0])) / np.maximum(vf[k1], 1.0)
                rw['closed_30s_transient'] = round(float(1 - np.median(ef1) / np.median(ef[k0])), 3)
                rw['median_transient_s'] = [round(float(np.median(ef[k0])), 3), round(float(np.median(ef1)), 3)]
                rw['mean_rho'] = round(float(rho[k0].mean()), 3)
            # all windows with a past: regression of the change of e1 over H on the transient and persistent parts
            for H in (10.0, 30.0):
                j0, j1 = windows(d, H)
                j0, j1 = j0[has[j0]], j1[has[j0]]
                if len(j0) < 100:
                    continue
                de = e1[j1] - e1[j0]
                X = np.c_[ef[j0], pers[j0], np.ones(len(j0))]
                beta = np.linalg.lstsq(X, de, rcond=None)[0]
                g = drv[j0]; u, inv = np.unique(g, return_inverse=True)
                mem = [np.flatnonzero(inv == q) for q in range(len(u))]
                bs = []
                for _ in range(200):
                    pick = np.concatenate([mem[q] for q in rng.integers(0, len(u), len(u))])
                    bs.append(np.linalg.lstsq(X[pick], de[pick], rcond=None)[0][:2])
                bs = np.array(bs)
                # the whole excess on its own, for comparison
                b1 = np.linalg.lstsq(np.c_[e1[j0], np.ones(len(j0))], de, rcond=None)[0]
                rw[f'reg_{int(H)}s'] = dict(n=int(len(j0)), drivers=int(len(u)),
                                           transient=[round(float(-beta[0]), 3)] + [round(float(-x), 3) for x in np.percentile(bs[:, 0], [97.5, 2.5])],
                                           persistent=[round(float(-beta[1]), 3)] + [round(float(-x), 3) for x in np.percentile(bs[:, 1], [97.5, 2.5])],
                                           whole=round(float(-b1[0]), 3))
            r[which] = rw
        res[name] = r
        print(name, json.dumps(r), flush=True)
        del d
    save('decompose', res)


if __name__ == '__main__':
    globals()[sys.argv[1]]()
