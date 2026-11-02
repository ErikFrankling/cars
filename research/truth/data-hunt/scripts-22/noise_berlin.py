#!/usr/bin/env python3
"""Real-against-real noise floors for the network level of the benchmark, and a test of whether each
metric catches known-bad surrogates built from a real day. No simulator involved.
    python3 -I noise_berlin.py <mq_hr.csv.gz> <sites.csv> <out.json>
"""
import csv, gzip, json, sys, itertools
import numpy as np

mq, sites_csv, out = sys.argv[1:4]
rows = {}
if 'other_days' in mq:
    DAYS = ['2024-09-12', '2024-09-17', '2024-09-18', '2024-09-19', '2024-09-24', '2024-09-26']
    with gzip.open(mq, 'rt') as f:
        for x in csv.DictReader(f):
            if x['date'] in DAYS and x['speed']:
                rows[(x['site'], x['date'], int(x['hour']))] = (float(x['flow']), float(x['speed']))
else:
    DAYS = ['07.05.2019', '14.05.2019', '15.05.2019', '16.05.2019', '21.05.2019', '22.05.2019', '23.05.2019', '28.05.2019']
    with gzip.open(mq, 'rt', errors='replace') as f:
        r = csv.DictReader(f, delimiter=';')
        for x in r:
            if x['tag'] not in DAYS:
                continue
            try:
                rows[(x['mq_name'], x['tag'], int(x['stunde']))] = (float(x['q_kfz_mq_hr']), float(x['v_kfz_mq_hr']))
            except ValueError:
                pass
sites = sorted({k[0] for k in rows})
sites = [s for s in sites if all((s, d, h) in rows for d in DAYS for h in range(24))]
S, D = len(sites), len(DAYS)
Q, V = np.zeros((D, S, 24)), np.zeros((D, S, 24))
for i, d in enumerate(DAYS):
    for j, s in enumerate(sites):
        for h in range(24):
            Q[i, j, h], V[i, j, h] = rows[(s, d, h)]
V[V <= 0] = np.nan
reg = list(csv.DictReader(open(sites_csv)))
geo = {x['site']: (float(x['lat']), float(x['lon'])) for x in reg}
rc = {x['site']: x['road_class'] for x in reg}
XY = np.array([[geo.get(s, (np.nan, np.nan))[1] * 67.6, geo.get(s, (np.nan, np.nan))[0] * 111.2] for s in sites])
free = np.nanquantile(V, .9, axis=(0, 2))
CLS = np.array([2 if rc.get(x) == 'motorway' else 1 if f >= 50 else 0 for x, f in zip(sites, free)])  # 2 motorway by register, 1 fast urban, 0 slow urban
print('sites', S, 'classes', np.bincount(CLS).tolist(), 'with coords', int(np.isfinite(XY[:, 0]).sum()), file=sys.stderr)
A = np.isfinite(XY[:, 0])[:, None] & (np.nan_to_num(np.sqrt(((XY[:, None] - XY[None]) ** 2).sum(-1)), nan=1e9) <= 1.0)


KEEP_LOOP = False


def geh(a, b):
    s = a + b
    return np.sqrt(np.divide(2 * (a - b) ** 2, s, out=np.zeros_like(s), where=s > 0))


def jam(q, v, vfree):
    return np.nan_to_num(v, nan=1e9) < .7 * vfree[:, None]


def frac(J, tr, space):
    F = J.astype(float)
    if tr:
        G = np.zeros_like(F)
        for s in range(-tr, tr + 1):
            G += np.roll(F, s, axis=1)
        F = G / (2 * tr + 1)
    if space:
        F = (A @ F) / A.sum(1, keepdims=True)
    return F


def fss(Ja, Jb, tr, space):
    a, b = frac(Ja, tr, space), frac(Jb, tr, space)
    d = (a ** 2).sum() + (b ** 2).sum()
    return 1 - ((a - b) ** 2).sum() / d if d else 1.0


def spans(J):
    """first and last jammed hour per site in the PM (14-20) and AM (6-10) windows, nan if none."""
    out = {}
    for name, lo, hi in (('am', 6, 11), ('pm', 14, 21)):
        w = J[:, lo:hi]
        hit = w.any(1)
        first = np.where(hit, w.argmax(1) + lo, np.nan)
        last = np.where(hit, hi - 1 - w[:, ::-1].argmax(1), np.nan)
        out[name] = (first, last)
    return out


