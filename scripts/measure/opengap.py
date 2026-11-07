"""Round 5 of the measured driver, part 1: why do open gaps stay open? Three causes, each as a conditional closing rate on
P2's open windows, and each put into the twin of round 4's strongest-pull law (f). Forecasts F830-F834, research/truth/
measure/OPENGAP.md. Recordings not held out (HOLDOUT.md): follow.py's DLR HT 06-14 UTC, TGSIM I-90/94 stationary, I-294 L1,
I-395, with their raw tracks for lateral positions and free driving (TGSIM CSVs, dlrht.py blocks 0-23 only), and highD
without location 6 for the pairing check.

    python3 -I scripts/measure/opengap.py build        # annotated open windows per table -> cars-data/measure/md5
    python3 -I scripts/measure/opengap.py free         # F830
    python3 -I scripts/measure/opengap.py second       # F831
    python3 -I scripts/measure/opengap.py pairing      # F832 (and highD)
    python3 -I scripts/measure/opengap.py explain      # F833 F834
"""
import os, sys, json, math, pickle
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
RES = os.path.join(HERE, '..', '..', 'research', 'truth', 'measure')
OUT = os.path.join(RES, 'opengap.json')
CACHE = '/home/erikf/projects/personal/cars-data/measure/md5'
TG = '/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-tgsim'
HTB = '/home/erikf/projects/personal/cars-data/measure/dlrht'
HT_BLOCKS = range(24)        # 06:00-14:00 UTC. Blocks 24-29 (14:00-16:00) are held out and never opened here.
import fit_driver as FD

DT = 0.2
S = 150                      # 30 s at 5 Hz
HIST = 15
LINE = 1.5                   # a vehicle is on the follower's line within this lateral distance, m
ALIGN = 1.0                  # a certain pair: centres within this lateral distance at every sample, m
FREE = 150.0                 # free driving: nothing on the line within this distance ahead, m
TABLES = ['HT', 'I90stat', 'I294L1', 'I395']
rng = np.random.default_rng(830)


def save(key, val):
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    out[key] = val
    json.dump(out, open(OUT, 'w'), indent=1)


# ---------------------------------------------------------------- raw tracks in a road frame
def line_leaders(e):
    """e: one frame set with run, ti, dir, s, d, v, id. Adds the nearest vehicle ahead on the vehicle's own line (|d| within
    LINE), whatever its lane label: ll_id (-1 if none), ll_cc (centre spacing), ll_v, ll_d."""
    o = np.lexsort((e['s'].to_numpy(), e['dir'].to_numpy(), e['ti'].to_numpy(), e['run'].to_numpy()))
    e = e.iloc[o].reset_index(drop=True)
    run, ti, di = e.run.to_numpy(), e.ti.to_numpy(), e.dir.to_numpy()
    s, d, v, ids = e.s.to_numpy(float), e.d.to_numpy(float), e.v.to_numpy(float), e.id.to_numpy()
    n = len(e)
    found = np.full(n, -1, np.int64)
    for k in range(1, 16):
        j = np.arange(n) + k
        okj = j < n
        j = np.minimum(j, n - 1)
        same = okj & (run[j] == run) & (ti[j] == ti) & (di[j] == di)
        hit = same & (found < 0) & (np.abs(d[j] - d) < LINE) & (s[j] > s)
        found[hit] = j[hit]
    has = found >= 0
    jj = np.where(has, found, 0)
    e['ll_id'] = np.where(has, ids[jj], -1)
    e['ll_cc'] = np.where(has, s[jj] - s, np.nan)
    e['ll_v'] = np.where(has, v[jj], np.nan)
    e['ll_d'] = np.where(has, d[jj], np.nan)
    # the end of the observed road ahead, per run and direction: nothing ahead there is not free
    send = e.groupby(['run', 'dir']).s.transform(lambda x: np.nanpercentile(x, 99.5)).to_numpy()
    e['free'] = (~has | (e.ll_cc.to_numpy() > FREE)) & (s + FREE <= send)
    return e


def shape_correction(u, w, lab, sg):
    """Road curvature in the frame: median over lane labels of each label's lateral centre by 10 m station bin, each label
    taken relative to its own median. Returns w minus that shape."""
    out = np.array(w, float)
    for g in np.unique(sg):
        m = sg == g
        b = np.floor(u[m] / 10).astype(int)
        df = pd.DataFrame(dict(b=b, w=w[m], lab=lab[m]))
        c = df.groupby(['lab', 'b']).w.median()
        c = c - c.groupby(level=0).transform('median')
        cnt = df.groupby(['lab', 'b']).size()
        c = c[cnt >= 30]
        sh = c.groupby(level=1).median()
        bb = np.arange(b.min(), b.max() + 1)
        shp = np.interp(bb, sh.index.to_numpy(), pd.Series(sh.to_numpy()).rolling(5, center=True, min_periods=1).median().to_numpy())
        out[m] = w[m] - shp[b - b.min()]
    return out


