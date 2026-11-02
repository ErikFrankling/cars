#!/usr/bin/env python3
"""Songdo one-intersection one-day sample: sessions, vehicles, flows, speeds. Argument: zip path."""
import collections as C, csv, io, sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
for n in sorted(z.namelist()):
    ids, cls, tmin, tmax, spd, rows = set(), C.Counter(), None, None, [], 0
    with z.open(n) as f:
        rd = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
        for r in rd:
            rows += 1
            if r["Vehicle_ID"] not in ids: cls[r["Vehicle_Class"]] += 1
            ids.add(r["Vehicle_ID"])
            t = r["Local_Time"]; tmin = t if tmin is None or t < tmin else tmin; tmax = t if tmax is None or t > tmax else tmax
    print(n, "rows", rows, "vehicles", len(ids), tmin, tmax, dict(cls))
print("columns", rd.fieldnames)