def harm(q, v, mask):
    q2, v2 = q[mask].ravel(), v[mask].ravel()
    ok = np.isfinite(v2) & (q2 > 0)
    return q2[ok].sum() / (q2[ok] / v2[ok]).sum() if ok.any() else np.nan


def class_speed(q, v):
    ok = np.isfinite(v) & (q > 0)
    q2 = np.where(ok, q, 0.0)
    t = np.where(ok, q2 / np.where(ok, v, 1.0), 0.0)
    out = np.zeros((3, 24))
    for k in range(3):
        i = CLS == k
        out[k] = q2[i].sum(0) / np.maximum(t[i].sum(0), 1e-9)
    return out


def w1(a, b):
    a, b = np.sort(a[np.isfinite(a)]), np.sort(b[np.isfinite(b)])
    if not len(a) or not len(b):
        return np.nan
    p = np.linspace(.005, .995, 199)
    return float(np.abs(np.quantile(a, p) - np.quantile(b, p)).mean())


def mfd(q, v):
    k = np.where(np.isfinite(v), q / v, 0.0)
    return q.mean(0), k.mean(0)


def loop_area(qh, kh, hours):
    x, y = kh[hours], qh[hours]
    return .5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def metrics(qa, va, qr, vr):
    """a = candidate (simulation or another real day), r = reference day. Returns every level separately."""
    day = np.arange(6, 21)
    m = {}
    m['net_total_ratio_err'] = abs(qa.sum() / qr.sum() - 1)
    sa, sr = qa.sum(0) / qa.sum(), qr.sum(0) / qr.sum()
    m['hour_share_rmse_pts'] = 100 * np.sqrt(((sa - sr) ** 2).mean())
    m['am_peak_err_h'] = abs(sa[5:11].argmax() - sr[5:11].argmax())
    m['pm_peak_err_h'] = abs(sa[14:21].argmax() - sr[14:21].argmax())
    g = geh(qa[:, day], qr[:, day])
    m['site_hour_median_geh'] = np.median(g)
    m['site_hour_geh_ge5_share'] = (g >= 5).mean()
    m['site_hour_wape'] = np.abs(qa[:, day] - qr[:, day]).sum() / qr[:, day].sum()
    da, dr = qa.sum(1), qr.sum(1)
    m['site_day_mdape'] = np.median(np.abs(da - dr) / np.maximum(dr, 1))
    m['site_day_p95ape'] = np.quantile(np.abs(da - dr) / np.maximum(dr, 1), .95)
    pa, pr = qa[:, day] / np.maximum(qa[:, day].sum(1, keepdims=True), 1), qr[:, day] / np.maximum(qr[:, day].sum(1, keepdims=True), 1)
    m['site_shape_median_tv'] = np.median(.5 * np.abs(pa - pr).sum(1))
    c = class_speed(qa, va) - class_speed(qr, vr)
    m['class_hour_speed_mae_kmh'] = np.nanmean(np.abs(c[:, day]))
    m['class_hour_speed_max_kmh'] = np.nanmax(np.abs(c[:, day]))
    dv = np.abs(va[:, day] - vr[:, day])
    m['site_hour_speed_mae_kmh'] = np.nanmean(dv)
    m['site_hour_speed_p95_kmh'] = np.nanquantile(dv, .95)
    for name, hrs in (('am', (7, 8)), ('mid', (11, 12, 13)), ('pm', (15, 16, 17))):
        m[f'speed_dist_w1_{name}_kmh'] = w1(va[:, hrs].ravel(), vr[:, hrs].ravel())
    Fa, Fr = np.nanquantile(va, .9, axis=1), np.nanquantile(vr, .9, axis=1)
    dip = lambda v, f: np.nanmin(v[:, day], axis=1) / f
    m['dip_median_err'] = np.nanmedian(np.abs(dip(va, Fa) - dip(vr, Fr)))
    Ja, Jr = jam(qa, va, Fr), jam(qr, vr, Fr)
    m['jam_sitehours_log_ratio'] = abs(np.log(max(Ja[:, day].sum(), 1) / max(Jr[:, day].sum(), 1)))
    for nm, tr, sp in (('fss_exact', 0, False), ('fss_1h', 1, False), ('fss_1h_1km', 1, True)):
        m['jam_' + nm] = 1 - fss(Ja[:, day], Jr[:, day], tr, sp)
    sa2, sr2 = spans(Ja), spans(Jr)
    ons, clr = [], []
    for w in ('am', 'pm'):
        oa, ca = sa2[w]; or_, cr = sr2[w]
        both = np.isfinite(oa) & np.isfinite(or_)
        ons += list(np.abs(oa - or_)[both]); clr += list(np.abs(ca - cr)[both])
    m['jam_onset_mae_h'] = float(np.mean(ons)) if ons else np.nan
    m['jam_clear_mae_h'] = float(np.mean(clr)) if clr else np.nan
    qh, kh = mfd(qa, va); qs, ks = mfd(qr, vr)
    m['mfd_flow_nrmse'] = np.sqrt(((qh - qs)[day] ** 2).mean()) / qs[day].mean()
    m['mfd_density_nrmse'] = np.sqrt(((kh - ks)[day] ** 2).mean()) / ks[day].mean()
    m['mfd_peak_density_err'] = abs(kh[day].max() / ks[day].max() - 1)
    pmh = np.arange(13, 21)
    if KEEP_LOOP:
        m['mfd_loop_area_err'] = abs(loop_area(qh, kh, pmh) / max(loop_area(qs, ks, pmh), 1e-9) - 1)
    return {k: float(v) for k, v in m.items()}


