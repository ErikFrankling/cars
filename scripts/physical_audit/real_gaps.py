#!/usr/bin/env python3
"""Time gap by speed and standing spacing from the cached following pairs of report 05.

Time gap is (front-to-front spacing - 5 m) / follower speed, report 05's convention, because tracker lengths are unreliable.
Sampled once a second. python3 -I real_gaps.py FILE... --out f.json
"""
import argparse
import json
from pathlib import Path

import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument('files', nargs='+')
    p.add_argument('--out', required=True)
    a = p.parse_args()
    res = {}
    for f in a.files:
        z = np.load(f)
        cc, vf = z['cc'], z['vf']
        keep = np.arange(len(cc)) % 10 == 0
        if 'autof' in z.files:
            keep &= z['autof'] == 0
        cc, vf = cc[keep], vf[keep]
        name = Path(f).stem.replace('pairs_', '')
        tab = {}
        for lo, hi in [(1, 5), (5, 10), (10, 15), (15, 20), (20, 25), (25, 30), (30, 40)]:
            q = (vf >= lo) & (vf < hi) & (cc < 105)
            if q.sum() > 200:
                tg = (cc[q] - 5) / vf[q]
                tab[f'{lo}-{hi}'] = dict(n=int(q.sum()), p5=round(float(np.percentile(tg, 5)), 2), p25=round(float(np.percentile(tg, 25)), 2), p50=round(float(np.percentile(tg, 50)), 2), p95=round(float(np.percentile(tg, 95)), 2))
        st = vf < 0.1
        res[name] = dict(time_gap=tab, stand_spacing=dict(n=int(st.sum()), p5=round(float(np.percentile(cc[st], 5)), 2), p50=round(float(np.percentile(cc[st], 50)), 2), p95=round(float(np.percentile(cc[st], 95)), 2)) if st.sum() > 50 else None)
        print(name, json.dumps(res[name])[:300], flush=True)
    Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
