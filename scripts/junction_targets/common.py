"""Shared pieces of report 25: output rows, censored gap fit, quantile helpers. Same code for real and simulated tracks."""
import csv
import json
import os
import pathlib

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm

os.environ.setdefault('OMP_NUM_THREADS', '2')
OUT = pathlib.Path(os.environ.get('JT_OUT', '/home/erikf/projects/personal/cars-data/truth/junction-25'))
OUT.mkdir(parents=True, exist_ok=True)
COLS = ['metric', 'junction_type', 'site', 'value', 'spread', 'source', 'split', 'unit', 'n', 'spread_kind', 'lo', 'hi',
        'movement', 'bench_id', 'grade', 'note']


class Rows:
    def __init__(self, name):
        self.name, self.r = name, []

    def add(self, metric, jtype, site, value, spread, source, split, unit, n, spread_kind, lo=None, hi=None, movement='all',
            bench_id='', grade='MEASURED', note=''):
        def f(x):
            if x is None or (isinstance(x, float) and not np.isfinite(x)):
                return ''
            return round(float(x), 4) if isinstance(x, (float, np.floating)) else x
        self.r.append(dict(metric=metric, junction_type=jtype, site=site, value=f(value), spread=f(spread), source=source, split=split,
                           unit=unit, n=int(n), spread_kind=spread_kind, lo=f(lo), hi=f(hi), movement=movement, bench_id=bench_id,
                           grade=grade, note=note))

    def write(self):
        with open(OUT / f'rows_{self.name}.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, COLS)
            w.writeheader()
            w.writerows(self.r)
        print(self.name, 'rows', len(self.r), flush=True)


def gap_mle(acc, rmax):
    """Censored lognormal of report 05: the critical gap lies between the largest rejected and the accepted gap."""
    acc = np.maximum(np.asarray(acc, float), .05)
    r = np.asarray(rmax, float)
    r = np.minimum(r, acc * .999)

    def nll(p):
        s = np.exp(p[1])
        fa = norm.cdf((np.log(acc) - p[0]) / s)
        fr = np.where(r > 0, norm.cdf((np.log(np.maximum(r, 1e-3)) - p[0]) / s), 0.)
        return -np.sum(np.log(np.maximum(fa - fr, 1e-9)))
    b = minimize(nll, [1.2, -1.2], method='Nelder-Mead', options=dict(maxiter=600, xatol=1e-3, fatol=1e-2))
    return float(np.exp(b.x[0])), float(np.exp(b.x[1]))


def raff(acc, rej):
    g = np.arange(.5, 15, .05)
    a = np.searchsorted(np.sort(acc), g)
    s = np.sort(rej)
    r = len(s) - np.searchsorted(s, g)
    return float(g[np.argmin(np.abs(a - r))])


def boot_gap(acc, rmax, groups, n=40, seed=20261102):
    """Cluster bootstrap by flight, so one flight's mood counts once."""
    rng = np.random.default_rng(seed)
    u = np.unique(groups)
    idx = {g: np.flatnonzero(groups == g) for g in u}
    out = []
    for _ in range(n):
        pick = np.concatenate([idx[g] for g in rng.choice(u, len(u))])
        out.append(gap_mle(acc[pick], rmax[pick])[0])
    return np.percentile(out, [2.5, 97.5])


def q(x, p):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(np.percentile(x, p)) if len(x) else float('nan')


def spread_of(x):
    """Half of the p10 to p90 width: the spread column, in the metric's own unit."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float((np.percentile(x, 90) - np.percentile(x, 10)) / 2) if len(x) > 1 else float('nan')


def dump(name, o):
    (OUT / f'{name}.json').write_text(json.dumps(o, indent=1, default=float))


GAP_BINS = (1, 2, 3, 4, 5, 6, 8, 10, 15)


def gap_rows(add, A, bid):
    """The critical gap depends heavily on who is counted, so every version is reported, plus the plain acceptance curve. A is one row per first-in-line car with acc, rmax, nrej and stopped."""
    x = A[A['acc'].notna()]
    rej = x[x['nrej'] > 0]
    if len(rej) >= 25:
        add('critical_gap_those_who_rejected', gap_mle(rej['acc'].values, rej['rmax'].values)[0], None, 's', len(rej), 'none', bench_id=bid, note='only drivers who let at least one car go')
    st = x[x['stopped'] & (x['nrej'] > 0)]
    if len(st) >= 25:
        add('critical_gap_stopped_and_rejected', gap_mle(st['acc'].values, st['rmax'].values)[0], None, 's', len(st), 'none', bench_id=bid, note='stopped below 1 m/s and let a car go. Closest to how design guides define it')
    for lo, hi in zip(GAP_BINS[:-1], GAP_BINS[1:]):
        na = int(((x['acc'] >= lo) & (x['acc'] < hi)).sum())
        nr = int(((rej['rmax'] >= lo) & (rej['rmax'] < hi)).sum())
        if na + nr >= 15:
            add('gap_acceptance_share', na / (na + nr), float(np.sqrt(na * nr / (na + nr)) / (na + nr)), 'share', na + nr, 'standard_error', movement=f'gap_{lo}_{hi}', bench_id=bid, note='accepted gaps over accepted plus largest rejected, first-in-line cars. Less fragile than one critical gap')