def mkrefs(d, sigma=15):
    """dlrht.mkrefs for short, curved TGSIM sites: only the directions present, and 30 m smoothing instead of 200 m."""
    from scipy.ndimage import gaussian_filter1d
    from scipy.spatial import cKDTree
    g = d.groupby('id'); ends = g.agg(x0=('x', 'first'), y0=('y', 'first'), x1=('x', 'last'), y1=('y', 'last'))
    ends['len'] = np.hypot(ends.x1 - ends.x0, ends.y1 - ends.y0)
    pts = d[['x', 'y']].values[::50]; c = pts.mean(0); _, _, vt = np.linalg.svd(pts - c, full_matrices=False); ax = vt[0]
    ends['dir'] = np.sign((ends.x1 - ends.x0) * ax[0] + (ends.y1 - ends.y0) * ax[1])
    R = {}
    for sg in (-1, 1):
        cand = ends[(ends['dir'] == sg)]
        if len(cand) < 20:
            continue
        best = cand.sort_values('len').index[-1]
        t = d[d['id'] == best].sort_values('ti'); xy = t[['x', 'y']].values.astype('f8')
        seg = np.r_[0, np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]; ss = np.arange(0, seg[-1], 2.0)
        rx = gaussian_filter1d(np.interp(ss, seg, xy[:, 0]), sigma, mode='nearest'); ry = gaussian_filter1d(np.interp(ss, seg, xy[:, 1]), sigma, mode='nearest')
        tx = np.gradient(rx); ty = np.gradient(ry); n = np.hypot(tx, ty)
        R[sg] = dict(x=rx, y=ry, tx=tx / n, ty=ty / n, tree=cKDTree(np.c_[rx, ry]), len=seg[-1])
    return R


def centres(d, LW=3.75):
    """dlrht.centres for the directions present."""
    from scipy.ndimage import gaussian_filter1d, median_filter
    C = {}
    for sg in np.unique(d['dir'].values):
        m = (d['dir'].values == sg) & (np.abs(d['dd'].values) < 12)
        s = d['s'].values[m]; dd = d['dd'].values[m]
        bins = (s / 100).astype(int); nb = bins.max() + 1; c = np.full(nb, np.nan)
        for b in range(nb):
            z_ = dd[bins == b]
            if len(z_) < 300:
                continue
            h, e = np.histogram(z_, bins=np.arange(-12, 12.01, .25)); hs = gaussian_filter1d(h.astype(float), 2)
            c[b] = e[np.argmax(hs)] + .125
        v = np.where(np.isfinite(c))[0]
        if not len(v):
            C[sg] = np.zeros(nb); continue
        cc = np.interp(np.arange(nb), v, c[v])
        for i in range(1, nb):
            while cc[i] - cc[i - 1] > LW / 2: cc[i] -= LW
            while cc[i] - cc[i - 1] < -LW / 2: cc[i] += LW
        C[sg] = gaussian_filter1d(median_filter(cc, min(9, nb)), 1)
    return C


def raw_tgsim(name):
    want = {'id', 'time', 'xloc_kf', 'yloc_kf', 'lane_kf', 'speed_kf', 'length_smoothed', 'type_most_common', 'run_index'}
    d = pd.read_csv(f'{TG}/{name}.csv', usecols=lambda c: c in want, dtype={'lane_kf': 'float32'})
    if 'run_index' not in d:
        d['run_index'] = 0
    d = d.drop_duplicates(['run_index', 'id', 'time'])
    ti = np.round(d.time.to_numpy() * 10).astype(np.int64)
    d = d[(ti % 2 == 0) & np.isfinite(d.xloc_kf.to_numpy()) & np.isfinite(d.yloc_kf.to_numpy())].copy()
    d['ti'] = np.round(d.time.to_numpy() * 10).astype(np.int64)
    # Leaders as report 05 paired them (opus_pairs.py): the next vehicle with the same lane label along the site's axis,
    # centre spacing as the straight distance. Lateral checks use the leader's own driven path (path_checks), which needs
    # no road frame: these sites curve and I-90/94 has two roadways in one direction.
    axis = 'yloc_kf' if name == 'I395' else 'xloc_kf'
    d = d.sort_values(['run_index', 'id', 'ti'])
    du = d.groupby(['run_index', 'id'])[axis].diff()
    sg = np.sign(du.groupby([d.run_index, d.id]).transform('median')).fillna(0).to_numpy()
    keep = sg != 0
    d = d[keep]; sg = sg[keep]
    e = pd.DataFrame(dict(run=d.run_index.to_numpy(), ti=d.ti.to_numpy(), id=d.id.to_numpy(), dir=sg.astype(np.int8), s=d[axis].to_numpy(float) * sg,
                          x=d.xloc_kf.to_numpy(float), y=d.yloc_kf.to_numpy(float), v=d.speed_kf.to_numpy(float), lab=d.lane_kf.fillna(-99).to_numpy()))
    return label_leaders(e)


def label_leaders(e):
    o = np.lexsort((e['s'].to_numpy(), e['dir'].to_numpy(), e['lab'].to_numpy(), e['ti'].to_numpy(), e['run'].to_numpy()))
    e = e.iloc[o].reset_index(drop=True)
    run, ti, di, lab = e.run.to_numpy(), e.ti.to_numpy(), e.dir.to_numpy(), e.lab.to_numpy()
    same = np.r_[(run[1:] == run[:-1]) & (ti[1:] == ti[:-1]) & (di[1:] == di[:-1]) & (lab[1:] == lab[:-1]), False]
    j = np.minimum(np.arange(len(e)) + 1, len(e) - 1)
    x, y, v = e.x.to_numpy(), e.y.to_numpy(), e.v.to_numpy()
    e['ll_id'] = np.where(same, e.id.to_numpy()[j], -1)
    e['ll_cc'] = np.where(same, np.hypot(x[j] - x, y[j] - y), np.nan)
    e['ll_v'] = np.where(same, v[j], np.nan)
    send = e.groupby(['run', 'dir']).s.transform(lambda q: np.nanpercentile(q, 99.5)).to_numpy()
    e['free'] = (~same | (e.ll_cc.to_numpy() > FREE)) & (e.s.to_numpy() + FREE <= send)
    return e


def _to_path(p, P):
    """Distance from point p to polyline P (m x 2), and the station along it in segment units (0 = the path's start)."""
    A, B = P[:-1], P[1:]
    AB = B - A; L2 = np.maximum((AB ** 2).sum(1), 1e-9)
    t = np.clip(((p - A) * AB).sum(1) / L2, 0, 1)
    Q = A + t[:, None] * AB
    dd = np.hypot(*(p - Q).T)
    k = int(np.argmin(dd))
    return float(dd[k]), k + float(t[k])


