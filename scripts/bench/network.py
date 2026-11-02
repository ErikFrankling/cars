"""Metric functions of level 4, one per quantity, used alike for real days and simulated days.
From report 22's noise_berlin.py, with missing hours allowed."""
import numpy as np

DAY = np.arange(6, 21)


def geh(a, b):
    s = a + b
    return np.sqrt(np.divide(2 * (a - b) ** 2, s, out=np.zeros_like(s), where=s > 0))


def w1(a, b):
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if not len(a) or not len(b):
        return np.nan
    p = np.linspace(.01, .99, 99)
    return float(np.abs(np.quantile(a, p) - np.quantile(b, p)).mean())


class Panel:
    """Sites with coordinates and classes. Q, V: sites x 24, nan for a missing hour."""

    def __init__(self, sites, cls, xy):
        self.sites, self.cls = list(sites), np.asarray(cls)
        self.top = max(5, round(len(self.sites) * 20 / 239))
        xy = np.asarray(xy, float)
        d = np.sqrt(((xy[:, None] - xy[None]) ** 2).sum(-1))
        self.A = np.nan_to_num(d, nan=1e9) <= 1.0

    def frac(self, J, tr, space):
        F = J.astype(float)
        if tr:
            F = sum(np.roll(F, s, axis=1) for s in range(-tr, tr + 1)) / (2 * tr + 1)
        if space:
            F = (self.A @ F) / self.A.sum(1, keepdims=True)
        return F

    def fss_loss(self, Ja, Jb, tr, space):
        a, b = self.frac(Ja, tr, space), self.frac(Jb, tr, space)
        d = (a ** 2).sum() + (b ** 2).sum()
        return float(((a - b) ** 2).sum() / d) if d else 0.0


def free_speed(V):
    return np.array([np.nanquantile(v, .9) if np.isfinite(v).any() else np.nan for v in V])


def jam(V, f):
    return np.nan_to_num(V, nan=1e9) < .7 * f[:, None]


def spans(J):
    out = []
    for lo, hi in ((6, 11), (14, 21)):
        w = J[:, lo:hi]
        hit = w.any(1)
        out.append((np.where(hit, w.argmax(1) + lo, np.nan), np.where(hit, hi - 1 - w[:, ::-1].argmax(1), np.nan)))
    return out


def class_speed(q, v, cls):
    ok = np.isfinite(v) & np.isfinite(q) & (q > 0)
    q2 = np.where(ok, q, 0.0)
    t = np.where(ok, q2 / np.where(ok, v, 1.0), 0.0)
    keys = [k for k in np.unique(cls) if (cls == k).sum() >= 20] or list(np.unique(cls))
    return np.array([q2[cls == k].sum(0) / np.maximum(t[cls == k].sum(0), 1e-9) for k in keys])


def curve(q, v):
    k = np.where(np.isfinite(v) & (v > 0), np.nan_to_num(q) / np.where(v > 0, v, 1), np.nan)
    return np.nanmean(q, axis=0), np.nanmean(k, axis=0)


