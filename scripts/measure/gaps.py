"""Part 5: gap acceptance at give-way junctions (inD) and roundabout entries (rounD); standstill gaps in their queues.

Who gives way comes from the site's Lanelet2 map: every right_of_way regulatory element names yield lanelets, priority
lanelets and the yield line (ref_line). For each minor car that crosses a yield line:
  arrival  t_arr   = its front comes within 10 m of the line, or the car ahead from the same lanelet crosses, if later
                     (so the car is first in line from t_arr on); waiting time = t_cross - t_arr
  decision t_cross = its front crosses the line
  conflicts        = priority vehicles (cars, trucks, buses, motorbikes) on a priority lanelet of the same element whose
                     path comes within 2.5 m of the minor car's path after the line; each passes at the time its centre
                     is nearest that point
Offered intervals start at t_arr and at each passage after it. The interval holding t_cross is accepted, those ending
before it are rejected (the first one is a lag). Critical gap: lognormal, censored likelihood F(accepted) - F(largest
rejected), as report 05 section 4.5; Raff's crossing point as a cross-check. Follow-up time: two minor cars from the same
lanelet crossing in one interval, the second already within 15 m of the line (queued) when the first crossed.

    python3 -I scripts/measure/gaps.py inD        # -> cars-data/measure/gaps/inD.csv and research/truth/measure/gaps_inD.json
    python3 -I scripts/measure/gaps.py rounD
"""
import os, sys, json, zipfile, xml.etree.ElementTree as ET
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from scipy.optimize import minimize
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import levelx as LX

RES = os.path.join(HERE, '..', '..', 'research', 'truth', 'measure')
WORK = '/home/erikf/projects/personal/cars-data/measure/gaps'
MOTOR = {'car', 'truck', 'van', 'bus', 'truck_bus', 'trailer', 'motorcycle'}
rng = np.random.default_rng(11)
import collections
DROPS = collections.Counter()
INTERVALS = []
INTERVALS_DF = None
COMMIT = 3.0


def regulatory(ds, site, construction=False):
    """right_of_way elements: yield lanelet ids, priority lanelet ids, ref_line polylines (local frame)."""
    from pyproj import Transformer
    z = LX.zf(ds)
    key = f'{site:02d}_' if ds == 'inD' else f'{site}_'
    names = [n for n in z.namelist() if n.endswith('.osm') and n.split('/')[-2].startswith(key)]
    names = [n for n in names if ('constuction' in n) == construction] or names
    root = ET.fromstring(z.read(names[0]))
    m = LX.recordings(ds, holdout=True); m = m[m.site == site].iloc[0].raw
    tr = Transformer.from_crs('EPSG:4326', 'EPSG:32632', always_xy=True)
    P = {}
    for n in root.iter('node'):
        x, y = tr.transform(float(n.get('lon')), float(n.get('lat')))
        P[int(n.get('id'))] = (x - m['xUtmOrigin'], y - m['yUtmOrigin'])
    ways = {int(w.get('id')): np.array([P[int(r.get('ref'))] for r in w.iter('nd')]) for w in root.iter('way')}
    els = []
    for r in root.iter('relation'):
        t = {x.get('k'): x.get('v') for x in r.iter('tag')}
        if t.get('subtype') != 'right_of_way':
            continue
        mem = [(x.get('role'), int(x.get('ref')), x.get('type')) for x in r.iter('member')]
        els.append(dict(id=int(r.get('id')), yield_=[i for ro, i, ty in mem if ro == 'yield'],
                        prio=[i for ro, i, ty in mem if ro == 'right_of_way'],
                        lines=[ways[i] for ro, i, ty in mem if ro == 'ref_line' and i in ways]))
    return els