def path_checks(W, raw, every=5):
    """For TGSIM: at every 5th sample (1 s), the follower's distance to the path its leader drove (back far enough to pass
    behind the follower), and whether any other vehicle sits on that path between them (within LINE of it)."""
    from scipy.spatial import cKDTree
    r = raw.sort_values(['run', 'id', 'ti'])
    tracks = {k: (g.ti.to_numpy(), g[['x', 'y']].to_numpy(float)) for k, g in r.groupby(['run', 'id'])}
    frames = {}
    n = len(W['v0']); cols = np.arange(0, W['ti'].shape[1], every)
    seen = np.zeros((n, len(cols)), bool); aligned = np.zeros((n, len(cols)), bool); clear = np.zeros((n, len(cols)), bool); off = np.full((n, len(cols)), np.nan)
    for k in range(n):
        run, fid, lid = W['run'][k], W['fid'][k], W['lid'][k]
        F = tracks.get((run, fid)); L = tracks.get((run, lid))
        if F is None or L is None:
            continue
        for c, j in enumerate(cols):
            t = W['ti'][k, j]
            jf = np.searchsorted(F[0], t); jl = np.searchsorted(L[0], t)
            if jf >= len(F[0]) or F[0][jf] != t or jl >= len(L[0]) or L[0][jl] != t:
                continue
            pf = F[1][jf]
            # the leader's path back until it covers the spacing plus 20 m, at most 120 s
            P = L[1][max(0, jl - 600):jl + 1][::-1]
            seglen = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
            need = np.hypot(*(P[0] - pf)) + 20.0
            m = np.searchsorted(seglen, need)
            if m >= len(P) or len(P) < 3:
                continue
            P = P[:m + 1][::-1]
            dist, st = _to_path(pf, P)
            if st <= 1e-6:
                continue
            seen[k, c] = True; off[k, c] = dist; aligned[k, c] = dist < ALIGN
            key = (run, t)
            if key not in frames:
                fr = raw[(raw.run.to_numpy() == run) & (raw.ti.to_numpy() == t)]
                frames[key] = (fr.id.to_numpy(), fr[['x', 'y']].to_numpy(float), cKDTree(fr[['x', 'y']].to_numpy(float)))
            ids, XY, tree = frames[key]
            near = tree.query_ball_point(pf, np.hypot(*(P[-1] - pf)) + 1.0)
            ok = True
            for q in near:
                if ids[q] in (fid, lid):
                    continue
                dq, sq = _to_path(XY[q], P)
                if dq < LINE and st < sq < len(P) - 1 - 1e-6:
                    ok = False; break
            clear[k, c] = ok
        if len(frames) > 20000:
            frames.clear()
    W['seen'] = seen; W['aligned'] = aligned; W['line_is_leader'] = clear; W['lat_offset'] = off
    W['certain'] = (seen & aligned & clear).all(1)
    return W


def raw_ht_block(k):
    assert k in HT_BLOCKS
    import dlrht as DH
    z = np.load(f'{HTB}/b{k:02d}.npz')
    d = pd.DataFrame({c: z[c] for c in ('id', 'ti', 's', 'dd', 'dir', 'lane', 'v')})
    C = DH.centres(d)
    dc = np.array(d.dd.to_numpy(), float)
    for sg in (-1, 1):
        m = d.dir.to_numpy() == sg
        dc[m] = dc[m] - np.interp(d.s.to_numpy()[m] / 100, np.arange(len(C[sg])), C[sg])
    # table time is 10 Hz ticks; blocks are 5 Hz
    e = pd.DataFrame(dict(run=0, ti=d.ti.to_numpy().astype(np.int64) * 2, id=d.id.to_numpy(), dir=d.dir.to_numpy(), s=d.s.to_numpy(float),
                          d=dc, v=d.v.to_numpy(float), lab=d.lane.to_numpy()))
    return line_leaders(e)


# ---------------------------------------------------------------- open windows with their annotations
def open_windows(name):
    """P2's open windows (personal.build_sets 'open', every start, no subsample) with the driver's past factor."""
    import personal as PS
    d = PS.table_past(name)
    seg = d.seg.to_numpy(); n = len(d)
    vf = d.vf.to_numpy(float); vl = d.vl.to_numpy(float); al = d.al.to_numpy(float); gap = d.gap.to_numpy(float)
    fB = np.exp(PS.shrink(d.sB.to_numpy(), d.cB.to_numpy())[0])
    start = np.r_[0, np.flatnonzero(np.diff(seg) != 0) + 1]
    pos = np.arange(n) - np.repeat(start, np.diff(np.r_[start, n]))
    ok = np.zeros(n, bool)
    ok[HIST:n - S] = (seg[HIST:n - S] == seg[:n - S - HIST]) & (seg[HIST:n - S] == seg[HIST + S:])
    ok &= (pos % 25 == 0) & (vf > 2.0) & (gap > 0.5) & (gap < 100) & ((gap / np.maximum(vf, 1.0) - FD.t_gap(vf)) >= 1.0)
    i = np.flatnonzero(ok)
    Jw = i[:, None] + np.arange(S + 1)[None, :]; Jh = i[:, None] + np.arange(-HIST, 0)[None, :]
    good = np.isfinite(al[Jw]).all(1) & np.isfinite(vl[Jw]).all(1) & np.isfinite(vl[Jh]).all(1)
    i, Jw, Jh = i[good], Jw[good], Jh[good]
    xf = np.concatenate([[0], np.cumsum(0.5 * (vf[1:] + vf[:-1]) * DT)])
    tt = np.round(d.t.to_numpy() * 10).astype(np.int64)
    W = dict(name=name, drv=d.drv.to_numpy()[i], run=d.rec.to_numpy()[i], fid=d.fid.to_numpy()[i], lid=d.lid.to_numpy()[i],
             ti=tt[Jw], v0=vf[i], a0=(vf[i] - vf[i - 2]) / (2 * DT), g=gap[Jw], vl=vl[Jw], al=al[Jw], xf=xf[Jw] - xf[Jw[:, :1]],
             VLh=np.concatenate([vl[Jh], vl[i][:, None]], 1), vf=vf[Jw], fB=fB[i], vdes=float(np.percentile(vf[::7], 99)))
    return W, d


