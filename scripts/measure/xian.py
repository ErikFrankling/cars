"""F861, F862: SinD Xi'an (held out until round 5, HOLDOUT.md), opened once for the round 5 law (MODEL.md).

F861: queue launches cut by queues.py exactly as the P6 sites (follower stands, leader passes 1 m/s), rolled out 8 s with the
shipped law's twin (structure.roll, candidate j, the kernel's order; kernel against twin F839) behind the recorded leader.
F862: the first car of a queue at green, sind.py's method: time from green to 1.5 m/s and its peak acceleration.

    python3 -I scripts/measure/xian.py          # -> research/truth/measure/xian.json
"""
import os, sys, json
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
RES = os.path.join(HERE, '..', '..', 'research', 'truth', 'measure')
import queues as Q
import structure as ST
import ship  # registers candidate j
import sind as SD

CITY = 'Xi_an'
TRACKS = 'Xi_an_Xi_an_412_m1_Veh_smoothed_tracks.csv'
LIGHTS = 'Xi_an_Xi_an_412_m1_Traffic_Lights.csv'
rng = np.random.default_rng(861)


def launches():
    f, hz = Q.frames_sind(TRACKS)
    Q.events(Q.enrich(f, hz), hz, f'SinD {CITY}')
    d = pd.concat(Q.LAUNCH); Q.LAUNCH.clear()
    os.makedirs(Q.WORK, exist_ok=True)
    d.to_csv(f'{Q.WORK}/xian_launch.csv', index=False)
    return d


def events(d):
    ev = []
    for e, g in d.groupby('ev'):
        g = g.sort_values('t'); t = g.t.to_numpy(float)
        tt = np.arange(t[0], t[-1] + 1e-6, ST.DT)
        if len(tt) < 12:
            continue
        cols = {c: np.interp(tt, t, g[c].to_numpy(float)) for c in ('v', 'gap', 'vl', 'al')}
        cols['lok'] = np.interp(tt, t, g.lok.to_numpy(float)) > 0.999
        ev.append((e, cols))
    return ev


def main():
    p = [json.load(open(os.path.join(RES, 'ship_jw.json')))['fit']['j']['params'][k] for k in ST.CANDS['j']['names']]
    out = {}
    d = launches()
    R = ST.launch_rollouts(events(d))
    n = len(R['v0'])
    out['launches'] = int(n)
    if n >= 5:
        res = {}
        for mode in ('f = 1', 'random f, 20 draws'):
            rows = {t: [] for t in (2, 4, 8)}
            draws = 1 if mode == 'f = 1' else 20
            for s in range(draws):
                w = dict(R)
                w['f'] = np.ones(n) if mode == 'f = 1' else np.exp(0.27 * np.random.default_rng(9000 + s).standard_normal(n))
                e, _ = ST.w_err('j', p, w)
                for t in rows:
                    ge = -e[:, int(t / ST.DT)]
                    rows[t].append(ge)
            r = {}
            for t, gl in rows.items():
                med = float(np.mean([np.median(g) for g in gl]))
                g0 = gl[0]
                bs = [np.median(g0[rng.integers(0, n, n)]) for _ in range(400)]
                r[f'{t}s'] = [round(med, 2), round(float(np.percentile(bs, 2.5)), 2), round(float(np.percentile(bs, 97.5)), 2)]
            r['inside_P6'] = all(abs(r[f'{t}s'][0]) <= lim for t, lim in ((2, 0.5), (4, 0.5), (8, 1.0)))
            res[mode] = r
        out['F861_gap_error_m'] = res
    # F862: first car at green
    SD.REC[CITY] = (TRACKS, LIGHTS)
    try:
        o, r = SD.analyse(CITY)
    finally:
        SD.REC.pop(CITY, None)
    first = r[r.pos == 1]
    out['F862_first_car'] = dict(n=int(len(first)), start_delay_to_1_5_m_s=SD.boot_median(first.start_delay.dropna()),
                                 peak_acc=SD.boot_median(first.peak_acc.dropna()),
                                 saturation_headway_pos4plus=SD.boot_median(r[r.pos >= 4].headway.dropna()) if (r.pos >= 4).sum() >= 5 else None,
                                 approaches=o)
    print(json.dumps(out, indent=1, default=str))
    json.dump(out, open(os.path.join(RES, 'xian.json'), 'w'), indent=1, default=str)


if __name__ == '__main__':
    main()
