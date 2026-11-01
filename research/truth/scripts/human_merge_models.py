"""Published merge models against report 14's logit on held-out cars: Lee 2006 and Choudhury 2007 (ch. 5),
both estimated on I-80, scored per car on later I-80 runs and on US-101. Writes human-build/merge_models.json.
Usage: python3 -I research/truth/scripts/human_merge_models.py"""
import json, pathlib, sys
import numpy as np, pandas as pd
from scipy.optimize import minimize
from scipy.special import ndtr, expit

OUT = pathlib.Path('research/truth/human-build')
S = pathlib.Path('research/truth/courtesy')
NODES, WEIGHTS = np.polynomial.hermite_e.hermegauss(9)
WEIGHTS = WEIGHTS / WEIGHTS.sum()


def load(site):
    d = pd.read_csv(S / f'merge_steps_{site}.csv.gz')
    # One second, as both theses estimate on, keeping the crossing.
    d = d[(d.tleft * 10).round().astype(int) % 10 == 0].copy()
    d['changed'] = d.tleft == 0
    for c in ('lag', 'lead'):
        d[c] = d[c].fillna(200.0).clip(upper=200.0)
    d['vT'] = d.vT.fillna(d.vM)
    d['vL'] = d.vL.fillna(d.vM)
    d['aT'] = d.aT.fillna(0.0)
    d['avg'] = 0.5 * (d.vT + d.vL)
    d['d10'] = np.maximum(d.rem.fillna(0), 0) / 10.0
    d['rho'] = 20.0 / np.maximum(d.lag.clip(0, 100) + d.lead.clip(0, 100) + 15.0, 7.5)
    return d


def phi_gap(gap, mu, sigma):
    """P(gap > lognormal critical gap). A gap at or under zero is never accepted."""
    with np.errstate(divide='ignore', invalid='ignore'):
        z = (np.log(np.maximum(gap, 1e-3)) - mu) / sigma
    return np.where(gap > 0, ndtr(z), 1e-6)


LEE = dict(c_lead=0.182, avg=1.45, dv_lead=-0.571, d_lead=1.03, k0_lead=-0.492, k1_lead=0.798, a_lead=-0.00016, s_lead=4.28,
           c_lag=0.379, dvp_lag=0.179, dvn_lag=0.0909, d_lag=0.179, k0_lag=-2.22, k1_lag=2.88, acc_lag=0.0766, a_lag=-0.00011, s_lag=0.91)
# Lee's table prints d_lag 0.179 with a label "dlag, 10 meters", and constant, relative speed terms as above.


def lee_p(d, p, v):
    mu_l = p['c_lead'] + p['avg'] / (1 + np.exp(-np.maximum(0, d.avg - d.vM))) + p['dv_lead'] * np.minimum(0, d.vL - d.vM) + p['d_lead'] * d.d10 / (1 + np.exp(p['k0_lead'] + p['k1_lead'] * v)) + p['a_lead'] * v
    dvt = d.vT - d.vM
    mu_g = p['c_lag'] + p['dvp_lag'] * np.maximum(0, dvt) + p['dvn_lag'] * np.minimum(0, dvt) + p['d_lag'] * d.d10 / (1 + np.exp(p['k0_lag'] + p['k1_lag'] * v)) + p['acc_lag'] * np.maximum(0, d.aT) + p['a_lag'] * v
    return phi_gap(d.lead.values, mu_l.values, abs(p['s_lead'])) * phi_gap(d.lag.values, mu_g.values, abs(p['s_lag']))


CH = dict(c_lead=-0.230, avg=0.521, dv_lead=-0.505, d_lead=1.32, k0_lead=0.420, k1_lead=0.355, s_lead=3.42, a_lead=-0.819,
          c_lag=0.198, dvp_lag=0.208, dvn_lag=0.184, d_lag=0.239, k0_lag=0.0242, k1_lag=0.0180, acc_lag=0.0545, s_lag=0.840, a_lag=-0.0076,
          # initiate courtesy: critical anticipated gap
          c_a=1.82, dv_a=1.82, rho_a=-0.153, d_a=0.244, k0_a=0.449, k1_a=0.360, s_a=0.0106, a_a=-0.231, tau=1.87, tau_sd=1.44,
          # courtesy and forced gap acceptance use the normal slopes with their own constants
          c_clead=-0.582, s_clead=0.0109, a_clead=-0.054, c_clag=-1.23, d_clag=0.439, k1_clag=0.00018, s_clag=0.554, a_clag=-0.0226,
          c_flead=3.11, s_flead=7.95, a_flead=-0.0401, c_flag=-2.53, d_flag=0.439, k1_flag=0.00018, s_flag=0.465, a_flag=-0.0239,
          f0=-6.41, f1=5.43)


