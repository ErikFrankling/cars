#!/usr/bin/env python3
"""Join single-hour model A runs into one day for score.py. merge_hours.py OUT HOUR=RUN..."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
vs = vm = None
A, E = [], []
for arg in sys.argv[2:]:
    h, run = arg.split('=', 1)
    h, run = int(h), Path(run)
    pn, ne, period = open(run / 'shape.txt').read().split()
    pn, ne = int(pn), int(ne)
    a = np.fromfile(run / 'vs.bin', np.float32).reshape(pn, ne)
    b = np.fromfile(run / 'vm.bin', np.float32).reshape(pn, ne)
    if vs is None:
        vs, vm = np.zeros_like(a), np.zeros_like(b)
        shape = f'{pn} {ne} {period}\n'
    vs[h] += a[h]
    vm[h] += b[h]
    x = pd.read_csv(run / 'arcs.tsv', sep='\t')
    A.append(x[x.hour == h])
    y = pd.read_csv(run / 'edge_hour.tsv', sep='\t')
    E.append(y[y.hour == h])
vs.tofile(out / 'vs.bin')
vm.tofile(out / 'vm.bin')
(out / 'shape.txt').write_text(shape)
pd.concat(A).to_csv(out / 'arcs.tsv', sep='\t', index=False)
pd.concat(E).to_csv(out / 'edge_hour.tsv', sep='\t', index=False)
print('hours', len(A))
