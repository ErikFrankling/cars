#!/usr/bin/env python3
"""Inspect Xuancheng LPR, signal, loop and FCD samples. Pass the dataset directory as argument."""
import csv, collections, os, sys, statistics as st
d = sys.argv[1]
def rows(n):
    with open(os.path.join(d, n), newline="", encoding="utf-8", errors="replace") as f:
        yield from csv.DictReader(f)
for n in ["lpr.csv", "signal.csv", "road_network_stream_level.csv", "road_network_segment_level.csv", "loop.head.csv", "fcd.head.csv"]:
    it = rows(n); h = []
    for i, r in zip(range(3), it): h.append(r)
    print("==", n, os.path.getsize(os.path.join(d, n))); [print("  ", x) for x in h]
L = list(rows("lpr.csv"))
print("lpr rows", len(L), "cols", list(L[0]))
for c in L[0]:
    vals = collections.Counter(r[c] for r in L)
    print(f"  {c}: distinct={len(vals)} top={vals.most_common(3)} min={min(vals)} max={max(vals)}")
S = list(rows("signal.csv"))
print("signal rows", len(S), "cols", list(S[0]))
for c in S[0]:
    vals = collections.Counter(r[c] for r in S)
    print(f"  {c}: distinct={len(vals)} top={vals.most_common(3)} min={min(vals)} max={max(vals)}")