def match(d, ll):
    """Lanelet id of each sample: nearest centreline point whose direction agrees within 60 degrees."""
    P, H, L = [], [], []
    for k, v in ll.items():
        c = LX._resample(v['centre'], max(2, int(np.hypot(*np.diff(v['centre'], axis=0).T).sum() / 0.5)))
        h = np.arctan2(*np.gradient(c, axis=0)[:, ::-1].T)
        P.append(c); H.append(h); L.extend([k] * len(c))
    P = np.vstack(P); H = np.concatenate(H); L = np.array(L)
    tree = cKDTree(P)
    hd = np.arctan2(d.vy.to_numpy(), d.vx.to_numpy())
    slow = np.hypot(d.vx, d.vy).to_numpy() < 0.5
    hd[slow] = np.deg2rad(d.heading.to_numpy()[slow])
    dist, ii = tree.query(np.c_[d.xc, d.yc], k=12)
    ok = (np.cos(H[ii] - hd[:, None]) > 0.5) & (dist < 4.0)
    first = ok.argmax(1)
    lane = np.where(ok.any(1), L[ii[np.arange(len(d)), first]], -1)
    return lane


def line_frame(line, ll_y):
    """Yield line as point p0, unit normal n (downstream) and half-length; downstream from the yield lanelet's end."""
    a, b = line[0], line[-1]
    c = (a + b) / 2; t = (b - a) / max(np.hypot(*(b - a)), 1e-6)
    n = np.array([-t[1], t[0]])
    end = ll_y['centre'][-1] - ll_y['centre'][-3]
    if n @ end < 0:
        n = -n
    return c, n, np.hypot(*(b - a)) / 2, t


