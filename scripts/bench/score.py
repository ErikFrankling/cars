"""Statuses, floors and the skill rule of report 22, section 6. Everything here is plain arithmetic on D_m(i, j)."""
import math

import numpy as np

ORDER = ['FAIL', 'INVALID', 'INCONCLUSIVE', 'THIN', 'NO DATA', 'CREDIBLE', 'NEAR', 'FLOOR']
RANK = {s: i for i, s in enumerate(ORDER)}
PASSING = ('FLOOR', 'NEAR')
Z_CAP = 999.0


def floor_of(pairs):
    x = np.asarray(pairs, float)
    x = x[np.isfinite(x)]
    return float(np.quantile(x, .97)) if x.size else float('nan')


def bootstrap_upper(D, n=400, seed=7):
    """Upper limit of a 95% interval of the median, resampling seeds and real days together."""
    D = np.atleast_2d(np.asarray(D, float))
    if D.size <= 1:
        return float(D.ravel()[0]) if D.size else float('nan')
    rng = np.random.default_rng(seed)
    r, c = D.shape
    out = []
    for _ in range(n):
        i, j = rng.integers(0, r, r), rng.integers(0, c, c)
        v = D[np.ix_(i, j)]
        v = v[np.isfinite(v)]
        if v.size:
            out.append(np.median(v))
    return float(np.quantile(out, .975)) if out else float('nan')


def judge(D, F, N=None, credible=None, thin=False, proxy=False):
    """Returns the record for one metric cell. D: seeds x real days or blocks, lower is better."""
    D = np.atleast_2d(np.asarray(D, float))
    good = D[np.isfinite(D)]
    rec = dict(S=None, S90=None, U=None, F=_r(F), N=_r(N), z=None, skill=None, n_pairs=int(good.size), shape=list(D.shape))
    if good.size == 0:
        rec['status'] = 'INCONCLUSIVE'
        rec['note'] = 'the simulation produced nothing to measure here'
        return rec
    S, S90, U = float(np.median(good)), float(np.quantile(good, .9)), bootstrap_upper(D)
    rec.update(S=_r(S), S90=_r(S90), U=_r(U))
    if F is None or not math.isfinite(F):
        rec['status'] = 'INVALID'
        rec['note'] = 'no real-against-real floor'
        return rec
    z = S / F if F > 0 else (0.0 if S <= 0 else Z_CAP)
    rec['z'] = _r(min(z, Z_CAP))
    beats = True
    if N is not None and math.isfinite(N):
        rec['skill'] = _r((N - S) / (N - F)) if N != F else None
        beats = S < N
    if not beats:
        rec['status'] = 'FAIL'
        rec['note'] = 'no better than the null model'
    elif S <= F and U <= 1.25 * F and S90 <= 1.5 * F:
        rec['status'] = 'THIN' if thin else 'FLOOR'
    elif S <= F:
        rec['status'] = 'INCONCLUSIVE'
        rec['note'] = 'median inside the floor, spread or confidence bound outside'
    elif S <= 1.25 * F:
        rec['status'] = 'NEAR'
    elif _credible(S, F, N, credible):
        rec['status'] = 'CREDIBLE'
    else:
        rec['status'] = 'FAIL'
    return rec


def _credible(S, F, N, credible):
    """Report 22: meets the credible threshold of section 7, and closes half the gap from the null to real noise. No threshold, no such status."""
    if credible is None or S > credible:
        return False
    has_skill = N is not None and math.isfinite(N) and N > F
    return S <= F + .5 * (N - F) if has_skill else True


def band(values, lo, hi, N=None, credible=None, thin=False):
    """Inside [lo, hi] is at the floor: distance from the middle, ruler half the width."""
    mid, half = (lo + hi) / 2, (hi - lo) / 2
    D = [[abs(v - mid)] for v in values]
    null = abs(N - mid) if N is not None else None
    rec = judge(D, half, null, abs(credible - mid) if credible is not None else None, thin)
    rec.update(value=_r(float(np.nanmedian(values))) if len(values) else None, lo=lo, hi=hi)
    return rec


def zero(values, what='count'):
    """A count that must be zero."""
    v = float(np.nansum(values))
    return dict(status='FLOOR' if v == 0 else 'FAIL', S=_r(v), S90=_r(v), U=_r(v), F=0.0, N=None, z=0.0 if v == 0 else Z_CAP, skill=None, n_pairs=len(values), shape=[len(values)], value=_r(v), note=what)


def no_data(why):
    return dict(status='NO DATA', S=None, S90=None, U=None, F=None, N=None, z=None, skill=None, n_pairs=0, shape=[0, 0], note=why)


def invalid(why):
    return dict(status='INVALID', S=None, S90=None, U=None, F=None, N=None, z=None, skill=None, n_pairs=0, shape=[0, 0], note=why)


def worst(statuses):
    return min(statuses, key=lambda s: RANK[s]) if statuses else 'NO DATA'


def _r(x):
    if x is None:
        return None
    x = float(x)
    return round(x, 5) if math.isfinite(x) else None


def rollup(cells):
    """cells: {sub: record}. A metric is as good as its worst cell, and z its largest."""
    recs = list(cells.values())
    st = worst([c['status'] for c in recs])
    zs = [c['z'] for c in recs if c.get('z') is not None]
    return dict(status=st, z=max(zs) if zs else None)


def compare(a, b):
    """Per cell of two runs with the same shape: paired difference, margin, verdict for that cell."""
    A, B = np.atleast_2d(np.asarray(a['D'], float)), np.atleast_2d(np.asarray(b['D'], float))
    if a.get('F') is None:
        return None
    F = a['F']
    eps = max(.25 * F, F - (a.get('p50') if a.get('p50') is not None else F))
    if A.shape != B.shape:
        d = float(np.nanmedian(B) - np.nanmedian(A))
        lo, hi = d, d
    else:
        D = B - A
        rng = np.random.default_rng(11)
        r, c = D.shape
        boots = []
        for _ in range(400):
            i, j = rng.integers(0, r, r), rng.integers(0, c, c)
            v = D[np.ix_(i, j)]
            v = v[np.isfinite(v)]
            if v.size:
                boots.append(np.median(v))
        lo, hi = (float(np.quantile(boots, .025)), float(np.quantile(boots, .975))) if boots else (0.0, 0.0)
    verdict = 'better' if hi < -eps else 'worse' if lo > eps else 'same'
    return dict(lo=_r(lo), hi=_r(hi), eps=_r(eps), verdict=verdict)
