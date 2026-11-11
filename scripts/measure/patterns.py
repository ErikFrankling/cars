"""Round 4 of the measured driver, step 1: check the round 3 patterns before they are used again. Forecasts F810-F813,
research/truth/measure/PERSONAL.md. Recordings not held out (HOLDOUT.md).

    python3 -I scripts/measure/patterns.py p8          # F810: Lankershim line headways under the tracker's errors
    python3 -I scripts/measure/patterns.py p12         # F811: motorway lane flow, breakdown and queue discharge
    python3 -I scripts/measure/patterns.py i395        # F812: why I-395 differs, split-half consistency
    python3 -I scripts/measure/patterns.py p5p2        # F813 (b): two patterns recomputed with separate code
"""
import os, sys, json, math
import numpy as np, pandas as pd
from scipy.signal import savgol_filter, lfilter

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
RES = os.path.join(HERE, '..', '..', 'research', 'truth', 'measure')
OUT = os.path.join(RES, 'patterns.json')
FT = 0.3048
rng = np.random.default_rng(810)


def save(key, val):
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    out[key] = val
    json.dump(out, open(OUT, 'w'), indent=1)


def med_ci(x, groups, reps=400):
    x = np.asarray(x, float); ok = np.isfinite(x); x = x[ok]; g = np.asarray(groups)[ok]
    if len(x) < 5:
        return [None, None, None, int(len(x))]
    u, inv = np.unique(g, return_inverse=True)
    parts = [x[inv == i] for i in range(len(u))]
    b = [np.median(np.concatenate([parts[i] for i in rng.integers(0, len(u), len(u))])) for _ in range(reps)]
    return [round(float(np.median(x)), 2), round(float(np.percentile(b, 2.5)), 2), round(float(np.percentile(b, 97.5)), 2), int(len(x))]


# ---------------------------------------------------------------- F810: P8 on Lankershim
def lank_frames():
    import queues as Q
    p = '/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-ngsim/lankershim.csv'
    d = pd.read_csv(p, usecols=['vehicle_id', 'frame_id', 'local_x', 'local_y', 'v_length', 'v_class', 'preceding', 'lane_id',
                                'int_id', 'section_id', 'direction'])
    d = d.drop_duplicates(['vehicle_id', 'frame_id']).sort_values(['vehicle_id', 'frame_id']).reset_index(drop=True)
    f, hz = Q.frames_lankershim()
    assert len(f) == len(d) and (f.id.to_numpy() == d.vehicle_id.to_numpy()).all()
    f['xr'] = d.local_x.to_numpy(float) * FT; f['yr'] = d.local_y.to_numpy(float) * FT
    f['int_id'] = d.int_id.to_numpy(); f['section'] = d.section_id.to_numpy()
    f = Q.enrich(f, hz)       # sorts by id, t: same order
    return f, hz


def lank_starts(f, hz):
    """queues.events' start loop: follower row k standing, leader row j passing 1 m/s, the queue head's row while it stood."""
    ids = f.id.to_numpy(); t = f.t.to_numpy(); v = f.v.to_numpy()
    lid = f.lid.to_numpy(); li = f.li.to_numpy(); lcar = f.lcar.to_numpy(); car = f.car.to_numpy()
    pos = f.pos.to_numpy(); head = f.qhead.to_numpy()
    starts = np.r_[0, np.flatnonzero(np.diff(ids)) + 1]; ends = np.r_[starts[1:], len(ids)]
    out = []
    for b, e in zip(starts, ends):
        if not car[b]:
            continue
        seen = set()
        for k in range(b + 1, e):
            if li[k] < 0 or not (v[k] < 0.3) or not lcar[k]:
                continue
            j = li[k]
            if not (v[j] >= 1.0 and j - 1 >= 0 and ids[j - 1] == ids[j] and v[j - 1] < 1.0):
                continue
            if lid[k] in seen:
                continue
            m = k
            while m < e and v[m] < 1.0 and lid[m] == lid[k]:
                m += 1
            if m >= e or v[m] < 1.0:
                continue
            jj = j
            while jj - 1 >= 0 and ids[jj - 1] == ids[j] and v[jj] >= 0.3:
                jj -= 1
            kq = max(b, k - (j - jj)); r0 = kq
            while r0 - 1 >= b and v[r0 - 1] < 0.3 and kq - r0 < 90 * hz and lid[r0 - 1] == lid[k]:
                r0 -= 1
            kq = r0 + int(np.argmax(pos[r0:kq + 1]))
            hd = head[kq] if head[kq] >= 0 and pos[kq] >= 2 else -1
            if hd < 0:
                continue
            jb = starts[np.searchsorted(starts, j, 'right') - 1]; je = ends[np.searchsorted(starts, j, 'right') - 1]
            out.append(dict(k=k, j=j, hd=hd, b=b, e=e, jb=jb, je=je, pos=int(pos[kq]), id=int(ids[k]), lid=int(lid[k]), t=float(t[k])))
            seen.add(lid[k])
    return out