def _lookup(raw, run, ti, ids, cols):
    q = pd.DataFrame(dict(run=run.ravel(), ti=ti.ravel(), id=ids.ravel()))
    m = q.merge(raw[['run', 'ti', 'id'] + cols], on=['run', 'ti', 'id'], how='left')
    return {c: m[c].to_numpy().reshape(ti.shape) for c in cols}


def annotate(W, raw):
    """Pairing, second leader and free past for each window, from the raw frames."""
    n = len(W['v0'])
    run = np.repeat(W['run'][:, None], S + 1, 1); fid = np.repeat(W['fid'][:, None], S + 1, 1); lid = np.repeat(W['lid'][:, None], S + 1, 1)
    L_ = _lookup(raw, run, W['ti'], lid, ['ll_id', 'll_cc', 'll_v', 'v'])
    if 'x' in raw:
        W = path_checks(W, raw)
    else:
        F_ = _lookup(raw, run, W['ti'], fid, ['d', 'll_id'])
        Ld = _lookup(raw, run, W['ti'], lid, ['d'])['d']
        W['lat_offset'] = np.abs(Ld - F_['d'])
        W['line_is_leader'] = (F_['ll_id'] == W['lid'][:, None])
        W['aligned'] = W['lat_offset'] < ALIGN
        W['seen'] = np.isfinite(F_['d']) & np.isfinite(Ld)
        W['certain'] = (W['seen'] & W['line_is_leader'] & W['aligned']).all(1)
    g2 = L_['ll_cc'] - 5.0
    absent = ~np.isfinite(g2) | (g2 > FREE)
    W['g2'] = np.where(absent, np.nan, g2); W['v2'] = np.where(absent, np.nan, L_['ll_v'])
    v2s = pd.DataFrame(W['v2'].T).interpolate(limit_direction='both').to_numpy().T
    W['a2'] = np.gradient(v2s, DT, axis=1)
    W['a2'] = pd.DataFrame(W['a2'].T).rolling(5, center=True, min_periods=1).mean().to_numpy().T
    # free past of the follower: median speed over its own free samples before the window start (at least 2 s)
    fr = raw[raw.free.to_numpy()][['run', 'id', 'ti', 'v']].sort_values(['run', 'id', 'ti'])
    grp = {k: (g.ti.to_numpy(), g.v.to_numpy()) for k, g in fr.groupby(['run', 'id'])}
    vp = np.full(n, np.nan); npast = np.zeros(n, int)
    for k in range(n):
        x = grp.get((W['run'][k], W['fid'][k]))
        if x is None:
            continue
        j = np.searchsorted(x[0], W['ti'][k, 0])
        if j >= 10:
            vp[k] = np.median(x[1][:j]); npast[k] = j
    W['vdes_past'] = vp; W['n_free_past'] = npast
    # the site's per-car free speeds (cars with at least 2 s free), the fallback distribution
    pc = fr.groupby(['run', 'id']).v.agg(['median', 'size'])
    W['site_free'] = np.sort(pc['median'][pc['size'] >= 10].to_numpy())
    return W


def vdes_own(W, floor=True):
    v0 = W['v0']; site = W['site_free']
    out = np.empty(len(v0))
    for k in range(len(v0)):
        if np.isfinite(W['vdes_past'][k]):
            out[k] = max(W['vdes_past'][k], v0[k]) if floor else W['vdes_past'][k]
        else:
            above = site[site >= v0[k]]
            out[k] = np.median(above) if len(above) else v0[k]
    return out