def ch_terms(d, p, v, c_lead, s_lead, a_lead, c_lag, d_lag, k1_lag, s_lag, a_lag):
    mu_l = c_lead + p['avg'] * 1.0 / (1 + np.exp(-np.maximum(0, d.avg - d.vM).values)) + p['dv_lead'] * np.minimum(0, d.vL - d.vM).values + p['d_lead'] * d.d10.values / (1 + np.exp(p['k0_lead'] + p['k1_lead'] * v)) + a_lead * v
    dvt = (d.vT - d.vM).values
    mu_g = c_lag + p['dvp_lag'] * np.maximum(0, dvt) + p['dvn_lag'] * np.minimum(0, dvt) + d_lag * d.d10.values / (1 + np.exp(p['k0_lag'] + k1_lag * v)) + p['acc_lag'] * np.maximum(0, d.aT.values) + a_lag * v
    return phi_gap(d.lead.values, mu_l, abs(s_lead)) * phi_gap(d.lag.values, mu_g, abs(s_lag))


def ch_car_like(d, p, v):
    """Forward over the latent state of one car: normal, courtesy, forced. Stays until the adjacent gap changes."""
    n = len(d)
    pn = ch_terms(d, p, v, p['c_lead'], p['s_lead'], p['a_lead'], p['c_lag'], p['d_lag'], p['k1_lag'], p['s_lag'], p['a_lag'])
    pc = ch_terms(d, p, v, p['c_clead'], p['s_clead'], p['a_clead'], p['c_clag'], p['d_clag'], p['k1_clag'], p['s_clag'], p['a_clag'])
    pf = ch_terms(d, p, v, p['c_flead'], p['s_flead'], p['a_flead'], p['c_flag'], p['d_flag'], p['k1_flag'], p['s_flag'], p['a_flag'])
    # Probability the anticipated gap is acceptable, over the anticipation time. Accelerations of the lead are unknown: zero.
    taus = np.maximum(np.array([p['tau'] + p['tau_sd'] * x for x in (-1.2, 0.0, 1.2)]), 0.0)
    dv = (d.vL - d.vT).values
    base = d.lead.clip(lower=0).values + d.lag.clip(lower=0).values
    pa = np.zeros(n)
    for tau in taus:
        ag = base + 5.0 + dv * tau + 0.5 * (0.0 - d.aT.values) * tau * tau
        mu = p['c_a'] + p['dv_a'] * np.maximum(0, (d.vT - d.vM).values) + p['rho_a'] * d.rho.values + p['d_a'] * d.d10.values / (1 + np.exp(p['k0_a'] + p['k1_a'] * v)) + p['a_a'] * v
        pa += phi_gap(ag, mu, max(abs(p['s_a']), 0.1)) / len(taus)
    pfi = 1.0 / (1 + np.exp(-(p['f0'] + p['f1'] * v)))
    same = np.r_[False, (d['T'].values[1:] == d['T'].values[:-1]) & (d['Lead'].values[1:] == d['Lead'].values[:-1])]
    st = np.array([1.0, 0.0, 0.0])
    y = d.changed.values
    like = 1.0
    hazards = np.zeros(n)
    for i in range(n):
        if not same[i]:
            st = np.array([st.sum(), 0.0, 0.0])
        # From normal: normal merge, else initiate courtesy, else initiate forced.
        p_change_n = pn[i]
        to_c = (1 - pn[i]) * pa[i]
        to_f = (1 - pn[i]) * (1 - pa[i]) * pfi
        change = st[0] * (p_change_n + to_c * pc[i] + to_f * pf[i]) + st[1] * pc[i] + st[2] * pf[i]
        total = st.sum()
        hazards[i] = change / max(total, 1e-300)
        if y[i]:
            like = change
            break
        st = np.array([st[0] * (1 - p_change_n - to_c - to_f), st[1] * (1 - pc[i]) + st[0] * to_c * (1 - pc[i]), st[2] * (1 - pf[i]) + st[0] * to_f * (1 - pf[i])])
    return like


R14 = np.array([-5.5, -6.19 / 50, 4.84 / 10, -1.04 / 3, -0.37 / 3, 0.28 / 10, 0.24 / 10])


def r14_x(d):
    return np.c_[np.ones(len(d)), d.rem.fillna(0).clip(lower=0), d.vM, d.vM - d.vL, d.vT - d.vM, d.lag.clip(-20, 100), d.lead.clip(-20, 100)]