def analyse_recording(ds, rec, site, construction):
    ll = LX.lanelets(ds, site, construction)
    els = regulatory(ds, site, construction)
    d = LX.tracks(ds, rec)
    tm = LX.tracks_meta(ds, rec).set_index('trackId')
    d['cls'] = tm['class'].reindex(d.id).values
    # Everyone, pedestrians and cyclists too, sorted by time, to see who else stands on a waiting car's path.
    allu = d[['frame', 'id', 'xc', 'yc']].sort_values('frame', kind='stable')
    AF, AI, AX, AY = (allu[c].to_numpy() for c in ('frame', 'id', 'xc', 'yc'))
    d = d[d.cls.isin(MOTOR)].reset_index(drop=True)
    d['t'] = d.frame / 25.0
    d['lanelet'] = match(d, {k: v for k, v in ll.items() if v['tags'].get('subtype') in ('road', 'highway', 'bus_lane')})
    ids, st, en = LX.by_track(d)
    trk = {i: (a, b) for i, a, b in zip(ids, st, en)}
    X, Y, T, V = d.xc.to_numpy(), d.yc.to_numpy(), d.t.to_numpy(), np.hypot(d.vx, d.vy).to_numpy()
    LN, LEN, HD = d.lanelet.to_numpy(), d.length.to_numpy(), np.deg2rad(d.heading.to_numpy())
    CLS = d.cls.to_numpy()
    decisions, follow = [], []
    Y_all = set().union(*[set(e['yield_']) for e in els]) if els else set()
    P_all = set().union(*[set(e['prio']) for e in els]) if els else set()
    for el in els:
        prio = set(el['prio'])
        on_prio = np.isin(LN, list(prio))
        prio_ids = np.unique(d.id.to_numpy()[on_prio])
        for yl in el['yield_']:
            if yl not in ll:
                continue
            # The rule this lanelet gives way under: a minor road, a left turn off the priority road across oncoming
            # traffic, or right-before-left (its priority lanelets themselves give way: a cycle, as at Frankenburg).
            role = 'minor' if yl not in P_all else ('right_before_left' if set(el['prio']) & Y_all else 'major_left')
            ends = [ln for ln in el['lines']]
            if not ends:
                c = ll[yl]['centre']; lb, rb = ll[yl]['left'][-1], ll[yl]['right'][-1]
                ends = [np.array([lb, rb])]
            dist_end = [np.hypot(*(ln.mean(0) - ll[yl]['centre'][-1])) for ln in ends]
            line = ends[int(np.argmin(dist_end))]
            if min(dist_end) > 8:
                line = np.array([ll[yl]['left'][-1], ll[yl]['right'][-1]])
            p0, n, half, tline = line_frame(line, ll[yl])
            users = np.unique(d.id.to_numpy()[LN == yl])
            crossing = []
            for i in users:
                a, b = trk[i]
                fx = X[a:b] + np.cos(HD[a:b]) * LEN[a] / 2; fy = Y[a:b] + np.sin(HD[a:b]) * LEN[a] / 2
                dl = (fx - p0[0]) * n[0] + (fy - p0[1]) * n[1]
                lat = (fx - p0[0]) * tline[0] + (fy - p0[1]) * tline[1]
                # Commitment: front 3 m past the line. Cars often stand with the front up to 2 m over the mapped line.
                cr = np.flatnonzero((dl[:-1] < COMMIT) & (dl[1:] >= COMMIT) & (np.abs(lat[1:]) < half + 2.5))
                if not len(cr):
                    continue
                if CLS[a] not in ('car', 'van'):
                    DROPS['not a car'] += 1; continue
                k = cr[0] + 1
                k0 = int(np.flatnonzero(dl[:k + 1] < 0)[-1]) + 1 if (dl[:k + 1] < 0).any() else 0
                near = np.flatnonzero((dl > -10) & (np.arange(b - a) <= k))
                if not len(near):
                    continue
                t_near, extrap = T[a + near[0]], False
                if near[0] == 0 and dl[0] > -10:
                    # First seen inside the 10 m zone: if already moving, carry it back at its first speed; if standing, drop.
                    if V[a] < 1.0:
                        DROPS['first seen standing within 10 m of the line'] += 1; continue
                    t_near, extrap = T[a] - (10 + dl[0]) / V[a], True
                    DROPS['arrival extrapolated'] += 1
                crossing.append((T[a + k], i, a, b, k, t_near, dl, extrap, k0))
            crossing.sort()
            prev_cross = -np.inf
            for j, (tc, i, a, b, k, tnear, dl, extrap, k0) in enumerate(crossing):
                tarr = max(tnear, prev_cross)
                queued_at_prev = prev_cross > tnear
                prev_cross = tc
                # Minor path after the line, 40 m on, centre points.
                s = np.r_[0, np.cumsum(np.hypot(np.diff(X[a + k0:b]), np.diff(Y[a + k0:b])))]
                kk = a + k0 + np.flatnonzero(s <= 40)
                if len(kk) < 10:
                    DROPS['track ends at the line'] += 1; continue
                tree = cKDTree(np.c_[X[kk], Y[kk]])
                passes = []
                for pid in prio_ids:
                    if pid == i:
                        continue
                    pa, pb = trk[pid]
                    w = np.flatnonzero((T[pa:pb] > tarr - 30) & (T[pa:pb] < tc + 30)) + pa
                    if len(w) < 5:
                        continue
                    dd, ix = tree.query(np.c_[X[w], Y[w]])
                    if dd.min() > 2.5:
                        continue
                    m_ = int(np.flatnonzero(dd <= 2.5)[0])   # first time it comes onto the minor car's path
                    # The priority vehicle must come to that point from a priority lanelet.
                    before = LN[w[:m_ + 1]]
                    if not np.isin(before, list(prio)).any():
                        continue
                    passes.append(T[w[m_]])
                passes = np.sort(np.array(passes))
                # Disturbed: someone other than the priority stream (a pedestrian, a cyclist, the car ahead still in
                # the way, another minor stream) is within 2.5 m of the first 25 m of the car's path while it waits.
                lo_, hi_ = np.searchsorted(AF, int(round(tarr * 25))), np.searchsorted(AF, int(round(tc * 25)), side='right')
                near25 = kk[:max(2, int(np.searchsorted(s[:len(kk)], 25)))]
                t25 = cKDTree(np.c_[X[near25], Y[near25]])
                others, block_t = set(), np.array([])
                if hi_ > lo_:
                    dd2, _ = t25.query(np.c_[AX[lo_:hi_], AY[lo_:hi_]])
                    on = (dd2 <= 2.5) & (AI[lo_:hi_] != int(i)) & ~np.isin(AI[lo_:hi_], prio_ids)
                    others = set(np.unique(AI[lo_:hi_][on]).tolist())
                    block_t = AF[lo_:hi_][on] / 25.0
                pts = np.r_[tarr, passes[passes > tarr]]
                rej, acc, nrej, nblk, iv = 0.0, np.inf, 0, 0, []
                for p, q_ in zip(pts, np.r_[pts[1:], np.inf]):
                    if q_ <= tc:
                        # A refusal only counts if the path was clear of everyone else during that interval.
                        if ((block_t >= p) & (block_t <= q_)).any():
                            nblk += 1; continue
                        rej = max(rej, q_ - p); nrej += 1
                        iv.append((ds, rec, site, int(i), p - tarr, q_ - p, 0, p == tarr))
                    elif p <= tc < q_:
                        iv.append((ds, rec, site, int(i), p - tarr, q_ - p if np.isfinite(q_) else np.inf, 1, p == tarr))
                        acc = q_ - p if np.isfinite(q_) else np.inf
                        acc_is_lag = p == tarr
                        break
                # Movement: heading change between the approach and 25-35 m past the line.
                h0 = np.arctan2(Y[a + k] - Y[max(a, a + k - 25)], X[a + k] - X[max(a, a + k - 25)])
                far = a + k0 + np.flatnonzero((s > 20) & (s <= 40))
                if not len(far):
                    DROPS['track ends within 20 m past the line'] += 1; continue
                h1 = np.arctan2(Y[far[-1]] - Y[far[0]], X[far[-1]] - X[far[0]])
                turn = np.rad2deg(np.angle(np.exp(1j * (h1 - h0))))
                mv = 'left' if turn > 45 else 'right' if turn < -45 else 'straight'
                vmin = float(V[a + np.flatnonzero(T[a:b] >= tarr)[0]:a + k + 1].min()) if tc > tarr else float(V[a + k])
                decisions.append(dict(ds=ds, rec=rec, site=site, el=el['id'], yl=yl, role=role, id=int(i), cls=CLS[a], disturbed=len(others) > 0, t_arr=tarr, t_cross=tc,
                                      wait=tc - tarr, stopped=vmin < 1.0, vmin=vmin, accepted=acc, acc_is_lag=bool(np.isfinite(acc) and acc_is_lag),
                                      largest_rejected=rej, n_rejected=nrej, n_blocked=nblk, n_conflicts=int(len(passes)), turn=float(turn), movement=mv,
                                      queued=queued_at_prev, arrival_extrapolated=extrap, t_near=tnear, passes=';'.join(f'{x:.2f}' for x in passes)))
                INTERVALS.extend(r_ + (mv, el['id'], yl) for r_ in iv)
            # Follow-up: consecutive crossers of one lanelet with no conflicting passage in between, second queued.
            for (t1, i1, a1, b1, k1, *_), (t2, i2, a2, b2, k2, tn2, dl2, *_) in zip(crossing[:-1], crossing[1:]):
                j1 = np.searchsorted(T[a2:b2], t1)
                if j1 >= b2 - a2 or dl2[j1] < -15 or t2 - t1 > 10:
                    continue
                follow.append(dict(ds=ds, rec=rec, site=site, el=el['id'], yl=yl, lead=int(i1), id=int(i2), t1=t1, t2=t2, headway=t2 - t1,
                                   gap_behind_at_t1=float(dl2[j1]), v2_at_t1=float(V[a2 + j1])))
    return decisions, follow, d