def build():
    os.makedirs(CACHE, exist_ok=True)
    for name in sys.argv[2:] or TABLES:
        W, d = open_windows(name)
        if name == 'HT':
            blk = (W['ti'][:, 0] // 2 - 108000) // 6000
            parts = []
            for k in sorted(set(blk.tolist())):
                if k not in HT_BLOCKS:
                    continue
                raw = raw_ht_block(int(k)); raw['run'] = 0
                m = blk == k
                Wk = {key: (val[m] if isinstance(val, np.ndarray) and val.shape[:1] == (len(m),) else val) for key, val in W.items()}
                Wk['run'] = np.zeros(m.sum(), np.int64)
                parts.append(annotate(Wk, raw))
                print('HT block', k, m.sum(), flush=True)
            site = np.sort(np.concatenate([p['site_free'] for p in parts]))
            W = {key: (np.concatenate([p[key] for p in parts]) if isinstance(parts[0][key], np.ndarray) and key != 'site_free' else parts[0][key]) for key in parts[0]}
            W['site_free'] = site
        else:
            raw = raw_tgsim(name)
            W = annotate(W, raw)
        pickle.dump(W, open(f'{CACHE}/open_{name}.pkl', 'wb'))
        print(name, 'windows', len(W['v0']), 'certain', round(float(W['certain'].mean()), 3), 'free past', round(float(np.isfinite(W['vdes_past']).mean()), 3),
              'second leader at start', round(float(np.isfinite(W['g2'][:, 0]).mean()), 3), flush=True)


def load(name):
    return pickle.load(open(f'{CACHE}/open_{name}.pkl', 'rb'))


# ---------------------------------------------------------------- closing statistics
def excess(g, v):
    return g / np.maximum(v, 1.0) - FD.t_gap(v)


def closed(ex0, ex1):
    return 1 - np.median(ex1) / np.median(ex0)


def boot_closed(ex0, ex1, drv, reps=300, extra=None):
    u, inv = np.unique(drv, return_inverse=True)
    mem = [np.flatnonzero(inv == j) for j in range(len(u))]
    b = []
    for _ in range(reps):
        ii = np.concatenate([mem[j] for j in rng.integers(0, len(u), len(u))])
        b.append(closed(ex0[ii], ex1[ii]))
    c = closed(ex0, ex1)
    return [round(float(c), 3), round(float(np.percentile(b, 2.5)), 3), round(float(np.percentile(b, 97.5)), 3)]


def tau(c):
    return round(float(-30.0 / math.log(1 - c)), 1) if 0 < c < 1 else None


def free():
    res = {}
    for name in TABLES:
        W = load(name)
        ex = excess(W['g'], W['vf'])
        vd = vdes_own(W); vd_raw = vdes_own(W, floor=False)
        dl = vd - W['vl'].mean(1)
        r = dict(windows=int(len(dl)), share_with_free_past=round(float(np.isfinite(W['vdes_past']).mean()), 3),
                 median_vdes=round(float(np.median(vd)), 2), median_leader_speed=round(float(np.median(W['vl'].mean(1))), 2),
                 median_d=round(float(np.median(dl)), 2), all=boot_closed(ex[:, 0], ex[:, -1], W['drv']))
        bins = [(-99, 0.5), (0.5, 1.5), (1.5, 3.0), (3.0, 99)]
        for lab, sel in (('all windows', np.ones(len(dl), bool)), ('own free past only', np.isfinite(W['vdes_past']))):
            rows = {}
            for lo, hi in bins:
                m = sel & (dl >= lo) & (dl < hi)
                if m.sum() >= 30:
                    c = boot_closed(ex[m, 0], ex[m, -1], W['drv'][m])
                    rows[f'{lo}..{hi}'] = dict(n=int(m.sum()), closed_30s=c, tau_s=tau(c[0]), closed_10s=round(float(closed(ex[m, 0], ex[m, 50])), 3))
            r[lab] = rows
        # unfloored past speed (a past slower than the window's start)
        m = np.isfinite(W['vdes_past'])
        if m.sum() >= 30:
            r['past_below_start_speed_share'] = round(float((W['vdes_past'][m] < W['v0'][m]).mean()), 3)
            dl2 = vd_raw[m] - W['vl'][m].mean(1)
            r['unfloored_own_past'] = {f'{lo}..{hi}': boot_closed(ex[m][(dl2 >= lo) & (dl2 < hi), 0], ex[m][(dl2 >= lo) & (dl2 < hi), -1], W['drv'][m][(dl2 >= lo) & (dl2 < hi)])
                                       for lo, hi in bins if ((dl2 >= lo) & (dl2 < hi)).sum() >= 30}
        res[name] = r
        print(name, json.dumps(r), flush=True)
    save('F830_free', res)


def second():
    res = {}
    for name in TABLES:
        W = load(name)
        ex = excess(W['g'], W['vf'])
        g2, v2 = W['g2'][:, 0], W['v2'][:, 0]
        v1 = W['vl'][:, 0]
        e2 = np.where(np.isfinite(g2), excess(np.nan_to_num(g2, nan=1e3), v1), np.inf)
        close = e2 < 0.5
        slower = np.isfinite(v2) & (v2 < W['v0'] - 0.5)
        cons = close | slower
        r = dict(windows=int(len(g2)), share_second_seen=round(float(np.isfinite(g2).mean()), 3), share_close=round(float(close.mean()), 3),
                 share_slower=round(float(slower.mean()), 3))
        for lab, m in (('close or slower', cons), ('close', close), ('slower', slower), ('free or absent', ~cons)):
            if m.sum() >= 30:
                r[lab] = dict(n=int(m.sum()), closed_30s=boot_closed(ex[m, 0], ex[m, -1], W['drv'][m]))
        if cons.sum() >= 30 and (~cons).sum() >= 30:
            u, inv = np.unique(W['drv'], return_inverse=True); mem = [np.flatnonzero(inv == j) for j in range(len(u))]
            b = []
            for _ in range(300):
                ii = np.concatenate([mem[j] for j in rng.integers(0, len(u), len(u))])
                a, c = cons[ii], ~cons[ii]
                if a.sum() > 5 and c.sum() > 5:
                    b.append(closed(ex[ii][c, 0], ex[ii][c, -1]) - closed(ex[ii][a, 0], ex[ii][a, -1]))
            dd = closed(ex[~cons, 0], ex[~cons, -1]) - closed(ex[cons, 0], ex[cons, -1])
            r['free minus constrained'] = [round(float(dd), 3), round(float(np.percentile(b, 2.5)), 3), round(float(np.percentile(b, 97.5)), 3)]
        res[name] = r
        print(name, json.dumps(r), flush=True)
    save('F831_second', res)


# ---------------------------------------------------------------- pairing (F832)
def pairing():
    res = {}
    for name in TABLES:
        W = load(name)
        ex = excess(W['g'], W['vf'])
        c = W['certain']
        r = dict(windows=int(len(c)), certain=round(float(c.mean()), 3), seen_throughout=round(float(W['seen'].all(1).mean()), 3),
                 leader_is_line_leader_throughout=round(float((W['line_is_leader'] | ~W['seen']).all(1).mean()), 3),
                 aligned_throughout=round(float((W['aligned'] | ~W['seen']).all(1).mean()), 3),
                 median_lateral_offset_m=round(float(np.nanmedian(W['lat_offset'])), 2),
                 p90_lateral_offset_m=round(float(np.nanpercentile(W['lat_offset'], 90)), 2),
                 closed_all=boot_closed(ex[:, 0], ex[:, -1], W['drv']))
        if c.sum() >= 30:
            r['closed_certain'] = boot_closed(ex[c, 0], ex[c, -1], W['drv'][c])
        if (~c).sum() >= 30:
            r['closed_uncertain'] = boot_closed(ex[~c, 0], ex[~c, -1], W['drv'][~c])
        res[name] = r
        print(name, json.dumps(r), flush=True)
    res['I395 gain by gap'] = i395_gain()
    res['highD'] = pairing_highd()
    save('F832_pairing', res)


def i395_gain():
    """F801's gain fit on I-395's next-second queries, all against certain pairs (certain over the 3 s before and 1 s after)."""
    import personal as PS
    from scipy.optimize import least_squares
    name = 'I395'
    d = PS.table_past(name)
    raw = raw_tgsim(name)
    seg = d.seg.to_numpy(); n = len(d)
    vf = d.vf.to_numpy(float); vl = d.vl.to_numpy(float); al = d.al.to_numpy(float); gap = d.gap.to_numpy(float)
    start = np.r_[0, np.flatnonzero(np.diff(seg) != 0) + 1]
    pos = np.arange(n) - np.repeat(start, np.diff(np.r_[start, n]))
    h = 5
    ok = np.zeros(n, bool)
    ok[HIST:n - h] = (seg[HIST:n - h] == seg[:n - h - HIST]) & (seg[HIST:n - h] == seg[HIST + h:])
    ok &= (pos % 5 == 0) & (vf > 2.0) & (gap > 0.5) & (gap < 100) & np.isfinite(al)
    i = np.flatnonzero(ok)
    J = i[:, None] + np.arange(-HIST, h + 1)[None, :]
    good = np.isfinite(al[J]).all(1) & np.isfinite(vl[J]).all(1)
    i, J = i[good], J[good]
    tt = np.round(d.t.to_numpy() * 10).astype(np.int64)
    run = d.rec.to_numpy()[J]; fid = d.fid.to_numpy()[J]; lid = d.lid.to_numpy()[J]
    Wq = path_checks(dict(v0=vf[i], run=run[:, 0], fid=fid[:, 0], lid=lid[:, 0], ti=tt[J]), raw)
    cert = Wq['certain']
    q = dict(v=vf[i], a=(vf[i] - vf[i - 2]) / 0.4, g=gap[i], VL=vl[J], AL=al[J], y=vf[i + h] - vf[i], drv=d.drv.to_numpy()[i])
    beta = 1 - math.exp(-DT / FD.TAU_R)
    R2 = json.load(open(FD.OUTJ))['pooled']; kg, kp = R2['k_g'], R2['k_p']

    def roll(lam, ca, idx):
        v, a, g = q['v'][idx].copy(), q['a'][idx].copy(), q['g'][idx].copy()
        VL, AL = q['VL'][idx, HIST:], q['AL'][idx, HIST:]
        v0 = v.copy()
        for k in range(VL.shape[1] - 1):
            vt = np.maximum(v, 6.5); gs = FD.S0 + (FD.t_gap(vt) - FD.S0 / vt) * v
            e = (g - gs) / np.maximum(v, 1.0)
            c = lam * (VL[:, k] - v) + ca * AL[:, k] + kp * np.maximum(e, 0) - kg * np.maximum(-e - 0.5, 0)
            a = a + beta * (c - a); vn = np.maximum(v + a * DT, 0.0); a = (vn - v) / DT
            g = g + 0.5 * (VL[:, k] + VL[:, k + 1] - v - vn) * DT; v = vn
        return v - v0
    out = dict(queries=int(len(cert)), certain=round(float(cert.mean()), 3))
    for lab, sel in (('all', np.ones(len(cert), bool)), ('certain', cert), ('uncertain', ~cert)):
        rows = []
        for lo, hi in [(1.5, 3), (3, 6), (6, 10), (10, 15), (15, 25), (25, 40), (40, 70)]:
            idx = np.flatnonzero(sel & (q['g'] >= lo) & (q['g'] < hi))
            if len(idx) < 150:
                continue
            fitf = lambda ii, x0=(0.3, 0.5): least_squares(lambda p: roll(p[0], p[1], ii) - q['y'][ii], x0, bounds=([0, -1], [5, 3]), loss='soft_l1', f_scale=0.5).x
            p = fitf(idx)
            u, inv = np.unique(q['drv'][idx], return_inverse=True); mem = [np.flatnonzero(inv == j) for j in range(len(u))]
            bs = [fitf(idx[np.concatenate([mem[j] for j in rng.integers(0, len(u), len(u))])], p)[0] for _ in range(30)]
            rows.append(dict(gap=f'{lo}-{hi}', n=int(len(idx)), gain=round(float(p[0]), 3), ci=[round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)],
                             c_a=round(float(p[1]), 3)))
        out[lab] = rows
        print('I395 gain', lab, rows, flush=True)
    return out