def cross_time(t, pr):
    w = np.flatnonzero((pr[:-1] < 0) & (pr[1:] >= 0))
    if not len(w):
        return np.nan
    i0 = w[0]
    return t[i0] + (0 - pr[i0]) / max(pr[i0 + 1] - pr[i0], 1e-6) * (t[i0 + 1] - t[i0])


def p8():
    f, hz = lank_frames()
    ev = lank_starts(f, hz)
    print('starts with a head', len(ev), flush=True)
    t = f.t.to_numpy(); ids = f.id.to_numpy()
    xs, ys, xr, yr = (f[c].to_numpy() for c in ('x', 'y', 'xr', 'yr'))
    hx, hy, L = f.hx.to_numpy(), f.hy.to_numpy(), f.L.to_numpy()
    v = f.v.to_numpy(); intid = f.int_id.to_numpy()
    lid = f.lid.to_numpy(); li = f.li.to_numpy(); gap = f.gap.to_numpy()
    # raw speed from unsmoothed positions, for tracking jumps
    vr = np.r_[np.hypot(np.diff(xr), np.diff(yr)) * hz, np.nan]
    vr[np.r_[ids[1:] != ids[:-1], True]] = np.nan
    jump = np.r_[np.abs(np.diff(vr)) > 30.0, False]       # raw speed step over 3 m/s in 0.1 s
    # each track's entry to an intersection (int_id 0 -> non-zero): time and arc length
    s = f.s.to_numpy()
    starts = np.r_[0, np.flatnonzero(np.diff(ids)) + 1]; ends = np.r_[starts[1:], len(ids)]
    entry = {}
    for b, e in zip(starts, ends):
        ii = intid[b:e]
        w = np.flatnonzero((ii[:-1] == 0) & (ii[1:] != 0))
        entry[ids[b]] = [(b + i + 1, int(ii[i + 1])) for i in w]

    def headway(E, offset=1.0, mode='centre', src='smooth', noise=None):
        k, j, hd = E['k'], E['j'], E['hd']
        X, Y = (xs, ys) if src == 'smooth' else (xr, yr)
        ux, uy = hx[hd], hy[hd]
        half = (lambda r: L[r] / 2) if mode == 'centre' else (lambda r: 0.0 * L[r])
        fx, fy = X[hd] + ux * (half(hd) + offset), Y[hd] + uy * (half(hd) + offset)
        res = []
        h_off = noise(ids[hd], 1)[0] if noise is not None else 0.0
        for (r0, r1, Lr) in ((E['jb'], E['je'], j), (E['b'], E['e'], k)):
            pr = (X[r0:r1] - fx) * ux + (Y[r0:r1] - fy) * uy + half(Lr)
            if noise is not None:
                pr = pr + noise(ids[r0], r1 - r0) - h_off
            res.append(cross_time(t[r0:r1], pr))
        return res[1] - res[0], res

    rows = []
    for E in ev:
        k, j, hd = E['k'], E['j'], E['hd']
        r = dict(pos=E['pos'], id=E['id'])
        r['base'], (cl, cf) = headway(E)
        r['front'] = headway(E, mode='front')[0]
        r['raw'] = headway(E, src='raw')[0]
        for off in (0.0, 3.0, 5.0):
            r[f'line+{off:g}'] = headway(E, offset=off)[0]
        # tracking jumps within 2 s of either crossing
        bad = False
        for (r0, r1, c) in ((E['jb'], E['je'], cl), (E['b'], E['e'], cf)):
            if np.isfinite(c):
                m = (t[r0:r1] > c - 2) & (t[r0:r1] < c + 2)
                bad |= bool(jump[r0:r1][m].any())
        r['jump'] = bad
        # the head: distance from its standing front to its next intersection entry, and what is ahead when it starts
        hid = ids[hd]
        ent = [x for x in entry.get(hid, []) if x[0] > hd]
        r['head_to_line'] = float(s[ent[0][0]] - s[hd]) if ent else np.nan
        r['head_int'] = ent[0][1] if ent else -1
        # the head's leader when the head first passes 1 m/s
        hb = hd
        while hb + 1 < len(ids) and ids[hb + 1] == hid and v[hb] < 1.0:
            hb += 1
        r['head_lead_gap'] = float(gap[hb]) if lid[hb] >= 0 and np.isfinite(gap[hb]) else np.inf
        # the real stop line: intersection entries of leader and follower, same intersection as the head's
        def ent_t(tid, after):
            for (ri, ii) in entry.get(tid, []):
                if ri > after and ii == r['head_int']:
                    return t[ri - 1] + 0.5 / hz
            return np.nan
        r['stopline'] = ent_t(ids[k], k) - ent_t(ids[j], j) if r['head_int'] > 0 else np.nan
        rows.append(r)
    D = pd.DataFrame(rows)

    def tab(col, m=None):
        d = D if m is None else D[m]
        x = d[col]; ok = (x > 0.5) & (x < 8) & d.pos.between(1, 8)
        return {int(p): med_ci(g[col], g.id) for p, g in d[ok].groupby('pos') if len(g) >= 8}

    res = {'n_starts': int(len(D))}
    for col in ('base', 'front', 'raw', 'line+0', 'line+3', 'line+5'):
        res[col] = tab(col)
    res['no_jump'] = tab('base', ~D.jump)
    res['jump_share'] = round(float(D.jump.mean()), 3)
    sig = D.head_to_line.between(-2, 10) & (D.head_lead_gap > 30)
    res['signal_head'] = tab('base', sig)
    res['signal_head_n'] = int(sig.sum())
    res['stopline_signal_head'] = tab('stopline', sig)
    res['stopline_all'] = tab('stopline')
    res['head_to_line_quantiles'] = [round(float(x), 1) for x in np.nanpercentile(D.head_to_line, [10, 25, 50, 75, 90])]
    res['mid_block'] = tab('base', ~sig)
    # (v) Monte Carlo: per-vehicle constant offset SD 1 m and a 2 s-correlated error SD 0.5 m, along the heading
    res['signal_head_to_line_quantiles'] = [round(float(x), 1) for x in np.nanpercentile(D.head_to_line[sig], [10, 25, 50, 75, 90])]
    res['stopline_signal_head_pos6_any'] = med_ci(D.stopline[sig & (D.pos >= 5) & D.stopline.between(0.5, 8)], D.id[sig & (D.pos >= 5) & D.stopline.between(0.5, 8)])
    rho = math.exp(-1.0 / (2.0 * hz))
    for line_off in (1.0, 4.0):
      draws = {2: [], 3: [], 6: []}
      for dr in range(200):
          r2 = np.random.default_rng(10_000 + dr)
          off = {}

          def noise(tid, n):
              if tid not in off:
                  off[tid] = r2.normal(0, 1.0)
              w = r2.normal(size=n); w[0] /= math.sqrt(1 - rho * rho)
              z = lfilter([math.sqrt(1 - rho * rho)], [1, -rho], w)
              return off[tid] + 0.5 * z
          hw = []
          for E in ev:
              if E['pos'] in draws:
                  off.clear()
                  hw.append((E['pos'], headway(E, offset=line_off, noise=noise)[0]))
          h = pd.DataFrame(hw, columns=['pos', 'hw'])
          h = h[(h.hw > 0.5) & (h.hw < 8)]
          for p in draws:
              draws[p].append(float(h[h.pos == p].hw.median()))
      res[f'monte_carlo_line+{line_off:g}_p5_p50_p95'] = {p: [round(float(np.percentile(x, q)), 2) for q in (5, 50, 95)] for p, x in draws.items()}
    print(json.dumps(res, indent=1), flush=True)
    save('p8', res)



