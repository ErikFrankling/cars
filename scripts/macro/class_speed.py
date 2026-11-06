#!/usr/bin/env python3
"""Space-mean speed by class and hour in the box, model against probe v_hm and v_med, as score.py's blind check, for any hours. class_speed.py PREP RUN H [H...]"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score import CLASSES, DATA

prep, run = Path(sys.argv[1]), Path(sys.argv[2])
hours = [int(x) for x in sys.argv[3:]]
meta = pd.read_csv(prep / 'edge_meta.csv', keep_default_na=False, dtype={'id': str})
box = json.load(open(DATA / 'step0/district.json'))['box']
inbox = (meta.x >= box[0]) & (meta.x < box[2]) & (meta.y >= box[1]) & (meta.y < box[3])
z = np.load(DATA / 'probes/edge_15min.npz', allow_pickle=True)
keys = {str(k): i for i, k in enumerate(z['keys'])}
pn, ne, period = open(run / 'shape.txt').read().split()
pn, ne, period = int(pn), int(ne), float(period)
vs = np.fromfile(run / 'vs.bin', np.float32).reshape(pn, ne)
vm = np.fromfile(run / 'vm.bin', np.float32).reshape(pn, ne)
pph = int(round(3600 / period))
for cl, ts in CLASSES.items():
    idx = np.where(meta.type.isin(ts) & inbox)[0]
    ki = [keys[meta.id[i]] for i in idx if meta.id[i] in keys]
    vol, hm, med = (np.nan_to_num(z[k][ki]) for k in ('vol', 'hm', 'med'))
    out = []
    for h in hours:
        q = slice(h * 4, h * 4 + 4)
        w = vol[:, :, q]
        ps = list(range(h * pph, (h + 1) * pph))
        t = vs[np.ix_(ps, idx)].sum(axis=0)
        d = vm[np.ix_(ps, idx)].sum(axis=0)
        out.append((h, round(float((w * hm[:, :, q]).sum() / max(w.sum(), 1)), 1), round(float((w * med[:, :, q]).sum() / max(w.sum(), 1)), 1), round(3.6 * float(d.sum() / max(t.sum(), 1e-9)), 1)))
    print(cl, 'hour, v_hm, v_med, model:', out)