pairs = [(a, b) for a in range(D) for b in range(D) if a != b]
noise = [metrics(Q[a], V[a], Q[b], V[b]) for a, b in pairs]
keys = list(noise[0])
floor = {}
for k in keys:
    x = np.array([n[k] for n in noise], float)
    floor[k] = dict(p50=float(np.nanmedian(x)), p90=float(np.nanquantile(x, .9)), max=float(np.nanmax(x)))

rng = np.random.default_rng(20261102)


def class_perm():
    p = np.arange(S)
    for k in range(3):
        i = np.where(CLS == k)[0]
        p[i] = rng.permutation(i)
    return p


def S_scale(f):
    return lambda q, v: (q * f, v)


def S_shift(s):
    return lambda q, v: (np.roll(q, s, axis=1), np.roll(v, s, axis=1))


def S_sites(q, v):
    p = class_perm()
    return q[p], v[p]


def S_speed_sites(q, v):
    return q, v[class_perm()]


def S_flat(q, v):
    q2 = q.copy()
    q2[:, 6:21] = q[:, 6:21].sum(1, keepdims=True) / 15
    return q2, v


def S_nodip(q, v):
    return q, np.repeat(np.nanmedian(v[:, 6:21], axis=1, keepdims=True), 24, axis=1)


def S_free(q, v):
    return q, np.repeat(np.nanquantile(v, .9, axis=1, keepdims=True), 24, axis=1)


def S_speed(f):
    return lambda q, v: (q, v * f)


def S_capped(q, v):
    """Capacity too low, peak spreads: daily totals and network distance stay, peaks are clipped and the excess runs later."""
    q2 = q.copy()
    for s in range(S):
        cap = .85 * q[s].max()
        carry = 0.0
        for h in range(24):
            t = q[s, h] + carry
            q2[s, h] = min(t, cap)
            carry = t - q2[s, h]
    return q2, v


def S_late_clear(q, v):
    """Every jam clears one hour later and nothing else changes."""
    J = jam(q, v, np.nanquantile(v, .9, axis=1))
    v2 = v.copy()
    for s in range(S):
        for h in range(1, 24):
            if J[s, h - 1] and not J[s, h]:
                v2[s, h] = v[s, h - 1]
    return q, v2


def S_compensate(q, v):
    """Motorways 25% short, everything else over by whatever keeps the network total: right total, wrong split."""
    q2 = q.copy()
    mw = CLS >= 1
    lost = .25 * q[mw].sum()
    q2[mw] *= .75
    q2[~mw] *= 1 + lost / q[~mw].sum()
    return q2, v


noise_by_pair = dict(zip(pairs, noise))
RULES = {'p90': lambda x: np.nanquantile(x, .9), 'max': np.nanmax, '1.25 p90': lambda x: 1.25 * np.nanquantile(x, .9), '1.25 max': lambda x: 1.25 * np.nanmax(x)}
loo = {r: {} for r in RULES}
for rn, rule in RULES.items():
    for i in range(D):
        n_flag = []
        for k in keys:
            stat = np.nanmedian([noise_by_pair[(i, b)][k] for b in range(D) if b != i])
            rest = np.array([noise_by_pair[(a, b)][k] for a, b in pairs if i not in (a, b)], float)
            if stat > rule(rest) + 1e-9:
                n_flag.append(k)
        loo[rn][DAYS[i]] = n_flag


