#!/usr/bin/env python3
"""Assignment's pop.csv.gz to a route file with the same types and departures. pop_routes.py POP OUT [ROUTES_FOR_VTYPES]"""
import csv
import gzip
import sys

csv.field_size_limit(10**8)
src = sys.argv[3] if len(sys.argv) > 3 else '/home/erikf/projects/personal/cars-data/berlin2019/district/m10/routes_f05.rou.gz'
head = []
with gzip.open(src, 'rt') as f:
    for line in f:
        if '<vehicle' in line:
            break
        head.append(line)
with gzip.open(sys.argv[2], 'wt', compresslevel=1) as o:
    o.writelines(head)
    n = 0
    for r in csv.DictReader(gzip.open(sys.argv[1], 'rt')):
        o.write(f'  <vehicle id="{r["vehicle"] or r["id"]}" type="{r["vtype"]}" depart="{r["depart_s"]}" departLane="best"><route edges="{r["route"]}"/></vehicle>\n')
        n += 1
    o.write('</routes>\n')
print(n, 'written')