def pairing_highd():
    """highD (no location 6): the table leader (precedingId) against the line leader from y, on a sample of recordings."""
    import levelx as LX
    meta = LX.recordings('highD')
    meta = meta[meta.site != 6]
    rows = []
    for rec in meta.rec.to_numpy()[::6]:
        d = LX.tracks('highD', int(rec))
        d = d[d.frame % 25 == 0]
        sg = np.sign(d.vx.to_numpy())
        e = pd.DataFrame(dict(run=0, ti=d.frame.to_numpy(), id=d.id.to_numpy(), dir=sg.astype(np.int8), s=d.xc.to_numpy() * sg,
                              d=d.yc.to_numpy() * sg, v=np.abs(d.vx.to_numpy())))
        e = line_leaders(e)
        m = e.merge(pd.DataFrame(dict(ti=d.frame.to_numpy(), id=d.id.to_numpy(), prec=d.prec.to_numpy())), on=['ti', 'id'])
        m = m[m.prec > 0]
        lat = m[['ti', 'id', 'd']].rename(columns={'id': 'prec', 'd': 'd_l'})
        m = m.merge(lat, on=['ti', 'prec'], how='left')
        rows.append(pd.DataFrame(dict(same=(m.ll_id == m.prec).to_numpy(), aligned=(np.abs(m.d_l - m.d) < ALIGN).to_numpy())))
    a = pd.concat(rows)
    return dict(samples=int(len(a)), leader_is_line_leader=round(float(a.same.mean()), 3), aligned=round(float(a.aligned.mean()), 3),
                certain=round(float((a.same & a.aligned).mean()), 3))