# ---------------------------------------------------------------- F811: P12 on motorways
def _minutes(t, u, lane, v, tr, tid, cs_list, site, zone=(400.0, 150.0)):
    """1-min records per cross-section and lane rank: count, trucks, crossing speed; and the all-lane space-mean speed in the
    zone 150-400 m upstream. t s, u m along travel, sorted by track then time."""
    rows = []
    same = np.r_[tid[1:] == tid[:-1], False]
    t0 = math.floor(np.nanmin(t) / 60) * 60
    for cs in cs_list:
        w = np.flatnonzero(same & (u < cs) & (np.r_[u[1:], np.inf] >= cs))
        if not len(w):
            continue
        fr = (cs - u[w]) / np.maximum(u[w + 1] - u[w], 1e-6)
        tc = t[w] + fr * (t[w + 1] - t[w]); vc = v[w] + fr * (v[w + 1] - v[w])
        X = pd.DataFrame(dict(m=((tc - t0) // 60).astype(int), lane=lane[w], v=vc, tr=tr[w]))
        X = X[X.lane >= 0]
        g = X.groupby(['m', 'lane']).agg(n=('v', 'size'), trucks=('tr', 'sum'), v=('v', 'mean')).reset_index()
        z = (u >= cs - zone[0]) & (u < cs - zone[1])
        zs = pd.DataFrame(dict(m=((t[z] - t0) // 60).astype(int), v=v[z])).groupby('m').v.mean()
        allv = X.groupby('m').v.mean()
        g['v_up'] = zs.reindex(g.m).to_numpy(); g['v_cs_all'] = allv.reindex(g.m).to_numpy()
        g['cs'] = cs; g['site'] = site
        rows.append(g)
    return pd.concat(rows, ignore_index=True) if rows else None


def p12_highd():
    import levelx as LX
    out = []
    for _, m in LX.recordings('highD').iterrows():
        rec = int(m.rec)
        d = LX.tracks('highD', rec)
        d = d[d.frame % 5 == 0]
        cls = LX.tracks_meta('highD', rec).set_index('id')['class']
        for dirn in (1, 2):
            k = d[d.dir == dirn].sort_values(['id', 'frame'])
            if not len(k):
                continue
            u = (-k.xc if dirn == 1 else k.xc).to_numpy(float)
            # lane rank from the median: direction 1 (upper half, moving left) has its fast lane at the largest y
            ly = k.groupby('lane').yc.median().sort_values(ascending=(dirn == 2))
            rank = pd.Series(np.arange(len(ly)), index=ly.index)
            lane = rank.reindex(k.lane).to_numpy()
            tr = (cls.reindex(k.id).to_numpy() != 'Car').astype(int)
            lo, hi = np.percentile(u, 1), np.percentile(u, 99)
            g = _minutes(k.frame.to_numpy() / 25.0, u, lane, np.abs(k.vx.to_numpy(float)), tr, k.id.to_numpy(), [hi - 30.0],
                         f'highD loc {int(m.site)}', zone=(min(400.0, hi - 30 - lo), 150.0))
            if g is not None:
                g['rec'] = rec; g['dir'] = dirn; g['lanes'] = len(ly)
                out.append(g)
        print('highD', rec, flush=True)
    return pd.concat(out, ignore_index=True)


def p12_dlrht():
    out = []
    for b in range(24):                         # blocks 0-23: 06:00-14:00 UTC; 24-29 are held out
        z = np.load(f'/home/erikf/projects/personal/cars-data/measure/dlrht/b{b:02d}.npz')
        d = pd.DataFrame({c: z[c] for c in ('id', 'ti', 's', 'dir', 'lane', 'v', 'tr')})
        for dirn, fast, slow in ((-1, 1, 0), (1, 2, 1)):
            k = d[d.dir == dirn].sort_values(['id', 'ti'])
            lane = np.where(k.lane == fast, 0, np.where(k.lane == slow, 1, -1))
            g = _minutes(k.ti.to_numpy() / 5.0, k.s.to_numpy(float), lane, k.v.to_numpy(float), k.tr.to_numpy(int), k.id.to_numpy(),
                         np.arange(500.0, 6001.0, 500.0), f'DLR HT dir {dirn}')
            if g is not None:
                g['rec'] = b; g['dir'] = dirn; g['lanes'] = 2
                out.append(g)
        print('DLR HT block', b, flush=True)
    return pd.concat(out, ignore_index=True)


def p12():
    cache = '/home/erikf/projects/personal/cars-data/measure/md4'
    os.makedirs(cache, exist_ok=True)
    pth = f'{cache}/p12_minutes.csv'
    if os.path.exists(pth):
        M = pd.read_csv(pth)
    else:
        M = pd.concat([p12_highd(), p12_dlrht()], ignore_index=True)
        M.to_csv(pth, index=False)
    M['m_abs'] = M.m + M.rec * 10_000            # minutes do not run across recordings or blocks
    res = {}
    for site, S in M.groupby('site'):
        r = {}
        # (i) highest sustained 15-min flow per lane rank: 15 consecutive minutes at one cross-section
        for ln, L in S.groupby('lane'):
            best = 0; best_tr = None
            for (cs, rec, dirn), c in L.groupby(['cs', 'rec', 'dir']):
                c = c.set_index('m').sort_index()
                full = c.reindex(range(c.index.min() + 1, c.index.max()))        # drop the partial first and last minute
                n = full.n.fillna(0).to_numpy(); trk = full.trucks.fillna(0).to_numpy()
                if len(n) >= 15:
                    q = np.convolve(n, np.ones(15), 'valid') * 4
                    i = int(np.argmax(q))
                    if q[i] > best:
                        best = int(q[i]); best_tr = round(float(trk[i:i + 15].sum() / max(n[i:i + 15].sum(), 1)), 3)
            r[f'max15_lane{ln}'] = [best, best_tr]
        # 1-min lane flows when the cross-section flows (all-lane speed over 80 km/h) and the busiest 5% of those minutes
        free = S[S.v_cs_all > 80 / 3.6]
        r['free_1min_p95_by_lane'] = {int(ln): int(np.percentile(L.n * 60, 95)) for ln, L in free.groupby('lane') if len(L) > 50}
        # (ii) breakdown: all-lane 5-min speed falls under 70 km/h after 10 min over 80 km/h, at one cross-section
        bd = []
        A = S.groupby(['rec', 'dir', 'cs', 'm']).agg(n=('n', 'sum'), v=('v_cs_all', 'first'), lanes=('lanes', 'first')).reset_index()
        for (rec, dirn, cs), c in A.groupby(['rec', 'dir', 'cs']):
            c = c.set_index('m').sort_index().reindex(range(c.m.min(), c.m.max() + 1))
            v5 = c.v.rolling(5, min_periods=4).mean().to_numpy(); n = c.n.fillna(0).to_numpy()
            for i in range(15, len(c)):
                if v5[i] < 70 / 3.6 and np.nanmin(v5[i - 15:i - 4]) > 80 / 3.6:
                    bd.append(dict(rec=int(rec), dir=int(dirn), cs=float(cs), m=int(c.index[i]),
                                   flow_5min_before_per_lane=round(float(n[i - 9:i - 4].sum() * 12 / c.lanes.iloc[0]), 0)))
                    break
        r['breakdowns'] = bd
        # (iii) queue discharge: the zone 150-400 m upstream under 40 km/h, the cross-section over 60 km/h
        dis = S[(S.v_up < 40 / 3.6) & (S.v_cs_all > 60 / 3.6)]
        dis = dis[(dis.m > dis.groupby(['rec', 'dir', 'cs']).m.transform('min'))]
        r['discharge_minutes'] = int(dis.groupby(['rec', 'dir', 'cs', 'm']).ngroups)
        r['discharge_by_lane'] = {int(ln): dict(flow=med_ci(L.n * 60, L.rec.astype(str) + L.dir.astype(str)), truck_share=round(float(L.trucks.sum() / max(L.n.sum(), 1)), 3))
                                  for ln, L in dis.groupby('lane') if len(L) >= 10}
        cong = S[S.v_cs_all < 60 / 3.6]
        r['congested_minutes_at_cs'] = int(cong.groupby(['rec', 'dir', 'cs', 'm']).ngroups)
        r['minutes'] = int(S.groupby(['rec', 'dir', 'cs', 'm']).ngroups)
        res[site] = r
        print(site, json.dumps(r)[:900], flush=True)
    save('p12', res)



def p12w(recs=(25, 26, 36, 46)):
    """F814: outflow of stop-and-go waves on highD location 1, per lane, at 100 / 200 / 300 m into the section."""
    import levelx as LX
    rows = []
    for rec in recs:
        d = LX.tracks('highD', rec)
        d = d[d.frame % 5 == 0]
        cls = LX.tracks_meta('highD', rec).set_index('id')['class']
        for dirn in (1, 2):
            k = d[d.dir == dirn].sort_values(['id', 'frame'])
            u = (-k.xc if dirn == 1 else k.xc).to_numpy(float)
            ly = k.groupby('lane').yc.median().sort_values(ascending=(dirn == 2))
            lane = pd.Series(np.arange(len(ly)), index=ly.index).reindex(k.lane).to_numpy()
            tr = (cls.reindex(k.id).to_numpy() != 'Car').astype(int)
            t = k.frame.to_numpy() / 25.0; v = np.abs(k.vx.to_numpy(float)); tid = k.id.to_numpy()
            same = np.r_[tid[1:] == tid[:-1], False]
            lo = np.percentile(u, 1)
            for off in (100.0, 200.0, 300.0):
                cs = lo + off
                w = np.flatnonzero(same & (u < cs) & (np.r_[u[1:], np.inf] >= cs))
                fr = (cs - u[w]) / np.maximum(u[w + 1] - u[w], 1e-6)
                tc = t[w] + fr * (t[w + 1] - t[w])
                X = pd.DataFrame(dict(tc=tc, lane=lane[w], tr=tr[w]))
                # 10-s mean speed of the lane at the cross-section: samples within 15 m of it
                near = np.abs(u - cs) < 15
                V = pd.DataFrame(dict(b=(t[near] // 10).astype(int), lane=lane[near], v=v[near])).groupby(['lane', 'b']).v.mean()
                for ln in np.unique(lane[w]):
                    vs = V.loc[ln] if ln in V.index.get_level_values(0) else None
                    if vs is None:
                        continue
                    vs = vs.reindex(range(vs.index.min(), vs.index.max() + 1))
                    b = vs.index.to_numpy(); vv = vs.to_numpy()
                    last_slow = -10 ** 9; i = 0
                    while i < len(b):
                        if vv[i] < 30 / 3.6:
                            last_slow = i
                        elif vv[i] > 60 / 3.6 and i - last_slow <= 3 and last_slow >= 0:
                            j = i
                            while j + 1 < len(b) and j - i < 5 and np.isfinite(vv[j + 1]) and vv[j + 1] > 60 / 3.6:
                                j += 1
                            dur = (j - i + 1) * 10.0
                            if dur >= 30:
                                t0 = b[i] * 10.0; t1 = t0 + dur
                                m = (X.lane == ln) & (X.tc >= t0) & (X.tc < t1)
                                rows.append(dict(rec=rec, dir=dirn, cs=off, lane=int(ln), lanes=len(ly), t0=t0, dur=dur, n=int(m.sum()),
                                                 trucks=int(X.tr[m].sum()), flow=3600.0 * m.sum() / dur))
                            last_slow = -10 ** 9; i = j
                        i += 1
        print('highD', rec, len(rows), flush=True)
    D = pd.DataFrame(rows)
    res = dict(recoveries=int(len(D)))
    for ln, L in D.groupby('lane'):
        res[f'lane{ln}'] = dict(outflow=med_ci(L.flow, L.rec.astype(str) + L.dir.astype(str) + L.t0.astype(str)),
                                truck_share=round(float(L.trucks.sum() / max(L.n.sum(), 1)), 3), recoveries=int(len(L)),
                                by_cs={int(c): round(float(g.flow.median())) for c, g in L.groupby('cs')})
    # the same recoveries by direction-lane count, and all lanes of a direction together per lane
    res['by_rec_dir'] = {f'{r}/{d}': int(len(g)) for (r, d), g in D.groupby(['rec', 'dir'])}
    print(json.dumps(res, indent=1), flush=True)
    D.to_csv('/home/erikf/projects/personal/cars-data/measure/md4/p12w_recoveries.csv', index=False)
    save('p12w', res)



# ---------------------------------------------------------------- F812: I-395
def crps_each(X, y):
    m = X.shape[1]
    t1 = np.mean(np.abs(X - y[:, None]), 1)
    Xs = np.sort(X, 1); w = (2 * np.arange(1, m + 1) - m - 1) / (m * m)
    return t1 - np.sum(Xs * w, 1)


def p1_each(cand, p, q, members=20):
    import structure as ST
    A = ST.q_args(q); N = len(q['y'])
    ens = np.stack([ST.roll(cand, p, noise=ST.ou(N, 6, 100 + m), **A)[1][:, -1] - q['v'] for m in range(members)], 1)
    return crps_each(ens, q['y'])


def i395():
    import structure as ST
    FS = ST.fit_sets()
    F = json.load(open(ST.OUT))['filter']
    res = {}
    # split-half: follower ids rise with time on I-395 (correlation 1.00), so the id median splits the two hours
    for n in ST.FIT_TABLES:
        q = FS['next'][n]
        base = p1_each('a', ST.P_R2, q)
        r = {}
        for c in ('e', 'f'):
            pc = [F[c]['params'][k] for k in ST.CANDS[c]['names']]
            cc = p1_each(c, pc, q)
            fid = q['fid']; half = fid > np.median(fid)
            u, inv = np.unique(fid, return_inverse=True)
            members = [np.flatnonzero(inv == j) for j in range(len(u))]

            def ratio(idx):
                return float(cc[idx].mean() / base[idx].mean())
            bs = []
            for _ in range(300):
                pick = np.concatenate([members[j] for j in rng.integers(0, len(u), len(u))])
                bs.append(ratio(pick))
            r[c] = dict(ratio=round(ratio(np.arange(len(cc))), 4), ci=[round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)],
                        first_half=round(ratio(np.flatnonzero(~half)), 4), second_half=round(ratio(np.flatnonzero(half)), 4))
        res[f'P1 ratio {n}'] = r
        print(n, r, flush=True)
    # F801 closing gain against gap on I-395, split by speed
    S = ST.load_sets(); q = S['tables']['I395']
    kg, kp = ST.R2['k_g'], ST.R2['k_p']
    from scipy.optimize import least_squares

    def roll(lam, ca, idx):
        v, a, g = q['v'][idx].copy(), q['a'][idx].copy(), q['g'][idx].copy()
        VL, AL = q['VL'][idx, ST.HIST:], q['AL'][idx, ST.HIST:]
        v0 = v.copy()
        for k in range(VL.shape[1] - 1):
            vt = np.maximum(v, 6.5); gs = ST.FD.S0 + (ST.FD.t_gap(vt) - ST.FD.S0 / vt) * v
            e = (g - gs) / np.maximum(v, 1.0)
            c = lam * (VL[:, k] - v) + ca * AL[:, k] + kp * np.maximum(e, 0) - kg * np.maximum(-e - 0.5, 0)
            a = a + ST.BETA * (c - a)
            vn = np.maximum(v + a * ST.DT, 0.0); a = (vn - v) / ST.DT
            g = g + 0.5 * (VL[:, k] + VL[:, k + 1] - v - vn) * ST.DT; v = vn
        return v - v0
    gb = {}
    for vlo, vhi in ((2, 7), (7, 10), (10, 30)):
        rows = []
        for lo, hi in ((3, 6), (6, 10), (10, 15), (15, 25), (25, 40), (40, 70)):
            idx = np.flatnonzero((q['g'] >= lo) & (q['g'] < hi) & (q['v'] >= vlo) & (q['v'] < vhi))
            if len(idx) < 150:
                continue
            r = least_squares(lambda p: roll(p[0], p[1], idx) - q['y'][idx], [0.3, 0.5], bounds=([0, -1], [5, 3]), loss='soft_l1', f_scale=0.5)
            rows.append(dict(gap=f'{lo}-{hi}', n=int(len(idx)), gain=round(float(r.x[0]), 3), gain_x_gap=round(float(r.x[0] * np.median(q['g'][idx])), 2)))
        gb[f'{vlo}-{vhi} m/s'] = rows
        print(vlo, vhi, rows, flush=True)
    res['I395_gain_by_gap_and_speed'] = gb
    # the same split on I-90/94 st., the other congested table
    save('i395', res)



# ---------------------------------------------------------------- F813 (a): multi-start refits
def fitcheck(cands=('e', 'f')):
    import structure as ST, time
    from scipy.optimize import least_squares
    FS = ST.fit_sets(); sc_ = ST.scales(FS)
    F = json.load(open(ST.OUT))['filter']
    r0 = np.random.default_rng(813)
    res = {}
    for c in cands:
        C = ST.CANDS[c]
        lo, hi = np.array(C['lo'], float), np.array(C['hi'], float)
        starts = [np.array(C['p0'], float)] + [np.clip(np.array(C['p0'], float) * r0.uniform(0.5, 2.0, len(C['p0'])) + 1e-3, lo, hi) for _ in range(3)]
        out = []
        for i, p0 in enumerate(starts):
            t0 = time.time()
            r = least_squares(lambda q: ST.objective(c, list(q), FS, sc_), p0, bounds=(lo, hi), diff_step=1e-3, max_nfev=400)
            out.append(dict(start=[round(float(x), 4) for x in p0], params=[round(float(x), 4) for x in r.x], objective=round(float(np.sum(r.fun ** 2)), 5),
                            status=int(r.status), nfev=int(r.nfev), njev=int(r.njev) if r.njev is not None else None, secs=round(time.time() - t0)))
            print(c, i, out[-1], flush=True)
        res[c] = dict(round3=dict(params=F[c]['params'], objective=F[c]['objective']), starts=out)
        save('fitcheck', {**(json.load(open(OUT)).get('fitcheck', {}) if os.path.exists(OUT) else {}), c: res[c]})



# ---------------------------------------------------------------- F813 (b): two patterns with separate code
def p5p2():
    """P5 and P2 (I-294 L1) for the round 2 law, written apart from structure.py: a scalar car-by-car loop with
    fit_driver.command for the law, and windows built afresh from follow.py's table."""
    import fit_driver as FD, md_twin_lite as MT, follow as F
    J = json.load(open(FD.OUTJ))['pooled']; P = [J['K'], J['c_a'], J['k_g'], J['k_p']]
    beta_of = lambda dt: 1 - math.exp(-dt / FD.TAU_R)
    res = {}
    # P5: six cars, 8 m/s, each on the median driver's desired gap; the head brakes at 1.5 m/s2 from t = 10 s to a stop
    dt, Lc = 0.25, 5.0
    g0 = FD.S0 + (FD.t_gap(8.0) - FD.S0 / 8.0) * 8.0
    x = [-(i * (Lc + g0)) for i in range(6)]; v = [8.0] * 6; a = [0.0] * 6
    for k in range(int(50 / dt)):
        t1 = (k + 1) * dt
        xn, vnn, an = list(x), list(v), list(a)
        for i in range(6):
            if i == 0:
                target = max(0.0, 8.0 - 1.5 * max(t1 - 10, 0))
                cmd = min((target - v[0]) / 1.0, float(MT.a_cap(np.array(v[0]), dt)))
                cmd = min(cmd, max(2.02 - 0.125 * v[0], 0.7))
                lead = False
            else:
                gap = x[i - 1] - Lc - x[i]
                cmd = float(FD.command(np.array(v[i]), np.array(gap), np.array(v[i - 1]), np.array(a[i - 1]), P))
                cmd = min(cmd, (8.0 - v[i]) / 1.0, float(MT.a_cap(np.array(v[i]), dt)))
                lead = True
            nv = max(v[i] + (a[i] + beta_of(dt) * (cmd - a[i])) * dt, 0.0)
            if lead:
                gap = x[i - 1] - Lc - x[i]
                if v[i - 1] < 0.5 * v[i]:
                    nv = min(nv, float(MT.stop_comfort(np.array(gap - FD.S0 + v[i - 1] ** 2 / 2.6), np.array(v[i]), dt)))
                c = float(MT.cert(np.array(gap), np.array(v[i]), np.array(v[i - 1]), np.array(a[i]), dt))
                nv = -1.0 if c <= 0 else min(nv, c)
            jerk = 8.3 / (0.3 + dt)
            floor = v[i] - min(8.3, max(0, -a[i]) + 8.3 * dt / (0.3 + dt)) * dt
            release = 1e9 if a[i] >= 0 else v[i] + (a[i] + jerk * dt) * dt
            nv = floor if nv < 0 else max(min(nv, release), floor)
            acc = (nv - v[i]) / dt; nv = max(nv, 0.0)
            ds = v[i] * dt + 0.5 * acc * dt * dt if nv > 0 else (v[i] ** 2 / (2 * max(-acc, 1e-9)) if acc < 0 else 0.0)
            xn[i] = x[i] + ds; vnn[i] = nv; an[i] = acc if nv > 0 else 0.0
        x, v, a = xn, vnn, an
    gaps = [x[i - 1] - Lc - x[i] for i in range(1, 6)]
    res['P5_round2'] = dict(separate=round(float(np.median(gaps)), 3), gaps=[round(g, 2) for g in gaps])
    # P2 on I-294 L1: open windows (time gap 1 s or more above T(v)), same leader for 30 s, every 25th sample of a segment
    d = F.load('I294L1'); d = d[d.lcar.astype(bool)].reset_index(drop=True)
    seg = d.seg.to_numpy(); vf = d.vf.to_numpy(float); vl = d.vl.to_numpy(float); al = d.al.to_numpy(float); gap = d.gap.to_numpy(float)
    fid = d.fid.to_numpy(); n = len(d); S = 150; H = 15
    rows = []
    for sg in np.unique(seg):
        ii = np.flatnonzero(seg == sg)
        for o in range(0, len(ii), 25):
            i = ii[o]
            if o < H or o + S >= len(ii):
                continue
            J_ = ii[o:o + S + 1]
            if not (vf[i] > 2 and 0.5 < gap[i] < 100 and gap[i] / max(vf[i], 1) - FD.t_gap(vf[i]) >= 1.0):
                continue
            if not (np.isfinite(al[J_]).all() and np.isfinite(vl[J_]).all() and np.isfinite(vl[ii[o - H:o]]).all()):
                continue
            rows.append(J_)
    W = np.array(rows)
    # the driver's own factor: steady samples of its other segments, shrunk by reliability (ROUND2 section 2)
    st = (np.abs(vl - vf) < 1.0) & (vf > 5)
    lr = np.where(st, np.log(np.maximum(gap, 0.01) / np.maximum(vf, 0.1) / FD.t_gap(vf)), np.nan)
    fw = []
    for J_ in W:
        i = J_[0]
        m = (fid == fid[i]) & (seg != seg[i]) & np.isfinite(lr)
        c = int(m.sum())
        if c >= 25:
            rho_ = 0.27 ** 2 / (0.27 ** 2 + (0.47 ** 2 - 0.27 ** 2) / (c / 50.0))
            fw.append(math.exp(rho_ * lr[m].mean()))
        else:
            fw.append(1.0)
    fw = np.array(fw)
    dt = 0.2; beta = beta_of(dt)
    xf = np.concatenate([[0], np.cumsum(0.5 * (vf[1:] + vf[:-1]) * dt)])
    vdes = float(np.percentile(vf[::7], 99))
    V = vf[W[:, 0]].copy(); A = (vf[W[:, 0]] - vf[W[:, 0] - 2]) / (2 * dt); X = np.zeros(len(W))
    XL = gap[W[:, 0]][:, None] + (xf[W] - xf[W[:, :1]])  # leader rear relative to the follower's start, via recorded gap
    XL = gap[W] + xf[W] - xf[W[:, :1]]
    exm = []
    for k in range(S + 1):
        g = XL[:, k] - X
        exm.append(g / np.maximum(V, 1.0) - FD.t_gap(V))
        if k == S:
            break
        vt = np.maximum(V, 6.5); gs = FD.S0 + fw * (FD.t_gap(vt) - FD.S0 / vt) * V
        e = (g - gs) / np.maximum(V, 1.0)
        c = P[0] * np.minimum(vl[W[:, k]] - V, FD.DV_MAX) / np.maximum(g, 1.0) + P[1] * al[W[:, k]] + P[3] * np.maximum(e, 0) - P[2] * np.maximum(-e - 0.5, 0)
        c = np.minimum(c, np.minimum((vdes - V) / 1.0, MT.a_cap(V, dt)))
        A = A + beta * (c - A)
        Vn = np.maximum(V + A * dt, 0.0)
        Vn = np.where(vl[W[:, k]] < 0.5 * V, np.minimum(Vn, MT.stop_comfort(g - FD.S0 + vl[W[:, k]] ** 2 / 2.6, V, dt)), Vn)
        A = (Vn - V) / dt
        X = X + 0.5 * (V + Vn) * dt; V = Vn
    exr = gap[W] / np.maximum(vf[W], 1.0) - FD.t_gap(vf[W])
    rec = 1 - np.median(exr[:, S]) / np.median(exr[:, 0]); mod = 1 - np.median(exm[S]) / np.median(exr[:, 0])
    res['P2_I294L1_round2'] = dict(windows=int(len(W)), recorded=round(float(rec), 3), model=round(float(mod), 3))
    print(json.dumps(res, indent=1), flush=True)
    save('p5p2', res)


if __name__ == '__main__':
    globals()[sys.argv[1]]()