def standstill(d):
    """Bumper gap between two stopped vehicles one behind the other on the same lanelet (both under 0.3 m/s)."""
    out = []
    s = d[(np.hypot(d.vx, d.vy) < 0.3) & (d.lanelet >= 0) & d.cls.isin(['car', 'van'])]
    for (fr, ln), g in s[s.frame % 25 == 0].groupby(['frame', 'lanelet']):
        if len(g) < 2:
            continue
        h = np.deg2rad(g.heading.to_numpy()); x = g.xc.to_numpy(); y = g.yc.to_numpy(); L = g.length.to_numpy()
        u = np.array([np.cos(np.median(h)), np.sin(np.median(h))])
        a = x * u[0] + y * u[1]; o = np.argsort(a)
        for p, q_ in zip(o[:-1], o[1:]):
            lat = abs((x[q_] - x[p]) * -u[1] + (y[q_] - y[p]) * u[0])
            gap = a[q_] - a[p] - (L[p] + L[q_]) / 2
            if lat < 1.5 and -0.5 < gap < 10:
                out.append((g.id.iat[p], gap))
    return out


def mle_critical(acc, rej):
    """Lognormal critical gap from accepted a and largest rejected r: max sum log(F(a) - F(r))."""
    acc = np.asarray(acc, float); rej = np.asarray(rej, float)
    la = np.log(np.where(np.isfinite(acc), acc, 1e6)); lr = np.where(rej > 0, np.log(np.maximum(rej, 1e-6)), -np.inf)
    def nll(p):
        mu, ls = p; sg = np.exp(ls)
        pr = norm.cdf((la - mu) / sg) - norm.cdf((lr - mu) / sg)
        return -np.sum(np.log(np.maximum(pr, 1e-12)))
    r = minimize(nll, [np.log(4.0), np.log(0.3)], method='Nelder-Mead')
    return float(np.exp(r.x[0])), float(np.exp(r.x[1]))


