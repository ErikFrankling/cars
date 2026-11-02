#!/usr/bin/env python3
"""The real column in one JSON: pooled cornering by radius and a fit, acceleration, braking, jerk. python3 -I real_summary.py DATA"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

D = Path(sys.argv[1])
ut_t = pd.read_csv(D / 'ut/ut_turns_w1.csv')
ut_t = ut_t[ut_t.kind == 'car']
t = pd.concat([ut_t] + [pd.read_csv(D / f'realout/{n}_w1_turns.csv') for n in ('pneuma', 'swiss', 'foggy')])
t = t[(t.turn_deg > 40) & t.kind.isin(['car', 'taxi'])]
t['bin'] = pd.cut(t.r_core, [5, 8, 10, 13, 16, 20, 25, 30, 40, 60, 100])
out = {'turns_n': len(t), 'turn_table': {}}
for k, g in t.groupby('bin', observed=True):
    out['turn_table'][str(k)] = dict(n=len(g), v=round(g.v_core.median(), 2), v15=round(g.v_core.quantile(.15), 2), v85=round(g.v_core.quantile(.85), 2), ay=round(g.ay_core.median(), 2), ay85=round(g.ay_core.quantile(.85), 2), peak=round(g.ay_peak.median(), 2), peak95=round(g.ay_peak.quantile(.95), 2), peak99=round(g.ay_peak.quantile(.99), 2))
f = lambda r, a, b: a * r ** b
ok = (t.r_core > 6) & (t.r_core < 100) & (t.v_core > 1.5)
p50, _ = curve_fit(f, t.r_core[ok], t.v_core[ok], p0=(1, .5))
out['v_of_r_fit'] = [round(float(x), 3) for x in p50]
out['ay_overall'] = dict(p50=round(t.ay_core.median(), 2), p85=round(t.ay_core.quantile(.85), 2), p95=round(t.ay_core.quantile(.95), 2), peak_p50=round(t.ay_peak.median(), 2), peak_p95=round(t.ay_peak.quantile(.95), 2), peak_p99=round(t.ay_peak.quantile(.99), 2), peak_p999=round(t.ay_peak.quantile(.999), 2))
out['cities'] = {}
for name, st, la, sm in [('braunschweig', 'ut/ut_stops_w1.csv', 'ut/ut_launches_w1.csv', 'ut/ut_samples_w1.npy'), ('athens', 'realout/pneuma_w1_stops.csv', 'realout/pneuma_w1_launches.csv', 'realout/pneuma_w1_samples.npy'), ('switzerland', 'realout/swiss_w1_stops.csv', 'realout/swiss_w1_launches.csv', 'realout/swiss_w1_samples.npy'), ('washington', 'realout/foggy_w1_stops.csv', 'realout/foggy_w1_launches.csv', 'realout/foggy_w1_samples.npy')]:
    s = pd.read_csv(D / st)
    l = pd.read_csv(D / la)
    a = np.load(D / sm)
    v, al, at, j = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    m = v > 0.5
    row = dict(stops=len(s), stop_mean=[round(s['mean'].quantile(q), 2) for q in (.05, .5, .95)], stop_peak=[round((-s.peak).quantile(q), 2) for q in (.05, .5, .95, .99)], launches=len(l), launch_peak=[round(l.peak.quantile(q), 2) for q in (.05, .5, .95)], t5=round(l.t5.median(), 2), d5=round(l.d5.median(), 1), t10=round(l.t10.median(), 2), d10=round(l.d10.median(), 1),
               acc_p50_p95=[round(float(x), 2) for x in np.percentile(al[m & (al > .1)], [50, 95])], dec_p50_p95_p99=[round(float(x), 2) for x in np.percentile(-al[m & (al < -.1)], [50, 95, 99])], jerk_p50_p95=[round(float(x), 2) for x in np.percentile(np.abs(j[m]), [50, 95])],
               share_dec_over={str(x): round(float((al[m] < -x).mean()), 5) for x in (2, 3, 4.5, 6)}, share_acc_over={str(x): round(float((al[m] > x).mean()), 5) for x in (1.5, 2, 2.6)})
    if 'leader_gap' in s:
        row['stop_peak_first_vs_behind'] = [round((-s[s.leader_gap.isna()].peak).median(), 2), round((-s[s.leader_gap.notna()].peak).median(), 2)]
    if name == 'braunschweig':
        k = a[:, 4] == 0
        row['by_speed'] = {f'{lo}-{hi}': dict(acc=[round(float(x), 2) for x in np.percentile(al[k & (v >= lo) & (v < hi) & (al > .1)], [50, 95, 99])], dec=[round(float(x), 2) for x in np.percentile(-al[k & (v >= lo) & (v < hi) & (al < -.1)], [50, 95, 99])], jerk95=round(float(np.percentile(np.abs(j[k & (v >= lo) & (v < hi)]), 95)), 2)) for lo, hi in [(.5, 5), (5, 10), (10, 15), (15, 20)]}
    out['cities'][name] = row
d = pd.read_csv(D / 'ut/ut_dims.csv')
out['dims'] = {k: dict(n=len(g), length=round(g.length.median(), 2), width=round(g.width.median(), 2)) for k, g in d.groupby('kind')}
out['class_share_tracks'] = (d.kind.value_counts() / len(d)).round(3).to_dict()
(D / 'real_summary_w1.json').write_text(json.dumps(out, indent=1, default=float))
print(json.dumps(out, default=float))
