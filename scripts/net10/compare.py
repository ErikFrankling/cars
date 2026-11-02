#!/usr/bin/env python3
"""One row per run. Usage: compare.py RUN_DIR ... (each holds summary.csv, trips.csv, edges.csv)"""
import sys, csv, os, statistics as S, collections
for d in sys.argv[1:]:
    rows = list(csv.DictReader(open(d + '/summary.csv')))
    if not rows:
        continue
    last = rows[-1]; demand_end = next((r for r in rows if int(float(r['time'])) >= 3600), last)
    tr = list(csv.DictReader(open(d + '/trips.csv')))
    dur = [float(t['duration']) for t in tr]; loss = [float(t['time_loss']) for t in tr]; ln = [float(t['route_length']) for t in tr]
    tp = collections.Counter()
    for r in csv.DictReader(open(d + '/edges.csv')):
        if r.get('teleports'):
            tp[r['edge']] += int(float(r['teleports']))
    print(f"{os.path.basename(d):11s} t_end {last['time']:>5s} inserted {last['inserted']:>6s} arrived {last['arrived']:>6s} left {last['running']:>5s} tp@3600 {demand_end['teleports']:>5s} tp_end {last['teleports']:>5s} peakrun {max(int(r['running']) for r in rows):>5d} "
          f"dur {S.mean(dur):6.1f} loss {S.mean(loss):6.1f} routeKm {sum(ln)/1000:8.0f} tpedges {len(tp):4d} top3 {[(k[:18], v) for k, v in tp.most_common(3)]}")
