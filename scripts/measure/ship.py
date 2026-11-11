"""Round 5, part 2: the decision rule's second branch (F836). Candidates fitted on P1 + P6 with each driver's past factor
(round 4's sets), P2 left out of the fit; every pattern scored as in round 4; the system-scale patterns filter, P1 ranks.
Recordings not held out (HOLDOUT.md).

    python3 -I scripts/measure/ship.py fit f e j        # -> research/truth/measure/ship.json
"""
import os, sys, json, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
RES = os.path.join(HERE, '..', '..', 'research', 'truth', 'measure')
OUT = os.path.join(RES, os.environ.get('SHIP_OUT', 'ship.json'))
import fit_driver as FD
import structure as ST
import personal as PS

DT = 0.2


def save(key, val):
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    out[key] = val
    json.dump(out, open(OUT, 'w'), indent=1)


def c_j(p, v, g, vl, al, x):
    """(f) with a launch gain: below 6.5 m/s while the leader pulls away, K_1 replaces K and the leader's acceleration share
    is dropped (F801: launches show none)."""
    K, g1, ca, kg, kp, K1 = p
    launch = (v < 6.5) & (vl > v)
    clos = np.minimum(vl - v, FD.DV_MAX) / (np.maximum(g, 0.0) + g1)
    return np.where(launch, K1 * clos, K * clos + ca * al) + ST.band(v, g, x['f'], kg, kp)


ST.CANDS['j'] = dict(fn=c_j, names=['K', 'g_1', 'c_a', 'k_g', 'k_p', 'K_1'], p0=[7.05, 4.04, 0.33, 0.34, 0.086, 9.0], lo=[0] * 6, hi=[30, 40, 2, 3, 1, 40])
LAUNCH_W = math.sqrt(5 / 3) if os.environ.get('SHIP_W') == '1' else 1.0   # F837
SYSTEM = ('P5', 'P6', 'P7', 'P8', 'P9', 'P12')


def objective(cand, p, FS, scale):
    r = []
    for n in ST.FIT_TABLES:
        q = FS['next'][n]
        r.append(ST._soft((PS.next_pred(cand, p, q) - q['y']) / scale[f'next {n}']) / math.sqrt(len(q['y'])))
    for ds in ST.LAUNCH_SITES:
        e, _ = ST.w_err(cand, p, FS['launch'][ds])
        z = e[:, [int(t / DT) for t in ST.LAUNCH_AT]] / scale[f'launch {ds}']
        r.append(ST._soft(z.ravel()) / math.sqrt(z.size) * LAUNCH_W)
    return np.concatenate(r)


def fit(cand, FS, sc_):
    from scipy.optimize import least_squares
    C = ST.CANDS[cand]
    r = least_squares(lambda q: objective(cand, list(q), FS, sc_), C['p0'], bounds=(C['lo'], C['hi']), diff_step=1e-3, max_nfev=300)
    return list(map(float, r.x)), float(np.sum(r.fun ** 2)), int(r.status)


def p1_ratio(sc, ref):
    return float(np.mean([sc[f'P1 {n}']['crps'] / ref[f'P1 {n}']['crps'] for n in ST.FIT_TABLES]))


def run(cands):
    FS0 = PS.load4()
    FS = {m: PS.with_f(FS0, m) for m in ('past', 'random')}
    sc_ = PS.scales(FS['past'])
    ref = json.load(open(os.path.join(RES, 'personal.json')))['twin']['round2']
    res = json.load(open(OUT)).get('fit', {}) if os.path.exists(OUT) else {}
    for cand in cands:
        p, obj, status = fit(cand, FS['past'], sc_)
        pp = PS.platoon_patterns(cand, p)
        r = dict(params={k: round(v, 4) for k, v in zip(ST.CANDS[cand]['names'], p)}, objective=round(obj, 4), status=status)
        for m in FS:
            sc = {**PS.score_data(cand, p, FS[m]), **pp}
            miss = PS.verdict(sc, ref[m])
            r[m] = dict(scores=sc, misses=miss, system_misses=[x for x in miss if x.startswith(SYSTEM)],
                        p1_beats_null=all(sc[f'P1 {n}']['crps'] < sc[f'P1 {n}']['null'] for n in ST.FIT_TABLES),
                        p1_ratio_to_round2=round(p1_ratio(sc, ref[m]), 4))
        res[cand] = r
        save('fit', res)
        print(cand, r['params'], 'obj', r['objective'], '| system misses', r['past']['system_misses'], '| all misses', len(r['past']['misses']),
              r['past']['misses'], '| P1 ratio', r['past']['p1_ratio_to_round2'], flush=True)


if __name__ == '__main__':
    if sys.argv[1] == 'fit':
        run(sys.argv[2:] or ['f', 'e', 'j'])


def seeds(cand='j', src='ship_jw.json', n=20):
    """F838: P6 with random personal factors over n draws."""
    p = [json.load(open(os.path.join(RES, src)))['fit'][cand]['params'][k] for k in ST.CANDS[cand]['names']]
    FS0 = PS.load4()
    rows = {}
    for s in range(n):
        FS = PS.with_f(FS0, 'random', seed=s)
        for ds in ST.LAUNCH_SITES:
            e, _ = ST.w_err(cand, p, FS['launch'][ds])
            for t in (2, 4, 8):
                rows.setdefault(f'{ds} {t}s', []).append(float(np.median(-e[:, int(t / DT)])))
    lim = {2: 0.5, 4: 0.5, 8: 1.0}
    out = {k: dict(mean=round(float(np.mean(v)), 3), sd=round(float(np.std(v)), 3), share_inside=round(float(np.mean(np.abs(v) <= lim[int(k.split()[-1][:-1])])), 2),
                   inside_on_mean=bool(abs(np.mean(v)) <= lim[int(k.split()[-1][:-1])])) for k, v in rows.items()}
    print(json.dumps(out, indent=1))
    save('F838_random_f_launch_seeds', out)


if __name__ == '__main__' and sys.argv[1] == 'seeds':
    seeds()