def raff(acc, rej):
    """Raff: the gap t where the number of accepted gaps shorter than t equals the number of rejected gaps longer."""
    grid = np.arange(0.5, 15, 0.01)
    A = np.array([(acc < g).sum() for g in grid]); R = np.array([(rej > g).sum() for g in grid])
    i = np.argmin(np.abs(A - R))
    return float(grid[i])


def crit_with_ci(k, reps=200):
    acc, rej = k.accepted.to_numpy(), k.largest_rejected.to_numpy()
    tc, sg = mle_critical(acc, rej)
    rj = k.rejected_all if 'rejected_all' in k else None
    bs = []
    recs = k.rec.to_numpy(); ur = np.unique(recs)
    for _ in range(reps):
        ii = rng.integers(0, len(k), len(k))
        bs.append(mle_critical(acc[ii], rej[ii])[0])
    return dict(n=len(k), with_rejection=int((rej > 0).sum()), critical_gap_s=round(tc, 2), log_sd=round(sg, 3),
                ci=[round(float(np.percentile(bs, 2.5)), 2), round(float(np.percentile(bs, 97.5)), 2)],
                raff_s=round(raff(acc[np.isfinite(acc)], rej[rej > 0]), 2), accepted_p50=round(float(np.median(acc[np.isfinite(acc)])), 2))


def run(ds):
    os.makedirs(WORK, exist_ok=True)
    meta = LX.recordings(ds)
    D, Fu, SS = [], [], []
    for _, m in meta.iterrows():
        rec, site = int(m.rec), int(m.site)
        cons = ds == 'inD' and site == 1 and 11 <= rec <= 17
        dec, fol, d = analyse_recording(ds, rec, site, cons)
        D += dec; Fu += fol
        SS += [(rec, site, i, g) for i, g in standstill(d)]
        print(ds, rec, site, m.day, len(dec), len(fol), flush=True)
    global INTERVALS_DF
    dec = pd.DataFrame(D); fol = pd.DataFrame(Fu); ss = pd.DataFrame(SS, columns=['rec', 'site', 'id', 'gap'])
    INTERVALS_DF = pd.DataFrame(INTERVALS, columns=['ds', 'rec', 'site', 'id', 'start', 'length', 'accepted', 'lag', 'movement', 'el', 'yl'])
    dec.to_csv(f'{WORK}/{ds}_decisions.csv', index=False)
    pd.DataFrame(INTERVALS, columns=['ds', 'rec', 'site', 'id', 'start', 'length', 'accepted', 'lag', 'movement', 'el', 'yl']).to_csv(f'{WORK}/{ds}_intervals.csv', index=False)
    fol.to_csv(f'{WORK}/{ds}_followup.csv', index=False)
    ss.to_csv(f'{WORK}/{ds}_standstill.csv', index=False)
    summarise(ds, dec, fol, ss, meta)


