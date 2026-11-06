#!/usr/bin/env python3
"""Member edges of each real jam place, which real_jams.csv counts but doesn't list. Same places as scripts/reality/jams.py, joined on
(threshold, period, head_edge). Writes cars-data/berlin2019/macro/real_jam_edges.csv, outside the repo since it is per-edge probe output."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reality'))
import jams as J
import pandas as pd

rows = []
for frac, name in ((1 / 3, 'third'), (.5, 'half')):
    ep = J.episodes(J.jam_mask(frac))
    for p in J.places(ep, range(J.D), 2):
        d = J.describe(p, ep, name)
        rows.append(dict(threshold=name, period=d['period'], head_edge=d['head_edge'], tier=d['tier'], in_district=d['in_district'], n=len(p['edges']), edge_ids=' '.join(J.KEYS[i] for i in p['edges'])))
pd.DataFrame(rows).to_csv(J.B19 / 'macro/real_jam_edges.csv', index=False)
print(len(rows))
