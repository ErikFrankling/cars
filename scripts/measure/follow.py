"""Parts 2 and 4: car following in steady following, the response to gap error and closing speed, and the response lag.

One table of leader-follower samples at 5 Hz per dataset (cars behind cars, same lane, same leader):
  highD (levelX cache, real box lengths: bumper gap exact), TGSIM I-90/94 stationary, I-294 L1 and I-395 and DLR HT
  (report 05's caches; centre spacing minus 5 m, as report 05, since TGSIM lengths are defaults).
Held out (HOLDOUT.md): highD location 6, TGSIM I-90/94 moving, DLR HT after 14:00 UTC (not in report 05's cache).

    python3 -I scripts/measure/follow.py table          # -> cars-data/measure/follow/<ds>.npz
    python3 -I scripts/measure/follow.py steady         # F131 F132 F133 -> research/truth/measure/follow_steady.json
    python3 -I scripts/measure/follow.py response       # F134 F135     -> research/truth/measure/follow_response.json
    python3 -I scripts/measure/follow.py lag            # F138          -> research/truth/measure/follow_lag.json
"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.signal import savgol_filter

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import levelx as LX

RES = os.path.join(HERE, '..', '..', 'research', 'truth', 'measure')
TAB = '/home/erikf/projects/personal/cars-data/measure/follow'
C05 = '/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-cache'
TGSIM = {'I90stat': 'Wed 6 Oct 2021', 'I294L1': 'Oct 2021', 'I395': 'Thu 26 Jan 2023'}
rng = np.random.default_rng(20261106)


def q(v, ps=(5, 25, 50, 75, 95)):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    if not len(v):
        return {'n': 0}
    return {f'p{p}': round(float(np.percentile(v, p)), 3) for p in ps} | {'n': int(len(v))}


def boot_median(x, groups, reps=400):
    """Median with a 95% interval from resampling groups (vehicles or recordings), not samples."""
    x = np.asarray(x, float); g = pd.factorize(groups)[0]
    order = np.argsort(g); x = x[order]; g = g[order]
    cut = np.flatnonzero(np.diff(g)) + 1; parts = np.split(x, cut)
    k = len(parts); out = []
    for _ in range(reps):
        pick = rng.integers(0, k, k)
        out.append(np.median(np.concatenate([parts[i] for i in pick])))
    return [round(float(np.median(x)), 3), round(float(np.percentile(out, 2.5)), 3), round(float(np.percentile(out, 97.5)), 3)]


def deriv(v, seg, hz):
    """1 s local-quadratic derivative within each segment (NaN where a segment is shorter than 1 s)."""
    w = int(hz) + (1 - int(hz) % 2)
    out = np.full(len(v), np.nan)
    cut = np.flatnonzero(np.diff(seg)) + 1
    for a, b in zip(np.r_[0, cut], np.r_[cut, len(v)]):
        if b - a >= w:
            out[a:b] = savgol_filter(v[a:b], w, 2, deriv=1, delta=1.0 / hz)
    return out


# ---------------------------------------------------------------- tables
def table_highd():
    rows = []
    meta = LX.recordings('highD')
    for _, m in meta.iterrows():
        rec = int(m.rec)
        d = LX.tracks('highD', rec)
        cls = LX.tracks_meta('highD', rec).set_index('id')['class']
        car = cls.reindex(d.id).values == 'Car'
        d['v'] = np.abs(d.vx)
        key = pd.MultiIndex.from_arrays([d.frame, d.id])
        look = pd.Series(np.arange(len(d)), index=key)
        f = d[(d.prec > 0) & car].copy()
        li = look.reindex(pd.MultiIndex.from_arrays([f.frame, f.prec])).to_numpy()
        ok = np.isfinite(li); f = f[ok]; li = li[ok].astype(int)
        f['vl'] = d.v.to_numpy()[li]; f['Ll'] = d.length.to_numpy()[li]
        f['lcar'] = cls.reindex(d.id.to_numpy()[li]).values == 'Car'
        f = f.sort_values(['id', 'frame'])
        fr, ii, pr, ln = f.frame.to_numpy(), f.id.to_numpy(), f.prec.to_numpy(), f.lane.to_numpy()
        brk = np.r_[True, (ii[1:] != ii[:-1]) | (pr[1:] != pr[:-1]) | (fr[1:] != fr[:-1] + 1) | (ln[1:] != ln[:-1])]
        seg = np.cumsum(brk)
        af = deriv(f.v.to_numpy(float), seg, 25); al = deriv(f.vl.to_numpy(float), seg, 25)
        keep = (fr % 5 == 0)
        rows.append(pd.DataFrame(dict(site=int(m.site), day=m.day, rec=rec, seg=seg[keep] + rec * 1_000_000, fid=ii[keep] + rec * 100_000,
                                      lid=pr[keep] + rec * 100_000, t=fr[keep] / 25.0, gap=f.dhw.to_numpy()[keep], vf=f.v.to_numpy()[keep],
                                      vl=f.vl.to_numpy()[keep], af=af[keep], al=al[keep], Lf=f.length.to_numpy()[keep],
                                      Ll=f.Ll.to_numpy()[keep], lcar=f.lcar.to_numpy()[keep])))
        print('highD', rec, len(rows[-1]), flush=True)
    return pd.concat(rows, ignore_index=True)


def table_cache(name):
    z = np.load(f'{C05}/pairs_{name}.npz')
    hz = 10
    keep = (z['t'] % 2 == 0)
    tf, tl = z['tf'], z['tl']
    car_f = tf == 1; car_l = tl == 1
    seg = z['seg']; vf = z['vf'].astype(float); vl = z['vl'].astype(float)
    af = deriv(vf, seg, hz); al = deriv(vl, seg, hz)
    auto = (z['autof'] != 0) | (z['autol'] != 0)
    m = keep & car_f & ~auto
    site = 'DLR HT' if name == 'HT' else name
    day = 'Mon' if name == 'HT' else TGSIM.get(name, '')
    return pd.DataFrame(dict(site=site, day=day, rec=z['run'][m], seg=seg[m], fid=z['fid'][m], lid=z['lid'][m], t=z['t'][m] / 10.0,
                             gap=z['cc'][m] - 5.0, vf=vf[m], vl=vl[m], af=af[m], al=al[m], Lf=z['Lf'][m], Ll=z['Ll'][m], lcar=car_l[m]))


def table():
    os.makedirs(TAB, exist_ok=True)
    for name, fn in [('highD', table_highd)] + [(n, lambda n=n: table_cache(n)) for n in ('HT', 'I90stat', 'I294L1', 'I395')]:
        d = fn()
        np.savez(f'{TAB}/{name}.npz', **{c: d[c].to_numpy() for c in d.columns})
        print(name, len(d), d.fid.nunique(), flush=True)


def load(name):
    z = np.load(f'{TAB}/{name}.npz', allow_pickle=True)
    return pd.DataFrame({k: z[k] for k in z.files})


DSETS = ['highD', 'HT', 'I90stat', 'I294L1', 'I395']


# ---------------------------------------------------------------- steady following
def runs(mask, seg):
    """Start and end index of each run of True inside one segment."""
    m = mask.astype(np.int8)
    edge = np.r_[True, seg[1:] != seg[:-1]]
    start = m.astype(bool) & (edge | np.r_[True, m[:-1] == 0])
    end = m.astype(bool) & (np.r_[seg[1:] != seg[:-1], True] | np.r_[m[1:] == 0, True])
    return np.flatnonzero(start), np.flatnonzero(end) + 1


def steady_windows(d, vmin, dvmax=1.0, dur=10.0, gapmax=100.0):
    m = (np.abs(d.vl - d.vf) < dvmax) & (d.vf > vmin) & (d.gap > 0.3) & (d.gap < gapmax) & d.lcar.astype(bool)
    s, e = runs(m.to_numpy(), d.seg.to_numpy())
    long = (e - s) >= dur * 5
    s, e = s[long], e[long]
    tg = (d.gap / d.vf).to_numpy()
    rows = []
    for a, b in zip(s, e):
        rows.append((d.fid.iat[a], d.site.iat[a], d.day.iat[a], d.rec.iat[a], float(np.median(tg[a:b])), float(np.median(d.vf.iat[a] if b - a == 1 else d.vf.to_numpy()[a:b])),
                     float(np.median(d.gap.to_numpy()[a:b])), (b - a) / 5.0))
    return pd.DataFrame(rows, columns=['fid', 'site', 'day', 'rec', 'tg', 'v', 'gap', 'dur'])


def standstill(d):
    m = (d.vf < 0.3) & (d.vl < 0.3) & d.lcar.astype(bool) & (d.gap > -1)
    s, e = runs(m.to_numpy(), d.seg.to_numpy())
    long = (e - s) >= 10
    return pd.DataFrame([(d.fid.iat[a], d.site.iat[a], float(np.median(d.gap.to_numpy()[a:b]))) for a, b in zip(s[long], e[long])],
                        columns=['fid', 'site', 'gap'])


def steady():
    out = {}
    for name in DSETS:
        d = load(name)
        r = {}
        w = steady_windows(d, 15.0)
        if len(w):
            r['v_over_15'] = dict(windows=len(w), vehicles=int(w.fid.nunique()), time_gap_s=q(w.tg), median_ci_by_vehicle=boot_median(w.tg, w.fid),
                                  log_sd=round(float(np.log(w.tg).std()), 3), gap_m=q(w.gap), speed=q(w.v))
        w5 = steady_windows(d, 3.0)
        bands = {}
        for lo, hi in [(3, 10), (10, 15), (15, 20), (20, 25), (25, 30), (30, 35), (35, 45)]:
            k = w5[(w5.v >= lo) & (w5.v < hi)]
            if len(k) >= 30:
                bands[f'{lo}-{hi}'] = dict(windows=len(k), time_gap_s=q(k.tg), median_ci_by_vehicle=boot_median(k.tg, k.fid, 200))
        r['by_speed'] = bands
        if name == 'highD' and len(w):
            r['by_site_day'] = {f'{s} {dd}': dict(windows=len(k), median_ci=boot_median(k.tg, k.fid, 200), p5=round(float(k.tg.quantile(.05)), 3), p95=round(float(k.tg.quantile(.95)), 3))
                                for (s, dd), k in w.groupby(['site', 'day']) if len(k) >= 30}
            # Linear steady state: spacing against speed, as a check on the time gap and the standstill intercept.
            A = np.c_[np.ones(len(w5)), w5.v]; c = np.linalg.lstsq(A, w5.gap, rcond=None)[0]
            r['gap_vs_speed_fit'] = dict(intercept_m=round(float(c[0]), 2), slope_s=round(float(c[1]), 3))
        ss = standstill(d)
        r['standstill_gap_m'] = dict(q(ss.gap, (10, 25, 50, 75, 90)), vehicles=int(ss.fid.nunique()),
                                     median_ci=boot_median(ss.gap, ss.fid, 200) if len(ss) > 20 else None)
        r['note'] = 'bumper gap from real box lengths' if name == 'highD' else 'centre spacing minus 5 m (report 05 convention)'
        out[name] = r
        print(name, json.dumps(r)[:600], flush=True)
    json.dump(out, open(os.path.join(RES, 'follow_steady.json'), 'w'), indent=1)


# ---------------------------------------------------------------- response
def response_samples(d, vmin=5.0):
    """State at t and the mean acceleration over the next second, inside one leader-follower segment."""
    d = d[d.lcar.astype(bool)].reset_index(drop=True)
    seg = d.seg.to_numpy(); vf = d.vf.to_numpy(float)
    nxt = np.r_[seg[5:] == seg[:-5], np.zeros(5, bool)]
    y = np.full(len(d), np.nan); y[:-5] = (vf[5:] - vf[:-5]) / 1.0
    y[~nxt] = np.nan
    tg = d.gap.to_numpy() / np.maximum(vf, 0.1)
    steady = (np.abs(d.vl - d.vf) < 1.0).to_numpy() & (vf > vmin)
    # Each follower's own reference: median time gap over its steady samples, all leaders.
    own = pd.Series(np.where(steady, tg, np.nan)).groupby(d.fid.to_numpy()).transform('median').to_numpy()
    nown = pd.Series(steady.astype(int)).groupby(d.fid.to_numpy()).transform('sum').to_numpy()
    out = pd.DataFrame(dict(fid=d.fid, site=d.site, y=y, tg=tg, own=own, nown=nown, dv=(d.vl - d.vf).to_numpy(), v=vf,
                            gap=d.gap.to_numpy(), al=d.al.to_numpy(), af=d.af.to_numpy()))
    return out[(vf > vmin) & np.isfinite(y) & np.isfinite(out.al) & (out.gap > 0.5) & (out.gap < 120)].reset_index(drop=True)


def hinge_design(e, dv, al, b, dd):
    ce = np.clip(e, -b, b); cd = np.clip(dv, -dd, dd)
    return np.c_[np.ones(len(e)), ce, e - ce, cd, dv - cd, al]


def fit(X, y):
    c, res, *_ = np.linalg.lstsq(X, y, rcond=None)
    sse = float(((y - X @ c) ** 2).sum())
    return c, sse


def bic(sse, n, k):
    return n * np.log(sse / n) + k * np.log(n)


def hinge_search(e, dv, al, y, bs, ds):
    best = None
    for b in bs:
        for dd in ds:
            X = hinge_design(e, dv, al, b, dd)
            c, sse = fit(X, y)
            if best is None or sse < best[0]:
                best = (sse, b, dd, c)
    return best


def response():
    out = {}
    BS = np.round(np.arange(0.0, 1.61, 0.1), 2); DS = np.round(np.arange(0.0, 1.61, 0.1), 2)
    for name in DSETS:
        d = load(name)
        uf0 = d.fid.unique()
        if len(uf0) > 15000:
            d = d[d.fid.isin(rng.choice(uf0, 15000, replace=False))].reset_index(drop=True)
        s = response_samples(d)
        r = {'samples': len(s), 'followers': int(s.fid.nunique()), 'followers_sampled_from': int(len(uf0))}
        for ref in ('own', 'population'):
            if ref == 'own':
                k = s[(s.nown >= 25)].copy(); k['e'] = k.tg - k.own
            else:
                k = s.copy()
                vb = np.clip((k.v // 5).astype(int), 0, 8)
                med = k[np.abs(k.dv) < 1].groupby(vb[np.abs(k.dv) < 1]).tg.median()
                k['e'] = k.tg - med.reindex(vb).to_numpy()
            k = k[np.isfinite(k.e) & (np.abs(k.e) < 4) & (np.abs(k.dv) < 6)]
            if len(k) < 2000:
                continue
            uf_all = k.fid.unique()
            if len(k) > 800_000:
                keep = rng.choice(uf_all, int(len(uf_all) * 800_000 / len(k)), replace=False)
                k = k[k.fid.isin(keep)]
            e, dv, al, y = k.e.to_numpy(), k.dv.to_numpy(), k.al.to_numpy(), k.y.to_numpy()
            # Conditional means: gap error at small closing speed, closing speed at small gap error.
            grid_e = {}
            sm = np.abs(dv) < 0.5
            for lo in np.arange(-2.0, 2.0, 0.25):
                mm = sm & (e >= lo) & (e < lo + 0.25)
                if mm.sum() >= 50:
                    grid_e[f'{lo:+.2f}'] = [round(float(y[mm].mean()), 3), int(mm.sum())]
            grid_dv = {}
            se = np.abs(e) < 0.3
            for lo in np.arange(-4.0, 4.0, 0.5):
                mm = se & (dv >= lo) & (dv < lo + 0.5)
                if mm.sum() >= 50:
                    grid_dv[f'{lo:+.1f}'] = [round(float(y[mm].mean()), 3), int(mm.sum())]
            sse_lin = fit(hinge_design(e, dv, al, 0.0, 0.0), y)[1]
            sse, b, dd, c = hinge_search(e, dv, al, y, BS, DS)
            n = len(y)
            # Band on gap error only, closing speed linear, and dead zone only: which part carries the gain.
            sse_b, b_only, _, c_b = hinge_search(e, dv, al, y, BS, [0.0])
            sse_d, _, d_only, c_d = hinge_search(e, dv, al, y, [0.0], DS)
            # Bootstrap by follower on a subsample, refitting the band edges on a coarse grid.
            fids = k.fid.to_numpy(); uf = np.unique(fids)
            sub = rng.choice(uf, min(len(uf), 2500), replace=False)
            idx_by = pd.Series(np.arange(len(fids))).groupby(fids).apply(np.array)
            boots = []
            for _ in range(40):
                pick = rng.choice(sub, len(sub))
                ii = np.concatenate([idx_by[f] for f in pick])
                _, bb, ddb, cb = hinge_search(e[ii], dv[ii], al[ii], y[ii], BS[::2], DS[::2])
                boots.append((bb, ddb, cb[1], cb[2], cb[3], cb[4], cb[5]))
            B = np.array(boots)
            ci = lambda col: [round(float(np.percentile(B[:, col], 2.5)), 3), round(float(np.percentile(B[:, col], 97.5)), 3)]
            ratio = np.where(np.abs(B[:, 2]) > 1e-4, B[:, 3] / np.where(np.abs(B[:, 2]) > 1e-4, B[:, 2], 1), np.inf)
            r[ref] = dict(samples=n, followers=int(len(uf)), mean_y=round(float(y.mean()), 3),
                          cond_mean_by_gap_error_at_dv_under_0_5=grid_e, cond_mean_by_dv_at_gap_error_under_0_3=grid_dv,
                          linear=dict(coef=[round(float(x), 4) for x in fit(hinge_design(e, dv, al, 0, 0), y)[0]], bic=round(bic(sse_lin, n, 4), 1)),
                          hinge=dict(band_s=float(b), dead_zone_ms=float(dd), coef=dict(const=round(float(c[0]), 4), gain_in=round(float(c[1]), 4),
                                     gain_out=round(float(c[2]), 4), dv_in=round(float(c[3]), 4), dv_out=round(float(c[4]), 4), leader_acc=round(float(c[5]), 4)),
                                     bic=round(bic(sse, n, 8), 1), bic_gain_over_linear=round(bic(sse_lin, n, 4) - bic(sse, n, 8), 1),
                                     r2=round(1 - sse / float(((y - y.mean()) ** 2).sum()), 4)),
                          band_only=dict(band_s=float(b_only), gain_in=round(float(c_b[1]), 4), gain_out=round(float(c_b[2]), 4), bic_gain=round(bic(sse_lin, n, 4) - bic(sse_b, n, 6), 1)),
                          dead_zone_only=dict(dead_zone_ms=float(d_only), dv_in=round(float(c_d[3]), 4), dv_out=round(float(c_d[4]), 4), bic_gain=round(bic(sse_lin, n, 4) - bic(sse_d, n, 6), 1)),
                          bootstrap_by_follower=dict(reps=len(B), band_s=ci(0), dead_zone_ms=ci(1), gain_in=ci(2), gain_out=ci(3), dv_in=ci(4), dv_out=ci(5),
                                                     ratio_out_in=[round(float(np.percentile(ratio, 2.5)), 2), round(float(np.percentile(ratio, 50)), 2), round(float(np.percentile(ratio, 97.5)), 2)]))
        r['action_points'] = action_points(d)
        out[name] = r
        print(name, json.dumps({kk: (vv.get('hinge') if isinstance(vv, dict) else vv) for kk, vv in r.items()})[:900], flush=True)
    json.dump(out, open(os.path.join(RES, 'follow_response.json'), 'w'), indent=1)


def action_points(d):
    """Wiedemann-style action points: where the follower's smoothed acceleration changes sign and keeps it for 1 s.
    |dv| there, by spacing, is the closing speed the driver let build before responding."""
    d = d[d.lcar.astype(bool) & (d.vf > 3)].reset_index(drop=True)
    af = d.af.to_numpy(); seg = d.seg.to_numpy()
    sgn = np.sign(af)
    ok = np.isfinite(af)
    same5 = np.r_[seg[5:] == seg[:-5], np.zeros(5, bool)]
    flip = np.r_[False, (sgn[1:] != sgn[:-1]) & (seg[1:] == seg[:-1])] & same5 & ok
    keep = np.zeros(len(d), bool)
    for i in np.flatnonzero(flip):
        if np.all(sgn[i:i + 5] == sgn[i]):
            keep[i] = True
    k = d[keep]
    out = {}
    for lo, hi in [(5, 15), (15, 25), (25, 40), (40, 60), (60, 100)]:
        m = (k.gap >= lo) & (k.gap < hi)
        if m.sum() >= 50:
            adv = np.abs(k.vl - k.vf)[m]
            out[f'{lo}-{hi} m'] = dict(n=int(m.sum()), abs_dv=q(adv, (25, 50, 75)))
    return out


# ---------------------------------------------------------------- lag
def lag():
    out = {}
    taus = np.round(np.arange(0.0, 3.01, 0.2), 1)
    for name in DSETS:
        d = load(name)
        d = d[d.lcar.astype(bool) & (d.vf > 3) & (d.gap > 0.5) & (d.gap < 120)].reset_index(drop=True)
        seg = d.seg.to_numpy(); af = d.af.to_numpy()
        groups = [('all', d)] + ([(f'site {s}', g) for s, g in d.groupby('site')] if name == 'highD' else [])
        res = {}
        for label, g in groups:
            g = g.reset_index(drop=True); sg = g.seg.to_numpy(); a = g.af.to_numpy()
            X = np.c_[np.ones(len(g)), g.gap, g.vf, g.vl - g.vf]
            r2 = {}; r2dv = {}; xc = {}
            for tau in taus:
                k = int(round(tau * 5))
                yy = np.full(len(g), np.nan)
                if k == 0:
                    yy = a.copy()
                else:
                    yy[:-k] = np.where(sg[k:] == sg[:-k], a[k:], np.nan)
                m = np.isfinite(yy) & np.isfinite(X).all(1)
                c, sse = fit(X[m], yy[m]); sst = float(((yy[m] - yy[m].mean()) ** 2).sum())
                r2[float(tau)] = round(1 - sse / sst, 4)
                c2, sse2 = fit(X[m][:, [0, 3]], yy[m]); r2dv[float(tau)] = round(1 - sse2 / sst, 4)
                al = g.al.to_numpy(); mm = m & np.isfinite(al)
                xc[float(tau)] = round(float(np.corrcoef(al[mm], yy[mm])[0, 1]), 4)
            best = max(r2, key=r2.get); bestdv = max(r2dv, key=r2dv.get); bestxc = max(xc, key=xc.get)
            # Finer search around the optimum on the 5 Hz grid is its resolution: 0.2 s. Bootstrap the argmax by follower.
            fids = g.fid.to_numpy(); uf = np.unique(fids)
            sub = rng.choice(uf, min(len(uf), 2000), replace=False)
            idx_by = pd.Series(np.arange(len(fids))).groupby(fids).apply(np.array)
            bt = []
            Ys = {}
            for tau in taus:
                k = int(round(tau * 5)); yy = np.full(len(g), np.nan)
                if k == 0: yy = a.copy()
                else: yy[:-k] = np.where(sg[k:] == sg[:-k], a[k:], np.nan)
                Ys[float(tau)] = yy
            for _ in range(30):
                ii = np.concatenate([idx_by[f] for f in rng.choice(sub, len(sub))])
                sc = {}
                for tau, yy in Ys.items():
                    m = np.isfinite(yy[ii]) & np.isfinite(X[ii]).all(1)
                    c, sse = fit(X[ii][m], yy[ii][m]); sc[tau] = 1 - sse / float(((yy[ii][m] - yy[ii][m].mean()) ** 2).sum())
                bt.append(max(sc, key=sc.get))
            res[label] = dict(samples=len(g), followers=int(len(uf)), best_lag_s=best, best_lag_ci=[float(np.percentile(bt, 2.5)), float(np.percentile(bt, 97.5))],
                              r2_by_lag=r2, best_lag_dv_only_s=bestdv, leader_acc_xcorr_peak_s=bestxc, xcorr=xc)
        out[name] = res
        print(name, {k: (v['best_lag_s'], v['best_lag_ci'], v['best_lag_dv_only_s'], v['leader_acc_xcorr_peak_s']) for k, v in res.items()}, flush=True)
    json.dump(out, open(os.path.join(RES, 'follow_lag.json'), 'w'), indent=1)


def kernel():
    """Distributed lag: a_f(t) = c + g gap(t) + h v(t) + sum_j w_j dv(t - j*0.2 s), j = 0..15 (0-3 s), fitted jointly.
    The weights w_j are the follower's response to closing speed j*0.2 s ago. A dead time d and first-order time constant
    T are fitted to them: w(t) = K exp(-(t - d) / T) / T for t >= d, else 0 (report 05's filter is d = 0, T = 0.66 s)."""
    from scipy.optimize import least_squares
    out = {}
    J = 16
    lagsec = np.arange(J) * 0.2
    for name in DSETS:
        d = load(name)
        d = d[d.lcar.astype(bool) & (d.vf > 3) & (d.gap > 0.5) & (d.gap < 120)].reset_index(drop=True)
        seg = d.seg.to_numpy(); dv = (d.vl - d.vf).to_numpy(np.float32)
        ok = np.ones(len(d), bool); cols = []
        for j in range(J):
            x = np.full(len(d), np.nan, np.float32)
            if j == 0: x = dv.copy()
            else:
                x[j:] = np.where(seg[j:] == seg[:-j], dv[:-j], np.nan)
            cols.append(x); ok &= np.isfinite(x)
        X = np.c_[np.ones(len(d)), d.gap, d.vf, np.column_stack(cols)][ok].astype(np.float64)
        y = d.af.to_numpy()[ok]; m = np.isfinite(y); X, y = X[m], y[m]
        fids = d.fid.to_numpy()[ok][m]
        def fitk(X, y):
            c = np.linalg.lstsq(X, y, rcond=None)[0]; w = c[3:]
            f = lambda p: np.where(lagsec >= p[1], p[0] * np.exp(-(lagsec - p[1]) / p[2]) / p[2], 0.0) - w
            best = None
            for d0 in (0.0, 0.4, 0.8, 1.2):
                r = least_squares(f, [max(w.sum(), 1e-3), d0, 0.6], bounds=([0, 0, 0.05], [5, 3, 10]))
                if best is None or r.cost < best.cost: best = r
            cen = float((w.clip(0) * lagsec).sum() / max(w.clip(0).sum(), 1e-9))
            return w, best.x, cen
        w, p, cen = fitk(X, y)
        uf = np.unique(fids); sub = rng.choice(uf, min(len(uf), 3000), replace=False)
        by = pd.Series(np.arange(len(fids))).groupby(fids).apply(np.array)
        B = []
        for _ in range(30):
            ii = np.concatenate([by[f] for f in rng.choice(sub, len(sub))])
            _, pb, cb = fitk(X[ii], y[ii]); B.append((pb[1], pb[2], cb, pb[0]))
        B = np.array(B)
        ci = lambda k: [round(float(np.percentile(B[:, k], 2.5)), 2), round(float(np.percentile(B[:, k], 97.5)), 2)]
        out[name] = dict(samples=int(len(y)), followers=int(len(uf)), kernel_per_lag_s={f'{t:.1f}': round(float(x), 4) for t, x in zip(lagsec, w)},
                         total_gain=round(float(w.sum()), 3), dead_time_s=round(float(p[1]), 2), dead_time_ci=ci(0),
                         time_constant_s=round(float(p[2]), 2), time_constant_ci=ci(1), centroid_s=round(cen, 2), centroid_ci=ci(2),
                         fitted_gain=round(float(p[0]), 3))
        print(name, json.dumps({k: v for k, v in out[name].items() if k != 'kernel_per_lag_s'}), flush=True)
    json.dump(out, open(os.path.join(RES, 'follow_kernel.json'), 'w'), indent=1)


def kernel_leader():
    """Response to the leader alone: a_f(t) = c + sum_j h_j a_l(t - j*0.2 s), j from -5 (1 s ahead) to 15 (3 s back).
    The leader's acceleration comes from its own track, so the follower's smoothing cannot leak into it; weights at
    negative lags (the follower 'answering' before the leader moves) show how much the shared traffic state and the
    smoother spread things. Onset = first lag where h exceeds 20% of its peak; centroid = mean lag of the positive part."""
    out = {}
    J0, J1 = -5, 15
    lags = np.arange(J0, J1 + 1)
    lagsec = lags * 0.2
    for name in DSETS:
        d = load(name)
        d = d[d.lcar.astype(bool) & (d.vf > 3) & (d.gap > 0.5) & (d.gap < 120)].reset_index(drop=True)
        seg = d.seg.to_numpy(); al = d.al.to_numpy(np.float64); n = len(d)
        cols, ok = [], np.isfinite(d.af.to_numpy())
        for j in lags:
            x = np.full(n, np.nan)
            if j == 0: x = al.copy()
            elif j > 0: x[j:] = np.where(seg[j:] == seg[:-j], al[:-j], np.nan)
            else: x[:j] = np.where(seg[:j] == seg[-j:], al[-j:], np.nan)
            cols.append(x); ok &= np.isfinite(x)
        X = np.c_[np.ones(ok.sum()), np.column_stack(cols)[ok]]; y = d.af.to_numpy()[ok]; fids = d.fid.to_numpy()[ok]
        def fitk(X, y):
            h = np.linalg.lstsq(X, y, rcond=None)[0][1:]
            pk = h.max(); on = lagsec[np.flatnonzero(h >= 0.2 * pk)[0]] if pk > 0 else np.nan
            hp = np.clip(h, 0, None); cen = float((hp * lagsec).sum() / max(hp.sum(), 1e-9))
            return h, float(on), cen, float(lagsec[np.argmax(h)])
        h, on, cen, peak = fitk(X, y)
        uf = np.unique(fids); sub = rng.choice(uf, min(len(uf), 3000), replace=False)
        by = pd.Series(np.arange(len(fids))).groupby(fids).apply(np.array)
        B = []
        for _ in range(30):
            ii = np.concatenate([by[f] for f in rng.choice(sub, len(sub))])
            _, o, c, p_ = fitk(X[ii], y[ii]); B.append((o, c, p_))
        B = np.array(B)
        ci = lambda k: [round(float(np.nanpercentile(B[:, k], 2.5)), 2), round(float(np.nanpercentile(B[:, k], 97.5)), 2)]
        out[name] = dict(samples=int(len(y)), followers=int(len(uf)), kernel={f'{t:+.1f}': round(float(x), 4) for t, x in zip(lagsec, h)},
                         onset_s=on, onset_ci=ci(0), centroid_s=round(cen, 2), centroid_ci=ci(1), peak_s=peak, peak_ci=ci(2),
                         share_of_weight_at_negative_lags=round(float(np.clip(h[lagsec < 0], 0, None).sum() / max(np.clip(h, 0, None).sum(), 1e-9)), 3),
                         total_gain=round(float(h.sum()), 3))
        print(name, json.dumps({k: v for k, v in out[name].items() if k != 'kernel'}), flush=True)
    json.dump(out, open(os.path.join(RES, 'follow_kernel_leader.json'), 'w'), indent=1)


if __name__ == '__main__':
    os.makedirs(RES, exist_ok=True)
    {'table': table, 'steady': steady, 'response': response, 'lag': lag, 'kernel': kernel, 'kernel_leader': kernel_leader}[sys.argv[1]]()
