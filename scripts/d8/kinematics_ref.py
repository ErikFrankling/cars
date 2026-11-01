#!/usr/bin/env python3
"""Reference values from ci_model.py for the kinematics test in coord.rs (build spec, test 1)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'research/truth/scripts'))
import ci_model as M

a, b, vmax = 2.6, 2.5, 13.89
rows = []
for d in (0.0, 0.5, 3.0, 8.0, 20.0, 45.0, 90.0, 180.0, 300.0):
    for v in (0.0, 0.5, 2.0, 5.0, 8.0, 11.0, 13.89):
        for ve in (0.0, 1.302, 2.778, 5.0, 8.334, 13.89):
            te = M.earliest(d, v, ve, vmax, a, b)
            tl = M.latest(d, v, ve, a, b)
            rows.append(dict(d=d, v=v, ve=ve, te=-1.0 if te is None else te, tl=-1.0 if tl is None else (1e30 if tl == float('inf') else tl)))


class Lane:
    speed = 13.89


class Mov:
    vm = 6.52
    P = 12.0
    from_lane = Lane


cfg = dict(a=a)
times = []
for v0 in (0.0, 1.3, 2.6, 5.2, 6.52):
    for s in (0.0, 0.5, 4.0, 11.9, 12.0, 15.0, 30.0, 80.0):
        times.append(dict(v0=v0, s=s, t=M.travel_time(Mov, v0, s, cfg)))
out = ROOT / 'research/truth/fig/d8/kinematics.json'
out.write_text(json.dumps(dict(rows=rows, times=times, vm=Mov.vm, p=Mov.P, v_after=Lane.speed, a=a, b=b, vmax=vmax)))
print(len(rows), len(times))