def metrics(qa, va, qr, vr, panel):
    """a is the candidate, r the reference. Both from the same instrument, on the same sites."""
    m = {}
    day = DAY
    ok = np.isfinite(qa) & np.isfinite(qr)
    A, R = np.where(ok, qa, 0.0), np.where(ok, qr, 0.0)
    m['N1'] = abs(A.sum() / max(R.sum(), 1) - 1)
    sa, sr = A.sum(0) / max(A.sum(), 1), R.sum(0) / max(R.sum(), 1)
    m['N3'] = 100 * np.sqrt(((sa - sr) ** 2).mean())
    m['N4.am'] = abs(int(sa[5:11].argmax()) - int(sr[5:11].argmax()))
    m['N4.pm'] = abs(int(sa[14:21].argmax()) - int(sr[14:21].argmax()))
    okd = ok[:, day]
    ad, rd = qa[:, day][okd], qr[:, day][okd]
    if ad.size == 0:
        return {k: np.nan for k in KEYS}
    g = geh(ad, rd)
    m['N5'] = np.abs(ad - rd).sum() / max(rd.sum(), 1)
    m['N6'] = np.sqrt(((ad - rd) ** 2).mean()) / max(rd.mean(), 1e-9)
    m['N7.geh'] = np.median(g)
    m['N7.geh5'] = (g >= 5).mean()
    m['N7.r2'] = 1 - min(1.5, ((ad - rd) ** 2).sum() / max(((rd - rd.mean()) ** 2).sum(), 1e-9))
    m['N7.r2'] = 1 - m['N7.r2']
    da, dr = A.sum(1), R.sum(1)
    ape = np.abs(da - dr) / np.maximum(dr, 1)
    m['N8.med'], m['N8.p95'] = np.median(ape), np.quantile(ape, .95)
    pa = np.where(ok, qa, 0.0)[:, day]
    pr = R[:, day]
    pa, pr = pa / np.maximum(pa.sum(1, keepdims=True), 1), pr / np.maximum(pr.sum(1, keepdims=True), 1)
    m['N9'] = np.median(.5 * np.abs(pa - pr).sum(1))
    c = np.abs(class_speed(qa, va, panel.cls) - class_speed(qr, vr, panel.cls))[:, day]
    m['N10.mean'], m['N10.max'] = np.nanmean(c), np.nanmax(c)
    dv = np.abs(va[:, day] - vr[:, day])
    if np.isfinite(dv).any():
        m['N11.mean'], m['N11.p95'] = np.nanmean(dv), np.nanquantile(dv, .95)
    else:
        m['N11.mean'], m['N11.p95'] = np.nan, np.nan
    for name, hrs in (('am', (7, 8)), ('mid', (11, 12, 13)), ('pm', (15, 16, 17))):
        m[f'N12.{name}'] = w1(va[:, hrs].ravel(), vr[:, hrs].ravel())
    Fa, Fr = free_speed(va), free_speed(vr)
    low = lambda v, f: np.array([np.nanmin(x[day]) / g if np.isfinite(x[day]).any() and g > 0 else np.nan for x, g in zip(v, f)])
    d = np.abs(low(va, Fa) - low(vr, Fr))
    m['N13'] = np.nanmedian(d) if np.isfinite(d).any() else np.nan
    Ja, Jr = jam(va, Fr), jam(vr, Fr)
    m['N16.log'] = abs(np.log(max(Ja[:, day].sum(), 1) / max(Jr[:, day].sum(), 1)))
    for nm, tr, sp in (('exact', 0, False), ('1h', 1, False), ('1h1km', 1, True)):
        m['N14.' + nm] = panel.fss_loss(Ja[:, day], Jr[:, day], tr, sp)
    hit = (Ja[:, day] & Jr[:, day]).sum()
    m['N16.miss'] = 1 - hit / max(Jr[:, day].sum(), 1)
    m['N16.false'] = 1 - hit / max(Ja[:, day].sum(), 1)
    deficit = lambda v, f: np.nansum(np.maximum(f[:, None] - v[:, day], 0), axis=1)
    ta, tr_ = set(np.argsort(-deficit(va, Fr))[:panel.top]), set(np.argsort(-deficit(vr, Fr))[:panel.top])
    m['N17'] = 1 - len(ta & tr_) / panel.top
    ons, clr = [], []
    for (oa, ca), (orr, cr) in zip(spans(Ja), spans(Jr)):
        both = np.isfinite(oa) & np.isfinite(orr)
        ons += list(np.abs(oa - orr)[both])
        clr += list(np.abs(ca - cr)[both])
    m['N18.onset'] = float(np.mean(ons)) if ons else np.nan
    m['N18.clear'] = float(np.mean(clr)) if clr else np.nan
    qh, kh = curve(qa, va)
    qs, ks = curve(qr, vr)
    m['N19.flow'] = np.sqrt(np.nanmean((qh - qs)[day] ** 2)) / max(np.nanmean(qs[day]), 1e-9)
    m['N19.density'] = np.sqrt(np.nanmean((kh - ks)[day] ** 2)) / max(np.nanmean(ks[day]), 1e-9)
    m['N19.peak'] = abs(np.nanmax(kh[day]) / max(np.nanmax(ks[day]), 1e-9) - 1)
    return {k: float(v) for k, v in m.items()}


KEYS = ['N1', 'N3', 'N4.am', 'N4.pm', 'N5', 'N6', 'N7.geh', 'N7.geh5', 'N7.r2', 'N8.med', 'N8.p95', 'N9', 'N10.mean', 'N10.max', 'N11.mean', 'N11.p95', 'N12.am', 'N12.mid', 'N12.pm', 'N13', 'N14.exact', 'N14.1h', 'N14.1h1km', 'N16.log', 'N16.miss', 'N16.false', 'N17', 'N18.onset', 'N18.clear', 'N19.flow', 'N19.density', 'N19.peak']


def crps(y, ens):
    e1 = np.nanmean(np.abs(ens - y), axis=0)
    e2 = np.nanmean(np.abs(ens[:, None] - ens[None]), axis=(0, 1))
    return e1 - .5 * e2


def spread(Qs, Vs, Qreal, Vreal):
    """N15: replicates as an ensemble against each real day. Needs at least 2 replicates."""
    R = np.stack(Qs)
    day = DAY
    sim = np.nanstd(R[:, :, day], axis=0)
    real = np.nanstd(Qreal[:, :, day], axis=0)
    ok = (real > 0)
    ratio = float(np.nanmedian(sim[ok] / real[ok]))
    cq, cv, ranks = [], [], []
    VV = np.nan_to_num(np.stack(Vs), nan=0.0)
    for q, v in zip(Qreal, Vreal):
        cq.append(np.nanmean(crps(q[:, day], R[:, :, day])) / max(np.nanmean(q[:, day]), 1e-9))
        cv.append(np.nanmean(crps(np.nan_to_num(v, nan=0.0)[:, day], VV[:, :, day])))
        rk = (R[:, :, day] < q[:, day]).sum(0) + .5 * (R[:, :, day] == q[:, day]).sum(0)
        ranks.append(rk[np.isfinite(q[:, day])].ravel())
    rk = np.concatenate(ranks)
    n = R.shape[0]
    outer = float(((rk <= .5) | (rk >= n - .5)).mean())
    return dict(ratio=ratio, crps_flow=float(np.mean(cq)), crps_speed=float(np.mean(cv)), rank_outer=outer)