def S_scale_f(f):
    return S_scale(f)


BAD = {
    'control: another real day': lambda q, v: (q, v),
    'flow x0.97': S_scale(.97), 'flow x0.95': S_scale(.95), 'flow x0.9': S_scale(.9), 'flow x0.8': S_scale(.8), 'flow x1.2': S_scale(1.2),
    'clock +1 h': S_shift(1), 'clock -1 h': S_shift(-1),
    'sites shuffled within class': S_sites,
    'speeds shuffled within class': S_speed_sites,
    'flat demand 06-20': S_flat,
    'no rush-hour dip': S_nodip, 'free flow all day': S_free,
    'speed x0.9': S_speed(.9), 'peaks clipped 15%, spread later': S_capped,
    'jams clear 1 h late': S_late_clear, 'fast roads -25%, slow roads compensate': S_compensate,
}
res = {}
for name, fn in BAD.items():
    runs = []
    for a in range(0, D, 2):
        b = (a + 1) % D
        qa, va = fn(Q[a].copy(), V[a].copy())
        runs.append(metrics(qa, va, Q[b], V[b]))
    res[name] = {k: float(np.nanmedian([r[k] for r in runs])) for k in keys}
    print(name, flush=True, file=sys.stderr)

# day against ensemble: CRPS and rank share, real day against the other seven, then a corrupted ensemble
def crps(y, ens):
    n = ens.shape[0]
    e1 = np.abs(ens - y).mean(0)
    e2 = np.abs(ens[:, None] - ens[None]).mean((0, 1))
    return e1 - .5 * e2


ens_res = {}
for name, fn in BAD.items():
    out_q, out_v, out_rankq, ranks_all = [], [], [], []
    for r in range(0, D, 3):
        others = [i for i in range(D) if i != r]
        pairsq = [fn(Q[i].copy(), V[i].copy()) for i in others]
        eq = np.stack([p[0] for p in pairsq]); ev = np.nan_to_num(np.stack([p[1] for p in pairsq]), nan=0)
        y, yv = Q[r], np.nan_to_num(V[r], nan=0)
        out_q.append(crps(y[:, 6:21], eq[:, :, 6:21]).mean() / y[:, 6:21].mean())
        out_v.append(crps(yv[:, 6:21], ev[:, :, 6:21]).mean())
        rk = (eq[:, :, 6:21] < y[:, 6:21]).sum(0) + .5 * (eq[:, :, 6:21] == y[:, 6:21]).sum(0)
        ranks_all.append(rk.ravel())
    rk = np.concatenate(ranks_all)
    hist = np.histogram(rk, bins=np.arange(-.25, 8, 1))[0] / rk.size
    ens_res[name] = dict(crps_flow_norm=float(np.mean(out_q)), crps_speed_kmh=float(np.mean(out_v)), rank_outer_share=float(hist[0] + hist[-1]), rank_low=float(hist[0]), rank_high=float(hist[-1]))

# which metric moved beyond its real-day p90, per surrogate
flags = {name: [k for k in keys if res[name][k] > floor[k]['p90'] * 1.0 + 1e-9] for name in BAD}
flags_max = {name: [k for k in keys if res[name][k] > floor[k]['max'] + 1e-9] for name in BAD}
flags_125 = {name: [k for k in keys if res[name][k] > 1.25 * floor[k]['max'] + 1e-9] for name in BAD}
# leave-one-day-out false alarm rate at each candidate threshold
far = {}
for k in keys:
    x = np.array([n[k] for n in noise], float)
    far[k] = dict(over_p90=float((x > floor[k]['p90']).mean()))
json.dump(dict(days=DAYS, sites=S, classes=np.bincount(CLS).tolist(), floor=floor, surrogate=res, ensemble=ens_res, flags=flags, flags_max=flags_max, flags_125max=flags_125, loo_false_alarms=loo), open(out, 'w'), indent=1)
print(json.dumps(floor, indent=0)[:300], file=sys.stderr)