def summarise(ds, dec, fol, ss, meta):
    res = {'recordings': meta.rec.tolist(), 'decisions': len(dec), 'drops': dict(DROPS),
           'arrival_extrapolated_share': round(float(dec.arrival_extrapolated.mean()), 3)}
    k = dec[(dec.n_conflicts > 0) & dec.cls.isin(['car', 'van'])]
    res['with_conflicting_traffic'] = len(k)
    res['disturbed_share'] = round(float(k.disturbed.mean()), 3)
    res['blocked_intervals_dropped'] = int(k.n_blocked.sum()); res['rejections_kept'] = int(k.n_rejected.sum())
    groups = {'all': k, 'undisturbed_only': k[~k.disturbed], 'stopped': k[k.stopped], 'arrival_seen': k[~k.arrival_extrapolated]}
    for (role, mv), g in k.groupby(['role', 'movement']):
        groups[f'{role} {mv}'] = g
    for role, g in k.groupby('role'):
        groups[f'{role}'] = g
    for (site, role, mv), g in k.groupby(['site', 'role', 'movement']):
        groups[f'site {site} {role} {mv}'] = g
    for (site, day), g in k.groupby(['site', meta.set_index('rec').day.reindex(k.rec).values]):
        groups[f'site {site} {day}'] = g
    res['critical_gap'] = {name: crit_with_ci(g) for name, g in groups.items() if len(g) >= 40 and (g.largest_rejected > 0).sum() >= 10}
    # Impatience: acceptance of each offered interval against its length and the time already waited (logit).
    iv = INTERVALS_DF if INTERVALS_DF is not None else pd.DataFrame()
    if len(iv):
        keep = set(zip(k.rec, k.id))
        iv = iv[[x in keep for x in zip(iv.rec, iv.id)]]
        res['impatience_logit'] = impatience(iv)
        role = dec.drop_duplicates(['rec', 'id']).set_index(['rec', 'id']).role
        iv = iv.assign(role=role.reindex(list(zip(iv.rec, iv.id))).values)
        for key, g in list(iv.groupby('site')) + list(iv.groupby('role')) + list(iv.groupby(['role', 'movement'])):
            if g.accepted.sum() >= 50 and (g.accepted == 0).sum() >= 50:
                res['impatience_logit'][str(key)] = impatience(g, reps=100)
    # Within one driver: with a fixed critical gap a driver never takes a gap shorter than one it refused. The share
    # who do, by how long they had waited, is the impatience test that driver differences cannot fake.
    r_ = k[k.largest_rejected > 0].copy()
    r_['shorter'] = r_.accepted < r_.largest_rejected
    res['accepted_shorter_than_rejected'] = {lab: dict(n=int(m_.sum()), share=round(float(r_.shorter[m_].mean()), 3) if m_.sum() else None,
                                                       ratio_p50=round(float((r_.accepted / r_.largest_rejected)[m_].median()), 2) if m_.sum() else None)
                                             for lab, m_ in [('all', r_.wait >= 0), ('wait_under_5s', r_.wait < 5), ('wait_5_15s', (r_.wait >= 5) & (r_.wait < 15)), ('wait_over_15s', r_.wait >= 15)]}
    # Within one driver: with a fixed critical gap a driver never takes a gap shorter than one it refused. The share
    # who do, by how long they had waited, is the impatience test that driver differences cannot fake.
    r_ = k[k.largest_rejected > 0].copy()
    r_['shorter'] = r_.accepted < r_.largest_rejected
    res['accepted_shorter_than_rejected'] = {lab: dict(n=int(m_.sum()), share=round(float(r_.shorter[m_].mean()), 3) if m_.sum() else None,
                                                       ratio_p50=round(float((r_.accepted / r_.largest_rejected)[m_].median()), 2) if m_.sum() else None)
                                             for lab, m_ in [('all', r_.wait >= 0), ('wait_under_5s', r_.wait < 5), ('wait_5_15s', (r_.wait >= 5) & (r_.wait < 15)), ('wait_over_15s', r_.wait >= 15)]}
    # Follow-up: consecutive crossers of one yield lanelet, the second queued before the first crossed (it was within
    # 10 m of the line), no conflicting priority passage between the two crossings, under 10 s apart.
    rows = []
    for (rec, el, yl), g in dec.sort_values('t_cross').groupby(['rec', 'el', 'yl']):
        g = g.reset_index(drop=True)
        for i in range(1, len(g)):
            a_, b_ = g.iloc[i - 1], g.iloc[i]
            if not (b_.t_near < a_.t_cross and b_.t_cross - a_.t_cross < 10 and b_.cls in ('car', 'van') and a_.cls in ('car', 'van')):
                continue
            ps = [float(x) for x in str(b_.passes).split(';') if x not in ('', 'nan')]
            if any(a_.t_cross < x < b_.t_cross for x in ps):
                continue
            rows.append((rec, b_.site, b_.movement, b_.t_cross - a_.t_cross, b_.role))
    f = pd.DataFrame(rows, columns=['rec', 'site', 'movement', 'headway', 'role'])
    res['follow_up_s'] = {'all': dict(n=len(f), p25=round(float(f.headway.quantile(.25)), 2), median=round(float(f.headway.median()), 2),
                                      p75=round(float(f.headway.quantile(.75)), 2), mean=round(float(f.headway.mean()), 2), median_ci=boot(f.headway))} if len(f) else {}
    for key, g in list(f.groupby('site')) + list(f.groupby(['role', 'movement'])) + list(f.groupby(['site', 'role', 'movement'])) + list(f.groupby('role')):
        if len(g) >= 15:
            res['follow_up_s'][str(key)] = dict(n=len(g), median=round(float(g.headway.median()), 2), mean=round(float(g.headway.mean()), 2), median_ci=boot(g.headway))
    if len(ss):
        res['standstill_gap_m'] = dict(pairs_sampled_each_second=len(ss), vehicles=int(ss.id.nunique()),
                                       p10=round(float(ss.gap.quantile(.1)), 2), median=round(float(ss.gap.median()), 2), p90=round(float(ss.gap.quantile(.9)), 2),
                                       median_ci=boot(ss.drop_duplicates(['rec', 'id']).gap))
    json.dump(res, open(os.path.join(RES, f'gaps_{ds}.json'), 'w'), indent=1)
    print(json.dumps(res, indent=0)[:5000])


