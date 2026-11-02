#!/usr/bin/env python3
"""Factor f of the 10% sample, streamed so it takes no memory: clone_routes.py DIR F. f copies, departures spread +-150 s.
Cars sorts trips by departure when it loads them, so the file need not be sorted."""
import gzip
import random
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import B19, DISTRICT

d, fac = DISTRICT / sys.argv[1], int(sys.argv[2])
rng = random.Random(20190515 + fac)
pat = re.compile(r'id="([^"]+)" type="([^"]+)" depart="([^"]+)"')
with gzip.open(d / 'routes_f01.rou.gz', 'rt') as f, gzip.open(d / f'routes_f{fac:02}.rou.gz', 'wt', compresslevel=1) as o:
    for line in f:
        m = pat.search(line)
        if not m:
            o.write(line)
            continue
        for c in range(fac):
            t = (float(m[3]) + rng.uniform(-150, 150)) % 86400
            o.write(pat.sub(f'id="{m[1][:-2]}.{c}" type="{m[2]}" depart="{t:.1f}"', line, count=1))
