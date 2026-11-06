#!/usr/bin/env python3
"""The engine's rule greens as rung3.py --greens rows, by hour. greens_for_rung3.py NETDIR RUN_AM RUN_PM OUT.csv
Hours 05-14 from the morning run's blocks, 15-04 from the afternoon run's. Controller index to name is sorted(district ids + 'r:' region ids), as prepare.py numbers them.
The engine exports green after 1 s lost per start; rung3.py takes that off again, so 1 s goes back."""
import csv
import re
import sys
from pathlib import Path

B19 = Path('/home/erikf/projects/personal/cars-data/berlin2019')
netdir, am, pm, out = sys.argv[1:5]
pat = re.compile(rb'<tlLogic id="([^"]+)"')
ids = set(m.group(1).decode() for m in pat.finditer((B19 / 'district' / netdir / 'net.net.xml').read_bytes()))
ids |= {'r:' + m.group(1).decode() for m in pat.finditer((B19 / 'raw/sumo.net.xml').read_bytes())}
names = sorted(ids)
BLOCK = lambda h: 0 if 5 <= h < 10 else 1 if 10 <= h < 15 else 2 if 15 <= h < 21 else 3
with open(out, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['ctrl', 'idx', 'gp', 'gq', 'C', 'nst', 'hour'])
    for run, hours in ((am, range(5, 15)), (pm, [*range(15, 24), *range(0, 5)])):
        g = {}
        for r in csv.DictReader(open(Path(run) / 'greens.tsv'), delimiter='\t'):
            g[(int(r['ctrl']), int(r['idx']), int(r['block']))] = (float(r['gp']), float(r['gq']), float(r['C']))
        for h in hours:
            b = BLOCK(h)
            for (c, i, bb), (gp, gq, C) in g.items():
                if bb == b:
                    if gp > 0:
                        gp += 1
                    elif gq > 0:
                        gq += 1
                    w.writerow([names[c], i, round(gp, 2), round(gq, 2), C, 1, h])
print(len(names))