def impatience(iv, reps=200):
    """Logit P(accept) = 1 / (1 + exp(-(b0 + bg log(length) + bw wait_at_offer))); critical gap at wait w is
    exp(-(b0 + bw w) / bg). Intervals never closed (no later passage) are long and count as accepted with length 60 s."""
    L = np.log(np.clip(np.where(np.isfinite(iv.length), iv.length, 60.0), 0.1, 60.0)); W = iv.start.to_numpy(); y = iv.accepted.to_numpy()
    X = np.c_[np.ones(len(iv)), L, W]
    def fit(X, y):
        def nll(b):
            z = X @ b; return np.sum(np.logaddexp(0, z)) - np.sum(y * z)
        def grad(b):
            p = 1 / (1 + np.exp(-(X @ b))); return X.T @ (p - y)
        return minimize(nll, np.zeros(X.shape[1]), jac=grad, method='BFGS').x
    b = fit(X, y)
    ids = (iv.rec.astype(str) + '_' + iv.id.astype(str)).to_numpy(); u = np.unique(ids)
    by = pd.Series(np.arange(len(ids))).groupby(ids).apply(np.array)
    bs = []
    for _ in range(reps):
        ii = np.concatenate([by[x] for x in rng.choice(u, len(u))])
        bs.append(fit(X[ii], y[ii]))
    bs = np.array(bs)
    tc = lambda bb, w: float(np.exp(-(bb[0] + bb[2] * w) / bb[1]))
    out = dict(intervals=len(iv), drivers=int(len(u)), coef=dict(const=round(float(b[0]), 3), log_gap=round(float(b[1]), 3), wait_per_s=round(float(b[2]), 4)),
               wait_coef_ci=[round(float(np.percentile(bs[:, 2], 2.5)), 4), round(float(np.percentile(bs[:, 2], 97.5)), 4)])
    for w in (0, 5, 10, 20):
        v = [tc(bb, w) for bb in bs]
        out[f'critical_gap_at_wait_{w}s'] = [round(tc(b, w), 2), round(float(np.percentile(v, 2.5)), 2), round(float(np.percentile(v, 97.5)), 2)]
    return out


def boot(x, reps=400):
    x = np.asarray(x, float)
    b = [np.median(x[rng.integers(0, len(x), len(x))]) for _ in range(reps)]
    return [round(float(np.median(x)), 2), round(float(np.percentile(b, 2.5)), 2), round(float(np.percentile(b, 97.5)), 2)]


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[2] == 'summary':
        ds = sys.argv[1]
        INTERVALS_DF = pd.read_csv(f'{WORK}/{ds}_intervals.csv')
        summarise(ds, pd.read_csv(f'{WORK}/{ds}_decisions.csv'), pd.read_csv(f'{WORK}/{ds}_followup.csv'),
                  pd.read_csv(f'{WORK}/{ds}_standstill.csv'), LX.recordings(ds))
    else:
        run(sys.argv[1])