# ---------------------------------------------------------------- the twin with each cause (F833, F834)
def law_f():
    p = json.load(open(os.path.join(RES, 'personal.json')))['twin']['f']['params']
    return [p['K'], p['g_1'], p['c_a'], p['k_g'], p['k_p']]


def roll2(p, W, vdes, second=False, cand='f', form='full', stats=None):
    """structure.roll for candidate (f) with an optional second constraint behind the leader's leader: the same law on the
    distance to its rear, g + 5 + g_2 (centre spacing minus 5 m, the tables' convention), with desired distance
    g*(v) + 5 + g*(v_1). No new number."""
    import structure as ST
    K, g1, ca, kg, kp = p
    fn = ST.CANDS[cand]['fn']
    xl = W['g'] + W['xf']; VL, AL = W['vl'], W['al']
    n, S1 = VL.shape
    v = W['v0'].astype(float).copy(); a = np.clip(W['a0'].astype(float), -3, 3); x = np.zeros(n); steps = np.zeros(n, int)
    f = W['fB']; ctx = dict(f=f, vdes=vdes)
    X = [x.copy()]; Vs = [v.copy()]
    beta = ST.BETA
    for k in range(S1 - 1):
        g = xl[:, k] - x
        vl, al = VL[:, k], AL[:, k]
        c = fn(p, v, g, vl, al, ctx)
        if second:
            g2 = W['g2'][:, k]; has = np.isfinite(g2)
            g2z = np.nan_to_num(g2, nan=1e3)
            gst1 = ST.gstar(vl, 1.0)
            ge = g + 5.0 + g2z
            e2 = (g + g2z - gst1 - ST.gstar(v, f)) / np.maximum(v, 1.0)
            clos = K * np.minimum(np.nan_to_num(W['v2'][:, k], nan=1e3) - v, FD.DV_MAX) / (np.maximum(ge, 0.0) + g1) + ca * np.nan_to_num(W['a2'][:, k])
            bnd = kp * np.maximum(e2, 0.0) - kg * np.maximum(-e2 - FD.E_NEAR, 0.0)
            if form == 'full':
                c2 = clos + bnd
            elif form == 'closing':
                c2 = clos
            else:
                c2 = ST.c_f(p, v, g, vl, al, ctx) - ST.band(v, g, f, kg, kp) + bnd
            if stats is not None:
                stats.append(float(np.mean(has & (c2 < c))))
            c = np.where(has, np.minimum(c, c2), c)
        free_ = np.minimum((vdes - v) / 1.0, ST.MT.a_cap(v, DT))
        c = np.minimum(c, free_)
        an = a + beta * (c - a)
        vn = np.maximum(v + an * DT, 0.0)
        vn = np.where(vl < 0.5 * v, np.minimum(vn, ST.MT.stop_comfort(g - FD.S0 + vl ** 2 / 2.6, v, DT)), vn)
        ce = ST.MT.cert(g, v, vl, a, DT)
        vn = np.where(ce <= 0, -1.0, np.minimum(np.maximum(vn, 0.0), ce))
        jerk = 8.3 / (0.3 + DT)
        floor = v - np.minimum(8.3, np.maximum(0, -a) + 8.3 * DT / (0.3 + DT)) * DT
        release = np.where(a >= 0, 1e9, v + (a + jerk * DT) * DT)
        vn = np.where(vn < 0, floor, np.maximum(np.minimum(vn, release), floor))
        stand = v < 0.05; still = (vl < 1e-3) & (g < 15.0)
        steps = np.where(stand & still, 0, np.where(stand & (vn > 0), steps + 1, steps))
        waited = steps * DT
        held = np.where(still | (steps == 0) | (waited + DT <= 1.0 + 1e-3), 0.0, np.where(waited < 1.0 - 1e-3, vn * (waited + DT - 1.0) / DT, vn))
        vn = np.where(stand, held, vn)
        acc = (vn - v) / DT; vn = np.maximum(vn, 0.0)
        ds = np.where(vn > 0, v * DT + 0.5 * acc * DT * DT, np.where(acc < 0, v * v / (2 * np.maximum(-acc, 1e-9)), 0.0))
        a = np.where(vn > 0, acc, 0.0); x = x + ds; v = vn
        X.append(x.copy()); Vs.append(v.copy())
    X = np.stack(X, 1); V = np.stack(Vs, 1)
    gm = xl - X
    return gm, V