def r14_p(x, b):
    return expit(x @ b)


def car_ll_static(d, p_fn):
    """Mean over drivers of the likelihood of one car's sequence."""
    y = d.changed.values
    like = 0.0
    for v, w in zip(NODES, WEIGHTS):
        p = np.clip(p_fn(d, v), 1e-9, 1 - 1e-9)
        like += w * np.exp(np.log1p(-p[~y]).sum() + np.log(p[y]).sum())
    return np.log(max(like, 1e-300))


def score(data, model):
    out = []
    for _, g in data.groupby(['run', 'id']):
        out.append(model(g))
    return np.array(out)


def ch_ll(g, p):
    like = 0.0
    for v, w in zip(NODES, WEIGHTS):
        like += w * ch_car_like(g, p, v)
    return np.log(max(like, 1e-300))


def fit_logit(tr):
    x = r14_x(tr)
    y = tr.changed.values
    def nll(b):
        q = np.clip(expit(x @ b), 1e-9, 1 - 1e-9)
        return -(y * np.log(q) + (~y) * np.log(1 - q)).sum()
    return minimize(nll, R14, method='L-BFGS-B').x


LEE_FIT_KEYS = ['c_lead', 'avg', 'dv_lead', 'd_lead', 'k0_lead', 's_lead', 'c_lag', 'dvp_lag', 'dvn_lag', 'd_lag', 'k0_lag', 'acc_lag', 's_lag']


def fit_lee(tr):
    groups = [g for _, g in tr.groupby(['run', 'id'])]
    def nll(x):
        p = dict(LEE, **dict(zip(LEE_FIT_KEYS, x)))
        return -sum(car_ll_static(g, lambda d, v: lee_p(d, p, v)) for g in groups)
    r = minimize(nll, [LEE[k] for k in LEE_FIT_KEYS], method='Nelder-Mead', options=dict(maxiter=350, xatol=1e-2, fatol=0.5))
    return dict(LEE, **dict(zip(LEE_FIT_KEYS, r.x)))


def main():
    i80 = load('i-80')
    us = load('us-101')
    runs = sorted(i80.run.unique())
    print('i-80 cars by run', i80.groupby('run').id.nunique().to_dict(), 'us-101', us.groupby(['run', 'id']).ngroups, flush=True)
    # Lee and Choudhury used the 5:00-5:30 set. Hold out the 4:00-4:15 run for refits fairly: train where they did not fit.
    tr = i80[i80.run == runs[0]]
    te = i80[i80.run != runs[0]]
    b = fit_logit(tr)
    bb = fit_logit(i80)
    logit = lambda g, c: car_ll_static(g, lambda d, v: r14_p(r14_x(d), c))
    res = {}
    lee_fit = fit_lee(tr)
    models = {
        'report14_start_logit_refit_train': lambda g: logit(g, b),
        'lee2006_published_I80': lambda g: car_ll_static(g, lambda d, v: lee_p(d, LEE, v)),
        'lee2006_form_refit_train': lambda g: car_ll_static(g, lambda d, v: lee_p(d, lee_fit, v)),
        'choudhury2007_published_I80': lambda g: ch_ll(g, CH),
    }
    for name, m in models.items():
        res[name] = {}
        for lab, data in (('i80_later_runs', te), ('us101', us), ('i80_train_run', tr)):
            ll = score(data, m)
            res[name][lab] = dict(cars=len(ll), ll_per_car=float(ll.mean()), median=float(np.median(ll)))
        print(name, res[name], flush=True)
    # Paired bootstrap on US-101, each model against the logit.
    us_ll = {n: score(us, m) for n, m in models.items()}
    te_ll = {n: score(te, m) for n, m in models.items()}
    rng = np.random.default_rng(1)
    base = 'report14_start_logit_refit_train'
    res['paired_vs_logit'] = {}
    for n in models:
        if n == base:
            continue
        for lab, table in (('us101', us_ll), ('i80_later_runs', te_ll)):
            diff = table[n] - table[base]
            boot = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(2000)]
            res['paired_vs_logit'][f'{n}|{lab}'] = dict(mean=float(diff.mean()), lo=float(np.percentile(boot, 2.5)), hi=float(np.percentile(boot, 97.5)))
    res['lee_refit_params'] = lee_fit
    res['logit_train'] = b.tolist()
    OUT.mkdir(exist_ok=True, parents=True)
    (OUT / 'merge_models.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res['paired_vs_logit'], indent=1))


main()
