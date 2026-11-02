#!/usr/bin/env python3
"""Recipe step 4 input, unfitted. Every vehicle leg of MATSim v6.4's 10% experienced plans.

gzip -dc plans | grep -E '<person id|<leg mode|<route ' | python3 -I extract_legs.py OUT.tsv.gz STATS.json
Only legs on the road network are kept: car, trucks, freight and vans. Ride, walk, bike and pt are counted.
"""
import collections
import gzip
import json
import re
import sys

person = re.compile(r'<person id="([^"]+)"')
leg = re.compile(r'<leg mode="([^"]+)" dep_time="([^"]+)" trav_time="([^"]+)"')
route = re.compile(r'<route type="([^"]+)" start_link="([^"]+)" end_link="([^"]+)" trav_time="[^"]*" distance="([^"]+)"[^>]*>([^<]*)')


def secs(t):
    h, m, s = t.split(':')
    return int(h) * 3600 + int(m) * 60 + int(float(s))


stats = collections.defaultdict(lambda: [0, 0.0])
out = gzip.open(sys.argv[1], 'wt', compresslevel=4)
out.write('person\tleg\tmode\tdep\ttrav\tdist\tlinks\n')
p, mode, dep, trav, n = '', None, 0, 0, 0
for line in sys.stdin:
    m = person.search(line)
    if m:
        p, n = m[1], 0
        continue
    m = leg.search(line)
    if m:
        mode, dep, trav = m[1], secs(m[2]), secs(m[3])
        continue
    m = route.search(line)
    if m and mode:
        dist = float(m[4]) if m[4] not in ('NaN', '') else 0.0
        stats[mode][0] += 1
        stats[mode][1] += dist / 1000
        if m[1] == 'links' and m[5].strip():
            out.write(f'{p}\t{n}\t{mode}\t{dep}\t{trav}\t{dist:.0f}\t{m[5].strip()}\n')
            n += 1
        mode = None
out.close()
json.dump({k: dict(legs=v[0], km=round(v[1])) for k, v in stats.items()}, open(sys.argv[2], 'w'), indent=1)
print(json.dumps({k: dict(legs=v[0], km=round(v[1])) for k, v in stats.items()}))