def explain():
    p = law_f()
    res = dict(law_f=dict(zip(['K', 'g_1', 'c_a', 'k_g', 'k_p'], p)))
    for name in TABLES:
        W = load(name)
        exr = excess(W['g'], W['vf'])
        vd_own = vdes_own(W)
        runs = {'baseline': (W['vdes'], False), 'free speed': (vd_own, False), 'second leader': (W['vdes'], True), 'free + second': (vd_own, True)}
        exm = {}
        for k, (vd, sec) in runs.items():
            gm, V = roll2(p, W, vd, second=sec)
            exm[k] = excess(gm[:, -1], V[:, -1])
        cert = W['certain']; drv = W['drv']
        u, inv = np.unique(drv, return_inverse=True); mem = [np.flatnonzero(inv == j) for j in range(len(u))]

        def stats(ii):
            out = {}
            sets = {'baseline': (np.ones(len(ii), bool), 'baseline'), '1 free speed': (np.ones(len(ii), bool), 'free speed'),
                    '2 second leader': (np.ones(len(ii), bool), 'second leader'), '3 certain pairs': (cert[ii], 'baseline'),
                    '4 all three': (cert[ii], 'free + second'), '1+2 (all pairs)': (np.ones(len(ii), bool), 'free + second')}
            for lab, (m, run) in sets.items():
                jj = ii[m]
                rec = closed(exr[jj, 0], exr[jj, -1])
                mod = 1 - np.median(exm[run][jj]) / np.median(exr[jj, 0])
                out[lab] = (rec, mod, mod - rec)
            return out
        base = stats(np.arange(len(drv)))
        bs = [stats(np.concatenate([mem[j] for j in rng.integers(0, len(u), len(u))])) for _ in range(300)]
        r = dict(windows=int(len(drv)), certain=int(cert.sum()))
        G0 = base['baseline'][2]
        for lab in base:
            rec, mod, gap_ = base[lab]
            expl = 1 - gap_ / G0 if G0 else None
            be = [1 - b[lab][2] / b['baseline'][2] for b in bs if b['baseline'][2] != 0]
            r[lab] = dict(recorded=round(float(rec), 3), law_f=round(float(mod), 3), law_minus_recorded=round(float(gap_), 3),
                          within_P2=bool(abs(gap_) <= 0.15),
                          explained=None if lab == 'baseline' else [round(float(expl), 2), round(float(np.percentile(be, 2.5)), 2), round(float(np.percentile(be, 97.5)), 2)])
        if name == 'I90stat':
            dvl = W['vl'][:, -1] - W['vl'][:, 0]
            sp = {}
            for lo, hi in [(-99, -1), (-1, 1), (1, 99)]:
                m = (dvl >= lo) & (dvl < hi)
                if m.sum() >= 30:
                    sp[f'{lo}..{hi}'] = dict(n=int(m.sum()), recorded=boot_closed(exr[m, 0], exr[m, -1], drv[m]),
                                             law_f=round(float(1 - np.median(exm['baseline'][m]) / np.median(exr[m, 0])), 3),
                                             law_f_free_second=round(float(1 - np.median(exm['free + second'][m]) / np.median(exr[m, 0])), 3))
            r['F834 by leader speed change'] = sp
        res[name] = r
        print(name, json.dumps(r), flush=True)
    save('F833_explain', res)


def diagnose():
    p = law_f()
    res = {}
    for name in TABLES:
        W = load(name)
        exr = excess(W['g'], W['vf'])
        e12 = excess(W['g2'][:, 0], W['vl'][:, 0])
        r = dict(leader_excess_at_start=dict(n=int(np.isfinite(e12).sum()), median=round(float(np.nanmedian(e12)), 3),
                                             p25_p75=[round(float(np.nanpercentile(e12, 25)), 3), round(float(np.nanpercentile(e12, 75)), 3)],
                                             share_below_0=round(float(np.nanmean(e12 < 0)), 3)))
        vd = vdes_own(W)
        for form in ('full', 'closing', 'band'):
            st = []
            gm, V = roll2(p, W, vd, second=True, form=form, stats=st)
            exm = excess(gm[:, -1], V[:, -1])
            rec = closed(exr[:, 0], exr[:, -1]); mod = 1 - np.median(exm) / np.median(exr[:, 0])
            r[f'form {form}'] = dict(recorded=round(float(rec), 3), law_f=round(float(mod), 3), law_minus_recorded=round(float(mod - rec), 3),
                                     within_P2=bool(abs(mod - rec) <= 0.15), share_of_steps_binding=round(float(np.mean(st)), 3))
        if name != 'HT':
            raw = raw_tgsim(name)
            L2 = _lookup(raw, W['run'][:, None], W['ti'][:, :1], W['lid'][:, None], ['ll_id'])['ll_id'][:, 0]
            has = (L2 >= 0)
            Wq = path_checks(dict(v0=W['v0'][has], run=W['run'][has], fid=W['lid'][has], lid=L2[has], ti=W['ti'][has]), raw)
            c2 = np.zeros(len(L2), bool); c2[np.flatnonzero(has)] = Wq['certain']
            m = c2 & W['certain']
            gm, V = roll2(p, {k: (v[m] if isinstance(v, np.ndarray) and v.shape[:1] == (len(m),) else v) for k, v in W.items()}, vd[m], second=True)
            exm = excess(gm[:, -1], V[:, -1])
            rec = closed(exr[m, 0], exr[m, -1]); mod = 1 - np.median(exm) / np.median(exr[m, 0])
            r['both pairs certain'] = dict(n=int(m.sum()), share=round(float(m.mean()), 3), recorded=round(float(rec), 3), law_f_full=round(float(mod), 3),
                                           law_minus_recorded=round(float(mod - rec), 3))
        res[name] = r
        print(name, json.dumps(r), flush=True)
    save('F835_diagnose', res)


if __name__ == '__main__':
    globals()[sys.argv[1]]()
